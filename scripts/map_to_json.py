#!/usr/bin/env python3
"""
map_to_json.py — Convert Fallout 1/2 .MAP files to JSON (DarkFO format).

Adapted from darkfo/fomap.py and darkfo/convertMaps.py
Original: Copyright 2015 darkf (Apache 2.0)

Supports both Fallout 1 (MAP version 19) and Fallout 2 (version 20) files.
Output JSON is directly consumed by our Phaser 3 MapLoader.

Usage:
    python map_to_json.py DATA_DIR MAP_FILE_OR_DIR OUT_DIR [--jobs N]

    DATA_DIR         root of extracted Fallout data (art/, maps/, proto/, ...)
    MAP_FILE_OR_DIR  single .MAP file OR a directory of .MAP files
    OUT_DIR          output directory — typically public/assets/maps/

    --jobs N         parallel workers when converting a directory (default: 4)

Examples:
    # Single map
    python map_to_json.py fallout/data fallout/data/maps/v13ent.map public/assets/maps/

    # All maps
    python map_to_json.py fallout/data fallout/data/maps/ public/assets/maps/ --jobs 4
"""

import sys
import os
import glob
import argparse
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Tuple

sys.path.insert(0, os.path.dirname(__file__))

from lib.fomap import export_map


# ── Worker (must be module-level for multiprocessing) ─────────────────────────

def _worker(task: Tuple[str, str, str, bool]) -> Tuple[str, bool]:
    data_dir, map_file, out_file, verbose = task
    name = os.path.basename(map_file)
    try:
        export_map(data_dir, map_file, out_file, verbose=verbose)
        return (name, True)
    except Exception as e:
        print(f"  ERROR: {name}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return (name, False)


# ── Main ──────────────────────────────────────────────────────────────────────

def convert_maps(data_dir: str, map_source: str, out_dir: str,
                 n_jobs: int = 4, verbose: bool = False) -> None:
    os.makedirs(out_dir, exist_ok=True)

    # Collect MAP files
    if os.path.isdir(map_source):
        map_files = sorted(
            glob.glob(os.path.join(map_source, "*.map")) +
            glob.glob(os.path.join(map_source, "*.MAP"))
        )
    elif os.path.isfile(map_source):
        map_files = [map_source]
    else:
        raise FileNotFoundError(f"Not a file or directory: {map_source}")

    if not map_files:
        print("No .MAP files found.")
        return

    tasks = []
    for mf in map_files:
        stem     = os.path.splitext(os.path.basename(mf))[0].lower()
        out_file = os.path.join(out_dir, stem + ".json")
        tasks.append((data_dir, mf, out_file, verbose))

    print(f"Converting {len(tasks)} map(s) with {n_jobs} worker(s)…")
    ok = fail = 0

    with ProcessPoolExecutor(max_workers=n_jobs) as pool:
        futs = {pool.submit(_worker, t): t for t in tasks}
        for fut in as_completed(futs):
            name, success = fut.result()
            if success:
                ok += 1
                print(f"  OK   {name}")
            else:
                fail += 1
                print(f"  FAIL {name}")

    print(f"\nDone: {ok} OK, {fail} failed.")


def main():
    ap = argparse.ArgumentParser(description="Convert Fallout MAP files to JSON")
    ap.add_argument("data_dir",   help="Root of extracted Fallout data")
    ap.add_argument("map_source", help=".MAP file or directory of .MAP files")
    ap.add_argument("out_dir",    help="Output directory for JSON files")
    ap.add_argument("--jobs",     type=int, default=4, metavar="N")
    ap.add_argument("--verbose",  action="store_true")
    args = ap.parse_args()

    try:
        convert_maps(args.data_dir, args.map_source, args.out_dir,
                     n_jobs=args.jobs, verbose=args.verbose)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
