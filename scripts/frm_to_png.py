#!/usr/bin/env python3
"""
frm_to_png.py — Convert Fallout 1/2 FRM/FR[0-5] art to PNG sprite sheets.

Based on darkfo/exportImages.py + darkfo/frmpixels.py
Original: Copyright 2014-2015 darkf (Apache 2.0)

Python 3.9+ rewrite:
  - Built-in generics (list/dict/tuple) instead of typing module equivalents
  - ProcessPoolExecutor for parallel conversion
  - np.frombuffer() instead of np.array([ord(b) for b in ...])
  - time.perf_counter() instead of removed time.clock()

Output layout (mirrors DarkFO art/ directory):
  OUT_DIR/
    tiles/       *.png
    critters/    *.png
    items/       *.png
    scenery/     *.png
    walls/       *.png
    misc/        *.png
    intrface/    *.png
    inven/       *.png
    skilldex/    *.png
    backgrnd/    *.png
    imageMap.json   (art key → full frame metadata, consumed by DarkFO engine)

Usage:
    python frm_to_png.py DATA_DIR OUT_DIR [--jobs N] [--no-image-map] [--update]

    DATA_DIR   root of extracted Fallout data (must contain art/ and color.pal)
    OUT_DIR    output directory — typically public/assets/art/
"""

import sys
import os
import glob
import json
import time
import argparse
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))

from lib.pal import read_pal, flatten_palette
from lib.frm import export_frm, export_frms

# Subdirectories to convert — matches Harold's exportImages.py list plus backgrnd
SUBDIRS: tuple[str, ...] = (
    "critters", "skilldex", "inven", "tiles", "items",
    "scenery", "walls", "misc", "intrface", "backgrnd",
)


# ── Worker functions (module-level required for ProcessPoolExecutor) ──────────

def _worker_frm(task: tuple) -> tuple[str, dict | None]:
    art_key, frm_path, out_path, palette = task
    try:
        info = export_frm(frm_path, out_path, palette)
        return art_key, info
    except Exception:
        print(f"  ERROR {art_key}:\n{traceback.format_exc()}", file=sys.stderr)
        return art_key, None


def _worker_frx(task: tuple) -> tuple[str, dict | None]:
    art_key, frm_files, out_path, palette = task
    try:
        info = export_frms(frm_files, out_path, palette)
        return art_key, info
    except Exception:
        print(f"  ERROR {art_key}:\n{traceback.format_exc()}", file=sys.stderr)
        return art_key, None


# ── Task builders ─────────────────────────────────────────────────────────────

def _frm_tasks(
    palette: list[int], data_dir: str, out_dir: str
) -> list[tuple]:
    """Single-direction .frm files."""
    tasks = []
    for subdir in SUBDIRS:
        pattern = os.path.join(data_dir, "art", subdir, "*.frm")
        for frm_path in sorted(glob.glob(pattern)):
            stem     = os.path.splitext(os.path.basename(frm_path))[0].lower()
            art_key  = f"art/{subdir}/{stem}"
            out_path = os.path.join(out_dir, subdir, stem + ".png")
            tasks.append((art_key, frm_path, out_path, palette))
    return tasks


def _frx_tasks(
    palette: list[int], data_dir: str, out_dir: str
) -> list[tuple]:
    """Multi-directional .fr0–.fr5 sets (mostly critters)."""
    tasks = []
    for subdir in SUBDIRS:
        pattern = os.path.join(data_dir, "art", subdir, "*.fr0")
        for fr0 in sorted(glob.glob(pattern)):
            stem    = os.path.splitext(os.path.basename(fr0))[0].lower()
            base    = os.path.join(data_dir, "art", subdir, stem)
            files   = sorted(glob.glob(base + ".fr[0-5]"))
            if not files:
                continue
            art_key  = f"art/{subdir}/{stem}"
            out_path = os.path.join(out_dir, subdir, stem + ".png")
            tasks.append((art_key, files, out_path, palette))
    return tasks


# ── Main conversion ───────────────────────────────────────────────────────────

def convert_all(
    data_dir: str,
    out_dir: str,
    n_jobs: int = 4,
    write_image_map: bool = True,
    update: bool = False,
) -> dict[str, dict]:
    """
    Convert all FRM/FR[0-5] files under data_dir/art/ to PNG sprite sheets.

    Follows Harold's exportImages.py approach:
      - imageMap key format: "art/{subdir}/{lowercase_stem}"
      - imageMap.json written to out_dir/imageMap.json
      - Full frame metadata per entry: numFrames, fps, numDirections,
        totalFrames, directionOffsets, frameOffsets (with sx/ox/oy),
        frameWidth, frameHeight

    Returns the complete imageMap dict.
    """
    pal_path = os.path.join(data_dir, "color.pal")
    if not os.path.exists(pal_path):
        raise FileNotFoundError(f"Palette not found: {pal_path}")

    palette = flatten_palette(read_pal(pal_path))

    os.makedirs(out_dir, exist_ok=True)
    for subdir in SUBDIRS:
        os.makedirs(os.path.join(out_dir, subdir), exist_ok=True)

    image_map: dict[str, dict] = {}
    image_map_path = os.path.join(out_dir, "imageMap.json")

    if update and os.path.exists(image_map_path):
        with open(image_map_path, encoding="utf-8") as fh:
            image_map = json.load(fh)
        print(f"  Loaded {len(image_map)} existing entries for incremental update")

    t0 = time.perf_counter()

    # ── FR[0-5] multi-directional ─────────────────────────────────────────────
    frx = _frx_tasks(palette, data_dir, out_dir)
    if update:
        frx = [t for t in frx if t[0] not in image_map]
    if frx:
        print(f"\nConverting {len(frx)} FR[0-5] sets ({n_jobs} workers)...")
        done = 0
        with ProcessPoolExecutor(max_workers=n_jobs) as pool:
            futs = {pool.submit(_worker_frx, t): t for t in frx}
            for fut in as_completed(futs):
                art_key, info = fut.result()
                done += 1
                print(f"  [{done}/{len(frx)}] {art_key}")
                if info:
                    image_map[art_key] = info

    # ── Single-direction FRMs ─────────────────────────────────────────────────
    frm = _frm_tasks(palette, data_dir, out_dir)
    if update:
        frm = [t for t in frm if t[0] not in image_map]
    print(f"\nConverting {len(frm)} FRM files ({n_jobs} workers)...")
    done = 0
    with ProcessPoolExecutor(max_workers=n_jobs) as pool:
        futs = {pool.submit(_worker_frm, t): t for t in frm}
        for fut in as_completed(futs):
            art_key, info = fut.result()
            done += 1
            print(f"  [{done}/{len(frm)}] {art_key}")
            if info:
                image_map[art_key] = info

    elapsed = time.perf_counter() - t0
    print(f"\nConverted {len(image_map)} art files in {elapsed:.1f}s")

    if write_image_map:
        with open(image_map_path, "w", encoding="utf-8") as fh:
            json.dump(image_map, fh)
        print(f"Wrote {image_map_path}")

    return image_map


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Convert Fallout FRM art to PNG sprite sheets (Harold approach)"
    )
    ap.add_argument("data_dir", help="Root of extracted Fallout data (contains art/, color.pal)")
    ap.add_argument("out_dir",  help="Output directory for PNGs (e.g. public/assets/art/)")
    ap.add_argument("--jobs",         type=int, default=4, metavar="N",
                    help="Parallel workers (default: 4)")
    ap.add_argument("--no-image-map", action="store_true",
                    help="Skip writing imageMap.json")
    ap.add_argument("--update",       action="store_true",
                    help="Merge with existing imageMap.json, skip already-converted files")
    args = ap.parse_args()

    try:
        convert_all(
            data_dir        = args.data_dir,
            out_dir         = args.out_dir,
            n_jobs          = args.jobs,
            write_image_map = not args.no_image_map,
            update          = args.update,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
