"""Albums and the photos inside them.

An album is the unit of organization, of ownership, and of access:

- ``artist_id`` says whose portfolio it belongs to, which is what decides who
  may subscribe to it.
- ``access`` is the album's tier on the free/paid/premium ladder (see
  models/tiers.py). A subscription's level decides which tiers it opens.
- Unpublishing hides the album and everything in it at once.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.tiers import TIER_FREE


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # Whose work this is. Subscriptions are per artist, so this is what decides
    # whether a given customer may download the paid photos inside.
    artist_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # Shown when the work isn't the album owner's - e.g. a guest feature.
    credit: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    access: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{TIER_FREE}'"),
        default=TIER_FREE,
    )
    # The kill switch: an unpublished album is invisible and undownloadable, for
    # everyone below admin.
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    album_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("albums.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Paths relative to the media root (see services/storage.py).
    #
    # Three files per photo: the original is what a download hands over, and the
    # preview/thumb are what the grid and the viewer actually load, so a public
    # page never streams somebody's full-resolution file. Both derived files are
    # nullable so hand-seeded placeholders can have only the one.
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    preview_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumb_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Stored as displayed (EXIF rotation already baked in), so a grid can
    # reserve space before the image loads.
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
