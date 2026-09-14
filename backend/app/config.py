"""Runtime configuration, ported from the Rust backend's config.rs.

A personal root ``.env`` always wins (existing env vars are never overwritten);
the committed dev profile (``.env.dev``) only fills in when ``NODE_ENV`` is
unset or ``development``.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Default DSN for local development, used when DATABASE_URL is unset (both by
# the server and the set-role subcommand).
DEFAULT_DATABASE_URL = (
    "postgres://postgres:postgres@localhost:5432/db_template?sslmode=disable"
)


def _env_or(key: str, fallback: str) -> str:
    """Go's envOr: an empty value counts as unset."""
    value = os.environ.get(key)
    return value if value else fallback


def _int_or(key: str, fallback: int) -> int:
    """Go's intOr: unparsable or non-positive falls back."""
    try:
        value = int(os.environ.get(key, ""))
    except (TypeError, ValueError):
        return fallback
    return value if value > 0 else fallback


@dataclass(frozen=True)
class Settings:
    port: int
    database_url: str
    env: str  # development | qa | production
    frontend_url: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    mail_from: str
    max_attempts: int
    email_verification_required: bool
    jwt_secret: str


def load_env_files() -> None:
    """Load ``.env`` (root wins) then ``.env.dev`` for development.

    Mirrors config.rs's load_env_files: existing environment variables always
    win, quotes are stripped, and a leading ``export `` is tolerated.
    """

    def apply_env(path: Path) -> None:
        try:
            contents = path.read_text()
        except OSError:
            return
        for raw in contents.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            key, sep, value = line.partition("=")
            if not sep:
                continue
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)

    for directory in (".", ".."):
        path = Path(directory) / ".env"
        if path.exists():
            apply_env(path)
            break

    # Unset counts as development, otherwise .env.dev could never be seen,
    # since .env.dev is itself what sets NODE_ENV.
    node_env = os.environ.get("NODE_ENV", "")
    if node_env in ("", "development"):
        for directory in (".", ".."):
            path = Path(directory) / ".env.dev"
            if path.exists():
                apply_env(path)
                break


@lru_cache
def get_settings() -> Settings:
    env = _env_or("NODE_ENV", "development")

    jwt_secret = os.environ.get("JWT_SECRET") or ""
    if not jwt_secret:
        if env == "production":
            print("JWT_SECRET must be set in production", file=sys.stderr)
            raise SystemExit(1)
        print(
            "[config] JWT_SECRET not set - using insecure dev fallback",
            file=sys.stderr,
        )
        jwt_secret = "dev-insecure-jwt-secret"

    return Settings(
        port=_int_or("PORT", 8080),
        database_url=_env_or("DATABASE_URL", DEFAULT_DATABASE_URL),
        env=env,
        frontend_url=_env_or("FRONTEND_URL", "http://localhost:3000"),
        smtp_host=os.environ.get("SMTP_HOST", ""),
        smtp_port=_int_or("SMTP_PORT", 587),
        smtp_user=os.environ.get("SMTP_USER", ""),
        smtp_pass=os.environ.get("SMTP_PASS", ""),
        mail_from=_env_or("MAIL_FROM", "no-reply@example.com"),
        max_attempts=_int_or("MAX_ATTEMPTS", 3),
        # Bypass email verification only when explicitly set to "false".
        email_verification_required=os.environ.get("EMAIL_VERIFICATION_REQUIRED")
        != "false",
        jwt_secret=jwt_secret,
    )


def fatal(context: str, err: object) -> None:
    """Print and exit, matching the Rust backend's fatal()."""
    print(f"{context}: {err}", file=sys.stderr)
    raise SystemExit(1)
