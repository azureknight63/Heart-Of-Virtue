# Live QA — beta 2 regression, Grondia through the Ferry Landing (2026-09-25)

**Build:** master @ `91d946d4` + #711 (Alpha worktree, branch `qa-skill-helpers`)
**Scope:** a regression pass over the shipped beta 2 arc (`config_prod.ini`), re-checking every fix merged in #707 (#683–#694), plus the first live use of the QA skill's new helper scripts (#711).
**Method:**
- one Opus tester played the whole route in the **in-app browser pane** (audio muted, live NPC chat);
- five Sonnet **REST API testers** ran in parallel on five backends: the whole route unaided, Pools and King Slime depth, the Votha → Descent leg, the camp to the ferry, and live LLM voice grading;
- the orchestrator verified every contested finding on a clean API client or in source.

**Outcome:**
- every #707 fix the run could exercise **passes**;
- **7 new issues** (#712–#718), one of them a soft-lock;
- **3 tester Criticals dropped**: two came from gaps in my primer, one from a test-session limitation.

## Headline

1. **#707 holds.** #683 (King Slime's scene rides collect-loot, and plays once in the UI), #684, #685 (Jambo), #686, #687, #688, #689, #690, #691, #693 and #694 all PASS with evidence; #692 PASSES in the browser.
2. **New soft-lock, #712 (High):** a passageway "Step through?" confirmation left unanswered when combat starts locks the session permanently. Confirm is refused in combat, there's no cancel, combat moves are refused because an event is pending, and abort doesn't apply. The orchestrator reproduced it on a clean client on the first attempt.
3. **#713 (Medium):** the server accepts moves while a needs-input scene is pending. That is the easy road into #712 over the API, and it lets a later answer teleport Jean back across maps. It's the same client-only-guard shape as #690.
4. **#714 (Medium):** the Tactical Advisor prices *any* enemy move in progress as a hit. King Slime's **Rest** shows as "potentially lethal" and pulls Dodge.
5. **#715 (Medium):** the event dialog's keyboard shortcuts still act while LOG is open. The #707 pass paused staged dialogue but missed `EventDialog`'s own handler.
6. **#716 / #717 (Medium):** live NPC chat.
   - Jean's options quote Liss's *private* prompt ("You said you adore Gorran").
   - Liss calls Jean "child" in an adult register.
   - Mara invents a route; Jambo's Grondia tent talk describes his riverbank tent.

## Setup

| stack | API | frontend | config | LLM | testers |
|---|---|---|---|---|---|
| `full0925` | :5001 | :3001 | `config_prod.ini` | NPC chat on (model `auto`), Mynx + advisor off | O1 |
| `api0925` | :5002 | — | `config_prod.ini` | all off | A1, A2 |
| `leg0925` | :5003 | — | `config_qa_leg_0924.ini` (untracked; King Slime done + MineralFragment) | all off | A3 |
| `camp0925` | :5004 | — | `config_qa_camp.ini` (untracked; King Slime + Votha done) | all off | A4, orchestrator V1 |
| `campllm0925` | :5005 | — | `config_qa_camp.ini` | NPC chat on (model `auto`) | A5 |

All backends ran `qa_api.py` (reloader-free, `FLASK_ENV=testing`, `GITHUB_TOKEN` blanked); logins used `POST /api/test/session`.

**New helper scripts, first live use:**
- `preflight.py --llm` found Groq and Cerebras keys configured (unlike 09-24), Ollama not running, `MYNX_LLM_MODEL` still pinned to a `:free` slug (overridden to `auto` in the stack env), and OpenRouter at 50/50.
- `lint_qa_config.py` passed all three configs. It warned that the camp seed can't fire the King Slime memory flash; the primer said so and nobody filed it.
- `route_tiles.py` generated the briefs' tile lists; `list_routes.py` generated the primer's endpoint table (no phantom endpoints this time).
- `check_contamination.py` showed all five stacks clean five minutes in; `summarize_api_log.py` fed the triage.

The run also found four defects in the helpers themselves, all fixed on this branch:
- `route_tiles` printed story events as "UnknownEvent" (they use a dotted `class` key);
- `preflight`'s Playwright probe crashed decoding output as cp1252;
- `check_contamination --since` listed every archived tester;
- `summarize_api_log` grouped about 750 refusals as "(no message)" (they're under `error`).

`preflight` also correctly FAILed on the venv's missing Playwright Chromium. The browser tester used the pane, so the run didn't need it.

### Setup faults and what they contaminated

None at the stack level. My **primer** had four gaps, each of which produced a false Critical or a false finding. They're listed under "Reported and not filed" and now written into the skill (`references/tester-roles.md`, REST brief facts):
1. The #683 contract was described wrongly (the status echo was presented as a leak).
2. It didn't say where no-input scenes arrive.
3. It didn't say how loot collection works.
4. It asked for a save-path check that test sessions can't reach.

## Testers

| tester | model | surface | stack | assignment | result |
|---|---|---|---|---|---|
| O1 | Opus | in-app browser pane, muted | full | whole route + UX + capped LLM (Jambo 3, Mara 3) | END OF BETA reached; ~215 calls |
| A1 | Sonnet | REST | api | whole route, unaided | all 7 checkpoints; ferry `beta_end` |
| A2 | Sonnet | REST | api | all 18 Pools tiles, King Slime advisor, #688/#691/#693, #690 death checks | cleared; King Slime down at 93% HP |
| A3 | Sonnet | REST | leg | #694 before/after Votha, all 32 Descent tiles | camp entry; found #712 |
| A4 | Sonnet | REST | camp | all 13 camp tiles, scenes, chat mechanics, #695 | ferry reached; chat mechanics sane, no 5xx |
| A5 | Sonnet | REST | campllm | live voice: Jambo ×2 tents, Mara, Devet, Liss, Kaelen, Vespera | 21 exchanges graded verbatim |

## Fix verification

| fix | verdict | evidence |
|---|---|---|
| #683 | PASS | A2: two status GETs echo the scene tagged `post_combat`; collect-loot delivers it once; a third GET and a second collect-loot come back empty. O1: Victory alone, then "The churning stilled…" and the memory flash, each once |
| #684 | PASS | A5: failed turns drained the reduced 3 (Devet 17→14, Vespera 12→9), with an in-voice fallback |
| #685 (Jambo) | PASS | A5: 7 turns across both tents, third person, no directions. Residue in #717 |
| #686 | PASS | A2 / O1: surge named at 14 beats; Dodge scored 97 at ~4 beats; Jean survived. The Dodge reason goes generic inside the window (#718); ally-target sub-case untestable (the Pools are solo) |
| #687 | PASS | A1, A3; the server log shows `Applied starting_story_flags` |
| #688 | PASS | A2: a `{0,0}` preview on a Stone Creature, and the advisor routes around it. O1: range + "☠ LETHAL" as a word. The all-harmless → Swap branch wasn't reachable in these encounters |
| #689 | PASS | A1, A2, A4 |
| #690 | PASS | A1, A2: move/interact/use/loot refused with the death message; GET saves allowed; Start Over hp > 0 (the save path is masked by test sessions; unit-pinned) |
| #691 | PASS | A2: "No opponents on the field" / `no_opponents` |
| #692 | PASS | O1: the guesthold keeps Grondia's BGM; Jambo's tent keeps its own track by design |
| #693 | PASS | A2: "Unknown move type: item" |
| #694 | PASS | A1, A3: refused with no confirmation before Votha; confirmation offered after |
| #695 (partial) | PASS / residue | A4: "She turned back"; Iron & Oath prose correct. Anvil `pet` fires `AnvilIntro` but still carries the generic message (#718, comment on #695) |

## Findings, ranked

| sev | finding | verified by | issue |
|---|---|---|---|
| High | Passageway confirmation + combat = permanent deadlock | orchestrator clean client (V1), first attempt; source (#543 guard + "Event pending") | #712 |
| Med | Moves accepted while a needs-input event is pending; later answers teleport Jean | source (`move_player` has no guard; `ch02.py:183` teleports) + A1 log | #713 |
| Med | Advisor prices Rest (any move in progress) as a hit, "potentially lethal" | source (`_estimate_incoming_damage` has no damage check; the multiplier defaults to 1.0) + O1 | #714 |
| Med | Event dialog keys act under LOG | source (`EventDialog.jsx` handler has no `showHistory`) + O1 | #715 |
| Med | Jean's options quote the NPC's private prompt | A5 log (open response) vs `liss.json` | #716 |
| Med/Low | Liss out of voice; Mara invents geography; Jambo describes the wrong tent | A5 log (verbatim), O1 | #717 |
| Low | Polish batch: combat text, audio transitions, labels, a11y, gate `locked` flag, Anvil message | O1 / A1 / A4; the gate flag is source-verified | #718 |

## Reported and not filed

| claim (tester) | verdict |
|---|---|
| "#683 FAIL: status leaks the victory scene, collect-loot duplicates it" (A1, Critical) | **My primer's error.** By design, status echoes held scenes tagged `post_combat: true`, and the SPA filters them (`GamePage.jsx:367`). A1's log (rows 969-970) shows the tag, with collect-loot delivering. A2 and O1 confirm PASS |
| "DevetIntro and IronAndOath never fire; the ferry scene is locked" (A4, Critical) | **Tester error, primer gap.** All three fired as no-input scenes in the entering move's `events_triggered` (A4 log rows 1154, 1165, 1219); A4 looked only in `pending_events`. A1 and O1 reached the end of the beta normally |
| "#690 FAIL: a dead player's save returns the generic 403" (A2) | **Test-session artefact.** The save route refuses unregistered accounts first; the death refusal is pinned by `tests/test_routes_coverage.py` |
| "Ordinary mobs drop nothing" (A1) / "collect-loot always `collected: []`" (A3) | **Method artefact.** 21/22 victories carried `items_dropped`; the testers never passed `item_names` |
| "#688 card shows 1–2 while the preview says 1–1" (O1) | The card renders `min–max` verbatim (`CombatInputDialog.jsx:132`), so the two readings came from different polls. Inconsistent evidence; not filed |
| "Ferry gives a generic 'not today'" (A4) | The same line appears on the natural route (A1); O1 reached END OF BETA in the UI. By design before the prerequisites |
| Vespera/Anvil chat opens 429 (A4) | The per-session chat-open rate limiter: intentional |
| Status poll advances an in-flight move on every GET (A2) | Resume-on-poll, by design |
| Fatigue exhaustion leaves only Wait/Rest mid-fight (A1) | Observation; Rest works mid-combat |

## Dialogue voice

- **Scripted scenes:** complete and correctly ordered on every route; both testers who compared called them markedly stronger than live turns.
- **Live LLM (A5, 21 turns):**
  - Mara was the cleanest, and her chat closed correctly on exhaustion.
  - Kaelen was the strongest match to his file.
  - Jambo was in voice across both tents, with minor tag slips.
  - Devet was partly in voice (one dense turn).
  - Liss was **out of voice** (#717).
  - Vespera was in voice.
- **Provider health:** there were failed turns, but they produced in-voice fallbacks with the reduced drain (#684), and no provider errors reached the player.

## What works

- The whole beta 2 route plays end to end, in the browser and over the API, on the shipped config.
- Every story gate on the route held and opened in order.
- There were no 5xx responses and no tracebacks in any stack log during the run. The #711 unavailability fold removed the 707-line Attack traceback flood from 09-24.
- King Slime is survivable by following the advisor; the Healing Spring and Antidote loops work; the chat mechanics (open, respond, end, history, double-open, bad key) all behaved sanely.

## Recommended order of work

1. **#712** (soft-lock), then **#713** (the server-side guard; it closes the API road into #712).
2. **#715** (a one-line guard) and **#714** (the advisor's threat pricing).
3. **#716** and **#717** together; both are prompt/pipeline work needing the live A/B.
4. **#718** polish.

## Re-running this

`/orchestrate-qa-testers` (`.claude/skills/orchestrate-qa-testers/`). This run's primer is at `docs/qa/beta-live-test-2026-09-25/API_TESTER_PRIMER.md`. The four primer gaps above are now in `references/tester-roles.md`, so the next primer can't repeat them. Tester reports are in `docs/qa/beta-live-test-2026-09-25/tester-reports/`. The memory note is "Live browser QA toolkit".
