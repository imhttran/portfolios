"""Database-backed auth tests: signup, login, 2FA, sessions, password reset."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.session import get_sessionmaker
from app.models import User, UserDevice
from app.services.security import issue_token, issue_token_with_ttl
from tests.helpers import (
    cleanup,
    do_json,
    login,
    requires_db,
    set_role,
    signup,
    unique_email,
)

pytestmark = requires_db


async def test_signup_weak_password(client):
    response, body = await signup(client, unique_email(), password="weak")
    assert response.status_code == 400
    assert "at least 8 characters" in body["message"]


async def test_signup_and_login_happy_path(client):
    email = unique_email()
    try:
        response, body = await signup(client, email)
        assert response.status_code == 201, body
        assert body["user"]["email"] == email

        token = await login(client, email)
        response, body = await do_json(client, "GET", "/api/me", token=token)
        assert response.status_code == 200, body
        assert body["user"]["email"] == email
        assert body["user"]["role"] == "client"
    finally:
        await cleanup(email)


async def test_me_requires_token(client):
    response, body = await do_json(client, "GET", "/api/me")
    assert response.status_code == 401
    assert body == {"message": "No token provided"}

    response, body = await do_json(client, "GET", "/api/me", token="not-a-jwt")
    assert response.status_code == 403
    assert body == {"message": "Invalid or expired token"}


async def test_two_factor_login(client):
    email = unique_email()
    try:
        response, _ = await signup(client, email)
        assert response.status_code == 201

        # First login from an unknown device -> 2FA required, no real JWT.
        response, body = await do_json(
            client,
            "POST",
            "/api/login",
            json={"email": email, "password": "Valid123!", "deviceId": "dev-1"},
        )
        assert response.status_code == 200, body
        assert body["twoFactorRequired"] is True
        pending = body["token"]
        assert pending

        # Wrong code -> 400, code stays pending.
        response, _ = await do_json(
            client,
            "POST",
            "/api/login/verify",
            json={"token": pending, "code": "0000", "deviceId": "dev-1"},
        )
        assert response.status_code == 400

        # Resend rotates the code.
        response, _ = await do_json(
            client, "POST", "/api/login/resend", json={"token": pending}
        )
        assert response.status_code == 200

        # Correct (resent) code -> real JWT.
        from tests.helpers import fetch_login_code

        code = await fetch_login_code(email)
        response, body = await do_json(
            client,
            "POST",
            "/api/login/verify",
            json={"token": pending, "code": code, "deviceId": "dev-1"},
        )
        assert response.status_code == 200, body
        token = body["token"]
        assert token and token != pending

        response, _ = await do_json(client, "GET", "/api/me", token=token)
        assert response.status_code == 200

        # Same device again -> 2FA skipped.
        response, body = await do_json(
            client,
            "POST",
            "/api/login",
            json={"email": email, "password": "Valid123!", "deviceId": "dev-1"},
        )
        assert response.status_code == 200, body
        assert body.get("twoFactorRequired") is not True
        assert body["token"]
    finally:
        await cleanup(email)


async def test_a_lapsed_device_has_to_verify_again(client):
    """Trust expires. A device trusted forever is how a stolen laptop stays a way in."""
    email = unique_email()
    try:
        await signup(client, email)
        await login(client, email, device="lapsing")

        async with get_sessionmaker()() as session:
            await session.execute(
                update(UserDevice).values(
                    expires_at=datetime.now(UTC) - timedelta(minutes=1)
                )
            )
            await session.commit()

        # The same device is no longer trusted, so 2FA comes back.
        response, body = await do_json(
            client,
            "POST",
            "/api/login",
            json={"email": email, "password": "Valid123!", "deviceId": "lapsing"},
        )
        assert response.status_code == 200, body
        assert body["twoFactorRequired"] is True
    finally:
        await cleanup(email)


async def test_verifying_again_slides_the_trust_forward(client):
    from tests.helpers import fetch_login_code

    email = unique_email()
    try:
        await signup(client, email)
        await login(client, email, device="sliding")

        async with get_sessionmaker()() as session:
            near = await session.scalar(
                select(UserDevice.expires_at).where(UserDevice.device_id == "sliding")
            )
            # Push it close to lapsing without lapsing it.
            await session.execute(
                update(UserDevice).values(
                    expires_at=datetime.now(UTC) + timedelta(minutes=5)
                )
            )
            await session.commit()

        response, body = await do_json(
            client,
            "POST",
            "/api/login",
            json={"email": email, "password": "Valid123!", "deviceId": "sliding"},
        )
        # Still trusted, so it skips 2FA - but the clock is nearly out.
        assert body.get("twoFactorRequired") is not True, body

        # Force a verification, which should push the expiry out again.
        async with get_sessionmaker()() as session:
            await session.execute(
                update(UserDevice).values(
                    expires_at=datetime.now(UTC) - timedelta(minutes=1)
                )
            )
            await session.commit()

        response, body = await do_json(
            client,
            "POST",
            "/api/login",
            json={"email": email, "password": "Valid123!", "deviceId": "sliding"},
        )
        pending = body["token"]
        code = await fetch_login_code(email)
        response, body = await do_json(
            client,
            "POST",
            "/api/login/verify",
            json={"token": pending, "code": code, "deviceId": "sliding"},
        )
        assert response.status_code == 200, body

        async with get_sessionmaker()() as session:
            after = await session.scalar(
                select(UserDevice.expires_at).where(UserDevice.device_id == "sliding")
            )

        assert after > near, (near, after)
        assert after > datetime.now(UTC) + timedelta(days=20)
    finally:
        await cleanup(email)


async def test_two_users_can_each_trust_the_same_browser(client):
    """device_id is unique per user, not globally: two people share a laptop."""
    first = unique_email("first")
    second = unique_email("second")
    try:
        for email in (first, second):
            await signup(client, email)
            await login(client, email, device="shared-browser")

        async with get_sessionmaker()() as session:
            rows = (
                (
                    await session.execute(
                        select(UserDevice.user_id).where(
                            UserDevice.device_id == "shared-browser"
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 2, rows

        # And each still skips 2FA on its own account.
        for email in (first, second):
            response, body = await do_json(
                client,
                "POST",
                "/api/login",
                json={
                    "email": email,
                    "password": "Valid123!",
                    "deviceId": "shared-browser",
                },
            )
            assert body.get("twoFactorRequired") is not True, (email, body)
    finally:
        await cleanup(first)
        await cleanup(second)


async def test_session_slides_while_active(client):
    email = unique_email()
    try:
        await signup(client, email)

        # 60 seconds left of the 10-minute window -> renewed on use.
        aging = issue_token_with_ttl(email, "test-secret", 60)
        response, _ = await do_json(client, "GET", "/api/me", token=aging)
        assert response.status_code == 200
        renewed = response.headers.get("X-Renewed-Token")
        assert renewed and renewed != aging

        response, _ = await do_json(client, "GET", "/api/me", token=renewed)
        assert response.status_code == 200

        # A fresh token is not renewed.
        fresh = issue_token(email, "test-secret")
        response, _ = await do_json(client, "GET", "/api/me", token=fresh)
        assert response.status_code == 200
        assert response.headers.get("X-Renewed-Token") is None

        # Past the window, the token is rejected outright.
        expired = issue_token_with_ttl(email, "test-secret", -60)
        response, _ = await do_json(client, "GET", "/api/me", token=expired)
        assert response.status_code == 403
    finally:
        await cleanup(email)


async def test_forgot_and_reset_password(client):
    email = unique_email()
    try:
        await signup(client, email)

        response, body = await do_json(
            client, "POST", "/api/forgot-password", json={"email": email}
        )
        assert response.status_code == 200
        assert "if that email is registered" in body["message"].lower()

        async with get_sessionmaker()() as session:
            reset_token = await session.scalar(
                select(User.reset_token).where(User.email == email)
            )
        assert reset_token

        response, body = await do_json(
            client,
            "POST",
            "/api/reset-password",
            json={"token": reset_token, "password": "NewPass123!"},
        )
        assert response.status_code == 200, body
        assert body["user"]["email"] == email

        # The old password no longer works; the new one does.
        response, _ = await do_json(
            client, "POST", "/api/login", json={"email": email, "password": "Valid123!"}
        )
        assert response.status_code == 401
        assert await login(client, email, password="NewPass123!")
    finally:
        await cleanup(email)


async def test_change_password(client):
    email = unique_email()
    try:
        await signup(client, email)
        token = await login(client, email)

        response, body = await do_json(
            client,
            "POST",
            "/api/change-password",
            token=token,
            json={"currentPassword": "Wrong123!", "newPassword": "NewPass123!"},
        )
        assert response.status_code == 401
        assert body["message"] == "Current password is incorrect"

        response, body = await do_json(
            client,
            "POST",
            "/api/change-password",
            token=token,
            json={"currentPassword": "Valid123!", "newPassword": "NewPass123!"},
        )
        assert response.status_code == 200, body
        assert await login(client, email, password="NewPass123!", device="other-device")
    finally:
        await cleanup(email)


async def test_a_staff_account_needs_no_registration_form(client):
    """A session and the right role are enough.

    This used to be a gate: staff and admin were blocked until they filled in a
    mailing address. Nothing collects one now.
    """
    email = unique_email()
    try:
        await signup(client, email)
        await set_role(email, "staff")
        token = await login(client, email)

        response, body = await do_json(client, "GET", "/api/users", token=token)
        assert response.status_code == 200, body
    finally:
        await cleanup(email)


async def test_resend_verification_is_enumeration_safe(client):
    email = unique_email()
    try:
        # Unknown email -> same generic 200 as a real one.
        response, body = await do_json(
            client, "POST", "/api/resend-verification", json={"email": email}
        )
        assert response.status_code == 200
        assert "if that email is registered" in body["message"].lower()
    finally:
        await cleanup(email)
