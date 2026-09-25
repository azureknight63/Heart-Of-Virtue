# Live QA — beta 2, Grondia through the Ferry Landing (2026-09-24)

**Build:** master @ `347a08d5` (Alpha worktree)
**Scope:** the shipped beta 2 arc (`config_prod.ini`): Grondia (1,2) briefing → Mineral Pools → King Slime →
Votha Krr → Eastern Gate → Eastern Descent → Nomad Camp → Mara → Ferry Landing / end-of-beta.
**Method:** one Opus tester playing the whole route in the **in-app browser pane** (audio muted, live NPC
LLM capped at 23 turns) plus **Sonnet REST-API testers** playing their own sessions against three scripted
backends — the first run of this skill with API testers alongside a browser. Every Critical/High was
reproduced by the orchestrator on a clean client or confirmed from source/logs before filing.
**Outcome:** 13 issues, **#683–#695**. One High, six Medium, six Low. No Criticals survived — five were
filed by testers, all five were method artifacts (see "Reported and not filed").
Raw tester reports: `beta-live-test-2026-09-24/tester-reports/`; triage ledger with every verdict:
`beta-live-test-2026-09-24/triage-ledger.md`.

## Headline

1. **The beta is finishable end to end, in the browser and over the API.** O1 (browser) and A1 (API, the
   unmodified shipped config) both reached the end-of-beta at the Ferry Landing; A4b reached it from the
   camp start. The whole story chain fires in order, including Gorran's farewell at the gate (#582 holds)
   and the new #669 gate lock (refuses before Votha Krr's response, opens after — four testers).
2. **The King Slime victory scene never reaches a browser player (#683, High).** The server sends
   `AfterDefeatingKingSlime` only inside the post-kill `/combat/status` `events_triggered` (it needs no
   input, so it is never pending); O1's shipped client log shows the browser never received it. Effects
   apply (fragment, cleansed pools, Gorran), the prose ("The churning stilled...") is simply lost.
3. **Combat doesn't explain its most important numbers.** The advisor recommends 0-damage attacks for 150
   turns and the target card hides the `damage_preview` the server already computes (#688); King Slime's
   Tidal Surge — the one deadly blow — dropped its "get clear" cue and the advisor suggests Turn (#686).
4. **Live NPC chat is fragile in two independent ways.** A slow provider turn ran 48 s past the 21 s
   ceiling, the client timed out at 28 s and resent into a wall of 409s, and the chat died with no word to
   the player (#684). And no Grondia NPC (Jambo, Votha Krr, Gorran) has a character file, so Jambo gave
   river-crossing advice inside his cavern tent (#685).
5. **`starting_story_flags` has been a dead config key since the terminal teardown (#687).** It surfaced
   because #669 made the QA camp config's "already given" flag matter; it cost two testers their legs.
   No shipped impact (`config_prod.ini`'s only flag, `lurker_defeated`, is read by nothing).

## Setup

| stack | API | frontend | config | start | LLM | testers |
|---|---|---|---|---|---|---|
| `full0924` | :5001 | :3001 | `config_prod.ini` (shipped) | Grondia (1,2), L4 unspent, Gorran | NPC chat **on** (model `auto`), Mynx + advisor off | O1 |
| `api0924` | :5002 | :3000 | `config_prod.ini` (shipped) | same | all off | A1, A2, A5, orchestrator browser check |
| `leg0924` → `b` → `c` | :5003 | — | `config_qa_leg_0924.ini` (untracked) | Grondia (7,9), L6, `king_slime_defeated` + MineralFragment | all off | A3, A3b, A3c |
| `camp0924` → `b` | :5004 | — | `config_qa_camp.ini` (untracked) | Grondia (14,5), L3, King Slime + Votha done | all off | A4, A4b |

All backends: `qa_api.py` (reloader-free, `FLASK_ENV=testing`, `GITHUB_TOKEN` blanked); logins via
`POST /api/test/session`. API testers used a session-persisting REST client (`hov_api.py`, login / where /
get / post / exec, JSONL request log). OpenRouter probe at start: 50/50 free requests; no Groq/Cerebras key
and no Ollama on this box, so there was no fallback provider.

### Setup faults and what they contaminated

1. **Leg config lacked the MineralFragment** (mine). `AfterKingSlimeReturn` waits for it
   (`src/story/ch02.py:1515`); A3 was blocked at Votha Krr. Fixed and restarted as `leg0924b`.
2. **`starting_story_flags` is never applied** — found by A3b, confirmed in source: every seeded flag was
   silently dropped, so neither leg config could open the #669 gate. A real bug (#687), not a tester fault.
   The QA launcher now carries a logged shim restoring the old semantics (`HOV_QA_NO_FLAG_SHIM=1` disables
   it); legs restarted as `leg0924c` / `camp0924b`. A4's session died with its restart (stopped; its ~3000
   request log was mined — its only anomaly was its own Turn loop). **Contamination:** A3 and A3b report
   nothing but the blocker; A4 produced no report. A3c and A4b covered those legs cleanly.
3. **Primer errors** (mine): it named `/api/combat/end` and `/api/combat/pray` (neither exists; Pray is a
   move) and pointed testers at `battle_state` without saying top-level `combat_active` is authoritative —
   which is how two false Criticals were born (see below).

### Testers

| tester | model | surface | stack | assignment | result |
|---|---|---|---|---|---|
| O1 | Opus | in-app browser pane, muted | full | whole route + designer's eye + capped LLM | end-of-beta reached; ~235 calls; LLM died after 2 Jambo turns (#684) |
| A1 | Sonnet | REST | api | whole route, unaided, shipped config | end-of-beta reached, 11/11 checkpoints |
| A2 | Sonnet | REST | api | Mineral Pools full clear + King Slime + combat robustness | 15/18 Pools tiles (missed (1,0), (4,3), (3,4)), 8 fights, King Slime down |
| A3 / A3b | Sonnet | REST | leg | Votha Krr → gate → Descent | blocked by setup faults 1–2 |
| A3c | Sonnet | REST | leg (fixed) | same | all 32 Eastern Descent tiles, 8 fights, Votha + gate + farewell |
| A4 | Sonnet | REST | camp | camp → ferry | stopped (backend restarted under it) |
| A4b | Sonnet | REST | camp (fixed) | camp → ferry, ordering variants, shop | end-of-beta reached, all 13 camp tiles |
| A5 | Sonnet | REST | api | Grondia systems sweep + adversarial inputs | 38/38 Grondia tiles + 5 side maps, no unexpected 5xx |

## Coverage

| scene / area | O1 | A1 | A2 | A3c | A4b | A5 |
|---|---|---|---|---|---|---|
| BetaTesterBriefing + level-up allocation | PASS | PASS | PASS | — | — | PASS (+ adversarial) |
| Ch02GuideToCitadel / Votha intro (#657 "???", #663 teleport) | PASS | PASS | — | — | — | PASS |
| Jambo's Grondia tent (#664 intro, #665 read, #660 spacing) | PASS | PASS | — | — | — | PASS |
| Mineral Pools fights + Sacred Spring | PASS | PASS | PASS (15/18 tiles) | — | — | — |
| King Slime | PASS | PASS | PASS | — | — | — |
| AfterDefeatingKingSlime prose | **FAIL (#683)** | PASS (API) | PASS (API) | — | — | — |
| Ch02KingSlimeMemoryFlash | PASS | — | — | — | — | — |
| Eastern Gate refuses before Votha (#669) | PASS | PASS | — | PASS | — | — |
| AfterKingSlimeReturn (Votha's response) | PASS | PASS | — | PASS (6 stages quoted) | pre-seeded | — |
| Eastern Gate opens + GorranGestureEvent | PASS | PASS | — | PASS | PASS | — |
| Eastern Descent (32 tiles) | main line | main line | — | PASS 32/32 | main line | — |
| Camp scenes (Entry, Devet, Liss, Iron & Oath, Mara x2) | PASS | PASS | — | CampEntry | PASS 13/13 tiles | — |
| Ferry declines before Mara's chain / ends beta after | PASS | PASS | — | — | PASS (+ Mara-before-Devet) | — |
| Shops (Grondia / camp) | Grondia | — | — | — | camp, exact arithmetic | Grondia, exact + adversarial |
| Containers / TAKE ALL (#609) | — | — | — | PASS | PASS | PASS (20+ containers) |
| Voice grading (LLM) | Jambo only (2 turns) | — | — | — | — | — |

**Fix verifications passed this run:** #609, #610, #643, #650, #657, #658, #659, #660, #661, #663 (the
teleport is automatic after Votha's intro, not an offered choice), #664, #665, #666, #667, #669, #671.
Inconclusive: #668 (smooth token movement, weakly observed), #670 (death animations — King Slime's token
still drawn behind the victory dialog).

## Findings, ranked

| # | sev | finding | how verified |
|---|---|---|---|
| #683 | High | King Slime victory prose never reaches the browser | server payloads (A1, A2) + O1's shipped client log: never received |
| #684 | Med | NPC chat turn breached its 21 s ceiling (48 s); client 28 s timeout → 6× 409 → chat dies silently | API log + structured request log timestamps |
| #685 | Med | Jambo / Votha Krr / Gorran have no chat character file; camp-only world facts | `ai/npc/human/` listing + `world_facts.json` geography |
| #686 | Med | Tidal Surge wind-up drops the "get clear" cue; advisor suggests Turn | source (`src/moves/_npc.py:414` vs `:505-509`) + O1/A2 payloads |
| #687 | Med | `starting_story_flags` never applied on the web path | source (its only consumer was the terminal game loop, removed with the teardown; see 311a644e) + shim A/B on a clean client |
| #688 | Med | Advisor recommends 0-damage attacks; target card hides `damage_preview` | source (`ai/combat_strategist.py:986-1070` ignores `combat_adapter.py:4414`) + A2/O1 payloads |
| #689 | Med | Wire fields contradict state: `battle_state.status`, `new_position`, `/inventory/currency` | orchestrator clean client x2; `hasattr(Player(), "gold") is False` |
| #690 | Low | Server accepts world actions at 0 HP after a defeat (API-only) | orchestrator forced defeat; browser DefeatDialog verified safe across 2 reloads |
| #691 | Low | Advance "No one is out of reach" with enemies at 8–10 ft | seen once (A2); catch-all fallthrough in `src/moves/_movement.py:219-229` |
| #692 | Low | Grondia interiors play the Mineral Pools BGM | map metadata of all four interior maps |
| #693 | Low | Docs describe things that aren't there (ch03 coordinates, combat move_type list) | source |
| #694 | Low | Browser polish batch (stale swap label, Faith "(n)", log wrap, ...) | O1, API cross-checks where applicable |
| #695 | Low | Narrative batch (speaker plates before naming, continuity slips, ...) | O1 quotes |

## Reported and not filed

| claim (tester) | verdict |
|---|---|
| "Combat never ends after the last enemy dies, 7/7 fights" — Critical (A2) | **Method artifact.** A2 read `battle_state.status`, a stale field of the post-combat snapshot; top-level `combat_active` goes false and Jean moves on (orchestrator, clean client). The stale field itself is #689(a). |
| "HP 0 never recognised as defeat" — Critical (A2), and "King Slime fight ends at 0 HP with the boss alive" — Critical ×2 (A1) | **Wrong.** Defeat returns `end_state {status: defeat, game_over: true}` and the SPA renders DefeatDialog (`CombatManager.jsx:105`); verified in a headless browser across two reloads (`shots/V1_001`, `V1_003`). Residue: #690. |
| "Attack stalls permanently in recoil" — High (A3c) | **Tester error.** Attack was `available: false` ("Available in 5 beats") the whole time with `input_type: move_selection`; beats advance on another move. |
| "Seed config missing MineralFragment" / "story flags ignored" — Critical (A3, A3b) | Setup fault 1 (mine) / real bug at its true severity (#687). |
| "`/inventory/drop` ignores quantity" — Medium (A5) | **Not a defect.** The route's contract has no quantity and the only client sends `item_id` alone; whole-stack drop is designed. |
| "`/world/interact` returns 200 for a missing target" — Low (A5) | Documented convention: game-condition refusals are 200 + `success:false` (`routes/world.py:722`, `routes/combat.py:138`). |
| "Combat `move_type: item` is a silent no-op" (A4b) | Not silent — "Unknown move type"; the docstring advertising it is #693. |
| A4's 1,200-move stall at `direction_selection` | Its own loop re-sent `move "Turn"` instead of a direction. `cancel` clears the prompt and the UI sends it (`LeftPanel.jsx:782`). |
| "Gorran's farewell not pending on arrival" (orchestrator smoke) | Not a bug: a no-input event whose prose is appended to the Step-through response (verified verbatim). |
| "Votha says Echoing Caves are west, but Jean leaves by the east gate" (A1, O1) | Lore-consistent (`docs/lore/story/ch02-ch03-transition.md:66-118`); the presentation gap is a bullet in #695. |
| "Loot silently lost — collect-loot empty" (A2) | Not reproduced as loss; empty is consistent with no drop rolled. |
| "Pending dialogue makes `/world/move` a silent no-op" (A5, seen once) | `move_player` has no pending check; most likely an arrival event returning Jean (the RoadEast pattern). Observation only. |
| NPC chat double-open has no server guard (A4b) | By design since #661/#674 (the client de-dupes). |
| "Primer's `/combat/end` and `/combat/pray` 404" (A2) | Primer error (mine). |

## Dialogue voice

Scripted scenes: every one quoted by at least one tester fired with complete prose, in order, once. Defects
are in #695 (names on speaker plates before the naming beat, Vespera knowing Jean's name, a narration line
plated as Gorran, a triple space and an unexplained "Wailing Badlands" in Mara's scene).

LLM: only two live Jambo turns before the provider fell over (#684), both off-location because Jambo has no
character file (#685). No voice grading for Votha Krr, Gorran, Mara, Devet or Liss this run.

## What works

- The full route, both ways a player can play it, with every scripted beat in order.
- #669's gate lock: refuses in fiction on every keyword and through the confirmation path, opens after
  Votha Krr, and the farewell still fires.
- Input hardening: A5's adversarial level-up, shop and inventory inputs were all rejected cleanly with no
  state change. Across ~5,000 logged API-tester requests (A1 1,370 · A2 1,316 · A3c 833 · A4b 887 ·
  A5 605) the only 5xx was the feedback route's by-design 503 with `GITHUB_TOKEN` blanked. Huge shop
  quantities are capped to stock.
- Shop arithmetic exact in both shops; merchandise-drop rule behaves as documented.
- Defeat handling in the browser: DefeatDialog survives reloads and locks movement.
- Ferry Landing ordering (Mara-before-Devet, early ferry, post-ending movement) is robust; nothing repeats.
- Scripted fallbacks with LLM off (Mynx, NPC chat) are clean.
- Balance note (not filed): Gorran-assisted Eastern Descent fights are safe; the Healing Spring at
  eastern-descent (1,4) is an unlimited free full-heal before every later fight.

## Recommended order of work

1. **#683** — the boss payoff scene is invisible; small frontend fix, big story cost.
2. **#686** and **#688** — make the deadly surge and the 0-damage trap legible (pillar 3).
3. **#684** then **#685** — before the next LLM-scoped run; #684 first, because it ends conversations.
4. **#687** — unblocks every seeded QA config without the launcher shim; delete the shim after.
5. **#689**, **#690** — cheap wire hygiene; #689(c) is a one-line fix.
6. Batches **#694**, **#695**, then **#691**, **#692**, **#693**.

## Re-running this

`/orchestrate-qa-testers` (`.claude/skills/orchestrate-qa-testers/`). Changes made during this run:
Phase 0 now asks a fifth question (audio for visible browsers, default muted; recipe in
`references/gotchas.md`); `qa_api.py` carries the `starting_story_flags` shim until #687 lands;
`file_issues.py` accepts labels containing spaces; the API testers' REST client is now
`scripts/qa_api_client.py` (logs to `logs/qa/api-runs/`). Memory note: "Live browser QA toolkit"
(fifth-run section).
