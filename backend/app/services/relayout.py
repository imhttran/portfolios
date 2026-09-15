"""Moving existing photos into the current media layout.

The layout changed once, from ``artists/{id}/{album}/`` (and, for the seeded
placeholders, no artist folder at all) to
``artists/{id}-{slug}/{album}/``. Rows and files therefore have to be moved
together: a row pointing at a path where the file no longer is serves nothing.

The new path is always derivable from the old one - the file's stem and suffix
plus the album's owner - so this needs no knowledge of which scheme a file is
currently in, and re-running it is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Album, ArtistProfile, Photo
from app.services import storage


@dataclass
class RelayoutReport:
    rows_seen: int = 0
    rows_to_move: int = 0
    files_to_move: int = 0
    already_current: int = 0
    # Rows whose files aren't where the row says - reported, never guessed at.
    missing: list[str] = field(default_factory=list)

    @property
    def in_place(self) -> int:
        return self.rows_seen - self.rows_to_move


async def _current_paths(
    db: AsyncSession,
    *,
    filename: str,
    album_slug: str,
    artist_id: int,
) -> storage.PhotoPaths:
    """Where this photo's three files belong under the current layout."""
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    slug = await db.scalar(
        select(ArtistProfile.slug).where(ArtistProfile.user_id == artist_id)
    )
    key = f"{artist_id}-{slug}" if slug else str(artist_id)
    return storage.photo_paths(
        artist_key=key, album_slug=album_slug, stem=stem, suffix=suffix
    )


async def relayout_media(db: AsyncSession, *, apply: bool = False) -> RelayoutReport:
    """Move every photo's files, and its row, into the current layout."""
    report = RelayoutReport()

    rows = (
        await db.execute(
            select(
                Photo.id,
                Photo.filename,
                Photo.preview_filename,
                Photo.thumb_filename,
                Album.slug,
                Album.artist_id,
            )
            .join(Album, Album.id == Photo.album_id)
            .order_by(Photo.id)
        )
    ).all()

    for row in rows:
        report.rows_seen += 1
        wanted = await _current_paths(
            db,
            filename=row.filename,
            album_slug=row.slug,
            artist_id=row.artist_id,
        )

        current = {
            "filename": row.filename,
            "preview_filename": row.preview_filename,
            "thumb_filename": row.thumb_filename,
        }
        target = {
            "filename": wanted.original,
            "preview_filename": wanted.preview,
            "thumb_filename": wanted.thumb,
        }

        moves = [
            (old, target[column])
            for column, old in current.items()
            if old and old != target[column]
        ]
        if not moves:
            report.already_current += 1
            continue

        if not storage.photo_path(row.filename).is_file():
            report.missing.append(row.filename)
            continue

        report.rows_to_move += 1
        report.files_to_move += len(moves)

        if not apply:
            continue

        for old, new in moves:
            storage.move_file(old, new)

        await db.execute(
            Photo.__table__.update()
            .where(Photo.id == row.id)
            .values(
                filename=target["filename"],
                preview_filename=(
                    target["preview_filename"] if row.preview_filename else None
                ),
                thumb_filename=(
                    target["thumb_filename"] if row.thumb_filename else None
                ),
            )
        )

    if apply:
        await db.commit()
        storage.prune_empty_dirs()
    else:
        await db.rollback()

    return report
