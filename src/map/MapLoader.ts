/**
 * MapLoader — loads and validates DarkFO-format map JSON.
 *
 * DarkFO map format (SerializedMap / mapObj):
 *   {
 *     name:      string
 *     mapID:     number
 *     numLevels: number
 *     levels: [
 *       {
 *         tiles: {
 *           floor: string[][]   // [y][x], 100 rows × 100 cols, "grid000" = empty
 *           roof:  string[][]
 *         }
 *       },
 *       ...
 *     ]
 *   }
 */

export interface MapLevel {
  tiles: {
    floor: string[][]
    roof:  string[][]
  }
}

export interface MapData {
  name:      string
  mapID:     number
  numLevels: number
  levels:    MapLevel[]
}

/**
 * Load a JSON map from the given URL (relative to public/).
 * Validates that the floor/roof arrays look reasonable before returning.
 */
export async function loadMap(url: string): Promise<MapData> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`MapLoader: failed to fetch ${url} — ${res.status}`)
  const data = await res.json() as MapData
  validateMap(data, url)
  return data
}

function validateMap(data: MapData, url: string): void {
  if (!Array.isArray(data.levels) || data.levels.length === 0) {
    throw new Error(`MapLoader: "${url}" has no levels`)
  }
  const floor = data.levels[0]?.tiles?.floor
  if (!Array.isArray(floor)) {
    throw new Error(`MapLoader: "${url}" level 0 missing tiles.floor`)
  }
  if (floor.length !== 100 || floor[0]?.length !== 100) {
    console.warn(`MapLoader: "${url}" floor is ${floor.length}×${floor[0]?.length ?? 0}, expected 100×100`)
  }
}
