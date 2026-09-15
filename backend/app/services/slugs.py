"""URL slugs, and the folder names derived from them.

Derived from the display name once, when the profile is first created, and then
left alone: the slug is a public URL, so renaming yourself shouldn't break every
link to your page.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Album, ArtistProfile

_FALLBACK = "artist"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or _FALLBACK


async def unique_artist_slug(
    db: AsyncSession, display_name: str, user_id: int | None = None
) -> str:
    """A slug not already taken, suffixed -2, -3 … if it is.

    ``user_id`` is the profile being saved, so re-saving your own row is allowed
    to keep its own slug rather than counting itself as a collision.
    """
    base = slugify(display_name)
    candidate = base
    suffix = 1
    while True:
        taken_by = await db.scalar(
            select(ArtistProfile.user_id).where(ArtistProfile.slug == candidate)
        )
        if taken_by is None or taken_by == user_id:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


async def unique_album_slug(db: AsyncSession, title: str) -> str:
    """A slug no album is using, suffixed -2, -3 … if it is."""
    base = slugify(title)
    candidate = base
    suffix = 1
    while True:
        taken = await db.scalar(select(Album.id).where(Album.slug == candidate))
        if taken is None:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


async def artist_media_key(db: AsyncSession, artist_id: int) -> str:
    """An artist's folder name under ``originals/artists/`` and ``public/``.

    ``4-ted-nguy`` rather than ``4``, so browsing the media folder says whose work
    it is - and rather than a bare slug, so it still works for an album owned by
    someone with no artist profile, and stays put if that profile is deleted.
    """
    slug = await db.scalar(
        select(ArtistProfile.slug).where(ArtistProfile.user_id == artist_id)
    )
    return f"{artist_id}-{slug}" if slug else str(artist_id)
