# Hardening the review skills against F.L.A.W.E.D. patches

**Status:** proposed, not implemented.
**Source:** 1Password / Off-by-1 Labs, *Frontier Models' Vulnerability Patches are
Often F.L.A.W.E.D.* (Aug 2026). The PDF host is blocked by this environment's
egress proxy; findings below were reconstructed from the search index and
secondary coverage (Help Net Security, Dark Reading, Security Boulevard,
1Password's own blog). **Re-verify the numbers against the PDF before quoting
them anywhere outside this repo.**

## The findings this plan is built on

6,080 patches, two frontier reasoning models, six recently-disclosed CVEs in
open-source software. F.L.A.W.E.D. = "Fix-Like Artifacts with Embedded Defects".

| Finding | Number | What it means for a review skill |
|---|---|---|
| Fully fixed, no behaviour change | 26.0% | The success case is the minority case |
| Fixed **but changed application behaviour** | 20.1% | A vulnerability-only test never catches this |
| Failed to fix, added a new flaw, or both | 53.9% | The modal outcome is a bad patch |
| "Successful" patches that were **fragile** | >33% | Blocked the PoC input or gated one caller; vulnerable core still reachable |
| Fix rate with *correct* guidance | 65.0% | Good context helps |
| Fix rate with *no* guidance | 50.4% | — |
| Fix rate with *incorrect* guidance | **15.2%** | **Wrong context is far worse than no context** |
| Conditions safe to trust unsupervised | none | Model self-assessment does not track correctness |

Three mechanisms follow from this, and every change below is one of them:

- **M1 — Behaviour regression is a separate gate from "the suite is green."**
- **M2 — A fix must address the root cause, not the reproduction input.**
- **M3 — Injected context is a liability unless verified; stale guidance is
  worse than no guidance.**

## Which skills this applies to

Audited every skill in `.claude/skills/` plus the agent definitions in
`.claude/agents/`.

### In scope — these produce or bless patches

| Skill / file | Relevance | Why |
|---|---|---|
| `code-scrubber` | **High** | Applies fixes itself (Step 4). Closes findings on a green suite. Carries hard-coded project security claims. |
| `code-review` | **High** | Handles every diff ≤1000 lines, i.e. most real fixes. Its Security section finds vulnerabilities but has no rubric for validating a *remediation*. |
| `issue-triage` | **High** | The skill that actually generates patches in bulk. Already the strongest on M2-adjacent discipline (Step 4 revert-proof) and has nothing for M1 or M3. |
| `devops-review` | **Medium** | Phase 8/9 "Suggest Fixes / Fix & Verify Loop" applies config, pipeline, secrets and dependency changes — the same failure modes, on a blast radius that includes production. |
| `.claude/agents/code-scrubber-security.md` | **High** | Hunts vulnerabilities; no fragility rubric. Carries an M3 hazard (below). |
| `.claude/agents/code-scrubber-adversary-security.md` | **High** | Can *downgrade* real findings by citing mitigations it never read. Prime M3 surface. |
| `.claude/agents/code-scrubber-alignment-correctness.md` | **Medium** | Owns Correctness; the natural home for "did this patch change observable behaviour?" |
| `_shared/review_rules/` | **High** | Rules-as-code home for the new constants; both skills already import from here. |
| `CLAUDE.md` | **High** | Verification Ladder and Code Review Gate are where the policy belongs. Best leverage per line changed. |

### Adjacent — referenced, not rewritten

- **`combat-test`** — it is the *instrument* an M1 behaviour-regression check
  would call for engine changes (rung 3 of the Verification Ladder). It needs no
  paper-derived rules of its own; the other skills need to know it exists for
  this purpose.
- **`orchestrate-qa-testers`** — already does the adversarial-confirm pattern
  ("the orchestrator verifies contested findings on a clean client"). The one
  gap worth a sentence: it verifies *findings*, not *fixes*. A fix that
  resolves a QA finding while changing behaviour elsewhere is exactly the 20.1%.

### Out of scope — checked and ruled out

`mockup`, `narrative-review`, `music-designer`, `sound-designer`. None produces
or validates a security patch. The paper says nothing about them.

### Vendored (gstack) — flag, do not edit

`security-review`, `cso`, `investigate`, `qa`, `review`, `ship`, `simplify` all
have the same exposure, and several are worse (`/simplify` applies fixes with no
security dimension at all; `/ship` gates a merge). They are upstream files that
`/gstack-upgrade` will overwrite. The project-local answer is CLAUDE.md's Code
Review Gate, which already routes to `/code-review` regardless of which skill
found the problem — reinforce that rather than patching vendored files.

## An M3 hazard already present in the tree

This is not hypothetical, and it is the strongest argument for the whole plan.

`.claude/agents/code-scrubber-security.md` tells the security reviewer:

> this codebase's own save/load path is deliberately hardened via
> `src/secure_pickle.py` (`SafeUnpickler`, allow-lists, strict mode)

and `.claude/agents/code-scrubber-adversary-security.md` gives the adversary a
ready-made downgrade justification:

> `src/secure_pickle.py`'s `SafeUnpickler` already enforces the allow-list for
> this deserialization path

But CLAUDE.md states the allow-list **only enforces under
`HOV_STRICT_UNPICKLE`, which nothing sets**. So the adversary can downgrade a
genuine deserialization finding by citing a control that is switched off. That
is the 15.2% condition, hand-written into an agent definition. Fixing it is
Phase 1.

## The plan

Six phases. Phases 1–3 are the substance; 4–6 are propagation. Each phase is
independently shippable and leaves the suite green.

### Phase 0 — Verify the source (blocking, cheap)

Retrieve the PDF from an unblocked network and confirm the eight numbers in the
table above, particularly the 20.1% / 33% / 15.2% figures. Everything below is
structural and survives small numeric corrections, but the doc should not cite
second-hand statistics as fact. If a number is wrong, correct this file; do not
correct it silently in the skill files.

### Phase 1 — Audit and re-state injected context (M3)

Highest value, lowest risk, no new machinery.

1. **Audit every hard-coded project claim** in the two security agent files and
   in `code-review`'s Security section (SKILL.md:110) and Security Review
   checklist (SKILL.md:167–179) against current source. For each claim, either:
   - restate it **with its precondition** — e.g. "`SafeUnpickler` enforces its
     allow-list *only when `HOV_STRICT_UNPICKLE` is set, which nothing in this
     repo sets* — treat an unset-strict-mode deserialization path as unmitigated"; or
   - delete it if it no longer holds.
2. **Require read-backed citations before any downgrade.** In
   `code-scrubber-adversary-security.md`, change criterion 2 ("Mitigated
   elsewhere … Cite the mitigating component explicitly") to require a
   `file:line` the adversary **`Read` during this run**, plus a one-line quote.
   The agent has `Read`/`Grep` and currently is not obliged to use them. Same
   treatment for criterion 1 ("threat not reachable") — reachability is a claim
   about call sites and should cite them.
3. **Mark `GOAL_CONTEXT` as unverified input.** In
   `code-scrubber-alignment-correctness.md`, add: a PR body or commit message is
   the *author's* claim about intent, not a specification. Where the diff
   contradicts the stated intent, the finding is "intent and diff disagree" —
   file it, do not resolve it by assuming either side is right.
4. **Add a standing instruction to all three security-touching agents:** if a
   claim in this prompt about the codebase cannot be confirmed in source, say so
   in `NOTES` and review as though the claim were absent. This is the general
   defence against the 15.2% condition — it makes stale guidance degrade to the
   50.4% case instead of the 15.2% one.

*Files:* `.claude/agents/code-scrubber-security.md`,
`.claude/agents/code-scrubber-adversary-security.md`,
`.claude/agents/code-scrubber-alignment-correctness.md`,
`.claude/skills/code-review/SKILL.md`.

### Phase 2 — Rules-as-code for patch outcomes (M1 + M2 foundation)

New shared module so `code-scrubber`, `code-review`, `issue-triage` and
`devops-review` all speak one vocabulary, following the existing pattern where
`code_scrubber_rules.py` imports from `code_review_rules.py`.

**New:** `.claude/skills/_shared/review_rules/patch_validation.py`

```python
PATCH_OUTCOMES = [
    "fixed",                  # root cause addressed, no behaviour change
    "fixed-behaviour-changed",# resolved but observable behaviour moved
    "fixed-fragile",          # unexploitable now, root cause still reachable
    "not-fixed",
    "regressed",              # introduced a new defect (with or without a fix)
]

FRAGILE_BLOCKS_A_GRADE = True          # a fragile fix is not a closed finding
BEHAVIOUR_CHANGE_REQUIRES_CONFIRMATION = True
SECURITY_FIX_ALWAYS_CONFIRMS = True    # Critical/Major Security -> AskUserQuestion regardless of confidence
SECURITY_SEVERITIES_REQUIRING_CONFIRMATION = frozenset({"Critical", "Major"})

def outcome_blocks_closure(outcome: str) -> bool: ...
def fix_requires_user_confirmation(dimension, severity, changes_behaviour, confidence) -> tuple[bool, str]: ...
```

Rationale for `SECURITY_FIX_ALWAYS_CONFIRMS`: the scrubber currently escalates
only below ~80% confidence or on behaviour change. The paper's finding is that
model confidence does not track patch correctness on security work, so
confidence is the wrong gate for this dimension.

**Tests:** extend `test_code_scrubber_rules.py` (or add
`test_patch_validation.py` beside it) per the module header's own contract:
value, test and SKILL.md change together, then
`python -m pytest .claude/skills/_shared/review_rules/ -v`.

This phase is test-first per CLAUDE.md's TDD rule — the rules module is
importable Python with real behaviour, not config.

### Phase 3 — The two new gates in `code-scrubber`

**3a. Extend Step 4.25 with "Prove the Fix" (M2).**

Step 4.25 is already the best-written section in the skill and already names the
exact failure the paper found — *fail-open scope*: "the guard scopes itself to
one function, so a second call site satisfies it while the site that matters
goes uncovered." It aims that lens at *test guards* only. The paper found the
same shape in the *patches*. Add a sibling subsection:

- Before closing a Security finding, `Grep` every call site and every entry path
  to the vulnerable symbol; state in the report which are covered by the fix.
- A fix applied at one caller while the vulnerable function remains publicly
  callable is `fixed-fragile`, not closed.
- Name the two shapes explicitly, in the style the section already uses:
  **input-filter fix** (blocks the reproduction string, root cause untouched —
  alternative inputs resurface the bug) and **caller-gated fix** (the exploit
  path is guarded, the vulnerable core is not).

**3b. New Step 4.5 — Prove the Behaviour (M1).**

Placed after 4.25 so guard-proof and behaviour-proof read as a pair.

- For any fix touching engine semantics (combat math, save format, story flags,
  serializer output), capture a concrete before/after on real input and diff it.
  Green tests are not evidence of unchanged behaviour when coverage is thin.
- Point at the instruments that already exist rather than inventing one:
  `python tools/bug_hunt.py --scenario …` (Verification Ladder rung 2) and
  `/combat-test` (rung 3). The Ladder already says balance or behaviour changes
  need rung 2 or 3 — this makes it binding for *fixes the reviewer itself applies*,
  which is the gap.
- A behaviour delta the reviewer cannot explain is `fixed-behaviour-changed`
  and routes to `AskUserQuestion`.

**3c. Report the outcomes (Step 6).**

Replace the flat `Fixes applied: <count>` with the five-way classification, and
add:

```
Security fixes applied:  <N>  (<M> with an executed reproduction)
Fragile fixes (root cause still reachable): <count>
Behaviour deltas observed: <count>  (<count> confirmed with the user)
```

The skill already forbids fabricating test results and already refuses to count
an unproven guard toward an A. Both rules extend to fixes verbatim: **a security
finding is not closed on reasoning alone.**

**3d. Fix the stale docstring.** `chunk_requires_confirmation` in
`code_scrubber_rules.py` says the skill "runs as a background-dispatched Agent …
which cannot pause to ask the user," contradicting SKILL.md v2.0.0's "the main
session orchestrates … it **can** ask the user." Left over from the pre-2.0
design; it will mislead anyone implementing the new confirmation gates.

*Files:* `.claude/skills/code-scrubber/SKILL.md` (Steps 4, 4.25, 4.5, 6 and the
Constraints block), `_shared/review_rules/code_scrubber_rules.py`.

### Phase 4 — Port the gates to `code-review`

`/code-review` handles every diff at or under 1000 lines, so it sees most real
fixes. It currently has a strong vulnerability-*finding* checklist and nothing
about validating a *remediation*.

1. Add a **Security Fix Validation** block to the Security Review checklist
   (after SKILL.md:171): root cause vs. reproduction input; all call sites
   enumerated; fragility explicitly judged.
2. Add behaviour-regression to the Testing Review checklist: for a fix, does a
   test exist that would fail if behaviour moved — not just one that fails
   without the fix? This complements the existing revert-proof rule rather than
   replacing it.
3. Adopt `SECURITY_FIX_ALWAYS_CONFIRMS` from Phase 2 in the Rules section: a
   Critical/Major Security finding is never resolved by the reviewer's own
   judgement without asking. The skill already has `AskUserQuestion` in
   `allowed-tools`.
4. Extend the confidence filter with one sentence: the 0–100 score measures
   confidence that a *finding* is real. It is not a measure of confidence that a
   *fix* is correct, and must not be reused as one.

### Phase 5 — `issue-triage` and `devops-review`

**`issue-triage`** already implements the revert-proof discipline better than
anything else in the tree (Step 4, lines 163–200) and explicitly cross-references
Step 4.25. Two additions:

- **Step 4 gains a behaviour half.** The current proof shows the test fails
  without the fix. Add: show that nothing *else* moved — for engine fixes, a
  `bug_hunt` scenario or `/combat-test` run before and after. This is the 20.1%,
  and a batch triage pass is where it compounds across issues.
- **Root-cause vs. symptom for security-labelled issues.** The skill already
  demands "the root cause with `file:line` evidence" from diagnosis agents; make
  the *fix* answer to the same standard, with the fragility test from Phase 3a.

**`devops-review`** Phase 9's Fix & Verify Loop:

- A dependency bump or config change that makes a scanner go quiet is the
  infrastructure form of an input-filter fix. Require the finding's *mechanism*
  to be re-tested, not the scanner's verdict re-read.
- Phase 9 step 3 ("If config/secrets: verify in test environment first") is
  already halfway to M1 — extend it to name the behaviour that must be unchanged.

### Phase 6 — CLAUDE.md

The policy home. Three small edits, highest leverage in the plan:

1. **Verification Ladder** — add a line: for *fixes*, pick the rung that can
   observe the regression the fix might cause, not just the rung that observes
   the fix. The Ladder's existing "Balance or behaviour changes need rung 2 or 3"
   currently reads as advice to feature authors; it applies to reviewers applying
   fixes too.
2. **Code Review Gate** — record that a Critical/Major Security finding is never
   closed on model judgement alone, and that a fragile fix does not close a
   finding. The Gate section is already where the scrubber's architecture-pass
   gap is documented, so it is the established place for review-surface caveats.
3. **TDD section** — the review-gate carve-out ("fixes applied by `/code-review`
   or `/code-scrubber` to land a finding don't need a preceding failing test")
   is exactly the exemption the paper argues against for security fixes. Narrow
   it: the carve-out stands for style dimensions; a Security fix needs the
   reproduction, before and after.

## Verification for this work

Meta-level, but the plan should hold itself to its own standard:

- `python -m pytest .claude/skills/_shared/review_rules/ -v` — the rules modules
  are tested code and Phase 2 is test-first.
- `python -m pytest -q` — full backend suite green after each phase.
- **Dogfood:** run `/code-review` over the Phase 1–2 diff. If the updated
  Security section does not change how the review of its own diff reads, the
  wording is decorative.
- **Negative control:** construct a deliberately fragile patch (guard the
  caller, leave the vulnerable function public) and confirm the updated
  `code-scrubber-security` agent classifies it `fixed-fragile`. A rubric that
  passes a known-bad patch has the same problem as a guard that matches nothing.

## Sequencing and effort

| Phase | Effort | Risk | Depends on |
|---|---|---|---|
| 0 — verify source | 10 min | none | unblocked network |
| 1 — context audit | ~1h | low; prose only | — |
| 2 — rules-as-code | ~1h | low; new module + tests | — |
| 3 — scrubber gates | ~2h | medium; changes closure criteria | 2 |
| 4 — code-review | ~1h | medium; same | 2 |
| 5 — triage + devops | ~1h | low | 3, 4 |
| 6 — CLAUDE.md | ~30 min | low | 3, 4 |

Phases 1 and 2 are independent and can land together. Phase 1 alone fixes a live
defect and is worth shipping even if nothing else proceeds.

## Decisions for the maintainer

1. **`SECURITY_FIX_ALWAYS_CONFIRMS`** — routing every Critical/Major Security fix
   through `AskUserQuestion` makes an unattended scrub impossible on a diff with
   real security findings. That is arguably the paper's point, but it is a
   workflow cost. Alternative: allow auto-apply but mark the fix
   `applied-unconfirmed` in the report and refuse to grade Security an A.
2. **Does a fragile fix block an A?** The plan says yes, mirroring the existing
   unproven-guard rule. The looser option is a `[fragile]` tag that reports but
   does not block, matching how `[advisory]` findings behave today.
3. **Scope of behaviour-proof.** "Engine semantics" needs a concrete boundary.
   Proposal: `src/moves/`, `src/combatant.py`, `src/api/combat_adapter.py`,
   `src/save_format.py`, `src/story/` — the same hot-path list `/code-review`
   already uses for weighting Optimization.
4. **Vendored gstack skills.** Leave them, or maintain a project-local overlay
   documenting their exposure? Leaving them means `/simplify` and `/ship` keep
   applying and blessing changes with no security dimension.
