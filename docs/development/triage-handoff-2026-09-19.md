# Triage pass handoff — 2026-09-19

**Status:** in progress (session 3). **Read §0 first** — it supersedes §3's "where it stopped".
**Branch:** `claude/issue-triage-a7acc5` (worktree `.claude/worktrees/issue-triage-a7acc5`)
**Merge base:** `c8f5f17b` (== `origin/master` at pass start)
**PR #645 is open** (pushed at `c363213d`). `closingIssuesReferences` verified: 611 612 614 618 620 621
624 625 633 634 — not 613 (already closed), not 615. After merging, re-run §12's per-issue state
check. Follow-ups filed: #636–#644. PR #635 overlaps on `game_service.py` and
`test_wire_field_contract.py`.

This file is the resume point. Update it at milestones.

---

## 0. Session 2 — resume point (supersedes §3's status lines)

A session whose launch worktree is a *different* one is blocked from editing this worktree's
files. Enter it first: `EnterWorktree` with `path` = this worktree.

### Scrub state (updated session 3)
| Chunk | Dimension agents | Adversaries | Fixes |
|---|---|---|---|
| c1-620-security | 5/5 | done | all substantive findings fixed |
| c2-621-loot | 5/5 | done | all substantive findings fixed |
| c3-shop-items | 5/5 | done | all substantive findings fixed |
| c4-frontend-combat-chat | 5/5 | done | all Majors and confirmed Minors fixed (F7, E2, E4-E6, E8, E10-E12, E16, E17, E19) |
| c5-dry-feedback | 5/5 (Opt A, Sec A, DRY/Maint B/B, Clean/AIF C/B, Align/Corr A/B) | done | all fixed (G1, G4, G6, G8-G12, G14, H1, H2); G3/H3 are follow-up issues; G5/G13 advisory |

**Session 3 commits:** `b9d1b151` F1 typewriter completes only once shown (hook fix +
real-hook panel tests `NpcChatPanel.autoClose.test.jsx`) · `2f897cec` F4/F5 range shortfall only on
range locks (`RANGE_LOCK_REASONS`, `shortfallSuffix`, contract pin in
`test_combat_glossary_contract.py`) · `c5ad430e` **server-side chat turn budget**
(`NpcChatLLMAdapter.bounded_by` thread-local deadline, `_call_timeout` clipping, chain stops when
spent, personality inside the budget, `_TURN_CEILING_SECONDS = 21.0`, client `NPC_CHAT_TIMEOUT_MS
= 28000`, `tests/test_npc_chat_turn_budget.py` derives both bounds incl. the Procfile worker
timeout) · `000f3ff1` **single-flight chat turns** (`GameService._one_chat_turn`, weak-keyed
per-player lock, 409 via `_chat_status`, client "Still composing a reply — give it a moment.") ·
`8c2b1e1c` c5 backend (G6 `join_party` seeds the party, H1 call-site test, H2 fail-open log-dir
probe, G8 `MERCHANDISE_RETURN_PHRASES`, G11, G12, G14) · `3e3ed707` c5 frontend (G1, G4 contract
keys applied after caller props/style, G10) + **F7** End closes at once, `/end` fire-and-forget ·
`46f245c2` comments that still described await-then-close (E16 moot: every path now latches) ·
`136f1f0c` G9 #611 test samples the holding when the confirmation is queued (revert-proved) +
G14 frontend nits · `92b42f68` c4 style Minors (E2, E4-E6, E8, E10-E12, E17, E19).
Last full runs (after `92b42f68`): backend 4 failed (pre-existing openai) / 14712 passed; frontend
165 files / 3796 passed; flake8 `src/` clean.

**Round-2 re-review (session 3):** r1 Security over the #620 root fix → **Security A, no findings**
(every map/save write path gated at the write; root fix, not fragile). r2 Alignment/Correctness over
the chat budget → C/C, all findings fixed in `d63483e6` except the double commit (decided above):
clipped timeouts no longer bench models, the 400 retry is held to the turn, `bounded_by` nests by
tightening, the turn clock starts before a cold `_get_adapter()`, End in the auto-close window sends
no `/end`, a 409 on `/open` has its own copy. `/code-review` over the architecture subset
(`src/api/` + `ai/llm_client.py`, 479 lines): **Architecture A**; Correctness findings folded into
the same fixes. After `d63483e6`: backend 4 failed (openai) / 14719 passed; frontend 165 / 3798;
flake8 clean; `bug_hunt` full 0 bugs; `--scenario victory_loot` (its config) 0 bugs.

**c4/c5 findings:** all closed — see the commits above. One correction to a finding, recorded so
it is not "fixed" back: E17 said the recenter control disappears anyway when the window grows to
cover the arena. It does not for a sub-cell drag remainder (0 cells is still legal, so the
re-clamp effect returns early), which is why the control stays ungated on `canPan`.

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
| #618 chat turn budget (session 3) | **Bound the turn server-side**: the turn deadline reaches `_call_llm` (stop walking the chain once spent, clip each call's timeout to what remains) and `_ensure_personality`. |
| Prod topology (session 3) | **The Procfile is production** (`gunicorn -w 1`, sync, 30s timeout, in-memory sessions): keep a turn under **~25s total**; client deadline **~28s**, pinned by a relational test to the engine budget. |
| Retry double-commit (session 3) | **Single-flight now**: a per-player chat-turn lock in `npc_chat_open`/`npc_chat_respond`; a second request while one is in flight gets **409** and the client shows a fixed "still composing" line. |
| #615 (session 3) | **Leave open** — its own branch, suite run and review later. Do not claim it in this PR. |
| Re-review depth (session 3) | **Targeted, 2 agents**: c1 Security over the #620 root fix, c4 Alignment/Correctness over the chat budget + single-flight. No adversary pass (findings verified inline). |
| Retry double commit (session 3, round 2) | **Accept + follow-up.** The single-flight lock never fires under production's sync worker (requests are serialised, so a Retry queues and commits a second turn AFTER the abandoned one). Keep the lock for threaded servers, correct the comments, file idempotent turns (`turn_id` replay) as a follow-up. |
| Floor equip mid-fight (session 3, round 2) | **Allow it.** Equip picks a floor item up but never restacks; the take/drop gate exists for merges. Documented on `_FLOOR_PILE_HANDLERS`. |
| #620 closure (session 3, round 2) | **Signed off by the maintainer** — close #620 in this PR (Major Security; the re-review graded Security A, no findings). |

### Committed in session 2
`78577df1` C1 alias-word helper read off the class (repro: 21 red → green) · `5c4b608b` derived
shop guards (families incl. Key; every stackable keeps its name) · `d030abe8` shared
`walk_json_strings`, authored-path containment test · `65e87b7e` identity in #621 fixtures,
keywords keyed by placement.

Then: `a89f3b96` **#620 root fix** (map loader refuses shadowing props; pure-Python
`SafeUnpickler` refuses BUILD onto classes/functions and drops shadowing state; class-marker gate
requires a trusted class; C2/C4 per-site) · `bf430364` `accepts_step_through` + `advertised_keywords`
(C7, D1) + stale #620 docs (C8) · `92fd5321` full-universe save round-trip moved to `tests/api/` ·
`68a726b9` **#621 freeze** (`functions.restack_floor` is the only merge site; frozen while the
victory is unresolved and the room holds an offered object; take/drop refused mid-fight; harness
provokes a restack — freeze off: 4/4 runs catch it).

Pre-existing, unrelated, for a follow-up issue: `--scenario combat` under
`config_combat_testing.ini` with `active_scenario = boss` walks east twice through the aggro Fodder
Pit and the #543 move guard refuses the second step. A11 (victory_loot identity half skipped when
the roll drops only Gold) needs a TESTING-only loot-pinning debug op — follow-up.

Then: `31890ca3` C5 (`_MAX_LOOT_REQUEST_NAMES`), C6 (remove the drop by identity, not the stale
index), A2 (`Item.take` leaves the floor before entering the pack) via
`functions.remove_by_identity` · `3d4357d8` A7 split piles mint their own handle
(`functions.copy_item_state`) · `e0676418` A6 VICTORY dialog details by handle · `5aff2126` c2
docstrings + `_floor_of` · `48216303` **B1/B2 shop economy** · `88e76fe5` B10 container-take count,
B4 `Book.text` repo-relative + no path/errno in narration · `1cb61379` c3 comments,
`_NEVER_STOCK_EXACT_CLASSES` rename. Every fix above had a red test first; security ones were
revert-proved. Last full run: backend **4 failed (pre-existing openai) / 14693 passed**, flake8 `src/`
clean, `bug_hunt` 0 bugs (full, default config), `--scenario shop` 0, `--scenario victory_loot` 0
(freeze on) / 4-of-4 caught (freeze off).

### Pending, in order (resume here)
ALL DONE through PR #645 (session 3). Remaining: CI green, maintainer review/merge, then §12's
post-merge state check.
1. (done) Decide the re-review depth (ask the maintainer if budget is tight — weekly was 82% at the end of
   session 3): at minimum re-dispatch **c1 Security** over the #620 root fix (secure_pickle,
   universe, map_placeholders) and **c4 Alignment/Correctness** over the chat budget +
   single-flight; the skill's full rule is every below-A (chunk, dimension) pair, max 3 iterations.
2. (done) `/code-review` over the architecture-touching subset (`src/api/`, `GameService`, serializers,
   `combat_adapter`, `ai/llm_client.py`) — the scrubber has no Architecture dimension.
3. (done) Full suites + `bug_hunt` (full, default config) + `--scenario victory_loot` under its config.
4. PR per §12. Closes: #611 #612 #614 #618 #620 #621 #624 #625 #633 #634. NOT #613, NOT #615
   (decided: leave open). #633/#634 were filed mid-pass and fixed by A7/A6; round 2 added the
   derived guards each issue asked for. File the follow-ups below first so the PR body can link them.

### Follow-up issues to file (not this branch)
- Idempotent NPC chat turns: the single-flight lock is inert under the Procfile's sync worker, so a Retry after a client timeout commits a second turn after the abandoned one. Client mints a `turn_id` per option click; Retry reuses it; the server replays the stored result.
- `SafeUnpickler.load_build` refuses BUILD onto classes/functions/modules but not onto a module-level *instance* of an engine class; refuse BUILD onto any resolved module global (security re-review residual, pre-existing).
- `requests` applies a timeout per phase (connect, then read), so a clipped chat call can still end past the turn deadline by its own length; only dangerous with a raised `NPC_CHAT_LLM_TIMEOUT`. A wall-clock bound needs different machinery.
- A cold `NpcChatLLMAdapter` is built on the request path (model discovery up to 20s + validation calls); the turn now counts that time, but construction itself can approach the worker timeout. Don't build on the request path while a prewarm is in flight.
- `npc_chat_end` pops `_active_chat_npc_id` unconditionally, so a late `/end` from panel A can clear B's marker; store the npc_key with the marker (pre-existing).
- Touch-target floor gated on viewport width, not pointer type (H3): a >767px touch tablet gets ~13px targets; gate every `useMobile`-only floor on `isMobile || isCoarse` (HeatMeter, GlossaryHelpButton.jsx:26, ShopDialog.jsx:198) with a combat-panel height check.
- Remaining fold toggles hand-rolled (ChangelogPanel, CombatLog `<div onClick>`, SuggestedMovesPanel) — move onto CollapsibleSectionHeader (G3).
- Per-session mutation lock over collect/take/drop/shop (root of A1/A2/A4/A5; `_LOOT_PHASE_LOCK`
  only serialises collects).
- Save loader: REDUCE may call any allow-listed engine global with arbitrary arguments during
  load (pre-existing; #13's territory).
- `victory_loot` identity half is skipped when the roll drops only Gold — needs a TESTING-only
  loot-pinning debug op (A11).
- `--scenario combat` under `active_scenario = boss` walks through the aggro Fodder Pit and the
  #543 move guard refuses the second step.
- B8: a pre-#624 save's stacks keep a baked name ("Mineral Powder x3") that nothing resyncs.
  Save compat is suspended for beta; decide whether to normalise in `__setstate__`.
- Style Minors left from c1–c3 (T1 `_fill_remaining_stock` extraction, T4 `_spawn_merchandise`,
  T11 harness `_live_player_tile`, T16 harness shop.py, S7/S9 victory_loot helpers, S1/S2).

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
for n in 611 612 614 615 618 620 621 624 625 633 634; do
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
