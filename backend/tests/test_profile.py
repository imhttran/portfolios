"""Database-backed profile tests."""

from __future__ import annotations

from tests.helpers import (
    cleanup,
    do_json,
    fill_profile,
    login,
    requires_db,
    signup,
    unique_email,
)

pytestmark = requires_db


async def test_profile_flow(client):
    email = unique_email()
    try:
        await signup(client, email)
        token = await login(client, email)

        # Missing profile is a 200 with null, not a 404.
        response, body = await do_json(client, "GET", "/api/profile", token=token)
        assert response.status_code == 200
        assert body == {"profile": None}

        response, body = await fill_profile(client, token)
        assert response.status_code == 201, body
        assert body["profile"]["firstName"] == "Test"
        assert body["profile"]["lastName"] == "User"

        response, body = await do_json(client, "GET", "/api/profile", token=token)
        assert response.status_code == 200
        assert body["profile"]["lastName"] == "User"

        # A second save hits the unique constraint.
        response, body = await fill_profile(client, token)
        assert response.status_code == 400
        assert body["message"] == "Profile already exists"
    finally:
        await cleanup(email)


async def test_profile_validation_error(client):
    email = unique_email()
    try:
        await signup(client, email)
        token = await login(client, email)

        response, body = await do_json(
            client,
            "POST",
            "/api/profile",
            token=token,
            json={"firstName": "Test"},  # no last name
        )
        assert response.status_code == 400
        assert "Missing required field(s)" in body["message"]
    finally:
        await cleanup(email)
