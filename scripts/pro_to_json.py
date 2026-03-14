#!/usr/bin/env python3
"""
pro_to_json.py — Convert Fallout PRO (prototype object) files to JSON.

Based on darkfo/exportPRO.py
Original: Copyright 2014-2017 darkf (Apache 2.0)

Python 3.9+ port:
  - Uses lib/proto.py (Python 3 port of darkfo/proto.py)
  - fo1=True default (Fallout 1 mode; pass --fo2 for Fallout 2)
  - Parallel processing via ProcessPoolExecutor

Input layout:
    DATA_DIR/proto/items/*.pro
    DATA_DIR/proto/critters/*.pro
    DATA_DIR/proto/scenery/*.pro
    DATA_DIR/proto/walls/*.pro
    DATA_DIR/proto/misc/*.pro

Output:
    OUT_DIR/proto/pro.json   ← master JSON consumed by DarkFO engine

Usage:
    python pro_to_json.py DATA_DIR OUT_DIR [--fo2] [--verbose]

    DATA_DIR   root of extracted Fallout data (contains proto/)
    OUT_DIR    output root (writes OUT_DIR/proto/pro.json)
"""

import sys
import os
import glob
import json
import argparse
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))

from lib.proto import read_pro

SUBDIRS: tuple[str, ...] = ("items", "critters", "scenery", "walls", "misc")


# ── Worker ────────────────────────────────────────────────────────────────────

def _worker(task: tuple) -> tuple[str, int, dict | None]:
    """Parse one .pro file.  Returns (subdir, id, data_or_None)."""
    subdir, pro_id, path, fo1 = task
    try:
        with open(path, "rb") as f:
            return subdir, pro_id, read_pro(f, fo1=fo1)
    except Exception:
        print(f"  ERROR reading {path}:\n{traceback.format_exc()}", file=sys.stderr)
        return subdir, pro_id, None


# ── Public API ────────────────────────────────────────────────────────────────

def convert_pro(
    data_dir: str,
    out_dir: str,
    fo1: bool = True,
    n_jobs: int = 4,
    verbose: bool = False,
) -> int:
    """
    Convert all .pro files under data_dir/proto/ into a single pro.json.

    Mirrors Harold's extractPROs() logic, adapted for Python 3.9+ and
    parallel processing.

    Returns the total number of successfully converted PRO entries.
    """
    proto_src = os.path.join(data_dir, "proto")
    if not os.path.isdir(proto_src):
        print(f"  WARNING: proto directory not found at {proto_src}, skipping.")
        return 0

    proto_out = os.path.join(out_dir, "proto")
    os.makedirs(proto_out, exist_ok=True)

    # Build task list: (subdir, id, path, fo1)
    tasks: list[tuple] = []
    for subdir in SUBDIRS:
        pattern = os.path.join(proto_src, subdir, "*.pro")
        for path in sorted(glob.glob(pattern)):
            base = os.path.splitext(os.path.basename(path))[0]
            try:
                pro_id = int(base)
            except ValueError:
                print(f"  WARNING: skipping {path} (non-numeric filename)")
                continue
            tasks.append((subdir, pro_id, path, fo1))

    if not tasks:
        print("  WARNING: no .pro files found, skipping PRO export.")
        return 0

    if verbose:
        print(f"  Converting {len(tasks)} PRO files ({n_jobs} workers)...")

    # master dict: {subdir: {id: data}}
    root: dict[str, dict] = {s: {} for s in SUBDIRS}
    done = 0
    errors = 0

    with ProcessPoolExecutor(max_workers=n_jobs) as pool:
        futs = {pool.submit(_worker, t): t for t in tasks}
        for fut in as_completed(futs):
            subdir, pro_id, data = fut.result()
            done += 1
            if data is not None:
                root[subdir][str(pro_id)] = data
                if verbose:
                    print(f"  [{done}/{len(tasks)}] {subdir}/{pro_id}")
            else:
                errors += 1

    out_path = os.path.join(proto_out, "pro.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(root, fh)

    total = sum(len(v) for v in root.values())
    print(f"  Wrote {total} PRO entries to {out_path}"
          + (f" ({errors} errors)" if errors else ""))
    return total


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Convert Fallout .pro prototype files to pro.json"
    )
    ap.add_argument("data_dir", help="Root of extracted Fallout data (contains proto/)")
    ap.add_argument("out_dir",  help="Output root (writes out_dir/proto/pro.json)")
    ap.add_argument("--fo2",     action="store_true", help="Fallout 2 mode (default: FO1)")
    ap.add_argument("--jobs",    type=int, default=4, metavar="N")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    n = convert_pro(
        data_dir = args.data_dir,
        out_dir  = args.out_dir,
        fo1      = not args.fo2,
        n_jobs   = args.jobs,
        verbose  = args.verbose,
    )
    if n == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
