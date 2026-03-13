/**
 * GameScene — main isometric game view
 *
 * Responsibilities:
 *   - Two-camera system: world camera (scrollable, zoomable) + HUD camera (static)
 *   - Render floor tiles via IsoRenderer (DarkFO projection math)
 *   - Display player critter sprite at map start position
 *   - Controls: arrow keys, WASD, mousewheel zoom, mouse-at-edge scroll
 *
 * Asset loading is handled by PreloadScene, which passes mapData and
 * imageMap via scene data so this scene needs no async fetch of its own.
 *
 * Camera start position mirrors DarkFO defaults (cameraX=3580, cameraY=1020).
 */

import Phaser from 'phaser'
import { IsoRenderer }    from '../iso/IsoRenderer'
import { MapData }        from '../map/MapLoader'
import { tileFromScreen, TILE_COLS, TILE_ROWS, tileToScreen } from '../iso/geometry'
import { PLAYER_TEXTURE_KEY } from './PreloadScene'

// ─── Camera tuning ────────────────────────────────────────────────────────
const CAM_START_X   = 3580
const CAM_START_Y   = 1020
const SCROLL_SPEED  = 6
const EDGE_MARGIN   = 32
const ZOOM_MIN      = 0.25
const ZOOM_MAX      = 4.0
const ZOOM_STEP     = 0.12

// ─── HUD ─────────────────────────────────────────────────────────────────
const HUD_HEIGHT    = 120

// ─── Player default tile position ────────────────────────────────────────
// Used when the map JSON has no startPosition (e.g. hand-crafted test maps).
// Tile (59, 35) is the approximate screen-centre at DarkFO's default camera.
const DEFAULT_PLAYER_TILE_X = 59
const DEFAULT_PLAYER_TILE_Y = 35

// ─── Scene init data (passed from PreloadScene) ───────────────────────────
interface SceneData {
  mapData:  MapData
  imageMap: Record<string, unknown>
}

export class GameScene extends Phaser.Scene {
  private isoRenderer!:  IsoRenderer
  private mapData!:      MapData
  private imageMap:      Record<string, unknown> = {}
  private hudCamera!:    Phaser.Cameras.Scene2D.Camera
  private worldLayer!:   Phaser.GameObjects.Layer
  private hudLayer!:     Phaser.GameObjects.Layer
  private playerSprite:  Phaser.GameObjects.Image | Phaser.GameObjects.Sprite | null = null

  private cursors!:      Phaser.Types.Input.Keyboard.CursorKeys
  private wasd!: {
    up:    Phaser.Input.Keyboard.Key
    down:  Phaser.Input.Keyboard.Key
    left:  Phaser.Input.Keyboard.Key
    right: Phaser.Input.Keyboard.Key
  }

  private debugText!:    Phaser.GameObjects.Text

  constructor() {
    super({ key: 'GameScene' })
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────

  /**
   * Receive map data and imageMap from PreloadScene.
   * Using init() guarantees the data is available before create() runs.
   */
  init(data: SceneData): void {
    this.mapData  = data.mapData
    this.imageMap = data.imageMap ?? {}
  }

  create(): void {
    const { width, height } = this.scale

    // ── Layers ─────────────────────────────────────────────────────────
    this.worldLayer = this.add.layer()
    this.hudLayer   = this.add.layer()

    // ── Cameras ────────────────────────────────────────────────────────
    this.cameras.main
      .setViewport(0, 0, width, height)
      .setScroll(CAM_START_X, CAM_START_Y)
      .setZoom(1)

    this.hudCamera = this.cameras.add(0, height - HUD_HEIGHT, width, HUD_HEIGHT)
    this.hudCamera.setScroll(0, 0)
    this.hudCamera.ignore(this.worldLayer)
    this.cameras.main.ignore(this.hudLayer)

    // ── Input ──────────────────────────────────────────────────────────
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

    // ── HUD ────────────────────────────────────────────────────────────
    this.buildHud(width)

    // ── Floor tiles ────────────────────────────────────────────────────
    this.isoRenderer = new IsoRenderer(this)
    this.isoRenderer.renderFloor(this.mapData.levels[0].tiles.floor)
    const rt = this.isoRenderer.getRenderTexture()!
    this.worldLayer.add(rt)

    // ── Player critter sprite ──────────────────────────────────────────
    this.placePlayerSprite()

    // ── Debug overlay ──────────────────────────────────────────────────
    this.debugText = this.add.text(8, 8, '', {
      fontFamily:       'monospace',
      fontSize:         '11px',
      color:            '#00ff88',
      backgroundColor:  '#00000099',
      padding:          { x: 4, y: 2 },
    }).setScrollFactor(0).setDepth(100)
    this.hudLayer.add(this.debugText)
  }

  update(_time: number, _delta: number): void {
    this.handleScroll()
    this.updateDebugText()
  }

  // ── Player sprite ──────────────────────────────────────────────────────

  private placePlayerSprite(): void {
    if (!this.textures.exists(PLAYER_TEXTURE_KEY)) {
      // Critter PNG not found; fallback placeholder diamond will be shown
      // in the tile layer — no separate sprite needed here.
      console.warn('[GameScene] Player critter texture not loaded — skipping sprite.')
      return
    }

    // Tile position: prefer map startPosition, fall back to default
    const start = (this.mapData as MapData & { startPosition?: { x: number; y: number } }).startPosition
    const tx    = start?.x ?? DEFAULT_PLAYER_TILE_X
    const ty    = start?.y ?? DEFAULT_PLAYER_TILE_Y

    const worldPos = tileToScreen(tx, ty)
    // Anchor at bottom-centre of the tile diamond (standard isometric origin)
    const px = worldPos.x + 40   // tile half-width
    const py = worldPos.y + 36   // tile full height (bottom edge)

    const tex = this.textures.get(PLAYER_TEXTURE_KEY)
    const hasFrames = tex.frameTotal > 1

    if (hasFrames) {
      // Loaded as spritesheet — show standing frame 0 (south-facing)
      this.playerSprite = this.add.sprite(px, py, PLAYER_TEXTURE_KEY, 0)
    } else {
      // Loaded as plain image (no imageMap) — show the full strip
      this.playerSprite = this.add.image(px, py, PLAYER_TEXTURE_KEY)
    }

    // Anchor at bottom-centre so the feet sit on the tile surface
    this.playerSprite.setOrigin(0.5, 1)
    this.playerSprite.setDepth(ty * 100 + tx)  // correct iso depth within layer

    this.worldLayer.add(this.playerSprite)
    this.cameras.main.ignore(this.hudLayer)
  }

  // ── Camera scroll ─────────────────────────────────────────────────────

  private handleScroll(): void {
    const cam   = this.cameras.main
    const speed = SCROLL_SPEED / cam.zoom
    let   dx    = 0
    let   dy    = 0

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

  // ── Debug overlay ─────────────────────────────────────────────────────

  private updateDebugText(): void {
    if (!this.debugText?.active) return

    const cam = this.cameras.main
    const ptr = this.input.mousePointer

    const wx   = ptr.x / cam.zoom + cam.scrollX
    const wy   = ptr.y / cam.zoom + cam.scrollY
    const tile = tileFromScreen(wx, wy)

    let tileName = 'out of bounds'
    const floor  = this.mapData?.levels[0]?.tiles?.floor
    if (floor && tile.x >= 0 && tile.x < TILE_COLS && tile.y >= 0 && tile.y < TILE_ROWS) {
      tileName = floor[tile.y]?.[tile.x] ?? 'undefined'
    }

    const tscr    = (tile.x >= 0 && tile.x < TILE_COLS) ? tileToScreen(tile.x, tile.y) : null
    const tScrStr = tscr ? `tile_world(${tscr.x},${tscr.y})` : ''

    // Show whether tiles are real PNGs or procedural fallbacks
    const realTile = tileName !== 'out of bounds' && this.textures.exists(tileName)
    const tileMode = realTile ? '🖼' : '◇'

    this.debugText.setText([
      `cam: scroll(${cam.scrollX | 0}, ${cam.scrollY | 0})  zoom: ${cam.zoom.toFixed(2)}`,
      `mouse_world: (${wx | 0}, ${wy | 0})`,
      `tile: (${tile.x}, ${tile.y})  ${tileMode}  ${tileName}`,
      tScrStr,
    ])
  }

  // ── HUD ──────────────────────────────────────────────────────────────

  private buildHud(width: number): void {
    const bar    = this.add.rectangle(width / 2, HUD_HEIGHT / 2, width, HUD_HEIGHT, 0x1a1008, 0.92)
    const border = this.add.rectangle(width / 2, 2, width, 2, 0xc8a84b, 1)
    const label  = this.add.text(12, HUD_HEIGHT / 2, 'VAULT 13 ENTRANCE', {
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

    this.hudLayer.add([bar, border, label, hint])
    this.cameras.main.ignore(this.hudLayer)
  }
}
