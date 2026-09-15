"""Tests for rebuilding photo rows from the media tree.

The point of the command is surviving a database reset, so the tests check the
two ways that could go wrong: rebuilding rows that point at nothing, and
duplicating rows for files that are already accounted for.
"""

from __future__ import annotations

import io
import uuid

from PIL import Image
from sqlalchemy import delete, select

from app.db.session import get_sessionmaker
from app.models import Album, Photo, User
from app.models.tiers import TIER_PAID
from app.services import storage
from app.services.restore import restore_from_media
from tests.helpers import requires_db, unique_email

pytestmark = requires_db


def _jpeg(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), (100, 120, 140))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


async def _write_photo_files(
    artist_id: int, slug: str, stem: str, w: int, h: int
) -> None:
    """The three files a photo is made of, as the pipeline would leave them.

    The key is the bare id: these tests' artists have no profile, which is
    exactly the case artist_media_key falls back for.
    """
    paths = storage.photo_paths(
        artist_key=str(artist_id), album_slug=slug, stem=stem, suffix=".jpg"
    )
    storage.write_bytes(paths.original, _jpeg(w, h))
    storage.write_bytes(paths.preview, _jpeg(min(w, 400), min(h, 400)))
    storage.write_bytes(paths.thumb, _jpeg(80, 60))


async def _artist_id() -> int:
    """Any existing user is enough - the media tree keys off the id."""
    from app.services.security import hash_password

    email = unique_email("restore-artist")
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
        return await session.scalar(select(User.id).where(User.email == email))


async def _drop(artist_id: int, slug: str) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(delete(Album).where(Album.slug == slug))
        await session.execute(delete(User).where(User.id == artist_id))
        await session.commit()


async def test_files_with_no_rows_become_rows_again(client):
    artist_id = await _artist_id()
    slug = f"restored-{uuid.uuid4().hex[:8]}"
    try:
        await _write_photo_files(artist_id, slug, "heron", 1234, 800)
        await _write_photo_files(artist_id, slug, "egret", 800, 1234)

        async with get_sessionmaker()() as session:
            report = await restore_from_media(
                session,
                tiers={slug: TIER_PAID},
                apply=True,
            )

        assert report.albums_created == 1
        assert report.photos_added == 2

        async with get_sessionmaker()() as session:
            album = (
                await session.execute(select(Album).where(Album.slug == slug))
            ).scalar_one()
            rows = (
                await session.execute(
                    select(Photo.title, Photo.width, Photo.height).where(
                        Photo.album_id == album.id
                    )
                )
            ).all()

        # The tier came from the caller, because filenames can't record it.
        assert album.access == TIER_PAID
        assert album.artist_id == artist_id
        # Title from the stem; dimensions read off the file.
        assert sorted(rows) == [("egret", 800, 1234), ("heron", 1234, 800)]

        # And every row points at files that exist.
        async with get_sessionmaker()() as session:
            names = (
                await session.execute(
                    select(Photo.filename, Photo.preview_filename).where(
                        Photo.album_id == album.id
                    )
                )
            ).all()
        for original, preview in names:
            assert storage.photo_path(original).is_file()
            assert storage.photo_path(preview).is_file()
    finally:
        await _drop(artist_id, slug)


async def test_restoring_twice_does_not_duplicate(client):
    artist_id = await _artist_id()
    slug = f"restored-{uuid.uuid4().hex[:8]}"
    try:
        await _write_photo_files(artist_id, slug, "one", 400, 300)

        async with get_sessionmaker()() as session:
            first = await restore_from_media(session, apply=True)
        async with get_sessionmaker()() as session:
            second = await restore_from_media(session, apply=True)

        assert first.photos_added >= 1
        assert second.photos_added == 0
        assert second.albums_created == 0
        assert second.already_present >= 1
    finally:
        await _drop(artist_id, slug)


async def test_a_report_changes_nothing(client):
    artist_id = await _artist_id()
    slug = f"restored-{uuid.uuid4().hex[:8]}"
    try:
        await _write_photo_files(artist_id, slug, "pending", 400, 300)

        async with get_sessionmaker()() as session:
            report = await restore_from_media(session, apply=False)

        assert report.photos_added == 1  # counted…

        async with get_sessionmaker()() as session:
            album = await session.scalar(select(Album.id).where(Album.slug == slug))
        assert album is None  # …but nothing was written
    finally:
        await _drop(artist_id, slug)


async def test_a_folder_whose_artist_is_gone_is_skipped(client):
    """The media tree names an artist id; if no such user exists, say so."""
    slug = f"orphaned-{uuid.uuid4().hex[:8]}"
    await _write_photo_files(999_999, slug, "lost", 400, 300)

    async with get_sessionmaker()() as session:
        report = await restore_from_media(session, apply=True)

    assert any("999999" in entry for entry in report.skipped)
    async with get_sessionmaker()() as session:
        album = await session.scalar(select(Album.id).where(Album.slug == slug))
    assert album is None


async def test_the_seed_rebuilds_from_disk_only_in_development(client, settings):
    """What makes a reset survivable: boot rebuilds work the seeds don't know.

    Assertions are scoped to this test's own slug, because every test in the run
    shares one media root - other tests' files are there too, and the seed will
    happily restore those as well.
    """
    from dataclasses import replace

    from app.services.seeds import seed_dev_restore_media

    artist_id = await _artist_id()
    slug = f"seeded-{uuid.uuid4().hex[:8]}"
    try:
        await _write_photo_files(artist_id, slug, "boot", 640, 480)

        async with get_sessionmaker()() as session:
            album = await session.scalar(select(Album.id).where(Album.slug == slug))
        assert album is None  # nothing yet

        # Outside development it must do nothing at all.
        await seed_dev_restore_media(
            replace(settings, env="production"), get_sessionmaker()
        )
        async with get_sessionmaker()() as session:
            album = await session.scalar(select(Album.id).where(Album.slug == slug))
        assert album is None

        # In development, boot rebuilds it.
        await seed_dev_restore_media(
            replace(settings, env="development"), get_sessionmaker()
        )
        async with get_sessionmaker()() as session:
            album = (
                await session.execute(select(Album).where(Album.slug == slug))
            ).scalar_one()
            count = await session.scalar(
                select(Photo.id).where(Photo.album_id == album.id)
            )
        assert album.title.lower() == slug.replace("-", " ")
        assert count is not None
    finally:
        await _drop(artist_id, slug)
