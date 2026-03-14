#!/usr/bin/env python3
"""
msg_to_json.py — Convert Fallout .msg message files to JSON.

Fallout .msg format (same format parsed by Harold's fomap.py loadMessage()):

    # This is a comment
    {id}{flags}{message text}

  - Lines starting with # are comments
  - Each valid line has three brace-delimited fields: numeric id, flags (usually
    empty), and the message text
  - A line not starting with { is a continuation of the previous line

Input layout:
    DATA_DIR/text/english/game/*.msg
    DATA_DIR/text/english/dialog/*.msg
    DATA_DIR/text/english/cuts/*.msg
    (any subdirectory under DATA_DIR/text/english/)

Output layout:
    OUT_DIR/data/text/english/{subdir}/{name}.json

    Each JSON file is a dict:  {"id_string": "message text", ...}
    e.g. {"100": "You have entered a dark cave.", "101": "It is very dark."}

Usage:
    python msg_to_json.py DATA_DIR OUT_DIR [--verbose]

    DATA_DIR   root of extracted Fallout data (contains text/)
    OUT_DIR    output root
"""

import sys
import os
import glob
import json
import re
import argparse

sys.path.insert(0, os.path.dirname(__file__))


# ── Parser ────────────────────────────────────────────────────────────────────

_MSG_RE = re.compile(r"\{(\d+)\}\{[^}]*\}\{(.*)\}$")


def parse_msg(text: str) -> dict[str, str]:
    """
    Parse the contents of a .msg file into a dict mapping id → message text.

    Mirrors Harold's fomap.py loadMessage() logic.
    """
    lines = text.splitlines()

    # Preprocess: strip comments, merge continuation lines
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("{"):
            cleaned.append(stripped)
        elif cleaned:
            # continuation line — merge with previous
            cleaned[-1] += stripped

    result: dict[str, str] = {}
    for line in cleaned:
        m = _MSG_RE.match(line)
        if m:
            msg_id, text_val = m.group(1), m.group(2)
            # Harold's HACK: replace Unicode replacement char with apostrophe
            result[msg_id] = text_val.replace("\ufffd", "'")
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def convert_msg(
    data_dir: str,
    out_dir: str,
    verbose: bool = False,
) -> int:
    """
    Convert all .msg files under data_dir/text/english/ to JSON.

    Returns the total number of JSON files written.
    """
    text_root = os.path.join(data_dir, "text", "english")
    if not os.path.isdir(text_root):
        print(f"  WARNING: text directory not found at {text_root}, skipping.")
        return 0

    written = 0
    errors  = 0

    for msg_path in sorted(glob.glob(os.path.join(text_root, "**", "*.msg"),
                                      recursive=True)):
        # relative path from text_root, e.g. "game/misc.msg"
        rel = os.path.relpath(msg_path, text_root)
        name = os.path.splitext(os.path.basename(msg_path))[0].lower()
        subdir = os.path.dirname(rel)

        out_subdir = os.path.join(out_dir, "data", "text", "english", subdir)
        os.makedirs(out_subdir, exist_ok=True)
        out_path = os.path.join(out_subdir, name + ".json")

        try:
            raw = open(msg_path, "rb").read().decode("latin-1")
            messages = parse_msg(raw)
        except Exception as exc:
            print(f"  ERROR parsing {msg_path}: {exc}", file=sys.stderr)
            errors += 1
            continue

        if not messages:
            if verbose:
                print(f"  SKIP {rel} (0 messages)")
            continue

        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(messages, fh, ensure_ascii=False)

        written += 1
        if verbose:
            print(f"  {rel} → {len(messages)} messages")

    print(f"  Wrote {written} message JSON files"
          + (f" ({errors} errors)" if errors else ""))
    return written


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Convert Fallout .msg message files to JSON"
    )
    ap.add_argument("data_dir", help="Root of extracted Fallout data (contains text/)")
    ap.add_argument("out_dir",  help="Output root")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    n = convert_msg(
        data_dir = args.data_dir,
        out_dir  = args.out_dir,
        verbose  = args.verbose,
    )
    if n == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
