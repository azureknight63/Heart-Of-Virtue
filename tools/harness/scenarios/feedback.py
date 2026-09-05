"""In-game feedback endpoint checks (feedback_bp).

``_create_github_issue()`` has no TESTING guard, by design: it files a **real**
issue on azureknight63/heart-of-virtue whenever ``GITHUB_TOKEN`` is set, and
this repo's own ``.env`` has carried a live one. So the safety here is not a
property of "this environment" — that reading is what let ten harness runs file
twenty real issues (#301-324).

The control is ``tools/bug_hunt.py``'s bootstrap: before ``src.api`` is
imported it blanks ``GITHUB_TOKEN`` along with every other name in
``OUTBOUND_CREDENTIAL_ENVS`` (``tests/llm_doubles.py``), by *assignment* rather
than ``pop`` — ``load_dotenv(override=False)`` refills a key that is absent and
leaves an assigned blank one alone. Read that header before changing anything
here.

The expected happy-path result is therefore 503 ("service not configured"). A
201 means the token was live and this run just wrote to the tracker, so this
scenario reports it as a bug rather than a pass — the scenario is the last
place that can notice.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class FeedbackScenario(Scenario):
    name = "feedback"
    description = (
        "Verify the feedback/issue endpoint validates input and never 5xx's, "
        "even without a configured GITHUB_TOKEN."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        def check_real_crash(resp, label, request_body=None):
            """Flag only a literal 500 — 503 ('service not configured', the
            expected outcome whenever GITHUB_TOKEN is absent) is not a crash
            for this endpoint. _check_no_crash's blanket 5xx-is-a-crash rule
            doesn't fit here since 503 is this route's own documented, correct
            degraded-mode response (src/api/routes/feedback.py:250).
            """
            if resp.status_code != 500:
                return None
            return self._bug(
                title=f"{label}: server crash (HTTP 500)",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/feedback/issue",
                method="POST",
                expected="No unhandled exception (503 for 'not configured' is fine)",
                actual="HTTP 500",
                response=resp,
                request_body=request_body,
            )

        # Missing body entirely -----------------------------------------------
        resp = client.post("/api/feedback/issue", json={})
        bug = self._check_rejected(
            resp, "/api/feedback/issue", "POST",
            "Feedback issue with empty body not rejected",
            "HTTP 400 (invalid feedback type / missing title)",
        )
        if bug:
            bugs.append(bug)

        # Invalid feedback type -------------------------------------------------
        body = {"type": "harness_bad_type", "title": "Test"}
        resp = client.post("/api/feedback/issue", json=body)
        bug = self._check_rejected(
            resp, "/api/feedback/issue", "POST",
            "Feedback issue with invalid type not rejected",
            "HTTP 400 (Invalid feedback type)",
            severity=BugSeverity.MEDIUM, request_body=body,
        )
        if bug:
            bugs.append(bug)

        # Valid type, missing title ---------------------------------------------
        body = {"type": "bug", "fields": {"steps": "do a thing"}}
        resp = client.post("/api/feedback/issue", json=body)
        bug = self._check_rejected(
            resp, "/api/feedback/issue", "POST",
            "Feedback issue without title not rejected",
            "HTTP 400 (Title is required)",
            severity=BugSeverity.MEDIUM, request_body=body,
        )
        if bug:
            bugs.append(bug)

        # Oversized title, must not 500 ------------------------------------------
        body = {"type": "bug", "title": "x" * 5000, "fields": {}}
        resp = client.post("/api/feedback/issue", json=body)
        bug = self._check_no_crash(
            resp, "/api/feedback/issue", "POST", "Oversized title",
            request_body={"type": "bug", "title": "(5000 chars)", "fields": {}},
        )
        if bug:
            bugs.append(bug)
        else:
            bug = self._check_rejected(
                resp, "/api/feedback/issue", "POST",
                "Feedback issue with oversized title not rejected",
                "HTTP 400 (title too long)",
            )
            if bug:
                bugs.append(bug)

        # Malformed 'fields' (not an object), must not 500 -----------------------
        body = {"type": "general", "title": "Harness test", "fields": "not-an-object"}
        resp = client.post("/api/feedback/issue", json=body)
        bug = check_real_crash(resp, "Malformed 'fields' (string, not dict)", body)
        if bug:
            bugs.append(bug)

        # Wrong-typed inner 'fields' values (issue #428), must not 500 ----------
        # `fields` itself is a dict, but the body builders call
        # .strip()/.lower()/.get() on individual entries assuming they're
        # strings (or, for ratings, a dict). A non-string value used to raise
        # an unhandled AttributeError deep in _build_bug_body/_build_general_body.
        body = {
            "type": "bug",
            "title": "Harness wrong-typed field test",
            "fields": {"steps": 123, "expected": ["not", "a", "string"]},
        }
        resp = client.post("/api/feedback/issue", json=body)
        bug = check_real_crash(resp, "Wrong-typed inner fields value (bug.steps=int)", body)
        if bug:
            bugs.append(bug)
        else:
            bug = self._check_rejected(
                resp, "/api/feedback/issue", "POST",
                "Feedback issue with wrong-typed inner fields value not rejected",
                "HTTP 400 (fields.steps must be a string)",
                severity=BugSeverity.MEDIUM, request_body=body,
            )
            if bug:
                bugs.append(bug)

        # 'general' type with non-dict 'ratings' inner value, must not 500 ------
        body = {
            "type": "general",
            "title": "Harness wrong-typed ratings test",
            "fields": {"message": "hi", "ratings": "not-a-dict"},
        }
        resp = client.post("/api/feedback/issue", json=body)
        bug = check_real_crash(resp, "Wrong-typed inner fields value (general.ratings=str)", body)
        if bug:
            bugs.append(bug)
        else:
            bug = self._check_rejected(
                resp, "/api/feedback/issue", "POST",
                "Feedback issue with non-dict ratings not rejected",
                "HTTP 400 (fields.ratings must be an object)",
                severity=BugSeverity.MEDIUM, request_body=body,
            )
            if bug:
                bugs.append(bug)

        # Well-formed bug report. bug_hunt.py's bootstrap blanks GITHUB_TOKEN,
        # so the only correct outcome is a clean 503 ("service not
        # configured") — never a 500, and never a 201.
        body = {
            "type": "bug",
            "title": "Harness bug-hunt test submission",
            "anonymous": True,
            "fields": {
                "steps": "1. Run the harness",
                "expected": "Graceful validation",
                "actual": "Graceful validation",
                "severity": "low",
            },
        }
        resp = client.post("/api/feedback/issue", json=body)
        bug = check_real_crash(resp, "Well-formed bug report submission", body)
        if bug:
            bugs.append(bug)
        elif resp.status_code == 201:
            # 201 is the route working perfectly, and that is the failure: the
            # harness has just filed a real GitHub issue from a test payload.
            # It was accepted as a pass here for as long as the docstring above
            # claimed the token could not be set, which is why twenty of them
            # reached the tracker before anyone looked. Reported at CRITICAL
            # because the harness has written to something outside itself; the
            # fix is in bug_hunt.py's credential sweep, not in this file.
            bugs.append(self._bug(
                title="Harness filed a REAL GitHub issue (GITHUB_TOKEN was live)",
                severity=BugSeverity.CRITICAL,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/feedback/issue",
                method="POST",
                expected=(
                    "HTTP 503 — bug_hunt.py's bootstrap blanks GITHUB_TOKEN "
                    "before src.api is imported, so the issue-filing path must "
                    "be unreachable from the harness"
                ),
                actual=(
                    "HTTP 201: an issue was created at "
                    f"{client.parse(resp).get('issue_url', 'unknown URL')}"
                ),
                response=resp,
                request_body=body,
            ))
        elif resp.status_code != 503:
            bugs.append(self._bug(
                title="Well-formed feedback submission returned unexpected status",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/feedback/issue",
                method="POST",
                expected="HTTP 503 (no GITHUB_TOKEN configured)",
                actual=f"HTTP {resp.status_code}",
                response=resp,
                request_body=body,
            ))

        return bugs
