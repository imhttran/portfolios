"""Who may download an artist's paid work.

A subscription is one customer's access to one artist's paid catalogue, at a
level (``paid`` or ``premium``) that says how far up the tier ladder it reaches.
It is granted by an admin today: there is no payment provider wired up, and a
self-serve "subscribe" button that granted access for free would make the tiers
meaningless. Adding a provider later means writing a row here from the payment
webhook instead of from the admin endpoint.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.tiers import TIER_PAID


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        # One customer, one artist, one row.
        UniqueConstraint("subscriber_id", "artist_id", name="uq_subscription"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The paying customer.
    subscriber_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The artist whose catalogue this opens.
    artist_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # How far up the ladder this reaches: TIER_PAID or TIER_PREMIUM. Plain text
    # like the album tier, so adding a level is additive.
    level: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{TIER_PAID}'"),
        default=TIER_PAID,
    )
    # Free-text note for the admin, e.g. an invoice reference. No money is
    # handled here.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
