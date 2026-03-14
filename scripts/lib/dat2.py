"""
Fallout 2 DAT2 archive reader — Python 3 port of darkfo/dat2.py
Original: Copyright 2015 darkf (Apache 2.0)

Python 3 changes vs Harold's original:
  - iteritems() → items()
  - ord(f.read(1)) → f.read(1)[0]
  - filename encoding handled via .decode('ascii', errors='replace')
  - read_dat(path) takes a path string instead of a file object
  - read_file(dat_path, entry) takes a path + entry instead of open file

Harold-compatible aliases provided:
  - read_file_obj(f, entry)  → read from an already-open file object
  - dump_files(dat_path, out_dir, verbose) → alias for extract_all()
"""

import os
import struct
import zlib
import collections
from typing import Dict


_SEEK_END = 2

Dat2Entry = collections.namedtuple(
    "Dat2Entry", "filename compressed unpacked_size packed_size offset"
)


def _r32(f) -> int:
    return struct.unpack("<l", f.read(4))[0]


def read_dat(path: str) -> Dict[str, Dat2Entry]:
    """
    Parse a Fallout 2 .DAT archive and return a dict mapping
    lowercase filename → Dat2Entry.
    """
    entries: Dict[str, Dat2Entry] = {}

    with open(path, "rb") as f:
        f.seek(-8, _SEEK_END)
        dir_tree_size = _r32(f)
        archive_size  = _r32(f)
        data_block_size = archive_size - dir_tree_size - 8

        f.seek(data_block_size)
        num_files = _r32(f)

        for _ in range(num_files):
            fname_size   = _r32(f)
            filename     = f.read(fname_size).decode("ascii", errors="replace")
            compressed   = bool(f.read(1)[0])   # Python 3: bytes[0] is int
            unpacked     = _r32(f)
            packed       = _r32(f)
            offset       = _r32(f)

            filename = filename.lower().replace("\\", "/")
            entries[filename] = Dat2Entry(filename, compressed, unpacked, packed, offset)

    return entries


def read_file(dat_path: str, entry: Dat2Entry) -> bytes:
    """Extract a single file from a DAT2 archive, decompressing if needed."""
    with open(dat_path, "rb") as f:
        f.seek(entry.offset)
        data = f.read(entry.packed_size)

    if entry.compressed:
        data = zlib.decompress(data, 15, entry.unpacked_size)
        if len(data) != entry.unpacked_size:
            raise ValueError(
                f"Zlib decompress size mismatch for {entry.filename}"
            )
    return data


def extract_all(dat_path: str, out_dir: str, verbose: bool = True) -> int:
    """Extract all files from a DAT2 archive into out_dir."""
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


# ── Harold-compatible API ─────────────────────────────────────────────────────

def read_file_obj(f: "IO[bytes]", entry: Dat2Entry, check_size: bool = True) -> bytes:
    """
    Extract a single file from an already-open DAT2 file object.
    Mirrors Harold's readFile(f, fileEntry, checkSize=True).
    """
    f.seek(entry.offset)
    data = f.read(entry.packed_size)

    if entry.compressed:
        data = zlib.decompress(data, 15, entry.unpacked_size)
        if check_size and len(data) != entry.unpacked_size:
            raise ValueError(
                f"Zlib decompress size mismatch for {entry.filename}: "
                f"got {len(data)}, expected {entry.unpacked_size}"
            )
    return data


def dump_files(dat_path: str, out_dir: str, verbose: bool = True) -> int:
    """Alias for extract_all() — matches Harold's dumpFiles() name."""
    return extract_all(dat_path, out_dir, verbose=verbose)
