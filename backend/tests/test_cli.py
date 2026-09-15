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
from tests.helpers import requires_db

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
