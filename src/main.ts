/**
 * Entry point — initialises Phaser 3 and launches the GameScene.
 *
 * Renderer: WebGL (falls back to Canvas automatically via Phaser).
 * Resolution: 800×600 — matches the HUD layout in GameScene.
 */

import Phaser from 'phaser'
import { GameScene } from './scenes/GameScene'

const SCREEN_WIDTH  = 800
const SCREEN_HEIGHT = 600

new Phaser.Game({
  type:   Phaser.AUTO,
  width:  SCREEN_WIDTH,
  height: SCREEN_HEIGHT,
  backgroundColor: '#1a1008',
  scene:  [GameScene],
  scale: {
    mode:            Phaser.Scale.FIT,
    autoCenter:      Phaser.Scale.CENTER_BOTH,
    width:           SCREEN_WIDTH,
    height:          SCREEN_HEIGHT,
  },
  render: {
    antialias:  false,   // pixel-perfect for retro art
    pixelArt:   true,
  },
})
