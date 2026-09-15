"""Subscriptions: which customers may download which artist's paid work.

No payment provider is wired up, so granting is an admin action. When one is
added, it writes the same row from a webhook and this endpoint becomes the
manual override.

``/mine`` is for any signed-in user and is what a client page uses to know which
buckets are open to it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, ensure_role, get_current_user
from app.api.responses import internal_error, msg, respond
from app.db.session import get_db
from app.models import Subscription, User
from app.models.tiers import SUBSCRIPTION_LEVELS, TIER_PAID
from app.schemas.subscription import GrantSubscriptionRequest, SubscriptionOut

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


# Validates the level a grant asks for, so the tier ladder can't be fed a word
# it doesn't know. Blank means the ordinary paid level.
def _level_or_error(requested: str) -> tuple[str, str | None]:
    level = requested.strip() or TIER_PAID
    if level not in SUBSCRIPTION_LEVELS:
        return level, f"level must be one of: {', '.join(SUBSCRIPTION_LEVELS)}"
    return level, None


def _serialize(row) -> dict:
    return SubscriptionOut(
        id=row.id,
        subscriber_id=row.subscriber_id,
        subscriber_email=row.subscriber_email,
        artist_id=row.artist_id,
        artist_email=row.artist_email,
        level=row.level,
        note=row.note,
        created_at=row.created_at,
    ).model_dump(by_alias=True, mode="json")


def _joined():
    """Subscriptions with both sides' emails, for an admin list."""
    subscriber = User.__table__.alias("subscriber")
    artist = User.__table__.alias("artist")
    return (
        select(
            Subscription.id,
            Subscription.subscriber_id,
            subscriber.c.email.label("subscriber_email"),
            Subscription.artist_id,
            artist.c.email.label("artist_email"),
            Subscription.level,
            Subscription.note,
            Subscription.created_at,
        )
        .join(subscriber, subscriber.c.id == Subscription.subscriber_id)
        .join(artist, artist.c.id == Subscription.artist_id)
        .order_by(Subscription.id)
    )


@router.get("/mine")
async def list_my_subscriptions(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """The artists this user has paid access to. Any signed-in user."""
    rows = (
        await db.execute(_joined().where(Subscription.subscriber_id == user.id))
    ).all()
    return respond(200, {"subscriptions": [_serialize(row) for row in rows]})


@router.get("")
async def list_subscriptions(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    ensure_role(user, "staff")
    rows = (await db.execute(_joined())).all()
    return respond(200, {"subscriptions": [_serialize(row) for row in rows]})


@router.post("")
async def grant_subscription(
    body: GrantSubscriptionRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    ensure_role(user, "admin")

    level, level_error = _level_or_error(body.level)
    if level_error:
        return respond(400, msg(level_error))

    # Plain columns, not ORM entities: the duplicate path below rolls back, and
    # touching an expired entity's attribute afterwards would trigger a lazy
    # refresh outside the async context and blow up.
    subscriber = (
        await db.execute(
            select(User.id, User.email).where(User.id == body.subscriber_id)
        )
    ).first()
    if subscriber is None:
        return respond(404, msg("Subscriber not found"))

    artist = (
        await db.execute(
            select(User.id, User.email, User.role).where(User.id == body.artist_id)
        )
    ).first()
    if artist is None:
        return respond(404, msg("Artist not found"))
    if artist.role not in ("artist", "admin"):
        return respond(400, msg(f"{artist.email} is not an artist"))

    try:
        subscription = Subscription(
            subscriber_id=subscriber.id,
            artist_id=artist.id,
            level=level,
            note=body.note.strip() or None,
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
    except IntegrityError:
        await db.rollback()
        return respond(
            400,
            msg(f"{subscriber.email} already subscribes to {artist.email}"),
        )
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Grant Subscription Error", err, False)

    return respond(
        201,
        {
            "success": True,
            "message": (
                f"{subscriber.email} can now download {artist.email}'s {level} work"
            ),
            "id": subscription.id,
        },
    )


@router.delete("/{subscription_id}")
async def revoke_subscription(
    subscription_id: str = Path(...),
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    ensure_role(user, "admin")

    try:
        parsed = int(subscription_id)
    except ValueError:
        return respond(400, msg("Invalid subscription id"))

    try:
        result = await db.execute(delete(Subscription).where(Subscription.id == parsed))
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Revoke Subscription Error", err, False)

    if result.rowcount == 0:
        return respond(404, msg("Subscription not found"))
    return respond(200, {"success": True, "message": "Subscription revoked"})
