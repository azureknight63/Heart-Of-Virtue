# Live browser beta QA — Grondia through the Nomad Camp (2026-09-08)

**Build:** master @ `4697569b` (Alpha worktree)
**Scope:** the shipped beta arc — Grondia (1,2) through the Nomad Camp — Scenes 0–7 of
`docs/development/beta-test-scope-grondia-arc.md`. **Scripted dialogue only**: all three LLM gates
(`NPC_CHAT_LLM_ENABLED`, `MYNX_LLM_ENABLED`, `COMBAT_LLM_ENABLED`) were forced off at the stack level,
so this run cost zero provider tokens and says nothing about free-form NPC chat.
**Method:** five tester agents playing the real React + Flask build concurrently — four in headless
Chromium behind per-tester driver ports, one UI/UX reviewer in the in-app browser pane — against two
backend/Vite pairs with different start states. Every Critical/High was then either reproduced by the
orchestrator on a separate clean client or confirmed in source with file:line before it reached the
tracker.
**Outcome:** 15 issues, **#551–#565**. One is a release blocker for the beta route as shipped.
Raw tester reports are in `beta-live-test-2026-09-08/tester-reports/`, cited screenshots in
`beta-live-test-2026-09-08/shots/`.
**Relationship to the last run:** the 2026-09-06 pass filed #528–#547; all were closed except #538.
This run is therefore half fix-verification, half first-ever coverage of the two scenes #528 had made
physically unreachable.

## Headline

1. **The beta route still cannot be completed — but the cause has changed.** #528 is genuinely fixed:
   the orchestrator crossed Grondia (2,4) (whose exits really are the restricted
   `['northwest','southeast']`), then walked the Mineral Pools' whole (2,y) column and entered the
   King Slime arena, with `(2,4) GrondelithNarrowPass exits=['east','north','south']` — south intact.
   That walk only completed because Jean had been debug-boosted. A real player is stopped two tiles
   earlier by a **different, deterministic blocker**: see 2.
2. **A fight in the Mineral Pools cannot be won, lost, fled, or walked away from. #551, Critical.**
   Pools (2,2) and (2,4) — the only path to the arena — each carry an authored, non-random spawner for
   `CorruptedStoneCreature` (60 hp, protection 18, `slashing 0.4`). Jean's shipped Shortsword is
   slashing, so a ~46 hit resolves to `46 × 0.4 = 18.4` against 18 protection — **zero**. Its 22 damage
   against Jean's protection 19 is **also zero**, so it cannot kill him and end the fight. There is no
   flee move, and `/api/world/move` is correctly refused in combat. T1 reproduced the permanent stall
   from two clean sessions. Scenes 2 and 3 are unreachable in the shipped beta, which is the same
   outcome as #528 last run by an unrelated cause.
3. **The beta has two end-of-demo mechanisms and neither can fire on its own route. #552.**
   `DemoEndEvent` is placed on no tile in any map — its docstring names the Ferry Landing's
   `events_before`, which is empty, and `git log -S` shows it was never placed. Separately the frontend
   ships a finished, unit-tested `BetaEndDialog` with a **Send Feedback** button, but its only trigger
   is a `beta_end` flag set solely on a Lurker kill, which this beta lists as out of scope. **Issue
   #326 checks the wiring off as "Done".** So the beta's entire in-game feedback funnel is dead, and
   has been through both live QA passes.
4. **Eighteen of the nineteen closed issues hold up; one is half-fixed.** #529, #530, #534, #535,
   #536, #539, #541, #543, #544, #545, #546 and #547 all verified good. **#537 is half fixed** — the
   description clipping is genuinely gone, but telling a hostile from an ally is still impossible in
   the room panel and the combat target picker (#558), which the orchestrator confirmed by measuring
   computed styles: ally and hostile rows are byte-identical.
5. **Three silent UI failures, each of which reads as a frozen game.** The Attack button stays
   enabled with no target in range and swallows the server's rejection — T1 clicked it twelve times
   over two and a half minutes before checking the network tab (#554). An open move-category panel
   swallows clicks on every other category tab, confirmed with a *raw* pointer event by three
   independent parties (#557). And ~31 map-authored object keywords dispatch straight into `getattr`,
   showing players `Error executing action: 'WallInscription' object has no attribute 'touch'` (#553).

## Setup

| stack | frontend | API | config | start state |
|---|---|---|---|---|
| `full` | :3001 | :5001 | `config_grondia_beta.ini` — **the shipped beta config, unmodified** | Grondia (1,2), level 1, Gorran, worn Shortsword + full leather, 3 Restoratives + Antidote, 300 gold, `lurker_defeated` |
| `camp` | :3000 | :5002 | `config_qa_camp.ini` (new, untracked) | Grondia (14,5), level 1, Gorran, same loadout, `lurker_defeated, king_slime_defeated, votha_krr_response_given` |

Both backends ran `create_app` + `socketio.run(use_reloader=False)` with `FLASK_ENV=testing`, a blank
`GITHUB_TOKEN`, and — new this run — `--no-llm`, which *assigns* all three LLM gates to `0`. That flag
had to be added: `.env` ships `MYNX_LLM_ENABLED=1` and `NPC_CHAT_LLM_ENABLED=1`, `load_project_env()`
uses `override=False` so only a pre-set value wins, and the combat Tactical Advisor bills through a
third variable (`COMBAT_LLM_ENABLED`) that falls back to the second. Verified in the API startup
banner rather than assumed.

**No setup fault contaminated any tester this run.** Both Vite ports were accepted Socket.IO origins
(3000/3001); a pre-dispatch smoke on both stacks found zero `socket.io` 400s and zero non-noise console
errors, and the first five minutes of all four driver logs were re-checked after dispatch and were
clean. Every 4xx in any driver log was the documented `Cloud saves require a registered account.` 403.
Nothing in this report needs a contamination caveat — **except one finding that the setup caused
outright**, called out in "Reported and not filed".

Two of the orchestrator's own mistakes were caught by the smoke test and are recorded because they
would otherwise have cost five testers their budgets:

- The first `config_qa_camp.ini` seeded `starting_exp = 1550`, which opened the session on a blocking
  `LEVEL UP` modal with 33 unspent points. Dropped the seed entirely — a level-1 Jean has protection
  19 against TalusHound 16 / ScarpAdder 22 damage and hits for 40–60 against their 35–36 HP, so the
  descent is survivable unseeded, and the run then matched the shipped config exactly.
- A *working* staged dialog was briefly mis-called a soft-lock, because an Event Result dialog advances
  in place and keeps its node in the DOM, so `"dialog" in aria()` stays true. The correct probe is
  diffing `.modal-content` inner text.

Both lessons went into the tester primer, along with the fact that the dismiss button's accessible
name is `Close` while CSS renders it `CLOSE`.

`config_qa_camp.ini` starts at Grondia **(14,5)**, one tile west of the east gate, on purpose:
`GorranGestureEvent` requires `previous_tile` to be a Grondia tile, and `Player.teleport()` — which
every Passageway uses — never sets it. The 2026-09-06 leg config started *on* the gate tile, which is
the sole reason Scene 4 never fired for four testers that run. From (14,5) it fires correctly.

One brief error worth recording, because a tester caught it: the brief told T1 it would fight the King
Slime "with Gorran (200 HP)". T1 found that the `Ch02` threshold beat leaves Gorran at the atrium arch
and PARTY reads "No party members" — **Jean faces the King Slime solo**. Gorran's 200 HP applies on the
eastern descent, not in the arena.

## Coverage

| Scene | T1 full route (opus) | T2 Grondia breadth | T3 camp story | T4 camp on a phone | T5 UX/a11y reviewer |
|---|---|---|---|---|---|
| 0 Briefing (1,2) | **PASS** | PASS (cleared, not graded) | — | — | — |
| 1 Grondia navigation + Citadel | **PASS** | **PASS** — 37/39 tiles, all 5 sub-maps, shop buy+sell, all panels | — | — | — |
| 2 Mineral Pools / King Slime | **FAIL — route blocker (#551)** | first tiles only, by design | — | — | — |
| 3 Votha Krr fragment return | **NOT REACHED** (behind #551) | dormant without the fragment: correct | — | — | — |
| 4 Eastern Gate / Gorran farewell | **PASS** | — | **PASS** | **PASS** | **PASS** |
| 5 Descent / camp arrival | partial — 2 of 3 fights won, camp not reached | — | **PASS** | **PASS** | partial (ended in combat at (3,4)) |
| 6 Camp scenes (Mara, Devet, Liss, Iron & Oath, Anvil) | not reached | — | **PASS — all fired, in order, verbatim** | **PASS** | NOT REACHED |
| 7 River tiles + turnback (6,4) | not reached | — | **PASS** (fired twice, both landed at (5,4)) | partial | — |

T1 was forced to restart its driver twice, both times by #551. The King Slime fight itself was
therefore **never fought by anyone** — see the note below.

### The King Slime: still unmeasured, and why

The run's open balance question — can a level-1 Jean with the shipped loadout beat a 400 hp boss —
remains unanswered, because #551 sits between the player and the arena. What is now known:

- Jean fights it **solo** (Gorran is left at the atrium arch).
- Attack costs 77 of 190 fatigue with a multi-beat recoil, so roughly one attack per two actions.
- `KingSlime` is 400 hp, protection 15, `slashing 0.65`, `crushing 1.2`, `fire 1.5`
  (`src/npc/_enemies.py:249-265`) — so the shipped slashing loadout is about half as effective as a
  blunt one here too.
- The orchestrator reached the arena only with debug-boosted stats, which makes any difficulty reading
  from that session worthless.

Re-run this leg once #551 is fixed, before signing the beta route off.

## Findings, ranked

Severity follows the beta plan (Critical = crash/soft-lock/data loss/route blocker; High = wrong flag,
event not firing, NPC missing, dialogue truncated, UI action not working; Low = typo, visual, pacing,
voice). "Verified" means reproduced by the orchestrator on a clean client or confirmed in source.

| # | Sev | Finding | Verified how | Issue |
|---|---|---|---|---|
| 1 | **Critical** | Corrupted Stone Creature at pools (2,2)/(2,4) cannot be damaged, killed, escaped or lost to — permanent soft-lock, blocks Scenes 2–3 | T1 ×2 clean sessions + authored spawner and full damage chain in source | [#551](https://github.com/azureknight63/Heart-Of-Virtue/issues/551) |
| 2 | High | `DemoEndEvent` placed on no tile; `BetaEndDialog` gated on an out-of-scope flag — no end-of-demo beat, no feedback funnel | source (empty `events_before`, `git log -S`, `beta_end` trigger) + T3 ×2 | [#552](https://github.com/azureknight63/Heart-Of-Virtue/issues/552) |
| 3 | High | Map-authored object keywords dispatch via bare `getattr`; ~31 placements show raw `AttributeError` text | source (`game_service.py:2291`) + audit of every map placement + T2 on 3 instances | [#553](https://github.com/azureknight63/Heart-Of-Virtue/issues/553) |
| 4 | High | Attack button enabled with no target in range; server rejection swallowed silently | T1 ×2 with network trace; orchestrator confirmed `viable_targets: []` in the live option payload | [#554](https://github.com/azureknight63/Heart-Of-Virtue/issues/554) |
| 5 | High | "struck but did no damage" never explained; advertised damage range doesn't predict outcomes | T1 ×2; T5 independently; arithmetic confirmed in source | [#555](https://github.com/azureknight63/Heart-Of-Virtue/issues/555) |
| 6 | High | A failed Feedback submission is silent; the report is lost | T1 (`[role=alert]` count 0) — see the scoping note in the issue | [#556](https://github.com/azureknight63/Heart-Of-Virtue/issues/556) |
| 7 | High | Open move-category panel swallows clicks on the other category tabs | **three** independent reproductions, all with `raw_click` (T3, T1, orchestrator) | [#557](https://github.com/azureknight63/Heart-Of-Virtue/issues/557) |
| 8 | High | Hostile and allied NPCs styled identically in the room panel and the target picker | orchestrator measured computed styles on a clean client + T5; `is_hostile` is on the wire and unread | [#558](https://github.com/azureknight63/Heart-Of-Virtue/issues/558) |
| 9 | High | Buffed/debuffed attributes render the total with a sign next to `BASE: n` — `+14` over `BASE: 10` reads as 24 | source (`StatsPanel.jsx:182`) + T5 measurement | [#559](https://github.com/azureknight63/Heart-Of-Virtue/issues/559) |
| 10 | Medium | Combat log attributes an ally's attack to an enemy from an earlier, finished encounter | T3 ×2, different enemy pairs; root-caused in source (`_npc.py:255-267`) | [#560](https://github.com/azureknight63/Heart-Of-Virtue/issues/560) |
| 11 | Med–High | Combat opens with the enemy outside the default camera and asks the player to fix the framing | T5 2/2 fights (8 ft, 7 ft); orchestrator 0/1 (6 ft) — distance-gated, mechanism confirmed | [#561](https://github.com/azureknight63/Heart-Of-Virtue/issues/561) |
| 12 | High | Beta loadout is slashing-only; the descent's first enemies resist slashing to zero, with no in-text hint | T4 (`{"min":0,"max":0}` preview, two fights) + resistance chain in source | [#562](https://github.com/azureknight63/Heart-Of-Virtue/issues/562) |
| 13 | High (a11y) | Combat log and narration not announced; 6 unnamed modal controls; 6 further gaps | T5 measured; items 1, 2, 6, 7 re-confirmed in source | [#563](https://github.com/azureknight63/Heart-Of-Virtue/issues/563) |
| 14 | Low | Mobile: battlefield toolbar and feedback severity controls measure 26–28px tall | T4 `bounding_box()` across 3 encounters | [#564](https://github.com/azureknight63/Heart-Of-Virtue/issues/564) |
| 15 | Low | Polish batch: 19 items (copy, labels, keyboard/hit areas, empty states, cosmetic) | various, each attributed | [#565](https://github.com/azureknight63/Heart-Of-Virtue/issues/565) |

### Fix verification ledger

| issue | verdict | evidence |
|---|---|---|
| #528 tile mods keyed without map name | **FIXED** | orchestrator crossed Grondia (2,4) then walked pools (2,4) with south intact into the arena (2,6); T1 on eastern-descent (2,4) — runtime exits match the authored JSON exactly; `_tile_mod_key` in source |
| #529 undismissable arrival modal | **FIXED** | orchestrator smoke; T2 at both named sub-maps, first click every time; T1's six-way dismissal test |
| #530 event dialog key hints do nothing | **FIXED** | orchestrator (`1` advanced the briefing with focus in the dialog); T5 on two dialogs; T3 |
| #534 advisor narrates the wrong battle | **FIXED** | "ANALYSIS OF PREVIOUS CYCLE" is now labelled as such; dev-branding footer gone; T1 all four sub-items |
| #535 combat UI batch | **FIXED** | `RESOLVING BATTLE…` during the delay (T5, T4); confirm verb reads `ADVANCE` not `STRIKE` on an ally (orchestrator); ring colours alignment-only |
| #536 accessibility | **FIXED, residual gaps** | landmarks, 0 unnamed of 21/14 on primary screens, focus trap + restore, visible ring, HP as `aria-label`. Gaps → #563 |
| #537 description clip + hostile/ally | **HALF FIXED** | clip fixed (242/242, cap 360px; ~39 descriptions clean). Hostile/ally half open → #558 |
| #539 Gorran never captioned | **FIXED** | T3: Gorran never speaks or is captioned in `LissObservingEvent`, matching the scripted intent |
| #541 VN stage unusable on a phone | **FIXED** | T4: portraits stack in a responsive grid, full-width 255.5px dialogue box, ~28 chars/line, 1–4 speakers, no horizontal scroll |
| #542 touch targets | **FIXED for everything it named** | combat categories, `✕`, feedback input font all at spec (T4); new offenders → #564. **Settings toggles NOT REACHED** |
| #543 move accepted during combat | **NOT REGRESSED** | guards at `game_service.py:1241` and `:2169`; T5 got `400`s; the orchestrator's own pools walk was refused mid-combat |
| #544 talk response not rendered at the Citadel | **FIXED** | T1 |
| #545 Anvil missing from INTERACT | **FIXED** | T3 |
| #546 Jambo's stocked no healing items | **FIXED** | T2: 5 potion types in the Grondia shop, buy and sell both work; T3 at the camp tent |
| #547 beta config cannot drive a live run | **FIXED** | the `full` stack ran the route off `config_grondia_beta.ini` unmodified; Scene 4 fires. (Its loadout is a separate problem — #562, #551) |
| #538 story pacing / dialog chrome | **STILL OPEN (accepted)** — not re-filed; new evidence below | |

### #538 — new evidence, not re-filed

T5 was asked to judge whether this is still the worst UX problem rather than re-report it. Its answer:
yes in aggregate, and worse than the closed report implies, because the affordances **stack inside a
single modal and one of them lies**. Measured across three Enter presses on one Event Result dialog:
stage 1 offered `▾ click or press Enter to continue`; stage 2 offered `▾ click to finish` *while two
paragraphs were still unrevealed*; stage 3 offered `▾ click to finish` **and** `CLOSE` **and**
`or click anywhere to continue...` simultaneously. The prose is centred italic 16px in a **718px**
measure (~110 characters per line, against the 45–75 the project's own accessibility rule asks for),
and the two hint lines are the `#666` that fails contrast.

Its recommendation, in order: collapse the four continue affordances into **one** state-labelled footer
control (`Continue` while stages remain, `Close` on the last), which is one component and no prose
edits; then add a `TEXT SPEED` row beside the `COMBAT SPEED 0.5x–2x` that Settings already ships. T5's
own caveat is worth honouring: #561 (the camera default) is the worse *first-impression* problem and
cheaper, so do that first.

Two concrete bugs in the same family were split out into #565 rather than left as pacing commentary:
the `📜 LOG` button keeps keyboard focus after `↩ BACK`, so the advertised Enter re-opens the log
instead of advancing (it ping-pongs indefinitely); and `or click anywhere to continue...` is false —
a click inside the modal body does nothing while a click on the overlay closes it.

T3 added one line of evidence: advancing with a click and an Enter in the same sub-second silently
dropped two short beats, and Enter-only captured every beat cleanly. Recorded on #538, not filed —
see below.

## Reported and not filed

Kept so the next run does not re-investigate these.

- **The Feedback 503 itself (T1): caused by this run's own setup, not a product bug.** `GITHUB_TOKEN`
  is deliberately blanked so QA cannot file real issues, and `_create_github_issue` correctly returns
  "Feedback service is not configured on this server." (`feedback.py:447-450`, 503 at `:634-637`). T1
  drew this distinction itself. Only the *client's silent handling* of a failed submit was filed
  (#556), and even that carries an explicit note that the cause may be the auto-dismissing toast T2
  independently observed rather than missing error handling — `FeedbackDialog.jsx:345-346` does have a
  `toastError`.
- **"No `aria-live` region anywhere" (T5, as written): FALSE, refiled with a correct scope.** Four
  live regions exist (`CombatManager.jsx:53-54`, `Battlefield.jsx:280`, `ToastContext.jsx:144-145`,
  `NpcChatPanel.jsx:42-43`), and T5's `[aria-live]` selector also misses `role="status"`, which carries
  an *implicit* polite region. `Battlefield.jsx:227-232` even documents a deliberate decision not to
  make the beat counter live. The true, narrower gap — the combat log and narration specifically — is
  #563 item 1.
- **"Hostiles look identical on three surfaces" (T5): it is two.** The INTERACT sub-claim cites
  Grondia (15,5), whose only NPCs are Gorran and a Grondite — both friendly — so there was no hostile
  row to differentiate. `InteractPanel.jsx:113-119` *does* apply `colors.danger` to hostile rows, and
  the orchestrator could not exercise that path at all: `is_hostile` requires `aggro=True`, and an
  aggro NPC starts combat on tile entry, which makes INTERACT unreachable. Flagged inside #558 as
  worth a separate look — possibly dead code in practice — not claimed as broken.
- **"Every combat opens with the enemy off-screen" (T5): distance-gated.** T5's enemies spawned at
  8 ft and 7 ft; the orchestrator's at 6 ft, with no banner. `Follow` is 13×13 cells (±6), so the
  banner fires above 6 ft on a random per-encounter roll — 2 of 3 observed fights. #561 states the
  real rate.
- **"An enemy with literally no resistances" (T1's premise in its zero-damage finding): wrong, and the
  correction strengthens the finding.** The Rumbler does resist slashing (0.5), and
  `combat_adapter.py:2546-2552` syncs it at combat start. The resistance simply is not visible to the
  player anywhere — which is the actual defect, filed as #555.
- **"No equip comparison / equipped gear missing from INVENTORY" (T5): dropped — tester reach, not a
  defect.** The comparison is implemented (`ItemDetailDialog.jsx:26-28`, fed by
  `ItemComparisonSerializer`), `is_equipped` ships per item (`inventory.py:232`), equipped items are
  bucketed by slot (`:108-117`), and `full-state` carries an `equipment` section. T5 only opened a
  *consumable's* detail, where no comparison applies. One manual check is folded into #565.
- **`Turn 75%` shown beside "Tactical analysis unavailable": working as designed.** `_NO_TACTICAL_READ`
  (`ai/combat_strategist.py:227`) is deliberately retained for catch-all categories, and #534 bug 2
  only ever split out the WARM/Offensive collision. Only the wording nit went into #565.
- **Native Enter/Space on a focused button generating no click (T5): harness limitation**, correctly
  not filed by T5 itself. A CDP-synthesised keydown reaches the element (`defaultPrevented === false`)
  but Chrome generates no click. Digit keys and Escape *are* delivered and work.
- **Issuing a move while a modal is open (T5):** possible only via a DOM `.click()` that bypasses the
  overlay; the server rejected both attempts (`400`) and focus is trapped, so it is not
  player-reachable.
- **Rapid click+Enter dropping a dialogue beat (T3): recorded on #538, not filed.** T3 itself calls it
  a harness artefact in its dialogue notes while calling it player-reachable in the finding, and the
  evidence came from a scripted sub-second double-input loop. Plausible for a real double-tapper,
  unproven.
- **Mojibake `â€"` in extracted room text (T3):** the map JSON is clean; a text-extraction artefact.
  Third run in a row it has been raised, and it is in the primer's known-noise list.
- **Nursery spawning 5 children rather than 4 (T4):** map-authored spawner randomisation. The
  orchestrator's brief was the thing that was wrong — as was its "King Slime with Gorran" premise.
- **Autosave 403s, "Autosave failed" toasts, BGM autoplay `NotAllowedError`, CSP `[Report Only]`:**
  expected consequences of test-session login and headless Chromium.

## Scripted dialogue

Nothing here reflects on the LLM path, which was switched off.

T3 captured every camp scene stage-by-stage and compared it line-for-line against `src/story/ch03.py`:
**every quoted line landed intact and in order**, and the scenes fired in strict dependency order —
`GorranGestureEvent` → `NomadCampSmellEvent` + `CampEntryGreetingEvent` (chained in the *same* visit,
no step-off needed, which answers a question the brief raised) → `MaraFirstContactEvent` →
`DevetIntroEvent` → `LissObservingEvent` → `MaraObservationEvent` (correctly taking the `has_mace`
branch, because T3 was carrying a Bludgeon-subtype drop) → `IronAndOathIntroEvent` →
`AnvilIntroEvent` → `EasternRoadTurnbackEvent` twice.

Voice held. T3 read `mara.json`, `devet.json` and `liss.json` in full and grepped the scripted prose
against their `prohibited_phrases`: **zero hits for all three**. Mara's sardonic economy, Devet's
two-word replies ("Eat." / "It's food.") and Liss's unfiltered run-on curiosity all match their
`voice_summary`. Gorran stays narrated rather than spoken throughout, correct for a Stage-1 speaker,
and he is never captioned during Liss's scene — the #539 fix, confirmed against prose that is explicit
he gives no sign of having heard her.

T5's independent judgement on the gate scene is worth recording: *"Gorran paused at the gate as it
sealed. His palm rested flat against the stone — one breath, maybe two. Then he turned without a word
and followed."* / *"Jean did not ask him."* — which it called the best writing it saw all session, and
the strongest argument for fixing #538 by changing the chrome and leaving the prose alone. Gorran's
in-combat ambient lines hold the same register ("Gorran fights the way stone moves downhill: with
momentum, not urgency.").

One prose defect: a line is duplicated across two stages of `Ch02GuideToCitadel` — *"He watched Jean's
face. Jean wasn't showing much."* closes log entry [7] and opens [8] verbatim (in #565).

## What works and should not regress

- **The camp arc is the strongest content in the build** and now delivers cleanly: every scene fires
  once, in order, with correct speaker labels, portraits and emotion tags, and no repeat on revisit.
- **#528's whole class of bug is gone.** Tile modifications are map-namespaced, and both victim tiles
  behave correctly.
- **Accessibility on the primary screens is genuinely good now**: landmarks, zero unnamed interactive
  elements on exploration (21) and combat (14), `role=dialog aria-modal=true` with resolving
  `aria-labelledby`, focus moved in, trapped and restored to the launching button, a visible focus
  ring, and a shipped reduced-motion setting.
- **Mobile exploration**: no horizontal scroll at 375px, zero sub-44px targets on the audited screens,
  and the VN stage now stacks portraits and reads properly at four speakers.
- **`▸ WHAT MOVES IT`** (the Heat explainer) is the "every number is explainable" pillar done properly
  — it expands to the full gain/loss table with drift and clamp values. #555 is the same idea applied
  to the outcome line.
- Hit chance is surfaced *before* you commit; the loot dialog does the carry-weight arithmetic for
  you; `TURN ORDER — BEATS UNTIL EACH ACTION RESOLVES` is legible and disambiguates duplicate enemies;
  combat pauses indefinitely for the player and a pending encounter survives a reload intact.
- The movement d-pad's disabled set matched the engine's exits on **every** tile checked — T2 across
  37 Grondia tiles, T5 across 9, T4 across the whole descent, T1 throughout. Zero mismatches.
- Grondia's five sub-maps, its shop (buy and sell), and all six panels work.

## Recommended order of work

1. **#551** — nothing in the back half of the beta can be tested until it lands. The cheapest fix
   (give the beta config a Bludgeon) also fixes #562 and restores the `has_mace` branch; the durable
   fix is an engine guard so a fight neither side can resolve cannot be entered, or a flee option.
2. **#555** — the message that makes #551 and #562 invisible. Fixing it converts a mystery soft-lock
   into a solvable puzzle and is worth doing regardless of how the loadout is resolved.
3. **#552** — the beta cannot collect the feedback it exists to collect. Decide between the two
   mechanisms; the `BetaEndDialog` path is the better UI. Add a test that no `src/story/` event class
   is silently unplaced.
4. **#554, #557, #561** — the three things that make combat look broken in its first minute. All small.
5. **#553** — validate the action table and stop leaking `str(e)`; add the map-placement contract test.
6. **#558, #559** — friend/foe legibility and the stat sign; both are correctness-of-display bugs.
7. **#563**, then **#538** with T5's collapse-the-affordances recommendation, then **#556**, **#560**,
   **#564**, **#565**.

Then re-run T1's leg — Scenes 0–3 unaided, and the King Slime at level 1 — before signing the route
off. That fight has still never been played.

## Re-running this

`/orchestrate-qa-testers`, plus the project memory note "Live browser QA toolkit", updated from this
run with: the `--no-llm` flag and why a scripted-only run needs it; the Grondia (14,5) start-tile rule
for `GorranGestureEvent`; never seeding `starting_exp`; that `SendMessage` to a running subagent is
still unavailable, so a parked tester cannot be nudged and its outcome must be recovered by reading its
live session; and the three verification traps that manufacture false findings (accessible name vs
CSS-uppercased text, staged dialogs advancing in place, and `text()` putting dialog body after the
room description).
