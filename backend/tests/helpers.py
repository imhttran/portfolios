"""Async test helpers shared across the test modules."""

from __future__ import annotations

import os
import re
import uuid

import pytest
from httpx import AsyncClient

requires_db = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


def unique_email(prefix: str = "pytest") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@mail.com"


async def do_json(
    client: AsyncClient, method: str, path: str, token: str = "", json=None
):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.request(method, path, json=json, headers=headers)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response, body


async def signup(client: AsyncClient, email: str, password: str = "Valid123!"):
    return await do_json(
        client, "POST", "/api/signup", json={"email": email, "password": password}
    )


async def fetch_login_code(email: str) -> str:
    """Newest queued email for the address -> its 4-digit code."""
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import EmailQueue

    async with get_sessionmaker()() as session:
        body = await session.scalar(
            select(EmailQueue.body)
            .where(EmailQueue.to == email)
            .order_by(EmailQueue.id.desc())
            .limit(1)
        )
    match = re.search(r"\b\d{4}\b", body or "")
    assert match, f"no 4-digit code in queued email: {body!r}"
    return match.group(0)


async def login(
    client: AsyncClient,
    email: str,
    password: str = "Valid123!",
    device: str = "test-device",
) -> str:
    """Full login, transparently completing 2FA (the first login needs it)."""
    response, body = await do_json(
        client, "POST", "/api/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, f"login for {email} failed: {body}"
    token = (body or {}).get("token") or ""
    assert token, f"login for {email} returned no token"

    if body.get("twoFactorRequired"):
        code = await fetch_login_code(email)
        response, body = await do_json(
            client,
            "POST",
            "/api/login/verify",
            json={"token": token, "code": code, "deviceId": device},
        )
        assert response.status_code == 200, f"2FA verify for {email} failed: {body}"
        token = body.get("token") or ""
        assert token, f"2FA verify for {email} returned no token"
    return token


async def fill_profile(client: AsyncClient, token: str):
    return await do_json(
        client,
        "POST",
        "/api/profile",
        token=token,
        json={
            "firstName": "Test",
            "lastName": "User",
            "address": "1 Test St",
            "state": "CA",
            "zip": "94043",
            "phone": "555-123-4567",
            "communicationPreference": "email",
        },
    )


async def set_role(email: str, role: str) -> None:
    from sqlalchemy import update

    from app.db.session import get_sessionmaker
    from app.models import User

    async with get_sessionmaker()() as session:
        await session.execute(update(User).where(User.email == email).values(role=role))
        await session.commit()


async def own_user_id(client: AsyncClient, token: str) -> int:
    response, body = await do_json(client, "GET", "/api/me", token=token)
    assert response.status_code == 200, f"/api/me failed: {body}"
    return body["user"]["id"]


async def cleanup(email: str) -> None:
    """Best-effort teardown so reruns against a dirty database still pass."""
    from sqlalchemy import delete

    from app.db.session import get_sessionmaker
    from app.models import EmailQueue, User

    async with get_sessionmaker()() as session:
        await session.execute(delete(User).where(User.email == email))
        await session.execute(delete(EmailQueue).where(EmailQueue.to == email))
        await session.commit()
