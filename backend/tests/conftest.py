"""Shared pytest fixtures.

Set TEST_DATABASE_URL to run the database-backed tests, e.g.

    TEST_DATABASE_URL=postgres://localhost/db_template_test pytest

Without it, the database tests skip and the unit tests still run - the same
behavior as the Rust backend's integration tests.
"""

from __future__ import annotations

import os
from dataclasses import replace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

# Point the app at the test database and pin a deterministic secret BEFORE the
# app is imported. load_env_files() uses setdefault, so these always win.
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET"] = "test-secret"
os.environ["EMAIL_VERIFICATION_REQUIRED"] = "false"
os.environ.setdefault("NODE_ENV", "")

from app.config import Settings, get_settings  # noqa: E402
from app.db.session import create_all, dispose_engine  # noqa: E402
from app.main import app  # noqa: E402

requires_db = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"
)


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Dev-like settings with env="" so login codes are random and no admin is
    seeded (mirrors the Rust tests' test_config(""))."""
    return replace(
        get_settings(),
        env="",
        jwt_secret="test-secret",
        email_verification_required=False,
        frontend_url="http://localhost:3000",
    )


@pytest.fixture(autouse=True)
def _override_settings(settings: Settings):
    app.dependency_overrides[get_settings] = lambda: settings
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _database():
    if not TEST_DATABASE_URL:
        yield
        return
    await create_all()
    yield
    await dispose_engine()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
