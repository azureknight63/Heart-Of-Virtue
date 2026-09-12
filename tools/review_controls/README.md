# Review rubric controls

Two fixtures that answer one question: **does the security review agent actually
catch a fragile fix, or does its rubric just read well?**

`.claude/agents/code-scrubber-security.md` and the Security Fix Validation block
in `.claude/skills/code-review/SKILL.md` are prose. Prose cannot be unit-tested,
and a rubric that flags everything is as useless as one that flags nothing — both
look fine when you only try the failing case. So these are a matched pair against
the *same* synthetic vulnerability (a path traversal in a save loader):

| Fixture | What it does | A working rubric says |
|---|---|---|
| `fragile_fix.diff` | Guards one caller; leaves the vulnerable primitive public and a second caller unguarded | **fragile / not closed** — caller-gated, and it misses the identical twin |
| `root_cause_fix.diff` | Normalises and confines the path inside the primitive itself | **closed** — Security A, at most a Nit |

Flagging both means the rubric is a rubber stamp. Flagging neither means it is
blind. Only the split result tells you the wording is load-bearing.

## Running it

Dispatch `code-scrubber-security` (and optionally
`code-scrubber-adversary-security` on its findings) once per fixture, following
the agent's input contract:

```
chunk_diff_path: tools/review_controls/<fixture>.diff
worktree_root:   <repo root>
context_paths:   tools/review_controls/vulnerable_baseline.py
chunk_id:        control-<fragile|root-cause>
```

Re-run it after any edit to the security agent definitions or the Security Fix
Validation checklist. That is the whole point: these files exist to catch a
prompt change that quietly stops working.

Nothing here is imported by the engine or collected by pytest — `pytest.ini`
restricts collection to `tests/`, and the baseline is deliberately vulnerable.

## Observed baseline (2026-09-12)

Run against the agent definitions as of commit `1c805a7`. A future run that
diverges materially from this is a signal the prompts have drifted.

**`code-scrubber-security`:**

| Fixture | Grade | Outcome |
|---|---|---|
| `fragile_fix.diff` | **F** | 2 Critical, 1 Major, 2 Minor, 1 Nit. Stated verdict: "this patch is FRAGILE and does NOT close the finding." |
| `root_cause_fix.diff` | **A** | 2 Nit + 1 pre-existing Minor. Stated: "The fragility modifier does not apply here." |

The split is the result that matters. Both F would mean the rubric flags
everything; both A would mean it is blind.

On the fragile fixture the agent did each thing the rules ask for, unprompted:
named the unguarded second caller (`handle_import_request`) rather than only the
patched one; enumerated all paths to the primitive by grep before grading;
separated `pre-existing` from `introduced-by-this-diff` provenance; and routed the
Criticals to human sign-off per the closure rules. It also found a bypass the
fixture's author did not design in — `name="/etc/passwd"` contains no `..`, and
`os.path.join` discards the prefix — so the fragile patch is even weaker than
intended, which is a fair illustration of why "blocks the reproduction input" is
not a fix.

**`code-scrubber-adversary-security`** on those findings: 3 CONFIRMED,
**1 ESCALATED** (Major→Critical on the untouched primitive), 0 DOWNGRADED,
2 ADVISORY. The escalation is the load-bearing observation: the verb did not exist
before this work, and the reason given was that grading the primitive below the
caller "invites the orchestrator to patch the caller and close a still-open root
cause" — precisely the fragile-fix failure the research measured. It also declined
the available blanket downgrade ("it's a fixture, therefore unreachable") and said
why, and it flagged that the packet's stated intent overclaimed relative to the
diff without an Alignment finding to match.

Two incidental findings worth keeping in mind when reading any packet: the
adversary caught line-number drift between pre- and post-patch citations and
warned against editing by line number, and it noted it can only dispose of
findings, never open them — so a gap in the dimension reviewers' output is a gap
the adversary can flag but not fill.
