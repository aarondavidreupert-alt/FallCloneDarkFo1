/**
 * LocationScene — load and render vault13.json
 *
 * Self-contained scene (no separate PreloadScene).
 * Two-pass Phaser 3 loader strategy:
 *   preload()    → fetch vault13.json
 *   create()     → collect unique tile names, load only those PNGs, then render
 *   buildScene() → called on 'complete'; sets up camera/input/map
 *
 * Map format (produced by scripts/map_to_json.py):
 *   data.levels[0].tiles.floor  — 100×100 string[][] (row-major: [y][x])
 *   "grid000"                   — void cell, skip rendering
 *   "{name}"                    → assets/art/tiles/{name}.png
 */

import Phaser from 'phaser'
import { IsoRenderer }    from '../iso/IsoRenderer'
import { tileFromScreen, TILE_COLS, TILE_ROWS, tileToScreen } from '../iso/geometry'

// ─── Asset paths ────────────────────────────────────────────────────────────
const MAP_URL   = 'assets/maps/vault13.json'
const TILE_BASE = 'assets/art/tiles/'

// ─── Camera tuning (mirrors DarkFO defaults) ────────────────────────────────
const CAM_START_X  = 3580
const CAM_START_Y  = 1020
const SCROLL_SPEED = 6
const EDGE_MARGIN  = 32
const ZOOM_MIN     = 0.25
const ZOOM_MAX     = 4.0
const ZOOM_STEP    = 0.12

// ─── HUD ────────────────────────────────────────────────────────────────────
const HUD_HEIGHT = 120

export class LocationScene extends Phaser.Scene {
  // Set after buildScene() — guarded in update()
  private floorMap:    string[][] = []
  private isoRenderer: IsoRenderer | null = null
  private worldLayer:  Phaser.GameObjects.Layer | null = null
  private hudLayer:    Phaser.GameObjects.Layer | null = null
  private hudCamera:   Phaser.Cameras.Scene2D.Camera | null = null
  private cursors:     Phaser.Types.Input.Keyboard.CursorKeys | null = null
  private wasd: {
    up:    Phaser.Input.Keyboard.Key
    down:  Phaser.Input.Keyboard.Key
    left:  Phaser.Input.Keyboard.Key
    right: Phaser.Input.Keyboard.Key
  } | null = null
  private debugText: Phaser.GameObjects.Text | null = null

  constructor() {
    super({ key: 'LocationScene' })
  }

  // ── Pass 1: load the map JSON ─────────────────────────────────────────────

  preload(): void {
    this.buildProgressUI()
    this.load.json('vault13', MAP_URL)
  }

  // ── Pass 2: load only the tile PNGs referenced in the map ─────────────────

  create(): void {
    type MapShape = { levels: Array<{ tiles: { floor: string[][] } }> }
    const mapData = this.cache.json.get('vault13') as MapShape | null
    this.floorMap = mapData?.levels?.[0]?.tiles?.floor ?? []

    // Collect only the unique non-void tile names referenced by the map
    const tileNames = new Set<string>()
    for (const row of this.floorMap) {
      for (const name of row) {
        if (name && name !== 'grid000') tileNames.add(name)
      }
    }

    // Warn on 404s — IsoRenderer will substitute a procedural diamond
    this.load.on('loaderror', (file: Phaser.Loader.File) => {
      console.warn(`[LocationScene] Tile PNG not found (will use placeholder): ${file.url}`)
    })

    // Load each unique tile under its name as the Phaser texture key
    for (const name of tileNames) {
      this.load.image(name, `${TILE_BASE}${name}.png`)
    }

    this.load.once('complete', () => this.buildScene())

    // Starts the pass-2 loader; fires 'complete' immediately if nothing queued
    this.load.start()
  }

  // ── Render ────────────────────────────────────────────────────────────────

  private buildScene(): void {
    const { width, height } = this.scale

    // ── Layers ────────────────────────────────────────────────────────────
    this.worldLayer = this.add.layer()
    this.hudLayer   = this.add.layer()

    // ── Cameras ───────────────────────────────────────────────────────────
    this.cameras.main
      .setViewport(0, 0, width, height)
      .setScroll(CAM_START_X, CAM_START_Y)
      .setZoom(1)

    this.hudCamera = this.cameras.add(0, height - HUD_HEIGHT, width, HUD_HEIGHT)
    this.hudCamera.setScroll(0, 0)
    this.hudCamera.ignore(this.worldLayer)
    this.cameras.main.ignore(this.hudLayer)

    // ── Input ─────────────────────────────────────────────────────────────
    this.cursors = this.input.keyboard!.createCursorKeys()
    this.wasd = {
      up:    this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.W),
      down:  this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.S),
      left:  this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.A),
      right: this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.D),
    }

    this.input.on('wheel', (_ptr: unknown, _objs: unknown, _dx: number, dy: number) => {
      const cam   = this.cameras.main
      const delta = dy > 0 ? -ZOOM_STEP : ZOOM_STEP
      cam.setZoom(Phaser.Math.Clamp(cam.zoom + delta, ZOOM_MIN, ZOOM_MAX))
    })

    // ── HUD ───────────────────────────────────────────────────────────────
    this.buildHud(width)

    // ── Floor tiles ───────────────────────────────────────────────────────
    this.isoRenderer = new IsoRenderer(this)
    this.isoRenderer.renderFloor(this.floorMap)
    const rt = this.isoRenderer.getRenderTexture()!
    this.worldLayer.add(rt)

    // ── Debug overlay ─────────────────────────────────────────────────────
    this.debugText = this.add.text(8, 8, '', {
      fontFamily:      'monospace',
      fontSize:        '11px',
      color:           '#00ff88',
      backgroundColor: '#00000099',
      padding:         { x: 4, y: 2 },
    }).setScrollFactor(0).setDepth(100)
    this.hudLayer.add(this.debugText)
  }

  // ── Game loop ─────────────────────────────────────────────────────────────

  update(_time: number, _delta: number): void {
    // Guard: buildScene() hasn't run yet (still loading pass-2 assets)
    if (!this.cursors) return
    this.handleScroll()
    this.updateDebugText()
  }

  // ── Camera scroll ─────────────────────────────────────────────────────────

  private handleScroll(): void {
    if (!this.cursors || !this.wasd) return
    const cam   = this.cameras.main
    const speed = SCROLL_SPEED / cam.zoom
    let dx = 0
    let dy = 0

    if (this.cursors.left.isDown  || this.wasd.left.isDown)  dx -= speed
    if (this.cursors.right.isDown || this.wasd.right.isDown) dx += speed
    if (this.cursors.up.isDown    || this.wasd.up.isDown)    dy -= speed
    if (this.cursors.down.isDown  || this.wasd.down.isDown)  dy += speed

    const ptr = this.input.mousePointer
    if (ptr.x < EDGE_MARGIN)                     dx -= speed
    if (ptr.x > this.scale.width - EDGE_MARGIN)  dx += speed
    if (ptr.y < EDGE_MARGIN)                     dy -= speed
    if (ptr.y > this.scale.height - EDGE_MARGIN) dy += speed

    if (dx !== 0 || dy !== 0) {
      cam.scrollX += dx
      cam.scrollY += dy
    }
  }

  // ── Debug overlay ─────────────────────────────────────────────────────────

  private updateDebugText(): void {
    if (!this.debugText?.active) return

    const cam  = this.cameras.main
    const ptr  = this.input.mousePointer
    const wx   = ptr.x / cam.zoom + cam.scrollX
    const wy   = ptr.y / cam.zoom + cam.scrollY
    const tile = tileFromScreen(wx, wy)

    let tileName = 'out of bounds'
    if (tile.x >= 0 && tile.x < TILE_COLS && tile.y >= 0 && tile.y < TILE_ROWS) {
      tileName = this.floorMap[tile.y]?.[tile.x] ?? 'undefined'
    }

    const tscr    = (tile.x >= 0 && tile.x < TILE_COLS) ? tileToScreen(tile.x, tile.y) : null
    const tScrStr = tscr ? `tile_world(${tscr.x},${tscr.y})` : ''

    this.debugText.setText([
      `cam: scroll(${cam.scrollX | 0}, ${cam.scrollY | 0})  zoom: ${cam.zoom.toFixed(2)}`,
      `mouse_world: (${wx | 0}, ${wy | 0})`,
      `tile: (${tile.x}, ${tile.y})  ${tileName}`,
      tScrStr,
    ])
  }

  // ── HUD ───────────────────────────────────────────────────────────────────

  private buildHud(width: number): void {
    const bar    = this.add.rectangle(width / 2, HUD_HEIGHT / 2, width, HUD_HEIGHT, 0x1a1008, 0.92)
    const border = this.add.rectangle(width / 2, 2, width, 2, 0xc8a84b, 1)
    const label  = this.add.text(12, HUD_HEIGHT / 2, 'VAULT 13', {
      fontFamily: 'monospace',
      fontSize:   '13px',
      color:      '#c8a84b',
    }).setOrigin(0, 0.5)
    const hint = this.add.text(width - 12, HUD_HEIGHT / 2,
      'WASD/Arrows: scroll   Wheel: zoom', {
      fontFamily: 'monospace',
      fontSize:   '11px',
      color:      '#887755',
    }).setOrigin(1, 0.5)
    this.hudLayer!.add([bar, border, label, hint])
    this.cameras.main.ignore(this.hudLayer!)
  }

  // ── Loading UI (shown during pass-1 JSON fetch) ───────────────────────────

  private buildProgressUI(): void {
    const { width, height } = this.scale
    const cx   = width  / 2
    const cy   = height / 2
    const barW = 360
    const barH = 14

    this.add.text(cx, cy - 36, 'VAULT 13', {
      fontFamily: 'monospace',
      fontSize:   '22px',
      color:      '#c8a84b',
    }).setOrigin(0.5)

    this.add.text(cx, cy - 14, 'loading map…', {
      fontFamily: 'monospace',
      fontSize:   '11px',
      color:      '#887755',
    }).setOrigin(0.5)

    this.add.rectangle(cx, cy + 14, barW + 4, barH + 4, 0x1a1008)
    this.add.rectangle(cx, cy + 14, barW + 2, barH + 2, 0x4a3810)
    const bar = this.add.rectangle(cx - barW / 2, cy + 14, 0, barH, 0xc8a84b).setOrigin(0, 0.5)
    this.load.on('progress', (v: number) => { bar.width = barW * v })
  }
}
