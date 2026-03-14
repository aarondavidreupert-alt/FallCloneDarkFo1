"""
Fallout PRO (prototype object) parser — Python 3.9+ port of darkfo/proto.py
Original: Copyright 2014 darkf (Apache 2.0)

Parses Fallout 1/2 .PRO binary files into Python dicts suitable for JSON export.

Key Python 2 → 3 fixes:
  - ord(f.read(1)) → f.read(1)[0]
  - repr(f.read(3)) + ord(flagsExt[i]) → read bytes directly, index as flags_raw[i]
  - print statements → print() calls
  - FO1 global bool → fo1 parameter on read_pro() and read_critter()

Object type constants match Harold's originals exactly so that downstream code
(fomap.py, pro_to_json.py) can compare against them.
"""

import struct
from typing import IO


# ── Object/subtype constants ──────────────────────────────────────────────────

TYPE_ITEM     = 0
TYPE_CRITTER  = 1
TYPE_SCENERY  = 2
TYPE_WALL     = 3
TYPE_TILE     = 4
TYPE_MISC     = 5

SUBTYPE_ARMOR     = 0
SUBTYPE_CONTAINER = 1
SUBTYPE_DRUG      = 2
SUBTYPE_WEAPON    = 3
SUBTYPE_AMMO      = 4
SUBTYPE_MISC      = 5
SUBTYPE_KEY       = 6

SCENERY_DOOR           = 0
SCENERY_STAIRS         = 1
SCENERY_ELEVATOR       = 2
SCENERY_LADDER_BOTTOM  = 3
SCENERY_LADDER_TOP     = 4
SCENERY_GENERIC        = 5


# ── Low-level binary readers ──────────────────────────────────────────────────

def _r16(f: IO[bytes]) -> int:
    return struct.unpack("!h", f.read(2))[0]


def _r32(f: IO[bytes]) -> int:
    return struct.unpack("!l", f.read(4))[0]


# ── Critter sub-parsers ───────────────────────────────────────────────────────

def _read_critter_stats(f: IO[bytes]) -> dict:
    stats = {}
    for stat in (
        "STR", "PER", "END", "CHR", "INT", "AGI", "LUK", "HP", "AP",
        "AC", "Unarmed", "Melee", "Carry", "Sequence", "Healing Rate",
        "Critical Chance", "Better Criticals",
    ):
        stats[stat] = _r32(f)

    for stat in (
        "DT Normal", "DT Laser", "DT Fire", "DT Plasma", "DT Electrical",
        "DT EMP", "DT Explosive",
        "DR Normal", "DR Laser", "DR Fire", "DR Plasma", "DR Electrical",
        "DR EMP", "DR Explosive", "DR Radiation", "DR Poison",
    ):
        stats[stat] = _r32(f)

    return stats


def _read_critter_skills(f: IO[bytes]) -> dict:
    skills = {}
    for skill in (
        "Small Guns", "Big Guns", "Energy Weapons", "Unarmed",
        "Melee", "Throwing", "First Aid", "Doctor", "Sneak",
        "Lockpick", "Steal", "Traps", "Science", "Repair",
        "Speech", "Barter", "Gambling", "Outdoorsman",
    ):
        skills[skill] = _r32(f)
    return skills


def _read_drug_effect(f: IO[bytes]) -> dict:
    return {
        "duration": _r32(f),
        "amount0":  _r32(f),
        "amount1":  _r32(f),
        "amount2":  _r32(f),
    }


# ── Type-specific parsers ─────────────────────────────────────────────────────

def _read_item(f: IO[bytes]) -> dict:
    obj: dict = {}

    # Harold used repr(f.read(3)) to store these 3 flag bytes, then accessed
    # them with ord(flagsExt[i]).  In Python 3 that is buggy (repr gives the
    # b'...' string representation).  We read the 3 bytes directly instead.
    flags_raw    = f.read(3)           # 3 bytes: itemFlags, actionFlags, weaponFlags
    attack_mode  = f.read(1)[0]        # was ord(f.read(1))
    script_id    = _r32(f)
    sub_type     = _r32(f)
    material_id  = _r32(f)
    size         = _r32(f)
    weight       = _r32(f)
    cost         = _r32(f)
    inv_frm      = _r32(f)
    sound_id     = f.read(1)[0]        # was ord(f.read(1))

    obj["flagsExt"]    = list(flags_raw)   # [itemFlags, actionFlags, weaponFlags]
    obj["itemFlags"]   = flags_raw[0]
    obj["actionFlags"] = flags_raw[1]
    obj["weaponFlags"] = flags_raw[2]
    obj["attackMode"]  = attack_mode
    obj["scriptID"]    = script_id
    obj["subType"]     = sub_type
    obj["materialID"]  = material_id
    obj["size"]        = size
    obj["weight"]      = weight
    obj["cost"]        = cost
    obj["invFRM"]      = inv_frm
    obj["soundID"]     = sound_id

    if sub_type == SUBTYPE_WEAPON:
        obj["animCode"]  = _r32(f)
        obj["minDmg"]    = _r32(f)
        obj["maxDmg"]    = _r32(f)
        obj["dmgType"]   = _r32(f)
        obj["maxRange1"] = _r32(f)
        obj["maxRange2"] = _r32(f)
        obj["projPID"]   = _r32(f)
        obj["minST"]     = _r32(f)
        obj["APCost1"]   = _r32(f)
        obj["APCost2"]   = _r32(f)
        obj["critFail"]  = _r32(f)
        obj["perk"]      = _r32(f)
        obj["rounds"]    = _r32(f)
        obj["caliber"]   = _r32(f)
        obj["ammoPID"]   = _r32(f)
        obj["maxAmmo"]   = _r32(f)
        obj["soundID"]   = f.read(1)[0]

    elif sub_type == SUBTYPE_AMMO:
        obj["caliber"]      = _r32(f)
        obj["quantity"]     = _r32(f)
        obj["AC modifier"]  = _r32(f)
        obj["DR modifier"]  = _r32(f)
        obj["damMult"]      = _r32(f)
        obj["damDiv"]       = _r32(f)

    elif sub_type == SUBTYPE_ARMOR:
        obj["AC"] = _r32(f)
        stats = {}
        for stat in (
            "DR Normal", "DR Laser", "DR Fire",
            "DR Plasma", "DR Electrical", "DR EMP", "DR Explosive",
            "DT Normal", "DT Laser", "DT Fire", "DT Plasma", "DT Electrical",
            "DT EMP", "DT Explosive",
        ):
            stats[stat] = _r32(f)
        obj["stats"]     = stats
        obj["perk"]      = _r32(f)
        obj["maleFID"]   = _r32(f)
        obj["femaleFID"] = _r32(f)

    elif sub_type == SUBTYPE_DRUG:
        obj["stat0"]   = _r32(f)
        obj["stat1"]   = _r32(f)
        obj["stat2"]   = _r32(f)
        obj["amount0"] = _r32(f)
        obj["amount1"] = _r32(f)
        obj["amount2"] = _r32(f)
        obj["firstDelayed"]  = _read_drug_effect(f)
        obj["secondDelayed"] = _read_drug_effect(f)
        obj["addictionRate"]   = _r32(f)
        obj["addictionEffect"] = _r32(f)
        obj["addictionOnset"]  = _r32(f)

    return obj


def _read_critter(f: IO[bytes], fo1: bool = True) -> dict:
    obj: dict = {}

    obj["actionFlags"] = _r32(f)
    obj["scriptID"]    = _r32(f)
    obj["headFID"]     = _r32(f)
    obj["AI"]          = _r32(f)
    obj["team"]        = _r32(f)
    obj["flags"]       = _r32(f)

    obj["baseStats"]  = _read_critter_stats(f)
    obj["age"]        = _r32(f)
    obj["gender"]     = _r32(f)

    obj["bonusStats"] = _read_critter_stats(f)
    obj["bonusAge"]   = _r32(f)
    obj["bonusGender"] = _r32(f)

    obj["skills"]     = _read_critter_skills(f)
    obj["bodyType"]   = _r32(f)
    obj["XPValue"]    = _r32(f)
    obj["killType"]   = _r32(f)

    # Fallout 1 always omits damageType; FO2 robots/brahmin also omit it
    if fo1 or obj["killType"] in (5, 10):
        obj["damageType"] = None
    else:
        obj["damageType"] = _r32(f)

    return obj


def _read_scenery(f: IO[bytes]) -> dict:
    obj: dict = {}

    obj["wallLightTypeFlags"] = _r16(f)
    obj["actionFlags"]        = _r16(f)
    obj["scriptPID"]          = _r32(f)
    obj["subType"]            = _r32(f)
    obj["materialID"]         = _r32(f)
    obj["soundID"]            = f.read(1)[0]   # was ord(f.read(1))

    sub = obj["subType"]
    if sub == SCENERY_DOOR:
        obj["walkthroughFlag"] = _r32(f)
        f.read(4)  # 4-byte unknown
    elif sub == SCENERY_STAIRS:
        obj["destination"]    = _r32(f)
        obj["destinationMap"] = _r32(f)
    elif sub == SCENERY_ELEVATOR:
        obj["elevatorType"]  = _r32(f)
        obj["elevatorLevel"] = _r32(f)
    elif sub in (SCENERY_LADDER_BOTTOM, SCENERY_LADDER_TOP):
        obj["destination"] = _r32(f)
    elif sub == SCENERY_GENERIC:
        f.read(4)  # 4-byte unknown

    return obj


# ── Public entry point ────────────────────────────────────────────────────────

def read_pro(f: IO[bytes], fo1: bool = True) -> dict:
    """
    Parse a Fallout .PRO file from an open binary file object.

    Args:
        f:   Open binary file object positioned at the start of the PRO data.
        fo1: True for Fallout 1 (affects critter damageType field parsing).

    Returns a dict with keys:
        pid, textID, type, flags, lightRadius, lightIntensity,
        frmPID, frmType, extra (type-specific sub-dict)
    """
    obj: dict = {}

    object_type_and_id  = _r32(f)
    text_id             = _r32(f)
    frm_type_and_id     = _r32(f)
    light_radius        = _r32(f)
    light_intensity     = _r32(f)
    flags               = _r32(f)

    pid      = object_type_and_id & 0xffff
    obj_type = (object_type_and_id >> 24) & 0xff

    obj["pid"]            = pid
    obj["textID"]         = text_id
    obj["type"]           = obj_type
    obj["flags"]          = flags
    obj["lightRadius"]    = light_radius
    obj["lightIntensity"] = light_intensity

    frm_pid  = frm_type_and_id & 0xffff
    frm_type = (frm_type_and_id >> 24) & 0xff
    obj["frmPID"]  = frm_pid
    obj["frmType"] = frm_type

    if obj_type == TYPE_ITEM:
        obj["extra"] = _read_item(f)
    elif obj_type == TYPE_CRITTER:
        obj["extra"] = _read_critter(f, fo1=fo1)
    elif obj_type == TYPE_SCENERY:
        obj["extra"] = _read_scenery(f)
    else:
        # Walls, tiles, misc — no extra data parsed (same as Harold)
        pass

    return obj
