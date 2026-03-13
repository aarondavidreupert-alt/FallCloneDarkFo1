# Asset Pipeline — scripts/

Converts Fallout 1 raw game files into web-friendly formats for FallClone.

All scripts are **Python 3.8+** and adapted from DarkFO's Python 2 tools
(see `darkfo/` for originals). The big additions are:

- **DAT1 reader** (`lib/dat1.py`) — Fallout 1 archive format (DarkFO only had DAT2 for FO2)
- **Parallel conversion** via `concurrent.futures` (more robust than `multiprocessing.Pool` on Python 3)
- **Unified `convert_all.py`** orchestrator with per-step skip flags

---

## Quick start

```bash
# 1. Install Python dependencies
pip install Pillow numpy

# 2. Run the full pipeline (replace path with your Fallout 1 install)
cd /path/to/FallCloneDarkFo1
python scripts/convert_all.py "C:/GOG Games/Fallout"
```

That's it. Output goes to `public/assets/`.

---

## Where to put Fallout 1 files

**Option A — Point at your install directory (recommended)**

If you have Fallout 1 installed (GOG, Steam, or original CD), just point
`convert_all.py` at the installation directory. It will find `MASTER.DAT`
and `CRITTER.DAT` automatically and extract them.

```
C:/GOG Games/Fallout/          ← this is your FALLOUT_DIR
  MASTER.DAT
  CRITTER.DAT
  FALLOUT.EXE
  ...
```

**Option B — Pre-extracted data directory**

If you already have the files extracted (e.g. from a previous setup), use
`--skip-extract` and point `--data-dir` at the extracted folder:

```
fallout/data/                  ← this is your DATA_DIR
  color.pal
  art/
    tiles/    *.frm
    critters/ *.frm  *.fr0–.fr5
    items/    *.frm
    scenery/  *.frm
    walls/    *.frm
    misc/     *.frm
    intrface/ *.frm
    inven/    *.frm
    skilldex/ *.frm
    backgrnd/ *.frm
  maps/       *.map
  proto/
    items/    *.pro
    scenery/  *.pro
    walls/    *.pro
    misc/     *.pro
    critters/ *.pro
  sound/
    sfx/      *.acm
    music/    *.acm
  scripts/    scripts.lst
```

---

## Output structure

Everything is written to `public/assets/` (committed to git, real assets are gitignored):

```
public/assets/
  art/
    tiles/        *.png   (80×36 isometric floor tiles)
    critters/     *.png   (sprite sheets)
    items/        *.png
    scenery/      *.png
    walls/        *.png
    misc/         *.png
    intrface/     *.png
    inven/        *.png
    imageMap.json          (frame metadata consumed by IsoRenderer)
  maps/
    v13ent.json            (Vault 13 entrance — used by Phase 1)
    *.json                 (all other maps)
    *.images.json          (per-map image dependency lists)
  sound/
    sfx/          *.mp3
    music/        *.mp3
  data/
    color.json             (256-entry palette, for shaders / debug)
```

> **Note:** Raw Fallout files (`.frm`, `.map`, `.acm`, `.pal`, `.pro`) are
> **never committed** — they stay local. Only the converted output goes to git.

---

## Individual scripts

### `convert_all.py` — master orchestrator

```bash
python scripts/convert_all.py FALLOUT_DIR [options]

Options:
  --data-dir DIR    Where to extract / find raw data  [FALLOUT_DIR/data]
  --out-dir DIR     Web output root                   [public/assets]
  --jobs N          Parallel workers                  [4]
  --skip-extract    Skip DAT extraction
  --skip-images     Skip FRM → PNG
  --skip-maps       Skip MAP → JSON
  --skip-audio      Skip ACM → MP3
  --update          Incremental: skip already-converted art
  --fo2             Input is Fallout 2 (DAT2 format)
```

### `extract_dat.py` — DAT archive extractor

Supports **Fallout 1 DAT1** (LZSS-compressed) and **Fallout 2 DAT2** (zlib).
Format is auto-detected; use `--fo2` to force DAT2.

```bash
# Extract all DATs from an install
python scripts/extract_dat.py "C:/Games/Fallout" fallout/data/

# Extract a single DAT
python scripts/extract_dat.py "C:/Games/Fallout" fallout/data/ --dat MASTER.DAT

# Fallout 2
python scripts/extract_dat.py "C:/Games/Fallout2" fallout2/data/ --fo2
```

### `frm_to_png.py` — FRM/FR[0-5] → PNG

Converts all art subdirectories in parallel. FRM files become horizontally-stitched
sprite sheets (one row, all frames left-to-right). Writes `imageMap.json` with frame
metadata (width, height, per-direction offsets) used by `IsoRenderer.ts`.

```bash
python scripts/frm_to_png.py DATA_DIR public/assets/art/ [--jobs 4] [--update]
```

Palette index **0 is transparent** (saved as PNG `transparency=0`).

### `map_to_json.py` — MAP → JSON

Produces the DarkFO `SerializedMap` format consumed directly by `MapLoader.ts`.
Supports Fallout 1 (version 19) and Fallout 2 (version 20) maps.

```bash
# Single map
python scripts/map_to_json.py DATA_DIR DATA_DIR/maps/v13ent.map public/assets/maps/

# Entire maps/ directory
python scripts/map_to_json.py DATA_DIR DATA_DIR/maps/ public/assets/maps/ --jobs 4
```

Each `.json` is accompanied by a `.images.json` listing all art keys the map needs.

### `pal_to_json.py` — PAL → JSON

```bash
python scripts/pal_to_json.py DATA_DIR/color.pal [public/assets/data/color.json]
```

### `acm_to_mp3.py` — ACM → MP3

Requires **ffmpeg** on PATH (preferred) or **acm2wav** + ffmpeg (fallback).

```bash
# Install ffmpeg: https://ffmpeg.org/download.html
# Install acm2wav: search nma-fallout.com tools archive

python scripts/acm_to_mp3.py DATA_DIR public/assets/sound/ [--jobs 4] [--quality 4]
```

If neither tool is found the script prints instructions and exits gracefully.

---

## Dependencies

| Package | Install | Required for |
|---------|---------|-------------|
| `Pillow` | `pip install Pillow` | FRM → PNG |
| `numpy`  | `pip install numpy`  | FRM → PNG |
| `ffmpeg` | https://ffmpeg.org/download.html | ACM → MP3 |
| `acm2wav`| NMA tools archive (optional) | ACM → MP3 fallback |

Python 3.8 or newer is required. No other packages needed.

---

## Library modules (`lib/`)

| Module | Source | Description |
|--------|--------|-------------|
| `lib/pal.py`   | darkfo/pal.py (Python 3) | PAL parser |
| `lib/frm.py`   | darkfo/frmpixels.py (Python 3) | FRM/FR[0-5] parser |
| `lib/fomap.py` | darkfo/fomap.py (Python 3) | MAP parser (FO1+FO2) |
| `lib/dat1.py`  | **NEW** (not in DarkFO) | Fallout 1 DAT1 + LZSS |
| `lib/dat2.py`  | darkfo/dat2.py (Python 3) | Fallout 2 DAT2 + zlib |

---

## Troubleshooting

**`color.pal not found`**
→ Your DAT extraction might not have completed. Run `extract_dat.py` first,
  or check that `DATA_DIR/color.pal` exists.

**`FRM → PNG: ERROR: ... numpy`**
→ `pip install numpy`

**`ACM → MP3: FAIL`**
→ `ffmpeg` may not include the Fallout ACM codec on your platform.
  Install `acm2wav` as a fallback: the script will use it automatically.

**`MAP: script check failed`**
→ This is a known edge case in certain Fallout 1 maps. The map JSON is still
  written (minus spatial scripts for that block). File a bug with the map name.

**Decompressed size mismatch (DAT1)**
→ Rare LZSS edge case. The file may be partially extractable. Run with
  `--verbose` to see which file caused it.
