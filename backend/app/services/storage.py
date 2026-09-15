"""Where photo files actually live.

The sample keeps them on local disk, and this module is the only place that
knows it - so moving to S3/R2 later is a change here and nowhere else.

It also owns the *layout*, so the folder importer and the browser upload path
can't drift apart about where a photo's three files belong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings


def media_root() -> Path:
    root = Path(get_settings().media_root)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def photo_path(filename: str) -> Path:
    """Resolve a stored filename inside the media root.

    Stored names are built by this module and never taken from a request, but
    re-checking containment here is what keeps a crafted name from turning into
    a path traversal.
    """
    root = media_root()
    path = (root / filename).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"filename escapes the media root: {filename!r}")
    return path


def write_bytes(filename: str, data: bytes) -> None:
    path = photo_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def delete_file(filename: str | None) -> None:
    """Remove a stored file if it's there. Missing is not an error."""
    if not filename:
        return
    try:
        path = photo_path(filename)
    except ValueError:
        return
    path.unlink(missing_ok=True)


def move_file(old: str, new: str) -> bool:
    """Move a stored file within the media root. True if it actually moved.

    False when there's nothing at ``old`` or something is already at ``new``, so
    a half-finished move is never clobbered.
    """
    try:
        source = photo_path(old)
        target = photo_path(new)
    except ValueError:
        return False
    if not source.is_file() or target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    source.replace(target)
    return True


def prune_empty_dirs() -> None:
    """Remove directories left empty inside the media root."""
    root = media_root()
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


_SAFE = re.compile(r"[^a-z0-9]+")


def safe_stem(name: str) -> str:
    """A file-name stem that is safe to put in a path.

    Client-supplied names are used for nothing but this: everything outside
    ``[a-z0-9]`` collapses to a dash, so ``../../etc/passwd`` can't survive as
    a path segment.
    """
    stem = _SAFE.sub("-", name.lower()).strip("-")
    return stem[:80] or "photo"


@dataclass(frozen=True)
class PhotoPaths:
    """The three files a photo is made of, relative to the media root."""

    original: str
    preview: str
    thumb: str


def photo_paths(
    *, artist_key: str, album_slug: str, stem: str, suffix: str
) -> PhotoPaths:
    """Where a photo's files live.

    ``artist_key`` is an artist's folder name - the user id, plus their slug when
    they have a profile (``4-ted-nguy``). The id keeps it working for an album
    owned by someone with no profile, and the slug makes the tree readable. One
    scheme for every photo, placeholders included, so a folder listing says who
    shot what.

    Originals are never public; previews are.
    """
    folder = f"artists/{safe_stem(artist_key)}"
    safe = safe_stem(stem)
    original_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return PhotoPaths(
        original=f"originals/{folder}/{safe_stem(album_slug)}/{safe}{original_suffix.lower()}",
        preview=f"public/{folder}/{safe_stem(album_slug)}/{safe}-preview.webp",
        thumb=f"public/{folder}/{safe_stem(album_slug)}/{safe}-thumb.webp",
    )
