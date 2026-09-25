# Heart of Virtue — live API QA, tester primer (2026-09-25)

You are one of several tester agents playing **beta 2** through the **real REST API**, in parallel. The route is Grondia, the Mineral Pools, King Slime, Votha Krr, the Eastern Gate, the Eastern Descent, the Nomad Camp, Mara, and the Ferry Landing / end-of-beta. Play like a player would: explore, fight, talk through scripted scenes, and pick things up, but over HTTP. One other tester plays the same build in a visible browser.

**This is a regression run.** Eleven fixes landed yesterday (listed under "Fixed since the last run"). Each one on your route needs an explicit PASS/FAIL with evidence.

```
ROOT    = C:\Users\azure\Desktop\dev\Heart-Of-Virtue\Alpha      (branch qa-skill-helpers = master @ 91d946d4 + PR #711; read-only for you)
PY      = C:\Users\azure\Desktop\dev\Heart-Of-Virtue\Alpha\.venv\Scripts\python.exe
CLIENT  = C:\Users\azure\Desktop\dev\Heart-Of-Virtue\Alpha\.claude\skills\orchestrate-qa-testers\scripts\qa_api_client.py
RUNS    = C:\Users\azure\Desktop\dev\Heart-Of-Virtue\Alpha\logs\qa\api-runs      (your request log: <NAME>_api.jsonl)
REPORTS = C:\Users\azure\AppData\Local\Temp\claude\C--Users-azure-Desktop-dev-Heart-Of-Virtue\781c6ece-533e-4355-bde8-8369becccec3\scratchpad\qa0925\reports
TILES   = C:\Users\azure\AppData\Local\Temp\claude\C--Users-azure-Desktop-dev-Heart-Of-Virtue\781c6ece-533e-4355-bde8-8369becccec3\scratchpad\qa0925\tiles_<map>.txt
```

`TILES` holds one line per tile for each map on the route: `(x,y) Title [occupants] exits: ... events: ...`. It is generated from the map JSON, so use it to plan your walks.

## The servers (already running: never start, stop or restart them)

| tag | API | config | start state | LLM |
|---|---|---|---|---|
| `full0925` | :5001 | `config_prod.ini` | the browser tester's stack, plus A5 only if your brief says so | NPC chat on |
| `api0925` | :5002 | `config_prod.ini` (shipped beta 2) | Grondia (1,2) Passage, level 4 with points UNSPENT (the LEVEL UP prompt at the start is by design), Gorran in party | all off |
| `leg0925` | :5003 | `config_qa_leg_0924.ini` | Grondia (7,9) Grondelith Entrance, level 6, Gorran; `king_slime_defeated` seeded, MineralFragment carried, Votha Krr's response NOT yet given | all off |
| `camp0925` | :5004 | `config_qa_camp.ini` | Grondia (14,5) Antechamber, level 3, Gorran; `king_slime_defeated` + `votha_krr_response_given` | all off |
| `campllm0925` | :5005 | `config_qa_camp.ini` | same as camp0925 | NPC chat on |

The engine now applies a config's `starting_story_flags` itself (#687 fixed; the server log shows `Applied starting_story_flags`). The camp seed carries no MineralFragment, so **the King Slime memory flash cannot fire on :5004/:5005. That is the seed, not a bug.** `lurker_defeated` is seeded but nothing reads it (#709); ignore it.

Every login gets an independent session and universe. Use only the port your brief names. On an LLM-off stack, `/api/npc/chat/*` returns deterministic fallback text: test the chat *mechanics* there, not the voice.

## Your client

Always prefix with `PYTHONIOENCODING=utf-8`. Log in ONCE (again only if you deliberately restart):

```
PYTHONIOENCODING=utf-8 "<PY>" "<CLIENT>" A1 login 5002
PYTHONIOENCODING=utf-8 "<PY>" "<CLIENT>" A1 where
PYTHONIOENCODING=utf-8 "<PY>" "<CLIENT>" A1 get /api/world/events/pending
PYTHONIOENCODING=utf-8 "<PY>" "<CLIENT>" A1 post /api/world/move '{"direction": "south"}'
PYTHONIOENCODING=utf-8 "<PY>" "<CLIENT>" A1 exec <<'PY'
r = post("/api/world/move", {"direction": "south"})
print(r["_status"], r.get("message") or r.get("error"))
PY
```

Inside `exec` you have `get`, `post`, `where()`, `state()` (= /api/full-state), `pending()`, `show(obj)`, `json`, `re` and `time`. Every response has `_status`. Use `exec` loops to save tool calls, and `--full` for untruncated output. Every request is logged, so cite from your log.

## The API surface: these are ALL the game routes (generated from the app; anything else 404s)

```
GET  /api/world  /api/world/tile  /api/world/commands  /api/world/explored  /api/world/events/pending
POST /api/world/move {direction}  /api/world/interact {target_id, action}  /api/world/search
POST /api/world/events  /api/world/events/input {event_id, user_input}  /api/world/tiles/batch
GET  /api/status  /api/full-state  /api/stats  /api/journal  /api/skills  /api/equipment  /api/info
POST /api/skills/learn  /api/level-up/allocate  /api/pray  /api/game/new
GET  /api/inventory  /api/inventory/{examine,compare,stats,currency}
POST /api/inventory/{equip,unequip,use,drop}
GET  /api/combat/status        POST /api/combat/{move,collect-loot,start,abort,suggestions/pause}
GET  /api/shop/state           POST /api/shop/{buy,sell,buyback}
POST /api/npc/chat/{open,respond,end}   GET /api/npc/chat/history/<npc_key>
GET/POST /api/saves  POST /api/saves/<id>/load  DELETE /api/saves/<id>
POST /api/feedback/issue
```

Read the route file (`src/api/routes/*.py`) for exact payloads before first use. `/api/debug/*` exists for tests. **Do not use it to play**; use it only to get past a blocker you have already documented, and say so.

## How to read responses (five false Criticals last time came from getting these wrong)

- **Combat end.** The top-level `combat_active` and `end_state` are the truth. When a fight ends, `combat_active` goes false and `end_state` says `victory` or `defeat`. Don't decide it from `battle_state` fields.
- **Defeat.** Defeat is `end_state.status == "defeat"` with `game_over: true`. HP 0 plus that end state *is* the game recognising defeat.
- **Refusals.** A game-condition refusal is `200` with `success: false` and a message; only malformed requests get 4xx. A refusal is a finding only if the message is wrong or the refusal shouldn't happen.
- **`input_type` decides your next request.**
  - `move_selection`: send a move.
  - `target_selection`: send `{"move_type": "target", ...}`.
  - `number_input`: send a number.
  - `direction_selection`: send a direction, NOT the move again; `cancel` clears the prompt.
  - A move with `available: false` ("Available in 5 beats") only becomes available when a *different* move spends beats.
  - If you catch yourself sending the same request 10+ times, stop and read `input_type`.
- **Your own reads can change state.** A GET that changes what a second identical GET returns (an event gone, a scene consumed) is a finding in itself. Report it with both responses.
- **Staged events** get a NEW `event_id` when they advance. Re-read pending before answering again.

## Ground rules

- Edit nothing under ROOT, run no git, start or kill no servers, install nothing. **Reading source is encouraged**: `src/story/ch02.py`, `src/story/ch03.py`, the map JSON, and `docs/lore/`. Read an event's trigger conditions before calling it "never fires".
- Read `CLAUDE.md` "QA — known intentional behaviors" before filing blocked exits or unresponsive objects. Jean fights the Mineral Pools WITHOUT Gorran on purpose.
- **Quote, don't summarise.** For every scripted scene, record the first line of prose you received, verbatim.
- Test sessions cannot save, so `POST /api/saves` returns **403**. That is expected (it is also what #690 returns for a dead player, so make sure you know which case you're in). Never call `/api/auth/register` or `/api/auth/login`.
- Budget: the cap in your brief. Stop and write the report even if incomplete.
- File no GitHub issues and write nothing outside REPORTS and RUNS.

## Fixed since the last run: verify each one on your route (PASS/FAIL + evidence)

- **#683**: the King Slime victory scene is delivered by `POST /api/combat/collect-loot` in its `events_triggered`. A `GET /api/combat/status` after victory must NOT consume it: GET status twice, then collect-loot, and the scene must arrive, exactly once.
- **#684**: in a failed NPC chat turn, loquacity drains by the reduced amount (LLM stacks only).
- **#686**: King Slime's Tidal Surge. The advisor's (`suggested_moves`) reasons name the incoming surge, and Dodge is recommended within the defence window. A surge aimed at Gorran must not trigger Jean's Dodge.
- **#687**: seeded story flags apply (legs start in the seeded state).
- **#688**: attacking a target Jean can't damage (e.g. Shortsword vs Stone Creature) has `damage_preview {min:0,max:0}`, and the advisor clamps that attack's score low. When every attack is harmless, it suggests Swap Weapon.
- **#689**: after combat, `battle_state.status` matches the end (no stale "active").
- **#690**: a dead player is refused every state mutation: moves, interactions, `POST /api/saves` (403 with a death message) and collect-loot. Start Over gives hp > 0.
- **#691**: Advance with no opponents on the field reports no opponents rather than a generic failure.
- **#692**: Grondia interiors (guesthold, forge, archive, vacated dwelling, Jambo's shop) use Grondia's music. That's frontend-only, so REST testers skip it.
- **#693**: the combat move route docs match reality. `move_type: item` gets "Unknown move type".
- **#694**: the Eastern Gate passageway's "step through?" confirmation is not offered while the gate is locked (before Votha Krr's response), plus the other items in the issue.
- **#695 (partial)**: Iron & Oath prose fixes. Anvil at the camp tradepost answers `pet` with an Anvil line once Iron & Oath is done, instead of generic text.
- **#685 (partial)**: Jambo (both tents) speaks in third person, stays inside his tent, and gives no directions (LLM stacks only).

## Known and still open (cite, don't rediscover)

#681, #685 (Votha Krr/Gorran chat not wired), #695 (writer items: naming beats, repeated lines, tile-description contradictions), #698 (doubled log lines), #700 (the advisor can recommend a multi-beat move that overshoots the surge window), #701, #703 (a defeat never fires post-combat tile events), #704, #705, #709, #710.

## Severity

- **Critical**: blocks the route, crashes, loses progress or items, or returns a 5xx.
- **High**: a feature or scene is broken, but the route continues.
- **Medium**: a wrong result with a workaround, missing feedback, or wrong state.
- **Low**: wording or a cosmetic payload issue.
- **Observation**: balance, pacing or design.

## Report: write it to `<REPORTS>\<YOURNAME>.md`

1. **Header**: tester, stack, tool calls used, where you ended, and level/HP at the end.
2. **Route checklist**: every step, marked PASS / FAIL / BLOCKED / NOT REACHED, with one line of evidence (quoted prose for scenes).
3. **Fix verification**: each fixed issue you passed, PASS/FAIL with evidence.
4. **Findings**, one `###` each: severity, location, numbered steps from login, expected/actual, verbatim request/response evidence, confidence, and the suspect file:line if you looked.
5. **Combat log summary**: one row per fight (tile, enemies, rounds, HP low-water, potions, oddities).
6. **Non-bug observations.**
