# Triage pass handoff — 2026-09-19

**Status:** in progress (session 2). **Read §0 first** — it supersedes §3's "where it stopped".
**Branch:** `claude/issue-triage-a7acc5` (worktree `.claude/worktrees/issue-triage-a7acc5`)
**Merge base:** `c8f5f17b` (== `origin/master` at pass start)
**Nothing has been pushed. No PR exists yet.**

This file is the resume point. Update it at milestones.

---

## 0. Session 2 — resume point (supersedes §3's status lines)

A session whose launch worktree is a *different* one is blocked from editing this worktree's
files. Enter it first: `EnterWorktree` with `path` = this worktree.

### Scrub state
| Chunk | Dimension agents | Adversaries | Fixes |
|---|---|---|---|
| c1-620-security | 5/5 (Security re-dispatched, returned **C**) | style + security done | C1 applied (`78577df1`); rest pending |
| c2-621-loot | 5/5 | style + security done | test-side fixes applied (`65e87b7e`); src-side pending |
| c3-shop-items | 5/5 | style + security done | test-side fixes applied (`5c4b608b`, `d030abe8`); src-side pending |
| c4-frontend-combat-chat | dispatched 2026-09-19 session 2 | — | — |
| c5-dry-feedback | **not dispatched** — hold until the 5-hour window resets | — | — |

The c1 Security re-dispatch escalated #620: the fix closed only the first hop. Handlers the class
declares still call `self.<method>` (go/leave/exit→`self.enter`, `wash`→`self.clean`,
`take_all`→`self.refresh_description`, `use`/`examine`→`self.drink`/`self.read`, event
`check_conditions`, …), and the map loader `setattr`s every prop, so an instance `__dict__`
entry shadowing any class-declared **non-data descriptor** (function/staticmethod/classmethod) or
UPPER_CASE policy constant reaches #620's primitive one hop later. Plus two pre-existing loader
Majors: `SafeUnpickler` (C `pickle.Unpickler`) cannot hook BUILD, so a save can `setattr` on an
allow-listed CLASS process-wide; and the map class-marker gate (`universe.py:141`, `:186`, `:251`,
`map_placeholders.py:134`) checks only `_is_allowed`, so `story:import_module` resolves to
`importlib.import_module`. **Keep property setters** (`demo_end_ready_flag` is a data descriptor
the loader must still apply).

### Maintainer decisions, session 2 (binding — add to §4)
| Topic | Decision |
|---|---|
| #620 scope | **Full root fix in this branch, and close #620**: map loader refuses props shadowing class non-data descriptors / UPPER_CASE constants; class-marker gate requires a real, trusted class; save side sanitises restored instance dicts and refuses BUILD on classes/functions (pure-Python unpickler); per-site hardening (C2 class-routed `enter`, C4 `type(self).CROSSING_METHOD_NAMES`) as defence in depth. |
| Shop B1/B2 | **Fix both here.** B1: buyback stamps the ledger's value on returned units (sell→buyback→resell profit, widened by #624). B2: `shop_sell` refuses merchandise-flagged items (mirror `equip_item`). Each with a before/after repro. |
| #621 freeze window | **Refuse floor take/drop during combat, then freeze merges at victory as decided in §5.** (Take/drop were ungated in combat — `interact_with_target` refuses only Passageway, `drop_item` has no check — so a merge could destroy a recorded drop before victory, and later arrivals merge INTO a recorded drop.) |
| Commits | **Commit per verified fix group**, local only; no push/PR until §12 is checked. |

### Committed in session 2
`78577df1` C1 alias-word helper read off the class (repro: 21 red → green) · `5c4b608b` derived
shop guards (families incl. Key; every stackable keeps its name) · `d030abe8` shared
`walk_json_strings`, authored-path containment test · `65e87b7e` identity in #621 fixtures,
keywords keyed by placement.

### Pending, in order
1. #620 full root fix (above) + C2/C4/C5/C6(A1 atomic pop)/C7/C8 + D1 (`Passageway.accepts_step_through`).
2. c2/c3 src fixes: A2 (`Item.take` appends before removing), A6 (VICTORY dialog details by handle, not name), A7 (skip `_combat_handle` in `__dict__` copies), A11/A12 (harness silent passes), B1, B2, B4 (`Book.text` cwd-relative; narrates path+errno), B10 (container take narration lost the count), stale comments/docstrings (T2/T3/T6/T12/T15, S10–S15), `_shop.py` extraction (T1/T4) if budget allows.
3. #621: refuse take/drop in combat + freeze at victory (§5, all merge sites).
4. c5 wave, c4 adversaries/fixes, targeted re-dispatch of below-A pairs, `/code-review` over the architecture-touching subset, full suites, `bug_hunt`, PR per §12.

Deferred with reason: B8 (pre-#624 saves keep baked names) — save compat is suspended for beta,
but the docstrings claim old saves are handled; correct the claim or add normalisation. A9/A10
downgraded to Nit (embedded arrows unrecorded; `_forget_drop_handles` has no observable effect —
fix its docstring). B12 moot (pytest-randomly reseeds per test). Per-session mutation lock
(root of A1/A2/A4/A5) → follow-up issue.

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

**This is the resume point.** `/code-scrubber` Steps 0–2 are done. Step 3 wave 1 ran for chunk
**c1 only**, and **4 of its 5 dimension agents returned**. **NO FIXES HAVE BEEN APPLIED** — findings
are recorded below and nothing has been edited.

### c1-620-security — returned grades (4 of 5)

`Alignment=B Correctness=B` · `DRY=C Maintainability=B` · `CleanCode=C AIFriendliness=C` ·
`Optimization=A`. **The Security agent was interrupted and never reported — re-dispatch it first.**

Findings worth carrying (full detail was in the agents' reports; these are the ones with teeth):

- **[Major, SECURITY] — FIXED 2026-09-19 in `900ac5e0`, maintainer-authorised.** Was: `src/objects.py:111` — the new docstring claims
  `__self__ is target` "readmits them and nothing else". It readmits **any bound method of the
  target**. A restored save (untrusted input per `.claude/rules/saves-persistence.md`) could store
  `obj.__dict__["look"] = obj.die`, and the allow-listed verb `look` would dispatch
  `NPC.die(player)` — exactly the surface `_ALLOWED_INTERACTION_VERBS` exists to close (#334). Not
  introduced here (bare `getattr` admitted it too), but the docstring now asserts it is closed.
  Either soften the claim or remove the instance carve-out entirely: replace
  `setattr(self, word, self.enter)` with a data-only `self._name_aliases` list that
  `resolve_interaction` maps to `type(target).enter`.
  **Resolution:** the maintainer authorised the recommended shape, so the instance carve-out is
  gone entirely. `Passageway`'s name words are now DATA, mapped to `enter` by a class-declared
  `instance_keyword_aliases()` derived from `self.name` on demand (so older saves resolve
  identically). `is_crossing_handler` was switched to class-declared comparison in the same commit,
  which also closes the `#552`-shaped asymmetry listed below. Two tests that pinned the removed rule
  were inverted rather than deleted, and the alias population scan was pointed at where the aliases
  now live rather than narrowed — it read `instance.__dict__` for callables and would have matched
  nothing and passed forever. Revert-proved **surgically**: restoring only the vulnerable line fails
  both guards on their own assertions (`assert take_all is None`, `assert drink is None`) instead of
  on a collection error. Verified: backend 4 failed (pre-existing `openai`) / **14602 passed**,
  `flake8 src/` clean, `python tools/bug_hunt.py` finds no bugs.
- **[Minor, Correctness] — FIXED in the same commit (`900ac5e0`).** Was: `is_crossing_handler` resolved its
  comparison targets with `getattr(self, name, None)` (instance `__dict__`) while
  `resolve_interaction` now sources from the class. The halves can disagree: an authored prop named
  `enter`/`go`/`leave`/`exit` poisons the comparison side, `_is_demo_end_crossing` returns False,
  and arm 5 calls the real `enter` → `end_demo()` with `beta_end` still False (the #552 symptom).
- **[Minor, Correctness]** `game_service.py:2695` — `action in getattr(target, "keywords", ())`
  defends only against absence. `keywords` is a map-authored prop, so it can be `None` (TypeError
  swallowed into `_ACTION_FAILED_MESSAGE`) or a string (substring match). The test mirror uses the
  stricter `(getattr(instance, "keywords", None) or [])` — guard and code disagree on degenerate
  input. Fix the production gate to match.
- **[Major, DRY]** The step-through predicate is retyped by hand in
  `tests/test_object_action_dispatch_contract.py:234`. Extract
  `Passageway.accepts_step_through(handler, action)` and have both arm 4 and `_is_dispatchable` call
  it, so the mirror cannot fail open a third time.
- **[Major, DRY]** `combat_drops` is now a 5-key implicit schema (`name`/`quantity`/`source`/`kind`/
  `handles`) read by key in three modules. The VICTORY dialog's count and what collect hands over
  can diverge with nothing to catch it.
- **[Major, CleanCode]** Two stale comments the diff invalidated: `game_service.py:476-478` still
  says hardening the arm "is #620" (it was), and `:2611-2616` still lists `passageway` among the
  arms that do not consult the handler (it now does).
- **[Minor]** `tests/test_passageway_step_through_gate.py:304` regroups keywords by placement
  *name*, so every unnamed placement pools its keywords onto one probe and rows lose identity.

**Chunk scope note (not a defect):** c1 is labelled #620 but roughly half its `game_service.py`
hunks are #621 (`_LOOT_PHASE_LOCK`, handle-based `_take_offered_drops`/`_offered_drops`) and one is
#611. That is a file-level chunking artifact of reviewing an already-merged branch, not scope creep.
Two agents independently checked those hunks and found nothing.

**Constraints verified concretely by the Alignment agent, so they need not be re-derived:**
`HealingSpring.clean` still resolves on all four shipped placements (`staticmethod.__get__` returns
a plain function and `_call_interaction_handler` passes `player` positionally — identical to
pre-fix). The three name-less crossing keywords exist as claimed and are admitted only by the
`keywords` half: `grondia.json:1482` `["enter","go","inside"]`, `grondia.json:1804`
`["enter","east"]`, `eastern-descent.json:43` `["enter","west"]`. `Container.take_all` resolves via
the MRO walk; `Book.read → use` works because alias substitution precedes the class lookup. No
shipped Passageway authors an allow-listed verb, so the `keywords` half leaves no shipped instance
of Gap B open.

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
| #621 (2026-09-19) | **Freeze stackable merges on the fight tile until the victory dialog is dismissed.** Supersedes "handle succession on merge" for the residual. See §5. |
| #617 | **Implement, with REDUCED exp** for reinforcements (not the full 45 each). |
| #612 | **Hide the hint when panning can't move** (clamp-derived), not "let Fit pan off the arena". |
| #600 | **Leave open awaiting reporter.** Do not close. |
| #615 | Collapse synonyms **in the serializer**, not by trimming map JSON. |
| #617 | Retune the boss via Elder Slime waves, not by moving the boss's own numbers. |

---

## 5. #621 residual — DECIDED 2026-09-19, ready to implement

The residual reported at the end of the #621 fix has a maintainer decision. Full reasoning is in
the issue comment; the constraints are repeated here because they are what the implementation
turns on.

**The residual:** if a **visible** pre-existing pile of the drop's kind sits on the fight tile and
the player picks anything up before collecting, `MapTile.stack_duplicate_items` merges them, keeps
the older object, and collect-loot answers `not_found`. The units stay on the floor, visible and
takeable by hand, but the dialog gives nothing. Pre-fix: too much. Post-fix: too little.

**Decision: freeze stackable merges on the fight tile while the victory is unresolved.** Not handle
succession on merge. The window already exists — `_is_unresolved_victory(player)` is
`combat_end_summary["status"] == "victory"`, with exits at `_end_loot_phase` →
`_mark_victory_resolved` (`game_service.py:5201`, `:5213`) and `_abandon_loot_phase` (`:5373`).

**Why it beats the shipped arrangement:** one statable invariant instead of a patchwork; it closes
the residual outright rather than trading it; and the cosmetic cost is near zero because the
victory dialog covers the screen. Precedent: commit `2d0f6259` (2026-04-17) records that items
previously did not stack until the next world beat and the only complaint was visual clutter.

**Three constraints, first is the real risk:**

1. **A freeze whose release leaks becomes permanent.** Enumerate every fight-ending path *before*
   writing the gate. Defeat is safe by construction (`status != "victory"`). Session drop and
   save/load across the window both need checking.
2. **The gate is player-scoped; the merge sites are room-scoped.** `_is_unresolved_victory` takes a
   player; the merges call `player.current_room.stack_duplicate_items()`. The predicate must mean
   *"is this room the unresolved fight's tile"*. The tile is tracked; the predicate is not written.
3. **Four merge sites, not one:** `src/npc/_loot.py:135`, plus `src/items.py:327`, `:461-462`,
   `:494-495`. Gating one is a partial fix. `src/functions.py:1108` stacks an *inventory* — out of
   scope.

**Do NOT revert as redundant:** handle-based collection (the actual identity fix), and the
hidden/visible merge guard (merging resumes after the victory resolves, and a visible item merging
into a hidden pile still partially reveals an undiscovered stash).

**Verification:** engine behaviour change, so rung 1 is not enough. `python tools/bug_hunt.py
--scenario victory_loot` and `--scenario combat`, before and after, diffed. The `victory_loot`
scenario already plants a decoy twin and checks departures by wire id — extend it with the residual
case itself.

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
`tests/test_serializers_coverage.py` and one new keyword-collapse test file.
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
