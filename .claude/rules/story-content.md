---
paths:
  - "src/story/**"
  - "src/events.py"
  - "src/tiles.py"
  - "src/objects.py"
  - "src/map_placeholders.py"
  - "src/resources/maps/**"
  - "src/resources/books/**"
  - "src/resources/outline.md"
  - "docs/lore/**"
---

# Story, maps, and content rules

**Canon:** `docs/lore/` (character profiles, enemies, creatures, environments, story arcs) and `src/resources/outline.md` (chapter spine). Read the relevant profile before writing a line of dialogue; `/narrative-review` audits implementation against these docs. A contradiction with lore is a bug, not a stylistic choice. New regions start from `/map-design` → `docs/lore/environments/<region>/<region>-map-design.md`; map audits → `<map>-audit-report.md`.

## Story events (`src/story/ch0N.py`)
- Events subclass `src.events.Event` (memory flashes: `src/story/effects.py`'s `MemoryFlash`). Output goes through the narration sink — `cprint`, `narrate`, `say`, `begin_conversation`, `enter_op`/`exit_op`, `react` from `src.narration`. Never `print`, never `input()`.
- `narrate(*parts, color=None)` joins like `print` and color is **keyword-only**; `cprint(text, color)` is positional. A `narrate()` split can drop a sentence — re-read the output when converting prose.
- Staged portrait dialogue: `begin_conversation(cast)` then `say()` per beat. Each stage that needs input hands the client a fresh `segments` array; the frontend resets per stage, so an event may call `begin_conversation()` more than once across `process_event_input` round-trips — but every stage-exit op needs its fade `span`, and the **canonical speaker id must not leak onto a portrait before the in-fiction naming beat** (the Gorran/Votha Krr spoiler lesson). Recurring casts go in a module-level constant (`_JEAN_SOLO`).
- Multi-stage events: the API mints a new `event_id` per stage; persist progress in story state so an event can't re-trigger across sessions (`Ch01ChestRumblerBattle` fires only after the chest is looted, and stays fired).
- `skipdialog` / `testmode` / `skipintro` (`config_*.ini`) skip most descriptive prints and the intro — test both paths when an event branches on them.
- Exceptions raised inside tile events are swallowed by the event loop. If an event "doesn't fire", check the logs before assuming its conditions failed.
- `WhisperingStatue` is the model for an event that used to call `input()` directly and now uses the structured `needs_input` protocol.

## Maps (`src/resources/maps/*.json`)
- Maps are data. Tiles, exits, objects, NPC/item placements, and events belong in the JSON (schema: `docs/development/map-authored-placeholder-schema.md`), not in Python. `__module__` fields in map JSON store **bare** module names by contract — resolve with `functions.canonical_module_name()`; don't "fix" them to `src.` paths.
- `NPCSpawnerEvent.evaluate_for_map_entry` falls back to `self.tile` when `spawn_tile` is `None` (JSON deserialization) — map-entry spawners (Lurker etc.) depend on it, and on `GameService.move_player` calling `game_tick_events()` every move.
- Test maps: `combat-testing-arena.json` (arena), `testing-map.json`, `shop-testing.json`, `test-chest.json`; acceptance maps are 2-tile arenas from `tools/acceptance_test_generator.py`. A config must set `startmap` to reach them — they have no link from the main world.
- Tile caching: read `docs/TILE_CACHING.md` before changing tile load/serialize paths. `python tools/map_fuzzer.py` hardens loaders against malformed JSON.

## Design principles — apply to every tile
- **Lore first, mechanics second** — every tile has a reason rooted in the world.
- **Sensory prose** — touch, sound, smell, not just sight.
- **Environmental storytelling** — objects, items, NPCs tell history.
- **Progressive complexity** — early zones tight and readable; later zones layer mechanics.
- **Secrets reward curiosity** — at least one genuinely discoverable secret per map.
- **Narrative beats embedded** — story moments anchor to tiles, not separate cutscenes.
- **Descriptions are permanent** — tile text persists after NPCs are killed and items are taken. Never write present-tense NPC behaviour ("The bats are aware of Jean", "Gorran places his hand on the crystal", "The Rumblers move through the water") or item references ("The supplies left here") into a description; describe durable evidence — staining, claw marks, smells, worn stone, old fire rings.
- **Fair puzzles** — hidden passages and locked exits are hinted in tile/object text (the Dark Grotto wall depression is the model); no unwarned lethal tiles; a dead end with an interactable is a puzzle, not a bug.

## Books and text assets
`src/resources/books/*.txt` hold in-world book text (`Book.read` is non-interactive and paginated — `docs/book_pagination.md`). Long prose belongs in a data file, not a Python string, wherever a loader exists.
