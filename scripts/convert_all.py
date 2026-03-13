#!/usr/bin/env python3
"""
convert_all.py — Master asset pipeline for FallClone.

Runs the full Phase 2 asset conversion in the correct order:

  1. extract_dat   — MASTER.DAT + CRITTER.DAT → fallout/data/  (if needed)
  2. pal_to_json   — color.pal → public/assets/data/color.json
  3. frm_to_png    — art/**/*.frm → public/assets/art/**/*.png  + imageMap.json
  4. map_to_json   — maps/*.map  → public/assets/maps/*.json
  5. acm_to_mp3    — sound/**/*.acm → public/assets/sound/**/*.mp3

Usage:
    python convert_all.py FALLOUT_DIR [options]

    FALLOUT_DIR   Path to your Fallout 1 installation
                  (the directory that contains MASTER.DAT and CRITTER.DAT,
                   OR an already-extracted "data/" subdirectory)

Options:
    --data-dir DIR    Where to put / find extracted raw data  [FALLOUT_DIR/data]
    --out-dir DIR     Root of web output                      [public/assets]
    --jobs N          Parallel workers for image/map/audio     [4]
    --skip-extract    Skip DAT extraction (data/ already exists)
    --skip-images     Skip FRM → PNG conversion
    --skip-maps       Skip MAP → JSON conversion
    --skip-audio      Skip ACM → MP3 conversion
    --update          Skip already-converted art files (incremental)
    --fo2             Input is Fallout 2 (DAT2 format)

Examples:
    # Full pipeline, Fallout 1 from GOG
    python convert_all.py "C:/GOG Games/Fallout"

    # Already extracted, re-convert everything
    python convert_all.py /games/fallout --skip-extract

    # Quick incremental update (only new/changed art)
    python convert_all.py /games/fallout --skip-extract --skip-maps --skip-audio --update
"""

import sys
import os
import argparse
import time

sys.path.insert(0, os.path.dirname(__file__))


def _step(label: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")


def main():
    ap = argparse.ArgumentParser(
        description="FallClone full asset conversion pipeline"
    )
    ap.add_argument("fallout_dir",
                    help="Fallout 1 installation directory")
    ap.add_argument("--data-dir",     default=None,
                    help="Extracted data directory [FALLOUT_DIR/data]")
    ap.add_argument("--out-dir",      default=os.path.join("public", "assets"),
                    help="Web asset output root [public/assets]")
    ap.add_argument("--jobs",         type=int, default=4)
    ap.add_argument("--skip-extract", action="store_true")
    ap.add_argument("--skip-images",  action="store_true")
    ap.add_argument("--skip-maps",    action="store_true")
    ap.add_argument("--skip-audio",   action="store_true")
    ap.add_argument("--update",       action="store_true",
                    help="Skip art files already in imageMap.json")
    ap.add_argument("--fo2",          action="store_true",
                    help="Input is Fallout 2 (DAT2 format)")
    args = ap.parse_args()

    fallout_dir = os.path.abspath(args.fallout_dir)
    data_dir    = os.path.abspath(args.data_dir or os.path.join(fallout_dir, "data"))
    out_dir     = os.path.abspath(args.out_dir)
    art_dir     = os.path.join(out_dir, "art")
    maps_dir    = os.path.join(out_dir, "maps")
    sound_dir   = os.path.join(out_dir, "sound")
    data_out    = os.path.join(out_dir, "data")

    print(f"FallClone Asset Pipeline")
    print(f"  Fallout dir : {fallout_dir}")
    print(f"  Data dir    : {data_dir}")
    print(f"  Output dir  : {out_dir}")
    print(f"  Workers     : {args.jobs}")

    t_start = time.perf_counter()

    # ── Step 1: Extract DATs ──────────────────────────────────────────────────
    if not args.skip_extract:
        _step("Step 1/5 — Extracting DAT archives")
        from extract_dat import extract_all_dats
        force_fmt = "dat2" if args.fo2 else ""
        extract_all_dats(fallout_dir, data_dir, force_fmt)
    else:
        print("\nStep 1/5 — DAT extraction SKIPPED")

    if not os.path.isdir(data_dir):
        print(f"\nERROR: data directory not found: {data_dir}", file=sys.stderr)
        print("Run without --skip-extract, or check that your data_dir exists.")
        sys.exit(1)

    # ── Step 2: PAL → JSON ────────────────────────────────────────────────────
    _step("Step 2/5 — Converting palette (PAL → JSON)")
    pal_path = os.path.join(data_dir, "color.pal")
    if os.path.exists(pal_path):
        from pal_to_json import convert_pal
        pal_out = os.path.join(data_out, "color.json")
        convert_pal(pal_path, pal_out)
    else:
        print(f"  WARNING: color.pal not found at {pal_path}, skipping palette export.")

    # ── Step 3: FRM → PNG ─────────────────────────────────────────────────────
    if not args.skip_images:
        _step("Step 3/5 — Converting art (FRM → PNG)")
        from frm_to_png import convert_all as convert_frms
        convert_frms(
            data_dir        = data_dir,
            out_dir         = art_dir,
            n_jobs          = args.jobs,
            write_image_map = True,
            update          = args.update,
        )
    else:
        print("\nStep 3/5 — FRM → PNG SKIPPED")

    # ── Step 4: MAP → JSON ────────────────────────────────────────────────────
    if not args.skip_maps:
        _step("Step 4/5 — Converting maps (MAP → JSON)")
        maps_src = os.path.join(data_dir, "maps")
        if os.path.isdir(maps_src):
            from map_to_json import convert_maps
            convert_maps(data_dir, maps_src, maps_dir, n_jobs=args.jobs)
        else:
            print(f"  WARNING: maps directory not found at {maps_src}, skipping.")
    else:
        print("\nStep 4/5 — MAP → JSON SKIPPED")

    # ── Step 5: ACM → MP3 ────────────────────────────────────────────────────
    if not args.skip_audio:
        _step("Step 5/5 — Converting audio (ACM → MP3)")
        from acm_to_mp3 import convert_audio
        convert_audio(data_dir, sound_dir, n_jobs=args.jobs)
    else:
        print("\nStep 5/5 — ACM → MP3 SKIPPED")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - t_start
    print(f"\n{'='*60}")
    print(f"  All done in {elapsed:.1f}s")
    print(f"  Web assets written to: {out_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
