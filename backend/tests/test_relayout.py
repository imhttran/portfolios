"""Tests for moving existing photos into the current media layout.

The dangerous part of a layout change is a row that still points at where a file
*used* to be, so the tests check the row and the file end up in the same place.
"""

from __future__ import annotations

import io
import uuid

from PIL import Image
from sqlalchemy import delete, select

from app.db.session import get_sessionmaker
from app.models import Album, ArtistProfile, Photo, User
from app.services import storage
from app.services.relayout import relayout_media
from app.services.security import hash_password
from tests.helpers import requires_db, unique_email

pytestmark = requires_db


def _jpeg(w: int = 300, h: int = 200) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (w, h), (90, 110, 130)).save(buffer, format="JPEG")
    return buffer.getvalue()


async def _artist(with_profile: bool) -> tuple[int, str | None]:
    email = unique_email("relayout")
    slug = f"test-{uuid.uuid4().hex[:8]}" if with_profile else None
    async with get_sessionmaker()() as session:
        session.add(
            User(
                email=email,
                password=hash_password("Valid123!"),
                role="artist",
                email_verified=True,
            )
        )
        await session.commit()
        user_id = await session.scalar(select(User.id).where(User.email == email))
        if slug:
            session.add(
                ArtistProfile(
                    user_id=user_id,
                    slug=slug,
                    display_name="Relayout Artist",
                    tagline="Photographer",
                    statement="s",
                    bio="b",
                    location="Austin, TX",
                    contact_email="a@example.com",
                )
            )
            await session.commit()
    return user_id, slug


async def _old_scheme_photo(artist_id: int, album_slug: str, stem: str) -> int:
    """A photo laid out the way the previous version wrote it, plus its row."""
    old_original = f"originals/artists/{artist_id}/{album_slug}/{stem}.jpg"
    old_preview = f"public/artists/{artist_id}/{album_slug}/{stem}-preview.webp"
    old_thumb = f"public/artists/{artist_id}/{album_slug}/{stem}-thumb.webp"
    storage.write_bytes(old_original, _jpeg())
    storage.write_bytes(old_preview, _jpeg(200, 140))
    storage.write_bytes(old_thumb, _jpeg(80, 60))

    async with get_sessionmaker()() as session:
        album = (
            await session.execute(select(Album).where(Album.slug == album_slug))
        ).scalar_one_or_none()
        if album is None:
            album = Album(
                slug=album_slug, title="Old Album", artist_id=artist_id, access="free"
            )
            session.add(album)
            await session.flush()
        photo = Photo(
            album_id=album.id,
            filename=old_original,
            preview_filename=old_preview,
            thumb_filename=old_thumb,
            width=300,
            height=200,
            title=stem,
            position=1,
        )
        session.add(photo)
        await session.flush()
        photo_id = photo.id
        await session.commit()
    return photo_id


async def _drop(artist_id: int, album_slug: str) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(delete(Album).where(Album.slug == album_slug))
        await session.execute(delete(User).where(User.id == artist_id))
        await session.commit()
    for name in (
        f"originals/artists/{artist_id}/{album_slug}",
        f"public/artists/{artist_id}/{album_slug}",
    ):
        directory = storage.photo_path(name)
        if directory.is_dir():
            for child in directory.iterdir():
                child.unlink()
            directory.rmdir()


async def test_a_report_moves_nothing(client):
    artist_id, _ = await _artist(with_profile=True)
    album_slug = f"old-{uuid.uuid4().hex[:8]}"
    try:
        photo_id = await _old_scheme_photo(artist_id, album_slug, "before")

        async with get_sessionmaker()() as session:
            report = await relayout_media(session, apply=False)

        assert report.rows_to_move >= 1
        async with get_sessionmaker()() as session:
            row = await session.get(Photo, photo_id)
        # Still pointing where it was, and the file is untouched.
        assert row.filename.startswith(f"originals/artists/{artist_id}/")
        assert storage.photo_path(row.filename).is_file()
    finally:
        await _drop(artist_id, album_slug)


async def test_files_and_rows_move_together(client):
    artist_id, slug = await _artist(with_profile=True)
    album_slug = f"old-{uuid.uuid4().hex[:8]}"
    key = f"{artist_id}-{slug}"
    try:
        photo_id = await _old_scheme_photo(artist_id, album_slug, "before")

        async with get_sessionmaker()() as session:
            await relayout_media(session, apply=True)

        async with get_sessionmaker()() as session:
            row = await session.get(Photo, photo_id)

        # The row names the new layout…
        assert row.filename == f"originals/artists/{key}/{album_slug}/before.jpg"
        assert row.preview_filename == (
            f"public/artists/{key}/{album_slug}/before-preview.webp"
        )
        # …and every file it names is actually there.
        for name in (row.filename, row.preview_filename, row.thumb_filename):
            assert storage.photo_path(name).is_file(), name

        # Nothing left at the old address.
        assert not storage.photo_path(
            f"originals/artists/{artist_id}/{album_slug}/before.jpg"
        ).exists()

        # Second run: nothing to do.
        async with get_sessionmaker()() as session:
            again = await relayout_media(session, apply=True)
        assert again.rows_to_move == 0
    finally:
        await _drop(artist_id, album_slug)


async def test_an_artist_without_a_profile_keeps_the_bare_id(client):
    """The key falls back to the id, so the folder is unchanged and safe."""
    artist_id, _ = await _artist(with_profile=False)
    album_slug = f"old-{uuid.uuid4().hex[:8]}"
    try:
        photo_id = await _old_scheme_photo(artist_id, album_slug, "plain")

        async with get_sessionmaker()() as session:
            report = await relayout_media(session, apply=True)

        async with get_sessionmaker()() as session:
            row = await session.get(Photo, photo_id)

        assert report.rows_to_move == 0  # already at the right address
        assert row.filename == (f"originals/artists/{artist_id}/{album_slug}/plain.jpg")
        assert storage.photo_path(row.filename).is_file()
    finally:
        await _drop(artist_id, album_slug)
