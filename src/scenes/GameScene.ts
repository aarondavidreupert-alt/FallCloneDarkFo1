/**
 * GameScene — main isometric game view
 *
 * Responsibilities:
 *   - Two-camera system: world camera (scrollable, zoomable) + HUD camera (static)
 *   - Load v13ent.json via MapLoader
 *   - Render floor tiles via IsoRenderer (DarkFO projection math)
 *   - Controls: arrow keys, WASD, mousewheel zoom, mouse-at-edge scroll
 *
 * Camera start position mirrors DarkFO defaults (cameraX=3580, cameraY=1020)
 * so the initial view matches what DarkFO would show for the same map.
 */

import Phaser from 'phaser'
import { IsoRenderer }         from '../iso/IsoRenderer'
import { loadMap, MapData }    from '../map/MapLoader'
import { tileFromScreen, TILE_COLS, TILE_ROWS, tileToScreen } from '../iso/geometry'

// ─── Camera tuning ────────────────────────────────────────────────────────
const CAM_START_X   = 3580     // matches DarkFO default cameraX
const CAM_START_Y   = 1020     // matches DarkFO default cameraY
const SCROLL_SPEED  = 6        // pixels per frame for key/edge scroll
const EDGE_MARGIN   = 32       // px from screen edge that triggers scroll
const ZOOM_MIN      = 0.25
const ZOOM_MAX      = 4.0
const ZOOM_STEP     = 0.12     // per wheel tick

// ─── HUD constants ────────────────────────────────────────────────────────
const HUD_HEIGHT    = 120      // bottom HUD bar height (placeholder)

export class GameScene extends Phaser.Scene {
  private isoRenderer!:  IsoRenderer
  private mapData!:      MapData
  private hudCamera!:    Phaser.Cameras.Scene2D.Camera
  private worldLayer!:   Phaser.GameObjects.Layer
  private hudLayer!:     Phaser.GameObjects.Layer

  // Scroll state
  private cursors!:      Phaser.Types.Input.Keyboard.CursorKeys
  private wasd!:         { up: Phaser.Input.Keyboard.Key; down: Phaser.Input.Keyboard.Key; left: Phaser.Input.Keyboard.Key; right: Phaser.Input.Keyboard.Key }

  // Overlay text
  private debugText!:    Phaser.GameObjects.Text
  private loadingText!:  Phaser.GameObjects.Text

  constructor() {
    super({ key: 'GameScene' })
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────

  preload(): void {
    // Real tile PNGs (Phase 2) will be loaded here via this.load.image().
    // For Phase 1 all textures are generated procedurally in IsoRenderer.
  }

  async create(): Promise<void> {
    const { width, height } = this.scale

    // ── Layers ──────────────────────────────────────────────────────────
    this.worldLayer = this.add.layer()
    this.hudLayer   = this.add.layer()

    // ── Cameras ─────────────────────────────────────────────────────────
    // Main camera: covers the full viewport, scrolls the world layer
    this.cameras.main
      .setViewport(0, 0, width, height)
      .setScroll(CAM_START_X, CAM_START_Y)
      .setZoom(1)

    // HUD camera: static overlay covering the bottom bar
    this.hudCamera = this.cameras.add(0, height - HUD_HEIGHT, width, HUD_HEIGHT)
    this.hudCamera.setScroll(0, 0)
    this.hudCamera.ignore(this.worldLayer)      // HUD never sees world tiles
    this.cameras.main.ignore(this.hudLayer)     // world camera never sees HUD

    // ── Input ────────────────────────────────────────────────────────────
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

    // ── Loading text ─────────────────────────────────────────────────────
    this.loadingText = this.add.text(width / 2, height / 2, 'Loading v13ent…', {
      fontFamily: 'monospace',
      fontSize: '18px',
      color: '#c8a84b',
    }).setOrigin(0.5)
    this.hudLayer.add(this.loadingText)
    this.cameras.main.ignore(this.loadingText)

    // ── HUD placeholder bar ───────────────────────────────────────────────
    this.buildHud(width)

    // ── Load map + render ─────────────────────────────────────────────────
    try {
      this.mapData    = await loadMap('./assets/maps/v13ent.json')
      this.isoRenderer = new IsoRenderer(this)
      this.isoRenderer.renderFloor(this.mapData.levels[0].tiles.floor)
      const rt = this.isoRenderer.getRenderTexture()!
      this.worldLayer.add(rt)
      this.cameras.main.ignore(this.hudLayer)
      this.loadingText.destroy()
    } catch (err) {
      this.loadingText.setText(`Error: ${err}`)
      console.error(err)
      return
    }

    // ── Debug text (world-space tile info under cursor) ───────────────────
    this.debugText = this.add.text(8, 8, '', {
      fontFamily: 'monospace',
      fontSize: '11px',
      color: '#00ff88',
      backgroundColor: '#00000099',
      padding: { x: 4, y: 2 },
    }).setScrollFactor(0).setDepth(100)
    this.hudLayer.add(this.debugText)
  }

  update(_time: number, _delta: number): void {
    this.handleScroll()
    this.updateDebugText()
  }

  // ── Camera scroll ─────────────────────────────────────────────────────

  private handleScroll(): void {
    const cam   = this.cameras.main
    const speed = SCROLL_SPEED / cam.zoom   // adjust speed with zoom level
    let   dx    = 0
    let   dy    = 0

    // Arrow keys + WASD
    if (this.cursors.left.isDown  || this.wasd.left.isDown)  dx -= speed
    if (this.cursors.right.isDown || this.wasd.right.isDown) dx += speed
    if (this.cursors.up.isDown    || this.wasd.up.isDown)    dy -= speed
    if (this.cursors.down.isDown  || this.wasd.down.isDown)  dy += speed

    // Mouse-at-edge scroll
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

  // ── Debug overlay ────────────────────────────────────────────────────

  private updateDebugText(): void {
    if (!this.debugText?.active) return

    const cam = this.cameras.main
    const ptr = this.input.mousePointer

    // World position under mouse cursor
    const wx = ptr.x / cam.zoom + cam.scrollX
    const wy = ptr.y / cam.zoom + cam.scrollY
    const tile = tileFromScreen(wx, wy)

    // Tile name under cursor (if in range)
    let tileName = 'out of bounds'
    const floor  = this.mapData?.levels[0]?.tiles?.floor
    if (floor && tile.x >= 0 && tile.x < TILE_COLS && tile.y >= 0 && tile.y < TILE_ROWS) {
      tileName = floor[tile.y]?.[tile.x] ?? 'undefined'
    }

    // Screen coords of the hovered tile (for alignment verification)
    const tscr = (tile.x >= 0 && tile.x < TILE_COLS) ? tileToScreen(tile.x, tile.y) : null
    const tScrStr = tscr ? `tile_world(${tscr.x},${tscr.y})` : ''

    this.debugText.setText([
      `cam: scroll(${cam.scrollX | 0}, ${cam.scrollY | 0})  zoom: ${cam.zoom.toFixed(2)}`,
      `mouse_world: (${wx | 0}, ${wy | 0})`,
      `tile: (${tile.x}, ${tile.y})  →  ${tileName}`,
      tScrStr,
    ])
  }

  // ── HUD ──────────────────────────────────────────────────────────────

  private buildHud(width: number): void {
    // Placeholder HUD bar — will be replaced by full UI in Phase 4+
    const bar = this.add.rectangle(width / 2, HUD_HEIGHT / 2, width, HUD_HEIGHT, 0x1a1008, 0.92)
    const border = this.add.rectangle(width / 2, 2, width, 2, 0xc8a84b, 1)
    const label = this.add.text(12, HUD_HEIGHT / 2, 'VAULT 13 ENTRANCE', {
      fontFamily: 'monospace',
      fontSize: '13px',
      color: '#c8a84b',
    }).setOrigin(0, 0.5)

    const hint = this.add.text(width - 12, HUD_HEIGHT / 2,
      'WASD/Arrows: scroll   Wheel: zoom', {
      fontFamily: 'monospace',
      fontSize: '11px',
      color: '#887755',
    }).setOrigin(1, 0.5)

    this.hudLayer.add([bar, border, label, hint])
    this.cameras.main.ignore(this.hudLayer)
  }
}
