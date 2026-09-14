"""Unit tests for password hashing, JWTs, and token/code generation."""

from __future__ import annotations

from app.services.security import (
    SESSION_TTL_SECS,
    hash_password,
    issue_token,
    issue_token_with_ttl,
    random_code,
    renew_token_if_due,
    verify_password,
    verify_token,
)

# A hash created by the original Go backend (the dev-admin seed). If this ever
# fails, the Node-compatible scrypt format has drifted.
GO_BACKEND_HASH = (
    "1b3720e73189cbc4c90595519584e629:"
    "b9d00978ebbb9477a6751a63c02933922146945a21ae6ee7c25d012cb3350917"
    "4daef57c7f782cfed8f811c4af52a6cc07ff476fccf2f3fe1b7abe880211772d"
)


def test_password_round_trip():
    stored = hash_password("Valid123!")
    assert verify_password("Valid123!", stored)
    assert not verify_password("Wrong123!", stored)


def test_verifies_hashes_created_by_the_go_backend():
    assert verify_password("Password1234!", GO_BACKEND_HASH)
    assert not verify_password("Password12345", GO_BACKEND_HASH)


def test_jwt_round_trip():
    token = issue_token("a@b.c", "secret")
    assert verify_token(token, "secret") == "a@b.c"
    assert verify_token(token, "other") is None


def test_renewal_only_past_half_life():
    # A fresh (full-life) token is not renewed...
    fresh = issue_token("a@b.c", "secret")
    assert renew_token_if_due(fresh, "secret") is None
    # ...one deep into its life is...
    due = issue_token_with_ttl("a@b.c", "secret", 60)
    renewed = renew_token_if_due(due, "secret")
    assert renewed is not None
    assert verify_token(renewed, "secret") == "a@b.c"
    # ...and an expired one is dead, not renewable.
    expired = issue_token_with_ttl("a@b.c", "secret", -60)
    assert renew_token_if_due(expired, "secret") is None


def test_rejects_garbage():
    assert verify_token("not-a-jwt", "secret") is None
    assert not verify_password("x", "no-colon")
    assert not verify_password("x", "zz:nothex")


def test_session_ttl_is_ten_minutes():
    assert SESSION_TTL_SECS == 600


def test_random_code_is_1234_in_development():
    assert random_code("development") == "1234"


def test_random_code_is_four_digits_elsewhere():
    for _ in range(50):
        code = random_code("production")
        assert len(code) == 4
        assert code.isdigit()


def test_random_token_is_32_bytes_hex():
    from app.services.security import random_token

    token = random_token()
    assert len(token) == 64
    int(token, 16)  # raises if not hex
