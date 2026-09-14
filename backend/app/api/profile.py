"""The one-time registration form: GET/POST /api/profile."""

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
from app.services.validation import optional_trimmed, validate_profile_fields

router = APIRouter(prefix="/api", tags=["profile"])

_PROFILE_COLUMNS = (
    UserProfile.id,
    UserProfile.user_id,
    UserProfile.first_name,
    UserProfile.last_name,
    UserProfile.address,
    UserProfile.address2,
    UserProfile.state,
    UserProfile.zip,
    UserProfile.country,
    UserProfile.phone,
    UserProfile.communication_preference,
    UserProfile.linkedin,
    UserProfile.github,
    UserProfile.alt_email,
)


def _serialize(row) -> dict:
    return ProfileOut(
        id=row.id,
        userId=row.user_id,
        firstName=row.first_name,
        lastName=row.last_name,
        address=row.address,
        address2=row.address2,
        state=row.state,
        zip=row.zip,
        country=row.country,
        phone=row.phone,
        communicationPreference=row.communication_preference,
        linkedin=row.linkedin,
        github=row.github,
        altEmail=row.alt_email,
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
    # A missing profile is a 200 with null, not a 404 - the absence is the gate.
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

    # Blank country falls back to 'US'.
    country = body.country.strip() or "US"
    profile = UserProfile(
        user_id=user.id,
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        address=body.address.strip(),
        address2=optional_trimmed(body.address2),
        state=body.state.strip(),
        zip=body.zip.strip(),
        country=country,
        phone=body.phone.strip(),
        communication_preference=body.communication_preference,
        linkedin=optional_trimmed(body.linkedin),
        github=optional_trimmed(body.github),
        alt_email=optional_trimmed(body.alt_email),
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
        return internal_error("Save Profile Error", err, False)

    return respond(
        201,
        {
            "success": True,
            "message": "Profile saved!",
            "profile": _serialize(profile),
        },
    )
