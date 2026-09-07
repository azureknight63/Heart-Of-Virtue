# Live browser beta QA — Grondia entrance to Mara (2026-09-06)

**Build:** master @ `e18b512b` (Alpha worktree)
**Scope:** first entry to Grondia at (1,2) through the conversation with Mara in the Nomad Camp — Scenes 0–7 of `docs/development/beta-test-scope-grondia-arc.md`, plus every named camp NPC and free-form LLM talk with Mara/Devet/Liss.
**Method:** six tester agents playing the real React + Flask stack in real browsers, concurrently, against two backend/Vite pairs with different start configs; an orchestrator re-verified every contested finding on a clean client before filing. Raw tester reports are in `beta-live-test-2026-09-06/tester-reports/`, cited screenshots in `beta-live-test-2026-09-06/shots/`.
**Outcome:** 20 GitHub issues (#528–#547). Two are release blockers for the beta route as it stands.

## Headline

1. **The beta route cannot be completed.** Session tile modifications are keyed by `x,y` without the map name, so the blocked-exit set of Grondia (2,4) — a tile every player crosses — is re-applied to (2,4) on every other map. The Mineral Pools' Narrow Pass loses its south exit, the King Slime arena is unreachable, and after two more moves the pools collapse into a closed three-tile pocket with no way out. Scenes 2, 3 and everything after them are untestable on a fresh play-through. **#528**
2. **Teleport arrival modals soft-lock the game.** Entering the Fabricarium Forge (and the Mineral Pools and the vacated dwelling) leaves an "Event Result" dialog that ✕, Enter, Escape and the overlay cannot close; only a browser reload recovers. Reproduced 6/6 across two sessions. **#529**
3. **The camp conversations are the best material in the build and are delivered badly.** Mara's scripted voice is exactly what `mara.json` asks for; the one genuine LLM line she produced was good and the client auto-closed it after two seconds; the LLM turns that failed (the configured OpenRouter model 404s) were served as stage directions under her speaker label. **#531, #532, #533**
4. **Keyboard hints lie on every event dialog**, four testers, two drivers, focus verified. **#530**
5. **On a phone the visual-novel stage is unreadable** (two 150px portrait columns in a 291px stage leave 36px for text). **#541**

Scenes 0, 1 and 4 pass cleanly on the full route (briefing, Grondia navigation and the Citadel scene, the gate farewell). Scenes 5–7 pass on the pre-seeded Leg B stack: every camp scene fires once and in order, no repeat on revisit, speaker labels and portraits correct, zero prohibited-phrase hits from any LLM NPC.

## Setup (so the next run doesn't repeat two mistakes)

| stack | frontend | API | config |
|---|---|---|---|
| full | :3001 | :5001 | `config_qa_beta_full.ini` — Grondia (1,2), `lurker_defeated`, Gorran in party, 8000 exp, worn Shortsword:3 + leather, consumables on the floor |
| legb | :3002, later :3000 | :5002 | `config_qa_beta_leg_b.ini` — Grondia (15,5) GateEast, `king_slime_defeated, votha_krr_response_given, lurker_defeated`, same loadout |

Both backends ran `create_app` + `socketio.run(use_reloader=False)` with `FLASK_ENV=testing` and a blank `GITHUB_TOKEN`; testers logged in through `/api/test/session`. Each Playwright tester had its own headless Chromium behind a small HTTP control port (`qa_driver.py`/`qa.py`, session scratchpad — worth promoting to `tools/qa/`); the UI/UX reviewers used the in-app browser pane. `frontend/vite.config.js` gained an `HOV_API_PROXY_TARGET` override so each Vite instance could proxy its own backend.

Two setup faults contaminated part of the run and are called out wherever they matter:

- **Vite on port 3002 is not an accepted Socket.IO origin** (`Config.CORS_ORIGINS` lists only 3000/3001). REST worked, but every polling POST got 400 and combat streaming was dead. T3, T4 and T5 ran on that origin: their *combat* observations were discarded unless re-verified. T6 and the orchestrator re-ran combat on port 3000: the "combat never ends", "move buttons dead" and "category buttons unclickable on touch" findings all vanished.
- **Git Bash mangled `VITE_API_URL=/games/HeartOfVirtue/api`** into a Windows path when the port-3000 Vite was launched from the Bash tool; T6 patched the client in-browser and continued (its one layout claim that only it saw — stale exits after a move — did not reproduce on a clean client and was dropped).

`config_grondia_beta.ini`, the config the beta plan assumes, cannot drive a live play-through at all (`skipdialog = True` silences every scene; no Gorran) — **#547**.

## Coverage

| Scene | Full route (T1) | Grondia breadth (T2) | Leg B desktop (T3) | Leg B phone (T4) | UX reviewers (T5/T6) |
|---|---|---|---|---|---|
| 0 Briefing (1,2) | PASS — fires once, both stages, no repeat | PASS | — | — | — |
| 1 Grondia navigation, Citadel scene | PASS — all ~30 stages, both branches | PASS — 36/40 tiles, 5 sub-maps, shop buy/sell, all panels | — | — | — |
| 2 Mineral Pools / King Slime | **BLOCKED** (#528) | first tiles only by design | — | — | — |
| 3 Votha Krr return | **BLOCKED** (#528) | dormant without fragment: correct | — | — | — |
| 4 Eastern Gate / Gorran farewell | PASS | — | not fired (config: starts on the gate tile) | same | same |
| 5 Descent / camp spawn | reached (2,4) | — | PASS | PASS | PASS |
| 6 Mara, Devet, Liss, observation, LLM talk | not reached | — | PASS (all scenes; Mara 4, Devet 2, Liss 2 exchanges) | PASS | PASS to Mara; chat defects |
| 7 River tiles, turnback (6,4) | not reached | — | PASS (turnback ×2, ferry landing loops back) | partial | — |

## Findings, ranked

Severity follows the beta plan's guide (Critical = crash/soft-lock/data loss; High = wrong flag, event not firing, NPC missing, dialogue truncated, UI action not working; Low = typo, visual, pacing, voice). "Verified" means reproduced by the orchestrator on a clean client or confirmed in source.

| # | Sev | Finding | Verified | Issue |
|---|---|---|---|---|
| 1 | Critical | Tile modifications keyed without map name → arena unreachable, pools trap the player, descent (2,4) serves Grondia's exits | source + T1 ×2 sessions, 3 maps | #528 |
| 2 | Critical (High by rubric) | Passageway arrival "Event Result" modal cannot be dismissed; reload only | orchestrator 3/3 + T2 3/3 | #529 |
| 3 | High | Event dialog key hints do nothing; Enter fires the focused LOG button; "Press 1-1" template | orchestrator (focus inside dialog) + T2/T5/T6 | #530 |
| 4 | High | NPC chat auto-closes 2 s after the closing LLM line; `closing_lines_when_exhausted` never shown | T6 network body + source (`AUTO_CLOSE_DELAY_MS`) | #531 |
| 5 | High | Fallback stage-directions rendered as the NPC's speech when `llm_available: false` | T6 network bodies | #532 |
| 6 | High | `stepfun/step-3.5-flash:free` 404s on OpenRouter; chat degrades silently | backend log | #533 |
| 7 | High | NPC talk response not rendered at the Citadel; `events_triggered` carries a dormant `AfterKingSlimeReturn` | T1 ×3 with captured payload; talk renders elsewhere | #544 |
| 8 | High | Tactical Advisor narrates the previous battle; wrong weapon; 85% beside "analysis unavailable"; dev branding | T6 on healthy origin, T5, T1, T3 | #534 |
| 9 | High | Combat UI: 8–16 s victory delay with no cue; STRIKE as the confirm verb on allies; HP bars red at full; ring colours; STRIKE buttons not hit-testable (raw click works) | T6; orchestrator hit-test | #535 |
| 10 | High | HP only as unlabeled colour capsules, no HP numbers in combat, 40px d-pad, no landmarks/focus styles, unnamed dialogs, colour-only stat deltas | T5 DOM-measured, T6 | #536 |
| 11 | High | Room description clipped at 200px over 149px of empty panel; hostile NPC lines fall below the clip; hostiles look like allies in INTERACT | T5, T6 measured | #537 |
| 12 | High (design) | Conversation stage never captions Gorran, dims him on his own beats | T6 | #539 |
| 13 | Critical on phone | VN stage: two 150px portrait columns in a 291px stage → one word per line | T4 measured + source (`ConversationStage.jsx:216`) | #541 |
| 14 | High on phone | Touch targets: combat categories 40×25, ✕ 26×41, settings toggles 31×28; Feedback input 13px | orchestrator + T4 | #542 |
| 15 | High (integrity) | `/api/world/move` accepted while combat is active; no `in_combat` guard in `move_player` | orchestrator + source | #543 |
| 16 | Low/High | Story pacing: one sentence per modal, no skip/text speed, centred italic prose, four continue verbs, stacked dismiss affordances, no journal for Mara's instruction | T5, T6 counted | #538 |
| 17 | Low–Med | Anvil not listed in INTERACT at the Tradepost → `AnvilIntroEvent` unreachable | T3, needs a second look | #545 |
| 18 | Low | Jambo's Tent sold no healing items | T2, possibly random stock | #546 |
| 19 | Low | Polish batch: header/gear collision, stats label collisions, inventory/skills/commands panels, Eastern Gate ENTER/EAST, uppercase truncated INTERACT text, loot popover clipped, LOG OUT prominence, feedback toast, autosave copy, Rumbler description spaces, duplicated Iron & Oath beat, Devet typo, triple item-grant narration, `<p>` in `<p>` warning, settings gaps | various | #540 |
| 20 | Low (docs/config) | `config_grondia_beta.ini` unusable; level-10 seed trivialises fights; Gorran gate guard only checks not-None | T1 (zero damage in two fights) | #547 |

### Reported and *not* filed (setup artefacts or not reproduced)

- Combat never ending / dead move buttons / Socket.IO 400 storm (T5), combat categories unclickable on touch (T4), API-only combat (T3/T4): all on the port-3002 origin. Did not reproduce on an accepted origin (T6 two fights, orchestrator desktop and phone). Memory note: keep Vite on 3000/3001 or extend `CORS_ORIGINS`.
- Stale exits after a move (T6): on a hand-patched client only; a clean client matched the engine within 300 ms on straight and diagonal moves.
- "GorranGestureEvent never fires" (T3, T4, T5, T6): fires on the real route (T1). The Leg B config starts *on* the gate tile, and the guard only needs any `previous_tile`; folded into #547.
- Mojibake em-dashes in the camp map (T3, T4): the JSON file is clean; an artefact of the testers' text extraction.
- SELECT TARGET soft-lock (T1): the buttons fail DOM hit-testing, which is why automation refuses them, but a raw pointer click commits the move. Kept in #535 as a hit-testing/a11y defect, not a blocker. T1's second-session BEAT 1 stall was not reproduced.
- Ferry Landing at Water Step returns the player to Eastern Bank with no Mara beat (T3): consistent with the plan's declared "no crossing event" gap; noted for the story team, not filed.
- Level-up modal on the first screen, cloud-save 403s, autosave "check your connection" spam: consequences of the seeded exp and the test-session login; the copy problem is in #540.

## Dialogue voice

Scripted: Mara's lines are sparse, sardonic and transactional with zero warmth — exactly `mara.json` ("Crossing west?" … "It's not padded and I'm not in the mood for haggling. Take it or don't."). Votha Krr's Citadel scene reads well end to end ("unhurried as erosion"), no truncation, portraits swapped correctly. Devet and Liss held their registers in every scripted beat.

LLM (live OpenRouter, T3 and T6): Mara 4 + 2 exchanges, Devet 2, Liss 2, one generic camper — all in character, no `prohibited_phrases` hits for any of the three profiles. The failures are delivery, not writing: the model 404 (#533) turns some turns into fallback stage directions shown as speech (#532), and the good closing line is auto-closed before it can be read (#531). Loquacity dropped 7 → 1 in one turn with nothing on screen explaining it (see #526). By the third exchange the generated Jean options had degenerated to "GO ON." / "NOTED." / "TELL ME MORE."

## What works and should not regress

The Combat Glossary (searchable, every entry tied to a named on-screen element); the move cards' fatigue cost, four-stage beat bar and "no valid target in range" with *range* linked into the glossary; the loot screen's carry-weight arithmetic; the visual grammar of the conversation stage (left-aligned spoken lines with a gold-framed captioned portrait vs centred italic narration with everything dimmed) and its per-emotion `alt` text; the `PREVIOUSLY` strip and tone tags in the chat panel; RANDOMIZE on the level-up gate; the inventory's equip comparison (UPGRADE/DOWNGRADE deltas); the container search → reveal → open → Take All flow; the mini-map's live legend; the mobile exploration layout as a whole.

## Recommended order of work

1. #528 (map-namespaced tile modifications) — nothing downstream can be beta-tested until this lands; add a two-map regression test and a bug-hunt scenario that walks the pools to the arena.
2. #529 (undismissable arrival modal) — second soft-lock on the route.
3. #547 — commit a config that can actually drive the beta, then re-run Scenes 2–3 and the full route end to end.
4. #531 / #532 / #533 together — the Mara conversation is the beta's payoff; fix delivery before the next tester sees it.
5. #530, #541, #542 — keyboard and phone; the design pillars promise both.
6. The rest by taste.

## Re-running this

Recipe, gotchas and the driver design are in the project memory note "Live browser QA toolkit (2026-09-06)". Short version: one backend per start config, Vite only on ports 3000/3001, launch Vite from Python or PowerShell (not Git Bash) when passing `VITE_API_URL`, never rely on Playwright's actionability check alone to declare a control unclickable — confirm with a raw pointer event and `elementsFromPoint`.
