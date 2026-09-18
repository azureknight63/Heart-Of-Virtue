# Live browser beta QA — Grondia through the Nomad Camp ferry (2026-09-17)

**Build:** master @ `6c916ad0` (Alpha worktree)
**Scope:** the shipped beta arc — Grondia (1,2), where the beta briefing fires, through the Nomad
Camp Ferry Landing and the end-of-beta dialog.
**Method:** nine tester agents playing the real React + Flask build — eight in headless Chromium
behind per-tester driver ports, one (Opus) playing the whole route in the in-app browser pane —
against two backend/Vite pairs with different start states. Every Critical/High was then either
reproduced by the orchestrator on a separate clean client or confirmed in source with file:line
before it reached the tracker.
**Outcome:** 10 issues, **#609–#618**. No Criticals survived verification.
Raw tester reports are in `beta-live-test-2026-09-17/tester-reports/`, cited screenshots in
`beta-live-test-2026-09-17/shots/`.
**Relationship to the last run:** everything from the 2026-09-09 pass (#570–#587) plus the
2026-09-12/14 batch (#592–#603) was closed before this run started, so roughly half of this pass is
fix-verification.

## Headline

1. **The beta route is finishable and the story chain is intact.** Three testers (O1, T1, and T5 from
   the camp start) reached the end-of-beta dialog with every scripted scene firing in order and
   quoting correctly, and all journal objectives closing. Scene 4 — Gorran's farewell at the gate,
   the beat that did not exist on the real route in the last two runs — fired for four independent
   testers with the right prose (**#582 confirmed fixed**).
2. **#581 worked, and now the route is flat.** Nobody died. At the shipped level-3 start the King
   Slime dealt **zero** damage to O1 (both telegraphed surges missed) and none to T1 once dodged;
   the only encounters with any texture are the multi-enemy Mineral Pools packs, which also grant
   enough XP to gain two levels inside the dungeon they are meant to pace. Filed as **#617** with the
   five-playthrough data table — a maintainer tuning call, not a defect.
3. **The TAKE ALL button is dead on 40 of the 47 container placements in the game (#609).** Three
   testers hit it in three different maps; the orchestrator reproduced it against the API and traced
   it to `take_all` being absent from the API verb allow-list while the frontend renders the button
   unconditionally. The 7 survivors are placements that author no `keywords` list and so keep the
   verb `Container.__init__` gives them. **This does not explain #600** — that crate is one of the
   seven (corrected after filing; the first count only looked at keyword-authoring placements).
4. **Reloading after a fight re-opens a stale VICTORY dialog, and uncollected loot is lost (#610).**
   Reproduced twice by the orchestrator on a clean client with the engine reporting
   `combat_active: false`. #570's fix handles the "stranded forever" case; this is the residue.
5. **The NPC-chat half of this run nearly died of a configuration fault, and the fault was mine.**
   The box's `.env` pins `stepfun/step-3.5-flash:free`, which the vendor has withdrawn — every call
   404s, which is exactly the failure #533 documented. Restarting the camp stack with model
   auto-discovery recovered it and the voice pass ran. Preflight checks the LLM *gates* and the
   *quota*; it does not check that the pinned model still exists. See "Setup faults".

## Setup

| stack | frontend | API | config | start state | LLM |
|---|---|---|---|---|---|
| `full0917` | :3001 | :5001 | `config_grondia_beta.ini` — **the shipped beta config, unmodified** | Grondia (1,2), level 3, Gorran, mace drawn + full leather, 3 Restoratives + Antidote, 315 gold, `lurker_defeated` | all three gates **off** |
| `camp0917` → `camp0917b` | :3000 | :5002 | `config_qa_camp.ini` (untracked) | Grondia (14,5), level 3, Gorran, same loadout, `king_slime_defeated, votha_krr_response_given, lurker_defeated` | NPC chat **on**, Mynx + tactical advisor **off** |

Both backends ran `create_app` + `socketio.run(use_reloader=False)` with `FLASK_ENV=testing` and a
blank `GITHUB_TOKEN`. Testers logged in through `POST /api/test/session` (cookie + localStorage
marker); nobody used the login/register form. **No tester was debug-boosted** — `config_qa_camp.ini`
was rebased onto #581's `starting_level = 3` instead of the old `/api/debug/player/level` recipe, so
every difficulty judgement in this report is a shipped-config judgement.

### Testers

| tester | model | surface | stack | assignment | calls |
|---|---|---|---|---|---|
| O1 | Opus | in-app browser pane | full | the whole route, unaided, with a designer's eye | ~264 |
| T1 | Sonnet | Playwright desktop | full | the whole route, unaided, engine cross-checks on every scene | 377 |
| T2 | Sonnet | Playwright desktop | full | Grondia breadth: 38 tiles, 5 side maps, every panel | 302 |
| T3 | Sonnet | Playwright desktop | full | Mineral Pools breadth + King Slime + reload robustness | 288 |
| T4 | Sonnet | Playwright desktop | camp | Eastern Descent breadth, Scene 4, Gorran as ally | 248 |
| T5 | Sonnet | Playwright desktop | camp | camp story leg + the capped LLM conversations | 230 |
| T6 | Sonnet | Playwright **mobile** (375×812) | camp | camp leg on a phone, Mara-first ordering, 44px audit | 142 |
| T7 | Sonnet | Playwright desktop | camp | camp systems: shops, objects, reloads, #600 | 258 |
| T8 | Sonnet | Playwright desktop | camp (restarted) | the voice pass, after the model pin was fixed | 190 |

### Setup faults, and what they contaminated

1. **The pinned OpenRouter model is dead.** `.env` sets `MYNX_LLM_MODEL=stepfun/step-3.5-flash:free`;
   OpenRouter now 404s it, the client falls through its candidate list into a 429 storm, and NPC
   chat degrades to canned dialogue. The tell is in the API log:
   `SDK request for stepfun/step-3.5-flash:free failed with status 404 (deterministic)` followed by
   `[LLM SATURATION] openrouter 100%` **while the account still had 44 of 50 free requests left**.
   T5's LLM exchanges ran against that fault; its voice grades for Jambo and half of Mara are
   therefore about the fallback text, not the model. The camp stack was restarted as `camp0917b`
   with `MYNX_LLM_MODEL=auto`/`NPC_CHAT_LLM_MODEL=auto` and T8 re-ran the voice pass cleanly.
   Preflight checked the gates and the quota and passed both; **it does not check that the pinned
   model still resolves.**
2. **The orchestrator's own automation swallowed a scene.** In the verification session a
   click-through loop dismissed the arrival dialog at eastern-descent (0,2) before reading it, which
   briefly looked like Scene 4 failing to fire. Four testers had already quoted it correctly. Method
   note, not a finding — and the same shape of error as the 2026-09-09 run's misidentification, in
   the other direction.

Nothing else was contaminated: no Socket.IO origin faults (both Vite ports were accepted origins),
no API tracebacks on the `full` stack, and every non-noise browser event in the first five minutes
of every tester log was the expected autosave 403.

## Coverage

| scene / area | O1 | T1 | T2 | T3 | T4 | T5 | T6 | T7 |
|---|---|---|---|---|---|---|---|---|
| 0 Beta briefing (grondia 1,2) | PASS | PASS | PASS | PASS | — | — | — | — |
| 1 Ch02GuideToCitadel (7,5) | PASS | PASS | PASS | PASS | — | — | — | — |
| Grondia breadth (38 tiles, 5 side maps) | part | part | PASS | part | — | part | — | — |
| 2a Gorran at the pools | PASS | PASS | — | PASS | — | — | — | — |
| Pools breadth (18 tiles, glands, puzzle) | part | part | — | PASS | — | — | — | — |
| 2b/2c King Slime + aftermath | PASS | PASS | — | PASS | — | — | — | — |
| 3 Votha Krr (Citadel 10,5) | PASS | PASS | — | PASS | — | — | — | — |
| 4 Gorran's gate farewell (descent 0,2) | PASS | PASS | — | — | PASS | PASS | PASS | PASS |
| Eastern Descent breadth (30 tiles) | part | part | — | — | PASS (22/24) | part | part | part |
| 4b RoadEast turnback | NOT REACHED | — | — | — | PASS | — | — | — |
| 5a Camp entry (smell + greeting) | PASS | PASS | — | — | PASS | PASS | PASS | PASS |
| 5b Devet / 5c Liss | PASS | PASS | — | — | — | PASS | PASS | PASS |
| 5d Mara first contact | PASS | PASS | — | — | — | PASS | PASS | PASS |
| 5e Iron & Oath + Anvil | NOT REACHED | — | — | — | — | PASS | — | PASS |
| 6 Mara observation (ferry gate) | PASS | PASS | — | — | — | PASS | PASS | PASS |
| 7 Ferry Landing + beta-end dialog | PASS | PASS | — | — | — | PASS | PASS | PASS |
| Ferry declines before Mara's scene (#579) | — | n/a | — | — | — | — | PASS | PASS |
| Mobile 44px / layout audit | — | — | — | — | — | — | PASS | — |
| Shops, containers, objects | part | part | PASS | part | PASS | — | — | PASS |

### Fix verification

**Confirmed fixed:** #570 (the immediate-reload case), #571, #572, #573, #574, #577, #579, #580,
#582, #583, #584 (the advance case), #585, #586, #594, #596, #598, #599, #602, #603.
**Partially landed:** #592 — drag-to-pan works in `Follow` but not in the default `Fit Fight`
(#612). #584 — Enter/Space advances stages but does not dismiss a CLOSE-labelled terminal stage
(in #616). #597 — the toast exists but two testers still lost merchandise with no visible feedback
(#611).
**Not superseded after all:** #600's crate inherits `take_all` and works; the silent failure a
tester saw there is #611's merchandise drop. Corrected on both issues after filing.

## Findings, ranked

| sev | finding | how it was verified | issue |
|---|---|---|---|
| High | TAKE ALL refused on 40 of 47 container placements; `take_all` missing from the API verb allow-list | orchestrator reproduced over REST on a clean session + source trace + a full placement sweep; seen by T2 and O1 (T7's crate is one of the 7 unaffected) | [#609](https://github.com/azureknight63/Heart-Of-Virtue/issues/609) |
| High | Reload after a finished fight re-opens a stale VICTORY dialog; uncollected loot is lost | orchestrator reproduced twice on a clean client with `combat_active: false` and an inventory diff; seen by T1, T3, T7 | [#610](https://github.com/azureknight63/Heart-Of-Virtue/issues/610) |
| High | Shop merchandise confiscated on exit with no visible feedback | two independent testers (T2, T7); engine mechanism confirmed in source; **not** orchestrator-reproduced (needs the shop dialog) | [#611](https://github.com/azureknight63/Heart-Of-Virtue/issues/611) |
| Medium | Battlefield drag-to-pan inert in the default Fit Fight view | three tester observations reconciled by T4's view-mode isolation | [#612](https://github.com/azureknight63/Heart-Of-Virtue/issues/612) |
| Medium | Gorran follows Jean into the pools after the scene says he stays | O1, corroborated by T1 and T3; scene text read from `ch02.py:971` | [#613](https://github.com/azureknight63/Heart-Of-Virtue/issues/613) |
| Medium | Combat does not explain its locks; `shortfall_ft` on the wire is never rendered | O1 + orchestrator confirmed `Attack` LOCKED at 7 ft while the wire carries the distance | [#614](https://github.com/azureknight63/Heart-Of-Virtue/issues/614) |
| Medium | NPC chat degrades to canned lines and the conversation self-closes with no honest banner | T5, T8 | [#618](https://github.com/azureknight63/Heart-Of-Virtue/issues/618) |
| Low | Ferry Landing renders its own name words as keyword buttons | O1; keyword list verified in the map JSON | [#615](https://github.com/azureknight63/Heart-Of-Virtue/issues/615) |
| Low | Polish batch: 17 items (stale banners, reused barrel description, placeholder portrait, grammar, mobile d-pad discoverability, stray narration) | each attributed to its tester; the barrel text and portrait fallback verified in source | [#616](https://github.com/azureknight63/Heart-Of-Virtue/issues/616) |
| — | Balance data after #581: the cliff is gone, the route is flat | five unaided playthroughs, tabulated | [#617](https://github.com/azureknight63/Heart-Of-Virtue/issues/617) |

## Reported and not filed

Kept here so the next run does not re-investigate them.

- **"Crate items vanish into an unrelated tile" (T7, filed by T7 as Critical).** Reframed, not
  dropped: `Container.take_all`/`take` do put the items in the inventory, and
  `Player.drop_merchandise_items` (`src/player/_inventory.py:40`) then moves every unpaid item onto
  the current tile when the Tent Flap is crossed — which is the tile where T7 found them. The real
  defect is that the player is never told, which is #611. The 20 other `merchandise: true` items
  T7 found on that tile are Jambo's own stock, not QA-config seed data.
- **"Combat category buttons render at 42×23 px" (O1).** Not reproduced: the orchestrator measured
  69×38 on desktop and T6's real mobile driver measured every combat control at ≥44px. Pane-sourced
  viewport measurements have now been wrong in two consecutive runs; treat them as unconfirmed.
- **"The open move panel covers the category tabs" (O1).** `hit_test` on OFFENSIVE with the panel
  open returns `top_is_element: True` (z=5) and `raw_click` opens the panel, so #575 is not
  regressed. The visual bleed is real and is in the polish batch.
- **"Nomad Trader has no shop" (T7).** Intentional: `NomadTrader`'s docstring
  (`src/npc/_eastern_descent.py:303`) says "Not a full merchant — no shop, no stock list."
- **"Scene 6 fires immediately after Scene 5d rather than on re-entry" (T5).** Correct per
  `MaraObservationEvent.check_conditions` — it fires as soon as all three prerequisite beats are
  done. The beta scope doc's route order is what makes the #579 decline path untestable; T6 and T7
  reached it by visiting Mara first.
- **"The Wait move freezes combat" (T4's own caveat).** The move opens an "enter beats" dialog that
  is invisible to anyone polling `/api/combat/status`; the orchestrator hit the same thing. Testing
  methodology, not a defect.
- **Playwright actionability timeouts (T6, and the orchestrator's own).** Every one that mattered
  resolved to a moving/re-rendering element, not a covered control.

## Dialogue voice

The scripted prose held up: no tester found a typo, POV slip or tonal break in any of the fifteen
scripted scenes, and several called the camp scenes the strongest writing on the route. The one
content defect is the reused Water Barrel description (#616).

**Live LLM (T8, on the repaired stack; T5's earlier grades for Jambo and half of Mara ran against the
dead-model fallback and are evidence about the degraded path, not about the personas):**

- **Mara — the one clean result, and it is good.** 3 of 4 exchanges produced real generated output at
  12–15 s, dry and in register, no prohibited-phrase hits, no invented lore:
  *"She taps the rim of her cup and watches the current turn. Good. Knowledge keeps fools alive a
  little longer."* T5's earlier real exchanges agreed before the provider fell over.
- **Devet — 0 of 3 exchanges reached the model.** Two hung indefinitely, one resolved to the honest
  fallback banner. The fallback line it did produce is his own scripted copy, so his voice is
  unverified live.
- **Liss — 0 of 2 reached the model**; both fell back in 8–10 s, and the second ignored the option
  the player picked ("Tell me more" answered with an unrelated question about Gorran's armour). T5's
  earlier pass, which did reach the model, graded her a strong match to her persona.
- **No prohibited-phrase or lore violations in any generated text.** One wrinkle worth a decision:
  the *player's* option buttons in Liss's conversation used "Fair enough." and "I see.", both of
  which are on *her* prohibited list — Jean's lines are generated against her constraints.
- The failures above are the substance of **#618**; the provider itself answered normally for other
  turns in the same sessions.

## What works

- The whole scripted chain, in order, including the two beats that were unreachable in previous runs
  (Scene 4 at the gate, and the ferry gate refusing to end the demo early).
- The journal. Three testers independently called it the clearest part of the UI; the next objective
  was never ambiguous, and objectives closed when they should.
- Combat telegraphs after #586: the log line, the turn-order chip (`⚠ DEADLY ⚔ King Slime +13`) and
  the spiked aura with a countdown on the token all fire together, and dodging the surge works.
- Gorran as an ally on the descent (#577): present in `battle_state.allies`, acting, landing 24–33
  damage, sometimes finishing enemies alone.
- Mobile: zero touch-target offenders, zero horizontal scroll, every dialog fitting 375px.
- The shop arithmetic at the Tradepost (buy and sell, both merchants, verified against displayed
  prices).

## Recommended order of work

1. **#609** (TAKE ALL) — one-line allow-list fix plus a contract test using a map-loaded container;
   it is a dead button on nearly every container in the game.
2. **#610** (stale victory on reload) — the loss of uncollected loot is the part with teeth; check
   the `CombatLog.jsx` update loop two testers saw while in there.
3. **#611** (silent merchandise confiscation) — needs a browser repro first; the engine behaviour is
   correct, so this is a feedback bug.
4. **#617** (balance) — a maintainer decision that should land before the next QA run, since it
   changes what "the route plays well" means.
5. **#614**, **#612**, **#613** — legibility and consistency.
6. **#616**, **#615** — polish, batchable.
7. Environment, not code: repoint `MYNX_LLM_MODEL` to `auto` in `.env`, and add a model-resolution
   probe to `preflight.py` so a withdrawn pin cannot eat another LLM-scoped run.

## Re-running this

`/orchestrate-qa-testers` (`.claude/skills/orchestrate-qa-testers/`) plus the project memory note
"Live browser QA toolkit", which now carries this run's per-gate LLM control, the OpenRouter
headroom probe, the dated-tag/`--outdir` convention and the `starting_level` recipe that replaced
debug boosting.
