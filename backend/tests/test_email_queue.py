"""Database-backed email-queue worker tests."""

from __future__ import annotations

from sqlalchemy import select

from app.config import get_settings
from app.db.session import get_sessionmaker
from app.models import EmailQueue
from app.services.email_queue import process_email_queue
from tests.helpers import cleanup, requires_db, signup, unique_email

pytestmark = requires_db


async def test_worker_marks_queued_emails_sent(client):
    email = unique_email("queue")
    try:
        await signup(client, email)

        # Signup queues the welcome + verification emails.
        async with get_sessionmaker()() as session:
            pending_before = (
                (
                    await session.execute(
                        select(EmailQueue.status).where(EmailQueue.to == email)
                    )
                )
                .scalars()
                .all()
            )
        assert pending_before.count("pending") >= 2

        # No SMTP configured -> send_mail logs and succeeds, so the worker
        # marks them sent.
        processed = await process_email_queue(get_settings(), get_sessionmaker())
        assert processed >= 1

        async with get_sessionmaker()() as session:
            statuses = (
                (
                    await session.execute(
                        select(EmailQueue.status).where(EmailQueue.to == email)
                    )
                )
                .scalars()
                .all()
            )
        assert statuses and all(status == "sent" for status in statuses)
    finally:
        await cleanup(email)
