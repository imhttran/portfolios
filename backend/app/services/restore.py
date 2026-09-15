"""Rebuilding photo rows from the files on disk.

The mirror of ``prune-media``. Files are written before their row is committed,
and the media tree is self-describing:

    originals/artists/{artist_id}/{album_slug}/{stem}{ext}
    public/artists/{artist_id}/{album_slug}/{stem}-preview.webp
                                            {stem}-thumb.webp

so rows can be rebuilt from it. That matters because a database reset wipes the
rows but *not* the files: work that didn't come from the seeds - an imported
folder, a browser upload - reappears with one command instead of being redone.

What the filenames *can't* tell us is the tier, because the tier deliberately
lives in the database rather than the path. Callers pass it in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Album, Photo, User
from app.models.tiers import TIER_FREE, TIERS
from app.services import storage

# EXIF orientation values that mean "the stored pixels are rotated 90 degrees".
_ROTATED = {5, 6, 7, 8}


@dataclass
class RestoreReport:
    albums_created: int = 0
    photos_added: int = 0
    already_present: int = 0
    # Originals we couldn't read, or whose artist doesn't exist.
    skipped: list[str] = field(default_factory=list)

    @property
    def considered(self) -> int:
        return self.photos_added + self.already_present + len(self.skipped)


def _title_from_slug(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.replace("_", "-").split("-"))


def _display_size(path: Path) -> tuple[int, int] | None:
    """The photo's size as displayed, reading only the header.

    Swaps the axes when EXIF says the pixels are rotated, so a restored row
    matches what the image processor would have stored. Header-only, because a
    restore may be thousands of multi-megabyte files.
    """
    try:
        with Image.open(path) as image:
            width, height = image.size
            orientation = image.getexif().get(274, 1)
    except (OSError, ValueError):
        return None
    if orientation in _ROTATED:
        return height, width
    return width, height


async def _albums_under_originals(root: Path) -> list[tuple[Path, int, str]]:
    """Every album folder under originals/, as (directory, artist_id, slug).

    Returns the directory itself rather than rebuilding it from the artist id,
    because the folder is ``{id}`` or ``{id}-{slug}`` - reconstructing would miss
    the slug half and look in a directory that doesn't exist.
    """
    found: list[tuple[Path, int, str]] = []
    base = root / "originals" / "artists"
    if not base.is_dir():
        return found
    for artist_dir in sorted(base.iterdir()):
        if not artist_dir.is_dir():
            continue
        leading = artist_dir.name.split("-", 1)[0]
        if not leading.isdigit():
            continue
        for album_dir in sorted(artist_dir.iterdir()):
            if album_dir.is_dir():
                found.append((album_dir, int(leading), album_dir.name))
    return found


async def restore_from_media(
    db: AsyncSession,
    *,
    tiers: dict[str, str] | None = None,
    default_tier: str = TIER_FREE,
    published: bool = True,
    apply: bool = False,
) -> RestoreReport:
    """Rebuild the rows for every photo sitting in the media tree.

    Additive and idempotent: a photo already in its album is left alone, so this
    is safe to run on a database that only lost some of its rows.
    """
    tiers = tiers or {}
    if default_tier not in TIERS:
        raise ValueError(f"tier must be one of: {', '.join(TIERS)}")

    root = storage.media_root()
    report = RestoreReport()

    for directory, artist_id, slug in await _albums_under_originals(root):
        originals = sorted(p for p in directory.iterdir() if p.is_file())
        if not originals:
            continue

        artist = await db.get(User, artist_id)
        if artist is None:
            report.skipped.append(
                f"{directory.relative_to(root)} (no user {artist_id})"
            )
            continue

        album = (
            await db.execute(select(Album).where(Album.slug == slug))
        ).scalar_one_or_none()
        if album is None:
            album = Album(
                slug=slug,
                title=_title_from_slug(slug),
                artist_id=artist_id,
                access=tiers.get(slug, default_tier),
                is_published=published,
            )
            db.add(album)
            await db.flush()
            report.albums_created += 1

        known = set(
            (await db.execute(select(Photo.filename).where(Photo.album_id == album.id)))
            .scalars()
            .all()
        )
        position = int(
            await db.scalar(
                select(func.coalesce(func.max(Photo.position), 0)).where(
                    Photo.album_id == album.id
                )
            )
            or 0
        )

        for original in originals:
            relative = str(original.relative_to(root))
            if relative in known:
                report.already_present += 1
                continue

            relative_dir = original.parent.relative_to(root)

            size = _display_size(original)
            if size is None:
                report.skipped.append(relative)
                continue

            stem = original.stem
            # Derived from the original's own directory rather than rebuilt from
            # the current naming scheme: whatever layout the files are in, the
            # previews sit beside them, and a row must point at what's there.
            public_dir = Path("public") / relative_dir.relative_to("originals")
            preview = str(public_dir / f"{stem}-preview.webp")
            thumb = str(public_dir / f"{stem}-thumb.webp")
            has_preview = storage.photo_path(preview).is_file()
            has_thumb = storage.photo_path(thumb).is_file()

            position += 1
            db.add(
                Photo(
                    album_id=album.id,
                    filename=relative,
                    # Null when a hand-seeded placeholder has no derived files;
                    # the delivery endpoint falls back to the original.
                    preview_filename=preview if has_preview else None,
                    thumb_filename=thumb if has_thumb else None,
                    width=size[0],
                    height=size[1],
                    title=stem,
                    position=position,
                )
            )
            report.photos_added += 1

    if apply:
        await db.commit()
    else:
        await db.rollback()
    return report
