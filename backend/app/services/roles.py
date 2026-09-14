"""Ranked roles: a role satisfies a check for itself or anything below it."""

from __future__ import annotations

ROLES: tuple[str, ...] = ("client", "staff", "admin")


def role_index(role: str) -> int | None:
    try:
        return ROLES.index(role)
    except ValueError:
        return None


def has_role(user_role: str, min_role: str) -> bool:
    user_index = role_index(user_role)
    min_index = role_index(min_role)
    if user_index is None or min_index is None:
        return False
    return user_index >= min_index
