"""Issue drafts for file_issues.py. Copy next to your run's findings and fill in.

Each entry: key (stable id, used for idempotent filing), title (ASCII only —
gh on Windows has mangled em dashes), labels (must exist in the repo), body.
Cite tester reports by name and the evidence they produced; say what the
orchestrator verified and how. One issue per confirmed defect; group polish
into one batch so the tracker does not drown.
"""

RUN = ("Found during the <DATE> live browser QA (<branch> @ <sha>; <N> tester agents over Playwright "
       "and the in-app browser, orchestrator verification on a clean Playwright client). "
       "Full report: `docs/qa/<report>.md`.")

ISSUES = [
    {
        "key": "example_soft_lock",
        "title": "Passageway arrival 'Event Result' modal cannot be dismissed (soft-lock until page reload)",
        "labels": ["bug", "frontend", "needs-testing"],
        "body": f"""**Severity:** High (soft-lock; only a full page reload recovers)

**Location:** teleport into `<map>` (x,y) via <object> at <map> (x,y)

**Steps to reproduce**
1. ...
2. ...

**Expected:** ...

**Actual:** ... Reproduced N/N by <tester> and N/N by the orchestrator in a separate session.

**Evidence:** screenshots `<file>.png` (docs/qa/<run>/shots/), console/network events verbatim, API excerpts.

**Notes / suspected cause:** `<file>:<line>` ...

{RUN}""",
    },
]
