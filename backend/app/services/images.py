"""Turning an uploaded file into the three files a photo needs.

An original, a preview, and a thumbnail. The original is what a download hands
over; the preview and thumb are what pages actually load, so a public gallery
never streams somebody's full-resolution work.

Two things here are not just resizing:

- **Orientation.** Phone cameras store rotation in EXIF rather than rotating the
  pixels, so a photo shot in portrait can be stored landscape. ``exif_transpose``
  bakes the rotation in, otherwise previews come out sideways.
- **Metadata.** EXIF routinely contains GPS coordinates and camera serial
  numbers. This is a portfolio site, so the derived files are rebuilt from pixel
  data and carry no metadata at all. The original keeps whatever it came with -
  it's the artist's own file, and it's only ever served as a download.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

# Long-edge caps. The preview is sized for a full-screen viewer on a large
# display; the thumb for a grid cell at roughly 3x.
PREVIEW_LONG_EDGE = 2000
THUMB_LONG_EDGE = 640

# WebP for both: markedly smaller than JPEG at the same visual quality, and
# supported everywhere that matters now.
PREVIEW_FORMAT = "WEBP"
PREVIEW_QUALITY = 82

# Refuse absurd uploads outright rather than letting Pillow try. This is a
# decompression-bomb guard as much as a size limit.
MAX_PIXELS = 80_000_000


class NotAnImage(ValueError):
    """The bytes aren't an image Pillow can read."""


@dataclass(frozen=True)
class Derived:
    """The encoded files, ready to be written by the caller.

    ``width``/``height`` describe the image as *displayed* - after any EXIF
    rotation is baked in - which is what a layout reserving space needs.
    """

    preview: bytes
    thumb: bytes
    width: int
    height: int


def _scaled(image: Image.Image, long_edge: int) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= long_edge:
        # Already small enough; don't upscale and invent detail.
        return image.copy()
    scale = long_edge / longest
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(size, Image.LANCZOS)


def _encode(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=PREVIEW_FORMAT, quality=PREVIEW_QUALITY, method=4)
    return buffer.getvalue()


def derive(data: bytes) -> Derived:
    """Preview + thumb + dimensions for one uploaded file.

    Raises NotAnImage if the bytes aren't a readable image.
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            if opened.width * opened.height > MAX_PIXELS:
                raise NotAnImage("Image is too large to process")

            # Bake in EXIF rotation, then drop all metadata.
            image = ImageOps.exif_transpose(opened)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            width, height = image.size
            preview = _encode(_scaled(image, PREVIEW_LONG_EDGE))
            thumb = _encode(_scaled(image, THUMB_LONG_EDGE))
    except (UnidentifiedImageError, OSError) as err:
        raise NotAnImage("That file isn't an image we can read") from err

    return Derived(preview=preview, thumb=thumb, width=width, height=height)
