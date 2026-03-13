#!/usr/bin/env python3
"""
frm_to_png.py — Convert Fallout 1/2 FRM/FR[0-5] art to PNG sprite sheets.

Adapted from darkfo/exportImages.py and darkfo/exportImagesPar.py
Original: Copyright 2014-2015 darkf (Apache 2.0)

Python 3 adaptation:
  - Multiprocessing pool via concurrent.futures (more robust than multiprocessing.Pool on Python 3)
  - numpy/Pillow API unchanged — only bytes handling fixed in lib/frm.py
  - time.perf_counter() replaces removed time.clock()

Output structure (mirroring DarkFO's art/ layout):
  OUT_DIR/
    tiles/        *.png
    critters/     *.png
    items/        *.png
    scenery/      *.png
    walls/        *.png
    misc/         *.png
    intrface/     *.png
    inven/        *.png
    skilldex/     *.png
    backgrnd/     *.png
    imageMap.json   (art key → frame metadata, consumed by Phaser IsoRenderer)

Usage:
    python frm_to_png.py DATA_DIR OUT_DIR [--jobs N] [--no-image-map] [--update]

    DATA_DIR   root of extracted Fallout data (contains art/, color.pal, ...)
    OUT_DIR    destination — typically public/assets/art/
"""

import sys
import os
import glob
import json
import time
import argparse
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Optional, Tuple

# Ensure lib/ is importable when script is run directly
sys.path.insert(0, os.path.dirname(__file__))

from lib.pal import read_pal, flatten_palette
from lib.frm import export_frm, export_frms

# Art subdirectories to convert — same list as DarkFO exportImages.py
SUBDIRS = (
    "tiles", "critters", "items", "scenery",
    "walls", "misc", "intrface", "inven", "skilldex", "backgrnd",
)


# ── Worker functions (must be module-level for multiprocessing) ───────────────

def _worker_frm(task: Tuple) -> Tuple[str, Optional[Dict]]:
    art_key, frm_path, out_path, palette = task
    try:
        info = export_frm(frm_path, out_path, palette)
        return (art_key, info)
    except Exception as e:
        print(f"  ERROR: {art_key}: {e}", file=sys.stderr)
        return (art_key, None)


def _worker_frx(task: Tuple) -> Tuple[str, Optional[Dict]]:
    art_key, frm_files, out_path, palette = task
    try:
        info = export_frms(frm_files, out_path, palette)
        return (art_key, info)
    except Exception as e:
        print(f"  ERROR: {art_key}: {e}", file=sys.stderr)
        return (art_key, None)


# ── Task builders ─────────────────────────────────────────────────────────────

def _frm_tasks(palette, data_dir, out_dir):
    for subdir in SUBDIRS:
        pattern = os.path.join(data_dir, "art", subdir, "*.frm")
        for frm_path in sorted(glob.glob(pattern, recursive=False)):
            stem    = os.path.splitext(os.path.basename(frm_path))[0].lower()
            art_key = f"art/{subdir}/{stem}"
            out_path = os.path.join(out_dir, subdir, stem + ".png")
            yield (art_key, frm_path, out_path, palette)


def _frx_tasks(palette, data_dir, out_dir):
    """Multi-directional FR0–FR5 sets (critters mostly)."""
    for subdir in SUBDIRS:
        pattern = os.path.join(data_dir, "art", subdir, "*.fr0")
        for fr0 in sorted(glob.glob(pattern, recursive=False)):
            stem     = os.path.splitext(os.path.basename(fr0))[0].lower()
            base     = os.path.join(data_dir, "art", subdir, stem)
            files    = sorted(glob.glob(base + ".fr[0-5]"))
            if not files:
                continue
            art_key  = f"art/{subdir}/{stem}"
            out_path = os.path.join(out_dir, subdir, stem + ".png")
            yield (art_key, files, out_path, palette)


# ── Main conversion ───────────────────────────────────────────────────────────

def convert_all(data_dir: str, out_dir: str,
                n_jobs: int = 4,
                write_image_map: bool = True,
                update: bool = False) -> Dict[str, Dict]:
    """
    Convert all FRM/FR[0-5] files found under data_dir/art/ to PNGs in out_dir.

    Returns the full imageMap dict {art_key: frame_info}.
    """
    pal_path = os.path.join(data_dir, "color.pal")
    if not os.path.exists(pal_path):
        raise FileNotFoundError(f"Palette not found: {pal_path}")

    palette = read_pal(pal_path)

    # Create output subdirectories
    os.makedirs(out_dir, exist_ok=True)
    for subdir in SUBDIRS:
        os.makedirs(os.path.join(out_dir, subdir), exist_ok=True)

    image_map: Dict[str, Dict] = {}

    # Load existing imageMap when doing an incremental update
    image_map_path = os.path.join(out_dir, "imageMap.json")
    if update and os.path.exists(image_map_path):
        with open(image_map_path, encoding="utf-8") as f:
            image_map = json.load(f)

    t0 = time.perf_counter()

    # ── FR[0-5] multi-directional ──
    frx_tasks = list(_frx_tasks(palette, data_dir, out_dir))
    if frx_tasks:
        print(f"\nConverting {len(frx_tasks)} FR[0-5] sets (using {n_jobs} workers)...")
        done = 0
        with ProcessPoolExecutor(max_workers=n_jobs) as pool:
            futs = {pool.submit(_worker_frx, t): t for t in frx_tasks
                    if not (update and t[0] in image_map)}
            for fut in as_completed(futs):
                art_key, info = fut.result()
                done += 1
                print(f"  [{done}/{len(futs)}] {art_key}")
                if info:
                    image_map[art_key] = info

    # ── Single-direction FRMs ──
    frm_tasks = list(_frm_tasks(palette, data_dir, out_dir))
    print(f"\nConverting {len(frm_tasks)} FRM files (using {n_jobs} workers)...")
    done = 0
    with ProcessPoolExecutor(max_workers=n_jobs) as pool:
        futs = {pool.submit(_worker_frm, t): t for t in frm_tasks
                if not (update and t[0] in image_map)}
        for fut in as_completed(futs):
            art_key, info = fut.result()
            done += 1
            print(f"  [{done}/{len(futs)}] {art_key}")
            if info:
                image_map[art_key] = info

    elapsed = time.perf_counter() - t0
    print(f"\nConverted {len(image_map)} art files in {elapsed:.1f}s")

    if write_image_map:
        with open(image_map_path, "w", encoding="utf-8") as f:
            json.dump(image_map, f)
        print(f"Wrote {image_map_path}")

    return image_map


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Convert Fallout FRM art to PNG sprite sheets")
    ap.add_argument("data_dir", help="Root of extracted Fallout data (contains art/, color.pal)")
    ap.add_argument("out_dir",  help="Output dir for PNGs (e.g. public/assets/art/)")
    ap.add_argument("--jobs",   type=int, default=4, metavar="N",
                    help="Parallel workers (default: 4)")
    ap.add_argument("--no-image-map", action="store_true",
                    help="Skip writing imageMap.json")
    ap.add_argument("--update", action="store_true",
                    help="Skip files that already exist in imageMap.json")
    args = ap.parse_args()

    try:
        convert_all(
            data_dir       = args.data_dir,
            out_dir        = args.out_dir,
            n_jobs         = args.jobs,
            write_image_map = not args.no_image_map,
            update         = args.update,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
