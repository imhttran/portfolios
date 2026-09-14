"""Database-backed RBAC and admin user-management tests."""

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


async def _make_user(client, role: str | None = None) -> tuple[str, int, str]:
    """Sign up, complete onboarding, optionally set a role. Returns token + id."""
    email = unique_email(role or "client")
    await signup(client, email)
    token = await login(client, email)
    await fill_profile(client, token)
    if role:
        await set_role(email, role)
    user_id = await own_user_id(client, token)
    return email, user_id, token


async def test_list_users_rbac(client):
    client_email, _, client_token = await _make_user(client, "client")
    staff_email, _, staff_token = await _make_user(client, "staff")
    admin_email, _, admin_token = await _make_user(client, "admin")
    try:
        # Client can't list.
        response, body = await do_json(client, "GET", "/api/users", token=client_token)
        assert response.status_code == 403
        assert body["message"] == "Insufficient permissions"

        # Staff sees clients and staff, but not admins.
        response, body = await do_json(client, "GET", "/api/users", token=staff_token)
        assert response.status_code == 200
        emails = {u["email"] for u in body["users"]}
        assert client_email in emails and staff_email in emails
        assert admin_email not in emails

        # Admin sees everyone.
        response, body = await do_json(client, "GET", "/api/users", token=admin_token)
        assert response.status_code == 200
        emails = {u["email"] for u in body["users"]}
        assert {client_email, staff_email, admin_email} <= emails
    finally:
        for email in (client_email, staff_email, admin_email):
            await cleanup(email)


async def test_admin_create_user_forces_password_change(client):
    admin_email, _, admin_token = await _make_user(client, "admin")
    created_email = unique_email("created")
    try:
        response, body = await do_json(
            client,
            "POST",
            "/api/users",
            token=admin_token,
            json={"email": created_email, "password": "Valid123!"},
        )
        assert response.status_code == 201, body
        assert body["user"]["emailVerified"] is True

        # Duplicate email -> 400.
        response, body = await do_json(
            client,
            "POST",
            "/api/users",
            token=admin_token,
            json={"email": created_email, "password": "Valid123!"},
        )
        assert response.status_code == 400
        assert body["message"] == "Email is already registered"

        # The new user is gated until they change the admin-set password.
        token = await login(client, created_email)
        response, body = await do_json(client, "GET", "/api/users", token=token)
        assert response.status_code == 403
        assert body["message"] == "Password change required"

        response, body = await do_json(
            client,
            "POST",
            "/api/change-password",
            token=token,
            json={"currentPassword": "Valid123!", "newPassword": "NewPass123!"},
        )
        assert response.status_code == 200, body

        # Now the profile gate kicks in.
        response, body = await do_json(client, "GET", "/api/users", token=token)
        assert response.status_code == 403
        assert body["message"] == "Profile information required"
    finally:
        await cleanup(created_email)
        await cleanup(admin_email)


async def test_delete_own_account_is_blocked(client):
    admin_email, admin_id, admin_token = await _make_user(client, "admin")
    try:
        response, body = await do_json(
            client, "DELETE", f"/api/users/{admin_id}", token=admin_token
        )
        assert response.status_code == 400
        assert body["message"] == "Cannot delete your own account"
    finally:
        await cleanup(admin_email)


async def test_delete_user(client):
    admin_email, _, admin_token = await _make_user(client, "admin")
    victim_email, victim_id, _ = await _make_user(client, "client")
    try:
        response, body = await do_json(
            client, "DELETE", f"/api/users/{victim_id}", token=admin_token
        )
        assert response.status_code == 200, body
        assert body["message"] == "User deleted"

        # Gone now -> 404.
        response, body = await do_json(
            client, "DELETE", f"/api/users/{victim_id}", token=admin_token
        )
        assert response.status_code == 404

        # Non-numeric id -> 400.
        response, body = await do_json(
            client, "DELETE", "/api/users/abc", token=admin_token
        )
        assert response.status_code == 400
        assert body["message"] == "Invalid user id"
    finally:
        await cleanup(victim_email)
        await cleanup(admin_email)


async def test_patch_role(client):
    admin_email, admin_id, admin_token = await _make_user(client, "admin")
    target_email, target_id, _ = await _make_user(client, "client")
    try:
        # Invalid role value.
        response, body = await do_json(
            client,
            "PATCH",
            f"/api/users/{target_id}/role",
            token=admin_token,
            json={"role": "superuser"},
        )
        assert response.status_code == 400
        assert "role must be one of" in body["message"]

        # Admin can't change their own role.
        response, body = await do_json(
            client,
            "PATCH",
            f"/api/users/{admin_id}/role",
            token=admin_token,
            json={"role": "client"},
        )
        assert response.status_code == 400
        assert body["message"] == "Cannot change your own role"

        # Valid promotion.
        response, body = await do_json(
            client,
            "PATCH",
            f"/api/users/{target_id}/role",
            token=admin_token,
            json={"role": "staff"},
        )
        assert response.status_code == 200, body
        assert body["user"]["role"] == "staff"
    finally:
        await cleanup(target_email)
        await cleanup(admin_email)


async def test_patch_verification(client):
    admin_email, _, admin_token = await _make_user(client, "admin")
    target_email, target_id, _ = await _make_user(client, "client")
    try:
        response, body = await do_json(
            client,
            "PATCH",
            f"/api/users/{target_id}/verification",
            token=admin_token,
            json={"emailVerified": False},
        )
        assert response.status_code == 200, body
        assert body["message"] == "User marked as unverified"
        assert body["user"]["emailVerified"] is False

        # Non-boolean value is rejected.
        response, body = await do_json(
            client,
            "PATCH",
            f"/api/users/{target_id}/verification",
            token=admin_token,
            json={"emailVerified": "yes"},
        )
        assert response.status_code == 400
        assert body["message"] == "emailVerified must be a boolean"

        response, body = await do_json(
            client,
            "PATCH",
            f"/api/users/{target_id}/verification",
            token=admin_token,
            json={"emailVerified": True},
        )
        assert response.status_code == 200
        assert body["user"]["emailVerified"] is True
    finally:
        await cleanup(target_email)
        await cleanup(admin_email)


async def test_staff_resend_verification(client):
    staff_email, _, staff_token = await _make_user(client, "staff")
    pending_email = unique_email("pending")
    try:
        # An unverified user (signup leaves email_verified false).
        await signup(client, pending_email)
        from sqlalchemy import select

        from app.db.session import get_sessionmaker
        from app.models import User

        async with get_sessionmaker()() as session:
            pending_id = await session.scalar(
                select(User.id).where(User.email == pending_email)
            )

        response, body = await do_json(
            client,
            "POST",
            f"/api/users/{pending_id}/resend-verification",
            token=staff_token,
        )
        assert response.status_code == 200, body
        assert body["message"] == "Verification email sent"

        # Unknown id -> 404.
        response, body = await do_json(
            client, "POST", "/api/users/99999999/resend-verification", token=staff_token
        )
        assert response.status_code == 404
        assert body["message"] == "User not found"
    finally:
        await cleanup(pending_email)
        await cleanup(staff_email)
