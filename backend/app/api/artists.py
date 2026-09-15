"""The public roster: who is on the site, and one artist's page.

Separate from ``/api/artist/*`` (which is about *your own* profile, and needs a
session) because these are read by visitors with no account at all. Plural for
the roster, singular for yourself.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_optional_user
from app.api.media import published_albums_for_artist
from app.api.responses import ApiError, msg, respond
from app.db.session import get_db
from app.models import ArtistProfile
from app.schemas.artist import ArtistProfileOut, ArtistSummary

router = APIRouter(prefix="/api/artists", tags=["artists"])


def _profile(row) -> dict:
    return ArtistProfileOut(
        slug=row.slug,
        display_name=row.display_name,
        tagline=row.tagline,
        statement=row.statement,
        bio=row.bio,
        about=row.about,
        location=row.location,
        contact_email=row.contact_email,
        phone=row.phone,
        instagram=row.instagram,
        # Not grid_columns: the sheet sizes itself from the album payload, which
        # carries the ceiling per album. This is only the page's own look.
        theme=row.theme,
        updated_at=row.updated_at,
    ).model_dump(by_alias=True, mode="json")


@router.get("")
async def list_artists(db: AsyncSession = Depends(get_db)) -> object:
    """Everyone with a profile, the front page's artist first."""
    rows = (
        await db.execute(
            select(
                ArtistProfile.slug,
                ArtistProfile.display_name,
                ArtistProfile.tagline,
                ArtistProfile.location,
            ).order_by(ArtistProfile.is_primary.desc(), ArtistProfile.id)
        )
    ).all()

    return respond(
        200,
        {
            "artists": [
                ArtistSummary(
                    slug=row.slug,
                    display_name=row.display_name,
                    tagline=row.tagline,
                    location=row.location,
                ).model_dump(by_alias=True, mode="json")
                for row in rows
            ]
        },
    )


@router.get("/{slug}")
async def get_artist(
    slug: str,
    user: AuthUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> object:
    """One artist's words and work, for their page."""
    profile = (
        await db.execute(
            select(
                ArtistProfile.user_id,
                ArtistProfile.slug,
                ArtistProfile.display_name,
                ArtistProfile.tagline,
                ArtistProfile.statement,
                ArtistProfile.bio,
                ArtistProfile.about,
                ArtistProfile.location,
                ArtistProfile.contact_email,
                ArtistProfile.phone,
                ArtistProfile.instagram,
                ArtistProfile.theme,
                ArtistProfile.updated_at,
            ).where(ArtistProfile.slug == slug)
        )
    ).first()
    if profile is None:
        raise ApiError(404, msg("Artist not found"))

    albums = await published_albums_for_artist(db, profile.user_id, user)
    return respond(200, {"artist": _profile(profile), "albums": albums})
