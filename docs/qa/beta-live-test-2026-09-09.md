# Live browser beta QA — Grondia through the Nomad Camp (2026-09-09)

**Build:** master @ `562c5263` (Alpha worktree)
**Scope:** the shipped beta arc — Grondia (1,2) through the Nomad Camp — Scenes 0–7 of
`docs/development/beta-test-scope-grondia-arc.md`.
**Method:** six tester agents playing the real React + Flask build concurrently — five in headless
Chromium behind per-tester driver ports, one UI/UX reviewer in the in-app browser pane — against two
backend/Vite pairs with different start states. Every Critical/High was then either reproduced by the
orchestrator on a separate clean client or confirmed in source with file:line before it reached the
tracker.
**Outcome:** 18 issues, **#570–#587**. One Critical.
Raw tester reports are in `beta-live-test-2026-09-09/tester-reports/`, cited screenshots in
`beta-live-test-2026-09-09/shots/`.
**Relationship to the last run:** the 2026-09-08 pass filed #551–#565 and **all of them were closed**
before this run started (only #569, a flaky unit test, was open). This pass is therefore mostly
fix-verification, plus first coverage of the scenes #551 had made unreachable.

## Headline

1. **The beta route can be finished, and #551/#562 are genuinely fixed.** The shipped config draws the
   Rusted Iron Mace (`is_equipped: True`, `damage_type: "crushing"`). T1 played the whole route
   unaided from Grondia (1,2) to Mara at the Nomad Camp, completing both authored pools fights, the
   King Slime, Votha Krr and the camp scenes.
2. **But the shipped level-1 start is a cliff.** T1 **died** at the first authored pools fight, won it
   on a second attempt bottoming out at **6/100 HP**, then found everything afterwards trivial. At
   level 4 the same enemy dies to **one 81-damage hit** losing 1 HP; the level-5 King Slime never got
   Jean below 76%. The curve is a cliff then a flat — **#581**. The fight is *meant* to be solo (the
   slimes are corrosive to Golemites and Votha Krr says so beforehand), which sharpens rather than
   softens the tuning question: no ally is coming.
3. **One Critical: reloading after a fight ends strands the client on the combat screen forever
   (#570).** Engine reports `combat_active: false` with every enemy dead; the client renders combat,
   replays the finished log, and never returns to exploration — through both a reload and a fresh
   navigation, with no client-side state involved.
4. **Two authored story beats cannot fire on the real route.** `GorranGestureEvent` — Scene 4, the
   Grondia farewell — never runs, because the only Grondia→Eastern-Descent route is an object
   teleport and `_commit_teleport` does not evaluate the destination tile's events (**#582**). And the
   Ferry Landing ends the demo without checking `nomad_ferry_ready`, so the closing beat can fire with
   Scenes 6–7 skipped (**#579**).
5. **The UI actively recommends the weapon that caused #551.** The inventory comparison badges the
   Shortsword **"↑ UPGRADE"** and the mace **"↓ DOWNGRADE"** — it ranks raw damage and ignores damage
   type — and the combat INVENTORY panel is consumables-only, so a player who follows it cannot swap
   back mid-fight (**#571**).
6. **The LLM half of this run's scope produced nothing, and it is not the game's fault.** The
   OpenRouter free tier was **already exhausted before the first NPC turn** — 0/50 requests, 40 × 429,
   **zero** successful completions. Voice grading cannot be claimed by this run.

## Setup

| stack | frontend | API | config | start state | LLM |
|---|---|---|---|---|---|
| `full` | :3001 | :5001 | `config_grondia_beta.ini` — **the shipped beta config, unmodified** | Grondia (1,2), level 1, Gorran, mace drawn + full leather, 3 Restoratives + Antidote, 300 gold, `lurker_defeated` | all three gates **off** |
| `camp` | :3000 | :5002 | `config_qa_camp.ini` (untracked) | Grondia (14,5), level 1, Gorran, same loadout, `king_slime_defeated, votha_krr_response_given, lurker_defeated` | NPC chat + Mynx **on** |

Both backends ran `create_app` + `socketio.run(use_reloader=False)` with `FLASK_ENV=testing` and a
blank `GITHUB_TOKEN`.

### Levelling: how, and why one tester stayed at level 1

The maintainer's instruction was that Jean should be at the level a real player would have reached by
the King Slime — 3 or 4 — so the boss is not graded against an unrealistically weak character.
`starting_exp` is the wrong lever: `Player._level_up_api` awards 6–9 **unspent** attribute points per
level, so any seed crossing a level boundary opens the session on a blocking LEVEL UP modal. The debug
routes set the values directly with none:

```
POST /api/debug/player/level      {"level": 4, "exp": 0}
POST /api/debug/player/attributes {"attributes": {"strength": 23, "endurance": 19, "speed": 19}}
```

Modelling three level-ups: ~+1 per attribute per level from `_level_up_api`'s random 0–2 auto bonus,
plus ~22 allocated points (3 × mean 7.5) spent as a melee player would. Only strength/endurance/speed
are set, because writing an attribute also writes its `_base` and would clobber the equipment bonus on
the others (finesse 14 and faith 11 were left intact).

**T3, T4 and T5 ran boosted; T1 deliberately did not.** Those answer two different questions — "is the
fight tuned right for the intended level?" and "can a player finish the config as shipped?" — and the
run's most useful result came from holding them apart.

**T1 disclosed one debug intervention.** After two honest deaths it restored level 3 with the stats it
had already earned by hand at the same point in a previous run, verified against that run's
`/api/debug/player` dump. Every level-1 difficulty judgement in #581 predates it.

**No setup fault reached a tester.** Both stacks were smoke-tested before dispatch: correct start tile,
mace present, zero Socket.IO 400s, zero console errors. Across the whole run, **every** non-noise
browser event on every tester was the documented `403 Cloud saves require a registered account.`, and
both API logs recorded **zero engine stack frames**.

Two orchestrator near-misses, caught before dispatch and recorded so the next run skips them:

- `logs/qa/<tag>/api.log` is **append-only across runs** (7.7 MB before this one started). Reading it
  with `grep | head` returns the *previous* run's banner, which looks exactly like a stack booting the
  wrong config. Read the tail, or record a byte offset before dispatch.
- `POST /api/debug/player/attributes` needs an `{"attributes": {…}}` envelope while its sibling
  `/player/hp` takes flat keys. A flat payload returns `{"success": true, "updated": {}}` — success
  having written nothing.

## Coverage

| Scene | T1 (full route, L1) | T2 (Grondia breadth) | T3 (camp story) | T4 (mobile) | T5 (pools/boss, L4) | T6 (UX/a11y) |
|---|---|---|---|---|---|---|
| 0 Beta briefing (1,2) | PASS | PASS | n/a | n/a | PASS | PASS |
| 1 Grondia navigation | PASS | **PARTIAL** 18/38 tiles | n/a | n/a | PASS | PASS |
| 2 Pools / King Slime | **PASS** (died twice first) | n/a | seeded past | n/a | **PASS** | partial (combat only) |
| 3 Votha Krr | **PASS** (fragment consumed, no repeat) | PASS (cutscene at (7,5)) | seeded past | n/a | NOT REACHED | n/a |
| 4 Gorran farewell | **FAIL — never fires (#582)** | n/a | reported PASS — **misidentified** | reported PASS — **misidentified** | n/a | n/a |
| 5 Camp NPCs present | PASS | n/a | PASS | PASS | n/a | n/a |
| 6 Mara / Devet / Liss | PASS (scripted only) | n/a | PASS (scripted only) | PASS | n/a | n/a |
| 7 River / turnback / demo end | turnback NOT REACHED | n/a | **PASS** (demo end fired) | BLOCKED by #570 | n/a | n/a |

**Known coverage gaps.** T2 reached only 18 of 38 Grondia tiles — its driver deadlocked twice
("timeout waiting for browser thread"), each time restarting from session start; Ecumerium,
Fabricarium, southern Residences, GateEast/Antechamber and GateSouth are uncovered. T5 did not reach
pools (3,1)/(4,1)/(3,2)/(4,2)/(3,3)/(4,3)/(3,4). T4 was stopped at RiversEdge by #570.
`EasternRoadTurnbackEvent` was reached by nobody — it is on **(6,4) RoadEast**, not (5,2) as the beta
plan says, and both testers routed down the west side. **Free-form LLM dialogue has no coverage at
all.**

## Fix verification — the 2026-09-08 batch

| Issue | Verdict | Evidence |
|---|---|---|
| #530 event-dialog keyboard hints | **CONTESTED — refiled as #584** | T3 verified Enter/Escape live; T1 and T6 both found them inert until a mouse click. See the correction note below. |
| #537 description clipping | **VERIFIED FIXED** | T6 swept for clamps/ellipsis across `<main>`; only header titles, and those are not clipped in fact. |
| #538 story pacing + journal | **PARTIALLY FIXED** | Journal now lists all 5 objectives. Pacing not addressed: ~93 stages for `Ch02GuideToCitadel`, ~72 clicks for Votha Krr, shortest body `"Humans."`, four different continue verbs. Skip control inert — **#583**. |
| #541 mobile conversation stage | **VERIFIED FIXED** | T4: portraits stack, dialogue box 255.5px against the old ~36px. |
| #542 phone touch targets | **3 of 4 FIXED** | Category buttons 80×44, modal close 44×44, Feedback title 16px. **Settings toggles still 31×28** — #580. |
| #543 `/world/move` during combat | **VERIFIED FIXED** | T5 and T1: `"Cannot move while in combat"`. |
| #544 talk response swallowed | **VERIFIED FIXED** | T2 across 6+ talks; T3 on the Grondite Elder. |
| #545 Anvil unreachable | **VERIFIED FIXED** | T3: Anvil listed in INTERACT, `AnvilIntroEvent` fires. |
| #547 beta config unusable | **VERIFIED FIXED** | The shipped config drove T1's entire unaided run. |
| #551 pools fight unwinnable | **VERIFIED FIXED** | T1 completed both authored fights; T5 one-hit-killed at level 4. |
| #552 demo end never fires | **VERIFIED FIXED** | T3: Ferry Landing → BetaEndDialog, Send Feedback opens, Jean not teleported. (Gate missing — #579.) |
| #553 raw `AttributeError` to players | **VERIFIED FIXED** | T2 across ~15 objects / 6 classes; T5 and T1 on every pools object reached. Zero raw tracebacks. |
| #554 Attack enabled with no target | **VERIFIED FIXED** | T5 and T1: disabled with a reason string, correct in both directions. |
| #555 damage never explained | **STILL BROKEN — #576** | `damage_preview` serialized at `combat_adapter.py:4000`, **zero** consumers in `frontend/src`. |
| #556 silent Feedback failure | **VERIFIED FIXED** | T2 and T6: inline `role="alert"`, dialog stays open, draft preserved. |
| #557 category tabs swallowed | **FIX WORKS AS DESIGNED; gap remains — #575** | Chrome-occluded tabs forward correctly; move-card-occluded tabs are declined *by design*. |
| #558 hostile vs allied styling | **VERIFIED FIXED where reachable** | T6, T4: `⚔️ HOSTILE` as icon **and** word. Never verifiable against an ally — see #577. |
| #559 buffed-attribute arithmetic | **VERIFIED FIXED** | T2, T5, T6: `Finesse 14 (+4) BASE: 10`. |
| #560 cross-encounter log leak | **VERIFIED FIXED** | T5 (167 lines) and T1 (~400 lines), zero misattribution. |
| #561 enemy outside the camera | **VERIFIED FIXED** | T5, T6, T1: Fit Fight pre-selected, `role="status"` announces the widening. |
| #562 slashing-only loadout | **VERIFIED FIXED** | T1 (`is_equipped: True`, `damage_type: "crushing"`, 46 damage), T2 (EQUIPPED badge), T5 (measured). |
| #563 a11y: unnamed controls | **MOSTLY FIXED** | T6: zero unnamed controls anywhere; combat narration is `aria-live="polite"`. **Residual:** exploration has zero live regions; combat tabs expose no selected state. |
| #564 mobile toolbar / severity | **VERIFIED FIXED** | T4 and orchestrator: severity buttons 97×44. |
| #533 NPC-chat fallback (older) | **VERIFIED under total provider loss** | Retry ×2 → deterministic fallback → honest UI banner, no crash. |

### Correction: #530

An earlier draft of this report recorded #530 as verified fixed, on the strength of the source reading
plus T3. That was too confident. T1 then independently reproduced T6's symptom with a specific
mechanism, making it two testers against one. The source facts are genuinely ambiguous — the listener
sits on `document` precisely so focus cannot matter, but the component's own comment confirms focus
never lands on the stage — and a keydown only reaches a `document` listener if the page itself has
focus. It is refiled as **#584** with all three accounts and the one experiment that would settle it.

## Findings filed

| Issue | Severity | Finding | How verified |
|---|---|---|---|
| **#570** | **Critical** | Reload after a fight ends strands the client on the combat screen | T4 ×3 on mobile; orchestrator reproduced on a clean desktop client; cause traced to `GamePage.jsx:471-478` + the `useCombatCoordinator` log gate |
| **#581** | High | Shipped level-1 start loses the run at the first authored pools fight; the rest is trivial | T1 unboosted (2 deaths, won at 6/100 HP) + T5 at level 4 (1 HP lost) |
| **#582** | High | `GorranGestureEvent` never fires — teleport arrival skips destination tile events | T1 both arrival paths + source; orchestrator reproduced the gate-object path |
| **#571** | High | Inventory badges the Shortsword UPGRADE and the mace DOWNGRADE | T5, with measured damage both ways |
| **#577** | High | Gorran does not join combat on the Eastern Descent *after* the King Slime; `/api/status` reports an empty party while the PARTY panel shows him | T1 (4 post-boss fights) + T5 (`party_members: []` at the arena). **Scoped down after maintainer review** — see the correction below |
| **#572** | High | `TileDescription` objects listed as interactables with a `null` name | T5 and T1; call site and class confirmed in source |
| **#573** | High | Cleansed pool tiles show corrupted **and** clean text together | T5 and T1; additive-vs-replacement mechanism confirmed in source |
| **#575** | High | Category tabs covered by a move card stay dead (raise the nav's z-index) | Orchestrator measured the chrome-vs-card split with real pointer clicks; T5 and T6 concur |
| **#576** | High | `damage_preview` computed and serialized but never rendered | T5; grep reproduced by orchestrator |
| **#579** | High | Ferry Landing can end the demo before Mara's scene | Orchestrator, source only — the gate was lost when #552 moved onto the object |
| **#583** | High | Hold-to-skip is inert on the longest scenes | T1 (8-second hold) and T6; caveated — synthetic pointer events only |
| **#584** | High if real | **Contested:** conversation scenes may not be keyboard-advanceable | T1 + T6 symptom, T3 contrary, source ambiguous |
| **#585** | High | A z-2100 overlay covers object-dialog controls; only Escape recovers | T1, with T2's corroborating hit-test observation |
| **#586** | High | King Slime surge hits for 84 with one grey log line as warning | T1 (died 79/114 → 0 at level 3) |
| **#587** | High | START OVER after death returns to the login page | T1, twice |
| **#578** | Low | Three double-encoded em dashes in the Nomad Camp map | Orchestrator codepoint scan; T3 saw it live |
| **#574** | Low | `Ch02KingSlimeMemoryFlash` narrates a pickup that no longer happens | T5's observation, rescoped by orchestrator from source |
| **#580** | Low/High | Touch targets under 44px (settings sliders/toggles, three combat controls) | Orchestrator and T4, all measured |

## Reported and not filed

Recorded so the next run does not re-investigate them.

- **"Gorran never joins any fight", High (T1 and T5) — scoped down after maintainer review.** Two
  testers reported `allies: []` across thirteen fights and the orchestrator filed it whole. **Gorran
  staying out of the Mineral Pools and the King Slime arena is intended design** — the slimes are
  corrosive to Golemites and Votha Krr says so before the descent — so ten of those thirteen
  observations are correct behaviour and were withdrawn. The PARTY panel was also fine
  (`👥 PARTY (1) — GORRAN, LVL 1, HP 200/200`); the orchestrator's original title claiming otherwise
  was wrong. What survives in #577 is the four **post-King-Slime Eastern Descent** fights, where
  Gorran should be an ally and is not, plus `/api/status` reporting `party_members: []` while the
  PARTY panel shows one member. **Lesson: none of the six testers or the orchestrator checked the
  lore or the preceding Votha Krr dialogue before calling an absent ally a bug.** `docs/lore/` and the
  chapter script are part of the verification bar for anything that looks like missing content.
- **T3's and T4's "Gorran farewell PASSED" — misidentification.** Both reported Scene 4 firing. The
  orchestrator walked their exact path (directional to (15,5), then the Eastern Gate object) and got
  `pending: []` and no scene. What they saw was the passageway's own transit narration — *"The mountain
  air hits without warning… Behind Jean, the Eastern Gate of Grondia has…"* — which reads like a
  farewell beat. The real prose is *"Gorran paused at the gate as it sealed…"*, which nobody saw. Filed
  as #582 on T1's evidence. **The 2026-09-08 note recording this scene as verified may have been the
  same error.**
- **#557 "regression" (T6) — rescoped, not a regression.** T6 tested DEFENSIVE with OFFENSIVE open,
  which a move card covers — the case `useOccludedNavHandoff` declines *by design*, documented in its
  own comment and pinned by a unit test. The orchestrator confirmed the handoff works for
  chrome-occluded tabs with a real pointer click. The genuine residual is #575.
- **T6's mobile layout findings — dropped, pane-emulation artifact.** T6 reported `MAIN` at 501px in a
  non-scrolling 375px document, six controls off-screen, and tabs at 68×37. Three independent tests
  found none of it: a true `--mobile` driver in combat, a desktop driver resized to 375 without reload,
  and the same at 375 after reload with a move panel open (T6's exact scenario). All three:
  `document.scrollWidth == innerWidth == 375`, zero off-screen controls, tabs **80×44**. The three
  genuinely undersized combat controls were kept and filed in #580.
- **"LLM connection down globally", High (T3) — dropped, environmental.** The provider was reachable;
  the OpenRouter free tier was spent (0/50 requests, resets 2026-09-10 00:00Z). Not a defect.
- **"Event-input retry loop with no cap", Medium (T2) — dropped.** Self-induced (T2 raced a scripted
  API resolution against the UI) and factually wrong: `useEventManager.js:19-33` has a bounded
  `maxAttempts` with exponential backoff, and line 111 documents this exact stale-`event_id` 400.
  T2 rated its own confidence low.
- **"MineralFragment never spawns", High (T5) — rescoped to Low (#574).** T5 checked the tile's item
  list; `ch02.py:613` grants the fragment directly to inventory by design under #378/#371, and T1
  confirmed `Rare Mineral Fragment` in inventory. The stale memory-flash prose is what was filed.
- **Audio autoplay `NotAllowedError` / `ERR_ABORTED` on BGM** — headless Chromium blocks autoplay.
- **`403 Cloud saves require a registered account.`** — expected for test-bypass sessions.

## Dialogue voice

**No coverage.** All three NPCs fell back to deterministic prose because the provider quota was
exhausted. T3 spent 6 of its 14 budgeted exchanges before recognising the pattern and stopping —
correct judgement. No prohibited phrases appeared in the scripted lines collected, and the scripted
beats (Votha Krr's "Humans.", the camp intros, Mara's 36-stage first contact) read in voice.
**Re-run the camp leg after 2026-09-10 00:00Z to get the coverage this run intended.**

Worth fixing regardless: the local `.env` pins `MYNX_LLM_MODEL=stepfun/step-3.5-flash:free`, the
retired slug `.env.example:105-119` warns against after #533, so the first call of every turn is a
wasted 404 before rotation begins. Set it to `auto`.

## What works

- **Zero backend crashes.** Both API logs recorded zero engine stack frames across six testers and
  roughly four hours of play.
- **The route is completable end to end.** #551, #562 and #547 are genuinely fixed.
- **The demo has an ending again.** #552's Ferry Landing → BetaEndDialog → Send Feedback works, with
  Jean correctly not teleported.
- **Story scenes are substantial and hold up.** `Ch02GuideToCitadel` (~93 stages), the King Slime
  memory flash (13 stages), Mara's first contact (36 stages) all played complete, with correct
  portraits and working branches. `AfterKingSlimeReturn` consumed the fragment and did not repeat.
- **Combat legibility improved markedly.** #554, #559, #560, #561 all hold; locked moves state their
  reason in words (`⚠ Enemy out of range (too far)`); damage previews are numerically accurate even
  though they are not rendered.
- **Accessibility took a real step.** Zero unnamed controls anywhere T6 looked; combat narration is a
  polite live region.
- **The Feedback dialog is the reference implementation** — 16px inputs, 44×44 close, inline
  `role="alert"` on failure with the draft preserved.
- **Graceful degradation under total LLM loss.**

## Recommended order of work

1. **#570** — the Critical. Unrecoverable in-session.
2. **#581** — the difficulty cliff. The pools fight is intentionally solo, so this is a straight
   tuning decision: most likely raise the beta's starting level to the 3–4 a real player would have.
3. **#571** — the UPGRADE/DOWNGRADE inversion actively undoes #562 for any player who trusts it.
4. **#582 and #579** — two authored beats that cannot fire correctly on the real route.
5. **#572 + #573** — same call site in `ch02.py`, one sitting.
6. **#586** — fairness pillar; cheap (the battlefield already renders "Preparing" for other moves).
7. **#576** — the backend work is done and discarded.
8. **#584** — needs one human keyboard check before it can be actioned either way.
9. **#575, #583, #585, #587, #580, #578, #574** — the remainder.
10. **Re-run the camp leg for LLM voice** once the quota resets.

## Re-running this

Use `/orchestrate-qa-testers`. Setup facts, gotchas and the level-boost recipe are in the project
memory note "Live browser QA toolkit". Four lessons added this run: the API log is append-only across
runs (read the tail); **pane `resize_window` is not a substitute for a `--mobile` driver**; check the
LLM provider's remaining quota *before* promising an LLM-scoped run; and a scene that "fired" needs its
actual prose quoted, because the passageway transit narration was mistaken for the Gorran farewell by
two testers this run and possibly by the last run too.
