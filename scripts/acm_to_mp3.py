#!/usr/bin/env python3
"""
acm_to_mp3.py — Convert Fallout ACM audio to MP3.

Adapted from darkfo/convertAudio.py
Original: Copyright darkf (Apache 2.0)

Fallout ACM is a proprietary audio format (not standard IMA ADPCM).
Two conversion paths are supported, tried in order:

  1. ffmpeg  — preferred. Modern ffmpeg (≥ 4.0) includes the ACM decoder.
               Converts directly: .acm → .mp3 in one step.
               Install: https://ffmpeg.org/download.html

  2. acm2wav — legacy fallback. Converts .acm → .wav (outputs next to input),
               then ffmpeg finishes .wav → .mp3. Requires acm2wav on PATH.
               Get from No Mutants Allowed tools archive.

If neither tool is found the script reports which ACM files were skipped.

Output structure:
  OUT_DIR/sfx/    *.mp3   (sound effects from sound/sfx/)
  OUT_DIR/music/  *.mp3   (music from sound/music/)

Usage:
    python acm_to_mp3.py DATA_DIR OUT_DIR [--jobs N] [--quality Q]

    DATA_DIR    root of extracted Fallout data (contains sound/)
    OUT_DIR     output dir — typically public/assets/sound/

    --jobs N    parallel ffmpeg invocations (default: 4)
    --quality Q MP3 VBR quality 0–9, lower = better (default: 4)
"""

import sys
import os
import glob
import shutil
import subprocess
import argparse
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional


# ── Tool detection ────────────────────────────────────────────────────────────

def _has(tool: str) -> bool:
    return shutil.which(tool) is not None


def _detect_tools() -> Tuple[bool, bool]:
    """Return (has_ffmpeg, has_acm2wav)."""
    return _has("ffmpeg"), _has("acm2wav")


# ── Conversion workers ────────────────────────────────────────────────────────

def _convert_ffmpeg_direct(acm_path: str, mp3_path: str, quality: int) -> bool:
    """Convert ACM → MP3 directly via ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-i", acm_path,
        "-q:a", str(quality),
        mp3_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def _convert_acm2wav_then_ffmpeg(acm_path: str, mp3_path: str, quality: int) -> bool:
    """Convert ACM → WAV via acm2wav, then WAV → MP3 via ffmpeg."""
    with tempfile.TemporaryDirectory() as tmp:
        wav_name = os.path.splitext(os.path.basename(acm_path))[0].lower() + ".wav"
        wav_path = os.path.join(tmp, wav_name)

        # acm2wav writes its output next to the input by default;
        # we run it from tmp so the .wav lands there
        result = subprocess.run(
            ["acm2wav", os.path.abspath(acm_path)],
            cwd=tmp,
            capture_output=True,
        )
        if result.returncode != 0 or not os.path.exists(wav_path):
            return False

        cmd = [
            "ffmpeg", "-y",
            "-i", wav_path,
            "-q:a", str(quality),
            mp3_path,
        ]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0


def _convert_one(task: Tuple) -> Tuple[str, bool, str]:
    acm_path, mp3_path, has_ffmpeg, has_acm2wav, quality = task
    name = os.path.basename(acm_path)

    if has_ffmpeg:
        if _convert_ffmpeg_direct(acm_path, mp3_path, quality):
            return (name, True, "ffmpeg")
        # ffmpeg might not support this ACM variant; try acm2wav fallback
        if has_acm2wav:
            if _convert_acm2wav_then_ffmpeg(acm_path, mp3_path, quality):
                return (name, True, "acm2wav+ffmpeg")

    elif has_acm2wav:
        if _convert_acm2wav_then_ffmpeg(acm_path, mp3_path, quality):
            return (name, True, "acm2wav+ffmpeg")

    return (name, False, "no tool")


# ── Main ──────────────────────────────────────────────────────────────────────

def convert_audio(data_dir: str, out_dir: str,
                  n_jobs: int = 4, quality: int = 4) -> None:
    has_ffmpeg, has_acm2wav = _detect_tools()

    if not has_ffmpeg and not has_acm2wav:
        print(
            "WARNING: Neither ffmpeg nor acm2wav found on PATH.\n"
            "  Install ffmpeg:   https://ffmpeg.org/download.html\n"
            "  Install acm2wav:  https://www.nma-fallout.com/threads/tools.196/ (search for acm2wav)\n"
            "Skipping audio conversion.",
            file=sys.stderr,
        )
        return

    # Locate audio source dirs — Fallout 1/2 use sound/sfx/ and sound/music/
    audio_sources = {
        "sfx":   os.path.join(data_dir, "sound", "sfx"),
        "music": os.path.join(data_dir, "sound", "music"),
    }

    tasks = []
    for subdir, src_dir in audio_sources.items():
        if not os.path.isdir(src_dir):
            # Try alternate casing (some installs use uppercase SOUND/SFX)
            alt = os.path.join(data_dir, "SOUND", subdir.upper())
            if os.path.isdir(alt):
                src_dir = alt
            else:
                print(f"  Skipping {subdir}: directory not found ({src_dir})")
                continue

        out_subdir = os.path.join(out_dir, subdir)
        os.makedirs(out_subdir, exist_ok=True)

        acm_files = sorted(
            glob.glob(os.path.join(src_dir, "*.acm")) +
            glob.glob(os.path.join(src_dir, "*.ACM"))
        )
        for acm in acm_files:
            stem    = os.path.splitext(os.path.basename(acm))[0].lower()
            mp3_out = os.path.join(out_subdir, stem + ".mp3")
            tasks.append((acm, mp3_out, has_ffmpeg, has_acm2wav, quality))

    if not tasks:
        print("No ACM files found.")
        return

    print(f"Converting {len(tasks)} ACM file(s) using {n_jobs} thread(s)…")
    ok = fail = 0

    with ThreadPoolExecutor(max_workers=n_jobs) as pool:
        futs = {pool.submit(_convert_one, t): t for t in tasks}
        for fut in as_completed(futs):
            name, success, method = fut.result()
            if success:
                ok += 1
                print(f"  OK   [{method}] {name}")
            else:
                fail += 1
                print(f"  FAIL {name}")

    print(f"\nDone: {ok} OK, {fail} failed.")
    if fail:
        print("TIP: If ffmpeg direct-decode failed, install acm2wav as fallback.")


def main():
    ap = argparse.ArgumentParser(description="Convert Fallout ACM audio to MP3")
    ap.add_argument("data_dir", help="Root of extracted Fallout data (contains sound/)")
    ap.add_argument("out_dir",  help="Output directory (e.g. public/assets/sound/)")
    ap.add_argument("--jobs",    type=int, default=4, metavar="N")
    ap.add_argument("--quality", type=int, default=4,  metavar="Q",
                    help="MP3 VBR quality 0–9, lower = better (default: 4 ≈ 165 kbps)")
    args = ap.parse_args()

    convert_audio(args.data_dir, args.out_dir,
                  n_jobs=args.jobs, quality=args.quality)


if __name__ == "__main__":
    main()
