"""
Fallout 1 DAT1 archive reader — not in DarkFO (which targets Fallout 2 DAT2).

DAT1 format documentation compiled from:
  - Fallout Modding Wiki (NMA) technical specs
  - TeamX Fallout 1 SDK notes
  - Cross-verified against multiple open-source implementations

Format overview (all multi-byte integers are big-endian):
  Header      16 bytes
  Dir names   variable  (n_dirs × [uint8 len + char[] name])
  File tree   variable  (for each dir: uint32 n_files + 3×uint32 unk +
                                       n_files × [uint8 len + char[] name +
                                                  uint8 attr + 3 pad +
                                                  uint32 orig + uint32 packed + uint32 offset])
  Data        raw file contents at stated offsets

Attributes byte:
  0x20 = stored (uncompressed)
  0x40 = LZSS compressed (Fallout's own LZSS variant — see _lzss_decompress)
"""

import os
import struct
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple


@dataclass
class Dat1Entry:
    filename:     str    # full lowercase POSIX path, e.g. "art/tiles/stonebl.frm"
    compressed:   bool
    orig_size:    int
    packed_size:  int
    offset:       int    # byte offset from start of DAT file


# ── LZSS decompressor ─────────────────────────────────────────────────────────

def _lzss_decompress(data: bytes, orig_size: int) -> bytes:
    """
    Fallout 1 LZSS decompressor.

    Parameters
    ----------
    data      : compressed bytes
    orig_size : expected decompressed length

    Algorithm
    ---------
    Circular window of 4096 bytes, initialised to 0x20 (space), pointer at 0xFEE.
    Each 1-byte control word encodes 8 operations (LSB-first):
      bit = 1 → literal: copy next byte to output and window
      bit = 0 → back-ref: read 2 bytes (lo, hi)
                  offset = lo | ((hi & 0xF0) << 4)   (12-bit window position)
                  count  = (hi & 0x0F) + 3
                  copy count bytes from window[offset..] to output and window
    """
    result = bytearray(orig_size)
    window = bytearray(b'\x20' * 4096)
    wptr   = 0xFEE   # window write pointer (initial fill position)
    rptr   = 0        # source read pointer
    wout   = 0        # output write pointer

    while wout < orig_size and rptr < len(data):
        ctrl = data[rptr]; rptr += 1

        for bit in range(8):
            if wout >= orig_size or rptr >= len(data):
                break

            if ctrl & (1 << bit):
                # Literal byte
                b = data[rptr]; rptr += 1
                result[wout] = b
                window[wptr] = b
                wout  += 1
                wptr   = (wptr + 1) & 0xFFF
            else:
                # Back-reference — needs 2 bytes
                if rptr + 1 >= len(data):
                    break
                lo = data[rptr];     rptr += 1
                hi = data[rptr];     rptr += 1
                offset = lo | ((hi & 0xF0) << 4)
                count  = (hi & 0x0F) + 3

                for _ in range(count):
                    if wout >= orig_size:
                        break
                    b = window[offset & 0xFFF]
                    result[wout] = b
                    window[wptr] = b
                    wout   += 1
                    wptr    = (wptr + 1) & 0xFFF
                    offset  = (offset + 1) & 0xFFF

    return bytes(result)


# ── DAT1 reader ───────────────────────────────────────────────────────────────

def _read_u8(f)  -> int: return f.read(1)[0]
def _read_u32(f) -> int: return struct.unpack(">I", f.read(4))[0]


def read_dat(path: str) -> Dict[str, Dat1Entry]:
    """
    Parse a Fallout 1 .DAT archive and return a dict mapping
    lowercase POSIX filename → Dat1Entry.

    Does not extract any data; use read_file() to get file contents.
    """
    entries: Dict[str, Dat1Entry] = {}

    with open(path, "rb") as f:
        # Header
        n_dirs      = _read_u32(f)
        _unk1       = _read_u32(f)
        _unk2       = _read_u32(f)
        _tree_size  = _read_u32(f)

        # Directory names
        dir_names: List[str] = []
        for _ in range(n_dirs):
            length = _read_u8(f)
            name   = f.read(length).decode("latin-1")
            dir_names.append(name)

        # File entries (one block per directory, in the same order)
        for dir_name in dir_names:
            n_files = _read_u32(f)
            _unk_a  = _read_u32(f)
            _unk_b  = _read_u32(f)
            _unk_c  = _read_u32(f)

            for _ in range(n_files):
                fname_len  = _read_u8(f)
                fname      = f.read(fname_len).decode("latin-1")
                attr       = _read_u8(f)
                f.read(3)                   # 3 padding bytes
                orig_size  = _read_u32(f)
                pack_size  = _read_u32(f)
                offset     = _read_u32(f)

                compressed = bool(attr & 0x40)

                # Build POSIX path: dir\file → dir/file, all lowercase
                if dir_name and dir_name not in (".", ""):
                    full = dir_name.replace("\\", "/") + "/" + fname
                else:
                    full = fname
                full = full.replace("\\", "/").lower()

                entries[full] = Dat1Entry(
                    filename    = full,
                    compressed  = compressed,
                    orig_size   = orig_size,
                    packed_size = pack_size,
                    offset      = offset,
                )

    return entries


def read_file(dat_path: str, entry: Dat1Entry) -> bytes:
    """Extract and (if needed) decompress a single file from a DAT1 archive."""
    with open(dat_path, "rb") as f:
        f.seek(entry.offset)
        data = f.read(entry.packed_size)

    if entry.compressed:
        data = _lzss_decompress(data, entry.orig_size)
        if len(data) != entry.orig_size:
            raise ValueError(
                f"LZSS decompress size mismatch for {entry.filename}: "
                f"got {len(data)}, expected {entry.orig_size}"
            )
    return data


def extract_all(dat_path: str, out_dir: str,
                verbose: bool = True) -> int:
    """
    Extract all files from a DAT1 archive into out_dir, preserving paths.

    Returns the number of files extracted.
    """
    entries = read_dat(dat_path)
    total   = len(entries)

    for i, (fname, entry) in enumerate(sorted(entries.items()), 1):
        out_path = os.path.join(out_dir, fname)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        if verbose:
            print(f"  [{i}/{total}] {fname}")

        try:
            data = read_file(dat_path, entry)
            with open(out_path, "wb") as f:
                f.write(data)
        except Exception as e:
            print(f"  WARNING: could not extract {fname}: {e}")

    return total
