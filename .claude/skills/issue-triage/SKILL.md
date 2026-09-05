---
name: issue-triage
version: 1.0.0
description: |
  Use when the user wants their open GitHub issues worked as a batch rather
  than one named issue fixed. Trigger on any ask to triage, sort, clear out,
  shrink, work through, deal with, knock out, or simply see what is on the
  issue list / queue / backlog — including casual phrasings ("what's open right
  now?", "close what you can", "handle whatever doesn't need me"), asks that
  mix doing the easy ones with flagging the rest, a count of open bug reports
  or refactors to be worked together, or several issue numbers handed over at
  once. Also trigger when the user describes the workflow themselves (fan out
  subagents across the issues, batch the decisions back to me).
  It reads every open issue, separates what can be fixed now from what needs
  the maintainer's call, diagnoses before fixing, revert-proves each fix, and
  returns the genuine decisions as one batched question instead of guessing.
  Do NOT use it to fix a single specified issue, or to file a new one — that is
  ordinary work.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Agent
  - Skill
  - AskUserQuestion
---

# Issue Triage

The goal is to move the issue list, not to look busy. A triage pass is
successful when issues are genuinely closed with verified fixes, the ones that
needed a human decision got asked as *one* clear question, and nothing was
quietly half-done.

Two failure modes are worth naming up front, because both feel productive:

- **Guessing at a decision issue.** Issues titled "Decision:" exist precisely
  because someone chose not to decide alone. Picking one yourself is not
  triage, it's a coin flip that costs a revert.
- **Declaring a fix done because the tests are green.** A test written
  alongside a fix usually passes with the fix removed too. Green means nothing
  until you have shown the test fails without the change.

## Step 1 — Read the whole list before touching anything

Pull every open issue with bodies and comments. Read them all before starting
work, because the sorting depends on seeing the set:

```bash
# via the GitHub MCP tools — this environment has no `gh` CLI
mcp__github__list_issues   (state: OPEN, include body + comments)
mcp__github__issue_read    (method: get, and get_comments where comments > 0)
```

Comments matter more than they look. An issue whose body poses a question may
already have been answered by a one-line maintainer comment months ago —
"Defer until SocketIO ships" settles the issue, and re-asking wastes the user's
attention. Always read the comments before classifying anything as needing a
decision.

Sort each issue into exactly one of:

| Bucket | Meaning | What happens |
|---|---|---|
| **Clear** | The issue states what to do, or the cause is findable | Diagnose, then fix, via subagents |
| **Decision** | Genuinely needs the maintainer's call | Batch into one `AskUserQuestion` |
| **Settled** | Already answered in comments | Leave it; say so in your report |
| **Verify** | Claims something is done — check before believing it | Confirm against the repo first |

The **Verify** bucket earns its place. A user may tell you an issue is finished
and be right about the substance while the wiring is missing — a composed asset
that ships in the repo but is registered nowhere, so it never loads. Check the
claim, close the issue as asked, and record the gap you found in the closing
comment rather than silently closing or silently refusing.

## Step 2 — Diagnose before you fix, read-only and in parallel

For every bug-shaped issue, dispatch a **read-only** diagnosis agent first, and
say so explicitly in the prompt: *"do NOT edit any files."* These are cheap,
they run in parallel without conflicting, and they routinely overturn the issue's
own framing.

This is the single highest-leverage habit in the whole workflow. In practice
the reported symptom is often not the defect:

- A "the advisor never suggests Rest" report turned out to be a scoring dead
  band, not a missing move — the fix the title implied would have been wrong.
- A "I submitted a bug report and got stuck" report was not caused by the bug
  report at all; the diagnosis proved combat state was byte-identical across
  the submission, and the real cause was refusals being silently swallowed.

Give each diagnosis agent your hypothesis *and* explicit permission to reject
it: "If the evidence does not support the hypothesis above, say so — do not
force the diagnosis to fit it." An agent that disproves your framing has done
better work than one that confirms it, and you want it to feel free to.

Ask every diagnosis agent for: the root cause with `file:line` evidence,
whether it is still live on the current default branch, a concrete minimal fix,
and which existing tests cover the area. That last one matters — a passing test
over the broken behaviour tells you the test is wrong too.

## Step 3 — Fix with worktree-isolated agents

Dispatch implementation agents with `isolation: "worktree"` so parallel work
cannot collide. Give each one:

- The diagnosis as established fact, plus **permission to disagree with it** —
  "verify its findings rather than trusting them blindly."
- The specific fix shape, and the traps around it.
- The verification commands, and which failures are pre-existing rather than
  theirs.
- Instructions **not to push**. You merge and push centrally so the branch
  stays coherent.

Agents given room to disagree produce better fixes than agents given orders.
One implementing a fatigue heuristic realised the specified condition would
misfire — it conflated "priced out by fatigue" with "out of range" — and
plumbed a new signal through to distinguish them. The prescribed fix would have
told players to rest when they should have closed distance.

## Step 4 — Every regression test must be revert-proven

This is not optional, and it is not satisfied by a green suite. For each fix:

```bash
git stash push -u -m "proof-$$" -- <source files only>   # or: git checkout <base> -- <files>
# confirm the revert actually happened — verify, don't assume
grep -c "<the new symbol>" <file>
python -m pytest <the new tests> -q      # MUST fail here
# restore, then confirm green again
```

Verify the revert took effect before trusting the result. A `git stash push`
with path arguments can silently no-op, and a test suite that passes because
nothing was reverted looks exactly like a test suite that passes because the
test is worthless. Checking that the symbol is gone takes one command and
distinguishes the two.

Ask for negative controls too. A test that passes both before *and* after the
fix is not necessarily bad — it may be guarding against over-fixing — but you
should know which of your tests are which.

## Step 5 — Route the review by diff size, from the main session

Per CLAUDE.md's Code Review Gate: ≤1000 changed lines goes to `/code-review`;
above that goes to `/code-scrubber`.

**Dispatch the scrubber's dimension agents from the main session.** A dispatched
agent cannot spawn its own subagents in this environment, so a scrubber handed
to a background agent silently degrades into one generalist wearing five hats.
The grades it reports will look identical to a real fanout and mean much less.

This matters most on exactly the changes you least want under-reviewed. A
self-reviewed auth migration passed its own single-pass review while leaking the
session credential back to page JavaScript in a socket ack, wrapping logout in
an auth guard that stranded expired browsers, and disarming its own auth fuzzer.
The fanout found all three; the single pass had found none of them.

Run the adversarial challenge pass. It exists to stop you making needless risky
edits, and it earns its keep — it will reject some of your own proposed fixes
with evidence, and it will catch reviewers overstating a finding. Verify any
factual dispute between two reviewers yourself before acting on either.

## Step 6 — Batch the decisions into one question

Collect every genuine decision and ask them together via `AskUserQuestion`, at
the point where you have enough context to frame real options. For each: state
the situation concretely, give 2–4 options with their actual trade-offs, and
mark a recommendation when you have one.

Ask about a decision when the options lead to materially different work and you
cannot pick from the repo or the issue. Do not ask about things with an obvious
default — pick it, say you did, and move on.

Some fixes are risky enough to deserve the user's call even when the diagnosis
is certain: anything that can log every player out, change an auth flow, alter
persisted data, or shift gameplay balance. Bring those the specific patch, not
a vague concern.

## Step 7 — Land it, then keep it landed

Merge each verified worktree branch into the triage branch, re-run the full
gates on the *combined* state (fixes that pass alone can conflict), then push.

Then open the PR against the **actual** remote default branch. Fetch first —
a stale local `master` will make the diff look enormous and claim other
people's work as yours. Confirm the merge is clean, and check for a PR template
before writing the body.

After opening, subscribe to PR activity and drive it to green. Schedule a
check-in, because webhooks deliver CI *failures* reliably but not successes.
Widen the interval as the PR goes quiet — hourly polling of a static, green PR
waiting on human review just burns budget. Stop the check-ins when it merges.

Two API notes that will otherwise mislead you: `get_status` reads the legacy
commit-status API and returns `"pending"` with zero statuses on repos that use
check runs — use `get_check_runs` and the PR's `mergeable_state`. And an
unchanged `updated_at` plus comment count is enough to prove nothing happened,
without re-querying everything.

## Working under interruption

Long triage passes get killed mid-flight — spend limits, session limits. Plan
for it rather than being surprised by it:

- Tell every implementation agent to **commit working state before it stops**
  if it runs low on budget or context. The difference between a clean handoff
  and hours of uncommitted work in an abandoned worktree is one sentence in the
  prompt.
- Worktrees survive the agents that made them. On resume, check
  `git worktree list` and each worktree's `git status` before assuming anything
  was lost.
- When re-dispatching, make **"assess and commit what you inherit"** the first
  instruction, and carry the established diagnosis forward so the new agent
  does not re-derive it.

## Reporting

Report what is verified, distinctly from what is claimed. Name the tests that
prove each fix, and say plainly which failures are pre-existing — confirm that
against the base branch rather than asserting it.

Surface the things the user could not have known to ask about: a diagnosis that
contradicted the issue's own title, a defect found in your own earlier fix, a
test suite that was passing vacuously. Those are the findings with the longest
shelf life, and they are worth a follow-up issue when they fall outside the
current scope.

If you made a mistake and caught it, say so once, plainly, and move on.
