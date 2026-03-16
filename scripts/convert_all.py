#!/usr/bin/env python3
"""
convert_all.py — Asset pipeline for FallClone.

Flow:
  1. extract  — MASTER.DAT + CRITTER.DAT → public/assets/
  2. pal      — color.pal → data/color.json
  3. frm      — art/**/*.frm  → art/**/*.png + imageMap.json; delete .frm/.fr[0-5]
  4. map      — maps/*.map    → maps/*.json;                  delete .map
  5. pro      — proto/**/*.pro → proto/pro.json;              delete .pro
  6. msg      — text/**/*.msg → data/text/**/*.json
  7. audio    — sound/**/*.acm → sound/**/*.mp3;              delete .acm

.lst / .txt / .pal / .int are left untouched after extraction.
All output lives under a single public/assets/ tree — no raw_assets/ staging.
A full convert.log is written to the project root.

Usage:
    python convert_all.py FALLOUT_DIR [options]

    FALLOUT_DIR   Fallout installation directory (contains MASTER.DAT etc.)

Options:
    --out-dir DIR     Web asset root   [public/assets]
    --jobs N          Parallel workers [4]
    --skip-extract    Skip DAT extraction (public/assets/ already populated)
    --skip-images     Skip FRM → PNG
    --skip-maps       Skip MAP → JSON
    --skip-pro        Skip PRO → JSON
    --skip-msg        Skip MSG → JSON
    --skip-audio      Skip ACM → MP3
    --update          Incremental FRM: skip already-converted files
    --fo2             Fallout 2 (DAT2 archives, FO2 PRO mode)
"""

import sys
import os
import glob
import argparse
import time

sys.path.insert(0, os.path.dirname(__file__))

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOG_PATH = os.path.join(_PROJECT_ROOT, "convert.log")


# ── Tee: mirror all stdout/stderr to convert.log ──────────────────────────────

class _Tee:
    def __init__(self, primary, secondary):
        self._p = primary
        self._s = secondary

    def write(self, data):
        self._p.write(data)
        self._s.write(data)

    def flush(self):
        self._p.flush()
        self._s.flush()

    def isatty(self):
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _step(n: int, label: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n  Step {n}/7 — {label}\n{bar}")


def _delete(path: str) -> None:
    try:
        os.remove(path)
        print(f"  deleted  {path}")
    except OSError as e:
        print(f"  WARNING: could not delete {path}: {e}", file=sys.stderr)


# ── Step runners ──────────────────────────────────────────────────────────────

def _run_extract(fallout_dir: str, out_dir: str, force_fmt: str) -> None:
    from extract_dat import extract_all_dats
    print(f"  Source : {fallout_dir}")
    print(f"  Output : {out_dir}")
    extract_all_dats(fallout_dir, out_dir, force_fmt)


def _run_pal(out_dir: str) -> None:
    pal_path = os.path.join(out_dir, "color.pal")
    if not os.path.exists(pal_path):
        print(f"  WARNING: color.pal not found at {pal_path}, skipping.")
        return
    from pal_to_json import convert_pal
    convert_pal(pal_path, os.path.join(out_dir, "data", "color.json"))


def _run_frm(out_dir: str, n_jobs: int, update: bool) -> None:
    from frm_to_png import convert_all as convert_frms
    art_dir = os.path.join(out_dir, "art")
    convert_frms(
        data_dir        = out_dir,
        out_dir         = art_dir,
        n_jobs          = n_jobs,
        write_image_map = True,
        update          = update,
    )
    # Delete source FRM / FR[0-5] files where the PNG was produced
    n_del = 0
    for frm in glob.glob(os.path.join(art_dir, "**", "*.frm"), recursive=True):
        if os.path.exists(os.path.splitext(frm)[0] + ".png"):
            _delete(frm)
            n_del += 1
    for ext in ("fr0", "fr1", "fr2", "fr3", "fr4", "fr5"):
        for frx in glob.glob(os.path.join(art_dir, "**", f"*.{ext}"), recursive=True):
            if os.path.exists(os.path.splitext(frx)[0] + ".png"):
                _delete(frx)
                n_del += 1
    print(f"  Deleted {n_del} source FRM/FR[0-5] files.")


def _run_maps(out_dir: str, n_jobs: int) -> None:
    from map_to_json import convert_maps
    maps_dir = os.path.join(out_dir, "maps")
    if not os.path.isdir(maps_dir):
        print(f"  WARNING: maps/ not found at {maps_dir}, skipping.")
        return
    convert_maps(out_dir, maps_dir, maps_dir, n_jobs=n_jobs)
    # Delete .map files where the .json was produced
    n_del = 0
    for mp in (glob.glob(os.path.join(maps_dir, "*.map")) +
               glob.glob(os.path.join(maps_dir, "*.MAP"))):
        stem = os.path.splitext(os.path.basename(mp))[0].lower()
        if os.path.exists(os.path.join(maps_dir, stem + ".json")):
            _delete(mp)
            n_del += 1
    print(f"  Deleted {n_del} .map source files.")


def _run_pro(out_dir: str, n_jobs: int, fo1: bool) -> None:
    from pro_to_json import convert_pro
    n = convert_pro(data_dir=out_dir, out_dir=out_dir, fo1=fo1,
                    n_jobs=n_jobs, verbose=False)
    if n == 0:
        return
    # Delete .pro files once pro.json is confirmed on disk
    pro_json = os.path.join(out_dir, "proto", "pro.json")
    if not os.path.exists(pro_json):
        return
    n_del = 0
    for pro in glob.glob(os.path.join(out_dir, "proto", "**", "*.pro"), recursive=True):
        _delete(pro)
        n_del += 1
    print(f"  Deleted {n_del} .pro source files.")


def _run_msg(out_dir: str) -> None:
    from msg_to_json import convert_msg
    convert_msg(data_dir=out_dir, out_dir=out_dir, verbose=False)


def _run_audio(out_dir: str, n_jobs: int) -> None:
    from acm_to_mp3 import convert_audio
    sound_dir = os.path.join(out_dir, "sound")
    if not os.path.isdir(sound_dir):
        print(f"  WARNING: sound/ not found at {sound_dir}, skipping.")
        return
    convert_audio(out_dir, sound_dir, n_jobs=n_jobs)
    # Delete .acm files where the .mp3 was produced
    n_del = 0
    for acm in glob.glob(os.path.join(sound_dir, "**", "*.acm"), recursive=True):
        if os.path.exists(os.path.splitext(acm)[0] + ".mp3"):
            _delete(acm)
            n_del += 1
    print(f"  Deleted {n_del} .acm source files.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="FallClone asset pipeline — extract DATs and convert in-place"
    )
    ap.add_argument("fallout_dir",
                    help="Fallout installation directory (contains MASTER.DAT etc.)")
    ap.add_argument("--out-dir",      default=os.path.join("public", "assets"),
                    help="Web asset root [public/assets]")
    ap.add_argument("--jobs",         type=int, default=4)
    ap.add_argument("--skip-extract", action="store_true",
                    help="Skip DAT extraction (out-dir already populated)")
    ap.add_argument("--skip-images",  action="store_true")
    ap.add_argument("--skip-maps",    action="store_true")
    ap.add_argument("--skip-pro",     action="store_true")
    ap.add_argument("--skip-msg",     action="store_true")
    ap.add_argument("--skip-audio",   action="store_true")
    ap.add_argument("--update",       action="store_true",
                    help="Incremental FRM: skip already-converted files")
    ap.add_argument("--fo2",          action="store_true",
                    help="Fallout 2 (DAT2 archives, FO2 PRO mode)")
    args = ap.parse_args()

    fallout_dir = os.path.abspath(args.fallout_dir)
    out_dir     = os.path.abspath(args.out_dir)

    log_file = open(_LOG_PATH, "w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)

    try:
        _run(args, fallout_dir, out_dir)
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        log_file.close()


def _run(args, fallout_dir: str, out_dir: str) -> None:
    t_start = time.perf_counter()

    print("FallClone Asset Pipeline")
    print(f"  Fallout dir : {fallout_dir}")
    print(f"  Assets dir  : {out_dir}")
    print(f"  Log         : {_LOG_PATH}")
    print(f"  Workers     : {args.jobs}")
    print(f"  Mode        : {'Fallout 2 (FO2)' if args.fo2 else 'Fallout 1 (FO1)'}")

    # Step 1 — Extract
    if not args.skip_extract:
        _step(1, "Extracting DATs → public/assets/")
        _run_extract(fallout_dir, out_dir, "dat2" if args.fo2 else "")
    else:
        print("\nStep 1/7 — DAT extraction SKIPPED")

    if not os.path.isdir(out_dir):
        print(f"\nERROR: output directory not found: {out_dir}", file=sys.stderr)
        sys.exit(1)

    # Step 2 — PAL
    _step(2, "color.pal → data/color.json")
    _run_pal(out_dir)

    # Step 3 — FRM → PNG
    if not args.skip_images:
        _step(3, "FRM → PNG + imageMap.json  (delete .frm/.fr[0-5] after)")
        _run_frm(out_dir, args.jobs, args.update)
    else:
        print("\nStep 3/7 — FRM → PNG SKIPPED")

    # Step 4 — MAP → JSON
    if not args.skip_maps:
        _step(4, "MAP → JSON  (delete .map after)")
        _run_maps(out_dir, args.jobs)
    else:
        print("\nStep 4/7 — MAP → JSON SKIPPED")

    # Step 5 — PRO → JSON
    if not args.skip_pro:
        _step(5, "PRO → proto/pro.json  (delete .pro after)")
        _run_pro(out_dir, args.jobs, fo1=not args.fo2)
    else:
        print("\nStep 5/7 — PRO → JSON SKIPPED")

    # Step 6 — MSG → JSON
    if not args.skip_msg:
        _step(6, "MSG → JSON")
        _run_msg(out_dir)
    else:
        print("\nStep 6/7 — MSG → JSON SKIPPED")

    # Step 7 — ACM → MP3
    if not args.skip_audio:
        _step(7, "ACM → MP3  (delete .acm after)")
        _run_audio(out_dir, args.jobs)
    else:
        print("\nStep 7/7 — ACM → MP3 SKIPPED")

    elapsed = time.perf_counter() - t_start
    print(f"\n{'='*60}")
    print(f"  Done in {elapsed:.1f}s  →  {out_dir}")
    print(f"  Log: {_LOG_PATH}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
