"""
Fallout FRM/FR[0-5] parser — Python 3 port of darkfo/frmpixels.py
Original: Copyright 2014 darkf (Apache 2.0)

Parses Fallout 1/2 .FRM sprite files and multi-directional .FR0–.FR5 sets,
rendering them as horizontally-stitched sprite sheets (one PNG per art key).

Key format facts:
  - Each FRM stores 1–6 directions, each with N frames.
  - All frames land on a single-row sprite sheet: totalFrames × maxH pixels.
  - Palette index 0 is transparent (saved via PNG transparency=0).
  - Multi-directional critters use separate .FR0–.FR5 files (one per direction).
"""

import struct
from typing import List, Dict, Any, Optional
import numpy as np
from PIL import Image

from .pal import Palette, flatten_palette


# ── Low-level readers ──────────────────────────────────────────────────────

def _r16(data: bytes, i: int) -> int:
    return struct.unpack_from("!h", data, i)[0]

def _r32(data: bytes, i: int) -> int:
    return struct.unpack_from("!l", data, i)[0]

def _ru16(data: bytes, i: int) -> int:
    return struct.unpack_from("!H", data, i)[0]

def _ru32(data: bytes, i: int) -> int:
    return struct.unpack_from("!L", data, i)[0]


# ── FRM info parsing ────────────────────────────────────────────────────────

def _read_frm_info(data: bytes, export_pixels: bool = True) -> Dict[str, Any]:
    """
    Parse FRM binary data.  Mirrors darkfo frmpixels.readFRMInfo() exactly,
    adapted to Python 3 (bytes slicing gives ints, no ord() calls needed).
    """
    pos = 0
    _version   = struct.unpack_from("!l", data, pos)[0]; pos += 4
    fps        = struct.unpack_from("!h", data, pos)[0]; pos += 2
    _actionFrm = struct.unpack_from("!h", data, pos)[0]; pos += 2
    num_frames = struct.unpack_from("!h", data, pos)[0]; pos += 2

    d_offset_x = [struct.unpack_from("!h", data, pos + 2*i)[0] for i in range(6)]; pos += 12
    d_offset_y = [struct.unpack_from("!h", data, pos + 2*i)[0] for i in range(6)]; pos += 12
    dir_ptrs   = [struct.unpack_from("!l", data, pos + 4*i)[0] for i in range(6)]; pos += 24
    frames_buf_size = struct.unpack_from("!l", data, pos)[0]; pos += 4

    frames_data = data[pos: pos + frames_buf_size]

    n_dir_total = 1 + sum(1 for x in dir_ptrs if x != 0)

    frame_pixels: List[List[np.ndarray]] = [[] for _ in range(n_dir_total)]
    frame_offsets: List[List[Dict]] = [[] for _ in range(n_dir_total)]

    for nd in range(n_dir_total):
        ptr = dir_ptrs[nd]
        for _ in range(num_frames):
            w    = _ru16(frames_data, ptr + 0)
            h    = _ru16(frames_data, ptr + 2)
            size = _ru32(frames_data, ptr + 4)
            ox   = _r16(frames_data,  ptr + 8)
            oy   = _r16(frames_data,  ptr + 10)

            frame_offsets[nd].append({"x": ox, "y": oy, "w": w, "h": h})

            if export_pixels:
                raw = frames_data[ptr + 12: ptr + 12 + size]
                # Python 3: np.frombuffer on bytes → read-only, so .copy()
                frame_pixels[nd].append(
                    np.frombuffer(raw, dtype=np.uint8).copy()
                )
            ptr += 12 + size

    return {
        "numFrames":       num_frames,
        "fps":             fps,
        "numDirections":   n_dir_total,
        "totalFrames":     num_frames * n_dir_total,
        "directionOffsets": [{"x": x, "y": y}
                              for x, y in zip(d_offset_x, d_offset_y)],
        "frameOffsets":    frame_offsets,
        "framePixels":     frame_pixels,
    }


# ── Single-FRM export ───────────────────────────────────────────────────────

def export_frm(frm_path: str, out_path: str, palette: Palette,
               export_image: bool = True) -> Dict[str, Any]:
    """
    Convert one .FRM file to a PNG sprite sheet.
    Returns the imageMap metadata dict for this art key.

    Adapted from darkfo frmpixels.exportFRM() — logic identical, Python 3 fixes:
      - bytes slicing instead of ord() iteration
      - np.frombuffer() instead of np.array([ord(b) for b in ...])
    """
    with open(frm_path, "rb") as f:
        raw = f.read()

    info = _read_frm_info(raw, export_image)
    frame_pixels  = info["framePixels"]
    frame_offsets = info["frameOffsets"]

    max_w = max(max(fo["w"] for fo in offs) for offs in frame_offsets)
    max_h = max(max(fo["h"] for fo in offs) for offs in frame_offsets)
    total_w = max_w * info["totalFrames"]

    info["frameWidth"]  = max_w
    info["frameHeight"] = max_h

    if export_image:
        flat_pal = flatten_palette(palette)
        sheet = Image.new("P", (total_w, max_h))
        sheet.putpalette(flat_pal)
        cur_x = 0

        for nd in range(info["numDirections"]):
            for fn, frame in enumerate(frame_pixels[nd]):
                offs = frame_offsets[nd][fn]
                w, h = offs["w"], offs["h"]
                pixels = np.reshape(frame, (h, w))
                img = Image.fromarray(pixels, "P")
                sheet.paste(img, (cur_x, 0))
                cur_x += max_w

        sheet.save(out_path, transparency=0)

    # Build imageMap metadata (cumulative sx/ox/oy — same as DarkFO)
    sx = 0
    for direction in info["frameOffsets"]:
        ox = oy = 0
        for frame in direction:
            ox += frame["x"]
            oy += frame["y"]
            frame["sx"] = sx
            frame["ox"] = ox
            frame["oy"] = oy
            sx += max_w

    del info["framePixels"]
    return info


# ── Multi-FRM (.FR0–.FR5) export ────────────────────────────────────────────

def export_frms(frm_files: List[str], out_path: str, palette: Palette,
                export_image: bool = True) -> Dict[str, Any]:
    """
    Combine multiple .FR0–.FR5 directional files into one sprite sheet.
    Adapted from darkfo frmpixels.exportFRMs() — Python 3 only.
    """
    infos = []
    for fp in frm_files:
        with open(fp, "rb") as f:
            infos.append(_read_frm_info(f.read(), export_image))

    max_w = max(max(max(fo["w"] for fo in offs) for offs in info["frameOffsets"])
                for info in infos)
    max_h = max(max(max(fo["h"] for fo in offs) for offs in info["frameOffsets"])
                for info in infos)
    total_frames = sum(info["totalFrames"] for info in infos)
    total_w = max_w * total_frames

    _fps        = next((i["fps"] for i in infos if i["fps"] != 0), 10)
    _num_frames = infos[0]["numFrames"]

    for info in infos:
        if info["numFrames"] != _num_frames:
            raise ValueError("frame count mismatch across directional FRMs")
        if info["fps"] not in (0, _fps):
            raise ValueError(f"FPS mismatch: {info['fps']} vs {_fps}")
        if len(info["frameOffsets"]) != 1:
            raise ValueError("directional FRM has more than one direction")

    flat_pal = flatten_palette(palette)

    if export_image:
        sheet = Image.new("P", (total_w, max_h))
        sheet.putpalette(flat_pal)

    cur_x = 0
    sx = 0

    for info in infos:
        fp_list   = info["framePixels"]
        fo_list   = info["frameOffsets"]

        for nd in range(info["numDirections"]):
            for fn, frame in enumerate(fp_list[nd]):
                offs = fo_list[nd][fn]
                w, h = offs["w"], offs["h"]
                if export_image:
                    pixels = np.reshape(frame, (h, w))
                    img = Image.fromarray(pixels, "P")
                    sheet.paste(img, (cur_x, 0))
                cur_x += max_w

        # Build sx/ox/oy metadata
        for direction in fo_list:
            ox = oy = 0
            for frame in direction:
                ox += frame["x"]
                oy += frame["y"]
                frame["sx"] = sx
                frame["ox"] = ox
                frame["oy"] = oy
                sx += max_w

        del info["framePixels"]

    if export_image:
        sheet.save(out_path, transparency=0)

    d_offsets = [[] for _ in range(6)]
    for i, info in enumerate(infos):
        d_offsets[i] = info["directionOffsets"][0]

    flat_offsets = [fo for info in infos for fo in info["frameOffsets"]]

    return {
        "numFrames":        _num_frames,
        "totalFrames":      total_frames,
        "frameWidth":       max_w,
        "frameHeight":      max_h,
        "fps":              _fps,
        "numDirections":    len(frm_files),
        "directionOffsets": d_offsets,
        "frameOffsets":     flat_offsets,
    }
