"""Placeholder images for the sample gallery.

Real photographs fill most of the demo; these stand in for the one artist whose
work is synthetic. Same image library as the upload pipeline, so a placeholder
is an ordinary PNG like any other file the site handles.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw


def gradient_png(width: int, height: int, top: int, bottom: int) -> bytes:
    """A vertical grayscale gradient: 8-bit, one tone per row."""
    image = Image.new("L", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(height - 1, 1)
        value = max(0, min(255, round(top + (bottom - top) * t)))
        draw.line([(0, y), (width - 1, y)], fill=value)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
