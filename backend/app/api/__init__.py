"""HTTP layer: routers and shared dependencies."""

from app.api import (
    artist,
    artists,
    auth,
    manage,
    media,
    profile,
    subscriptions,
    users,
)

__all__ = [
    "artist",
    "artists",
    "auth",
    "manage",
    "media",
    "profile",
    "subscriptions",
    "users",
]
