"""Staff/admin user management endpoints, ported from users.rs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, ensure_role, get_current_user
from app.api.responses import internal_error, msg, respond
from app.config import Settings, get_settings
from app.db.errors import is_unique_violation
from app.db.session import get_db
from app.models import User
from app.schemas.users import CreateUserRequest, PatchRoleRequest, UserSummary
from app.services.email_queue import (
    QueueNotFound,
    queue_password_reset,
    queue_verification_email,
)
from app.services.roles import BELOW_STAFF, ROLES, has_role, role_index
from app.services.security import hash_password
from app.services.validation import validate_email, validate_password

router = APIRouter(prefix="/api", tags=["users"])


def _parse_id(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        return None


@router.get("/users")
async def list_users(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    ensure_role(user, "staff")

    stmt = select(User.id, User.email, User.role, User.email_verified, User.created_at)
    # Staff sees every tier at or below their own; admin sees everyone.
    if not has_role(user.role, "admin"):
        stmt = stmt.where(User.role.in_(BELOW_STAFF))
    stmt = stmt.order_by(User.created_at.asc())

    try:
        rows = (await db.execute(stmt)).all()
    except SQLAlchemyError as err:
        return internal_error("List Users Error", err)

    users = [
        UserSummary(
            id=row.id,
            email=row.email,
            role=row.role,
            emailVerified=row.email_verified,
            createdAt=row.created_at,
        ).model_dump(by_alias=True, mode="json")
        for row in rows
    ]
    return respond(200, {"users": users})


@router.post("/users")
async def admin_create_user(
    body: CreateUserRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    ensure_role(user, "admin")

    if not validate_email(body.email):
        return respond(400, msg("Invalid email address"))
    password_error = validate_password(body.password)
    if password_error:
        return respond(400, msg(password_error))

    created = User(
        email=body.email,
        password=hash_password(body.password),
        role="client",
        email_verified=True,
        must_change_password=True,
    )
    try:
        db.add(created)
        await db.flush()
        await db.refresh(created)
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        if is_unique_violation(err):
            return respond(400, msg("Email is already registered"))
        return internal_error("Admin Create User Error", err)

    return respond(
        201,
        {
            "message": "User created successfully!",
            "user": {
                "id": created.id,
                "email": created.email,
                "role": created.role,
                "emailVerified": created.email_verified,
            },
        },
    )


@router.post("/users/{user_id}/resend-verification")
async def staff_resend_verification(
    user_id: str = Path(...),
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> object:
    ensure_role(user, "staff")

    parsed = _parse_id(user_id)
    if parsed is None:
        return respond(400, msg("Invalid user id"))

    row = (
        await db.execute(
            select(User.id, User.email, User.email_verified).where(User.id == parsed)
        )
    ).first()
    if row is None:
        return respond(404, msg("User not found"))
    if row.email_verified:
        return respond(400, msg("User is already verified"))

    try:
        await queue_verification_email(db, settings.frontend_url, row.id, row.email)
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Resend Verification Error", err)

    return respond(200, {"message": "Verification email sent"})


@router.patch("/users/{user_id}/verification")
async def patch_verification(
    user_id: str = Path(...),
    payload: dict[str, Any] | None = Body(default=None),
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    ensure_role(user, "admin")

    parsed = _parse_id(user_id)
    if parsed is None:
        return respond(400, msg("Invalid user id"))

    # A present-but-non-boolean value reads as not-a-boolean.
    verified = (payload or {}).get("emailVerified")
    if not isinstance(verified, bool):
        return respond(400, msg("emailVerified must be a boolean"))

    try:
        row = (
            await db.execute(
                update(User)
                .where(User.id == parsed)
                .values(email_verified=verified, verification_token=None)
                .returning(User.id, User.email, User.email_verified)
            )
        ).first()
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Update Verification Error", err)

    if row is None:
        return respond(404, msg("User not found"))

    message = (
        "User marked as verified" if row.email_verified else "User marked as unverified"
    )
    return respond(
        200,
        {
            "message": message,
            "user": {
                "id": row.id,
                "email": row.email,
                "emailVerified": row.email_verified,
            },
        },
    )


@router.patch("/users/{user_id}/role")
async def patch_role(
    body: PatchRoleRequest,
    user_id: str = Path(...),
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    ensure_role(user, "admin")

    parsed = _parse_id(user_id)
    if parsed is None:
        return respond(400, msg("Invalid user id"))

    if role_index(body.role) is None:
        return respond(400, msg(f"role must be one of: {', '.join(ROLES)}"))
    # Block self-demotion so an admin can't lock themselves out of admin routes.
    if parsed == user.id:
        return respond(400, msg("Cannot change your own role"))

    try:
        row = (
            await db.execute(
                update(User)
                .where(User.id == parsed)
                .values(role=body.role)
                .returning(User.id, User.email, User.role)
            )
        ).first()
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Update Role Error", err)

    if row is None:
        return respond(404, msg("User not found"))

    return respond(
        200,
        {
            "message": "User role updated",
            "user": {"id": row.id, "email": row.email, "role": row.role},
        },
    )


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str = Path(...),
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> object:
    ensure_role(user, "admin")

    parsed = _parse_id(user_id)
    if parsed is None:
        return respond(400, msg("Invalid user id"))

    try:
        await queue_password_reset(db, settings.frontend_url, parsed)
    except QueueNotFound:
        return respond(404, msg("User not found"))
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Admin Reset Password Error", err)

    return respond(200, {"message": "Password reset email sent"})


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str = Path(...),
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    ensure_role(user, "admin")

    parsed = _parse_id(user_id)
    if parsed is None:
        return respond(400, msg("Invalid user id"))
    if parsed == user.id:
        return respond(400, msg("Cannot delete your own account"))

    try:
        result = await db.execute(delete(User).where(User.id == parsed))
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Delete User Error", err)

    if result.rowcount == 0:
        return respond(404, msg("User not found"))
    return respond(200, {"message": "User deleted"})
