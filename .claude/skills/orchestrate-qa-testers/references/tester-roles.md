# Tester roles, briefs, and budgets

Five to six concurrent testers was the right size for a two-map story arc on a 16 GB box. Each tester gets its own driver control port (7001+), its own name (T1…), and a brief that names the exact tiles, events and NPCs so it doesn't have to derive the route. Every brief starts with "read the primer in full with the Read tool" and ends with the report path and a 12–15 line summary request.

## Models and budgets

| role | model | budget | why |
|---|---|---|---|
| Full route | opus | 250 calls / 2.5 h | longest route, boss fight, most judgement calls; restarts its driver if Jean dies or gets trapped |
| Breadth (every tile/object/panel of one region) | sonnet | 170 calls / 75 min | mechanical coverage; a tile table is the output |
| Leg (pre-seeded start past a blocker, story scenes + LLM talk) | sonnet | 170 calls / 75 min | the story team's half; scripted scenes + voice grading |
| Same leg on a phone viewport (`--mobile`) | sonnet | 150 calls / 75 min | pillar check; measures targets with `bounding_box()`, taps with `page.touchscreen.tap` |
| UI/UX reviewer in the in-app Browser pane | opus | 130 calls / 75 min | designer's eye; describes screenshots since the pane can't save files; one stack only (shared cookie jar) |
| REST API tester (`scripts/qa_api_client.py`, no browser) | sonnet | 170 calls / 75 min | engine and story coverage at volume; needs no Vite port, so any number can share one backend and the two-accepted-origins limit only binds browser stacks |
| Orchestrator verification | you | as needed | re-runs every Critical/High that is contested or came from a suspect stack |

Budgets are caps, not targets: "stop and write the report even if incomplete; a partial report with evidence beats a complete run without it." Testers reliably honoured this.

## Brief skeleton

```
You are tester T3 in a live browser QA run of <game>. FIRST read the primer, in full, with the Read tool:
<absolute path to primer>
It tells you how to start your browser driver, how to drive it, the ground rules, and the report format. Follow it exactly.

YOUR ASSIGNMENT: <one sentence>.
- Stack: `<tag>` (frontend http://localhost:<vite>/games/HeartOfVirtue/, API http://localhost:<api>). Driver name T3, control port 7003, <desktop viewport | START THE DRIVER WITH --mobile>.
- Budget: <N> tool calls or 75 minutes, then write the report regardless.

Route:
1. <tile (x,y) title>: <what fires, what to check, what to screenshot>
2. ...
For every story scene: screenshot each stage, note whether text is complete, whether portraits/speakers are right, whether choices work, whether the event repeats on revisit, and whether `pending` is empty after the scene.
LLM conversations (real tokens): <NPC> N exchanges, ... Quote every line and grade it against ai/npc/human/<name>.json.

Write your report to <absolute path>/T3.md in the primer's format, then `quit` your driver. Your final message to me should be a 12-line summary: scenes passed/failed, findings ranked by severity, where you stopped.
```

Things that made briefs work:
- **Tile lists with titles and occupants** from the map JSON (`src/resources/maps/*.json`), e.g. `(1,2) HighLedge [Rock Rumbler]`; `scripts/route_tiles.py` prints them. Testers navigate by `where()`; naming the destination tile saves them the BFS.
- **Tell them what the beta plan gets wrong** ("some tile coordinates in it are stale — trust the map JSON") so they don't file the plan's errors as bugs.
- **Name the scenes** (`MaraFirstContactEvent`, `DevetIntroEvent`) so they can read the source for expected behaviour.
- **LLM exchange counts per NPC** — otherwise a curious tester spends tokens freely.
- **A restart rule** for the full-route tester: "if Jean dies or is trapped, report it, quit the driver, start a fresh one with the same command and continue".
- **Reviewer briefs get the pane login recipe verbatim** and the instruction to stay on one stack.

## REST API testers — what their brief must say

On 2026-09-24, five Sonnet REST testers covered the whole route in breadth, but they also filed five Criticals, and none of them survived triage. Every false Critical came from a gap in the brief. A REST brief (or the primer) must state these up front:

- **Which fields are authoritative.** The combat response's top-level `combat_active` and `end_state` are the truth. `battle_state` is a snapshot. A tester that read the stale `battle_state.status` after the last kill reported "combat never ends, 7/7 fights". Defeat is `end_state.status == "defeat"` with `game_over: true`; HP 0 plus that end state *is* the game recognising defeat.
- **The refusal convention.** A game-condition refusal is `200` + `success: false` + a message (`routes/world.py`, `routes/combat.py`). Only malformed requests are 4xx. Otherwise testers file every refusal as "returns 200 on failure".
- **`input_type` decides the next request.** A `direction_selection` prompt wants a direction, not the move name again, and `cancel` clears it. One tester re-sent `move "Turn"` 1,200 times and reported a freeze. A move marked `available: false` ("Available in 5 beats") advances only when a *different* move spends beats.
- **Endpoints come from `scripts/list_routes.py`, never from memory.** That primer named `/api/combat/end` and `/api/combat/pray`; neither exists (Pray is a move), and the 404s were filed.
- **Their own reads can change state.** Tell them to log every request (the client does, in `logs/qa/api-runs/`) and to report "state changed after my GET" as a finding in itself. That is how #683's destructive status GET was eventually found.
- **Exchange caps for LLM talk, and which tester owns LLM.** With no fallback provider configured, one tester's quota is everyone's (see `gotchas.md`).

## Staggering and contamination

Dispatch all Playwright testers in one message so they run concurrently, but before that: start one throwaway driver yourself, do `where`, `text`, `aria`, one click, `shot`, and read the first events. That ten-minute smoke caught nothing the first time and would have caught the port-3002 fault if the stack had been the one on 3002. Then after dispatch, grep each tester's `<name>_events.jsonl` for `"status": 400` and `socket.io` within the first five minutes.

If a stack turns out faulty mid-run: you cannot redirect running testers (no SendMessage in this session type). Fix the stack, note which testers are contaminated, let them finish for the parts that don't depend on the fault (story scenes over REST were fine), and re-verify their affected findings yourself or with a fresh short-budget tester on the fixed stack.

## Reviewer output

The pane reviewer cannot attach screenshots; ask it to describe what it saw precisely and cite DOM facts via `read_page`/`find`/`javascript_tool` measurements (bounding boxes, computed styles, landmark counts). That produced the most actionable a11y findings of the run.
