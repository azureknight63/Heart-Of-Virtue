# A3b report — post-King-Slime leg (Votha Krr / Eastern Gate / Eastern Descent)

## 1. Header

- Tester: A3b, stack `leg0924b`, API port 5003 (`config_qa_leg_0924.ini`)
- Start: pre-seeded, NOT played — Grondia (7,9) GrondelithEntrance, level 6, Gorran in party, `king_slime_defeated`/`lurker_defeated` *claimed* set by config, `votha_krr_response_given` NOT set. `Rare Mineral Fragment` (type `MineralFragment`) **is** present in inventory this run (confirmed via `/api/inventory` — `A3`'s Finding #1 fix landed: item now spawns via `starting_items`).
- Tool calls used: ~14 API calls (login, inventory ×2, gate interact ×1 + event-input ×1, move sequence ×2, `/api/world/events` ×2, `/api/status`/`where` ×2) plus source-reading (Read/Grep, not counted against the API budget). Stopped early — see Finding #1, a hard blocker one level deeper than A3's.
- Ended at: Grondia (10,5) Citadel, level 6, HP 120/120 (unchanged — no combat reached)
- Route completion: gate-lock quick-check only (step 1). Steps 2–5 (Citadel scene, gate opening, Eastern Descent, Nomad Camp entry) are **BLOCKED** — same symptom as A3 hit, but the actual root cause is different and more serious (see Finding #1).

## 2. Route checklist

| Step | Item | Result | Evidence |
|---|---|---|---|
| 1 | Walk (7,9) → (14,5) Antechamber → (15,5) Gate East | PASS | Path NE×4, E×4; tile titles confirmed each step (`Passage`→`Fabricarium`×2→`Ecumerium`×3→`Antechamber`→`Gate East`) |
| 1 | Interact with Eastern Gate (`enter`) — must still refuse | PASS | `POST /api/world/interact {"target_id":"da2cf5ad948546f7a0b164aa68756967","action":"enter"}` queued `Passage_Eastern Gate`; `POST /api/world/events/input {"user_input":"continue"}` → `"Jean runs a hand along the seam in the stone, but the gate gives no purchase — whatever seals it hasn't yielded yet."`, player stayed at (15,5). |
| 2 | Walk to Citadel (10,5), `AfterKingSlimeReturn` fires | **BLOCKED** | See Finding #1. `POST /api/world/events {}` at (10,5) returns `200`, zero pending events, both on first arrival and after an explicit re-trigger. Confirmed the `MineralFragment` (the thing A3 diagnosed as missing) **is present** this run — the event still does not fire. |
| 2 | Fragment leaves inventory / no `Ch02FragmentReminder` nag / no repeat on revisit | NOT REACHED | Scene never started. |
| 3 | Walk back to gate, Eastern Gate opens, teleport to eastern-descent (0,2) | NOT REACHED | Gate lock (`votha_krr_response_given`) can only be set by `AfterKingSlimeReturn` completing, which never starts. |
| 3 | `GorranGestureEvent` on arrival, quote prose | NOT REACHED | — |
| 3 | Walk back west through gate | NOT REACHED | — |
| 4 | Eastern Descent full breadth (all 30 listed tiles) | NOT REACHED | — |
| 5 | Enter Nomad Camp via Camp Entrance (3,6) | NOT REACHED | — |

## 3. Fix verification

- **#669** (Eastern Gate refuses until Votha Krr's post-King-Slime conversation): **PASS** (re-verified). Direct-interact path still refuses in-fiction, player stays at (15,5). Same behavior A3 already confirmed; only did the one quick check per assignment.
- A3's Finding #1 fix (adding `MineralFragment` to `config_qa_leg_0924.ini`'s `starting_items`): **item-grant part PASS** (fragment confirmed in inventory), but the fix **does not unblock the route** — see Finding #1 below. A3's diagnosis was a real but partial cause; there is a second, deeper defect underneath it.

## 4. Findings

### Finding #1 — `starting_story_flags` (config seed option) is parsed but never applied to the player's story state; it is dead code, not a data-entry gap

- **Severity**: Critical (silently defeats the entire flag-seeding mechanism used by at least two QA configs; also a genuine, currently-unused engine feature that does nothing if anyone else ever reaches for it)
- **Location**: `src/config_manager.py` (parses the option) and `src/api/services/session_manager.py::_create_player_for_session` (builds the session player — never touches it), affecting `src/story/ch02.py`'s `AfterKingSlimeReturn.check_conditions()`
- **Steps to reproduce** (from login):
  1. `A3b login 5003` — config comment and primer both assert `king_slime_defeated` and `lurker_defeated` are pre-set via `starting_story_flags = king_slime_defeated, lurker_defeated` (`config_qa_leg_0924.ini:14`).
  2. `GET /api/inventory` — confirms `Rare Mineral Fragment` / type `MineralFragment` IS present (this session's seed also lists it in `starting_items`, which — unlike `starting_story_flags` — *is* consumed).
  3. Walk to Grondia (10,5) Citadel.
  4. `POST /api/world/events {}` at (10,5) — `200`, `GET /api/world/events/pending` → `{"events": []}`. Re-triggered a second time (moved off-tile and back) with the same null result.
- **Expected**: With `king_slime_defeated` set and the fragment carried, `AfterKingSlimeReturn.check_conditions()` (`src/story/ch02.py:1521-1530`) should pass both its guards (`slime_defeated` true, `already_given` false, `_has_fragment()` true) and start the 7-stage Votha Krr scene.
- **Actual**: Nothing fires, with no error surfaced to the client.
- **Root cause (confirmed by source read, not guesswork)**: `Config.starting_story_flags` is populated by `ConfigManager` (`src/config_manager.py:328-335`, parsing the `starting_story_flags` ini key into a list), but a project-wide grep (`grep -rn "starting_story_flags\|config\.starting" src/ --include=*.py`, excluding a stale worktree copy under `.claude/worktrees/`) shows **the only two places this attribute is ever read are inside `config_manager.py` itself** — nothing in `session_manager.py::_create_player_for_session` (the method that actually builds a fresh `Player`/`Universe` and applies `starting_gold`, `starting_items`, `starting_level`, `starting_exp`, `learn_all_skills`, `god_mode`, `_apply_starting_equipment`, `_apply_starting_party_members`, etc.) ever writes into `player.universe.story`. Compare: `starting_items` *is* applied, via `_create_items_from_config()` at line 947 — that's why the fragment shows up but the flags don't. The consequence: `king_slime_defeated` (and `lurker_defeated`, and `votha_krr_response_given` on other configs) are **never actually set** on any session built from a config that relies on `starting_story_flags`, regardless of what the ini comment or a tester primer claims. `AfterKingSlimeReturn.check_conditions()` bails on its very first guard (`slime_defeated` gate false) before it ever gets to check the fragment — so A3's diagnosis (missing fragment) explained a real but secondary gap; the primary gap is that the flag option does nothing at all.
- **Blast radius beyond this tester**: `config_qa_camp.ini` (assigned to the `camp0924`/:5004 tester) uses the identical mechanism — `starting_story_flags = king_slime_defeated, votha_krr_response_given, lurker_defeated` (line 14) — to claim the Eastern Gate is already unlocked. It is not; that tester's session will have the same unset gates as this one, silently. Since that tester starts at (14,5) Antechamber rather than at the gate itself, they may not notice until/unless their route requires crossing it or hits a `GorranGestureEvent`/`AfterKingSlimeReturn` check elsewhere. Worth flagging to the orchestrator before that report is taken at face value.
- **Confidence**: High. Confirmed two independent ways: (a) static — `starting_story_flags` has zero consumers outside `config_manager.py` in the whole `src/` tree (checked, excluding an unrelated stale worktree copy of the same file under `.claude/worktrees/claude+fix-item-targeting-bug-1z8FT/`); (b) dynamic — with the fragment now genuinely present (ruling out A3's hypothesis as sufficient), the event still never fires, which is exactly what "the flag was never set" predicts and inconsistent with "the flag is set but something else is wrong."
- **Suggested fix**: `_create_player_for_session` (or a small helper called from it, near `_apply_starting_party_members`) needs to iterate `self.game_config.starting_story_flags` and call the same `set_story_gate(player, flag, "1")` (`src/events.py:112`, `GATE_SET = "1"`) that in-game events use, after `player.universe` exists. This is a `src/api/services/session_manager.py` engine-adjacent fix, not a config-only one — out of scope for me to make (ROOT is read-only for this tester), flagging for the orchestrator/dev.
- I did **not** use `/api/debug/*` to get past this — there is no debug route that can write a story gate (`routes/debug.py` only exposes player stat/level/attribute/heat/restore/skill and arena-roster ops), so there was no legitimate workaround available, consistent with A3's note on the same constraint.

## 5. Combat log summary

No combat was reached — the blocker in Finding #1 prevented reaching the Eastern Gate crossing and the Eastern Descent, where every assigned fight (RockRumbler, TalusHound×2, ScarpAdder, etc.) lives. None of the assigned tile/fight/item checklist in step 4 could be attempted.

## 6. Non-bug observations

- The `Passage_Eastern Gate` confirmation event is idempotent on repeated interaction, matching A3's note — no duplicate pending events stacked.
- Party gold read 355 at time of report (config seeds presumably lower) — same passive-gain artifact A3 flagged as not investigated; not re-investigated here either, just corroborated.
- The `config_qa_leg_0924.ini` header comment is well-intentioned but doubly wrong now: it explains the fragment hand-over mechanic accurately, but both it and A3's report assumed fixing the item grant would be sufficient. It would not have been, even before A3's fix — the flags were never live in the first place. Recommend the orchestrator re-test `leg0924`/`camp0924` (and any other config using `starting_story_flags`) only after `session_manager.py` actually consumes that config field.
