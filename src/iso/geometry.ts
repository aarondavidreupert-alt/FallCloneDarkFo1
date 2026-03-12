/**
 * Isometric geometry — ported from DarkFO geometry.ts (darkf, Stratege)
 *
 * Fallout uses a rectangular tile grid rendered isometrically.
 * Each tile cell is TILE_WIDTH × TILE_HEIGHT pixels (80×36).
 * The grid is 100×100 tiles per map level.
 *
 * Tile coordinate conventions (matching DarkFO exactly):
 *   - x: column, 0–99 (left to right in tile space)
 *   - y: row,    0–99 (top to bottom in tile space)
 *
 * tileToScreen produces the top-left corner of the tile image in world space.
 * Camera offset is handled separately (Phaser camera scroll).
 */

export const TILE_WIDTH  = 80
export const TILE_HEIGHT = 36
export const TILE_COLS   = 100   // map grid width
export const TILE_ROWS   = 100   // map grid height

export interface Point {
  x: number
  y: number
}

/**
 * Convert tile grid coordinates → world (screen) pixel position.
 * Copied verbatim from DarkFO geometry.ts – this is the proven math.
 *
 * Returns the top-left corner of the tile image.
 */
export function tileToScreen(x: number, y: number): Point {
  x = 99 - x   // DarkFO stores tiles right-to-left; reverse here
  const sx = 4752 + (32 * y) - (48 * x)
  const sy = (24 * y) + (12 * x)
  return { x: sx, y: sy }
}

/**
 * Convert world pixel position → nearest tile grid coordinates.
 * Inverse of tileToScreen.  Copied verbatim from DarkFO.
 */
export function tileFromScreen(x: number, y: number): Point {
  const off_x = -4800 + x
  const off_y  = y
  let xx = off_x - off_y * 4 / 3
  let tx = xx / 64
  if (xx >= 0) tx++
  tx = -tx
  let yy = off_y + off_x / 4
  let ty = yy / 32
  if (yy < 0) ty--
  return { x: 99 - Math.round(tx), y: Math.round(ty) }
}

/**
 * World-space bounding box of the entire 100×100 tile map.
 * Useful for clamping camera bounds.
 */
export function mapWorldBounds(): { minX: number; minY: number; maxX: number; maxY: number } {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  // Sample all four corners of the grid
  const corners = [
    { x: 0,              y: 0 },
    { x: TILE_COLS - 1,  y: 0 },
    { x: 0,              y: TILE_ROWS - 1 },
    { x: TILE_COLS - 1,  y: TILE_ROWS - 1 },
  ]
  for (const c of corners) {
    const s = tileToScreen(c.x, c.y)
    if (s.x < minX) minX = s.x
    if (s.y < minY) minY = s.y
    if (s.x + TILE_WIDTH  > maxX) maxX = s.x + TILE_WIDTH
    if (s.y + TILE_HEIGHT > maxY) maxY = s.y + TILE_HEIGHT
  }
  return { minX, minY, maxX, maxY }
}
