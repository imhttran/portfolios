"""Unit tests for the image pipeline. No database needed."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.images import (
    PREVIEW_LONG_EDGE,
    THUMB_LONG_EDGE,
    NotAnImage,
    derive,
)


def _jpeg(width: int, height: int, *, exif_orientation: int | None = None) -> bytes:
    image = Image.new("RGB", (width, height), (120, 90, 60))
    buffer = io.BytesIO()
    if exif_orientation is not None:
        exif = image.getexif()
        exif[274] = exif_orientation  # 274 = Orientation
        image.save(buffer, format="JPEG", exif=exif)
    else:
        image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_landscape_is_scaled_to_the_caps():
    result = derive(_jpeg(4000, 3000))

    # Dimensions report the original, not the preview.
    assert (result.width, result.height) == (4000, 3000)

    with Image.open(io.BytesIO(result.preview)) as preview:
        assert max(preview.size) == PREVIEW_LONG_EDGE
        assert preview.format == "WEBP"
        # Aspect ratio preserved.
        assert round(preview.width / preview.height, 3) == round(4000 / 3000, 3)

    with Image.open(io.BytesIO(result.thumb)) as thumb:
        assert max(thumb.size) == THUMB_LONG_EDGE


def test_portrait_is_capped_on_its_long_edge():
    result = derive(_jpeg(1200, 3000))

    with Image.open(io.BytesIO(result.preview)) as preview:
        assert preview.height == PREVIEW_LONG_EDGE
        assert preview.width < preview.height


def test_small_images_are_not_upscaled():
    result = derive(_jpeg(300, 200))

    with Image.open(io.BytesIO(result.preview)) as preview:
        assert preview.size == (300, 200)
    with Image.open(io.BytesIO(result.thumb)) as thumb:
        assert thumb.size == (300, 200)


def test_exif_rotation_is_baked_in():
    """Orientation 6 means "rotate 90 clockwise" - the pixels must follow.

    The reported dimensions are post-rotation, i.e. as displayed, because that
    is what a layout reserving space for the image actually needs.
    """
    result = derive(_jpeg(4000, 3000, exif_orientation=6))

    assert (result.width, result.height) == (3000, 4000)
    with Image.open(io.BytesIO(result.preview)) as preview:
        assert preview.width < preview.height
        assert (preview.width, preview.height) == (1500, 2000)


def test_derived_files_carry_no_metadata():
    """EXIF can hold GPS coordinates; the public files must not."""
    result = derive(_jpeg(2000, 1500, exif_orientation=1))

    with Image.open(io.BytesIO(result.preview)) as preview:
        assert not preview.getexif()
    with Image.open(io.BytesIO(result.thumb)) as thumb:
        assert not thumb.getexif()


def test_transparent_png_is_flattened_to_rgb():
    image = Image.new("RGBA", (800, 600), (255, 0, 0, 128))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    result = derive(buffer.getvalue())
    with Image.open(io.BytesIO(result.preview)) as preview:
        assert preview.mode == "RGB"


@pytest.mark.parametrize("payload", [b"not an image at all", b"", b"\x00\x01\x02\x03"])
def test_non_images_are_rejected(payload):
    with pytest.raises(NotAnImage):
        derive(payload)
