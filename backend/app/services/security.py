"""Passwords, JWTs, and random tokens/codes.

Ported from the Rust backend's auth.rs. The scrypt format is Node-compatible
(``salt_hex:key_hex``, salt fed to scrypt as its hex string), so existing
Go/Rust/Node hashes verify unchanged.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

import jwt

# Node scrypt defaults: N=16384, r=8, p=1, 16-byte salt, 64-byte key.
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LEN = 64

# Sessions expire SESSION_TTL_SECS after issue; middleware slides active ones
# forward once they pass the half-life.
SESSION_TTL_SECS = 600  # 10 minutes
RENEW_THRESHOLD_SECS = 300  # half-life

_ALGORITHM = "HS256"


def _scrypt_key(password: str, salt_hex: str) -> bytes:
    return hashlib.scrypt(
        password.encode(),
        salt=salt_hex.encode(),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_LEN,
    )


def hash_password(password: str) -> str:
    salt_hex = secrets.token_hex(16)
    return f"{salt_hex}:{_scrypt_key(password, salt_hex).hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, sep, hash_hex = stored.partition(":")
    if not sep:
        return False
    try:
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    key = _scrypt_key(password, salt_hex)
    return len(expected) == len(key) and hmac.compare_digest(expected, key)


def issue_token_with_ttl(email: str, secret: str, ttl_secs: int) -> str:
    now = int(time.time())
    claims = {"email": email, "exp": now + ttl_secs, "iat": now}
    return jwt.encode(claims, secret, algorithm=_ALGORITHM)


def issue_token(email: str, secret: str) -> str:
    """HS256, claim {email}, 10-minute expiry."""
    return issue_token_with_ttl(email, secret, SESSION_TTL_SECS)


def _decode(token: str, secret: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            options={"require": ["exp"], "verify_aud": False, "verify_iss": False},
            leeway=0,
        )
    except jwt.PyJWTError:
        return None


def verify_token(token: str, secret: str) -> str | None:
    """Return the email claim, or None on any failure."""
    claims = _decode(token, secret)
    if claims is None:
        return None
    email = claims.get("email")
    return email if email else None


def random_token() -> str:
    return secrets.token_hex(32)


def renew_token_if_due(token: str, secret: str) -> str | None:
    """Re-issue a token past its half-life; expired/invalid ones are never renewed."""
    claims = _decode(token, secret)
    if claims is None:
        return None
    exp = claims.get("exp")
    if exp is None:
        return None
    if exp - int(time.time()) < RENEW_THRESHOLD_SECS:
        return issue_token(claims.get("email", ""), secret)
    return None


def random_code(env: str) -> str:
    """A 4-digit login code. In development it's always 1234."""
    if env == "development":
        return "1234"
    raw = secrets.token_bytes(2)
    n = (raw[0] << 8) | raw[1]
    return f"{n % 10000:04d}"
