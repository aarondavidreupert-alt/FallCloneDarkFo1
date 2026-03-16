"""
Fallout MAP → JSON converter — Python 3.9+ port of darkfo/fomap.py
Original: Copyright 2015 darkf (Apache 2.0)

Supports Fallout 1 (version 19) and Fallout 2 (version 20) MAP files.
Targeting FO2 (version 20); FO1 support retained for completeness.

Bugs fixed vs. our previous Python 3 port:
  1. ENDIANNESS — all struct reads now use "!" (big-endian / network order),
     matching both Harold's reference and the Fallout binary format.
     The previous port incorrectly used "<" (little-endian) everywhere.
  2. id3 bitmask in _get_critter_art_path: 0x70000 → 0x70000
  3. map_pid sentinel in _parse_object: 0xFFFF → 0xFFFF
  4. Added missing id2==0x12 and id2==0x0d guard cases in critter art path

Output JSON structure is unchanged (header, levels[].tiles/spatials/objects,
startPosition, startElevation, startOrientation).
"""

import os
import struct
import json
from typing import Dict, Any, List, Optional, Tuple


# ── Module-level state (mirrors Harold's globals) ────

_FO1_MODE: bool = False

SCRIPT_TYPES = ["s_system", "s_spatial", "s_time", "s_item", "s_critter"]

_map_script_pids: List[Dict[int, str]] = [{} for _ in range(5)]


# ── Binary readers — BIG-ENDIAN ("!"), matching Harold's fomap.py ────

def _r16(f)  -> int: return struct.unpack("!h", f.read(2))[0]   # signed
def _ru16(f) -> int: return struct.unpack("!H", f.read(2))[0]   # unsigned
def _r32(f)  -> int: return struct.unpack("!l", f.read(4))[0]   # signed
def _ru32(f) -> int: return struct.unpack("!L", f.read(4))[0]   # unsigned


# ── Helpers ────

def _strip_ext(path: str) -> str:
    return os.path.splitext(path)[0]

def _pid_type(pid: int) -> int:
    return (pid >> 24) & 0xFF

def _num_levels(elevation_flags: int) -> int:
    if elevation_flags & 8:
        return 1 if (elevation_flags & 4) else 2
    return 3

def _from_tile_num(tile_num: int) -> Dict[str, int]:
    return {"x": tile_num % 200, "y": tile_num // 200}

def _blank_tile_map() -> List[List[int]]:
    return [[0] * 100 for _ in range(100)]


# ── Tile parsing ────

def _parse_tiles(f, num_levels: int) -> Tuple[List, List]:
    """
    Read interspersed floor/roof tile indices (100×100 per level).
    X-axis is reversed to match tileToScreen() expectations — same as Harold.
    """
    floor = [_blank_tile_map() for _ in range(num_levels)]
    roof  = [_blank_tile_map() for _ in range(num_levels)]

    for level in range(num_levels):
        for i in range(10000):
            x = i % 100
            y = i // 100
            roof[level][y][99 - x]  = _ru16(f)
            floor[level][y][99 - x] = _ru16(f)

    return floor, roof


# ── Script / spatial parsing ────

def _parse_map_scripts(f, script_lst: List[str]) -> Dict[str, Any]:
    global _map_script_pids
    _map_script_pids = [{} for _ in range(5)]

    total    = 0
    spatials: List[Dict] = []

    for script_type in range(5):
        count  = _r32(f)
        total += count

        if count > 0:
            loop  = count + (16 - count % 16) if count % 16 else count
            check = 0

            for i in range(loop):
                pid  = _ru32(f)
                pt   = _pid_type(pid)
                _ru32(f)  # unk1

                tile_num      = None
                spatial_range = None

                if pt in (1, 2):
                    tile_num = _ru32(f)
                if pt == 1:
                    spatial_range = _ru32(f)

                _ru32(f)         # unk2
                script_id = _ru32(f)
                _ru32(f)         # unk3
                f.read(4 * 11)  # unknown block

                pid_id = pid & 0xFFFF

                if i < count:
                    if (pt == 1 and spatial_range is not None
                            and spatial_range <= 50 and script_id < len(script_lst)):
                        script_name = _strip_ext(script_lst[script_id].split()[0])
                        spatials.append({
                            "tileNum":   tile_num & 0xFFFF,
                            "elevation": ((tile_num >> 28) & 0xF) >> 1,
                            "range":     spatial_range,
                            "scriptID":  script_id,
                            "script":    script_name,
                        })

                    if 0 < script_id < len(script_lst):
                        name = _strip_ext(script_lst[script_id]).split()[0]
                        _map_script_pids[script_type][pid_id] = name

                if (i % 16) == 15:
                    check += _ru32(f)
                    _r32(f)  # unknown

            if check != count:
                raise ValueError(
                    f"Script check failed (got {check}, expected {count})"
                )

    return {"count": total, "spatials": spatials}


# ── Object parsing ────

def _parse_item_obj(f, frm_pid: int, proto_pid: int,
                    items_lst: List[str]) -> Dict:
    item = {
        "type":    "item",
        "artPath": "art/items/" + _strip_ext(items_lst[frm_pid & 0xFFFF]),
    }
    subtype = _ru32(f)

    if   subtype == 4: item["subtype"] = "ammo";      item["ammoCount"] = _ru32(f)
    elif subtype == 3: item["subtype"] = "weapon";     f.read(8)
    elif subtype == 1: item["subtype"] = "container"
    elif subtype == 0: item["subtype"] = "armor"
    elif subtype == 2: item["subtype"] = "drug"
    elif subtype == 5: item["subtype"] = "misc";       f.read(4)
    elif subtype == 6: item["subtype"] = "key";        f.read(4)

    return item


def _get_critter_art_path(frm_pid: int, critter_lst: List[str]) -> str:
    """
    Compute the art path for a critter FRM PID.
    Ported exactly from Harold's fomap.getCritterArtPath().

    Bugs fixed vs previous port:
      - id3 mask was 0x70000 (wrong); corrected to 0x70000
      - Added id2==0x12 and id2==0x0d guard cases (omitted before)
    """
    idx = frm_pid & 0x0000FFF
    id1 = (frm_pid & 0x0000F000) >> 12
    id2 = (frm_pid & 0x00FF0000) >> 16
    id3 = (frm_pid & 0x70000000) >> 28

    if id2 in (0x1B, 0x1D, 0x1E, 0x37, 0x39, 0x3A, 0x21, 0x40):
        raise ValueError("reindex")

    path = "art/critters/" + critter_lst[idx].split(",")[0].upper()

    if id1 >= 0x0B:
        raise ValueError("id1 >= 0x0b")

    if   0x26 <= id2 <= 0x2F:  raise ValueError("0x26-0x2f")
    elif id2 == 0x24:           path += "ch"
    elif id2 == 0x25:           path += "cj"
    elif id2 >= 0x30:           path += 'r' + chr(id2 + 0x31)
    elif id2 >= 0x14:           raise ValueError("id2 >= 0x14")
    elif id2 == 0x12:           raise ValueError("id2 == 0x12")   # guard — was missing
    elif id2 == 0x0D:           raise ValueError("id2 == 0x0d")   # guard — was missing
    else:
        if id2 <= 1 and id1 > 0:
            path += chr(id1 + ord('c'))
        else:
            path += 'A'
        path += chr(id2 + ord('a'))

    path += ".fr" + ("m" if not id3 else str(id3 - 1))
    return path


def _parse_object(f, lst: Dict[str, List[str]]) -> Dict[str, Any]:
    f.read(4)                    # separator / unknown
    position      = _r32(f)       # signed: -1 means no tile position
    f.read(4 * 2)                 # 2 unknown uint32s
    _frame_num    = _ru32(f)
    orientation   = _ru32(f)
    frm_pid       = _ru32(f)
    flags         = _ru32(f)
    _elevation    = _ru32(f)
    proto_pid     = _ru32(f)
    obj_type      = (proto_pid >> 24) & 0xFF
    f.read(4)                    # unknown
    light_radius  = _ru32(f)
    light_intens  = _ru32(f)
    f.read(4)                    # unknown
    map_pid       = _ru32(f)
    script_id     = _r32(f)       # signed (-1 = no script)
    num_inv       = _ru32(f)
    f.read(4 * 3)                 # unknown

    extra: Dict[str, Any] = {}
    art: Optional[str]    = None
    named_type: str       = ""

    if obj_type == 0:   # item
        extra = _parse_item_obj(f, frm_pid, proto_pid, lst["items"])
        named_type = "item"
        art = extra.pop("artPath")
        extra.pop("type", None)

    elif obj_type == 3:  # wall
        named_type = "wall"
        art = "art/walls/" + _strip_ext(lst["walls"][frm_pid & 0xFFFF])

    elif obj_type == 1:  # critter
        named_type = "critter"
        try:
            art = _strip_ext(_get_critter_art_path(frm_pid, lst["critters"]))
        except ValueError:
            art = "art/critters/unknown"
        f.read(4 * 4)
        extra["AInum"]   = _r32(f)
        extra["groupID"] = _ru32(f)
        f.read(4)
        extra["hp"]      = _ru32(f)
        f.read(4 * 2)

    elif obj_type == 2:  # scenery
        named_type = "scenery"
        art = "art/scenery/" + _strip_ext(lst["scenery"][frm_pid & 0xFFFF])
        subtype = _ru32(f)
        if subtype == 0:     # door
            extra["subtype"] = "door"
            f.read(4)
        elif subtype == 2:   # elevator
            extra["subtype"] = "elevator"
            extra["type"]    = _ru32(f)
            extra["level"]   = _ru32(f)
        elif subtype == 1:   # stairs
            extra["subtype"]        = "stairs"
            extra["destination"]    = _r32(f)
            extra["destinationMap"] = _r32(f)
        elif subtype in (3, 4):  # ladder
            extra["subtype"] = "ladder"
            if not _FO1_MODE:    # FO2
                extra["unknown1"]    = _r32(f)
                extra["destination"] = _r32(f)
            else:                # FO1
                extra["destination"] = _r32(f)
        else:
            extra["subtype"] = "generic"

    elif obj_type == 5:  # misc (exit grids etc.)
        named_type = "misc"
        art = "art/misc/" + _strip_ext(lst["misc"][frm_pid & 0xFFFF])
        if (proto_pid & 0xFFFF) not in (1, 12):
            extra["exitMapID"]           = _r32(f)
            extra["startingPosition"]    = _r32(f)
            extra["startingElevation"]   = _r32(f)
            extra["startingOrientation"] = _ru32(f)

    inventory: List[Dict] = []
    for _ in range(num_inv):
        amount  = _ru32(f)
        inv_obj = _parse_object(f, lst)
        inv_obj["amount"] = amount
        inventory.append(inv_obj)

    obj: Dict[str, Any] = {
        "type":           named_type,
        "pid":            proto_pid,
        "pidID":          proto_pid & 0xFFFF,
        "frmPID":         frm_pid,
        "flags":          flags,
        "position":       _from_tile_num(position),
        "orientation":    orientation,
        "lightRadius":    light_radius,
        "lightIntensity": light_intens,
        "inventory":      inventory,
    }
    if art:
        obj["art"] = art.lower()
    if extra:
        obj["extra"] = extra
        if "subtype" in extra:
            obj["subtype"] = extra["subtype"]

    if script_id != -1 and script_id < len(lst["scripts"]):
        obj["script"] = _strip_ext(lst["scripts"][script_id].split()[0])
    elif script_id == -1 and map_pid != 0xFFFF:   # was 0xFFFF — wrong sentinel
        s_type = (map_pid >> 24) & 0xFF
        s_pid  = map_pid & 0xFFFF
        if s_pid in _map_script_pids[s_type]:
            obj["script"] = _map_script_pids[s_type][s_pid]

    return obj


def _parse_level_objects(f, lst: Dict[str, List[str]]) -> List[Dict]:
    count = _ru32(f)
    return [_parse_object(f, lst) for _ in range(count)]


def _parse_map_objects(f, num_levels: int,
                    lst: Dict[str, List[str]]) -> List[List[Dict]]:
    _ru32(f)  # total object count across all levels (not needed per-level)
    return [_parse_level_objects(f, lst) for _ in range(num_levels)]


# ── LST file reader ────

def _read_lst(data_dir: str, rel_path: str) -> List[str]:
    """Read a Fallout .lst index file, returning a list of stripped strings."""
    with open(os.path.join(data_dir, rel_path), "rb") as f:
        return [line.decode("latin-1").rstrip() for line in f]


# ── Top-level MAP parser ────

def parse_map(f, lst: Dict[str, List[str]]) -> Dict[str, Any]:
    global _FO1_MODE

    version = _ru32(f)
    if version == 19:
        _FO1_MODE = True
        named_version = "FO1"
    elif version == 20:
        _FO1_MODE = False
        named_version = "FO2"
    else:
        raise ValueError(f"Not a FO1 or FO2 map (version={version})")

    raw_name        = f.read(16)
    map_name        = raw_name.split(b'\x00')[0].decode("latin-1")
    player_pos      = _r32(f)
    player_elev     = _r32(f)
    player_orient   = _r32(f)
    num_local_vars  = _r32(f)
    _map_script_id  = _r32(f)
    elev_flags      = _r32(f)
    num_levels      = _num_levels(elev_flags)
    _r32(f)                    # unk1
    num_global_vars = _r32(f)
    map_id          = _r32(f)
    _ru32(f)                    # time
    f.read(4 * 44)                  # unknown padding

    [_r32(f) for _ in range(num_global_vars)]
    [_r32(f) for _ in range(num_local_vars)]

    floor_tiles, roof_tiles = _parse_tiles(f, num_levels)
    scripts = _parse_map_scripts(f, lst["scripts"])
    objects = _parse_map_objects(f, num_levels, lst)

    def transform_tile(idx: int) -> str:
        entry = lst["tiles"][idx] if idx < len(lst["tiles"]) else "grid000.frm"
        return _strip_ext(entry.rstrip()).lower()

    def transform_tile_map(tile_map: List[List[int]]) -> List[List[str]]:
        return [[transform_tile(idx) for idx in row] for row in tile_map]

    levels = []
    for level in range(num_levels):
        levels.append({
            "tiles": {
                "floor": transform_tile_map(floor_tiles[level]),
                "roof":  transform_tile_map(roof_tiles[level]),
            },
            "spatials": [s for s in scripts["spatials"] if s["elevation"] == level],
            "objects":  objects[level],
        })

    return {
        "version":          named_version,
        "mapID":            map_id,
        "name":             map_name,
        "numLevels":        num_levels,
        "levels":           levels,
        "startPosition":    _from_tile_num(player_pos),
        "startElevation":   player_elev,
        "startOrientation": player_orient,
    }


def get_image_list(map_data: Dict[str, Any]) -> List[str]:
    images = set()
    for level in map_data["levels"]:
        for tilemap in level["tiles"].values():
            for row in tilemap:
                for tile in row:
                    if tile != "grid000":
                        images.add("art/tiles/" + tile)
    return sorted(images)


# ── Public API ────

def export_map(data_dir: str, map_file: str, out_file: str,
               verbose: bool = False) -> None:
    """
    Convert a single .MAP file to JSON.

    data_dir  — root of extracted Fallout data (art/, maps/, proto/, scripts/)
    map_file  — path to the .MAP file
    out_file  — destination .json path
    """
    lst = {
        "tiles":    _read_lst(data_dir, "art/tiles/tiles.lst"),
        "scenery":  _read_lst(data_dir, "art/scenery/scenery.lst"),
        "items":    _read_lst(data_dir, "art/items/items.lst"),
        "misc":     _read_lst(data_dir, "art/misc/misc.lst"),
        "walls":         _read_lst(data_dir, "art/walls/walls.lst"),
        "critters":      _read_lst(data_dir, "art/critters/critters.lst"),
        "scripts":       _read_lst(data_dir, "scripts/scripts.lst"),
    }

    with open(map_file, "rb") as fin:
        map_data = parse_map(fin, lst)

    os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as fout:
        json.dump(map_data, fout)
    if verbose:
        print(f"  wrote {out_file}")

    images_file = _strip_ext(out_file) + ".images.json"
    with open(images_file, "w", encoding="utf-8") as fimg:
        json.dump(get_image_list(map_data), fimg)
    if verbose:
        print(f"  wrote {images_file}")