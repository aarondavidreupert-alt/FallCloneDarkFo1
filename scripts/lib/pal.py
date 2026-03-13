"""
Fallout PAL palette reader — Python 3 port of darkfo/pal.py
Original: Copyright 2014-2015 darkf (Apache 2.0)

Reads Fallout 1/2 .PAL files (256 × RGB, values 0–63, scaled ×4 to 0–255).
Fallout 1 and 2 share identical .PAL format.
"""

import struct
from typing import List, Tuple


Palette = List[Tuple[int, int, int]]  # list of 256 (r, g, b) tuples


def read_pal(path: str) -> Palette:
    """Read a .PAL file and return 256 (r, g, b) tuples, each value 0–255."""
    palette: Palette = []
    with open(path, "rb") as f:
        for _ in range(256):
            # Python 3: indexing bytes gives ints directly (no ord() needed)
            r, g, b = f.read(1)[0], f.read(1)[0], f.read(1)[0]
            # Fallout palette values are 6-bit (0–63); scale to 8-bit
            if r <= 63 and g <= 63 and b <= 63:
                r, g, b = r * 4, g * 4, b * 4
            else:
                r = g = b = 0
            palette.append((r, g, b))
    return palette


def flatten_palette(palette: Palette) -> List[int]:
    """Flatten [(r,g,b), ...] to [r,g,b,r,g,b,...] for Pillow putpalette()."""
    return [c for rgb in palette for c in rgb]


def palette_to_dict(palette: Palette) -> List[List[int]]:
    """Convert palette to JSON-serialisable list of [r,g,b] lists."""
    return [list(rgb) for rgb in palette]
