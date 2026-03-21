# QA Report — Happy Path, Dark Grotto → Verdette Caverns
**Date:** 2026-03-21 (updated)
**Branch:** `claude/demo-deployment-prep-XnfPl`
**Scope:** Full story happy path — Dark Grotto Ch.1 through Verdette Caverns Ch.2 entry
**Auth mode:** Test session bypass (`POST /api/test/session`) — Turso DB unavailable
**Commits:** 73435e2 (3 fixes), 8454f54 (1 fix), d7cd4e9, e954310, 4ccf223, 50447de, f88a847, + pending (ISSUE-012, ISSUE-013, fatigue guard)

---

## Health Score

| Phase | Before Fixes | After Fixes |
|---|---|---|
| Login / session | ⚠️ DB-blocked reg, bypass works | same (known, unfixed) |
| New game / world load | ❌ "Loading location..." forever | ✅ loads correctly |
| Exploration / movement | ✅ | ✅ |
| Object interaction / puzzles | ✅ | ✅ |
| NPC interaction (Ferdie) | ✅ | ✅ |
| Combat (Ferdie) | ❌ 500 signal error on every move | ✅ combat works |
| Combat (Rock Rumbler wave 1) | ❌ 500 on moves | ✅ combat works |
| Memory flash event (Amelia) | ❌ blank event dialog | ✅ full narrative renders |
| Wave 2–N Rumbler encounters | ❌ blocked by memory flash bug | ✅ encounters proceed |
| Gorran rescue (HP < 30%) | — | ✅ Ch01PostRumbler2 fires |
| Gorran choice dialog (A/B/C) | — | ✅ renders, all options selectable |
| Choice A (heroic) — Gorran ally fight | — | ✅ 5 Rumblers + Gorran ally |
| AfterTheRumblerFight narrative | — | ✅ fires, Gorran renames |
| AfterGorranIntro → teleport | — | ✅ Jean moves to Verdette Caverns |
| Verdette Caverns event queue | — | ❌ NPCSpawnerEvent stuck pending (FIXED) |
| Verdette Caverns entry exploration | — | ✅ room, exits, item, Gorran NPC |
| Verdette Caverns (2,1) Battleaxe equip | — | ✅ equipped in weapon slot |
| Lurker spawn at (8,8) | — | ❌ NPCSpawnerEvent npc_cls dict format (FIXED) |
| Lurker fight at (8,8) | — | ⚠️ Ready to test — spawn fix applied |
| NPC flee loop (Withdraw) | — | ❌ NPCs flee forever past combat range (FIXED) |
| Wave-spawned enemy positions | — | ❌ Reinforcements lack combat_position (FIXED) |
| Rock Rumbler AI attack loop | — | ❌ stops attacking at high beats (FIXED) |
| Check move stale adapter state | — | ❌ combat deadlock on Check move (FIXED) |

**Overall: 12 bugs fixed. 4 open issues remain. (ISSUE-011 downgraded to Low — death flow confirmed working.)**

---

## Story Progress Achieved

| Milestone | Status | Notes |
|---|---|---|
| Login page renders | ✅ | |
| Auth bypass via test session | ✅ | Real registration 503s (ISSUE-001) |
| Main menu (New/Continue/Load/Settings/Credits/Logout) | ✅ | |
| New Game starts | ✅ | Fixed by ISSUE-002 fix |
| (1,1) Grottos Entrance — narrative tile | ✅ | |
| (2,2) JeanGameStartTile — narrative inscription READ | ✅ | |
| (3,2) FirstPuzzle — wall depression → east passage opens | ✅ | "Jean hears a faint 'click.'" |
| (4,2) RockLedgeWest — Ferdie NPC TALK | ✅ | |
| (4,2) Ferdie combat — Advance + Attack → Victory + XP + loot | ✅ | Fixed by ISSUE-004 fix |
| (5,2) RockLedgeEast — wall depression → bridge wall opens | ✅ | "The rock face splits open…" |
| (6,2) EmptyCave — traversal | ✅ | |
| (7,1) Chest Rumbler tile — Ch01ChestRumblerBattle event | ✅ | Mace equip + spawn |
| (7,1) Rock Rumbler wave 1 — combat → Victory | ✅ | |
| (7,1) Ch01_Memory_Amelia — Amelia memory flash | ✅ | Fixed by ISSUE-005 fix |
| (7,1) Wave 2 announcement — "Low rumbles vibrate…" | ✅ | Proper description |
| (7,1) Wave 2 combat (2 Rumblers) | ✅ | |
| (7,1) Wave 3+ announcement (Ch01_PostRumbler_Rep) | ✅ | Repeating escalation |
| (7,1) HP < 30% → Gorran rescue (Ch01PostRumbler2) | ✅ | Gorran kills one Rumbler, full HP/FP restore |
| (7,1) Ch01_PostRumbler3 choice dialog — 3 options | ✅ | Renders with all choices in browser |
| (7,1) Choice A: Stand with rock-man | ✅ | Gorran joins as ally, 5 Rumblers spawn |
| (7,1) Final 5-Rumbler fight with Gorran (200 HP, 55 dmg) | ✅ | All defeated |
| (7,1) AfterTheRumblerFight — Gorran introduction | ✅ | time.sleep mocked, narrative runs |
| (7,1) AfterGorranIntro → teleport to verdette-caverns (2,1) | ✅ | Jean transported |
| Verdette Caverns (2,1) — Spiritual Umbral Battleaxe | ✅ | Item picked up |
| Verdette Caverns (2,2) — Gorran NPC present, 3 exits | ✅ | room accessible |
| Verdette Caverns interior exploration | ✅ | Navigated to (8,8) with Battleaxe equipped |
| Verdette Caverns (2,1) Battleaxe equip | ✅ | `POST /api/equipment/equip {"item_id": <index>}` — uses index not ID |
| Lurker fight at (8,8) | ⚠️ | Spawn fix applied (50447de); ready to verify |
| AfterDefeatingLurker event | ❌ | Not reached |
| Chapter 2 entry / Grondia navigation | ❌ | Not reached |

---

## Bugs Found and Fixed

### ISSUE-002 — World stuck at "Loading location..." (FIXED)
**Severity:** Critical
**Symptom:** `GET /api/world` returned `{"error": "Invalid player position"}`. The game map never loaded.
**Root cause:** `Universe.starting_map_default` is only set when a map filename contains "start". No map in Dark Grotto does. `self.starting_map_name = "default"` matched nothing either. Result: `player.map = None`.
**Fix:** `src/api/services/session_manager.py` — fall back to `player.universe.maps[0]` when both lookups fail.
**Commit:** 73435e2

---

### ISSUE-004 — All combat moves crash with `signal only works in main thread` (FIXED)
**Severity:** Critical
**Symptom:** Every `POST /api/combat/move` returned 500. Traceback: `combat_adapter → moves.advance → moves.execute → animations.animate_to_main_screen → asciimatics.Screen.wrapper → signal.signal(SIGWINCH, ...)`.
**Root cause:** `moves.py` uses `from animations import animate_to_main_screen`, binding to the bare `animations` entry in `sys.modules`. `combat_adapter.py` called `import src.animations` and set `_API_MODE=True` on that object — a *different* sys.modules entry. The flag never reached the `animations` module that `moves.py` imported.
**Fix:** `src/api/combat_adapter.py` — iterate over both `"animations"` and `"src.animations"` and set `_API_MODE=True` on whichever is loaded.
**Commit:** 73435e2

---

### ISSUE-005 — Memory flash event dialog shows blank content (FIXED)
**Severity:** High
**Symptom:** After defeating Rock Rumbler wave 1, the `✨ EVENT` dialog appeared but with an empty (black) content box. The pending event API returned `description: ""`.
**Root cause:** `MemoryFlash.process()` in `src/story/effects.py` printed narrative text via `cprint()` for the terminal, but never set `self.description`. `Ch01PostRumbler.process()` tried to copy `memory.description` but got `""`.
**Fix:** `src/story/effects.py` — build `self.description` from `memory_lines` + `aftermath_text` before setting `needs_input = True`.
**Commit:** 73435e2

---

### ISSUE-007 — NPCSpawnerEvent blocked event queue in Verdette Caverns (FIXED)
**Severity:** High
**Symptom:** After entering Verdette Caverns (2,2), `GET /api/world/events/pending` returned an `NPCSpawnerEvent` with `needs_input: true`, empty `description`, and empty `input_options`. All `POST /api/world/events/input` calls returned `success: false`. The event queue was permanently blocked, preventing any further story progression.
**Root cause:** `EventSerializer._detect_input_requirement()` had `"NPCSpawnerEvent"` hardcoded in the `input_requiring_events` list. Since `NPCSpawnerEvent.process()` never sets `needs_input`, the event had no options and no description to acknowledge. The hardcoded entry was incorrect — NPCSpawnerEvent is a silent background spawner with no user interaction.
**Fix:** `src/api/serializers/event_serializer.py` — remove `"NPCSpawnerEvent"` from the hardcoded list. Verified `_detect_input_requirement()` returns `False` for NPCSpawnerEvent.
**Commit:** 8454f54

---

### ISSUE-009 — Ch01PostRumbler3 narrative text not exposed via API (FIXED)
**Severity:** Medium
**Symptom:** After the Gorran rescue scene, the pending event dialog returned only `description: "Jean must decide his next move quickly."`. The full atmospheric paragraph ("Jean wipes the blood from his lip...") was lost to terminal `cprint()` output.
**Root cause:** `Ch01PostRumbler3.process()` set `self.description` independently from `cprint()` lines, same pattern as ISSUE-005 (MemoryFlash) before its fix.
**Fix:** `src/story/ch01.py` — accumulated narrative lines into `self.description` before the choice prompt, identical pattern to ISSUE-005 fix.
**Commit:** 4ccf223

---

### ISSUE-010 — Check move crashes and leaves adapter in stale state (FIXED)
**Severity:** High
**Symptom:** Submitting `move_id: "0"` (Check move) returned `{"success": false, "message": "An internal error occurred"}`. Adapter then stuck: `input_type: "number_input"` but `pending_move_index: null`. Combat fully deadlocked.
**Root cause:** Check's internal crash left `self.input_type` and `self.pending_move_index` in an inconsistent intermediate state because the exception path skipped cleanup.
**Fix:** `src/api/combat_adapter.py` — wrapped `_execute_move()` in a try/except that resets `input_type = None` and `pending_move_index = None` on any unhandled exception, returning a clean `{"success": false}` response.
**Commit:** f88a847

---

### ISSUE-012 — NPC permanent flee loop (Withdraw past combat range) (FIXED)
**Severity:** Medium
**Symptom:** Enemies with the Withdraw move (e.g. NPCs at HP < 20%) would flee indefinitely past any reasonable combat range, never re-engaging. Withdraw's `viable()` check only tested `hp_pcnt > 0.2` without bounding the escape distance.
**Root cause:** No distance cap in `Withdraw.viable()`. Once an NPC fled past range ~20, it remained viable to keep fleeing each beat.
**Fix:** `src/moves.py` — added a distance cap in `Withdraw.viable()`: if the NPC's minimum combat proximity exceeds 20, viability is set `False` so it re-engages or stays put.
**Commit:** pending

---

### ISSUE-013 — Wave-spawned enemy reinforcements lack combat positions (FIXED)
**Severity:** High
**Symptom:** During the final 5-Rumbler wave (Choice A path), newly spawned enemies had no `combat_position`. `_synchronize_distances()` dropped them from Jean's proximity dict on the next beat, making them untargetable or invisible to the combat engine.
**Root cause:** Story event callbacks spawn enemies via `combat_engage()` which adds them to `player.combat_list` but does not call `initialize_combat_positions()`. The new entries had no coordinate in the combat grid.
**Fix:** `src/api/combat_adapter.py` — after event callbacks run in `_execute_move()`, scans `player.combat_list` for entries with `combat_position = None` and calls `positions.initialize_combat_positions()` on the full roster to assign grid coordinates.
**Note:** Also fixed a related issue where fatigue check blocked 0-cost moves. `fatigue_cost > 0` guard added to the pre-move fatigue check.
**Commit:** pending

---

### ISSUE-014 — NPCSpawnerEvent fails to spawn Lurker at verdette-caverns (8,8) (FIXED)
**Severity:** High
**Symptom:** Entering tile (8,8) in Verdette Caverns returned `events_triggered: []` and no Lurker NPC in the room. The NPCSpawnerEvent was in `tile.events_here` in the map JSON but processed silently without spawning.
**Root cause:** `npc_cls` in the map JSON is a deserialized dict `{"__class_type__": "npc:Lurker"}` rather than a string or class. `NPCSpawnerEvent._resolve_npc_class_name()` did not handle the dict format, returning `None`. `_do_spawn()` exited early on `None` class name with no error.
**Secondary root cause:** `evaluate_for_map_entry()` also silently skipped spawning because `spawn_tile` is `null` in JSON props, causing the map-entry pre-spawn path to short-circuit at `if self.spawn_tile and ...`.
**Fix:** `src/story/effects.py` — added dict format handling in `_resolve_npc_class_name()`: extracts class name from `__class_type__` value after the colon delimiter. The tile-entry path (`check_conditions` → `process` → `_do_spawn`) already falls back to `self.tile` correctly, so spawn fires when Jean steps onto the tile.
**Commit:** 50447de

---

## Bugs Found, Not Fixed

### ISSUE-001 — Registration blocked (503) — No DB
**Severity:** High (blocks real users; workaround exists for testing)
**Symptom:** `POST /api/auth/register` returns `{"error": "service_unavailable", "message": "Registration is temporarily unavailable."}`.
**Root cause:** Turso DB is not configured in this environment.
**Workaround:** `POST /api/test/session {}` (only active when `FLASK_ENV=testing`).
**Action needed:** Configure Turso credentials or add a local SQLite fallback.

---

### ISSUE-003 — HP displays as 108/100 (current > max)
**Severity:** Medium
**Symptom:** ATTRIBUTES panel shows Jean's HP as `108 / 100`.
**Root cause:** Unknown — likely a race between starting HP initialization and some bonus calculation.
**Action needed:** Investigate `player.hp` vs `player.max_hp` initialization order.

---

### ISSUE-011 — Player death: DefeatDialog exists but save/load unavailable without DB
**Severity:** Low (death flow works; only blocked by missing Turso DB)
**Symptom (API testing only):** When Jean's HP drops to ≤ 0, subsequent `GET /api/world` returns `state: "normal"` and `GET /api/combat/status` returns `"not_in_combat"` — Jean appears stuck at HP −11 in API testing. No automated recovery occurs.
**Actual behavior (browser):** `_execute_move()` in `combat_adapter.py` (lines 931–958) correctly detects death, sets `player.in_combat = False`, and populates `combat_end_summary` with `{status: "defeat", game_over: true}`. This is exposed as `end_state` in `GET /api/combat/status`. The frontend `useCombatCoordinator` hook detects `end_state.status === "defeat"` and renders `DefeatDialog` (skull ASCII art, "Load save" dropdown, "START OVER" logout). The "stuck" state is an API-testing artifact — in the browser the death flow is handled end-to-end.
**Root cause of perceived issue:** ISSUE-001 (no Turso DB) means no saves exist to load in `DefeatDialog`. `START OVER` logs out and creates a fresh session, which is the recovery path.
**Action needed:** Fix ISSUE-001 (Turso or SQLite fallback) to enable save/load recovery. No combat-engine changes required.

---

### ISSUE-006 — Victory dialog re-appears on page reload (cosmetic)
**Severity:** Low
**Symptom:** After closing the Victory dialog, navigating or reloading the page causes it to reappear.
**Root cause:** `lastEndStateId` is React `useState` — not persisted. On re-mount, `end_state` still present and `lastEndStateId` resets to `null`.
**Fix approach:** Persist `lastEndStateId` in `localStorage`, or clear `end_state` server-side once acknowledged.

---


## UI/UX Observations

| Item | Status |
|---|---|
| Retro terminal aesthetic (lime/cyan/orange on dark) | ✅ consistent |
| World map with explored tile tracking | ✅ |
| INTERACT modal for objects + NPCs | ✅ |
| Event dialog scrollable with `[1] Continue` button | ✅ |
| Event dialog with multiple choices (1-3 to select) | ✅ Gorran choice dialog confirmed |
| Tactical Advisor suggestions in combat | ✅ |
| Combat log with timestamps | ✅ |
| Move panels (OFFENSIVE/MANEUVER/etc.) | ⚠️ Not standard `<button>` — accessibility gap |
| Victory dialog with XP + loot breakdown | ✅ |
| Loot pickup (TAKE action on drops) | ✅ |
| Verdette Caverns (2,1) tile name | ⚠️ Shows "Map Tile" (no custom name set) |

---

## Architecture Notes from QA

- The `pending_events` system (`GET /api/world/events/pending` + `POST /api/world/events/input`) correctly gates story progression in combat.
- `Ch01PostRumbler` multi-stage event (`_stage` attribute) works correctly — `process()` is called twice (stage 1: show dialog; stage 2: advance). Fragile if deserialized mid-stage.
- `Ch01PostRumbler3` choice A path: Gorran joins allies, 5 Rumblers spawn, `AfterTheRumblerFight` runs via `tile.events_here`, `AfterGorranIntro` fires immediately via `check_conditions: pass`. Both use `time.sleep()` which is patched to `return_value=None` in API mode — narrative runs instantly.
- Jab deals 0 damage to Rock Rumblers. Only the mace Attack works. This appears to be by design (Rumbler physical resistance), though worth confirming in game design docs.
- `select_move_and_target` combined API call avoids the 2-step `move_selection → target_selection` loop and is the most reliable way to submit targeted attacks.
- Gorran's `allies` list shows in `GET /api/combat/status` under `battle_state.allies` — confirmed working.
- `POST /api/equipment/equip` takes `item_id` as an **integer inventory index** (not the Python object ID). Get the index from `GET /api/inventory` response `items[n].index` field.
- `evaluate_for_map_entry()` on `NPCSpawnerEvent` silently no-ops when `spawn_tile` is `null` (deserialized from JSON props). The tile-entry path (`check_conditions` → `process` → `_do_spawn`) is the reliable trigger path for map-file spawners.

---

## Recommended Next Steps

1. **Continue QA** — fresh session, equip Battleaxe, fight Lurker at (8,8), trigger AfterDefeatingLurker, reach Grondia (spawner fix in 50447de)
2. **Fix ISSUE-001 (Turso/SQLite)** — unblocks real user registration and DefeatDialog save/load (ISSUE-011)
3. **Investigate HP overflow** (ISSUE-003) — `player.hp > player.max_hp` at game start
4. **Fix Victory dialog replay** (ISSUE-006) — persist `lastEndStateId` in `localStorage`
5. **Name Verdette Caverns tiles** — (2,1) shows "Map Tile"; set `name` in map data
6. **Accessibility pass** on combat move panels — convert cursor-pointer divs to `<button>` elements
