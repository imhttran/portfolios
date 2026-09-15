"""The DB-backed email queue, its enqueue helpers, and the polling worker."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import EmailQueue, User
from app.services import mail
from app.services.security import random_token

RESET_TOKEN_TTL_HOURS = 1
WORKER_INTERVAL_SECS = 3
WORKER_BATCH = 10


class QueueNotFound(Exception):
    """The target user does not exist (Prisma's P2025 equivalent)."""


async def queue_password_reset(
    session: AsyncSession, frontend_url: str, who: str | int
) -> None:
    """Set a reset token and queue the reset email.

    ``who`` is an email for a self-service reset, or a user id for one an admin
    triggers. The update itself both finds the user and sets the token, so
    callers don't need their own lookup. Raises QueueNotFound when nothing
    matched.
    """
    token = random_token()
    expiry = datetime.now(UTC) + timedelta(hours=RESET_TOKEN_TTL_HOURS)
    column = User.id if isinstance(who, int) else User.email
    stmt = (
        update(User)
        .where(column == who)
        .values(reset_token=token, reset_token_expiry=expiry)
        .returning(User.email)
    )
    email = (await session.execute(stmt)).scalar_one_or_none()
    if email is None:
        await session.rollback()
        raise QueueNotFound()

    session.add(
        mail.password_reset_email(
            email, mail.token_link(frontend_url, "reset-password", token)
        )
    )
    await session.commit()


async def queue_verification_email(
    session: AsyncSession, frontend_url: str, user_id: int, email: str
) -> None:
    token = random_token()
    await session.execute(
        update(User).where(User.id == user_id).values(verification_token=token)
    )
    session.add(
        mail.verification_email(email, mail.token_link(frontend_url, "verify", token))
    )
    await session.commit()


async def process_email_queue(
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    take: int = WORKER_BATCH,
) -> int:
    """Send pending emails, marking each sent or retrying with a bounded cap.

    Returns the number of jobs picked up (used by tests).
    """
    async with sessionmaker() as session:
        rows = (
            await session.execute(
                select(
                    EmailQueue.id,
                    EmailQueue.to,
                    EmailQueue.subject,
                    EmailQueue.body,
                    EmailQueue.attempts,
                )
                .where(
                    EmailQueue.status == "pending",
                    EmailQueue.attempts < settings.max_attempts,
                )
                .order_by(EmailQueue.created_at.asc())
                .limit(take)
            )
        ).all()

        for job_id, to, subject, body, attempts in rows:
            try:
                await asyncio.to_thread(mail.send_mail, settings, to, subject, body)
            except Exception as err:  # noqa: BLE001 - record any send failure
                next_attempts = attempts + 1
                status = (
                    "failed" if next_attempts >= settings.max_attempts else "pending"
                )
                # ponytail: no backoff; the fixed-interval poll is the retry.
                await session.execute(
                    update(EmailQueue)
                    .where(EmailQueue.id == job_id)
                    .values(attempts=next_attempts, last_error=str(err), status=status)
                )
            else:
                await session.execute(
                    update(EmailQueue)
                    .where(EmailQueue.id == job_id)
                    .values(status="sent", sent_at=func.now())
                )
            await session.commit()

        return len(rows)


async def email_worker(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Poll the queue forever; cancelled at application shutdown."""
    while True:
        try:
            await process_email_queue(settings, sessionmaker)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 - the worker must never die
            print(f"[emailQueue] worker error: {err}", file=sys.stderr)
        await asyncio.sleep(WORKER_INTERVAL_SECS)
