# QA Report — Happy Path, Dark Grotto
**Date:** 2026-03-20
**Branch:** `claude/demo-deployment-prep-XnfPl`
**Scope:** Full story happy path, web UI (Flask API + React/Vite)
**Auth mode:** Test session bypass (`POST /api/test/session`) — Turso DB unavailable

---

## Health Score

| Phase | Before Fixes | After Fixes |
|---|---|---|
| Login / session | ⚠️ DB-blocked reg, bypass works | same (known, unfixed) |
| New game / world load | ❌ "Loading location..." forever | ✅ loads correctly |
| Exploration / movement | ✅ | ✅ |
| Object interaction | ✅ | ✅ |
| NPC interaction (Ferdie) | ✅ | ✅ |
| Combat (Ferdie) | ❌ 500 signal error on every move | ✅ combat works |
| Combat (Rock Rumbler wave 1) | ❌ 500 on moves | ✅ combat works |
| Memory flash event (Amelia) | ❌ blank event dialog | ✅ full narrative renders |
| Wave 2 Rumbler encounter | ❌ blocked by memory flash bug | ✅ encounter proceeds |

**Overall: 3 blocking bugs fixed. 1 known infrastructure issue remains (DB).**

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
| (2,3) EmptyCave — items present | ✅ (not visited in UI, confirmed via map) | |
| (5,2) RockLedgeEast — wall depression → bridge wall opens | ✅ | "The rock face splits open…" |
| (6,2) EmptyCave — traversal | ✅ | |
| (7,1) Chest Rumbler tile — Ch01ChestRumblerBattle event | ✅ | Mace equip + spawn |
| (7,1) Rock Rumbler Asabcel — combat → Victory | ✅ | One-shot (30 dmg) |
| (7,1) Ch01_Memory_Amelia — Amelia memory flash | ✅ | Fixed by ISSUE-005 fix |
| (7,1) Wave 2 announcement — "Low rumbles vibrate…" | ✅ | |
| (7,1) Wave 2 combat (Racora + Qerun) | 🔄 in progress | Story continues here |

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
**Symptom:** After defeating Rock Rumbler Asabcel, the `✨ EVENT` dialog appeared but with an empty (black) content box. The pending event API returned `description: ""`.
**Root cause:** `MemoryFlash.process()` in `src/story/effects.py` printed narrative text via `cprint()` for the terminal, but never set `self.description`. `Ch01PostRumbler.process()` tried to copy `memory.description` but got `""`.
**Fix:** `src/story/effects.py` — build `self.description` from `memory_lines` + `aftermath_text` before setting `needs_input = True`.
**Commit:** 73435e2

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
**Root cause:** Unknown — likely a race between starting HP initialization and some bonus calculation. Not investigated further.
**Action needed:** Investigate `player.hp` vs `player.max_hp` initialization order.

---

### ISSUE-006 — Victory dialog re-appears on page reload / navigation (cosmetic)
**Severity:** Low
**Symptom:** After closing the Victory dialog (Ferdie fight), navigating or reloading the page causes the same Victory dialog to reappear.
**Root cause:** `lastEndStateId` is React `useState` — not persisted. On re-mount, `end_state` is still present in the combat status response, `lastEndStateId` resets to `null`, and the dialog re-triggers.
**Fix approach:** Either (a) persist `lastEndStateId` in `localStorage`, or (b) clear `end_state` server-side once acknowledged. No combat breaks from this; it's a UX annoyance.

---

## UI/UX Observations

| Item | Status |
|---|---|
| Retro terminal aesthetic (lime/cyan/orange on dark) | ✅ consistent |
| World map with explored tile tracking | ✅ |
| INTERACT modal for objects + NPCs | ✅ |
| Event dialog scrollable with `[1] Continue` button | ✅ |
| Tactical Advisor suggestions in combat | ✅ |
| Combat log with timestamps | ✅ |
| Move panels (OFFENSIVE/MANEUVER/etc.) as @c refs | ⚠️ Not standard `<button>` — accessibility gap |
| Victory dialog with XP + loot breakdown | ✅ |
| Loot pickup (TAKE action on drops) | ✅ |

---

## Architecture Notes from QA

- The `pending_events` system (`GET /api/world/events/pending` + `POST /api/world/events/input`) works correctly for story gating.
- The `delay_mode: "combat"` in events correctly pauses combat moves until the event is acknowledged.
- `combat_active: True` persists briefly after all enemies die (backend doesn't immediately flip it); the frontend correctly transitions out of combat view once `end_state` appears.
- `Ch01PostRumbler` uses a multi-stage pattern (`_stage` attribute) — this works but is fragile if the event is serialized/deserialized mid-stage.

---

## Recommended Next Steps

1. **Configure Turso** or add SQLite fallback to unblock real user registration (ISSUE-001)
2. **Investigate HP overflow** (ISSUE-003) — `player.hp > player.max_hp` at game start
3. **Fix Victory dialog replay** (ISSUE-006) — persist `lastEndStateId` in localStorage
4. **Accessibility pass** on combat move panels — convert cursor-pointer divs to `<button>` elements for keyboard nav / screen reader support
5. **Test wave 2 combat** completion to verify `Ch01PostRumbler` stage 3+ (the full rumbler wave sequence)
