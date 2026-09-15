"""A user's own name: GET/POST /api/profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_current_user
from app.api.responses import internal_error, msg, respond
from app.db.errors import is_unique_violation
from app.db.session import get_db
from app.models import UserProfile
from app.schemas.profile import ProfileInput, ProfileOut
from app.services.validation import validate_profile_fields

router = APIRouter(prefix="/api", tags=["profile"])

_PROFILE_COLUMNS = (
    UserProfile.id,
    UserProfile.user_id,
    UserProfile.first_name,
    UserProfile.last_name,
)


def _serialize(row) -> dict:
    return ProfileOut(
        id=row.id,
        userId=row.user_id,
        firstName=row.first_name,
        lastName=row.last_name,
    ).model_dump(by_alias=True, mode="json")


@router.get("/profile")
async def get_profile(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    row = (
        await db.execute(
            select(*_PROFILE_COLUMNS).where(UserProfile.user_id == user.id)
        )
    ).first()
    # A missing profile is a 200 with null, not a 404: having one is optional.
    return respond(200, {"profile": _serialize(row) if row else None})


@router.post("/profile")
async def save_profile(
    body: ProfileInput,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    validation_error = validate_profile_fields(body)
    if validation_error:
        return respond(400, msg(validation_error))

    profile = UserProfile(
        user_id=user.id,
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
    )
    try:
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
        await db.commit()
    except SQLAlchemyError as err:
        await db.rollback()
        if is_unique_violation(err):
            return respond(400, msg("Profile already exists"))
        return internal_error("Save Profile Error", err)

    return respond(
        201,
        {
            "message": "Profile saved!",
            "profile": _serialize(profile),
        },
    )
