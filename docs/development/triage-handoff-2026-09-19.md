# Triage pass handoff — 2026-09-19

**Status:** in progress, paused near the weekly usage limit.
**Branch:** `claude/issue-triage-a7acc5` (worktree `.claude/worktrees/issue-triage-a7acc5`)
**Merge base:** `c8f5f17b` (== `origin/master` at pass start)
**Nothing has been pushed. No PR exists yet.**

This file is the resume point. Update it at milestones.

---

## 1. Read this first — how to resume in three commands

```bash
cd .claude/worktrees/issue-triage-a7acc5
git log --oneline c8f5f17b..HEAD      # 9 workstreams merged, 0 wip commits
git status --short                     # must be clean
```

The working tree is clean and every piece of work is committed. Agent worktrees under
`.claude/worktrees/agent-*` have already been merged in and are no longer needed.

---

## 2. What is merged and verified

Nine workstreams, **61 files, +4526 / −609**.

| Workstream | What it does |
|---|---|
| `run_api` flake fix (`639df017`) | Probe stubs `src.api.app`/`src.api.config` before exec'ing `run_api.py`; 59.8s → 3.2s |
| #625 | `join_party` helper (5 duplicate sites); shared `CollapsibleSectionHeader` |
| #618 | NPC chat client deadline; closing line readable before auto-close |
| #611 shop | Floor-litter leak; `Special`-family exclusion; map path separators; `isinstance` fidelity |
| #611 feedback | Names the goods a passageway takes back, in its confirmation |
| #614 | Range shortfall on locked move cards |
| #620 | Handler provenance; passageway step-through verb gate (**security**) |
| #612 | Pan affordance gated on clamp slack |
| #624 | `stack_grammar` stops mutating `item.name` |
| #621 | Loot drops collected by handle, not name (**security**) |

### Verified on the merged state — measured, not claimed

```
python -m pytest -q
  4 failed, 14599 passed, 1 skipped, 1 xfailed   (95.05s)

cd frontend && npx vitest run
  164 files, 3784 tests, all passing             (exit 0)

python -m flake8 --extend-ignore=E501 src/
  clean, exit 0
```

**The 4 failures are the pre-existing `ModuleNotFoundError: openai` set** — environmental, CI
installs the dependency:
`test_llm_client_coverage.py::TestGetSdkClient::{test_construction_error_returns_none,
test_real_openai_returns_instance}`, `test_llm_openrouter.py::{test_openrouter_plain_generation,
test_openrouter_structured_generation}`.

Baseline at `c8f5f17b` was `4 failed, 14356 passed` and `163 files / 3741 tests`, so this branch
adds **+243 backend and +43 frontend tests with no regressions**.

`flake8` findings in `tests/` and `tools/songs/` are **pre-existing** — verified two ways: neither
file is in this branch's diff, and they reproduce on the base commit. `src/` is the CLAUDE.md gate
and it is clean.

---

## 3. WHERE IT STOPPED — the review gate, mid-wave-1

**This is the resume point.** `/code-scrubber` Steps 0–2 are done; Step 3 wave 1 was dispatched and
interrupted before any subagent returned. **No findings exist yet. No fixes have been applied.**

Routing is correct and already checked against the rules file:
`git diff c8f5f17b..HEAD | wc -l` = **4778**, `DIFF_REDIRECT_THRESHOLD` = 1000,
`review_depth_for_diff_size(4778)` = `redirect-to-scrubber`.

### The chunk plan (already extracted to disk, already audited)

Chunk diffs live in the session scratchpad. **Regenerate them if that scratchpad is gone** — the
`git diff` path lists below are the authority:

| Chunk | Lines | Paths |
|---|---|---|
| `c1-620-security` | 1419 | `src/objects.py src/api/services/game_service.py tests/test_passageway_step_through_gate.py tests/test_interaction_handler_provenance.py tests/test_object_action_dispatch_contract.py tests/test_interaction_level_up_deferral.py tests/test_game_service_tier5_coverage.py` |
| `c2-621-loot` | 1155 | `src/npc/_loot.py src/tiles.py tests/test_victory_loot_resolution.py tools/harness/scenarios/victory_loot.py tests/_loot_fixtures.py tests/test_npc_loot_coverage.py tests/test_tiles.py tests/test_npc_eastern_descent_and_loot.py tests/acceptance/` |
| `c3-shop-items` | 1264 | `src/npc/_shop.py src/items.py frontend/src/utils/stackName.js src/resources/maps/ tests/test_shop_room_objects_regression.py tools/harness/scenarios/shop.py tests/test_map_authored_file_paths.py tests/test_items_coverage.py tests/test_game_service_shop_merchant_lookup.py tests/test_container_loot_event.py tests/test_npc_advanced_tier3.py` |
| `c4-frontend-combat-chat` | 1333 | `frontend/src/components/BattlefieldGrid.jsx(+test) CombatMovePanel.jsx CombatMovePanel.targetGating.test.jsx frontend/src/utils/combatMoveStatus.js(+test) NpcChatPanel.jsx(+test) frontend/src/hooks/useNpcChat.js(+test) frontend/src/api/npcChat.js(+test) frontend/src/test/ tests/test_wire_field_contract.py` |
| `c5-dry-feedback` | 1630 | `src/npc/_progression.py src/story/ src/events.py src/api/services/session_manager.py src/player/_inventory.py CollapsibleSectionHeader.jsx(+test) CollapsibleRoomDescription.jsx(+test) HeatMeter.jsx(+test) InteractPanel.jsx(+test) GamePage.jsx(+test) frontend/src/styles/theme.js tests/test_join_party_helper.py tests/test_issue_611_merchandise_return_feedback.py tests/test_run_api_log_dir.py` |

**Coverage audit passed:** all 61 changed files appear in exactly one chunk; the set difference
between the branch diff and the chunked files is empty. Re-run that audit if you re-chunk — a file
nobody chunked is never reviewed and nothing reports it.

`chunk_requires_confirmation()` returns `False` for every chunk and for the total. `c5` is 163% of
the 1000-line target, over `SOFT_CAP_PCT` (1.1) but well under `HARD_CAP_PCT` (2.0).

### Two hard constraints on resuming the scrub

1. **Orchestrate from the main session.** A dispatched agent cannot spawn subagents here, so
   backgrounding the scrubber silently degrades it into one generalist wearing five hats. CLAUDE.md
   records two real defect escapes from exactly this.
2. **The scrubber does NOT review Architecture.** `GRADING_DIMENSIONS` is the six core keys plus
   `Alignment`. After the scrub, run `/code-review` over the architecture-touching subset
   (`src/api/`, `GameService`, serializers) or that dimension never gets a pass.

### Pacing warning — this is what cost the pass

**Ten concurrent Opus implementation agents exhausted the session limit twice.** Diagnosis agents
are cheap (read-only); implementation and dimension agents are not, because each runs full test
suites. Resume at **2–3 chunks at a time**, i.e. 10–15 dimension agents, not 25.

---

## 4. Maintainer decisions already made — binding, do not re-litigate

| Issue | Decision |
|---|---|
| #621 | **Don't merge drops into pre-existing piles** in `before_death`. Not split-at-collect. |
| #617 | **Implement, with REDUCED exp** for reinforcements (not the full 45 each). |
| #612 | **Hide the hint when panning can't move** (clamp-derived), not "let Fit pan off the arena". |
| #600 | **Leave open awaiting reporter.** Do not close. |
| #615 | Collapse synonyms **in the serializer**, not by trimming map JSON. |
| #617 | Retune the boss via Elder Slime waves, not by moving the boss's own numbers. |

---

## 5. OPEN — needs the maintainer, do not close on model judgement

**#621 behaviour movement (security-labelled).** CLAUDE.md: a Critical/Major security finding never
closes on model judgement alone.

If a **visible** pre-existing pile of the drop's kind sits on the fight tile and the player picks
anything up before collecting, `MapTile.stack_duplicate_items` merges them, keeps the older object,
and collect-loot answers `not_found`. The units remain on the floor, visible and takeable by hand.
Pre-fix the player got the whole merged pile (too much); now they get none from the dialog (too
little). Closing it properly means **handle succession on merge**, which is an identity-design
change. The client pins the combat screen while a victory is unresolved, so reaching it needs a
second tab or a crafted request.

---

## 6. Not started

- **#617** Elder Slime reinforcement waves (decided: implement, reduced exp). Largest and riskiest
  remaining item — see §8 for why the maintainer's own scoping note understates it.
- **#616** 19 polish items triaged into 6 batches (A–F). See §9.
- **#623** `useBattlefieldPan` hook extraction. Correctly sequenced **after** #612, which has landed.

---

## 7. Issues where the FILED FRAMING WAS WRONG

These must be said in the closing comments, or the wrong diagnosis stays the record.

- **#612** — the drag *is* bound in Fit mode. It is inert because the fit frame covers the arena so
  the pan clamp collapses to `[0,0]`. Slack-specific, not mode-specific: the same dead hint appears
  in Follow when Jean stands centre-arena.
- **#618 defect 2** — the closing line *does* reach the wire and *does* render. The bug is a 2s
  auto-close armed against `npc_text` while the line lives in `npc_flavor` (#531's fix made inert by
  #532). **4 of the issue's 6 citations pointed at blank lines or unrelated comments.**
- **#624** — the stated bug does not reproduce; both name-baking classes carry a `stack_key`, so the
  merge key never reaches the name+description fallback. The root cause instead breaks **shop
  buyback**. The issue said "~14 writers"; there are 12 `stack_grammar` definitions and only 2 touch
  `name`.
- **#614 gaps 1–2** — the reason line already renders and cooldown beats already appear in prose.
  The real gap was the *number*. Underneath sat a genuine engine bug: `combat_proximity` holds both
  sides, so `viable()` counted an adjacent **ally** as an enemy in range.
- **#615** — symptom overstated: `InteractPanel.jsx:108` already drops `action_aliases`, so the row
  was 3 buttons, not 6. The collapse also does not generalise (see #626).
- **#620** — **both** fix shapes proposed in the issue break shipped content.
- **#611** — two independent failures, either alone sufficient; plus a larger separate bug
  (`_shop.py` abandoning ~23 merchandise items per restock on the merchant's floor) that is a
  competing explanation for the tester's report.

---

## 8. #617 scoping correction — the maintainer's note is wrong in one place

The comment on #617 says "there is no interval or wave spawning anywhere in the combat engine" and
lists battlefield placement as work item 2. **Placement is already built:**
`functions.add_enemies_to_combat` (`src/functions.py:152`) spawns mid-combat, places, and reinits
the adapter via `initialize_combat(reinit=True)`.

But the trigger is **harder** than the note implies:

- Every existing wave fires at **roster-empty** — `RumblerChainEvent.check_combat_conditions`
  (`src/story/ch01.py:600-604`) gates on `if not self.player.combat_list`. There is no per-beat or
  HP-threshold hook anywhere.
- `combat_adapter.py:1735-1747` documents that a mid-**execute** reinforcement spawn **spun the
  engine forever**; the stage-reset exemption is the fix. Existing waves dodge this by firing
  between fights. An HP-threshold trigger walks straight into that path.
- `functions.py:130-148` documents `combat_wave_pending` as armed by exactly two sites and says
  **"Do not add a third flag."**

### Maintainer's edge cases, checked against the code

1. *"No victory until all enemies cleared"* — **already holds, free.** Victory fires on
   `len(player.combat_list) == 0` (`combat_adapter.py:2733`).
2. *"New spawns can't happen with King Slime dead"* — **not free**, needs an explicit guard; the
   simultaneous-death beat is the slip case.
3. *"Spawns during boss death must not race the Victory dialog"* — a mechanism exists:
   `combat_wave_pending` + `victory_deferred` (`combat_adapter.py:2704-2726`, issues #514/#519) holds
   an emptied roster open across a wave transition. Consumption requires
   `len(combat_list)==0 AND in_combat AND event_just_triggered AND combat_wave_pending`.
4. *Future extensibility* — "captain" enemies forcing victory/defeat on death. **The seam is the
   hardcoded `len(combat_list) == 0` predicate at `combat_adapter.py:2716-2736`.** Leave it.

---

## 9. #616 batches (19 items triaged, none implemented)

- **A — items 17+19, one root cause.** `src/player/_movement.py:39` narrates `tile.intro_text()`
  inside the event's `capture_narration()`; `game_service.py:906-912` promotes >400-char narration
  (`_NARRATION_CHUNK_MAX_CHARS = 400`) into paced segments, so a room description renders as a story
  scene and blocks movement. eastern-descent (0,2) = 545 chars; grondia (7,9) = 462. **Medium.**
- **B — items 4+4b.** `RoomContents.jsx:51,:67` push idle lines from **unfiltered** arrays while
  `:31` filters `!e.hidden`. 21 hidden placements publish an `idle_message`. **Small.**
- **C — items 1+2.** RiversEdge Water Barrel description duplicated from Supply Tents
  (`eastern-descent-nomad-camp.json:1393` == `:2966`). "A iron lockbox" is systemic:
  `src/objects.py:517,:528,:532`; 6 of 47 nicknamed placements start with a vowel. Needs
  `indefinite_article()` in `src/functions.py` (existing logic is private to `src/api/`, and the
  engine cannot import from there).
- **D — items 12+14+7+10.** `LootDialog.jsx:222` passes neither `onClose` nor
  `showCloseButton={false}`, so the ✕ is inert (one-word fix). `EventDialog.jsx:301`
  `if (!showInput) return` blocks Enter/Space on a terminal CLOSE frame.
  `useWorldInteract.js:154-168` `takeOne` never clears `error`. `objects.py:852-860` Sacred Spring
  has no HP check (precedent at `:1695-1706`).
- **E — item 8.** `combat_adapter.py:3727-3738` and `:4533-4544` enumerate 6 attributes, omitting
  `faith_base`; the authority (`src/player/_leveling.py:20-28`) has 7. **The guard misses it by node
  type** — `tests/test_level_up_attribute_authority.py:88` walks `ast.Set/List/Tuple`, not
  `ast.Dict`. `VictoryDialog.test.jsx:23-30` encodes the identical omission. **Fix the guard; that
  is the point.**
- **F — item 16.** `src/story/ch03.py:151-155` teleports without `recall_friends()`.

**Defer:** 3 (duplicate of #624), 5 (stale — #591 landed after the QA build), 6/11/15 (maintainer
calls), 9 (needs art), 13 (re-file against `ItemDetailDialog`), 18 (needs live repro).

### Correction — do not act on this claim
The #616 triage agent asserted "#600 can be closed — commit `8f8f2f30` (#609) is in HEAD". **That is
wrong.** #609 only affects placements that *author* a `keywords` list; Jambo's crate authors none and
inherits `["loot","take_all"]` from `Container.__init__`, so it is one of the 7 of 47 placements #609
does **not** affect. The maintainer has decided #600 stays open.

---

## 10. Tests found asserting broken behaviour

Long shelf life — worth keeping visible.

| Test | Why it was wrong |
|---|---|
| `frontend/src/pages/GamePage.test.jsx:709-725` | Stubbed `refetch` to a no-op, so the mocked inventory kept its merchandise flag forever. **Could not fail while the feature was broken.** Fixed by #611. |
| `frontend/src/components/NpcChatPanel.test.jsx:316-337` | Asserted End Conversation is disabled during loading — the defect itself. Fixed by #618. |
| `tests/test_npc_chat_llm_tier4.py:2033-2049` | Pins "mid-conversation fallback prefers starters", which is the defect. Its innocuous fixture (`"Hello, friend!"`) hid it — a real starter is a direct question. **Still open, see #628.** |
| `tests/test_object_action_dispatch_contract.py:183-185` | `_is_dispatchable` waved through every non-demo-end Passageway — **failed open on the exact type #620 hardens.** Fixed by #620. |
| `tests/test_level_up_attribute_authority.py:88` | Walks `ast.Set/List/Tuple` but not `ast.Dict`, missing the two dicts that omit `faith_base`. **Still open, #616 batch E.** |
| `tests/test_wire_field_contract.py` `_assert_contract` | Presence-only, no exhaustiveness check — which is why 3 wire fields shipped with zero consumers. |
| `frontend/src/components/BattlefieldGrid.test.jsx:2223` | Codifies #612's inert pan as correct. Arguably right, but it is why nobody noticed Fit's pan is roster-size dependent. |

---

## 11. Follow-up issues filed this pass

#626 synonym button rows survive #615 · #627 `CANNOT_USE_REASON` is the only sentence ~22 untargeted
moves produce · #628 degraded NPC replies answer with a chapter opener · #629
`Container.open/take_all` destroy map-authored descriptions · #630 make passageway crossing verbs
authorable · #631 Dark Grotto's Tattered Journal points at a missing file · #632 `JeanWeddingBand`
can be rolled into random merchant stock.

---

## 12. PR and closing — the trap that cost the last pass

A Conventional-Commit subject like `fix(items): … (#624)` **closes nothing**. GitHub requires a
closing keyword followed by nothing but whitespace or a colon before `#NNN`. PR #549 merged fixes for
19 issues and closed exactly **one**.

Put closing keywords in the **PR body**, one per line, in their own section:

```
## Closes

Closes #611
Closes #612
...
```

Verify **before** merging, and again after:

```bash
gh pr view <N> --json closingIssuesReferences -q '.closingIssuesReferences[].number'
for n in 611 612 614 615 618 620 621 624 625; do
  gh issue view $n --json number,state,stateReason -q '"#\(.number)\t\(.state)\t\(.stateReason // "-")"'
done
```

`closingIssuesReferences` is **not** a safety net in either direction — a commit-message close never
populates it. Re-read the PR body immediately before merging; a body written mid-pass goes stale.

**Do not claim #613 or #615 are closed by this branch.** Verified 2026-09-19: `object_serializer.py`
is **not** in the merged diff, so **#615 did not land**. Its work survives, uncommitted-then-preserved,
on branch `triage/615-keyword-collapse` at `4f9e37ee` in worktree
`.claude/worktrees/agent-a89cf38950a883a04` — 4 files, +457/−1, touching
`src/api/serializers/object_serializer.py`, `tests/test_log_cleanup_and_object_serializer.py`,
`tests/test_serializers_coverage.py` and a new `tests/test_object_keyword_collapse.py`.
**It is unverified — no suite has been run against it.** Finish and verify it before merging, or
leave #615 open.

---

## 13. Other sessions

A background task chip for the `run_api` flaky test (`task_347e8d6a`) was **already started by the
user** in another session. That work is now redundant — the flake is fixed here in `639df017`. Check
before letting that session duplicate it.

`git stash` is shared across all worktrees and there is at least one other session's entry on the
stack (`"On master: wip: backend-owned combat streaming capability before master sync"`).
**Never run bare `git stash` / `git stash pop`.**
