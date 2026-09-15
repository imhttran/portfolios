"""Wire shapes for albums and photos."""

from __future__ import annotations

from app.schemas.base import CamelModel


class AlbumSummary(CamelModel):
    id: int
    slug: str
    title: str
    credit: str | None = None
    description: str | None = None
    # "free" | "paid" | "premium" - where this album sits on the ladder.
    access: str
    # Whose work it is. The name is absent if that artist has no profile yet.
    artist_name: str | None = None
    artist_slug: str | None = None
    # That artist's ceiling on how many photographs across this album's sheet
    # may get. Null means the grid decides on its own.
    artist_columns: int | None = None
    photo_count: int = 0
    # Computed per visitor, so the browser never has to re-implement the rule
    # and drift from the server.
    can_download: bool = False
    download_url: str


class PhotoOut(CamelModel):
    id: int
    title: str | None = None
    position: int
    width: int | None = None
    height: int | None = None
    # Same-origin /api paths. ``previewUrl`` needs no session (published albums
    # are public to view); ``downloadUrl`` needs a signed-in user, and for a paid
    # album a subscriber.
    preview_url: str
    download_url: str


class ManagedAlbum(CamelModel):
    """An album as its owner sees it, in /studio - unpublished ones included."""

    id: int
    slug: str
    title: str
    description: str | None = None
    credit: str | None = None
    access: str
    is_published: bool
    photo_count: int = 0


class AlbumInput(CamelModel):
    """Creating an album. Only the photo upload that follows needs multipart."""

    title: str = ""
    access: str = "free"
    description: str = ""
    credit: str = ""
    is_published: bool = False


class AlbumPatch(CamelModel):
    """Editing an album. Every field is optional: only what's sent changes."""

    title: str | None = None
    access: str | None = None
    description: str | None = None
    credit: str | None = None
    is_published: bool | None = None
