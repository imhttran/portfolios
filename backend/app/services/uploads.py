"""Adding photos to an album, from a browser upload or a folder on disk.

Both entry points land here so they can't drift: the same three files per photo,
in the same place, with the same rules about what counts as an image.

What a caller gets back is a per-file report rather than an all-or-nothing
result. Uploading twelve photos where one is a stray PDF should add eleven and
say so, not refuse the lot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Album, Photo
from app.services import storage
from app.services.images import NotAnImage, derive

# What Pillow can read. RAW and video are deliberately absent - see the README.
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}

# One upload may carry this many files at once. The browser is for a handful of
# new photos; importing a whole shoot is what `app.cli import-album` is for.
MAX_FILES_PER_UPLOAD = 20

# Per-file ceiling for a browser upload. Enforced at the HTTP boundary rather
# than inside add_photo: a 40 MB photo on the artist's own disk is theirs to
# import, but a 40 MB multipart body is worth refusing before it's decoded.
MAX_UPLOAD_BYTES = 30 * 1024 * 1024


@dataclass
class AddResult:
    """What happened to every file we were handed, by name."""

    added: int = 0
    skipped: int = 0
    rejected: list[tuple[str, str]] = field(default_factory=list)

    def reject(self, name: str, reason: str) -> None:
        self.rejected.append((name, reason))


def _title_from(name: str) -> str:
    """``_TED0113.jpg`` -> ``TED0113``. The file name is the only title we have.

    Takes the basename first, so a name like ``../../evil.jpg`` yields ``evil``
    rather than carrying the traversal into the stored title.
    """
    basename = Path(name).name
    return basename.rsplit(".", 1)[0].lstrip("_- ").strip() or basename


async def _used_stems(db: AsyncSession, album_id: int) -> set[str]:
    """File-name stems already in this album, sanitised the same way incoming
    names are.

    Stems, not full names: ``a.jpg`` and ``a.png`` would write the same
    ``a-preview.webp``, so a clash on the stem is the one that matters.

    The sanitising is load-bearing. A row written with an *unsanitised* stem (an
    earlier version of the importer stored names verbatim) would never match the
    sanitised name being added, so a re-import would silently duplicate every
    photo instead of skipping it.
    """
    names = (
        (await db.execute(select(Photo.filename).where(Photo.album_id == album_id)))
        .scalars()
        .all()
    )
    return {storage.safe_stem(Path(name).stem) for name in names}


async def _next_position(db: AsyncSession, album_id: int) -> int:
    current = await db.scalar(
        select(func.coalesce(func.max(Photo.position), 0)).where(
            Photo.album_id == album_id
        )
    )
    return int(current or 0) + 1


async def add_photo(
    db: AsyncSession,
    *,
    album: Album,
    artist_key: str,
    filename: str,
    data: bytes,
    skip_if_present: bool = False,
    max_bytes: int | None = None,
) -> Photo | None:
    """Write one photo's three files and stage its row.

    ``artist_key`` is the artist's folder name (see slugs.artist_media_key) -
    resolved once by the caller rather than per file.

    Returns None when ``skip_if_present`` and a photo of that name is already in
    the album (what makes re-running a folder import a no-op).

    ``max_bytes`` is for uploads, where the size of the request is worth bounding
    before anything is decoded. A folder import passes nothing: the files are
    already on the artist's own disk.

    Raises NotAnImage/ValueError for anything the caller should attribute to
    this file rather than to the request as a whole.
    """
    if max_bytes is not None and len(data) > max_bytes:
        raise ValueError(f"larger than {max_bytes // (1024 * 1024)} MB")

    suffix = Path(filename).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise NotAnImage(f"{suffix or 'no extension'} isn't an image format")

    stem = storage.safe_stem(Path(filename).stem)
    used = await _used_stems(db, album.id)
    if stem in used:
        if skip_if_present:
            return None
        # Two files can legitimately share a name across uploads; give the
        # second its own, rather than letting one overwrite the other.
        base, bump = stem, 1
        while stem in used:
            bump += 1
            stem = f"{base}-{bump}"

    # Decodes the file for real, so a renamed PDF is caught here rather than in
    # somebody's browser later. Also strips EXIF from the derived files.
    derived = derive(data)

    paths = storage.photo_paths(
        artist_key=artist_key, album_slug=album.slug, stem=stem, suffix=suffix
    )
    # The original is stored byte-for-byte: it's what a download hands over.
    storage.write_bytes(paths.original, data)
    storage.write_bytes(paths.preview, derived.preview)
    storage.write_bytes(paths.thumb, derived.thumb)

    photo = Photo(
        album_id=album.id,
        filename=paths.original,
        preview_filename=paths.preview,
        thumb_filename=paths.thumb,
        width=derived.width,
        height=derived.height,
        title=_title_from(filename),
        position=await _next_position(db, album.id),
    )
    db.add(photo)
    # Flushed so the next file in this same batch sees this row: without it,
    # positions repeat and a second file with the same name overwrites the first.
    await db.flush()
    return photo


async def add_folder(
    db: AsyncSession, *, album: Album, artist_key: str, folder: Path
) -> AddResult:
    """Every image in a folder, for the CLI importer. Skips what's already there."""
    result = AddResult()
    for path in sorted(p for p in folder.iterdir() if p.is_file()):
        try:
            photo = await add_photo(
                db,
                album=album,
                artist_key=artist_key,
                filename=path.name,
                data=path.read_bytes(),
                skip_if_present=True,
            )
        except NotAnImage as err:
            result.reject(path.name, str(err))
            continue
        except (OSError, ValueError) as err:
            result.reject(path.name, str(err))
            continue
        if photo is None:
            result.skipped += 1
        else:
            result.added += 1
    return result
