# Triage ledger — 2026-09-24 run

## Confirmed (to file)
1. **starting_story_flags is a dead config key on the web path** — Medium (dev/QA-blocking, no shipped impact).
   Source: parsed at src/config_manager.py:328-335; only consumer was src/game.py (311a644e), deleted in the
   terminal teardown; SessionManager._create_player_for_session never applies it (grep: zero readers of
   `config.starting_story_flags` in src/). Seen by A3 (indirectly), A3b (diagnosed), orchestrator (grep + shim
   verification: with game.py's semantics restored, camp session opens the #669 gate). Shipped config_prod.ini
   sets only `lurker_defeated`, which nothing in src/ reads -> no player impact. tests/test_prod_config.py
   pins the value but never that it lands on the story.
2. **Grondia interiors play the Mineral Pools BGM** — Low, possibly intentional. grondia-{conclave-archive,
   fabricarium-forge,guesthold,vacated-dwelling}.json metadata `bgm: mineral_pools` (authored in 1f78d3d7);
   Grondia proper falls back to `grondia` (game_service.py:1535-1551). A5 heard it in the Dwelling.

3. **Tactical Advisor recommends 0-damage attacks indefinitely** — Medium. A2 at Pools (2,4): Shortsword vs
   Stone Creature (slashing 0.4x + 27 protection) -> every Attack "did no damage", advisor kept scoring Attack
   80-90 for 150 turns; swapping to the mace won in 5. Source: `_score_move` (ai/combat_strategist.py:986-1070)
   scores Offensive moves from heat band only; the adapter already computes per-target
   `damage_preview {min,max,lethal}` (src/api/combat_adapter.py:4414-4449) that the scorer never reads.
   Pillar 3 ("every number is explainable") — the advice contradicts the numbers the UI can show.
4. **Server accepts /world/move at 0 HP after a defeat** — Low, API-only hardening (#682 family). Orchestrator:
   forced defeat (debug hp=1) vs Talus Hounds: end_state {defeat, game_over}; /world/move then 200 and Jean walks
   at 0 HP. UI verified safe: headless driver on :3000 — DefeatDialog ("START OVER") shows after reload and
   again after a second reload, no enabled Move buttons (shots runs/verify/V1_00{1,2,3}).
   Root cause (A1): `GameService.is_player_dead` (game_service.py:6600) is consulted only by
   `submit_event_input` (routes/world.py:364); `/world/move`, `/world/interact` and `/combat/*` never ask.
   A1 also reached it naturally (no debug): King Slime attempt 1 -> 0 HP, combat_active false, boss left at
   69/560 on the tile; A1 walked on and re-engaged — same defect, read without `end_state`.
5. **Advance reports "No one is out of reach" (already_adjacent) with enemies at 8-10** — Low, seen once (A2,
   Pools (3,3), at fight start, while Attack said "too far"). `Advance._unavailability_code`
   (src/moves/_movement.py:219-229) falls through to ALREADY_ADJACENT whenever no live combatant is recorded
   at distance > 1 — including an empty/unbuilt proximity map — so the code is a catch-all, not a measurement.

6. **Docs that describe things that aren't there** — Low (cleanup). (a) A1: src/story/ch03.py:416 says
   RiversEdge (1,0), :578 FireRing (1,1), :665 CampFarEdge (2,1); the map authors them at (1,2), (3,2), (3,4)
   (and :1188 already says (1,2)). (b) A4b: `POST /api/combat/move` docstring (routes/combat.py:87) advertises
   `move_type` "attack|defend|cast|item|swap_weapon"; `cast` and `item` don't exist ("Unknown move type",
   game_service.py:4060) and the real set (move, target, direction, number, attack, defend, cancel, flee,
   swap_weapon, select_move_and_target) is undocumented there. Both cost testers time.

7. **Wire fields that contradict the authoritative state (umbrella)** — Medium. None has a frontend reader,
   but together they produced 3 false Criticals this run, and (c) is simply wrong every time:
   (a) `battle_state.status` stays "active" after victory AND defeat while top-level `combat_active` is false
       (A2, A1, A4b; orchestrator VER1 twice). Misled A2 and A1 into "combat never ends"/"no death" Criticals.
   (b) `/world/move` into eastern-descent (6,4) RoadEast returns `new_position {6,4}` while the same response's
       `room` is (5,4) after EasternRoadTurnbackEvent sends Jean back (game_service.py:2116 uses the requested
       tile) (A3c).
   (c) `GET /api/inventory/currency` always returns `gold: 0` (and `platinum: 0`): routes/inventory.py:585
       reads `getattr(player, "gold", 0)`, and `Player` has no `gold` attribute (verified `hasattr(Player(),
       "gold") is False`); gold lives in inventory and every other route uses `get_gold(player.inventory)`
       (game_service.py:4312, 4381) (A4b, reproduced repeatedly). Same attribute-trap class as CLAUDE.md's list.
   (Dropped sibling: A5's "interact returns 200 for a missing target" — routes/world.py:722 follows the
   documented convention that game-condition refusals are 200 + success:false, same as routes/combat.py:138.)

## Leads to verify
- A5 Low: /api/world/interact returns 200 + success:false for a not-found target (siblings 4xx).
- A5 Obs: pending dialogue event makes /world/move a silent 200 no-op.
- ~~Can a pending Turn be cancelled at direction_selection?~~ CLOSED: yes — `move_type: "cancel"`
  (`_handle_cancel_selection`, combat_adapter.py:1993, "target/direction/number") resets to move_selection, and
  the UI sends it (LeftPanel.jsx:782 -> endpoints.js:84). `/combat/abort` is for in-flight moves, not prompts.
- Gorran farewell: orchestrator smoke saw 0 pending right after arriving at eastern-descent (0,2) from (15,5).

## Dropped (and why)
- A3 "Critical: seed config missing MineralFragment" — orchestrator setup fault (config_qa_leg_0924.ini), fixed.
- A3b "Critical: story flags ignored" — real, but it is finding 1 above at its true severity (no shipped impact).
- A5 "Medium: /inventory/drop ignores quantity" — the route's contract has no quantity (docstring: item_id |
  item_index) and the only client (ItemDetailDialog.jsx:316) sends item_id alone; whole-stack drop is the
  designed behaviour. Kept as an observation (no partial-drop affordance).

- A4 log "combat stalled at direction_selection for 1,200 moves" — tester fault: it picked Turn, then
  re-sent `move "Turn"` instead of a direction (direction_selection is Turn-only, combat_adapter.py:2365);
  each got the documented 200 + success:false (routes/combat.py:138). Not a defect.

- A2 "Critical #1: combat never ends (7/7)" — method artifact. A2 read `battle_state.status`, a field of the
  post-combat snapshot that stays "active"; the authoritative top-level `combat_active` goes false. Orchestrator
  clean client (VER1, camp stack, Rock Rumbler at eastern-descent (1,2)): after victory combat_active=false,
  combat moves answer "Not in combat", /world/move 200. The "move guard inconsistent" observations fit the same
  misread (moves refused only while a real fight, e.g. a fresh spawner pack, was live). Residue kept as a Low
  lead: the stale `battle_state.status` itself (check whether any client reads it).
- A2 "Critical #2: HP 0 never recognised as defeat" — wrong. Forced defeat at 1 HP vs 2 Talus Hounds: move
  response + /combat/status carry `end_state {status: defeat, game_over: true, message: "You have been
  defeated."}`, combat_active=false; the SPA renders DefeatDialog (Load / Start Over) from it
  (CombatManager.jsx:105). Residue: server still accepts /world/move at 0 HP after defeat (API-only unless a
  reload skips DefeatDialog — being checked in a browser).
- Gorran farewell "not pending on arrival" (orchestrator smoke) — not a bug: GorranGestureEvent is a
  no-input event whose prose is appended to the Step-through response's output_text (verified verbatim,
  "Gorran paused at the gate as it sealed... Jean did not ask him."). A3c/A4b were told to look in pending —
  discount a "farewell missing" report that didn't read output_text.

- A2 "Low: /combat/end and /combat/pray don't exist" — primer error (mine); Pray is a move. Not a product bug.
- A2 "loot silently lost (collect-loot empty)" — not reproduced as loss: VER1's Rumbler kill also returned an
  empty collect-loot, consistent with no drop rolled; no evidence an item was generated and then lost.

- A1 "Critical x2: King Slime fight ends at 0 HP with boss alive / death never checked" — the defeat path
  working as designed read without `end_state`; the real residue is finding 4 (A1 supplied its root cause).
- A1 "Votha says Echoing Caves are WEST, but Jean leaves by the EAST gate" — intentional: the eastern trail
  winds westward to a north-south river; the Echoing Caves trail starts on its west bank
  (docs/lore/story/ch02-ch03-transition.md:66-118).

- A3c "High: Attack stalls permanently in recoil" — tester error. Throughout, /combat/status had Attack
  `available: false, reason "Available in 5 beats", reason_code on_cooldown` and `input_type: move_selection,
  awaiting_input: true`; A3c resubmitted the greyed-out Attack 25+ times. Beats advance when another move is
  committed (Wait did it). Working as designed.
- Observations for the report (not issues): HealingSpring at eastern-descent (1,4) is an unlimited free
  full-heal before every later fight (A3c; capped at max HP); Mynx fallback lines are clean with LLM off.

- A4b "combat move_type item is a silent no-op" — not silent: 200 + success:false "Unknown move type: item"
  (the documented refusal convention); the defect is the docstring advertising it -> finding 6(b).
- A4b "NPC chat double-open has no guard" — matches the #661/#674 design (frontend de-dupes in-flight opens).
- A4b "Anvil `pet` gives generic boilerplate" — cosmetic, not filed; noted in the report.

## Setup faults this run
- A4 (camp0924): backend restarted under it for the flag shim; stopped, replaced by A4b. Its request log
  (runs/A4_api.jsonl, ~3000 requests, 13x400, 44x401 after the restart) is unreviewed — mine before closing.
- A3, A3b: leg config faults (fragment; dead flag key). Replaced by A3c.
