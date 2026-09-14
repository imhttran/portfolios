"""Postgres-backed outbound mail queue, drained by the polling worker."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmailQueue(Base):
    __tablename__ = "email_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # "to" is a reserved word in SQL, hence the explicit quoted name.
    to: Mapped[str] = mapped_column("to", Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'"), default="pending"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), default=0
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
