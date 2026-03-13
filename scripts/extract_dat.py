#!/usr/bin/env python3
"""
extract_dat.py — Extract Fallout 1 DAT1 or Fallout 2 DAT2 archives.

DarkFO only ships a DAT2 reader (dat2.py). This script adds DAT1 support
for Fallout 1's MASTER.DAT and CRITTER.DAT, using our lib/dat1.py reader.

Auto-detects format by magic: DAT2 footer is at end-of-file; DAT1 header
has a directory count > 0 in the first 4 bytes and uses big-endian integers.

Usage:
    python extract_dat.py FALLOUT_DIR DATA_DIR [--dat DAT_FILE] [--fo2]

    FALLOUT_DIR  Fallout 1 installation directory (contains MASTER.DAT etc.)
    DATA_DIR     Output directory for extracted files (e.g. fallout/data/)

    --dat FILE   Extract a single specific .DAT file instead of all
    --fo2        Force Fallout 2 DAT2 format (auto-detected if omitted)

Examples:
    # Extract all Fallout 1 DATs
    python extract_dat.py "C:/Games/Fallout" fallout/data/

    # Extract a specific file
    python extract_dat.py "C:/Games/Fallout" fallout/data/ --dat MASTER.DAT

    # Fallout 2
    python extract_dat.py "C:/Games/Fallout2" fallout2/data/ --fo2
"""

import sys
import os
import struct
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from lib import dat1, dat2


# ── Format detection ──────────────────────────────────────────────────────────

def _detect_format(dat_path: str) -> str:
    """Return 'dat1' or 'dat2'."""
    with open(dat_path, "rb") as f:
        # DAT2: last 8 bytes are (dir_tree_size LE, archive_size LE)
        # If archive_size matches file size it's DAT2
        file_size = os.path.getsize(dat_path)
        f.seek(-8, 2)
        _tree = struct.unpack("<l", f.read(4))[0]
        arch  = struct.unpack("<l", f.read(4))[0]
        if arch == file_size:
            return "dat2"

        # DAT1: first 4 bytes (big-endian) = directory count; plausible range 1–500
        f.seek(0)
        n_dirs = struct.unpack(">I", f.read(4))[0]
        if 1 <= n_dirs <= 500:
            return "dat1"

    return "dat1"  # default assumption for Fallout 1


# ── Extraction ────────────────────────────────────────────────────────────────

def extract_dat(dat_path: str, out_dir: str, force_fmt: str = "") -> None:
    fmt = force_fmt or _detect_format(dat_path)
    print(f"Extracting {os.path.basename(dat_path)} (format: {fmt}) → {out_dir}")

    os.makedirs(out_dir, exist_ok=True)

    if fmt == "dat1":
        n = dat1.extract_all(dat_path, out_dir, verbose=True)
    else:
        n = dat2.extract_all(dat_path, out_dir, verbose=True)

    print(f"Extracted {n} files from {os.path.basename(dat_path)}")


def extract_all_dats(install_dir: str, out_dir: str, force_fmt: str = "") -> None:
    """
    Find and extract all .DAT files in install_dir.

    Fallout 1 ships: MASTER.DAT, CRITTER.DAT
    Fallout 2 ships: master.dat, critter.dat  (same names, different format)
    """
    import glob
    dats = sorted(
        glob.glob(os.path.join(install_dir, "*.dat")) +
        glob.glob(os.path.join(install_dir, "*.DAT"))
    )

    if not dats:
        print(f"No .DAT files found in {install_dir}", file=sys.stderr)
        sys.exit(1)

    for dat_path in dats:
        extract_dat(dat_path, out_dir, force_fmt)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Extract Fallout DAT archives")
    ap.add_argument("fallout_dir", help="Fallout installation directory")
    ap.add_argument("data_dir",   help="Output directory for extracted data")
    ap.add_argument("--dat",      metavar="FILE",
                    help="Extract a single specific DAT file (basename or full path)")
    ap.add_argument("--fo2",      action="store_true",
                    help="Force Fallout 2 DAT2 format")
    args = ap.parse_args()

    force_fmt = "dat2" if args.fo2 else ""

    if args.dat:
        # Single file
        if os.path.isabs(args.dat) or os.sep in args.dat:
            dat_path = args.dat
        else:
            dat_path = os.path.join(args.fallout_dir, args.dat)

        if not os.path.exists(dat_path):
            print(f"ERROR: {dat_path} not found", file=sys.stderr)
            sys.exit(1)

        extract_dat(dat_path, args.data_dir, force_fmt)
    else:
        extract_all_dats(args.fallout_dir, args.data_dir, force_fmt)


if __name__ == "__main__":
    main()
