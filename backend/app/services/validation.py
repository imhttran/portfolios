"""Input validation, ported from the Rust backend's validators.rs."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.schemas.profile import ProfileInput

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# US phone numbers only, digits with optional standard formatting
# (spaces/dots/dashes/parens) and an optional leading +1/1.
_PHONE_RE = re.compile(r"^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$")

# US zip codes only, 5 digits (no ZIP+4 support yet).
_ZIP_RE = re.compile(r"^\d{5}$")

_SPECIAL_RE = re.compile(r"""[!@#$%^&*(),.?":{}|<>]""")

# One list shared with the frontend so the two can't drift out of sync.
US_STATE_CODES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
}

# One entry today, but a list so adding a second country later is additive.
COUNTRY_CODES = {"US"}

COMMUNICATION_PREFERENCES = ("email", "text", "phone")


def validate_email(email: str) -> bool:
    return _EMAIL_RE.match(email) is not None


def validate_phone(phone: str) -> bool:
    return _PHONE_RE.match(phone) is not None


def validate_zip(zip_code: str) -> bool:
    return _ZIP_RE.match(zip_code) is not None


def validate_url(raw_url: str) -> bool:
    """http(s) only; good enough for LinkedIn/GitHub profile links."""
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


def is_us_state(state: str) -> bool:
    return state in US_STATE_CODES


def is_country(country: str) -> bool:
    return country in COUNTRY_CODES


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
        ("address", body.address),
        ("state", body.state),
        ("zip", body.zip),
        ("phone", body.phone),
        ("communicationPreference", body.communication_preference),
    )
    missing = [name for name, value in required if not value.strip()]
    if missing:
        return f"Missing required field(s): {', '.join(missing)}"
    if body.communication_preference not in COMMUNICATION_PREFERENCES:
        return "communicationPreference must be one of: " + ", ".join(
            COMMUNICATION_PREFERENCES
        )
    if not validate_phone(body.phone):
        return "Phone number is invalid"
    if not validate_zip(body.zip):
        return "Zip code is invalid"
    if not is_us_state(body.state):
        return "State is invalid"
    # The dropdown only offers COUNTRY_CODES, but a direct API call could send
    # something else.
    if body.country and not is_country(body.country):
        return "Country is invalid"
    if body.alt_email and not validate_email(body.alt_email):
        return "Additional email address is invalid"
    if body.linkedin and not validate_url(body.linkedin):
        return "LinkedIn URL is invalid"
    if body.github and not validate_url(body.github):
        return "GitHub URL is invalid"
    return None
