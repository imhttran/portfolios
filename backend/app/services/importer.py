"""Importing a folder of existing photos into an artist's album.

The bridge between "I have a folder of photos" and the site's storage layout.
It reads the folder **in place** - the source is never moved or modified - and
hands each file to services/uploads.py, which writes what the site actually
serves:

    originals/artists/{id}/{album}/{name}.jpg         what a download hands over
    public/artists/{id}/{album}/{name}-preview.webp   what a page loads
    public/artists/{id}/{album}/{name}-thumb.webp

Why not just point the media root at the folder: the gallery needs a row per
photo (to know the dimensions, a title, and which files belong together), and
the derived files are not optional - a public page serving 6 MB originals
instead of previews would be unusable.

Idempotent: a file already imported into the album is skipped, so re-running
after adding more photos picks up only the new ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Album, User
from app.services.slugs import artist_media_key
from app.services.uploads import add_folder


@dataclass
class ImportReport:
    album_slug: str
    artist_email: str
    imported: int = 0
    skipped_existing: int = 0
    # (file name, why) for everything that couldn't be read.
    rejected: list[tuple[str, str]] = field(default_factory=list)

    @property
    def considered(self) -> int:
        return self.imported + self.skipped_existing + len(self.rejected)


async def import_folder(
    db: AsyncSession,
    *,
    artist_email: str,
    folder: Path,
    slug: str,
    title: str,
    access: str,
    published: bool = True,
) -> ImportReport:
    """Load every image in ``folder`` into the album ``slug``, owned by the artist."""
    artist_id = await db.scalar(
        select(User.id).where(
            User.email == artist_email, User.role.in_(("artist", "admin"))
        )
    )
    if artist_id is None:
        raise ValueError(f"No artist with email {artist_email}")
    if not folder.is_dir():
        raise ValueError(f"Not a folder: {folder}")

    album = (
        await db.execute(select(Album).where(Album.slug == slug))
    ).scalar_one_or_none()
    if album is None:
        album = Album(
            slug=slug,
            title=title,
            artist_id=artist_id,
            access=access,
            is_published=published,
        )
        db.add(album)
        await db.flush()

    result = await add_folder(
        db,
        album=album,
        artist_key=await artist_media_key(db, artist_id),
        folder=folder,
    )
    await db.commit()

    return ImportReport(
        album_slug=slug,
        artist_email=artist_email,
        imported=result.added,
        skipped_existing=result.skipped,
        rejected=result.rejected,
    )
