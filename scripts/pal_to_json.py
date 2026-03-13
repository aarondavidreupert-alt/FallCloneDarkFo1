#!/usr/bin/env python3
"""
pal_to_json.py — Convert Fallout .PAL palette to JSON.

Not in DarkFO (DarkFO uses the PAL in-process; we expose it as JSON so the
Phaser renderer and any future shader code can import it directly).

Output: public/assets/data/color.json
  {
    "palette": [[r, g, b], ...],   // 256 entries, values 0–255
    "transparent": 0               // palette index 0 = transparent
  }

Usage:
    python pal_to_json.py PAL_FILE [OUT_FILE]

    PAL_FILE   path to color.pal  (found in root of extracted Fallout data)
    OUT_FILE   output path (default: public/assets/data/color.json)
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from lib.pal import read_pal, palette_to_dict


def convert_pal(pal_path: str, out_path: str) -> None:
    palette = read_pal(pal_path)
    data = {
        "palette":     palette_to_dict(palette),
        "transparent": 0,   # index 0 = transparent in Fallout palette mode
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {out_path} ({len(palette)} palette entries)")


def main():
    ap = argparse.ArgumentParser(description="Convert Fallout PAL to JSON")
    ap.add_argument("pal_file", help="Path to color.pal")
    ap.add_argument("out_file", nargs="?",
                    default=os.path.join("public", "assets", "data", "color.json"),
                    help="Output JSON path")
    args = ap.parse_args()

    if not os.path.exists(args.pal_file):
        print(f"ERROR: {args.pal_file} not found", file=sys.stderr)
        sys.exit(1)

    convert_pal(args.pal_file, args.out_file)


if __name__ == "__main__":
    main()
