"""In-game feedback endpoint checks (feedback_bp).

GITHUB_TOKEN is not set in this environment, so a well-formed submission is
expected to reach the "service not configured" branch (503) rather than
actually filing a GitHub issue — that's still a legitimate, crash-free
response and is what this scenario asserts on the happy path.
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

        # Well-formed bug report — no GITHUB_TOKEN configured here, so we
        # expect a clean 503 ("service not configured"), never a 500.
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
        elif resp.status_code not in (200, 201, 503):
            bugs.append(self._bug(
                title="Well-formed feedback submission returned unexpected status",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/feedback/issue",
                method="POST",
                expected="HTTP 201 (issue filed) or 503 (no GITHUB_TOKEN configured)",
                actual=f"HTTP {resp.status_code}",
                response=resp,
                request_body=body,
            ))

        return bugs
