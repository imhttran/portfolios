"""Auth dependency and role gating, ported from routes.rs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import exists, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import ApiError, msg
from app.config import Settings, get_settings
from app.db.session import get_db
from app.models import User, UserProfile
from app.services.roles import has_role
from app.services.security import verify_token

# Routes a user can still reach mid-onboarding, so each gate owns its clearing
# route and working through one gate never blocks the other's route.
_ONBOARDING_EXEMPT = {
    ("GET", "/api/me"),
    ("POST", "/api/change-password"),
    ("GET", "/api/profile"),
    ("POST", "/api/profile"),
}

# The same idea for routes whose paths carry ids, so they can't be listed as
# exact strings. The gallery downloads live here: browsing and downloading are
# not steps of onboarding, and making a client enter an address before they can
# take their photos is friction with no security value.
_ONBOARDING_EXEMPT_PATTERNS = (
    re.compile(r"^/api/media/photos/\d+/download$"),
    re.compile(r"^/api/media/albums/[^/]+/download$"),
)


@dataclass
class AuthUser:
    """A logged-in user; extracting this IS the auth check (requireAuth)."""

    id: int
    email: str
    role: str
    email_verified: bool
    must_change_password: bool
    has_profile: bool
    password: str  # stored hash, for /api/change-password


async def _authenticate(
    request: Request, db: AsyncSession, settings: Settings
) -> AuthUser:
    """Resolve the caller's token to a user. Raises for anything unusable.

    Separated from the gates below because some routes want identity *without*
    enforcement: the public album endpoints use it to answer "could this visitor
    download this?" without refusing anyone.
    """
    authorization = request.headers.get("authorization", "")
    parts = authorization.split(" ")
    token = parts[1] if len(parts) > 1 else ""
    if not token:
        raise ApiError(401, msg("No token provided"))

    email = verify_token(token, settings.jwt_secret)
    if email is None:
        raise ApiError(403, msg("Invalid or expired token"))

    has_profile = exists().where(UserProfile.user_id == User.id)
    stmt = select(
        User.id,
        User.email,
        User.role,
        User.email_verified,
        User.must_change_password,
        User.password,
        has_profile.label("has_profile"),
    ).where(User.email == email)
    try:
        row = (await db.execute(stmt)).first()
    except SQLAlchemyError:
        # The lookup shares the JWT check's failure mode: any error reads as a
        # bad token.
        raise ApiError(403, msg("Invalid or expired token")) from None

    if row is None:
        raise ApiError(404, msg("User not found"))

    user = AuthUser(
        id=row.id,
        email=row.email,
        role=row.role,
        email_verified=row.email_verified,
        must_change_password=row.must_change_password,
        has_profile=row.has_profile,
        password=row.password,
    )

    if settings.email_verification_required and not user.email_verified:
        raise ApiError(403, msg("Please verify your email"))

    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    user = await _authenticate(request, db, settings)

    route = (request.method, request.url.path)
    if route not in _ONBOARDING_EXEMPT and not any(
        pattern.match(route[1]) for pattern in _ONBOARDING_EXEMPT_PATTERNS
    ):
        if user.must_change_password:
            raise ApiError(403, msg("Password change required"))
        if not user.has_profile:
            raise ApiError(403, msg("Profile information required"))

    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthUser | None:
    """The caller if they're signed in and usable, otherwise None.

    For public endpoints that want to say what *this* visitor may do. It never
    refuses anyone, and it deliberately skips the onboarding gates - being
    mid-onboarding shouldn't hide download buttons on a page anyone can read.
    """
    try:
        return await _authenticate(request, db, settings)
    except ApiError:
        return None


def ensure_role(user: AuthUser, min_role: str) -> None:
    """Raise 403 unless the user's role is min_role or higher."""
    if not has_role(user.role, min_role):
        raise ApiError(403, msg("Insufficient permissions"))
