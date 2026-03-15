#!/usr/bin/env python3
"""
convert_all.py — Master asset pipeline for FallClone.

Runs the full conversion pipeline in the correct order:

  0. copy_lst    — raw_assets/**/*.lst → public/assets/**/*.lst  (as-is copy)
  1. extract_dat — MASTER.DAT + CRITTER.DAT → data/        (skippable)
  2. pal_to_json — color.pal → public/assets/data/color.json
  3. frm_to_png  — art/**/*.frm → public/assets/art/**/*.png + imageMap.json
  4. map_to_json — maps/*.map  → public/assets/maps/*.json
  5. pro_to_json — proto/**/*.pro → public/assets/proto/pro.json
  6. msg_to_json — text/english/**/*.msg → public/assets/data/text/.../*.json
  7. acm_to_mp3  — sound/**/*.acm → public/assets/sound/**/*.mp3

Based on Harold's darkfo reference scripts (Python 3.9+ rewrite).

Usage:
    python convert_all.py FALLOUT_DIR [options]

    FALLOUT_DIR   Path to Fallout 1 installation
                  (contains MASTER.DAT and CRITTER.DAT,
                   or an already-extracted data/ subdirectory)

Options:
    --data-dir DIR    Where to find/place extracted raw data  [raw_assets/]
    --out-dir  DIR    Web asset output root                    [public/assets]
    --jobs N          Parallel workers for images/maps/audio  [4]
    --skip-lst        Skip .lst copy step
    --skip-extract    Skip DAT extraction (data/ already exists)
    --skip-images     Skip FRM → PNG conversion
    --skip-maps       Skip MAP → JSON conversion
    --skip-pro        Skip PRO → JSON conversion
    --skip-msg        Skip MSG → JSON conversion
    --skip-audio      Skip ACM → MP3 conversion
    --update          Skip art files already in imageMap.json (incremental)
    --fo2             Input is Fallout 2 (DAT2 format, disables FO1 PRO mode)

Examples:
    # Full pipeline from Fallout 1 GOG install
    python convert_all.py "C:/GOG Games/Fallout"

    # Already extracted, re-convert art only (incremental)
    python convert_all.py /games/fallout --skip-extract --skip-maps \\
        --skip-pro --skip-msg --skip-audio --update

    # Fallout 2 full pipeline
    python convert_all.py "C:/GOG Games/Fallout2" --fo2
"""

import sys
import os
import shutil
import argparse
import time

sys.path.insert(0, os.path.dirname(__file__))


def _run_lst(data_dir: str, out_dir: str) -> int:
    """
    Copy every .lst file from data_dir to the same relative path under out_dir.

    Example:
        raw_assets/art/critters/critters.lst
            → public/assets/art/critters/critters.lst
        raw_assets/proto/items/items.lst
            → public/assets/proto/items/items.lst

    Returns the number of files copied.
    """
    count = 0
    for dirpath, _dirnames, filenames in os.walk(data_dir):
        for fname in filenames:
            if fname.lower().endswith(".lst"):
                src = os.path.join(dirpath, fname)
                rel = os.path.relpath(src, data_dir)
                dst = os.path.join(out_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  {rel}")
                count += 1
    return count


def _step(label: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="FallClone full asset conversion pipeline (Harold reference)"
    )
    ap.add_argument("fallout_dir",
                    help="Fallout installation directory (contains MASTER.DAT etc.)")
    ap.add_argument("--data-dir",     default=None,
                    help="Extracted data directory [raw_assets/]")
    ap.add_argument("--out-dir",      default=os.path.join("public", "assets"),
                    help="Web asset output root [public/assets]")
    ap.add_argument("--jobs",         type=int, default=4)
    ap.add_argument("--skip-lst",     action="store_true",
                    help="Skip copying .lst index files to public/assets/")
    ap.add_argument("--skip-extract", action="store_true",
                    help="Skip DAT extraction (data/ already exists)")
    ap.add_argument("--skip-images",  action="store_true")
    ap.add_argument("--skip-maps",    action="store_true")
    ap.add_argument("--skip-pro",     action="store_true")
    ap.add_argument("--skip-msg",     action="store_true")
    ap.add_argument("--skip-audio",   action="store_true")
    ap.add_argument("--update",       action="store_true",
                    help="Skip art already in imageMap.json (incremental)")
    ap.add_argument("--fo2",          action="store_true",
                    help="Input is Fallout 2 (DAT2 archives, FO2 PRO mode)")
    args = ap.parse_args()

    fallout_dir = os.path.abspath(args.fallout_dir)
    # Default extraction target is raw_assets/ inside the project directory.
    # This keeps all local Fallout data in one gitignored folder rather than
    # writing outside the project tree.  raw_assets/ mirrors the DAT layout:
    #   art/tiles/tiles.lst, art/critters/critters.lst,
    #   proto/items/items.lst, proto/scenery/scenery.lst,
    #   proto/critters/critters.lst, proto/walls/walls.lst,
    #   scripts/scripts.lst, art/items/items.lst, art/walls/walls.lst,
    #   art/misc/misc.lst, art/scenery/scenery.lst, ...
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir    = os.path.abspath(args.data_dir or os.path.join(_project_root, "raw_assets"))
    out_dir     = os.path.abspath(args.out_dir)
    art_dir     = os.path.join(out_dir, "art")
    maps_dir    = os.path.join(out_dir, "maps")
    sound_dir   = os.path.join(out_dir, "sound")
    data_out    = os.path.join(out_dir, "data")

    print("FallClone Asset Pipeline (Harold reference, Python 3.9+)")
    print(f"  Fallout dir : {fallout_dir}")
    print(f"  Data dir    : {data_dir}")
    print(f"  Output dir  : {out_dir}")
    print(f"  Workers     : {args.jobs}")
    print(f"  Mode        : {'Fallout 2 (FO2)' if args.fo2 else 'Fallout 1 (FO1)'}")

    t_start = time.perf_counter()

    # ── Step 0: Copy .lst index files ────────────────────────────────────────
    if not args.skip_lst:
        _step("Step 0/7 — Copying .lst index files → public/assets/")
        if os.path.isdir(data_dir):
            n = _run_lst(data_dir, out_dir)
            print(f"  Copied {n} .lst file(s).")
        else:
            print(f"  WARNING: data dir not found ({data_dir}), skipping .lst copy.")
    else:
        print("\nStep 0/7 — .lst copy SKIPPED")

    # ── Step 1: Extract DATs ──────────────────────────────────────────────────
    if not args.skip_extract:
        _step("Step 1/7 — Extracting DAT archives")
        from extract_dat import extract_all_dats
        force_fmt = "dat2" if args.fo2 else ""
        extract_all_dats(fallout_dir, data_dir, force_fmt)
    else:
        print("\nStep 1/7 — DAT extraction SKIPPED")

    if not os.path.isdir(data_dir):
        print(f"\nERROR: data directory not found: {data_dir}", file=sys.stderr)
        print("Run without --skip-extract, or verify --data-dir.")
        sys.exit(1)

    # ── Step 2: PAL → JSON ────────────────────────────────────────────────────
    _step("Step 2/7 — Converting palette (PAL → JSON)")
    pal_path = os.path.join(data_dir, "color.pal")
    if os.path.exists(pal_path):
        from pal_to_json import convert_pal
        pal_out = os.path.join(data_out, "color.json")
        convert_pal(pal_path, pal_out)
    else:
        print(f"  WARNING: color.pal not found at {pal_path}, skipping.")

    # ── Step 3: FRM → PNG ─────────────────────────────────────────────────────
    if not args.skip_images:
        _step("Step 3/7 — Converting art (FRM → PNG + imageMap.json)")
        from frm_to_png import convert_all as convert_frms
        convert_frms(
            data_dir        = data_dir,
            out_dir         = art_dir,
            n_jobs          = args.jobs,
            write_image_map = True,
            update          = args.update,
        )
    else:
        print("\nStep 3/7 — FRM → PNG SKIPPED")

    # ── Step 4: MAP → JSON ────────────────────────────────────────────────────
    if not args.skip_maps:
        _step("Step 4/7 — Converting maps (MAP → JSON)")
        maps_src = os.path.join(data_dir, "maps")
        if os.path.isdir(maps_src):
            from map_to_json import convert_maps
            convert_maps(data_dir, maps_src, maps_dir, n_jobs=args.jobs)
        else:
            print(f"  WARNING: maps directory not found at {maps_src}, skipping.")
    else:
        print("\nStep 4/7 — MAP → JSON SKIPPED")

    # ── Step 5: PRO → JSON ────────────────────────────────────────────────────
    if not args.skip_pro:
        _step("Step 5/7 — Converting prototypes (PRO → JSON)")
        from pro_to_json import convert_pro
        convert_pro(
            data_dir = data_dir,
            out_dir  = out_dir,
            fo1      = not args.fo2,
            n_jobs   = args.jobs,
            verbose  = False,
        )
    else:
        print("\nStep 5/7 — PRO → JSON SKIPPED")

    # ── Step 6: MSG → JSON ────────────────────────────────────────────────────
    if not args.skip_msg:
        _step("Step 6/7 — Converting messages (MSG → JSON)")
        from msg_to_json import convert_msg
        convert_msg(
            data_dir = data_dir,
            out_dir  = out_dir,
            verbose  = False,
        )
    else:
        print("\nStep 6/7 — MSG → JSON SKIPPED")

    # ── Step 7: ACM → MP3 ────────────────────────────────────────────────────
    if not args.skip_audio:
        _step("Step 7/7 — Converting audio (ACM → MP3)")
        from acm_to_mp3 import convert_audio
        convert_audio(data_dir, sound_dir, n_jobs=args.jobs)
    else:
        print("\nStep 7/7 — ACM → MP3 SKIPPED")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - t_start
    print(f"\n{'='*60}")
    print(f"  All done in {elapsed:.1f}s")
    print(f"  Web assets written to: {out_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
