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
 * Real vs. placeholder textures:
 *   PreloadScene loads real PNGs from assets/tiles/{name}.png and registers
 *   them in the Phaser texture cache under the tile name (e.g. "metal01").
 *   ensureTileTextures() checks textures.exists(name) — if the real PNG was
 *   loaded it skips diamond generation, so real art is used automatically.
 *   Any tile whose PNG was missing (404 / pipeline not yet run) falls back
 *   to a procedural coloured diamond sized 80×36 px.
 */

import Phaser from 'phaser'
import { tileToScreen, TILE_WIDTH, TILE_HEIGHT, TILE_COLS, TILE_ROWS } from './geometry'

// ─── Fallback palette ──────────────────────────────────────────────────────
// Maps tile names → fill colour for procedural diamonds.
// These names match the v13ent.json test map exactly, so the placeholder
// graphics are visually sensible before real PNGs are available.
// When a real PNG is loaded by PreloadScene, the diamond is never generated.
const TILE_PALETTE: Record<string, number> = {
  // Vault interior
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

// Default grey used for any tile name not found in TILE_PALETTE
const FALLBACK_COLOUR = 0x4a5040

// Darkened edge colour for the diamond outline (grid alignment aid)
const OUTLINE_ALPHA = 0.45

// ─── World canvas dimensions ───────────────────────────────────────────────
// tileToScreen range for a 100×100 grid:
//   sx: 0 … ~7920   sy: 0 … ~3564
// One tile of padding on every side.
const WORLD_W = 8100
const WORLD_H = 3700

export class IsoRenderer {
  private scene: Phaser.Scene
  private rt:    Phaser.GameObjects.RenderTexture | null = null

  constructor(scene: Phaser.Scene) {
    this.scene = scene
  }

  // ── Texture generation ─────────────────────────────────────────────────

  /**
   * For every tile name in the floor map, ensure a texture exists in the
   * Phaser cache.  Real PNGs loaded by PreloadScene take priority — this
   * only runs diamond generation for tiles that are still missing.
   */
  ensureTileTextures(tileNames: Set<string>): void {
    for (const name of tileNames) {
      if (name === 'grid000') continue
      if (!this.scene.textures.exists(name)) {
        this.createDiamondTexture(name, TILE_PALETTE[name] ?? FALLBACK_COLOUR)
      }
    }
  }

  private createDiamondTexture(key: string, fill: number): void {
    const g = this.scene.make.graphics({ x: 0, y: 0 })
    g.setVisible(false)

    const hw = TILE_WIDTH  / 2   // 40
    const hh = TILE_HEIGHT / 2   // 18

    const pts = [
      new Phaser.Geom.Point(hw,         0           ),
      new Phaser.Geom.Point(TILE_WIDTH, hh          ),
      new Phaser.Geom.Point(hw,         TILE_HEIGHT ),
      new Phaser.Geom.Point(0,          hh          ),
    ]

    g.fillStyle(fill, 1)
    g.fillPoints(pts, true)

    // Subtle edge outline helps eye detect tile boundaries
    g.lineStyle(1, darken(fill, 0.4), OUTLINE_ALPHA)
    g.strokePoints(pts, true)

    g.generateTexture(key, TILE_WIDTH, TILE_HEIGHT)
    g.destroy()
  }

  // ── Map rendering ──────────────────────────────────────────────────────

  /**
   * Render the floor tile map onto a RenderTexture in world space.
   *
   * floorMap[y][x] — tile name strings; "grid000" means empty cell.
   *
   * Loop order mirrors DarkFO canvasrenderer.ts drawTileMap():
   *   outer i = column (x 0→99), inner j = row (y 0→99)
   * This paints higher-y tiles last so they occlude lower-y ones — correct
   * painter's-algorithm depth for isometric art.
   */
  renderFloor(floorMap: string[][]): void {
    // Collect names → generate any missing placeholder diamonds
    const names = new Set<string>()
    for (let i = 0; i < TILE_COLS; i++) {
      for (let j = 0; j < TILE_ROWS; j++) {
        const t = floorMap[j]?.[i]
        if (t && t !== 'grid000') names.add(t)
      }
    }
    this.ensureTileTextures(names)

    if (this.rt) this.rt.destroy()
    this.rt = this.scene.add.renderTexture(0, 0, WORLD_W, WORLD_H)
    this.rt.setOrigin(0, 0)

    for (let i = 0; i < TILE_COLS; i++) {
      for (let j = 0; j < TILE_ROWS; j++) {
        const name = floorMap[j]?.[i]
        if (!name || name === 'grid000') continue

        // Real PNG if present; procedural diamond guaranteed by ensureTileTextures
        const key = this.scene.textures.exists(name) ? name : this.fallbackTextureKey(name)
        if (!key) continue

        const { x, y } = tileToScreen(i, j)
        this.rt.draw(key, x, y)
      }
    }
  }

  getRenderTexture(): Phaser.GameObjects.RenderTexture | null {
    return this.rt
  }

  // ── Helpers ────────────────────────────────────────────────────────────

  /**
   * Resolve a texture key for a tile that somehow slipped past
   * ensureTileTextures() (should not happen in normal flow).
   * Generates a single grey default tile rather than silently dropping it.
   */
  private fallbackTextureKey(name: string): string {
    const DEFAULT_KEY = '_tile_default'
    if (!this.scene.textures.exists(DEFAULT_KEY)) {
      this.createDiamondTexture(DEFAULT_KEY, FALLBACK_COLOUR)
    }
    console.warn(`[IsoRenderer] No texture for "${name}" — using default diamond`)
    return DEFAULT_KEY
  }
}

// ─── Colour helpers ────────────────────────────────────────────────────────

function darken(colour: number, amount: number): number {
  const r = ((colour >> 16) & 0xff) * (1 - amount) | 0
  const g = ((colour >>  8) & 0xff) * (1 - amount) | 0
  const b = ( colour        & 0xff) * (1 - amount) | 0
  return (r << 16) | (g << 8) | b
}
