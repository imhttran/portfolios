"""Tests for database upkeep - what counts as dead, and what is kept."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import EmailQueue, LoginCode, User, UserDevice
from app.services.maintenance import prune_db
from app.services.security import hash_password
from tests.helpers import cleanup, requires_db, unique_email

pytestmark = requires_db


async def _seed_user_only(email: str) -> int:
    """Just a user, for tests that seed their own rows."""
    async with get_sessionmaker()() as session:
        session.add(
            User(
                email=email,
                password=hash_password("Valid123!"),
                role="client",
                email_verified=True,
            )
        )
        await session.commit()
        return await session.scalar(select(User.id).where(User.email == email))


async def _seed_rows(email: str) -> int:
    """One of everything: live and dead codes, recent and old mail."""
    user_id = await _seed_user_only(email)
    now = datetime.now(UTC)

    async with get_sessionmaker()() as session:
        session.add_all(
            [
                # Live: unused and not yet expired. Must survive.
                LoginCode(
                    user_id=user_id,
                    token="live-token",
                    code="1234",
                    expires_at=now + timedelta(minutes=10),
                ),
                # Used: can never be reused. Dead.
                LoginCode(
                    user_id=user_id,
                    token="used-token",
                    code="1234",
                    expires_at=now + timedelta(minutes=10),
                    used=True,
                ),
                # Expired and unused: dead too.
                LoginCode(
                    user_id=user_id,
                    token="expired-token",
                    code="1234",
                    expires_at=now - timedelta(minutes=1),
                ),
                # Delivered just now: kept, so "did it send?" stays answerable.
                EmailQueue(
                    to=email, subject="recent", body="x", status="sent", sent_at=now
                ),
                # Delivered long ago: past the retention window.
                EmailQueue(
                    to=email,
                    subject="old",
                    body="x",
                    status="sent",
                    sent_at=now - timedelta(days=30),
                    created_at=now - timedelta(days=30),
                ),
                # Still pending: never touched, however old.
                EmailQueue(
                    to=email,
                    subject="pending",
                    body="x",
                    status="pending",
                    created_at=now - timedelta(days=30),
                ),
            ]
        )
        await session.commit()
    return user_id


async def test_prune_reports_without_deleting(client):
    email = unique_email("prune")
    try:
        await _seed_rows(email)

        async with get_sessionmaker()() as session:
            report = await prune_db(session, keep_days=7, delete_rows=False)

        assert report.dead_login_codes == 2
        assert report.old_emails == 1
        assert report.orphan_total == 0
        assert report.deleted_codes == 0
        assert report.deleted_emails == 0

        # A report must not have removed anything.
        async with get_sessionmaker()() as session:
            still_there = await session.scalar(
                select(LoginCode.id).where(LoginCode.token == "used-token")
            )
        assert still_there is not None
    finally:
        await cleanup(email)


async def test_prune_deletes_the_dead_and_keeps_the_rest(client):
    email = unique_email("prune")
    try:
        user_id = await _seed_rows(email)

        async with get_sessionmaker()() as session:
            report = await prune_db(session, keep_days=7, delete_rows=True)

        assert report.deleted_codes == 2
        assert report.deleted_emails == 1

        async with get_sessionmaker()() as session:
            left_codes = (
                (
                    await session.execute(
                        select(LoginCode.token).where(LoginCode.user_id == user_id)
                    )
                )
                .scalars()
                .all()
            )
            left_mail = (
                (
                    await session.execute(
                        select(EmailQueue.subject).where(EmailQueue.to == email)
                    )
                )
                .scalars()
                .all()
            )

        assert left_codes == ["live-token"]
        assert sorted(left_mail) == ["pending", "recent"]
    finally:
        await cleanup(email)


async def test_prune_drops_devices_whose_trust_lapsed(client):
    """A lapsed device no longer skips 2FA, so the row is only history."""
    email = unique_email("prune")
    try:
        user_id = await _seed_user_only(email)
        now = datetime.now(UTC)

        async with get_sessionmaker()() as session:
            session.add_all(
                [
                    UserDevice(
                        user_id=user_id,
                        device_id="still-trusted",
                        expires_at=now + timedelta(days=10),
                    ),
                    UserDevice(
                        user_id=user_id,
                        device_id="lapsed",
                        expires_at=now - timedelta(days=1),
                    ),
                ]
            )
            await session.commit()

        async with get_sessionmaker()() as session:
            report = await prune_db(session, delete_rows=True)

        assert report.expired_devices == 1
        assert report.deleted_devices == 1

        async with get_sessionmaker()() as session:
            left = (
                (
                    await session.execute(
                        select(UserDevice.device_id).where(
                            UserDevice.user_id == user_id
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert left == ["still-trusted"]
    finally:
        await cleanup(email)
