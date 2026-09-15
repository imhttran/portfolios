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
from app.schemas.media import AlbumSummary, PhotoOut
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
    # Same argument one step further: an album's own page wears its artist's
    # theme, and that page reads only this endpoint.
    ArtistProfile.theme.label("artist_theme"),
    # Carried here for the same reason: the album's own footer signs off as its
    # artist, not the site, and that's the only place this is needed.
    ArtistProfile.contact_email.label("artist_email"),
    ArtistProfile.instagram.label("artist_instagram"),
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


def _cover_photo_id():
    """The album's first photograph by position - one for the index tile.

    Correlated for the same reason as the count: the listing is an index of
    albums and must not become a query per album. Position first, then id, so an
    album whose rows were never numbered still gets a stable cover.
    """
    return (
        select(Photo.id)
        .where(Photo.album_id == Album.id)
        .order_by(Photo.position, Photo.id)
        .limit(1)
        .scalar_subquery()
    )


def _album_columns_with_count():
    return (
        *_ALBUM_COLUMNS,
        *_ARTIST_COLUMNS,
        _photo_count().label("photo_count"),
        _cover_photo_id().label("cover_photo_id"),
    )


def _with_artist(stmt):
    """Left-join the artist's profile so an album carries its owner's name."""
    return stmt.join(
        ArtistProfile, ArtistProfile.user_id == Album.artist_id, isouter=True
    )


def _album(row, can_download: bool) -> dict:
    """An album's wire shape, plus what this visitor may do with it.

    One builder for the listing and the detail response: they carry the same
    fields, and the count rides along on both.
    """
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
        artist_theme=row.artist_theme,
        artist_email=row.artist_email,
        artist_instagram=row.artist_instagram,
        photo_count=row.photo_count,
        cover_url=(
            f"/api/media/photos/{row.cover_photo_id}/file"
            if row.cover_photo_id is not None
            else None
        ),
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


async def _albums(db: AsyncSession, user: AuthUser | None, artist_id: int | None):
    """Published albums, optionally narrowed to one artist, with entitlements.

    Shared by the site-wide listing, an artist's page and the roster endpoint,
    so none of them can disagree about which albums exist or who may download
    them.
    """
    stmt = _with_artist(
        select(*_album_columns_with_count()).where(Album.is_published.is_(True))
    )
    if artist_id is not None:
        stmt = stmt.where(Album.artist_id == artist_id)
    rows = (await db.execute(stmt.order_by(Album.id))).all()
    return [_album(row, await _can_download(db, user, row)) for row in rows]


async def published_albums_for_artist(
    db: AsyncSession, artist_id: int, user: AuthUser | None
) -> list[dict]:
    """An artist's published albums, for their page."""
    return await _albums(db, user, artist_id)


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


async def _can_download(db: AsyncSession, user, row) -> bool:
    """Whether this visitor may take ``row`` - an album row or a photo row.

    Both carry the album's ``access`` and its owner's id, which is all the rule
    needs; see services/access.py.
    """
    if user is None:
        return False
    return await access.may_download(
        db,
        user_id=user.id,
        role=user.role,
        artist_id=row.artist_id,
        access=row.access,
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
    return respond(200, {"albums": await _albums(db, user, None)})


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
            "album": _album(album, can_download),
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
    if not await _can_download(db, user, photo):
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
