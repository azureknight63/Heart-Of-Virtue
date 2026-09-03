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
| `frontend/src/hooks/useSpriteManifest.js` | Fetches the manifest once per page load (a missing manifest settles too and is never refetched) and re-validates every file path and frame count |
| `frontend/src/utils/sprites.js` | `spriteFor`, `spriteClipFor`, `facingRow`, `terrainTileUrl` |
| `frontend/src/components/SpriteToken.jsx` | Plays a clip from a strip (percentage background-position, east = mirrored west) |
| `frontend/src/components/BattlefieldGrid.jsx` | `CombatantMarker` swaps glyph for `SpriteToken`; `TerrainLayer` swaps fills for tiles |
| `src/api/serializers/combat.py` | `sprite_key` on every serialized combatant: `jean` for the player, else the NPC class's own `sprite_key` attribute (to share a sheet or alias a story-gated identity) or its class name lower-cased |
| `src/terrain.py` `REGION_PALETTES` | Which art variant each terrain kind takes per region; the tileset prompts are generated from it |

Guards: `tests/test_art_pipeline.py` (prompt pack <-> engine palettes, intake
slicing, committed manifest points at real files) and
`frontend/src/test/spriteManifest.test.js` (same manifest check from the
client side, plus clip names the renderer knows).

## Sheet spec

* Frame: 64 x 64 px after intake. Deliveries can be any size up to 4096 px a
  side: cells are found by dividing the image evenly, the magenta gaps and
  background are keyed to transparency, then the whole sheet is cropped by
  one box (the union of every cell's content) and scaled by one factor, so
  relative size and the shared feet baseline survive intake and frames do
  not pulse. Delivered file names must name a roster slug and a known clip;
  anything else is refused.
* Facings: three rows, **south, west, north**. East is the west row mirrored.
* Clips and frame counts: idle 4, walk 6, attack 6, cast 6, defend 4, hurt 3,
  death 6. One image per clip (`<slug>__<clip>.png`), rows = facings,
  columns = frames, hairline magenta (#FF00FF) gaps and background.
* Clip selection in play (`spriteClipFor`): dying -> death; hit landing ->
  hurt; source of a defend animation -> defend, of a buff/debuff/drain/heal/
  pulse/shockwave -> cast, of a dash (every movement move) -> walk, of any
  other animation type -> attack; a pending Dodge/Parry/Brace -> defend; a
  pending Advance/Withdraw/Retreat/Flank/Charge/Positioning/Swap/Take Ground
  -> walk; else idle. Loops (idle, walk) cycle at the clip's frame rate scaled
  by the player's combat speed; one-shots hold their last frame.

## Tileset spec

One image per region (`tileset__<region>.png`): a single row of tiles in the
order listed in `tileset-<region>.md`, i.e. the insertion order of
`REGIONS[region]["variants"]` in `tools/art_prompts.py` (floor, rough, hazard,
shelf, boulder, wall, cliff). `src/terrain.py`'s `REGION_PALETTES` must carry
the same variant *set* (the test checks both directions); its order does not
matter. Each tile is trimmed to its content before resizing so the keyed-out
gap never becomes a seam. Tiles must be seamless and low-contrast enough to
sit under a sprite. Once a region's tileset is in the
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
real sheets are taken in; re-running `placeholders` never overwrites delivered
art unless `--force` is given. `validate` lists them separately from real art
and also flags a strip whose size disagrees with its manifest entry.

## Adding a combatant or region

1. Add the NPC to `ROSTER` in `tools/art_prompts.py`. The slug must be what
   `CombatantSerializer.sprite_key` emits for it: the class name lower-cased,
   or the class's own `sprite_key` attribute if it declares one.
2. For a new region, add its palette to `src/terrain.py` `REGION_PALETTES`
   (and a `REGION_LABELS` entry) and its tile descriptions to `REGIONS` in
   `tools/art_prompts.py` with the cliff variant listed last -- the
   `test_region_palettes_match_the_engine_both_ways` test fails until every
   engine region has a matching prompt entry and vice versa.
3. Regenerate the prompt pack and commit it.
