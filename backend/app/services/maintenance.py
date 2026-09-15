"""Database upkeep: removing rows that are dead by definition.

Two tables grow on their own, because nothing in the app ever removes from them:

- ``login_codes`` — every login inserts one. A code that's been used, or whose
  expiry has passed, can never matter again.
- ``email_queue`` — every email inserts one, and delivery only *marks* it sent.
  Delivered and given-up rows are kept for a retention window (so you can still
  answer "did that email go out?") and then dropped.

Devices whose trust has lapsed are also dead: they no longer skip 2FA, so the
row is only history.

It also counts referential orphans, so "there are none" is a checked statement
rather than an assumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Album,
    ArtistProfile,
    EmailQueue,
    LoginCode,
    Photo,
    Subscription,
    User,
    UserDevice,
    UserProfile,
)

# Statuses the worker never comes back to.
TERMINAL_EMAIL_STATUSES = ("sent", "failed")

DEFAULT_KEEP_DAYS = 7


@dataclass
class DbPruneReport:
    dead_login_codes: int = 0
    expired_devices: int = 0
    old_emails: int = 0
    orphans: dict[str, int] = field(default_factory=dict)
    empty_albums: list[str] = field(default_factory=list)
    deleted_codes: int = 0
    deleted_devices: int = 0
    deleted_emails: int = 0

    @property
    def orphan_total(self) -> int:
        return sum(self.orphans.values())


def _dead_code_filter():
    return or_(LoginCode.used.is_(True), LoginCode.expires_at < func.now())


async def _orphan_count(db: AsyncSession, child, parent, child_fk, parent_pk) -> int:
    """How many child rows point at a parent that isn't there."""
    return (
        await db.scalar(
            select(func.count())
            .select_from(child)
            .where(~select(parent_pk).where(parent_pk == child_fk).exists())
        )
    ) or 0


async def prune_db(
    db: AsyncSession, *, keep_days: int = DEFAULT_KEEP_DAYS, delete_rows: bool = False
) -> DbPruneReport:
    """Count the dead rows; delete them when ``delete_rows`` is set."""
    report = DbPruneReport()

    report.dead_login_codes = (
        await db.scalar(
            select(func.count()).select_from(LoginCode).where(_dead_code_filter())
        )
    ) or 0

    report.expired_devices = (
        await db.scalar(
            select(func.count())
            .select_from(UserDevice)
            .where(UserDevice.expires_at <= func.now())
        )
    ) or 0

    cutoff = datetime.now(UTC) - timedelta(days=keep_days)
    report.old_emails = (
        await db.scalar(
            select(func.count())
            .select_from(EmailQueue)
            .where(
                EmailQueue.status.in_(TERMINAL_EMAIL_STATUSES),
                EmailQueue.created_at < cutoff,
            )
        )
    ) or 0

    report.orphans = {
        "photos with no album": await _orphan_count(
            db, Photo, Album, Photo.album_id, Album.id
        ),
        "albums with no artist": await _orphan_count(
            db, Album, User, Album.artist_id, User.id
        ),
        "artist profiles with no user": await _orphan_count(
            db, ArtistProfile, User, ArtistProfile.user_id, User.id
        ),
        "user profiles with no user": await _orphan_count(
            db, UserProfile, User, UserProfile.user_id, User.id
        ),
        "subscriptions with no subscriber": await _orphan_count(
            db, Subscription, User, Subscription.subscriber_id, User.id
        ),
        "subscriptions with no artist": await _orphan_count(
            db, Subscription, User, Subscription.artist_id, User.id
        ),
        "devices with no user": await _orphan_count(
            db, UserDevice, User, UserDevice.user_id, User.id
        ),
        "login codes with no user": await _orphan_count(
            db, LoginCode, User, LoginCode.user_id, User.id
        ),
    }

    report.empty_albums = list(
        (
            await db.execute(
                select(Album.slug)
                .where(~select(Photo.id).where(Photo.album_id == Album.id).exists())
                .order_by(Album.slug)
            )
        )
        .scalars()
        .all()
    )

    if not delete_rows:
        return report

    report.deleted_codes = (
        await db.execute(delete(LoginCode).where(_dead_code_filter()))
    ).rowcount
    report.deleted_devices = (
        await db.execute(delete(UserDevice).where(UserDevice.expires_at <= func.now()))
    ).rowcount
    report.deleted_emails = (
        await db.execute(
            delete(EmailQueue).where(
                EmailQueue.status.in_(TERMINAL_EMAIL_STATUSES),
                EmailQueue.created_at < cutoff,
            )
        )
    ).rowcount
    await db.commit()
    return report
