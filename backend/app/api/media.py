"""Photo delivery: albums, previews, and gated downloads.

Two separate questions, answered in order:

1. **Can this be seen?** A published album is readable by anyone - the paid
   bucket is gated on *download*, not on looking, so this stays a portfolio.
2. **Can this be taken?** Free photos need a registered user; paid photos need
   a subscription to that artist. See services/access.py, which owns the rule.

Previews are separate files from the originals, so a public page never streams
somebody's full-resolution work.
"""

from __future__ import annotations

import mimetypes
import os
import re
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.api.deps import AuthUser, get_current_user, get_optional_user
from app.api.responses import ApiError, msg, respond
from app.db.session import get_db
from app.models import Album, ArtistProfile, Photo
from app.schemas.media import AlbumDetail, AlbumSummary, PhotoOut
from app.services import access, storage

router = APIRouter(prefix="/api/media", tags=["media"])

_ALBUM_COLUMNS = (
    Album.id,
    Album.slug,
    Album.title,
    Album.credit,
    Album.description,
    Album.access,
    Album.artist_id,
)
# Joined in so an album knows whose it is. The profile row is optional - an
# album can belong to someone who never filled one in.
_ARTIST_COLUMNS = (
    ArtistProfile.display_name.label("artist_name"),
    ArtistProfile.slug.label("artist_slug"),
    # Carried on the album rather than looked up separately, because the grid
    # sizes itself per album and that is the only place it is needed.
    ArtistProfile.grid_columns.label("artist_columns"),
)
_PHOTO_COLUMNS = (
    Photo.id,
    Photo.title,
    Photo.position,
    Photo.filename,
    Photo.preview_filename,
    Photo.width,
    Photo.height,
)


def _photo_count():
    """A correlated count, so listing albums doesn't cost a query each."""
    return (
        select(func.count(Photo.id)).where(Photo.album_id == Album.id).scalar_subquery()
    )


def _album_columns_with_count():
    return (*_ALBUM_COLUMNS, *_ARTIST_COLUMNS, _photo_count().label("photo_count"))


def _with_artist(stmt):
    """Left-join the artist's profile so an album carries its owner's name."""
    return stmt.join(
        ArtistProfile, ArtistProfile.user_id == Album.artist_id, isouter=True
    )


def _album_summary(row, can_download: bool) -> dict:
    return AlbumSummary(
        id=row.id,
        slug=row.slug,
        title=row.title,
        credit=row.credit,
        description=row.description,
        access=row.access,
        artist_name=row.artist_name,
        artist_slug=row.artist_slug,
        artist_columns=row.artist_columns,
        photo_count=row.photo_count,
        can_download=can_download,
        download_url=f"/api/media/albums/{row.slug}/download",
    ).model_dump(by_alias=True, mode="json")


def _album_detail(row, can_download: bool) -> dict:
    return AlbumDetail(
        id=row.id,
        slug=row.slug,
        title=row.title,
        credit=row.credit,
        description=row.description,
        access=row.access,
        artist_name=row.artist_name,
        artist_slug=row.artist_slug,
        artist_columns=row.artist_columns,
        can_download=can_download,
        download_url=f"/api/media/albums/{row.slug}/download",
    ).model_dump(by_alias=True, mode="json")


def _photo(photo, can_download: bool) -> dict:
    # The preview is what a page loads; the original is only ever fetched by a
    # download.
    return PhotoOut(
        id=photo.id,
        title=photo.title,
        position=photo.position,
        width=photo.width,
        height=photo.height,
        preview_url=f"/api/media/photos/{photo.id}/file",
        download_url=f"/api/media/photos/{photo.id}/download",
    ).model_dump(by_alias=True, mode="json")


async def _published_album(db: AsyncSession, slug: str):
    stmt = _with_artist(
        select(*_album_columns_with_count()).where(
            Album.slug == slug, Album.is_published.is_(True)
        )
    )
    return (await db.execute(stmt)).first()


async def _album_photos(db: AsyncSession, album_id: int):
    stmt = (
        select(*_PHOTO_COLUMNS)
        .where(Photo.album_id == album_id)
        .order_by(Photo.position, Photo.id)
    )
    return (await db.execute(stmt)).all()


async def published_albums_for_artist(
    db: AsyncSession, artist_id: int, user: AuthUser | None
) -> list[dict]:
    """An artist's published albums, for their page.

    Shared with the roster endpoint so an artist page and the listings can't
    disagree about which albums exist or who may download them.
    """
    rows = (
        await db.execute(
            _with_artist(
                select(*_album_columns_with_count())
                .where(Album.artist_id == artist_id, Album.is_published.is_(True))
                .order_by(Album.id)
            )
        )
    ).all()
    return [_album_summary(row, await _can_download(db, user, row)) for row in rows]


async def _published_photo(db: AsyncSession, photo_id: int):
    """A photo plus the album fields the access rule needs."""
    stmt = (
        select(*_PHOTO_COLUMNS, Album.slug, Album.access, Album.artist_id)
        .join(Album, Album.id == Photo.album_id)
        .where(Photo.id == photo_id, Album.is_published.is_(True))
    )
    photo = (await db.execute(stmt)).first()
    if photo is None:
        raise ApiError(404, msg("Photo not found"))
    return photo


async def _can_download(db: AsyncSession, user, album) -> bool:
    if user is None:
        return False
    return await access.may_download(
        db,
        user_id=user.id,
        role=user.role,
        artist_id=album.artist_id,
        access=album.access,
    )


async def _may_download_photo(db: AsyncSession, user, photo) -> bool:
    if user is None:
        return False
    return await access.may_download(
        db,
        user_id=user.id,
        role=user.role,
        artist_id=photo.artist_id,
        access=photo.access,
    )


def _file(path_value: str | None) -> Path:
    if not path_value:
        raise ApiError(404, msg("Photo file not found"))
    try:
        path = storage.photo_path(path_value)
    except ValueError:
        raise ApiError(404, msg("Photo file not found")) from None
    if not path.is_file():
        raise ApiError(404, msg("Photo file not found"))
    return path


def _media_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _save_as(title: str | None, fallback: str, suffix: str) -> str:
    """The name the browser saves under: the photo's title when it has one."""
    stem = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return f"{stem or fallback}{suffix}"


@router.get("/albums")
async def list_albums(
    user: AuthUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    rows = (
        await db.execute(
            _with_artist(
                select(*_album_columns_with_count())
                .where(Album.is_published.is_(True))
                .order_by(Album.id)
            )
        )
    ).all()
    albums = []
    for row in rows:
        albums.append(_album_summary(row, await _can_download(db, user, row)))
    return respond(200, {"albums": albums})


@router.get("/albums/{slug}")
async def get_album(
    slug: str,
    user: AuthUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    album = await _published_album(db, slug)
    if album is None:
        raise ApiError(404, msg("Album not found"))

    can_download = await _can_download(db, user, album)
    photos = await _album_photos(db, album.id)
    return respond(
        200,
        {
            "album": _album_detail(album, can_download),
            "photos": [_photo(photo, can_download) for photo in photos],
        },
    )


@router.get("/photos/{photo_id}/file")
async def get_photo_file(photo_id: int, db: AsyncSession = Depends(get_db)) -> object:
    """The preview. Public for published albums; no download rights implied."""
    photo = await _published_photo(db, photo_id)
    path = _file(photo.preview_filename or photo.filename)
    return FileResponse(path, media_type=_media_type(path))


@router.get("/photos/{photo_id}/download")
async def download_photo(
    photo_id: int,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """One original as an attachment.

    Free photos: any registered user. Paid photos: a subscriber of that artist.
    """
    photo = await _published_photo(db, photo_id)
    if not await _may_download_photo(db, user, photo):
        raise ApiError(
            403,
            msg("This photo is part of a paid portfolio. Subscribe to download it."),
        )

    path = _file(photo.filename)
    return FileResponse(
        path,
        media_type=_media_type(path),
        filename=_save_as(photo.title, f"photo-{photo.id:02d}", path.suffix),
    )


@router.get("/albums/{slug}/download")
async def download_album(
    slug: str,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """Every original in an album as one zip."""
    album = await _published_album(db, slug)
    if album is None:
        raise ApiError(404, msg("Album not found"))
    if not await _can_download(db, user, album):
        raise ApiError(
            403,
            msg("This album is part of a paid portfolio. Subscribe to download it."),
        )

    photos = await _album_photos(db, album.id)
    if not photos:
        raise ApiError(404, msg("Album has no photos"))

    # Zipped on disk, not in memory: a real album is hundreds of megabytes of
    # originals, and buffering that per download would take the process out.
    # ZIP_STORED, not ZIP_DEFLATED: photos are already compressed, so deflating
    # them again costs CPU for no meaningful saving.
    handle, archive_path = tempfile.mkstemp(suffix=".zip")
    os.close(handle)
    try:
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_STORED) as archive:
            for index, photo in enumerate(photos, start=1):
                try:
                    path = storage.photo_path(photo.filename)
                except ValueError:
                    continue
                if not path.is_file():
                    # One missing file shouldn't fail the whole album.
                    continue
                archive.write(
                    path,
                    _save_as(photo.title, f"{album.slug}-{index:02d}", path.suffix),
                )
    except Exception:
        # Never leave the temp file behind on the way out.
        os.unlink(archive_path)
        raise

    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=f"{album.slug}.zip",
        # Removed once the response has been sent.
        background=BackgroundTask(os.unlink, archive_path),
    )
