# CLAUDE.md — Project Rules & Context

## What this project is
A browser-based Fallout 1 remake built on top of DarkFO (a Fallout 2 engine reimplementation in TypeScript).
We are adapting DarkFO for Fallout 1 assets and adding our own features on top.

## Tech Stack
- TypeScript + Vite
- Phaser 3 (rendering + input)
- DarkFO (reference engine in /darkfo/)
- Netlify (deployment)

## DarkFO Usage Rules
1. DarkFO code is in /darkfo/ — use it, adapt it, or replace it
2. Priority order:
   - DarkFO has it and it works → use/adapt it
   - DarkFO has it but it's broken/outdated → modernize it
   - DarkFO doesn't have it → write it fresh
3. Never rewrite working DarkFO code just for the sake of it

## Git Rules
- NEVER create pull requests
- ALWAYS push directly to main
- NEVER delete or overwrite files in public/assets/

## What we kept from v1
- Mousewheel zoom
- Arrow key scrolling + mouse-at-edge scrolling
- Static HUD (two-camera system)
- SPECIAL character creation system
- Dialogue system (JSON-driven)

## UI Theme System
- Default theme: New Vegas style (from v1)
- Alternative: Classic DarkFO style
- Switchable via in-game options menu
- All UI components must support theming

## Asset Rules
- Raw Fallout 1 assets stay LOCAL only (gitignored)
- Only converted assets (PNG, JSON, MP3) go to GitHub
- Asset pipeline scripts are in /scripts/