#!/usr/bin/env python3
"""Render the Faizy mark to PNG using only the standard library.

Why this exists: the module needs static/description/icon.png for the Odoo apps
tile and menu, and no rasteriser (ImageMagick, rsvg, Pillow) is guaranteed to be
present on a deploy box. This draws the same geometry as
faizy/packages/brand/assets/faizy-mark.svg with a scanline polygon fill and
writes the PNG by hand.

Regenerate after any change to the mark:

    python3 faizy/odoo/tools/make_icon.py

⚠️ The geometry mirrors the hand-built SVG, which is not a true vector trace of
the official artwork. When the source PNG is traced properly, update BOTH the SVG
and the POLYGONS below so the icon and the web mark stay identical.
"""

import struct
import zlib
from pathlib import Path

# Brand colours.
ORANGE = (246, 158, 34, 255)  # #F69E22
BLACK = (10, 10, 10, 255)  # #0A0A0A
TRANSPARENT = (0, 0, 0, 0)

# Source canvas of the mark, matching the SVG viewBox.
CANVAS = 1080.0
CIRCLE = (540.0, 540.0, 505.0)  # cx, cy, r

# Each entry is one path: a list of rings filled with the even-odd rule, so the
# second ring in each path punches its counter out of the first. Arcs from the
# SVG are approximated as corners — invisible at icon sizes.
POLYGONS = [
    [
        # Top arm: the angled wing.
        [(852, 345), (548, 345), (448, 452), (302, 452), (302, 500), (742, 500)],
        # Its long horizontal slot.
        [(796, 396), (566, 396), (512, 449), (745, 449)],
    ],
    [
        # Mid bar into the bowl, then the tapering blade to its point.
        [
            (320, 518),
            (700, 518),
            (634, 664),
            (494, 664),
            (408, 742),
            (332, 845),
            (430, 574),
            (320, 574),
        ],
        # The bowl counter.
        [(600, 582), (516, 582), (474, 646), (566, 646)],
    ],
]


def _crossings(x: float, y: float, ring: list[tuple[float, float]]) -> int:
    """How many times a ray cast from (x, y) crosses this ring's edges."""
    count = 0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            # X coordinate where the edge crosses the horizontal line at y.
            t = (y - y1) / (y2 - y1)
            if x < x1 + t * (x2 - x1):
                count += 1
    return count


def _inside_even_odd(x: float, y: float, rings: list[list[tuple[float, float]]]) -> bool:
    return sum(_crossings(x, y, ring) for ring in rings) % 2 == 1


def render(size: int, transparent_background: bool = False) -> bytes:
    """Rasterise the mark at `size` x `size` and return PNG bytes."""
    scale = CANVAS / size
    cx, cy, r = CIRCLE
    r_sq = r * r

    rows = []
    for py in range(size):
        # Sample at pixel centres — sampling at corners shifts the mark half a
        # pixel and makes small sizes look off-centre.
        sy = (py + 0.5) * scale
        row = bytearray([0])  # PNG filter byte: 0 = None
        for px in range(size):
            sx = (px + 0.5) * scale

            in_circle = (sx - cx) ** 2 + (sy - cy) ** 2 <= r_sq
            if not in_circle:
                row += bytes(TRANSPARENT if transparent_background else TRANSPARENT)
                continue

            glyph = any(_inside_even_odd(sx, sy, path) for path in POLYGONS)
            row += bytes(BLACK if glyph else ORANGE)
        rows.append(bytes(row))

    raw = b"".join(rows)
    return _png(size, size, raw)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _png(width: int, height: int, raw: bytes) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    targets = {
        root / "addons/faizy_core/static/description/icon.png": 256,
    }
    for path, size in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(render(size))
        print(f"wrote {path} ({size}x{size})")


if __name__ == "__main__":
    main()
