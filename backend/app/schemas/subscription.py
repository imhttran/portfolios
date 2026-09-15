"""Wire shapes for subscriptions."""

from __future__ import annotations

from datetime import datetime

from app.schemas.base import CamelModel


class GrantSubscriptionRequest(CamelModel):
    """Admin-granted. Both sides are user ids."""

    subscriber_id: int = 0
    artist_id: int = 0
    # "paid" or "premium"; blank falls back to "paid".
    level: str = ""
    note: str = ""


class SubscriptionOut(CamelModel):
    id: int
    subscriber_id: int
    subscriber_email: str
    artist_id: int
    artist_email: str
    level: str
    note: str | None = None
    created_at: datetime
