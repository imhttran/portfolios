"""Tests for the CLI's database handling.

These commands are what you reach for right after a schema reset, when the
database exists but has no tables - the backend is what normally creates them,
on boot.
"""

from __future__ import annotations

from sqlalchemy import inspect

from app import cli
from app.db.base import Base
from app.db.session import create_all, get_engine
from app.services import storage
from tests.helpers import cleanup, requires_db, unique_email

pytestmark = requires_db


async def _has_users_table() -> bool:
    async with get_engine().connect() as conn:
        return await conn.run_sync(lambda c: inspect(c).has_table("users"))


async def test_prepare_db_rebuilds_a_missing_schema() -> None:
    """The reported bug: a dropped schema used to crash every command."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    assert not await _has_users_table()

    try:
        assert await cli._prepare_db() is True
        assert await _has_users_table()
    finally:
        # This database is shared by the whole session, so leave the schema
        # behind even if an assertion above fails.
        await create_all()


async def test_prepare_db_is_idempotent() -> None:
    """An existing schema is reported as such and left alone."""
    assert await cli._prepare_db() is False


async def test_prune_media_refuses_when_the_schema_was_missing(
    monkeypatch, capsys
) -> None:
    """With no rows, every file on disk looks like an orphan.

    `prune-media --yes` would delete the lot, so it has to refuse instead.
    """
    orphan = storage.media_root() / "originals" / "artists" / "9-cli" / "a" / "x.jpg"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"not really a photo")

    async def empty_schema() -> bool:
        return True

    monkeypatch.setattr(cli, "_prepare_db", empty_schema)
    try:
        assert await cli._prune_media(["--yes"]) == 0
        assert orphan.exists()
        assert "restore-media" in capsys.readouterr().out
    finally:
        orphan.unlink(missing_ok=True)


async def _make_user(email: str, role: str = "client") -> None:
    """A user the subscription commands can point at."""
    from app.db.session import get_sessionmaker
    from app.models import User
    from app.services.security import hash_password

    async with get_sessionmaker()() as session:
        session.add(User(email=email, password=hash_password("Valid123!"), role=role))
        await session.commit()


async def _level_between(subscriber: str, artist: str) -> str | None:
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import Subscription, User

    async with get_sessionmaker()() as session:
        subscriber_id = await session.scalar(
            select(User.id).where(User.email == subscriber)
        )
        artist_id = await session.scalar(select(User.id).where(User.email == artist))
        return await session.scalar(
            select(Subscription.level).where(
                Subscription.subscriber_id == subscriber_id,
                Subscription.artist_id == artist_id,
            )
        )


async def test_set_subscription_grants_then_changes_the_level(capsys) -> None:
    subscriber = unique_email("sub")
    artist = unique_email("artist")
    await _make_user(subscriber)
    await _make_user(artist, role="artist")
    try:
        assert await cli._set_subscription([subscriber, artist]) == 0
        assert await _level_between(subscriber, artist) == "paid"
        assert "can now download" in capsys.readouterr().out

        # Re-running with another level upgrades rather than failing.
        assert (
            await cli._set_subscription([subscriber, artist, "--level", "premium"]) == 0
        )
        assert await _level_between(subscriber, artist) == "premium"
    finally:
        await cleanup(subscriber)
        await cleanup(artist)


async def test_set_subscription_refuses_a_non_artist(capsys) -> None:
    subscriber = unique_email("sub")
    customer = unique_email("cust")
    await _make_user(subscriber)
    await _make_user(customer)  # role=client
    try:
        assert await cli._set_subscription([subscriber, customer]) == 1
        assert "is not an artist" in capsys.readouterr().out
        assert await _level_between(subscriber, customer) is None
    finally:
        await cleanup(subscriber)
        await cleanup(customer)


async def test_revoke_subscription_closes_the_paid_work(capsys) -> None:
    subscriber = unique_email("sub")
    artist = unique_email("artist")
    await _make_user(subscriber)
    await _make_user(artist, role="artist")
    try:
        await cli._set_subscription([subscriber, artist])
        assert await cli._revoke_subscription([subscriber, artist]) == 0
        assert await _level_between(subscriber, artist) is None

        # Revoking what isn't there is reported, not silently accepted.
        assert await cli._revoke_subscription([subscriber, artist]) == 1
        assert "does not subscribe to" in capsys.readouterr().out
    finally:
        await cleanup(subscriber)
        await cleanup(artist)
