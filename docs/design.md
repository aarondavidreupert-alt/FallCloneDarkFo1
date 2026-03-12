# Design Document — Fallout 1 Browser Remake

## Vision
A faithful browser-based recreation of Fallout 1, playable without installation.
Built on DarkFO's proven engine, adapted for Fallout 1 content and modernized for 2024.

## Core Pillars
1. **Faithful** — Fallout 1 maps, dialogue, items, critters
2. **Browser-first** — runs on any modern browser, no install
3. **Moddable** — JSON-driven content, swappable UI themes
4. **Upgradeable** — architecture supports future 3D/hi-res upgrades

## UI Theme System
Two themes, switchable in options:

### Theme A: New Vegas (Default)
- Dark brown/amber color palette
- Pip-Boy inspired HUD
- Smooth modern fonts

### Theme B: Classic DarkFO
- Original Fallout green/black terminal look
- Pixel-perfect retro feel

## Camera & Controls
- Isometric view, mousewheel zoom
- Arrow keys to scroll map
- Mouse at screen edge to scroll map
- Click to move player
- Two-camera system: world camera + static HUD camera

## MVP Success Criteria
- [ ] Player can create a character with SPECIAL stats
- [ ] Player can walk around Vault 13 entrance map
- [ ] Player can talk to an NPC with dialogue tree
- [ ] Player can enter turn-based combat
- [ ] Player can pick up and use an item
- [ ] Game runs in browser, deployed on Netlify

## Future Upgrades (Post-MVP)
- Hi-res critter sprites (Nano Banana 2 AI upscaling)
- 3D model integration (Tripo AI)
- Enhanced lighting system
- World map + travel
- Full Fallout 1 quest line