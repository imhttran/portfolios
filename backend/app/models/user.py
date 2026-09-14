"""Accounts and their one-time registration profile."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'client'"), default="client"
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    verification_token: Mapped[str | None] = mapped_column(
        Text, unique=True, nullable=True
    )
    reset_token: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    reset_token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserProfile(Base):
    """One-time registration details.

    A missing row (not a boolean flag) is what gates a user into the completion
    form, so the data itself is the "is this done" signal.
    """

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    address2: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    zip: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'US'"), default="US"
    )
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    communication_preference: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'email'"), default="email"
    )
    linkedin: Mapped[str | None] = mapped_column(Text, nullable=True)
    github: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_email: Mapped[str | None] = mapped_column(Text, nullable=True)
