# Triage, verification, issue filing, report

## Verification discipline

Tester reports are leads, not verdicts. Before anything reaches the tracker:

1. **Sort by severity and by stack.** Anything from a stack later found faulty is suspect until re-verified.
2. **Read the source for every "event never fires" / "state wrong" claim.** Find the trigger condition (`check_conditions`, the key a cache is stored under, the guard a route lacks). Half of these are config artefacts; the real ones are found faster in code than in a browser. Quote file:line in the issue.
3. **Re-run every Critical/High on a clean client.** Start your own driver (`V1`, port 7009+) on a healthy stack; reproduce with `where()` cross-checks, `hit_test()` and `raw_click()` for anything "unclickable", request logging around the failing action (`page.on("request", …)`), and screenshots. Two reproductions in independent sessions is the bar for Critical.
4. **Classify each contested finding** as one of: verified (yours + theirs), verified-by-source, kept with caveat (seen once, mechanism plausible from code — say which), dropped as setup artefact, dropped as not reproduced. The report lists the dropped ones too, with the reason — the next run should not re-investigate them.
5. **Dedupe against the tracker.** `gh issue list --state all --search "<keyword>"` for each candidate; cite related closed issues in the body.

## Severity (the beta plan's scale)

- **Critical** — crash, soft-lock, data loss, route blocker.
- **High** — wrong story flag, event not firing, NPC missing, dialogue truncated, UI action not working.
- **Low** — typo, visual glitch, pacing, voice inconsistency.

Reviewers may use their own UX scale (blocks play / player will misunderstand / polish); map it to the above when filing.

## Grouping issues

One issue per confirmed defect with a clear owner and fix shape. Group the rest so the tracker does not drown:
- an **accessibility umbrella** (measured targets, colour-only state, landmarks, focus, unnamed dialogs),
- a **polish batch** (copy, alignment, string bugs, panel oddities — each a one-line bullet with the tester who saw it),
- a **pacing/chrome umbrella** for story dialogs,
- a **mobile** issue per layout defect (they need different fixes from desktop).

Every body carries: severity, location (map + tile), numbered steps from session start, expected/actual, evidence (screenshot filenames under `docs/qa/<run>/shots/`, verbatim console/network lines, API excerpts), confidence, suspected cause with file:line, and a one-line `RUN` footer pointing at the report. Titles ASCII-only. Use `file_issues.py --spec … ` dry-run, then `--go`; it is idempotent per key.

## The consolidated report (`docs/qa/<run>.md`)

Sections that proved useful, in order:

1. **Headline** — five bullets a reader can act on without reading further; issue numbers inline.
2. **Setup** — the stacks table, how testers logged in, the setup faults and exactly which findings they contaminated.
3. **Coverage** — scenes × testers matrix with PASS/FAIL/BLOCKED/NOT REACHED.
4. **Findings, ranked** — a table: severity, one-line finding, how it was verified, issue link.
5. **Reported and not filed** — every dropped or downgraded claim with its reason.
6. **Dialogue voice** — scripted vs LLM, prohibited-phrase hits, what was delivery vs writing.
7. **What works** — so it doesn't regress and so the team hears it.
8. **Recommended order of work.**
9. **Re-running this** — pointer to the skill and the memory note.

Copy the tester reports and only the cited screenshots into `docs/qa/<run>/` (13 screenshots ≈ 3.6 MB was acceptable; 130 was not). Commit the report separately from any code change.

## Closing the loop

- Save what changed in your understanding to memory (the toolkit note, the known-blocker list) so the next run starts where this one ended.
- Suggest `/commit` for code changes and the report; never commit the QA configs by accident (`*.ini` is gitignored; a corrected beta config should be force-added deliberately).
- Tear down: kill the API child of each stack (start_stack shuts Vite down), confirm no listeners on the QA ports and no stray `chrome-headless-shell` processes.
