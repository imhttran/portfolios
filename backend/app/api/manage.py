"""The artist's own control surface: create albums, upload into them, edit them.

Deliberately separate from ``/api/media``: that router is public delivery and
answers "can this visitor see or take this", while this one is about *managing*
your own work and every route on it needs a session.

Ownership is enforced here, not just role: an artist manages their own albums,
and staff/admin manage anyone's.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, ensure_role, get_current_user
from app.api.responses import ApiError, internal_error, msg, respond
from app.db.session import get_db
from app.models import Album, Photo
from app.models.tiers import TIERS
from app.schemas.media import AlbumInput, AlbumPatch, ManagedAlbum
from app.services import storage
from app.services.images import NotAnImage
from app.services.roles import has_role
from app.services.slugs import artist_media_key, unique_album_slug
from app.services.uploads import (
    MAX_FILES_PER_UPLOAD,
    MAX_UPLOAD_BYTES,
    add_photo,
)

router = APIRouter(prefix="/api/manage", tags=["manage"])


def _ensure_can_manage(user: AuthUser, artist_id: int) -> None:
    """Staff and admin manage anyone's work; an artist only their own."""
    if not has_role(user.role, "staff") and artist_id != user.id:
        raise ApiError(403, msg("That belongs to another artist"))


async def _album_or_404(db: AsyncSession, slug: str, user: AuthUser) -> Album:
    album = (
        await db.execute(select(Album).where(Album.slug == slug))
    ).scalar_one_or_none()
    if album is None:
        raise ApiError(404, msg("Album not found"))
    _ensure_can_manage(user, album.artist_id)
    return album


async def _serialize(db: AsyncSession, album: Album) -> dict:
    count = await db.scalar(
        select(func.count(Photo.id)).where(Photo.album_id == album.id)
    )
    return ManagedAlbum(
        id=album.id,
        slug=album.slug,
        title=album.title,
        description=album.description,
        credit=album.credit,
        access=album.access,
        is_published=album.is_published,
        photo_count=count or 0,
    ).model_dump(by_alias=True, mode="json")


@router.get("/albums")
async def list_my_albums(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """The caller's albums - unpublished ones included, which is the point."""
    ensure_role(user, "artist")

    stmt = select(Album).order_by(Album.id)
    if not has_role(user.role, "staff"):
        stmt = stmt.where(Album.artist_id == user.id)

    albums = (await db.execute(stmt)).scalars().all()
    return respond(200, {"albums": [await _serialize(db, album) for album in albums]})


@router.post("/albums")
async def create_album(
    body: AlbumInput,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """Create an album in one of the buckets. Owned by whoever creates it."""
    ensure_role(user, "artist")

    if not body.title.strip():
        return respond(400, msg("A title is required"))
    if body.access not in TIERS:
        return respond(400, msg(f"access must be one of: {', '.join(TIERS)}"))

    try:
        album = Album(
            slug=await unique_album_slug(db, body.title),
            title=body.title.strip(),
            description=body.description.strip() or None,
            credit=body.credit.strip() or None,
            access=body.access,
            artist_id=user.id,
            is_published=body.is_published,
        )
        db.add(album)
        await db.commit()
        await db.refresh(album)
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Create Album Error", err, False)

    return respond(
        201,
        {
            "success": True,
            "message": f"Created '{album.title}' in the {body.access} bucket",
            "album": await _serialize(db, album),
        },
    )


@router.patch("/albums/{slug}")
async def update_album(
    slug: str,
    body: AlbumPatch,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """Edit an album. Only the fields sent are changed.

    Moving an album between buckets is a column update and nothing else - no
    file moves, which is exactly why the tier lives in the database rather than
    in the path.
    """
    ensure_role(user, "artist")
    album = await _album_or_404(db, slug, user)

    if body.access is not None and body.access not in TIERS:
        return respond(400, msg(f"access must be one of: {', '.join(TIERS)}"))

    try:
        if body.title is not None and body.title.strip():
            album.title = body.title.strip()
        if body.access is not None:
            album.access = body.access
        if body.description is not None:
            album.description = body.description.strip() or None
        if body.credit is not None:
            album.credit = body.credit.strip() or None
        if body.is_published is not None:
            album.is_published = body.is_published
        await db.commit()
        await db.refresh(album)
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Update Album Error", err, False)

    return respond(200, {"success": True, "album": await _serialize(db, album)})


@router.post("/albums/{slug}/photos")
async def upload_photos(
    slug: str,
    files: list[UploadFile] | None = File(None),
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """Add photos to one of your albums.

    Reports per file: a batch with one bad file adds the rest. Nothing is
    committed if every file was refused.
    """
    ensure_role(user, "artist")
    album = await _album_or_404(db, slug, user)

    incoming = files or []
    if not incoming:
        return respond(400, msg("No files were sent"))
    if len(incoming) > MAX_FILES_PER_UPLOAD:
        return respond(400, msg(f"At most {MAX_FILES_PER_UPLOAD} files at a time"))

    # Resolved once for the whole batch, not per file.
    artist_key = await artist_media_key(db, album.artist_id)

    added = 0
    rejected: list[dict] = []
    for upload in incoming:
        name = upload.filename or "unnamed"
        try:
            data = await upload.read()
            photo = await add_photo(
                db,
                album=album,
                artist_key=artist_key,
                filename=name,
                data=data,
                max_bytes=MAX_UPLOAD_BYTES,
            )
            if photo is not None:
                added += 1
        except NotAnImage as err:
            rejected.append({"name": name, "reason": str(err)})
        except (OSError, ValueError) as err:
            rejected.append({"name": name, "reason": str(err)})
        finally:
            await upload.close()

    if added == 0:
        # Nothing landed, so don't leave a half-written transaction behind. Same
        # shape as the success case, so a client can read `added` either way.
        await db.rollback()
        return respond(
            400,
            {
                "success": False,
                "message": "None of those files could be added",
                "added": 0,
                "rejected": rejected,
            },
        )

    try:
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Upload Photos Error", err, False)

    return respond(
        201,
        {
            "success": True,
            "message": (
                f"Added {added} photo{'s' if added != 1 else ''}"
                + (f", skipped {len(rejected)}" if rejected else "")
            ),
            "added": added,
            "rejected": rejected,
            "album": await _serialize(db, album),
        },
    )


@router.delete("/albums/{slug}")
async def delete_album(
    slug: str,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """Delete an album, its photos' rows, and their files."""
    ensure_role(user, "artist")
    album = await _album_or_404(db, slug, user)

    stored = (
        await db.execute(
            select(Photo.filename, Photo.preview_filename, Photo.thumb_filename).where(
                Photo.album_id == album.id
            )
        )
    ).all()

    try:
        # Photos go with it: the FK is ON DELETE CASCADE.
        await db.execute(delete(Album).where(Album.id == album.id))
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Delete Album Error", err, False)

    # Only once the rows are gone: a stray file is a smaller problem than a row
    # pointing at nothing.
    for original, preview, thumb in stored:
        for name in (original, preview, thumb):
            storage.delete_file(name)

    return respond(
        200,
        {
            "success": True,
            "message": f"Deleted '{album.title}' and {len(stored)} photo(s)",
        },
    )


@router.delete("/photos/{photo_id}")
async def delete_photo(
    photo_id: int,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """Remove a photo and its three files."""
    ensure_role(user, "artist")

    photo = (
        await db.execute(select(Photo).where(Photo.id == photo_id))
    ).scalar_one_or_none()
    if photo is None:
        raise ApiError(404, msg("Photo not found"))

    album = await db.get(Album, photo.album_id)
    if album is None:
        raise ApiError(404, msg("Album not found"))
    _ensure_can_manage(user, album.artist_id)

    files = (photo.filename, photo.preview_filename, photo.thumb_filename)
    try:
        await db.execute(delete(Photo).where(Photo.id == photo_id))
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Delete Photo Error", err, False)

    # Only once the row is gone: a stray file is a smaller problem than a row
    # pointing at nothing.
    for name in files:
        storage.delete_file(name)

    return respond(200, {"success": True, "message": "Photo deleted"})
