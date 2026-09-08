---
name: issue-triage
version: 1.3.0
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
  the maintainer's call, diagnoses before fixing, fixes test-first and
  revert-proves each fix, routes the result through the size-appropriate review
  gate, and returns the genuine decisions as one batched question instead of
  guessing.
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
gh issue list --state open --limit 100 --json number,title,body,comments
gh issue view <N> --json number,title,body,comments,labels,state
```

Use whichever GitHub surface is actually connected, and check rather than
assume: the `mcp__github__*` server frequently fails to connect in this
environment (`Incompatible auth server: does not support dynamic client
registration`), while the `gh` CLI is installed and pre-approved read-only for
this repo. An earlier version of this skill asserted the opposite — that there
was no `gh` CLI — which was wrong and would have blocked the whole pass.

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

**A comment is not the code it sits above.** A wire-contract note claiming the
server sends `int(player.heat * 100)` was relayed into three further documents
before anyone opened the serializer, which does `round(...)`. Comments drift and
nothing fails when they do, so treat every one you plan to repeat — in a fix, a
docstring, a report — as a claim to check against the line it describes. The
same goes for a stale `file:line` citation: verify it still points at what it
names before carrying it forward.

## Step 3 — Fix test-first, with worktree-isolated agents

**Every fix is test-first.** CLAUDE.md requires TDD for `src/`, `ai/` and
`frontend/src/`, and a triage pass is where it is most tempting to skip: you
already know the fix, so writing the test afterwards feels like the same work in
a different order. It is not. Put the red step in each agent's brief explicitly:

1. **Red** — write the test that reproduces the defect, run it, and confirm it
   fails *for the reason the issue describes* — not on an import error, a typo,
   or an unrelated crash. Have the agent paste that failure into its report.
2. **Green** — the smallest change that makes it pass, and nothing else.
3. **Refactor** — with the suite green throughout, re-running as you go.

Done in that order the red step **is** Step 4's revert-proof: you have already
watched the test fail without the fix and you have the message to show for it.
Step 4 is for tests that arrived any other way.

Test-first does not apply to documentation, comment-only or config-only edits,
generated and vendored files, or scratch scripts outside those three trees. It
does apply to everything else, including the one-liner you are certain about.

Dispatch implementation agents with `isolation: "worktree"` so parallel work
cannot collide. Give each one:

- The diagnosis as established fact, plus **permission to disagree with it** —
  "verify its findings rather than trusting them blindly."
- The red-green-refactor sequence above, with the failing run required in its
  report — an agent that reports only a green suite has not shown you anything.
- The specific fix shape, and the traps around it.
- The verification commands, and which failures are pre-existing rather than
  theirs.
- Instructions **not to push**. You merge and push centrally so the branch
  stays coherent.
- The commit-message convention: cite the issue for traceability
  (`fix(scope): … (#NNN)`), but tell the agent plainly that this form closes
  nothing. Closing references are yours to write in the PR body and to verify
  after the merge — see Step 7.

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

`/code-scrubber`'s Step 4.25, *Prove the Guard*, is the long form of this and is
worth reading whole before writing a regression test. Three of its rules earn
their place in triage specifically:

- **Derive the expectation from an independent authority.** A test that
  hand-lists what the code hand-lists is one opinion written twice, and it agrees
  with itself forever. Read the expectation from the thing that owns it — the
  engine constant, the registry, the shared JSON, an AST walk. This is the same
  failure as a mock agreeing with a mock, which CLAUDE.md names as this
  codebase's dominant bug class.
- **Prove the derived population is non-empty.** A scan that matches nothing
  approves of everything, and a guard that has stopped matching reads exactly
  like a guard that passes.
- **Watch for fail-open scope.** A guard that greps a whole *file* is satisfied
  by any line in it. The contract test written to stop false player-facing copy
  searched the whole of `_movement.py` for a substring that `Advance` satisfies,
  so it passed while the sentence it guarded was wrong about `Withdraw` — and
  four more of its tests could not have failed for the reason their names gave.

When a guard has gone quiet, **fix the guard; never narrow the assertion to match
the new reality.** Narrowing is how a guard retires without anyone deciding to
retire it, and it is a finding worth reporting rather than a chore.

## Step 5 — Route the review by diff size, from the main session

Per CLAUDE.md's Code Review Gate: ≤1000 changed lines goes to `/code-review`;
above that goes to `/code-scrubber`. Measure before you route — `git diff --stat`
against the merge base — and route the **combined** triage branch rather than
each fix as it lands, because the combined state is what ships. The threshold is
`DIFF_REDIRECT_THRESHOLD` in
`.claude/skills/_shared/review_rules/code_review_rules.py`; read it there rather
than trusting this sentence.

**The scrubber does not review Architecture.** Its seventh dimension is
Alignment — `SCRUBBER_DIMENSION_ADDITIONS = ["Alignment"]` in
`code_scrubber_rules.py` — while Architecture (gating) and Correctness are
`/code-review`'s additions. So the diffs big enough to need the scrubber are
exactly the ones that get no architecture pass from the skill reviewing them.
After a scrub, run `/code-review` over the architecture-touching subset —
anything in `src/api/`, `GameService`, the serializers, a new move or passive —
before calling the gate closed. Not bookkeeping: the `player.attack` error
survived three correction rounds because the review surface itself carried it.

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

Two further things the scrubber's own design tells you. **Cross-chunk patterns**
— the same anti-pattern in four files, one config value scattered across three —
are structurally invisible to per-chunk review, so its aggregate pass is the only
place they surface; don't skip it because every chunk came back A. And the
**iteration cap is three per chunk**: a chunk still short of A after three rounds
is escalated and reported, not ground on.

**Audit the chunk set against the branch diff before you call the review done.**
Chunking is derived from your own list of what changed, so a file you forgot to
list is never reviewed and nothing anywhere says so — the run reports full
grades over a partial diff. Diff the branch against the merge base, take the set
difference against the files actually chunked, and review what falls out. Doing
that twice on one pass surfaced four unchunked files plus an entire rename,
and three of the real defects that pass found came out of them.

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

The scrubber's threshold is the right one to borrow, and it is lower than it
feels: a fix that could change observable behaviour, a public API, persisted data
or business logic — **or that you are below roughly 80% confident in** — goes to
the user with the patch attached rather than into the branch. Where you genuinely
cannot ask, take the conservative default (don't apply it) and report it as
deferred, with the finding, the `file:line`, and the patch in prose.

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

**A job can fail with every one of its tests green.** `Frontend (vitest)` came
back red on 2,832 passed / 0 failed: seven unhandled rejections after teardown
(`ReferenceError: window is not defined`) took the process to exit 1. Read the
job's conclusion and its `##[error]` lines, never the "N passed" summary — a
run that is green in the middle and red at the end reads as a pass to anyone
skimming. That failure was also invisible locally, where the suite is not under
load, so reproduce the *mechanism* rather than waiting to see the symptom
again: the dangling promise was a live XHR from a hook the test never mocked.

Two API notes that will otherwise mislead you: `get_status` reads the legacy
commit-status API and returns `"pending"` with zero statuses on repos that use
check runs — use `get_check_runs` and the PR's `mergeable_state`. And an
unchanged `updated_at` plus comment count is enough to prove nothing happened,
without re-querying everything.

### A Conventional Commits subject is not a closing reference

GitHub closes an issue on merge only when a closing keyword — `close`,
`closes`, `closed`, `fix`, `fixes`, `fixed`, `resolve`, `resolves`, `resolved`
— is followed by nothing but optional whitespace or a colon before the `#NNN`.
**Every form this project's commit convention naturally produces fails that
test**, because the scope parenthesis or the trailing citation puts a character
where the parser demands none:

| Form | Why it does not close |
|---|---|
| `fix(#544): stop reporting dormant tile events` | the `(` sits between keyword and number |
| `fix(combat-ui): hit-testable STRIKE button (#535)` | `fix` binds to the scope; `#535` is unattached |
| `Fix room-description clipping (issue #537)` | `Fix` binds to "room-description"; `issue` is not a keyword |
| `- #528 — exits bleed across maps` (PR body bullet) | no keyword at all |

PR #549 merged fixes for 19 issues and closed exactly **one**: #546, whose
commit happened to read `Fix #546: always_stock items now bypass container
placement`. The other 18 stayed open until a follow-up session closed them by hand.

`closingIssuesReferences` is not the safety net it looks like, in either
direction: a commit-message close never populates it, so on #549 it came back
empty even though #546 did close. Empty does not mean "nothing will close", and
non-empty does not cover commit-only references.

So do both of these, and trust only the second:

1. **Put real closing keywords in the PR body, one per line, in their own
   section.** Not woven into the summary bullets — a `Closes #528 — exits bleed
   across maps` reads fine to a human and parses fine too, but the moment
   someone reformats the bullet the reference dies silently. Keep them
   mechanical and separate:

   ```
   ## Closes

   Closes #528
   Closes #529
   Closes #530
   ```

2. **Verify against the API, before and after the merge.** Before merging,
   confirm the parser actually bound every issue you intend to close:

   ```bash
   gh pr view <N> --json closingIssuesReferences \
     -q '.closingIssuesReferences[].number'   # must match your intended list
   ```

   After merging, check every issue the PR claimed — including any referenced
   only from a commit message, which the field above will never show:

   ```bash
   for n in <every issue the PR touched>; do
     gh issue view $n --json number,state,stateReason \
       -q '"#\(.number)\t\(.state)\t\(.stateReason // "-")"'
   done
   ```

   Close whatever is still open yourself, with a comment naming the commits
   that fixed it — the audit trail is the point, since the commits no longer
   carry the link:

   ```bash
   gh issue comment $n --body-file <comment>.md
   gh issue close $n --reason completed
   ```

   Use `--reason "not planned"` for an issue the pass investigated and found to
   be a non-bug, and say in the comment what was traced and why the reported
   symptom occurred. Leave genuinely deferred issues open.

**Re-read the PR body immediately before merging.** #549's "Deferred" section
told the maintainer that #526 and #547's config half still needed a decision,
when both had already landed on the branch by merge time — #526 in `c08a1c74`,
the config as a tracked `config_grondia_beta.ini`. A body written mid-pass goes
stale as the pass continues, and a stale deferral is worse than no deferral: it
asks the maintainer to decide something already decided, and it argues against
closing an issue that is fixed. Diff the body's claims against `git log` on the
branch tip before you merge.

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

## Measure it before you say it

Every wrong statement in the last pass came from a shortcut in how something was
counted or searched, not from a wrong belief about the code. The shortcuts are
worth knowing by name, because each one produces a confident, plausible number.

- **`grep "failed"` matches `xfailed`.** A loop counting failures across ten
  random-order runs reported ten runs with failures; all ten had passed. Count
  process **exit codes**, not words in the output — pytest, vitest and npm all
  tell you the truth in `$?` and lie to a careless regex.
- **Grep searches contents, not filenames.** A test file was reported as
  nonexistent because the search was for its name *inside* files. Use `ls` or
  `find` to answer "does this file exist", and note that a reviewer asserting
  the same absence at "97% confidence" is not a second source — it is one
  unverified claim, and confirming it with the same flawed method confirms
  nothing.
- **Take the set difference before quoting a gap.** "104 found, 5 missed" was
  quoted from two counts that were never subtracted; exactly one item was
  actually exclusive, so the gap was overstated fivefold. If you are about to
  name a number of missed things, produce the list of them first.

None of these need a second tool call to avoid — they need the *right* one.
When a number is going into a report, a commit message or a PR body, spend the
one command that makes it checkable.

## Reporting

Report what is verified, distinctly from what is claimed. Name the tests that
prove each fix, and say plainly which failures are pre-existing — confirm that
against the base branch rather than asserting it.

**Never report a test result, a grade, or a count you did not produce.** If you
did not run it, say you did not run it; if a suite was still running when you
wrote the summary, say that instead of predicting how it ends. A fabricated green
is worse than a missing one, because it is acted on.

**A merged PR is not a closed issue.** The pass is not done until you have
re-queried the state of every issue it touched and reported the actual
`state`/`stateReason` per issue, not "the PR merged, so the issues are closed."
Report the closed set, the deliberately-open set, and the reason for each.

Surface the things the user could not have known to ask about: a diagnosis that
contradicted the issue's own title, a defect found in your own earlier fix, a
test suite that was passing vacuously. Those are the findings with the longest
shelf life, and they are worth a follow-up issue when they fall outside the
current scope.

If you made a mistake and caught it, say so once, plainly, and move on.
