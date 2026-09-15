"""Database-backed tests for admin-granted subscriptions."""

from __future__ import annotations

from tests.helpers import (
    cleanup,
    do_json,
    fill_profile,
    login,
    own_user_id,
    requires_db,
    set_role,
    signup,
    unique_email,
)

pytestmark = requires_db


async def _user(client, prefix: str, role: str | None = None) -> tuple[str, str, int]:
    email = unique_email(prefix)
    await signup(client, email)
    token = await login(client, email)
    await fill_profile(client, token)
    if role:
        await set_role(email, role)
    return email, token, await own_user_id(client, token)


async def test_admin_grants_and_revokes(client):
    admin_email, admin_token, _ = await _user(client, "admin", "admin")
    artist_email, _, artist_id = await _user(client, "artist", "artist")
    client_email, client_token, client_id = await _user(client, "client")
    try:
        response, body = await do_json(
            client,
            "POST",
            "/api/subscriptions",
            token=admin_token,
            json={
                "subscriberId": client_id,
                "artistId": artist_id,
                "level": "premium",
                "note": "inv-1",
            },
        )
        assert response.status_code == 201, body
        subscription_id = body["id"]
        assert "premium work" in body["message"]

        # The customer can see their own access, and at what level.
        response, body = await do_json(
            client, "GET", "/api/subscriptions/mine", token=client_token
        )
        assert response.status_code == 200
        assert [s["artistId"] for s in body["subscriptions"]] == [artist_id]
        assert body["subscriptions"][0]["level"] == "premium"
        assert body["subscriptions"][0]["note"] == "inv-1"

        # Granting twice is refused rather than silently duplicated.
        response, body = await do_json(
            client,
            "POST",
            "/api/subscriptions",
            token=admin_token,
            json={"subscriberId": client_id, "artistId": artist_id},
        )
        assert response.status_code == 400
        assert "already subscribes" in body["message"]

        response, body = await do_json(
            client,
            "DELETE",
            f"/api/subscriptions/{subscription_id}",
            token=admin_token,
        )
        assert response.status_code == 200

        response, body = await do_json(
            client, "GET", "/api/subscriptions/mine", token=client_token
        )
        assert body["subscriptions"] == []
    finally:
        await cleanup(admin_email)
        await cleanup(artist_email)
        await cleanup(client_email)


async def test_granting_requires_admin(client):
    artist_email, _, artist_id = await _user(client, "artist", "artist")
    staff_email, staff_token, _ = await _user(client, "staff", "staff")
    client_email, client_token, client_id = await _user(client, "client")
    try:
        # A client can't even list them.
        response, body = await do_json(
            client, "GET", "/api/subscriptions", token=client_token
        )
        assert response.status_code == 403

        # Staff can look but not grant.
        response, body = await do_json(
            client, "GET", "/api/subscriptions", token=staff_token
        )
        assert response.status_code == 200
        response, body = await do_json(
            client,
            "POST",
            "/api/subscriptions",
            token=staff_token,
            json={"subscriberId": client_id, "artistId": artist_id},
        )
        assert response.status_code == 403
        assert body["message"] == "Insufficient permissions"
    finally:
        await cleanup(artist_email)
        await cleanup(staff_email)
        await cleanup(client_email)


async def test_level_defaults_to_paid_and_is_validated(client):
    admin_email, admin_token, _ = await _user(client, "admin", "admin")
    artist_email, _, artist_id = await _user(client, "artist", "artist")
    client_email, _, client_id = await _user(client, "client")
    try:
        # An unknown level is refused rather than stored.
        response, body = await do_json(
            client,
            "POST",
            "/api/subscriptions",
            token=admin_token,
            json={
                "subscriberId": client_id,
                "artistId": artist_id,
                "level": "gold",
            },
        )
        assert response.status_code == 400
        assert body["message"] == "level must be one of: paid, premium"

        # Blank (and omitted) means the ordinary paid level.
        response, body = await do_json(
            client,
            "POST",
            "/api/subscriptions",
            token=admin_token,
            json={"subscriberId": client_id, "artistId": artist_id, "level": "  "},
        )
        assert response.status_code == 201, body

        response, body = await do_json(
            client, "GET", "/api/subscriptions", token=admin_token
        )
        assert body["subscriptions"][0]["level"] == "paid"
    finally:
        await cleanup(admin_email)
        await cleanup(artist_email)
        await cleanup(client_email)


async def test_granting_to_a_non_artist_is_refused(client):
    admin_email, admin_token, _ = await _user(client, "admin", "admin")
    other_email, _, other_id = await _user(client, "client")
    client_email, _, client_id = await _user(client, "client")
    try:
        response, body = await do_json(
            client,
            "POST",
            "/api/subscriptions",
            token=admin_token,
            json={"subscriberId": client_id, "artistId": other_id},
        )
        assert response.status_code == 400
        assert "is not an artist" in body["message"]
    finally:
        await cleanup(admin_email)
        await cleanup(other_email)
        await cleanup(client_email)


async def test_unknown_ids_are_not_found(client):
    admin_email, admin_token, _ = await _user(client, "admin", "admin")
    try:
        response, body = await do_json(
            client,
            "POST",
            "/api/subscriptions",
            token=admin_token,
            json={"subscriberId": 999_999, "artistId": 999_999},
        )
        assert response.status_code == 404
        assert body["message"] == "Subscriber not found"
    finally:
        await cleanup(admin_email)
