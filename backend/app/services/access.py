"""Who may download what.

One function, so the rule lives in a single place instead of being restated (and
eventually contradicted) in an endpoint and again in the browser.

- **free** album: any registered user. Signed in is the whole requirement.
- **paid** / **premium** album: a subscriber of that artist whose level ranks at
  or above the album's tier. So a premium subscription opens paid albums too.
- The artist's own work and staff/admin are always allowed, because refusing the
  owner their own files would be absurd.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription
from app.models.tiers import TIER_FREE, opens

MIN_ROLE_FOR_EVERYTHING = "staff"


async def subscription_level(
    db: AsyncSession, subscriber_id: int, artist_id: int
) -> str | None:
    """The level this user subscribes at, or None if they don't subscribe."""
    return await db.scalar(
        select(Subscription.level).where(
            Subscription.subscriber_id == subscriber_id,
            Subscription.artist_id == artist_id,
        )
    )


async def may_download(
    db: AsyncSession,
    *,
    user_id: int,
    role: str,
    artist_id: int,
    access: str,
) -> bool:
    # Fail closed: only the *free* tier is open, and anything unrecognised falls
    # through to the checks below. Written the other way round (`!= paid`) a typo
    # like "premuim" would silently behave as free, and hand the work to every
    # registered user.
    if access == TIER_FREE:
        return True

    if artist_id == user_id:
        return True

    # Imported here to keep this module free of the API layer at import time.
    from app.services.roles import has_role

    if has_role(role, MIN_ROLE_FOR_EVERYTHING):
        return True

    level = await subscription_level(db, user_id, artist_id)
    return level is not None and opens(access, level)
