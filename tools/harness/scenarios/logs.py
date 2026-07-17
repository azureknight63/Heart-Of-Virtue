"""Browser log-management endpoint checks (logs_bp).

POST /browser is intentionally unauthenticated (the frontend logger posts to
it via sendBeacon before a page unload) — this scenario calls it with the
harness's normal authenticated client, which is still a valid request. The
management routes (list/read/cleanup/stats/delete) are gated behind
TESTING mode, which is exactly the mode bug_hunt.py runs under.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity


class LogsScenario(Scenario):
    name = "logs"
    description = (
        "Verify browser log receive/list/read/cleanup/stats/delete endpoints "
        "work and reject bad input gracefully."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # POST /api/logs/browser — well-formed payload -----------------------
        session_id = f"harness_{self.name}_session"
        body = {
            "logs": [
                {
                    "timestamp": "2026-01-01T00:00:00.000Z",
                    "level": "INFO",
                    "message": "harness bug-hunt log entry",
                    "url": "http://localhost/harness",
                }
            ],
            "session_id": session_id,
        }
        resp = client.post("/api/logs/browser", json=body)
        bug = self._check_status(
            resp, 200, "/api/logs/browser", "POST", "Submit browser logs",
            request_body=body,
        )
        if bug:
            bugs.append(bug)

        # POST /api/logs/browser — missing "logs" field ----------------------
        resp = client.post("/api/logs/browser", json={})
        bug = self._check_rejected(
            resp, "/api/logs/browser", "POST",
            "Browser logs without 'logs' field not rejected",
            "HTTP 400 when 'logs' is absent",
        )
        if bug:
            bugs.append(bug)

        # POST /api/logs/browser — non-object body, must not 500 -------------
        resp = client.post("/api/logs/browser", json=["not", "an", "object"])
        bug = self._check_no_crash(
            resp, "/api/logs/browser", "POST", "Browser logs with a list body",
        )
        if bug:
            bugs.append(bug)

        # GET /api/logs/browser/files -----------------------------------------
        resp = client.get("/api/logs/browser/files")
        bug = self._check_status(
            resp, 200, "/api/logs/browser/files", "GET", "List browser log files"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["files"],
                "/api/logs/browser/files", "GET", "Browser log file list", resp,
            )

        # GET /api/logs/browser/files/<filename> — path traversal, must 400 --
        resp = client.get("/api/logs/browser/files/..%2F..%2Fetc%2Fpasswd")
        bug = self._check_rejected(
            resp, "/api/logs/browser/files/<filename>", "GET",
            "Browser log file read with traversal filename not rejected",
            "HTTP 400/404 for a path-traversal filename",
            allowed=(400, 404), severity=BugSeverity.MEDIUM,
        )
        if bug:
            bugs.append(bug)

        # GET /api/logs/browser/files/<filename> — unknown filename ----------
        resp = client.get("/api/logs/browser/files/harness_nonexistent.log")
        bug = self._check_no_crash(
            resp, "/api/logs/browser/files/<filename>", "GET",
            "Read a log file that does not exist",
        )
        if bug:
            bugs.append(bug)

        # GET /api/logs/browser/stats -------------------------------------------
        resp = client.get("/api/logs/browser/stats")
        bug = self._check_status(
            resp, 200, "/api/logs/browser/stats", "GET", "Browser log stats"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["stats", "cleanup_config"],
                "/api/logs/browser/stats", "GET", "Browser log stats", resp,
            )

        # POST /api/logs/browser/cleanup ---------------------------------------
        resp = client.post("/api/logs/browser/cleanup", json={})
        bug = self._check_status(
            resp, 200, "/api/logs/browser/cleanup", "POST", "Trigger log cleanup"
        )
        if bug:
            bugs.append(bug)

        # POST /api/logs/browser/cleanup — bad overrides, must not 500 -------
        body = {"retention_days": "not-a-number", "max_size_mb": "also-bad"}
        resp = client.post("/api/logs/browser/cleanup", json=body)
        bug = self._check_no_crash(
            resp, "/api/logs/browser/cleanup", "POST",
            "Cleanup with non-numeric overrides", request_body=body,
        )
        if bug:
            bugs.append(bug)

        # DELETE /api/logs/browser/files/<filename> — unknown filename -------
        resp = client._client.delete(
            "/api/logs/browser/files/harness_nonexistent.log",
            headers=client._auth_headers(),
        )
        bug = self._check_no_crash(
            resp, "/api/logs/browser/files/<filename>", "DELETE",
            "Delete a log file that does not exist",
        )
        if bug:
            bugs.append(bug)

        # DELETE /api/logs/browser/files/<filename> — path traversal ---------
        resp = client._client.delete(
            "/api/logs/browser/files/..%2F..%2Fetc%2Fpasswd",
            headers=client._auth_headers(),
        )
        bug = self._check_rejected(
            resp, "/api/logs/browser/files/<filename>", "DELETE",
            "Browser log file delete with traversal filename not rejected",
            "HTTP 400/404 for a path-traversal filename",
            allowed=(400, 404), severity=BugSeverity.MEDIUM,
        )
        if bug:
            bugs.append(bug)

        return bugs
