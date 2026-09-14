"""Out-of-band role management: the ``set-role`` subcommand.

Roles are granted CLI-only, so there's no HTTP endpoint and no self-service
escalation. Deliberately does NOT load .env files - it reads DATABASE_URL
directly, matching the Rust backend's set-role.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DEFAULT_DATABASE_URL
from app.db.session import build_engine
from app.models import User
from app.services.roles import ROLES, role_index


def _usage() -> str:
    return f"Usage: set-role <email> <{'|'.join(ROLES)}>"


async def _run(email: str, role: str) -> int:
    dsn = os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
    engine = build_engine(dsn)
    try:
        async with AsyncSession(engine) as session:
            exists = await session.scalar(select(User.id).where(User.email == email))
            if exists is None:
                print(f"No user found with email {email}")
                return 1
            await session.execute(
                update(User).where(User.email == email).values(role=role)
            )
            await session.commit()
    except Exception as err:  # noqa: BLE001 - surface any DB failure like the CLI does
        print(f"Failed to set role: {err}")
        return 1
    finally:
        await engine.dispose()

    print(f"{email} is now {role}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # Tolerate being invoked as `python -m app.cli set-role <email> <role>`.
    if args and args[0] == "set-role":
        args = args[1:]

    parser = argparse.ArgumentParser(prog="set-role", add_help=True)
    parser.add_argument("email", nargs="?")
    parser.add_argument("role", nargs="?")
    parsed = parser.parse_args(args)

    if parsed.email is None or parsed.role is None or role_index(parsed.role) is None:
        print(_usage())
        return 1

    return asyncio.run(_run(parsed.email, parsed.role))


if __name__ == "__main__":
    raise SystemExit(main())
