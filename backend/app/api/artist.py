"""The artist's public profile.

GET is public: it is the copy the portfolio pages render, so it has to be
readable before anyone signs in. PUT is gated to ``artist`` and above, and only
ever writes the caller's own row - there is no way to edit someone else's
profile.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, ensure_role, get_current_user
from app.api.responses import internal_error, msg, respond
from app.db.session import get_db
from app.models import ArtistProfile
from app.schemas.artist import ArtistProfileInput, ArtistProfileOut
from app.services.slugs import unique_artist_slug
from app.services.validation import optional_trimmed, validate_email

router = APIRouter(prefix="/api/artist", tags=["artist"])

_PROFILE_COLUMNS = (
    ArtistProfile.user_id,
    ArtistProfile.slug,
    ArtistProfile.display_name,
    ArtistProfile.tagline,
    ArtistProfile.statement,
    ArtistProfile.bio,
    ArtistProfile.location,
    ArtistProfile.contact_email,
    ArtistProfile.phone,
    ArtistProfile.instagram,
    ArtistProfile.grid_columns,
    ArtistProfile.is_primary,
    ArtistProfile.updated_at,
)


def _serialize(row) -> dict:
    return ArtistProfileOut(
        slug=row.slug,
        display_name=row.display_name,
        tagline=row.tagline,
        statement=row.statement,
        bio=row.bio,
        location=row.location,
        contact_email=row.contact_email,
        phone=row.phone,
        instagram=row.instagram,
        grid_columns=row.grid_columns,
        updated_at=row.updated_at,
    ).model_dump(by_alias=True, mode="json")


def _validate(body: ArtistProfileInput) -> str | None:
    """First unmet rule as a message, or None. Mirrors validate_profile_fields."""
    required = (
        ("displayName", body.display_name),
        ("tagline", body.tagline),
        ("statement", body.statement),
        ("bio", body.bio),
        ("location", body.location),
        ("contactEmail", body.contact_email),
    )
    missing = [name for name, value in required if not value.strip()]
    if missing:
        return f"Missing required field(s): {', '.join(missing)}"
    if not validate_email(body.contact_email.strip()):
        return "Contact email is invalid"
    # Two is the fewest columns a sheet can show and still read as a contact
    # sheet - the grid itself never goes below two for more than one photograph.
    # Past eight the frames are too small to be worth the ceiling.
    if body.grid_columns is not None and not 2 <= body.grid_columns <= 8:
        return "gridColumns must be between 2 and 8, or omitted"
    return None


@router.get("/profile")
async def get_public_profile(db: AsyncSession = Depends(get_db)) -> object:
    """The profile the portfolio front page renders. Null until one is saved.

    Prefers the artist flagged ``is_primary``; otherwise the oldest profile, so
    a site with one artist behaves the obvious way.
    """
    stmt = select(*_PROFILE_COLUMNS).order_by(
        ArtistProfile.is_primary.desc(), ArtistProfile.id
    )
    row = (await db.execute(stmt)).first()
    return respond(200, {"profile": _serialize(row) if row else None})


@router.get("/profile/mine")
async def get_my_profile(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """The caller's own row - what the editor form loads."""
    ensure_role(user, "artist")

    row = (
        await db.execute(
            select(*_PROFILE_COLUMNS).where(ArtistProfile.user_id == user.id)
        )
    ).first()
    return respond(200, {"profile": _serialize(row) if row else None})


@router.put("/profile")
async def save_my_profile(
    body: ArtistProfileInput,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    ensure_role(user, "artist")

    validation_error = _validate(body)
    if validation_error:
        return respond(400, msg(validation_error))

    try:
        profile = (
            await db.execute(
                select(ArtistProfile).where(ArtistProfile.user_id == user.id)
            )
        ).scalar_one_or_none()

        if profile is None:
            # The first artist to save a profile becomes the front page's.
            any_profile = await db.scalar(select(ArtistProfile.id).limit(1))
            profile = ArtistProfile(
                user_id=user.id,
                is_primary=any_profile is None,
                slug=await unique_artist_slug(db, body.display_name),
            )
            db.add(profile)

        profile.display_name = body.display_name.strip()
        profile.tagline = body.tagline.strip()
        profile.statement = body.statement.strip()
        profile.bio = body.bio.strip()
        profile.location = body.location.strip()
        profile.contact_email = body.contact_email.strip()
        profile.phone = optional_trimmed(body.phone)
        profile.instagram = optional_trimmed(body.instagram)
        profile.grid_columns = body.grid_columns

        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError as err:
        await db.rollback()
        return internal_error("Save Artist Profile Error", err)

    return respond(
        200,
        {"message": "Profile saved!", "profile": _serialize(profile)},
    )
