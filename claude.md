# Fallout Browser Clone — Project Context for Claude

## Project Goal
Build a Fallout 2 browser-based clone using DarkFO as the foundation.
DarkFO is an existing TypeScript reimplementation of the Fallout 2 engine.

## Stack
- **Engine base**: DarkFO (TypeScript) — located in `darkfo/`
- **Assets**: Converted Fallout 2 assets in `public/assets/`
- **Build**: Vite + TypeScript
- **Deploy**: Netlify
- **No framework**: DarkFO uses its own renderer, NOT Phaser

## Repo Structure
darkfo/ ← DarkFO engine source (our main codebase)
public/assets/
art/ ← converted FRM sprites (PNG)
data/ ← JSON data (proto, text)
maps/ ← converted MAP files (JSON)
DarkFO reference/darkfo-master/ ← original DarkFO for reference only
src/ ← old Phaser code (ignore/deprecate)
docs/ ← design documents
scripts/ ← Python asset conversion scripts


## Asset Path Convention
Fallout 2 assets are served from `public/assets/`.
In code, reference them as `assets/art/...`, `assets/maps/...` etc.

## Rules
- Push all changes directly to main — no pull requests
- DarkFO is the base — do not use Phaser
- Keep the old `src/` folder but do not add new code there
- Always check `darkfo/` before writing new engine code
