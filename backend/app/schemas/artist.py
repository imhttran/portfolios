"""Wire shapes for the artist's public profile."""

from __future__ import annotations

from datetime import datetime

from app.schemas.base import CamelModel


class ArtistSummary(CamelModel):
    """One row of the public roster."""

    slug: str
    display_name: str
    tagline: str
    location: str


class ArtistProfileInput(CamelModel):
    display_name: str = ""
    tagline: str = ""
    statement: str = ""
    bio: str = ""
    about: str = ""
    location: str = ""
    contact_email: str = ""
    phone: str = ""
    instagram: str = ""
    # Optional. An integer 2-8, or omitted to let the grid decide. Validated in
    # the route rather than here so the message reads like the others.
    grid_columns: int | None = None
    # Optional, and one of "dark", "light", "paper". Blank means the artist has
    # no theme of their own. Validated in the route for the same reason.
    theme: str = ""


class ArtistProfileOut(CamelModel):
    slug: str
    display_name: str
    tagline: str
    statement: str
    bio: str
    about: str
    location: str
    contact_email: str
    phone: str | None = None
    instagram: str | None = None
    grid_columns: int | None = None
    theme: str | None = None
    updated_at: datetime
