"""Database error helpers."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError


def is_unique_violation(err: BaseException) -> bool:
    """True for a Postgres unique-constraint violation (SQLSTATE 23505)."""
    if not isinstance(err, IntegrityError):
        return False
    orig = getattr(err, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    return sqlstate == "23505"
