"""Input validation."""

from __future__ import annotations

import re

from app.schemas.profile import ProfileInput

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_SPECIAL_RE = re.compile(r"""[!@#$%^&*(),.?":{}|<>]""")

# An Instagram handle: letters, digits, dots and underscores, up to 30 - the
# shape the platform itself allows. One place, because the handle is what builds
# the profile URL the glyph links to, and a stray character there is a link that
# quietly doesn't work.
_INSTAGRAM_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def validate_email(email: str) -> bool:
    return _EMAIL_RE.match(email) is not None


def validate_instagram(handle: str) -> bool:
    return _INSTAGRAM_RE.match(handle) is not None


def validate_password(password: str) -> str | None:
    """Return the first unmet rule as a message, or None if valid."""
    # The Go/Rust backends count bytes, so match that rather than characters.
    if len(password.encode()) < 8:
        return "Password must be at least 8 characters long"
    if not any(c.isascii() and c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if not any(c.isascii() and c.isdigit() for c in password):
        return "Password must contain at least one number"
    if not _SPECIAL_RE.search(password):
        return "Password must contain at least one special character"
    return None


def optional_trimmed(value: str | None) -> str | None:
    """``body.x?.trim() || null``: blank optionals are stored as NULL."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def validate_profile_fields(body: ProfileInput) -> str | None:
    """Return an error message describing the first unmet rule, or None."""
    required = (
        ("firstName", body.first_name),
        ("lastName", body.last_name),
    )
    missing = [name for name, value in required if not value.strip()]
    if missing:
        return f"Missing required field(s): {', '.join(missing)}"
    return None
