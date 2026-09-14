"""Unit tests for the field validators and profile validation."""

from __future__ import annotations

from app.schemas.profile import ProfileInput
from app.services.validation import (
    optional_trimmed,
    validate_email,
    validate_password,
    validate_phone,
    validate_profile_fields,
    validate_url,
    validate_zip,
)


def test_email():
    assert validate_email("a@b.co")
    assert not validate_email("nope")
    assert not validate_email("a@b")
    assert not validate_email("a b@c.co")


def test_phone():
    assert validate_phone("555-123-4567")
    assert validate_phone("(555) 123-4567")
    assert validate_phone("+1 555 123 4567")
    assert not validate_phone("12345")


def test_zip():
    assert validate_zip("94043")
    assert not validate_zip("9404")
    assert not validate_zip("94043-1234")


def test_url():
    assert validate_url("https://linkedin.com/in/x")
    assert validate_url("http://github.com/x")
    assert not validate_url("ftp://github.com/x")
    assert not validate_url("javascript:alert(1)")
    assert not validate_url("not a url")


def test_password_rules():
    assert validate_password("Valid123!") is None
    assert validate_password("short1!") == (
        "Password must be at least 8 characters long"
    )
    assert validate_password("lowercase1!") == (
        "Password must contain at least one uppercase letter"
    )
    assert validate_password("NoNumber!") == (
        "Password must contain at least one number"
    )
    assert validate_password("NoSpecial1") == (
        "Password must contain at least one special character"
    )


def test_optional_trimmed():
    assert optional_trimmed(None) is None
    assert optional_trimmed("  ") is None
    assert optional_trimmed("  x  ") == "x"


def _valid_profile(**overrides) -> ProfileInput:
    data = {
        "firstName": "Test",
        "lastName": "User",
        "address": "1 Test St",
        "state": "CA",
        "zip": "94043",
        "phone": "555-123-4567",
        "communicationPreference": "email",
    }
    data.update(overrides)
    return ProfileInput(**data)


def test_profile_valid():
    assert validate_profile_fields(_valid_profile()) is None


def test_profile_missing_fields():
    message = validate_profile_fields(_valid_profile(firstName="", lastName="  "))
    assert message is not None
    assert "firstName" in message and "lastName" in message


def test_profile_bad_values():
    assert validate_profile_fields(_valid_profile(state="XX")) == "State is invalid"
    assert validate_profile_fields(_valid_profile(zip="abc")) == "Zip code is invalid"
    assert (
        validate_profile_fields(_valid_profile(communicationPreference="fax"))
        is not None
    )
    assert (
        validate_profile_fields(_valid_profile(altEmail="nope"))
        == "Additional email address is invalid"
    )
    assert (
        validate_profile_fields(_valid_profile(linkedin="not a url"))
        == "LinkedIn URL is invalid"
    )
