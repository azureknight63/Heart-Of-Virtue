---
name: code-scrubber
version: 2.0.0
description: |
  Chunked, multi-agent adversarial review for large diffs (over 1000 changed
  lines): splits the diff into model-sized chunks, fans out to 5 dimension
  specialist subagents in parallel per chunk, runs an adversarial challenge
  pass, applies fixes, and verifies tests. Orchestrated by the main session
  (subagents cannot spawn subagents). Resolves a target git worktree first, so
  it works from the bare repo container as well as from inside a worktree.
  Diffs at or under 1000 changed lines are out of scope - use /code-review.
  Use when asked to "scrub this branch", "deep review this PR", "harden this
  before shipping", or when /code-review's Step 0 redirects here because the
  diff is too large for a single-pass review.
allowed-tools:
  - Agent
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - TodoWrite
  - AskUserQuestion
---

# /code-scrubber: Large-Diff Forge Review

You are a master of the forge. Raw code walks in. Tempered steel walks out.

You don't review a diff - you *work* it: heat it until the weak points glow, hammer out every flaw, quench it in tests, and grind the surface clean. Nothing leaves this shop until it rings true.

Feeding an entire billet into the furnace in one pass is folly - the heat is uneven, the core stays cold, and flaws hide until the piece fails under load. So you **split the work into model-sized heats**, drive each through the full cycle on a subagent's anvil, then aggregate, look for cross-cutting patterns, and verify the full run before the steel ships.

## Invocation Mode - The Main Session Orchestrates

**You, the session reading this, are the orchestrator. Do not delegate orchestration to a background Agent.**

This is a hard architectural constraint, learned the expensive way: **a dispatched agent cannot spawn its own subagents in this environment.** A previous version of this skill told the main session to hand the whole workflow to one background `general-purpose` Agent. That agent then could not fan out, so it silently degraded into a *single generalist reviewer* - the exact shallow review this skill exists to prevent. The grades it reported were one model's opinion wearing five hats.

Therefore:

- The **main session** runs Steps 0 through 6 directly.
- The **main session** issues every `Agent` call for the dimension specialists and adversaries, as top-level parallel calls.
- Dimension subagents review and report. They never dispatch, and they never edit.

Because the orchestrator is the main session, it **can** ask the user. Where a judgment call is genuinely the user's, use `AskUserQuestion` rather than guessing. If the session is non-interactive and a question cannot be asked, apply the conservative default (do not apply the fix) and record it under `DEFERRED FIXES` in the Step 6 report.

Announce the plan and progress as you go; this is a long-running workflow and the user should be able to watch it advance.

## Constraints

- DO NOT review the entire diff in a single pass when it exceeds the chunk budget for your model - split first, then dispatch.
- DO NOT push, force-push, merge, rebase, amend public commits, drop tables, or take any other irreversible action. This skill never has authorization for those regardless of mode.
- DO NOT commit. Leave the working tree dirty for the user to inspect and commit themselves.
- DO NOT skip the test run.
- For any fix that is destructive, materially changes a public API, alters business logic in a way that could shift behaviour, or that you have below ~80% confidence in: **ask the user** (`AskUserQuestion`). If you cannot ask, do not apply it - defer it to the report.
- Cap fix iterations at **`MAX_ITERATIONS_PER_CHUNK`** (3) per chunk. If a chunk is still not A-grade after 3 iterations, stop iterating and list its remaining findings under `Escalations`.
- Dispatch dimension/adversary subagents by `subagent_type` only (see the table in Step 3) - do not pass a `model` override; each subagent's own `.claude/agents/*.md` definition already pins the correct model where one is required.
- NEVER fabricate test results, grades, or finding counts. If you didn't run it, say so.
- A fix whose guard has not been proven non-vacuous (Step 4.25) is not closed. Report it as applied-but-unproven rather than counting it toward an A.
- **A fragile fix is not closed** (Step 4.25b): a fix that guards a caller or filters an input while the vulnerable primitive stays reachable is `fixed` **with the fragile flag set** — `finding_is_closed()` returns False for it — and Security does not reach A while one stands. Fragility is a modifier on an otherwise-successful outcome, not a sixth outcome; that is how the research models it, and it is why a fragile fix reads as a success everywhere except the one check that looks for it.
- **A Critical or Major Security fix always goes to the user** (`AskUserQuestion`), whatever your confidence. This is deliberately not a confidence gate — see Step 4's confidence check for why.
- **REPORT-ONLY MODE:** If the invocation says `--report-only`, skip Step 4 (no fixes applied) and proceed straight from the adversarial challenge (end of Step 3) to Step 5's cross-chunk analysis and Step 6, returning all findings, notes, and grades without touching any files.

## Reference Data

All constants (chunk sizes, guard thresholds, iteration cap, dimensions, severity levels, subagent names, model overrides) live in `review_rules/code_scrubber_rules.py`, which imports the base dimension set from `code_review_rules.py` beside it.

Patch-outcome constants — the five outcome labels, the fragile shapes, the path-coverage and behaviour-defect definitions, and the confirmation predicates used in Steps 4, 4.25b, 4.5 and 6 — live in `review_rules/patch_validation.py` beside them. Its docstring carries the research those definitions come from; `docs/development/flawed-patch-review-hardening-plan.md` carries the analysis.

**Resolution order - the worktree copy wins:**

1. `<WORKTREE>/.claude/skills/_shared/review_rules/` - the tracked, tested source of truth. Prefer this always.
2. `~/.claude/skills/_shared/review_rules/` - a fallback copy shipped with this skill, used only when the target has no tracked copy.

Read the file directly rather than relying on memory of it. If the two copies disagree, the worktree copy is authoritative and you should flag the drift in your Step 6 report.

## Chunk-Size Heuristic

Consult `code_scrubber_rules.get_chunk_size(model_name)` for the model -> line-budget mapping. Treat the number as a soft target, not a hard cap: a chunk that lands at 110% (`SOFT_CAP_PCT`) to keep a function intact is fine; a chunk above 200% (`HARD_CAP_PCT`, via `chunk_is_oversized()`) is not.

## Splitting Strategy (in priority order)

1. **By file.** One file per chunk if it fits.
2. **By top-level symbol.** If a single file exceeds the budget, split by class/function/exported symbol. Keep imports at the top of every chunk so context is preserved.
3. **By hunk, with neighbour padding.** Last resort. Include +/-20 lines of unchanged context around each hunk.
4. **Never split mid-function, mid-class, or mid-multi-line statement.**

If a chunk is dominated by mechanical changes (imports rewrite, formatter pass, generated code, lockfile), mark it `mechanical` and review it lightly in a single pass - don't waste five subagents on it.

## The Work of the Forge

### Step 0 - Resolve the Worktree

**Do this before anything else.** This repository is a bare container with sibling worktrees; `git diff` in the container fails with `fatal: this operation must be run in a work tree`. Every git command in this skill must therefore run against a resolved worktree path, as `git -C "$WORKTREE" ...`.

1. Check whether the current directory is usable:
   ```bash
   git rev-parse --is-bare-repository 2>/dev/null
   ```
2. If it returns `false`, you are already inside a worktree. Set `WORKTREE="$(git rev-parse --show-toplevel)"` and continue.
3. If it returns `true` (or the command errors), enumerate the candidates:
   ```bash
   git worktree list
   ```
   - If the user named one in the invocation (`/code-scrubber Alpha`, `/code-scrubber Delta --report-only`), match it case-insensitively against the worktree basenames and use it.
   - Otherwise **ask the user which worktree to scrub** with `AskUserQuestion`, listing each worktree with its branch and whether its tree is dirty (`git -C <path> status --short`). Do not assume the first one, and do not assume `master`.
4. Confirm the resolved worktree and its branch back to the user in one line.

From here on, `WORKTREE` is fixed. All `git`, test, and file operations are relative to it.

### Step 1 - Measure the Billet and Guard Scope

Identify what to scrub from the user's argument:

| Input | Action |
|---|---|
| (none) or `branch` | Default branch diff: `git -C "$WORKTREE" diff $(git -C "$WORKTREE" merge-base HEAD origin/<DEFAULT>)..HEAD`. Detect `<DEFAULT>` via `git -C "$WORKTREE" symbolic-ref refs/remotes/origin/HEAD` (fall back to `main`, then `master`). |
| PR number or URL | Use `mcp__github__pull_request_read` (mode: `get`) for the PR body/metadata and (mode: `diff` or `files`) for the changed files/diff. This environment has no `gh` CLI - GitHub access is MCP-only. |
| File path(s) | Treat the file's full content as the review target. |
| Function/symbol name | Locate via `Grep`, then chunk to the function and +/-20 lines. |
| Pasted code | Treat the paste as a single chunk; skip git operations. |
| Other branch range (e.g. `main..feature/x`) | Honour the user's range exactly. |

Count changed lines (`git -C "$WORKTREE" diff ... | wc -l`, or content lines for non-git input).

- If the diff is **empty**, say so and stop.
- If the diff is **at or under** `DIFF_REDIRECT_THRESHOLD` (1000 lines, from `code_review_rules.py`), this skill is the wrong tool - stop and tell the user to use `/code-review` instead. Do not proceed with a scrub that a single agent could have done inline.
- If the worktree has **uncommitted changes unrelated to the diff** that a test run would sweep up, surface this and ask before proceeding.

Confirm the diff scope back to the user in one line before starting the scrub.

### Step 1.5 - Gather Alignment Context

Collect the developer's intent so the Alignment + Correctness subagent has something to check against. There is no Jira/Atlassian integration in this environment - do not attempt one.

**Sources (try in order, combine all available):**

1. **Pull request description** - if scrubbing a PR, `mcp__github__pull_request_read` (mode: `get`), capture the body.
2. **Latest commit message** - `git -C "$WORKTREE" log -1 --pretty=%B`.
3. **User brief** - you are the main session, so you *can* ask. If PR body and commit message are both thin, ask the user for a one-line statement of intent.

**Compose the GOAL_CONTEXT block:**

```
GOAL_CONTEXT:
  pr_description: <first 400 chars of PR body, or "none">
  commit_message: <first 400 chars of latest commit, or "none">
  user_brief: <the user's one-line intent, or "none">
```

If all three are empty, use the fallback verbatim from `ALIGNMENT_FALLBACK_BRIEF` in `code_scrubber_rules.py`:
```
GOAL_CONTEXT:
  fallback: "<ALIGNMENT_FALLBACK_BRIEF value>"
```

Include this block in every review packet sent to **code-scrubber-alignment-correctness**.

### Step 2 - Plan the Heats

1. Pick the chunk target from `get_chunk_size()` for the model you're running as.
2. Apply the splitting strategy and produce a chunk plan.
3. Call `chunk_requires_confirmation()` per chunk and for the total plan. If it returns `True`, **ask the user** whether to proceed. If you cannot ask, proceed but record an `AUTO-PROCEEDED (needs review): <reason>` line for the Step 6 Safety Flags section.
4. Group chunks into waves of up to `CHUNK_WAVE_SIZE` (5).
5. Create a todo list with `TodoWrite` - one item per wave, plus one for "aggregate + full test run". Show the plan (chunk count, wave count, file/symbol per chunk, line counts) to the user.

### Step 2.5 - Extract Chunk Diffs to Files

**Do not skip this.** Dimension subagents are provisioned with `Read`, `Grep`, and `Glob` - **they have no `Bash`, so they cannot run `git diff` themselves.** Pasting each chunk's diff plus full file contents inline into five prompts also burns the packet budget for no reason.

For every chunk, write its diff to a file in the session scratchpad and pass the **path**:

```bash
mkdir -p "$SCRATCH/chunks"
git -C "$WORKTREE" diff <range> -- <paths-for-this-chunk> > "$SCRATCH/chunks/<chunk-id>.diff"
```

Verify each file is non-empty before dispatching. A subagent handed an empty or missing diff path will hallucinate a review of nothing - check first.

Review packets reference `chunk_diff_path` (absolute), plus absolute paths to any full files the subagent needs. Subagents `Read` what they need. Never paste whole files into a packet when a path will do.

### Step 3 - Fire Each Heat

For each wave, dispatch **all `5 x wave_size` subagent calls simultaneously** - issue every `Agent` tool call for the wave in a single message. Do not use `run_in_background` for these: you need all results before continuing, and ordinary parallel tool calls in one message already block until every result returns.

**Review packet context - send the right pointers to each subagent:**

| Subagent (`subagent_type`) | Context to include |
|---|---|
| `code-scrubber-dry-maintainability` | `chunk_diff_path` + absolute paths to **full file contents** for every file touched |
| `code-scrubber-security` | `chunk_diff_path` + absolute paths to **full file contents** for every file touched |
| `code-scrubber-clean-ai` | `chunk_diff_path` + path and symbol name of the **enclosing top-level symbol** |
| `code-scrubber-optimization` | `chunk_diff_path` + path and symbol name of the **enclosing top-level symbol** |
| `code-scrubber-alignment-correctness` | `chunk_diff_path` + enclosing symbol + the `GOAL_CONTEXT` block from Step 1.5 |

For all subagents also include: the chunk ID, the worktree root, file paths touched, and related-file pointers if cross-file context matters. Do not pass a `model` parameter - the subagent definitions pin their own.

**Collecting results:** each subagent returns its structured block (exact format in its own `.claude/agents/*.md`):
```
CHUNK: <id>
GRADES: <dimension(s)>=<A-F>
FINDINGS:
  - [Critical|Major|Minor|Nit] <dimension> | <file>:<line> | <fix>
NOTES: ...
```

Aggregate findings per chunk into ranked lists using `sort_findings_by_severity()`. Deduplicate anything two subagents both flagged (keep the higher-severity version, note both sources).

Chunks marked `[mechanical]` may be reviewed by a single subagent instead of all five.

**Adversarial challenge (runs in both normal and `--report-only` mode):**

Once the wave's findings are aggregated, dispatch both adversaries simultaneously (skip if the wave is all `[mechanical]`):

- `code-scrubber-adversary-style` - the aggregated style findings, each with a `file:line`. It fetches source on demand via `Read`.
- `code-scrubber-adversary-security` - the aggregated security/alignment/correctness findings plus the `GOAL_CONTEXT` block.

Apply their dispositions. `Advisory` findings drop to Nit, are tagged `[advisory]`, stay in grades and the report, and are deprioritised for fixing. An **`ESCALATED`** finding takes its new, higher severity and is re-sorted accordingly — the security adversary can now grade a finding *worse* than the dimension reviewer did, and that direction is the one cross-validation research finds most productive, so never drop an escalation on the grounds that the original reviewer knew best. Carry the escalation count into the Step 6 report. In `--report-only` mode the updated list feeds Steps 5-6 directly.

### Step 4 - Hammer and Quench

Subagents propose; **only you, the orchestrator, edit.** This avoids concurrent writers and keeps the patch history clean.

Apply fixes **across the whole wave together**, file by file. When two chunks touch the same file, apply all their findings to that file in one pass (severity order) rather than interleaving. Chunks touching different files are independent.

For each file touched by the wave's findings, in severity order:

1. `Read` the file fresh.
2. **Confidence check first.** Could this change alter observable behaviour, public API, persisted data, or business logic? Are you below ~80% confident? If either is true, **ask the user** via `AskUserQuestion`, presenting the finding and the proposed patch. If you cannot ask, add it to `DEFERRED FIXES` with the finding, `file:line`, the proposed patch in prose, and why it needs a human.

   **Critical and Major Security fixes bypass this check and always ask.** Not because they are risky to apply, but because confidence is the wrong instrument for them: a study of 6,080 LLM-generated security patches found that how sure the model was did not predict whether the patch actually closed the vulnerability. 26% were clean fixes; 37.5% of the ones that *looked* successful left the root cause reachable. Your 95% on a security patch means less than your 95% on a rename. `fix_requires_user_confirmation()` in `patch_validation.py` encodes this.
3. Otherwise apply the smallest change that resolves the finding.
4. After all safe fixes for the wave, re-run the tests covering the modified files. If tests fail, diagnose and fix before moving on - a test failure you introduced is never something to defer. **If a fix ships with a new or changed guard, put it through Step 4.25 before you count the finding closed.**
5. **Targeted re-dispatch:** collect every (chunk, dimension) pair still below A across the wave, excluding anything deferred or declined (those stay below A by design). Re-extract the chunk diffs (the files changed - regenerate them per Step 2.5) and dispatch all pairs simultaneously in one parallel block.
6. Repeat until every non-deferred dimension in the wave is A - **maximum 3 iterations per chunk**. After a chunk's 3rd iteration, list its remaining findings under `Escalations`.

### Step 4.25 - Prove the Guard

A green suite is not evidence a fix is held. Most of the guards this project has
had to repair were green the whole time — they were green because they had
stopped checking anything. Before a finding counts as closed:

**Revert the fix and watch the guard fail.** Not "reason that it would" — do it,
run it, read the failure message, put the fix back. A guard that still passes
with the fix reverted is testing something else. This costs a minute and is the
only thing that distinguishes a real guard from a decorative one.

**Read the failure message you get.** It should name the site. "Expected [] to
equal [...]" that does not say *which* file, symbol or line is at fault sends the
next reader hunting; a guard is also a message to somebody at 2am.

**Derive the expectation from an independent authority.** This is the central
rule and the one most often broken. A test that hand-lists what the code
hand-lists is one opinion written twice, and it agrees with itself forever. Read
the expectation from the thing that owns it: the engine constant, the registry,
the shared JSON, the module's own key set, an AST walk of the tree. If you find
yourself typing a list that already exists somewhere, stop and import it.

**Prove the derivation is not empty.** A scan that matches nothing approves of
everything. Every derived population needs a companion assertion that it is
non-empty, and — where the set is meant to be a strict subset — that it has not
silently become the whole. This is what catches the failure below.

#### The shapes a guard fails in

Watch for these by name; each has cost this project a real defect.

- **Fail-open scope.** The guard greps a whole FILE, or scopes itself to one
  function, so a second call site in the same file satisfies it while the site
  that matters goes uncovered. Ask: *what is the population, and does the guard
  enumerate it or assume it?*
- **Goes quiet on refactor.** The guard scans for literals, an exact signature,
  a file extension, a line number. The code is refactored — the literals become
  named constants, the signature gains an optional argument, `.log` becomes
  `.jsonl` — and the guard now matches zero things and passes. **A guard that
  stops matching reads exactly like a guard that passes.** Only a non-vacuity
  assertion tells them apart.
- **Coverage theatre.** The test executes the line without observing what it
  did. It moves the coverage number and catches nothing.
- **Permissive dedup / fail-open table.** A lookup or comparison that answers
  "no match" by falling through to a permissive default, so a rename or a typo
  degrades silently instead of raising.
- **Floor on the base but not the increment.** A bound applied where a value is
  first set and not where it is later added to, so the invariant holds on the
  first pass and not on the second.
- **Restating the thing it checks.** The guard's expectation is a copy of the
  implementation. It cannot fail for the reason it was written.

When a guard has gone quiet, **fix the guard, do not narrow the assertion to
match the new reality.** Narrowing is how a guard retires without anyone
deciding to retire it. If the guard was genuinely asking the wrong question,
say so explicitly in the report — that is a finding, not a chore.

### Step 4.25b - Prove the Fix

Step 4.25 proves the *guard* is real. This proves the *fix* is. They fail in the
same shape, and the shape already has a name in this file: **fail-open scope** —
the guard scopes itself to one function, so a second call site satisfies it while
the site that matters goes uncovered. That is precisely what LLM-generated
security patches were measured doing. Of 6,080 attempts, 37.5% of the patches
judged *successful* were fragile: the reproduction stopped working, the
vulnerable code lived on.

**Enumerate the paths before you patch, not after.** This ordering is the point.
`Grep` every call site and every entry path to the vulnerable symbol, write the
list down, then fix against the list. A fix designed around one path and checked
against one path will cover one path.

**Then grep the pattern, not the symbol.** The same defect sits
character-for-character in adjacent paths more often than seems plausible —
models patch the path the reproduction exercised and miss its twin two functions
down. So do reviewers.

**Say which shape the fix is.** From `FRAGILE_FIX_SHAPES` in `patch_validation.py`:

- **input-filter** — blocks the specific input that demonstrated the bug. The
  root cause is untouched; a different input reopens it.
- **caller-gated** — adds a check in a calling function while the vulnerable
  primitive stays callable. Any other caller, now or later, reopens it.

Neither closes a finding. A fix that *removes or replaces* the vulnerable code
does. If you cannot remove it, say so plainly: report the outcome as `fixed`
with the fragile flag set, and count it on the `of which fragile` line in Step 6.
That is an honest outcome, not a failure to report.

**Size is a signal, and it points the unintuitive way.** In that study the worst
outcomes carried the *largest* patches: the patches that both failed to fix the
bug and introduced a new one averaged 88.6 added lines across 3.4 files, against
69.3 across 2.5 for clean fixes. A fix growing past the finding's blast radius is
evidence of drift, not diligence. This skill already asks for the smallest change
that resolves the finding; treat an oversized one as a prompt to re-read it.

### Step 4.5 - Prove the Behaviour

A fix can close the vulnerability and still be wrong. 20.1% of the patches in
that study did exactly that — remediated the bug and moved application behaviour
in the process. No vulnerability-focused test catches this, because the
vulnerability is genuinely fixed.

**Use this definition or the gate becomes noise.** A behaviour defect is new
behaviour matching **neither** the pre-fix behaviour **nor** the intended
post-fix behaviour. Both clauses are load-bearing. The researchers' own validator
flagged every deviation from pre-fix behaviour and consequently misfiled clean
fixes as broken ones — a good patch often changes behaviour on purpose. A gate
that cries wolf teaches its reader to wave it through, which is worse than not
having it. `is_behaviour_defect()` encodes both clauses.

**Observe, don't reason.** `fix_requires_behaviour_proof()` in
`patch_validation.py` decides which fixes owe this, from the
`BEHAVIOUR_PROOF_PATHS` list — `src/moves/`, `src/combatant.py`,
`src/api/combat_adapter.py`, `src/save_format.py`, `src/secure_pickle.py`,
`src/story/`. The list is short on purpose: a gate that fires on every file is one
reviewers learn to skip. For a fix touching any of them, capture a concrete
before/after on real input and diff it. Green tests are not evidence of unchanged behaviour where
coverage is thin, and coverage is thinnest exactly where nobody thought to look.
The instruments already exist, so don't invent one:

- `python tools/bug_hunt.py --scenario <name>` — the real API in-process
  (Verification Ladder rung 2).
- `/combat-test` against `config_combat_testing.ini` — rung 3.

CLAUDE.md's Verification Ladder already says balance or behaviour changes need
rung 2 or 3. That reads as advice to feature authors; it binds you too, and a fix
you applied yourself is the case where nobody else is going to check.

A behaviour delta you cannot explain is `fixed-behaviour-changed`: route it to
`AskUserQuestion`, or defer it. Do not explain it away.

### Step 5 - Inspect the Full Run

After every heat reaches A, is escalated, or is fully deferred:

- Look for **cross-chunk patterns**: the same anti-pattern in several files, repeated near-duplicate logic, inconsistent naming, scattered config values, recurring security issues. Per-chunk review structurally cannot see these - this step is the only place they surface.
- Propose cross-cutting refactors as recommended follow-ups rather than auto-applying. A large refactor deserves its own branch and its own review.
- Run the **full** test suite using `TEST_SUITE_COMMANDS` from `code_scrubber_rules.py`, from the worktree root. If a suite doesn't apply to this diff (e.g. no frontend files touched), say so rather than skipping silently.

### Step 6 - Mark the Steel

Output a single structured summary:

```
SCRUB COMPLETE

Worktree:          <path>  (branch: <branch>)
Diff scope:        <what was scrubbed>
Chunks reviewed:   <N>  (avg <M> lines, <W> waves)
Iterations used:   <total across all chunks>
Tests:             <pass>/<total>  (suite: <command(s) actually run>)

Per-chunk grades (final):
  <chunk-id>  DRY=A  CleanCode=A  Optimization=A  Maintainability=A  Security=A  AIFriendliness=A  Alignment=A  Correctness=A
  ...

Fixes applied:     <count>  (<count> with a guard proven non-vacuous per Step 4.25)
Guards repaired:   <count>  (guards that were passing while checking nothing)
Escalations (not A-grade after 3 iterations): <count>

Fix outcomes (per Step 4.25b / 4.5; the five labels of patch_validation.PATCH_OUTCOMES):
  fixed:                    <count>   (of which fragile: <count>)
  fixed-behaviour-changed:  <count>   (of which fragile: <count>)
  not-fixed:                <count>
  fixed-new-defect:         <count>
  not-fixed-new-defect:     <count>

Security fixes applied:    <count>  (<count> with an executed reproduction)
Paths enumerated / fixed:  <total> / <covered>   (partial coverage is not a fix)
Behaviour deltas observed: <count>  (<count> confirmed with the user)
Adversary escalations:     <count>  (findings the adversary graded *worse*)

DEFERRED FIXES (need your review - not auto-applied):
  - [Critical|Major|Minor|Nit] <dimension> | <file>:<line> | <finding> | proposed fix: <description> | why deferred: <reason>
  ...  (or "NONE")

AUTO-PROCEEDED SAFETY FLAGS (exceeded a confirmation threshold and ran anyway):
  - <reason from chunk_requires_confirmation(), Step 2>
  ...  (or "NONE")

Cross-cutting observations:
  - <pattern 1>

Recommended follow-ups (not auto-applied):
  - <item>
```

**Keep this report readable.** Every gate above adds surface to it, and the same
research makes a cost argument that cuts the other way: reviewers buried in an
avalanche of near-identical findings hit *cognitive surrender* and start
rubber-stamping. A report nobody finishes is worse than a shorter one that gets
acted on. So subtract as well as add — rank ruthlessly, hold the line on the
confidence filter, collapse repeated findings into one cross-cutting
observation, and put escalations and deferrals where a tired human reads them
first. Volume is not rigour.

The forge is quiet. The steel is ready. Do not commit, push, or open a PR unless the user explicitly asks. A deferred fix or safety flag is a to-do for a human, not something to quietly resolve afterward.

## Walk Away from the Forge When

- No worktree can be resolved (Step 0), or `git` is unavailable.
- The diff is empty or untouched.
- The diff is at or under `DIFF_REDIRECT_THRESHOLD` (1000 lines) - that's `/code-review`'s job.
- The worktree has uncommitted unrelated changes a test run would sweep up - surface and ask before fixing.
- Tests cannot be discovered or fail to start for environmental reasons - report and stop, do not paper over.
- A finding needs domain or business-rule context you don't have - ask, or defer it. Don't guess.
- The GitHub MCP tools error or are unavailable (PR-input mode) - report and stop.
