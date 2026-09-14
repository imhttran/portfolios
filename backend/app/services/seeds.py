"""Dev-only convenience seeding, ported from the Rust backend's lib.rs."""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import User, UserProfile
from app.services.security import hash_password

DEV_ADMIN_EMAIL = "admin@mail.com"
DEV_ADMIN_PASSWORD = "Password1234!"


async def seed_dev_admin(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Guarantee a known admin login locally.

    Gated on NODE_ENV=development so these credentials can never appear in a
    qa/prod database.
    """
    if settings.env != "development":
        return

    async with sessionmaker() as session:
        inserted = (
            await session.execute(
                insert(User)
                .values(
                    email=DEV_ADMIN_EMAIL,
                    password=hash_password(DEV_ADMIN_PASSWORD),
                    role="admin",
                    email_verified=True,
                )
                .on_conflict_do_nothing(index_elements=["email"])
                .returning(User.id)
            )
        ).scalar_one_or_none()

        user_id = inserted
        if user_id is None:
            # Already exists (or the insert failed for another reason) - look it up.
            user_id = await session.scalar(
                select(User.id).where(User.email == DEV_ADMIN_EMAIL)
            )
            if user_id is None:
                print("[seed] failed: dev admin could not be created", file=sys.stderr)
                return

        # Pre-fill the profile so the dev admin isn't stopped by its own gate.
        await session.execute(
            insert(UserProfile)
            .values(
                user_id=user_id,
                first_name="Dev",
                last_name="Admin",
                address="N/A",
                state="N/A",
                zip="00000",
                phone="N/A",
            )
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        await session.commit()

    print(f"[seed] dev admin ready: {DEV_ADMIN_EMAIL}", file=sys.stderr)
