# FallCloneDarkFo2
npm run setup   # creates gitignored stubs (imageMap.json, pro.json) once
npm run dev     # launches Vite dev server
# Open http://localhost:5173/           → loads artemple (empty map)
# Open http://localhost:5173/?v13ent   → loads Vault 13 entrance map

%run convert_all.py "C:\Program Files (x86)\Steam\steamapps\common\Fallout 2" --out-dir "../converted_assets"