"""The artist's public profile: the copy a portfolio page renders.

Kept separate from ``user_profiles`` (which is registration data - address, zip,
phone) because these fields are the *site's* words: the statement in the hero,
the About prose, the credit line. One row per artist.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArtistProfile(Base):
    __tablename__ = "artist_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The user allowed to edit this profile.
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # The public URL: /artist/<slug>. Derived from the display name when the
    # profile is created, then left alone so links survive a rename.
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    # The line under the name, e.g. "Artist".
    tagline: Mapped[str] = mapped_column(Text, nullable=False)
    # The one sentence the hero is built around.
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    # The long-form About section, below the one-line bio. Optional, and
    # paragraphs apart: blank-line-separated, since that's the one shape a
    # plain textarea can hold without a second table for a list of strings.
    about: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    location: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    instagram: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A ceiling on how dense this artist's sheets get. The grid works its own
    # column count out of the window; this is the artist's say in it - a
    # portrait reads differently at two across than a wetland does at six. Null
    # leaves the whole decision to the grid.
    grid_columns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Which theme this artist's own page wears: "dark", "light" or "paper".
    # Null means the page follows the site, which is what a visitor sees before
    # an artist picks one. Only their own page - the landing page and /gallery
    # show every artist's work, so there is no single answer for them to give.
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whose profile the front page shows. Exactly one row should carry this;
    # the first artist to save a profile gets it.
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
