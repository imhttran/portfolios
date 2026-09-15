"""Unit tests for the field validators and profile validation."""

from __future__ import annotations

from app.schemas.profile import ProfileInput
from app.services.validation import (
    optional_trimmed,
    validate_email,
    validate_password,
    validate_profile_fields,
)


def test_email():
    assert validate_email("a@b.co")
    assert not validate_email("nope")
    assert not validate_email("a@b")
    assert not validate_email("a b@c.co")


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


def test_profile_valid():
    assert (
        validate_profile_fields(ProfileInput(firstName="Test", lastName="User")) is None
    )


def test_profile_missing_fields():
    message = validate_profile_fields(ProfileInput(firstName="", lastName="  "))
    assert message is not None
    assert "firstName" in message and "lastName" in message
