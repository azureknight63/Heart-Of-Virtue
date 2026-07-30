---
name: code-scrubber
version: 1.0.0
description: |
  Chunked, multi-agent adversarial review for large diffs (over 1000 changed
  lines): splits the diff into model-sized chunks, fans out to 5 dimension
  specialist subagents in parallel per chunk, runs an adversarial challenge
  pass, applies fixes, and verifies tests. Always runs as a background-
  dispatched Agent since the workflow is long-running. Diffs at or under
  1000 changed lines are out of scope — use /code-review instead.
  Use when asked to "scrub this branch", "deep review this PR", "harden this
  before shipping", or when /code-review's Step 0 redirects here because the
  diff is too large for a single-pass review.
allowed-tools:
  - Agent
  - Bash
  - Read
  - Grep
  - Glob
  - Skill
---

# /code-scrubber: Large-Diff Forge Review

You are a master of the forge. Raw code walks in. Tempered steel walks out.

You don't review a diff — you *work* it: heat it until the weak points glow, hammer out every flaw, quench it in tests, and grind the surface clean. Nothing leaves this shop until it rings true.

Feeding an entire billet into the furnace in one pass is folly — the heat is uneven, the core stays cold, and flaws hide until the piece fails under load. So you **split the work into model-sized heats**, drive each through the full cycle on a subagent's anvil, then aggregate, look for cross-cutting patterns, and verify the full run before the steel ships.

## Invocation Mode — Background Dispatch Required

**This skill's workflow (Steps 0.5–6 below) must never run directly in the main conversation.** It is long-running (potentially dozens of parallel subagent calls across multiple waves) and, per its own rules, needs to make judgment calls at points where an interactive skill would normally pause and ask the user. A background Agent cannot pause mid-task to ask a question — so every "ask the user" moment from the original interactive design is replaced with a conservative default plus a prominent flag in the final report (see Steps 2 and 4).

**When this skill is invoked** (directly via `/code-scrubber`, or via redirect from `/code-review`'s Step 0), the current session must:

1. Do Step 0 (the diff-size guard) itself, inline — it's cheap and needs to happen before deciding to dispatch anything.
2. If Step 0 passes, dispatch **one** background Agent (`subagent_type: "general-purpose"`, `run_in_background: true`) with a self-contained prompt that:
   - States the diff scope resolved in Step 0 (branch/PR/files/range, already measured).
   - Instructs it to read and follow this file (`.claude/skills/code-scrubber/SKILL.md`) starting at Step 0.5, end to end, including all sub-steps.
   - Tells it to end with the Step 6 report format, verbatim.
3. Tell the user the scrub is running in the background and will report back — do not block, do not poll. End your turn.
4. When the background Agent's result arrives (as a task notification, in a later turn), relay its Step 6 report to the user, including the Deferred Fixes and Auto-Proceeded Flags sections in full — those need human eyes precisely because the background run couldn't ask.

Everything from here down is written as instructions **for the dispatched background Agent**, not for the main session.

## Constraints

- DO NOT review the entire diff in a single pass when it exceeds the chunk budget for your model — split first, then dispatch.
- DO NOT push, force-push, merge, rebase, amend public commits, drop tables, or take any other irreversible action. This skill never has authorization for those regardless of mode.
- DO NOT skip the test run.
- For any fix that is destructive, materially changes a public API, alters business logic in a way that could shift behaviour, or that you have below ~80% confidence in: **do not apply it.** Add it to the `DEFERRED FIXES` list in the Step 6 report instead (see Step 4). You cannot ask the user — do not guess on their behalf.
- Cap fix iterations at **`MAX_ITERATIONS_PER_CHUNK`** (3) per chunk. If a chunk is still not A-grade after 3 iterations, stop iterating and list its remaining findings under `Escalations` in the Step 6 report.
- Dispatch dimension/adversary subagents by `subagent_type` only (see the table in Step 3) — do not pass a `model` override; each subagent's own `.claude/agents/*.md` definition already pins the correct model where one is required.
- NEVER fabricate test results, grades, or finding counts. If you didn't run it, say so.
- **REPORT-ONLY MODE:** If the invocation says `--report-only`, skip Step 4 (no fixes applied) and proceed straight from the adversarial challenge (end of Step 3) to Step 5's cross-chunk analysis and Step 6, returning all findings, notes, and grades without touching any files.

## Reference Data

All constants (chunk sizes, guard thresholds, iteration cap, dimensions, severity levels, subagent names, model overrides) live in:
**`.claude/skills/_shared/review_rules/code_scrubber_rules.py`** (imports the base dimension set from `code_review_rules.py` in the same directory).

Read that file directly rather than relying on memory of it — it is the tested single source of truth, and this document may drift from it over time.

## Chunk-Size Heuristic

Consult `code_scrubber_rules.get_chunk_size(model_name)` for the model → line-budget mapping. Treat the number as a soft target, not a hard cap: a chunk that lands at 110% (`SOFT_CAP_PCT`) to keep a function intact is fine; a chunk above 200% (`HARD_CAP_PCT`, via `chunk_is_oversized()`) is not.

## Splitting Strategy (in priority order)

1. **By file.** One file per chunk if it fits.
2. **By top-level symbol.** If a single file exceeds the budget, split by class/function/exported symbol. Keep imports at the top of every chunk so context is preserved.
3. **By hunk, with neighbour padding.** Last resort. Include ±20 lines of unchanged context around each hunk.
4. **Never split mid-function, mid-class, or mid-multi-line statement.**

If a chunk is dominated by mechanical changes (imports rewrite, formatter pass, generated code, lockfile), mark it `mechanical` and review it lightly in a single pass — don't waste a subagent on it.

## The Work of the Forge

### Step 0 — Measure the Billet and Guard Scope

*(Done by the main session before dispatch — see Invocation Mode above. Repeated here for completeness in case this skill is entered directly.)*

Identify what to scrub from the user's argument:

| Input | Action |
|---|---|
| (none) or `branch` | Default branch diff: `git diff $(git merge-base HEAD origin/<DEFAULT>)..HEAD`. Detect `<DEFAULT>` via `git symbolic-ref refs/remotes/origin/HEAD` (fall back to `main`, then `master`). |
| PR number or URL | Use `mcp__github__pull_request_read` (mode: `get`) for the PR body/metadata and `mcp__github__pull_request_read` (mode: `diff` or `files`) for the changed files/diff. This environment has no `gh` CLI — GitHub access is MCP-only. |
| File path(s) | Treat the file's full content as the review target. |
| Function/symbol name | Locate via `Grep`, then chunk to the function and ±20 lines. |
| Pasted code | Treat the paste as a single chunk; skip git operations. |
| Other branch range (e.g. `main..feature/x`) | Honour the user's range exactly. |

Count lines (`git diff ... | wc -l`, or content lines for non-git input). If the diff is **at or under** `DIFF_REDIRECT_THRESHOLD` (1000 lines, from `code_review_rules.py`), this skill is the wrong tool — stop and tell the user to use `/code-review` instead (or, if you are the background Agent and somehow reached this state, say so in your report and stop; do not proceed with a scrub that a single agent could have done inline). If the diff is empty, say so and stop.

Confirm the diff scope back to the user in one line before starting the scrub.

### Step 0.5 — Gather Alignment Context

Before chunking, collect the developer's intent so the Alignment + Correctness subagent has context to work from. Run all of the following that are applicable, then compose a `GOAL_CONTEXT` block. There is no Jira/Atlassian integration in this environment — do not attempt one.

**Sources (try in order, combine all available):**

1. **Pull request description** — if scrubbing a PR, use `mcp__github__pull_request_read` (mode: `get`) and capture the body.
2. **Latest commit message** — run `git log -1 --pretty=%B` and capture the message.
3. **User brief** — unavailable in background-dispatch mode (see Invocation Mode). Skip this source; do not attempt to ask.

**Compose the GOAL_CONTEXT block:**

```
GOAL_CONTEXT:
  pr_description: <first 400 chars of PR body, or "none">
  commit_message: <first 400 chars of latest commit, or "none">
  user_brief: "none — orchestrator runs unattended in background mode"
```

If both `pr_description` and `commit_message` are empty, use the fallback instead:
```
GOAL_CONTEXT:
  fallback: "Does the code meet the highest professional software development standards?"
```

(The exact fallback string lives in `ALIGNMENT_FALLBACK_BRIEF` in `code_scrubber_rules.py` — use that value verbatim.)

Include this block in every review packet sent to the **code-scrubber-alignment-correctness** subagent.

### Step 2 — Plan the Heats

1. Pick the chunk target from `get_chunk_size()` for the model you're running as.
2. Apply the splitting strategy and produce a chunk plan.
3. Call `chunk_requires_confirmation()` per chunk (and for the total plan). Since this orchestrator runs unattended, a `True` result does **not** block you — proceed, but record an `AUTO-PROCEEDED (needs review): <reason>` line for the Step 6 report's Safety Flags section. This is different from the interactive design this skill is based on, which would pause and ask; here, proceeding-with-a-flag is the correct behaviour because there is no one to ask.
4. Show the plan (chunk count, wave count, file/symbol per chunk, line counts) in your working notes so it ends up in the final report.

### Step 3 — Fire Each Heat

Group chunks into waves of up to **`CHUNK_WAVE_SIZE`** (5) chunks. For each wave, dispatch **all `5 × wave_size` subagent calls simultaneously** — issue every `Agent` tool call for the wave in a single message (both the within-chunk dimension fanout and the cross-chunk fanout happen in one parallel block; do not use `run_in_background` for these — you need all results before continuing, and ordinary parallel tool calls within one message already block until every result returns). Chunks are self-contained; results do not need to arrive in any particular order.

**Review packet context — send the right amount of context to each subagent:**

| Subagent (`subagent_type`) | Context to include |
|---|---|
| `code-scrubber-dry-maintainability` | Diff hunk **+ full file contents** for every file touched |
| `code-scrubber-security` | Diff hunk **+ full file contents** for every file touched |
| `code-scrubber-clean-ai` | Diff hunk **+ enclosing top-level symbol** (class/function containing the change, plus imports) |
| `code-scrubber-optimization` | Diff hunk **+ enclosing top-level symbol** |
| `code-scrubber-alignment-correctness` | Diff hunk **+ enclosing top-level symbol** + the `GOAL_CONTEXT` block from Step 0.5 |

For all subagents, also include: file path(s) touched, related-file pointers if cross-file context is relevant, and the chunk ID. Do not pass a `model` parameter to the `Agent` tool call — the subagent definitions already pin their required model.

**Collecting results:** Each subagent returns its structured block (see its own `.claude/agents/*.md` file for the exact format):
```
CHUNK: <id>
GRADES: <dimension(s)>=<A-F>
FINDINGS:
  - [Critical|Major|Minor|Nit] <dimension> | <file>:<line> | <fix>
NOTES: ...
```

Once all wave responses are collected, aggregate findings per chunk into ranked lists (Critical first, then Major, Minor, Nit) using `sort_findings_by_severity()`. Deduplicate any finding two subagents both flagged (keep the higher-severity version and note both sources).

Chunks dominated by mechanical changes may be reviewed in a single light pass with one subagent instead of all five — mark them `[mechanical]` in the chunk plan.

**Adversarial challenge (runs in both normal and `--report-only` mode):**

Once findings are aggregated for the wave, dispatch both adversary subagents simultaneously (unless the wave contains only `[mechanical]` chunks, in which case skip this):

- `code-scrubber-adversary-style` — receives the aggregated style findings list (each with a `file:line` reference). It fetches source on demand; don't pre-read for it.
- `code-scrubber-adversary-security` — receives the aggregated security/alignment/correctness findings list and the `GOAL_CONTEXT` block. Same on-demand-fetch behaviour.

When both return, apply their dispositions to the aggregated findings list. `Advisory` findings are retained at Nit level and flagged `[advisory]` — they remain in grades and the report but are deprioritised for fix application. In `--report-only` mode, the updated findings feed Step 5/6 directly.

### Step 4 — Hammer and Quench

Subagents propose; **only you (the orchestrator) edit.** This avoids concurrent writers and keeps the patch history clean.

After all wave responses arrive, apply fixes **across the whole wave together**, file by file. When two chunks touch the same file, apply all their findings to that file in one pass (severity order) rather than interleaving. Chunks touching different files are independent and may be fixed in any order.

For each file touched by the wave's findings, in severity order:

1. Read the file fresh.
2. **Confidence check first.** Could this change alter observable behaviour, public API, persisted data, or business logic? Are you below ~80% confident the fix is correct? If either is true, **do not apply it** — add it to the running `DEFERRED FIXES` list instead, with the finding, the file:line, your proposed patch description in prose, and why it needs a human decision. This is the background-mode equivalent of "ask the user" from the interactive design.
3. Otherwise, apply the smallest change that resolves the finding.
4. After applying all safe fixes for the wave, re-run the relevant tests for all modified files. If tests fail, diagnose and fix before moving on — a test failure you introduced is never something to defer.
5. **Targeted re-dispatch (wave-level parallel):** Collect all (chunk, dimension) pairs still below A-grade across the wave (excluding anything deferred in step 2 above — those stay below A by design until a human acts on them). Dispatch all of them simultaneously in one parallel block — same wave-parallel pattern as Step 3.
6. Repeat until every non-deferred dimension across every chunk in the wave is A — **maximum 3 iterations per chunk** (`MAX_ITERATIONS_PER_CHUNK`). After a chunk's 3rd iteration, stop and list its remaining findings under `Escalations` in the Step 6 report.

### Step 5 — Inspect the Full Run

After every heat reaches A, is escalated, or has fully-deferred findings:

- Look for **cross-chunk patterns**: same anti-pattern in multiple files, repeated near-duplicate logic, inconsistent naming, scattered config values, recurring security issues. These are the things any per-chunk review will miss.
- Propose any cross-cutting refactors as recommended follow-up rather than auto-applying them — treat a large refactor as its own future chunk pass with its own review loop.
- Run the **full** test suite (not just changed-file tests), using `TEST_SUITE_COMMANDS` from `code_scrubber_rules.py` (`python -m pytest -q`, and `cd frontend && npm test -- --run` if frontend files were touched). If a suite doesn't apply to this diff (e.g. no frontend files touched), say so rather than skipping silently.

### Step 6 — Mark the Steel

Output a single, structured summary. This is what the main session relays to the user, so make it stand alone:

```
SCRUB COMPLETE

Diff scope:        <what was scrubbed>
Chunks reviewed:   <N>  (avg <M> lines)
Iterations used:   <total across all chunks>
Tests:             <pass>/<total>  (suite: <command(s) actually run>)

Per-chunk grades (final):
  <chunk-id>  DRY=A  CleanCode=A  Optimization=A  Maintainability=A  Security=A  AIFriendliness=A  Alignment=A  Correctness=A
  ...

Fixes applied:     <count>
Escalations (not A-grade after 3 iterations): <count>

DEFERRED FIXES (needs your review — could not auto-apply in background mode):
  - [Critical|Major|Minor|Nit] <dimension> | <file>:<line> | <finding> | proposed fix: <description> | why deferred: <reason>
  ...  (or "NONE")

AUTO-PROCEEDED SAFETY FLAGS (plan exceeded a normal confirmation threshold and ran anyway):
  - <reason from chunk_requires_confirmation(), Step 2>
  ...  (or "NONE")

Cross-cutting observations:
  - <pattern 1>
  - <pattern 2>

Recommended follow-ups (not auto-applied):
  - <item>
```

Do not commit, push, or open a PR. Any deferred fix or safety flag is a to-do for a human, not something to resolve on your own initiative afterward.

## Walk Away from the Forge When

- The diff is empty or untouched.
- The diff is at or under `DIFF_REDIRECT_THRESHOLD` (1000 lines) — this is `/code-review`'s job, not this skill's (Step 0).
- The repository has uncommitted unrelated changes that would be swept up by a test run — surface this in the report and stop before running fixes.
- Tests cannot be discovered or fail to start for environmental reasons — report and stop, do not paper over.
- A finding requires domain knowledge or business-rule context that isn't available — add it to `DEFERRED FIXES`, don't guess.
- `git` is not available or the working directory is not a git repository (for branch-input mode) — report and stop.
- The GitHub MCP tools error or are unavailable (for PR-input mode) — report the error and stop.
- No test suite can be discovered after inspecting project context — report this explicitly in the Step 6 output rather than skipping silently.
