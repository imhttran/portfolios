"""Public auth endpoints, /api/me, and self-service password change.

Handler behavior mirrors the Rust backend's auth.rs response-for-response.
"""

from __future__ import annotations

import hmac
import sys
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_current_user
from app.api.responses import internal_error, msg, respond
from app.config import Settings, get_settings
from app.db.errors import is_unique_violation
from app.db.session import get_db
from app.models import LoginCode, User, UserDevice
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailRequest,
    LoginRequest,
    MeUser,
    ResendCodeRequest,
    ResetPasswordRequest,
    SignupRequest,
    VerifyLoginRequest,
)
from app.services import mail
from app.services.email_queue import (
    QueueNotFound,
    queue_password_reset,
    queue_verification_email,
)
from app.services.security import (
    hash_password,
    issue_token,
    random_code,
    random_token,
    verify_password,
)
from app.services.validation import validate_email, validate_password

router = APIRouter(prefix="/api", tags=["auth"])


def trusted_until(settings: Settings) -> datetime:
    """When a device's trust lapses.

    Recomputed on every verification, so the window slides with use: an active
    browser stays trusted, and a device nobody has used in a month has to prove
    itself again.
    """
    return datetime.now(UTC) + timedelta(days=settings.device_trust_days)


LOGIN_CODE_TTL_MINUTES = 10
MAX_CODE_ATTEMPTS = 5
MAX_RESENDS = 3


def _login_success(email: str, token: str) -> dict:
    return {
        "message": "Login successful!",
        "token": token,
        "user": {"email": email},
    }


@router.get("/me")
async def me(user: AuthUser = Depends(get_current_user)) -> object:
    payload = MeUser(
        id=user.id,
        email=user.email,
        role=user.role,
        emailVerified=user.email_verified,
        mustChangePassword=user.must_change_password,
    )
    return respond(
        200,
        {
            "message": "Welcome to the secret area!",
            "user": payload.model_dump(by_alias=True, mode="json"),
        },
    )


@router.post("/signup")
async def signup(
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> object:
    if not validate_email(body.email):
        return respond(400, msg("Invalid email address"))
    password_error = validate_password(body.password)
    if password_error:
        return respond(400, msg(password_error))

    token = random_token()
    try:
        # Atomic: user + welcome email + verification email together, so a
        # failed enqueue never leaves an orphaned account.
        db.add(
            User(
                email=body.email,
                password=hash_password(body.password),
                email_verified=False,
                verification_token=token,
            )
        )
        await db.flush()
        db.add(mail.welcome_email(body.email))
        link = mail.token_link(settings.frontend_url, "verify", token)
        db.add(mail.verification_email(body.email, link))
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        if is_unique_violation(err):
            # Keep the message generic so the API can't be used to probe
            # registered emails; log the real reason server-side.
            print(
                f"[signup] rejected: email already registered (email={body.email})",
                file=sys.stderr,
            )
            return respond(400, msg("Unable to sign up. Please try again later."))
        return internal_error("Signup Error", err)

    return respond(
        201,
        {
            "message": "User created successfully!",
            "user": {"email": body.email},
        },
    )


@router.get("/verify")
async def verify(
    token: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
) -> object:
    if not token:
        return respond(400, msg("Missing verification token"))

    user_id = await db.scalar(select(User.id).where(User.verification_token == token))
    if user_id is None:
        return respond(400, msg("Invalid or expired verification link"))

    try:
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(email_verified=True, verification_token=None)
        )
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Verify Error", err)

    return respond(200, {"message": "Email verified successfully!"})


@router.post("/resend-verification")
async def resend_verification(
    body: EmailRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> object:
    if not validate_email(body.email):
        return respond(400, msg("Invalid email address"))

    row = (
        await db.execute(
            select(User.id, User.email_verified).where(User.email == body.email)
        )
    ).first()
    # Same response regardless of account existence/verified state, so this
    # endpoint can't be used to enumerate registered emails.
    if row is not None and not row.email_verified:
        try:
            await queue_verification_email(
                db, settings.frontend_url, row.id, body.email
            )
        except SQLAlchemyError as err:
            await db.rollback()
            return internal_error("Resend Verification Error", err)

    return respond(
        200,
        {
            "message": (
                "If that email is registered and unverified, "
                "a verification link has been sent."
            ),
        },
    )


@router.post("/forgot-password")
async def forgot_password(
    body: EmailRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> object:
    if not validate_email(body.email):
        return respond(400, msg("Invalid email address"))

    try:
        await queue_password_reset(db, settings.frontend_url, body.email)
    except QueueNotFound:
        pass  # fall through to the generic response
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Forgot Password Error", err)

    # Same response whether or not the account exists.
    return respond(
        200,
        {
            "message": "If that email is registered, a reset link has been sent.",
        },
    )


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> object:
    if not body.token:
        return respond(400, msg("Missing reset token"))
    password_error = validate_password(body.password)
    if password_error:
        return respond(400, msg(password_error))

    row = (
        await db.execute(
            select(User.id, User.email, User.reset_token_expiry).where(
                User.reset_token == body.token
            )
        )
    ).first()
    now = datetime.now(UTC)
    if row is None or row.reset_token_expiry is None or row.reset_token_expiry < now:
        return respond(400, msg("Invalid or expired reset link"))

    try:
        await db.execute(
            update(User)
            .where(User.id == row.id)
            .values(
                password=hash_password(body.password),
                reset_token=None,
                reset_token_expiry=None,
                must_change_password=False,
            )
        )
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Reset Password Error", err)

    return respond(
        200,
        {
            "message": "Password reset successfully!",
            "token": issue_token(row.email, settings.jwt_secret),
            "user": {"email": row.email},
        },
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> object:
    row = (
        await db.execute(
            select(User.id, User.password, User.email_verified).where(
                User.email == body.email
            )
        )
    ).first()
    if row is None or not verify_password(body.password, row.password):
        return respond(401, msg("Invalid email or password"))

    if settings.email_verification_required and not row.email_verified:
        return respond(403, msg("Please verify your email before logging in."))

    # Trusted device? Skip 2FA - but only while its trust hasn't lapsed.
    if body.device_id:
        known = await db.scalar(
            select(
                exists().where(
                    UserDevice.user_id == row.id,
                    UserDevice.device_id == body.device_id,
                    UserDevice.expires_at > func.now(),
                )
            )
        )
        if known:
            return respond(
                200,
                _login_success(
                    body.email, issue_token(body.email, settings.jwt_secret)
                ),
            )

    # New device: queue an emailed code and hand back a pending token; the real
    # JWT is only issued by /api/login/verify.
    pending = random_token()
    code = random_code(settings.env)
    try:
        db.add(
            LoginCode(
                user_id=row.id,
                token=pending,
                code=code,
                expires_at=datetime.now(UTC)
                + timedelta(minutes=LOGIN_CODE_TTL_MINUTES),
            )
        )
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Login Error", err)

    await _send_login_code(db, body.email, code)
    return respond(
        200,
        {
            "twoFactorRequired": True,
            "token": pending,
            "message": "Enter the code sent to your device",
        },
    )


@router.post("/login/verify")
async def verify_login(
    body: VerifyLoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> object:
    row = (
        await db.execute(
            select(
                LoginCode.user_id,
                LoginCode.code,
                LoginCode.expires_at,
                LoginCode.used,
                LoginCode.attempts,
                User.email,
            )
            .join(User, User.id == LoginCode.user_id)
            .where(LoginCode.token == body.token)
        )
    ).first()
    if row is None:
        return respond(400, msg("Invalid or expired code"))

    now = datetime.now(UTC)
    # Lock the code after a handful of failed tries so a 4-digit code can't be
    # brute-forced inside its 10-minute window.
    if row.used or now > row.expires_at or row.attempts >= MAX_CODE_ATTEMPTS:
        return respond(400, msg("Invalid or expired code"))

    if not hmac.compare_digest(row.code.encode(), body.code.encode()):
        await db.execute(
            update(LoginCode)
            .where(LoginCode.token == body.token)
            .values(attempts=LoginCode.attempts + 1)
        )
        await db.commit()
        return respond(400, msg("Invalid or expired code"))

    try:
        await db.execute(
            update(LoginCode).where(LoginCode.token == body.token).values(used=True)
        )
        if body.device_id:
            # On conflict *do update*, not do nothing: verifying again slides the
            # trust forward, so a device in regular use never has to re-verify
            # just because a fixed window elapsed.
            await db.execute(
                pg_insert(UserDevice)
                .values(
                    user_id=row.user_id,
                    device_id=body.device_id,
                    expires_at=trusted_until(settings),
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "device_id"],
                    set_={"expires_at": trusted_until(settings)},
                )
            )
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Verify Login Error", err)

    return respond(
        200, _login_success(row.email, issue_token(row.email, settings.jwt_secret))
    )


@router.post("/login/resend")
async def resend_login_code(
    body: ResendCodeRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> object:
    row = (
        await db.execute(
            select(
                LoginCode.resends,
                LoginCode.expires_at,
                LoginCode.used,
                User.email,
            )
            .join(User, User.id == LoginCode.user_id)
            .where(LoginCode.token == body.token)
        )
    ).first()
    if row is None:
        return respond(400, msg("Invalid or expired code"))

    now = datetime.now(UTC)
    if row.used or now > row.expires_at:
        return respond(400, msg("Invalid or expired code"))
    if row.resends >= MAX_RESENDS:
        return respond(429, msg("Too many resend attempts"))

    code = random_code(settings.env)
    try:
        await db.execute(
            update(LoginCode)
            .where(LoginCode.token == body.token)
            .values(
                code=code,
                resends=LoginCode.resends + 1,
                expires_at=now + timedelta(minutes=LOGIN_CODE_TTL_MINUTES),
            )
        )
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Resend Code Error", err)

    await _send_login_code(db, row.email, code)
    return respond(200, msg("Code resent"))


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    if not verify_password(body.current_password, user.password):
        return respond(401, msg("Current password is incorrect"))
    password_error = validate_password(body.new_password)
    if password_error:
        return respond(400, msg(password_error))

    try:
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(
                password=hash_password(body.new_password),
                must_change_password=False,
            )
        )
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Change Password Error", err)

    return respond(200, {"message": "Password changed successfully!"})


async def _send_login_code(db: AsyncSession, email: str, code: str) -> None:
    """Queue the 2FA code; the worker delivers it."""
    try:
        db.add(mail.login_code_email(email, code))
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
