# Phases — Fallout 1 Browser Remake

## How to use this
Tell Claude: "Read docs/CLAUDE.md, docs/design.md and docs/phases.md. Start Phase X."

---

## Phase 0 — Foundation ✅ DONE
- Vite + TypeScript + Phaser 3 setup
- Netlify deployment working
- Two-camera system (world + HUD)
- Mousewheel zoom + edge/arrow scrolling

---

## Phase 1 — DarkFO Integration
- Copy DarkFO engine into /darkfo/
- Adapt DarkFO's IsoRenderer for Phaser 3
- Adapt DarkFO's tile projection math (proven correct)
- Load v13ent.json map using DarkFO's map format
- Render floor tiles correctly with no gaps or overlaps

---

## Phase 2 — Asset Pipeline
- Python scripts to convert Fallout 1 .FRM → PNG
- Python scripts to convert .MAP → JSON (DarkFO format)
- Python scripts to convert .ACM → MP3
- Test with real Vault 13 entrance assets locally

---

## Phase 3 — Player Movement
- Player sprite on map
- Click-to-move with A* pathfinding (adapt from DarkFO)
- Smooth walking animation
- Collision detection

---

## Phase 4 — Character Creation
- SPECIAL stat allocation (7 stats, 5 points each, 1-10 range)
- Derived stats (HP, AP, AC etc.)
- Skill points allocation
- Trait selection (2 traits)
- Name entry
- New Vegas UI theme by default

---

## Phase 5 — NPC & Dialogue
- NPC placement on map
- Click NPC to talk
- Dialogue tree loaded from JSON
- Fallout 1 style dialogue box UI
- Overseer gives water chip quest

---

## Phase 6 — Inventory & Items
- Item pickup from map
- Inventory screen (Fallout 1 style)
- Equip/use/drop items
- Item stats display

---

## Phase 7 — Combat
- Turn-based combat mode
- Action Points system
- Attack animations
- Hit/miss calculation (SPECIAL based)
- Enemy AI (basic)

---

## Phase 8 — Audio
- Background music per location
- Sound effects (footsteps, combat, UI)
- ACM → MP3 pipeline integrated

---

## Phase 9 — UI Theme System
- Theme switcher in options menu
- New Vegas theme (default)
- Classic DarkFO theme
- All UI components themed

---

## Phase 10 — Polish & Deploy
- Loading screen
- Save/load game
- Performance optimization
- Final Netlify deploy