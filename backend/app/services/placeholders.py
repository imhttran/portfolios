"""Placeholder images for the sample gallery, with no image library involved.

Pillow isn't a dependency yet - the real upload pipeline that needs it is
separate work - so these are written by hand. A grayscale PNG is a signature,
three chunks, and one zlib stream, which is cheaper than adding a dependency to
show a grid of tiles that get deleted the moment real photos exist.
"""

from __future__ import annotations

import binascii
import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    )


def gradient_png(width: int, height: int, top: int, bottom: int) -> bytes:
    """A vertical grayscale gradient: 8-bit, colour type 0, filter 0 per row."""
    # Each row is uniform, so it's built in one go rather than per pixel.
    scanlines = bytearray()
    for y in range(height):
        t = y / max(height - 1, 1)
        value = max(0, min(255, round(top + (bottom - top) * t)))
        scanlines.append(0)  # filter type: none
        scanlines += bytes([value]) * width

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(scanlines)))
        + _chunk(b"IEND", b"")
    )
