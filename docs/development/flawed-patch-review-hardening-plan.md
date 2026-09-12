# Hardening the review skills against F.L.A.W.E.D. patches

**Status:** implemented (Phases 0-6, 2026-09-11). Follow-ups listed at the end remain open.
**Source:** Mierczuk, Michaels & Hoodlet, *Frontier Models' Vulnerability Patches
are Often F.L.A.W.E.D. — Fix-Like Artifacts With Embedded Defects*, Off-by-1
Labs / 1Password, 2026. 49pp. **Numbers below are read from the paper itself**
(an earlier revision of this doc used second-hand figures; three were wrong and
are corrected here).

## Methodology, in enough detail to judge the transfer

Two models with cyber guardrails — ChatGPT 5.5 (Trusted Access for Cyber,
"medium" effort) and Claude Opus 4.8 (Cyber Verification Program, "high"
effort) — against **six** high-impact, high-complexity CVEs disclosed between
2026-03-26 and 2026-05-12, chosen to postdate training data and to have
canonical upstream patches touching multiple files or paths. **6,080** non-cheat
classified iterations. Three harness modes (one-shot, iterative with a
reproducer loop, exploratory) x nine prompt templates varying *richness* (six
ordinal knobs, R=0..21) and, orthogonally, *fix-guidance correctness*
(correct / wrong / none). Each patch was graded by its own model and
cross-graded by the other; >=10% of every campaign was human-reviewed, which
exposed three systematic rubric errors and produced a corrected second-pass
validator.

Caveats the authors state and this plan inherits: the CVEs were deliberately
harder than average; grading is LLM-driven with human sampling, not an oracle;
and the second-pass validator matched human review on the exact grade only
**65.9%** of the time (87.7% on "was the bug fixed", 70.5% on "was a new bug
introduced").

## The numbers

Outcome scale — S1 clean fix; S2 fixed but application behaviour changed;
S3 not fixed, no new vuln; S4 fixed but introduced a new vuln; S5 not fixed
*and* introduced a new vuln.

| Metric | Claude | ChatGPT | Average |
|---|---|---|---|
| S1 — successful & clean | 25.6% | 26.5% | **26.0%** |
| S2 — fixed, behaviour changed | 15.1% | 25.2% | **20.1%** |
| S3 — not fixed | 55.2% | 43.5% | **49.3%** |
| S4 — fixed, new vuln | 1.4% | 3.3% | **2.3%** |
| S5 — not fixed, new vuln | 2.7% | 1.6% | **2.2%** |
| Fail-to-fix (S3+S5) | 57.9% | 45.1% | **51.5%** |
| New vuln (S4+S5) | 4.2% | 4.9% | **4.5%** |
| Cheat rate | 12.9% | 8.8% | **10.8%** |

| Fix guidance | Fix-success | New vuln | Fail-to-fix |
|---|---|---|---|
| Correct | 65.0% | 4.1% | 35.0% |
| **Incorrect** | **15.2%** | 5.2% | **84.8%** |
| Not provided | 50.4% | 3.6% | 49.6% |

**Fragility:** 37.5% of *successful* (S1+S2) patches carried the fragile flag —
1,010 of 2,694 (Claude 39.2%, ChatGPT 35.3%).

**Mode:** iterative 53.0% > exploratory 49.9% > one-shot 45.0% — under 10pp
spread. Richness: R0 51.8% -> R21 76.3%, but new-vuln rate *rises* slightly with
richness (~4% -> ~5%).

**Patch size by outcome:** S5 patches are the largest (88.6 added lines, 3.4
files) and S1 the second-smallest (69.3, 2.5). Bigger fix, worse outcome.

**Cross-validator disagreement:** 36.8% of paired iterations disagreed on the
S-grade for the *same* patch, and the direction is set by validator identity
rather than patch quality — ChatGPT-as-cross overturns Claude's "fixed" 17.3%
of the time vs 0.8% the other way; Claude-as-cross rescues ChatGPT's
"not fixed" 25.8% vs 0.3%.

### Corrections to the earlier revision of this doc

- "53.9% failed or regressed" -> S3+S4+S5 = **53.8%**, but the paper's own
  headline framings are fail-to-fix **51.5%** and new-vuln **4.5%**. Use those.
- ">33% fragile" -> **37.5%**.
- "two frontier reasoning models" -> named models and guardrail programmes, above.
- Missing entirely: the **10.8% cheat rate**, the **36.8% validator
  disagreement**, and the three systematic rubric errors. All three change the
  plan; see M4-M6.

## The six mechanisms

Each change below implements one of these.

- **M1 — Behaviour regression is a gate separate from "the suite is green."**
  20.1% of patches fixed the bug and moved behaviour. The paper's corrected
  rubric is precise and worth copying verbatim: a behaviour change is *new
  behaviour matching neither the pre- nor the post-fix intended behaviour*.
  Without that clause the gate fires on every intended change and becomes noise —
  this was one of the three errors human review caught in the authors' own
  validator.
- **M2 — A fix must address the root cause, not the reproduction input.**
  37.5% of successful patches were fragile. §7.3: agents patch the one path the
  PoC exercises and miss "character-for-character identical instances of the same
  bug in adjacent code paths." §9.3's proposed intervention is to force the agent
  to *enumerate all reachable paths to the exploitable primitive before proposing
  a change* — adopt that literally.
- **M3 — Injected context is a liability unless verified.** Wrong guidance
  costs ~50pp (65.0 -> 15.2, fail-to-fix 84.8%); correct guidance buys only
  ~15pp over silence. §4.1/§7.5: agents ran with prompt claims their *own tool
  calls had contradicted*. Corollary the paper draws and this plan adopts: when
  a claim cannot be verified, **omit it rather than assert it**.
- **M4 — A reviewer with egress can look the answer up instead of reasoning
  (new).** 10.8% of iterations cheated; 46.4% on Copy Fail for Claude. Both
  `code-scrubber-security` and `code-scrubber-adversary-security` hold
  `WebFetch`. A review that pattern-matches a CVE writeup instead of reading
  this codebase produces a verdict with no local evidence behind it.
- **M5 — A one-directional adversary cannot correct the error that matters
  (new).** Our adversary may only confirm, downgrade, or mark advisory — the
  minimum disposition is Advisory and it cannot escalate. The paper's data says
  the *productive* cross-validation direction is stricter ("fixed" -> "not
  fixed"), and that self-validators favour their own output. Our design
  structurally forbids the useful direction. It must be able to escalate.
- **M6 — Separate "pre-existing" from "introduced here" (new).** The authors'
  validator conflated unchanged-but-still-vulnerable code with newly-introduced
  bugs, misfiling S3 as S5. Their fix: a new bug is one *in code the patch added
  or directly modified*. Our finding taxonomy has no such axis, and the
  confidence filter's "false positive or pre-existing — ignore" bucket actively
  discards the distinction.

## What does not transfer

Stated so the plan is not over-read:

- The 26% figure is for **novel, multi-path, high-complexity CVEs in unfamiliar
  code**. A typical Heart of Virtue finding (a missing `TESTING` gate, a bare
  `getattr` on a player attribute) is nothing like that. The failure *shapes*
  transfer; the base rates do not, and this doc should not be cited as "our
  review skills fix 26% of things."
- §7.1's headline recommendation — measure your own model against your own
  codebase's historical fixes — is the honest way to get a local number. It is
  a real project (a FLAWED-style harness over closed HoV issues) and is out of
  scope here; noted under follow-ups.
- §7.2 raises a cost question this plan cannot answer: whether LLM patch +
  human review beats a human patch at all, given reviewers face "an avalanche of
  unnecessary code" and slide into **cognitive surrender**. That argues for
  fewer, better-evidenced findings — not more gates. It is the main
  counterweight to everything below and shapes Phase 3c's report design.

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

## Two live defects already in the tree

Neither is hypothetical, and the first is the strongest single argument for this
work.

### 1. The pickling guidance asserts a control that is switched off (M3)

`.claude/agents/code-scrubber-security.md` tells the security reviewer:

> this codebase's own save/load path is deliberately hardened via
> `src/secure_pickle.py` (`SafeUnpickler`, allow-lists, strict mode)

and `.claude/agents/code-scrubber-adversary-security.md` hands the adversary a
ready-made downgrade justification:

> `src/secure_pickle.py`'s `SafeUnpickler` already enforces the allow-list for
> this deserialization path

**What is actually true.** The hardening is real and substantial — 658 lines,
two strict gates in `find_class`, `RestrictedUnpicklingError`, an auto-derived
engine allow-list, a curated `LEGACY_ALLOWED_MISSING` set, manifest drift
guarding via `tools/gen_allowlist_manifest.py`, and a save fuzzer asserting zero
security-invariant breaches. `load_in_subprocess()` already defaults
`strict=True`. But the default in-process path resolves `strict=None` through
`strict_mode_enabled()` -> `HOV_STRICT_UNPICKLE`, and **nothing sets that
variable**; `.env.example:396` ships it commented out as
`# HOV_STRICT_UNPICKLE=0`, advertising the wrong posture. On a default load what
protects the process is the sha256 integrity header, the 5 MB size cap and
legacy-module rewriting — not the allow-list
(`.claude/rules/saves-persistence.md` states this plainly).

So the adversary can downgrade a genuine deserialization finding by citing a
control that is off. That is the 15.2% condition, hand-written into an agent
definition.

**Maintainer's decision (recorded 2026-09-11): strict mode is the intended
production posture, and review must not assume the legacy path carries into
prod.** This is a better rule than restating the precondition, because it makes
the guidance correct in the end-state rather than accurate about a temporary one.
Phase 1 therefore instructs the reviewers to treat strict mode as on and to flag
any new deserialization path that only holds with it off.

Turning the flag on is a code change with save-compatibility consequences and is
out of scope for this plan; it is filed under follow-ups. Fixing `.env.example`
to stop suggesting `0` is in scope for Phase 1 as a one-line change.

### 2. The adversary cannot escalate (M5)

`code-scrubber-adversary-security.md` states: *"You may NOT dismiss findings
outright. The minimum disposition is Advisory."* Its three permitted actions are
confirm, downgrade, and mark advisory. This was designed against false
positives, and it is one-directional by construction.

The paper measured cross-validation in both directions on the same 6,077 paired
patches, and the useful direction is the one we forbid: a cross-validator
overturning a self-validator's "fixed" to "not fixed" (17.3% of Claude's, vs
0.8% the other way). Self-validators favour their own verdicts; our adversary
reviews the same wave, from the same model tier, with no ability to say *this
finding understates the problem* or *this finding missed the adjacent call
site*. Phase 1b gives it that verb.


## The plan

Six phases. Phases 1–3 are the substance; 4–6 are propagation. Each phase is
independently shippable and leaves the suite green.

### Phase 0 — Verify the source — **DONE (2026-09-11)**

All 49 pages read; the numbers above are from the paper. Three figures in the
first revision were wrong, and three findings were missing entirely (M4-M6).
Nothing in the structural analysis was invalidated, but the plan grew two phases.

### Phase 1 — Fix the injected context (M3 + M4)

Highest value, lowest risk, no new machinery. Prose only.

1. **Pickling guidance, per the maintainer's decision.** In both security agent
   files, replace the "already hardened / already enforces" claims with: strict
   allow-list enforcement is the **intended production posture**; review every
   new or changed deserialization path as though `HOV_STRICT_UNPICKLE=1`, and
   **file a finding for any path that only holds with strict mode off**. A
   default-mode load is protected by the integrity header, size cap and legacy
   rewriting — not the allow-list — so "SafeUnpickler handles it" is not a
   downgrade justification. Same edit to `/code-review`'s Security red flags
   (SKILL.md:110) and Security Review checklist.
2. **Stop advertising the wrong default:** change `.env.example:396` from
   `# HOV_STRICT_UNPICKLE=0` to `# HOV_STRICT_UNPICKLE=1` with a comment naming
   it the intended posture.
3. **Require read-backed citations before any downgrade.** In
   `code-scrubber-adversary-security.md`, criteria 1 ("threat not reachable")
   and 2 ("mitigated elsewhere") must cite a `file:line` the adversary `Read`
   *during this run*, plus a one-line quote. It has `Read`/`Grep` and is
   currently not obliged to use them.
4. **Reconcile the packet against tool-call evidence (§7.5).** Add to all three
   security-touching agents: where a claim in your review packet is contradicted
   by what you read in source, **the source wins and the conflict is reported**.
   The paper's finding is that models optimise for obedience to the prompt "in
   spite of the conflicting evidence in front of it"; §9.3 proposes requiring
   reconciliation as an explicit harness step. This is that step.
5. **Where a claim cannot be verified, omit it.** The paper's own corollary
   (§7.4, §5.4): no guidance beats wrong guidance by ~35pp. Any project claim in
   an agent prompt that cannot be confirmed in source should be deleted, not
   softened.
6. **No looking it up (M4).** Both security agents hold `WebFetch`. Add: use it
   for standards and CWE/OWASP definitions, never to retrieve a fix for a
   specific CVE or advisory. A verdict must rest on code read in this worktree.
   Cite local evidence or say you have none.
7. **Mark `GOAL_CONTEXT` as unverified input.** In
   `code-scrubber-alignment-correctness.md`: a PR body or commit message is the
   author's *claim* about intent, not a specification. Where the diff
   contradicts it, the finding is "intent and diff disagree" — file it; do not
   resolve it by assuming either side.

*Files:* the three `.claude/agents/code-scrubber-{security,adversary-security,alignment-correctness}.md`,
`.claude/skills/code-review/SKILL.md`, `.env.example`.

### Phase 1b — Let the adversary escalate (M5)

A three-line change to `code-scrubber-adversary-security.md` with more effect
than anything else in the plan.

1. Add **ESCALATED** to the permitted dispositions, with its own criteria: the
   finding understates severity; it names one site where the population is
   wider; or the proposed fix would leave the primitive reachable. The paper's
   evidence is that the stricter direction is where cross-validation earns its
   keep.
2. Keep the existing floor (no outright dismissal) — this widens the range, it
   does not relax it.
3. Add the count to the `SUMMARY:` block and to the skill's Step 3 aggregation
   so an escalation cannot be silently dropped.
4. Note in the agent file *why* a same-tier adversary is weak at this: it shares
   the reviewer's priors. That is an argument for keeping the verb explicit and
   its criteria concrete, not for trusting the disposition blindly.

### Phase 2 — Rules-as-code for patch outcomes (M1, M2, M6)

One shared module, so `code-scrubber`, `code-review`, `issue-triage` and
`devops-review` share a vocabulary — following the existing pattern where
`code_scrubber_rules.py` imports from `code_review_rules.py`.

**New:** `.claude/skills/_shared/review_rules/patch_validation.py`, carrying the
paper's S1-S5 scale under local names, the fragile flag, the M6 provenance axis,
and the confirmation predicates. Test-first per CLAUDE.md's TDD rule — it is
importable Python with real behaviour, not config.

Note for anyone extending it: the module deliberately carries **no report-key
vocabulary**. A first draft defined one and pinned it with a test that asserted
the tuple equalled its own literal, which the dogfood review caught as the
"restating the thing it checks" shape from Step 4.25 — nothing consumed the keys,
so the guard could not fail for the reason it was written. Skill report templates
use prose labels; if that ever needs to be machine-readable, add the vocabulary
*and a consumer* together.

Two definitions must be copied from the paper's *corrected* rubric rather than
invented, because the authors' human review showed the naive versions
misclassify:

- **fixed** = resolved across *every* code path the finding covers, not merely
  the one the reproduction exercises. A partial fix can never grade clean.
- **behaviour change** = new behaviour matching **neither** the pre-fix nor the
  intended post-fix behaviour. Without the second clause the gate fires on every
  deliberate change and trains reviewers to ignore it.

- **provenance (M6)** = `pre-existing` / `introduced-by-this-diff`, tracked
  separately from severity. Also reword `/code-review`'s confidence-filter
  0-24 bucket, which currently reads "False positive or pre-existing. Ignore" —
  collapsing the two is exactly the S3-as-S5 error, run backwards.

Rationale for `SECURITY_FIX_ALWAYS_CONFIRMS`: the scrubber escalates below ~80%
confidence, but the paper's whole point is that model confidence does not track
patch correctness on security work, so confidence is the wrong gate here.

*Tests:* `test_patch_validation.py` beside the module, per the rules modules'
own header contract (value, test and SKILL.md change together).


### Phase 3 — The two new gates in `code-scrubber`

**3a. Extend Step 4.25 with "Prove the Fix" (M2).**

Step 4.25 is already the best-written section in the skill and already names the
exact failure the paper found — *fail-open scope*: "the guard scopes itself to
one function, so a second call site satisfies it while the site that matters
goes uncovered." It aims that lens at *test guards* only. The paper found the
same shape in the *patches*. Add a sibling subsection:

- **Enumerate before patching, not after.** §9.3 names this as the authors' own
  proposed intervention: *force the agent to enumerate all reachable paths to the
  exploitable primitive before proposing a change.* So the enumeration is an
  input to the fix, not a checkbox after it — `Grep` every call site and entry
  path to the vulnerable symbol first, list them, then patch against the list
  and state in the report which are covered.
- **Look for the identical twin.** §7.3: agents miss "character-for-character
  identical instances of the same bug in adjacent code paths." After fixing,
  grep the *pattern* — not the symbol — across the tree.
- A fix applied at one caller while the vulnerable function remains publicly
  callable is `fixed` **with the fragile flag set** — a modifier on an otherwise
  successful outcome, exactly as the paper models it (the flag sits on S1 and S2),
  not a sixth outcome label. The paper's line: a fix that "fully
  removes or replaces the vulnerable code" is not fragile; one that gates it is.
- **Size is a signal.** S5 (worst) patches averaged 88.6 added lines across 3.4
  files; S1 averaged 69.3 across 2.5. A fix growing past the finding's blast
  radius is evidence of drift, not thoroughness — the skill already says "the
  smallest change that resolves the finding", so treat an oversized fix as a
  prompt to re-read rather than a job well done.
- Name the two shapes explicitly, in the style the section already uses:
  **input-filter fix** (blocks the reproduction string, root cause untouched —
  alternative inputs resurface the bug) and **caller-gated fix** (the exploit
  path is guarded, the vulnerable core is not).

**3b. New Step 4.5 — Prove the Behaviour (M1).**

Placed after 4.25 so guard-proof and behaviour-proof read as a pair.

- **Use the paper's corrected definition or this gate becomes noise.** A
  behaviour change is new behaviour matching **neither** the pre-fix behaviour
  **nor** the intended post-fix behaviour. Flagging every deviation from
  pre-patch behaviour was one of the three errors human review caught in the
  authors' own validator (it misfiled clean fixes as behaviour-changing), and a
  gate that cries wolf is how reviewers learn to wave it through.
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

**Counterweight — keep the report small (§7.2).** The paper's cost argument is
that reviewers buried in "an avalanche of unnecessary code" reach *cognitive
surrender* and rubber-stamp. Every gate above adds report surface, so 3c must
subtract as well as add: rank ruthlessly, keep the >=80 confidence filter, and
put escalations and deferrals where a tired human reads them first. A report
nobody finishes is worse than a shorter one that gets acted on.

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
  `code-scrubber-security` agent flags it fragile rather than closed. A rubric that
  passes a known-bad patch has the same problem as a guard that matches nothing.

## Sequencing and effort

| Phase | Effort | Risk | Depends on | State |
|---|---|---|---|---|
| 0 — verify source | — | none | the PDF | **done** |
| 1 — context audit | ~1h | low; prose only | — | **done** |
| 1b — adversary escalation | ~20 min | low | — | **done** |
| 2 — rules-as-code | ~1h | low; new module + tests | — | **done** |
| 3 — scrubber gates | ~2h | medium; changes closure criteria | 2 | **done** |
| 4 — code-review | ~1h | medium; same | 2 | **done** |
| 5 — triage + devops | ~1h | low | 3, 4 | **done** |
| 6 — CLAUDE.md | ~30 min | low | 3, 4 | **done** |

## Follow-ups outside this plan

- **Turn strict unpickling on.** The machinery is built and fuzzed; the flag is
  unset. Enabling it is a save-compatibility change needing its own regression
  pass over legacy fixtures, so it is its own task — but with the posture
  decision recorded above, the review skills now treat non-strict as a defect to
  flag rather than a baseline to accept.
- **Measure our own rate (§7.1).** The paper's headline recommendation is to run
  a FLAWED-style harness over your *own* previously-fixed bugs before trusting
  automated patching. Heart of Virtue has a closed-issue history and
  `tools/bug_hunt.py`; a local success-rate number would replace inherited
  statistics with evidence. Larger than this plan, and the only way to know
  whether the 26% means anything here.

## Decisions for the maintainer

0. **Pickling posture — ANSWERED (2026-09-11):** strict mode is the intended
   production posture; patches must not assume the legacy path reaches prod.
   Encoded in Phase 1.
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
