# Battlefield art pipeline: sprites and terrain tilesets

The battlefield draws every combatant as an animated 3/4-top-down sprite and
every terrain cell from a per-region tileset. The art is generated outside the
repo (Gemini / Nano Banana 2) from a prompt pack this repo owns, then pulled in
by an intake tool that normalises it into what the frontend loads. Until a
sheet or tileset lands, the game falls back to the glyph token and the
procedural terrain fills, so the pipeline can be filled in piecemeal.

## Moving parts

| Piece | Role |
|---|---|
| `tools/art_prompts.py` | Source of truth for the spec (frame size, clips, facings, roster, region tile lists) and generator of the prompt pack |
| `docs/development/art-prompts/` | Generated prompts: `sprite-<slug>.md`, `tileset-<region>.md`, `pack.json`, `README.md` |
| `tools/sprite_intake.py` | Slices delivered PNGs into strips/tiles, keys out the magenta background, writes the manifest |
| `frontend/public/assets/sprites/manifest.json` | What exists: `sprites[slug].clips[clip] = {file, frames, rows}` and `terrain[region].tiles[variant]` |
| `frontend/public/assets/sprites/<slug>/<clip>.png` | 64 px strips: rows south/west/north, columns = frames |
| `frontend/public/assets/terrain/<region>/<variant>.png` | 64 px tiles |
| `frontend/src/hooks/useSpriteManifest.js` | Fetches the manifest once per page load |
| `frontend/src/utils/sprites.js` | `spriteFor`, `spriteClipFor`, `facingRow`, `terrainTileUrl` |
| `frontend/src/components/SpriteToken.jsx` | Plays a clip from a strip (percentage background-position, east = mirrored west) |
| `frontend/src/components/BattlefieldGrid.jsx` | `CombatantMarker` swaps glyph for `SpriteToken`; `TerrainLayer` swaps fills for tiles |
| `src/api/serializers/combat.py` | `sprite_key` on every serialized combatant (`jean` / NPC class name lower-cased) |
| `src/terrain.py` `REGION_PALETTES` | Which art variant each terrain kind takes per region; the tileset prompts are generated from it |

Guards: `tests/test_art_pipeline.py` (prompt pack <-> engine palettes, intake
slicing, committed manifest points at real files) and
`frontend/src/test/spriteManifest.test.js` (same manifest check from the
client side, plus clip names the renderer knows).

## Sheet spec

* Frame: 64 x 64 px after intake (deliveries can be any size; cells are found
  by dividing the image evenly and resampled nearest-neighbour).
* Facings: three rows, **south, west, north**. East is the west row mirrored.
* Clips and frame counts: idle 4, walk 6, attack 6, cast 6, defend 4, hurt 3,
  death 6. One image per clip (`<slug>__<clip>.png`), rows = facings,
  columns = frames, hairline magenta (#FF00FF) gaps and background.
* Clip selection in play (`spriteClipFor`): dying -> death; hit landing ->
  hurt; source of a strike-type animation -> attack, of a buff/debuff/drain/
  heal/pulse/shockwave -> cast, of a defend -> defend; pending Dodge/Parry/
  Brace -> defend; pending movement move -> walk; else idle. Loops (idle, walk)
  cycle; one-shots hold their last frame.

## Tileset spec

One image per region (`tileset__<region>.png`): a single row of tiles in the
order listed in `tileset-<region>.md` (the region's `REGION_PALETTES` variants:
floor, rough, hazard, shelf, boulder, wall, cliff). Tiles must be seamless and
low-contrast enough to sit under a sprite. Once a region's tileset is in the
manifest, the grid paints every cell of that region from it (open floor
included); before that, only feature cells are drawn, procedurally.

## Workflow

```bash
python tools/art_prompts.py                    # regenerate prompts after editing the spec
# ... generate images from docs/development/art-prompts/*.md ...
python tools/sprite_intake.py sheet   deliveries/jean__idle.png deliveries/jean__walk.png
python tools/sprite_intake.py tileset deliveries/tileset__verdette_caverns.png
python tools/sprite_intake.py validate         # complete / placeholder / missing / broken
python tools/sprite_intake.py placeholders --only slime   # procedural stand-in strips
```

Placeholder strips (currently committed for `jean`, `slime`, `gorran`) are
flagged `"placeholder": true` in the manifest and are replaced clip by clip as
real sheets are taken in. `validate` lists them separately from real art.

## Adding a combatant or region

1. Add the NPC to `ROSTER` in `tools/art_prompts.py` (slug = class name
   lower-cased, which is what `CombatantSerializer.sprite_key` emits).
2. For a new region, add its palette to `src/terrain.py` `REGION_PALETTES` and
   its tile descriptions to `REGIONS` in `tools/art_prompts.py` -- the
   `test_region_palettes_match_the_engine` test fails until both agree.
3. Regenerate the prompt pack and commit it.
