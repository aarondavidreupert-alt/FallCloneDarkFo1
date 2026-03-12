/**
 * IsoRenderer — Phaser 3 isometric tile renderer
 *
 * Adapts DarkFO's CanvasRenderer.drawTileMap() for Phaser 3.
 * Uses the same DarkFO tileToScreen projection math (no gaps, no overlaps).
 *
 * Rendering strategy:
 *   - All floor tiles blit onto a single Phaser.GameObjects.RenderTexture so
 *     the entire floor is one draw call regardless of tile count.
 *   - The RenderTexture sits at world origin (0, 0); the Phaser camera scroll
 *     replicates DarkFO's "cameraX / cameraY" offset exactly.
 *
 * Placeholder tiles:
 *   Phase 1 has no real Fallout .FRM assets (those arrive in Phase 2).
 *   Each unique tile name gets a coloured diamond texture generated via
 *   Phaser Graphics so the isometric grid is fully visible for testing.
 */

import Phaser from 'phaser'
import { tileToScreen, TILE_WIDTH, TILE_HEIGHT, TILE_COLS, TILE_ROWS } from './geometry'

// ─── Tile palette ──────────────────────────────────────────────────────────
// Maps tile names (from v13ent.json) → fill colour used for placeholder art.
// Real PNGs from the asset pipeline (Phase 2) will override these via the
// Phaser texture cache — no code change needed.
const TILE_PALETTE: Record<string, number> = {
  // Vault interior surfaces
  metal01:    0x4a5568,
  metal02:    0x3d4a58,
  concrete01: 0x6b7280,
  concrete02: 0x7c8594,
  // Cave / rock
  cave01:     0x5c4033,
  cave02:     0x4a3025,
  cave03:     0x6b4c39,
  // Dirt paths
  dirt01:     0x8b7355,
  dirt02:     0x7a6345,
}

// Darkened edge colour for the diamond outline (grid alignment visual aid)
const OUTLINE_ALPHA = 0.45

// ─── World canvas dimensions ───────────────────────────────────────────────
// tileToScreen range for a 100×100 grid:
//   sx: 0  … ~7920   sy: 0 … ~3564
// We add one tile of padding on every side.
const WORLD_W = 8100
const WORLD_H = 3700

export class IsoRenderer {
  private scene:  Phaser.Scene
  private rt:     Phaser.GameObjects.RenderTexture | null = null

  constructor(scene: Phaser.Scene) {
    this.scene = scene
  }

  // ── Texture generation ──────────────────────────────────────────────────

  /**
   * Ensure a placeholder diamond texture exists in the Phaser cache for
   * every tile name that appears in the floor map.
   * If a real PNG was loaded under the same key it is left untouched.
   */
  ensureTileTextures(tileNames: Set<string>): void {
    for (const name of tileNames) {
      if (name === 'grid000') continue
      if (!this.scene.textures.exists(name)) {
        const colour = TILE_PALETTE[name] ?? 0x556655
        this.createDiamondTexture(name, colour)
      }
    }
  }

  private createDiamondTexture(key: string, fill: number): void {
    const g = this.scene.make.graphics({ x: 0, y: 0 })
    g.setVisible(false)

    const hw = TILE_WIDTH  / 2   // half-width  = 40
    const hh = TILE_HEIGHT / 2   // half-height = 18

    // Diamond vertices (top, right, bottom, left)
    const pts = [
      new Phaser.Geom.Point(hw,          0 ),
      new Phaser.Geom.Point(TILE_WIDTH,  hh),
      new Phaser.Geom.Point(hw,          TILE_HEIGHT),
      new Phaser.Geom.Point(0,           hh),
    ]

    // Filled diamond
    g.fillStyle(fill, 1)
    g.fillPoints(pts, true)

    // Subtle darker edge — helps eye detect tile boundaries
    g.lineStyle(1, darken(fill, 0.4), OUTLINE_ALPHA)
    g.strokePoints(pts, true)

    g.generateTexture(key, TILE_WIDTH, TILE_HEIGHT)
    g.destroy()
  }

  // ── Map rendering ────────────────────────────────────────────────────────

  /**
   * Render the floor tile map onto a RenderTexture in world space.
   *
   * floorMap layout (matches DarkFO SerializedMap.floorMap):
   *   floorMap[y][x]  — first index is row (y), second is column (x)
   *   values are tile name strings, "grid000" means empty
   *
   * Drawing order mirrors DarkFO canvasrenderer.ts drawTileMap():
   *   outer loop i = x (0..99), inner loop j = y (0..99)
   *   tile = floorMap[j][i] → tileToScreen(i, j)
   *
   * This order ensures tiles closer to the viewer (higher y) are drawn
   * last (on top) — correct painter's-algorithm depth for isometric tiles.
   */
  renderFloor(floorMap: string[][]): void {
    // Collect all unique tile names so we can pre-warm the texture cache
    const names = new Set<string>()
    for (let i = 0; i < TILE_COLS; i++) {
      for (let j = 0; j < TILE_ROWS; j++) {
        const t = floorMap[j]?.[i]
        if (t && t !== 'grid000') names.add(t)
      }
    }
    this.ensureTileTextures(names)

    // (Re)create the RenderTexture that covers the full world canvas
    if (this.rt) this.rt.destroy()
    this.rt = this.scene.add.renderTexture(0, 0, WORLD_W, WORLD_H)
    this.rt.setOrigin(0, 0)

    // Draw tiles — exact loop structure from DarkFO canvasrenderer.ts
    for (let i = 0; i < TILE_COLS; i++) {
      for (let j = 0; j < TILE_ROWS; j++) {
        const tileName = floorMap[j]?.[i]
        if (!tileName || tileName === 'grid000') continue

        const key = this.scene.textures.exists(tileName) ? tileName : this.fallbackKey(tileName)
        if (!key) continue

        const { x, y } = tileToScreen(i, j)
        this.rt.draw(key, x, y)
      }
    }
  }

  /**
   * Return the RenderTexture game object so the scene can control its depth
   * and the camera can ignore it if needed.
   */
  getRenderTexture(): Phaser.GameObjects.RenderTexture | null {
    return this.rt
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  private fallbackKey(name: string): string | null {
    // Try to find the closest palette entry by prefix
    for (const k of Object.keys(TILE_PALETTE)) {
      if (k.startsWith(name.slice(0, 4))) return k
    }
    // Last resort: generate a default grey tile on the fly
    if (!this.scene.textures.exists('_tile_default')) {
      this.createDiamondTexture('_tile_default', 0x556655)
    }
    return '_tile_default'
  }
}

// ─── Colour utilities ─────────────────────────────────────────────────────

function darken(colour: number, amount: number): number {
  const r = ((colour >> 16) & 0xff) * (1 - amount) | 0
  const g = ((colour >>  8) & 0xff) * (1 - amount) | 0
  const b = ( colour        & 0xff) * (1 - amount) | 0
  return (r << 16) | (g << 8) | b
}
