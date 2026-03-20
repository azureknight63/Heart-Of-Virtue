# QA Report — Happy Path, Dark Grotto → Verdette Caverns
**Date:** 2026-03-20 (updated)
**Branch:** `claude/demo-deployment-prep-XnfPl`
**Scope:** Full story happy path — Dark Grotto Ch.1 through Verdette Caverns Ch.2 entry
**Auth mode:** Test session bypass (`POST /api/test/session`) — Turso DB unavailable
**Commits:** 73435e2 (3 fixes), 8454f54 (1 fix)

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

**Overall: 4 bugs fixed. 3 open issues remain.**

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

### ISSUE-006 — Victory dialog re-appears on page reload (cosmetic)
**Severity:** Low
**Symptom:** After closing the Victory dialog, navigating or reloading the page causes it to reappear.
**Root cause:** `lastEndStateId` is React `useState` — not persisted. On re-mount, `end_state` still present and `lastEndStateId` resets to `null`.
**Fix approach:** Persist `lastEndStateId` in `localStorage`, or clear `end_state` server-side once acknowledged.

---

### ISSUE-008 — Rock Rumbler AI stops attacking at high beat counts
**Severity:** Medium
**Symptom:** After ~150+ combat beats, Rock Rumblers loop between Advance/Rest/Dodge and never execute Attack. Jean's HP stops decreasing even when adjacent. Observed during prolonged wave combat.
**Repro:** Let combat run to beat 150+ via repeated Wait moves. Rumblers exhibit the loop after initial attacks land.
**Root cause:** Unknown — possibly a fatigue system issue where the Rumbler AI's preferred moves (Attack) have high fatigue cost and the Rumbler runs low on fatigue, defaulting to rest/maneuver. Or a position/distance calculation bug causing the attack range check to never pass.
**Action needed:** Investigate NPC AI move selection logic at high beat counts / low fatigue.

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

---

## Recommended Next Steps

1. **Configure Turso** or add SQLite fallback to unblock real user registration (ISSUE-001)
2. **Investigate HP overflow** (ISSUE-003) — `player.hp > player.max_hp` at game start
3. **Fix Victory dialog replay** (ISSUE-006) — persist `lastEndStateId` in localStorage
4. **Investigate Rock Rumbler AI loop** (ISSUE-008) — NPC stops attacking at high beat counts
5. **Name Verdette Caverns tiles** — (2,1) shows "Map Tile"; set `name` in map data
6. **Accessibility pass** on combat move panels — convert cursor-pointer divs to `<button>` elements
7. **Continue QA** from Verdette Caverns (2,2) — interact with Gorran NPC, explore exits (southeast, southwest), find Chapter 2 story beats
