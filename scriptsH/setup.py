"""
Copyright 2015-2017 darkf

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# Setup script to import Fallout 2 data for DarkFO

from __future__ import print_function
import sys, os, glob, json, traceback

# Resolve project root (one level up from skriptsH/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ASSETS_DIR = os.path.join(PROJECT_ROOT, "public", "assets")

# Add skriptsH/ to path so local modules are importable
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import dat2
import parseCritTable
import parseElevatorTable
import exportImagesPar
import exportPRO
import fomap

def error(msg):
    print("ERROR:", msg)
    sys.exit(1)

def warn(msg):
    print("WARNING:", msg)

def info(msg):
    print(msg)

# global paths/flags
SRC_DIR = None
NO_EXTRACT_DAT = False
NO_EXPORT_IMAGES = False
EXE_PATH = None

def assets(path):
    """Helper to build a path under public/assets/"""
    return os.path.join(ASSETS_DIR, path)

def setup_check():
    global EXE_PATH

    print("Checking installation directory (%s)..." % SRC_DIR)

    def install_file_exists(path):
        return os.path.exists(os.path.join(SRC_DIR, path))

    if not os.path.exists(SRC_DIR):
        error("Installation directory (%s) does not exist." % SRC_DIR)
    if not (install_file_exists("master.dat") and install_file_exists("critter.dat")):
        error("Installation directory does not contain master.dat or critter.dat.")
    if not install_file_exists("fallout2.exe"):
        warn("Installation directory does not contain fallout2.exe. Some features may not be available.")
    else:
        EXE_PATH = os.path.join(SRC_DIR, "fallout2.exe")

    # Ensure public/assets exists
    os.makedirs(ASSETS_DIR, exist_ok=True)

    return True

def parse_crit_table():
    if EXE_PATH is not None:
        info("Parsing critical table from fallout2.exe...")
        try:
            with open(EXE_PATH, "rb") as fp:
                critTables = parseCritTable.readCriticalTables(fp, 0x000fef78, 0x00106597)
                os.makedirs(assets("lut"), exist_ok=True)
                json.dump(critTables, open(assets("lut/criticalTables.json"), "w"))
                info("Done parsing critical table")
        except Exception:
            traceback.print_exc()
            warn("Error parsing critical table (see traceback above).")
    else:
        warn("Cannot parse critical table, missing fallout2.exe")
    return True

def parse_elevator_table():
    if EXE_PATH is not None:
        info("Parsing elevator table from fallout2.exe...")
        try:
            with open(EXE_PATH, "rb") as fp:
                elevators = parseElevatorTable.parseElevators(fp)
                os.makedirs(assets("lut"), exist_ok=True)
                json.dump(elevators, open(assets("lut/elevators.json"), "w"))
                info("Done parsing elevator table")
        except Exception:
            traceback.print_exc()
            warn("Error parsing elevator table (see traceback above).")
    else:
        warn("Cannot parse elevator table, missing fallout2.exe")
    return True

def extract_dats():
    data_dir = assets("data")
    os.makedirs(data_dir, exist_ok=True)

    def extract_dat(path):
        with open(path, "rb") as f:
            dat2.dumpFiles(f, data_dir)

    if not NO_EXTRACT_DAT:
        info("Extracting master.dat...")
        extract_dat(os.path.join(SRC_DIR, "master.dat"))

        info("Extracting critter.dat...")
        extract_dat(os.path.join(SRC_DIR, "critter.dat"))

        info("Done extracting DAT archives.")
    return True

def export_images():
    data_dir = assets("data")
    art_dir = assets("art")

    try:
        palette = exportImagesPar.readPAL(os.path.join(data_dir, "color.pal"))
    except IOError:
        error("Couldn't read %s" % os.path.join(data_dir, "color.pal"))

    info("Converting images, please wait...")

    try:
        exportImagesPar.convertAll(palette, data_dir, art_dir, verbose=True)
    except Exception:
        traceback.print_exc()
        warn("Error converting images (see traceback above). Continuing setup.")
        return False
    return True

def export_pros():
    info("Converting prototypes (PROs)...")
    exportPRO.extractPROs(
        os.path.join(assets("data"), "proto"),
        assets("proto")
    )
    return True

def export_maps():
    info("Converting map files...")
    maps_dir = assets("maps")
    os.makedirs(maps_dir, exist_ok=True)

    for mapFile in glob.glob(os.path.join(assets("data"), "maps", "*.map")):
        mapName = os.path.basename(mapFile).lower()
        outFile = os.path.join(maps_dir, os.path.splitext(mapName)[0] + ".json")

        try:
            info(f"Converting {mapFile} -> {outFile}")
            fomap.exportMap(assets("data"), mapFile, outFile)
        except Exception:
            traceback.print_exc()
            warn("Error converting map %s (see traceback above). Continuing." % mapFile)
    return True

def main():
    global SRC_DIR, NO_EXTRACT_DAT, NO_EXPORT_IMAGES

    if len(sys.argv) < 2:
        print("USAGE:", sys.argv[0], "FALLOUT2_INSTALL_DIR [--no-extract-dat] [--no-export-images]")
        return

    NO_EXTRACT_DAT = "--no-extract-dat" in sys.argv
    if NO_EXTRACT_DAT:
        sys.argv.remove("--no-extract-dat")

    NO_EXPORT_IMAGES = "--no-export-images" in sys.argv
    if NO_EXPORT_IMAGES:
        sys.argv.remove("--no-export-images")

    SRC_DIR = sys.argv[1]

    setup_check()
    parse_crit_table()
    parse_elevator_table()
    extract_dats()
    if not NO_EXPORT_IMAGES:
        export_images()
    export_pros()
    export_maps()

    info("")
    info("Setup complete. Please review the messages above for any warnings.")
    info("Run tsc after this to compile the TypeScript source files.")

if __name__ == "__main__":
    main()
