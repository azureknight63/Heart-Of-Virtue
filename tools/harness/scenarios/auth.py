"""Auth / session lifecycle checks."""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class AuthScenario(Scenario):
    name = "auth"
    description = "Verify session creation, validation, and expiry."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # Session validation ------------------------------------------------
        # client.create_session() was already called by the orchestrator;
        # here we verify the validate endpoint acknowledges it.
        resp = client.get("/api/auth/validate")
        bug = self._check_status(
            resp, 200, "/api/auth/validate", "GET", "Session validate"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["valid", "player_id"],
                "/api/auth/validate", "GET", "Session validate", resp,
            )
            if not data.get("valid"):
                bugs.append(self._bug(
                    title="Session validate: valid=False for a live session",
                    severity=BugSeverity.CRITICAL,
                    category=BugCategory.AUTH,
                    endpoint="/api/auth/validate",
                    method="GET",
                    expected='"valid": true',
                    actual=f'"valid": {data.get("valid")}',
                    response=resp,
                ))

        # Unauthenticated request should be rejected -------------------------
        # Bypass the client wrapper to send a request without auth.
        raw = client._client.get("/api/auth/validate")
        if raw.status_code not in (400, 401, 403):
            bugs.append(self._bug(
                title="Session validate: unauthenticated request not rejected",
                severity=BugSeverity.HIGH,
                category=BugCategory.AUTH,
                endpoint="/api/auth/validate",
                method="GET",
                expected="HTTP 401 when Authorization header is absent",
                actual=f"HTTP {raw.status_code}",
                response=raw,
            ))

        # Logout (POST /api/auth/logout) ------------------------------------
        resp = client.post("/api/auth/logout")
        bug = self._check_status(
            resp, 200, "/api/auth/logout", "POST", "Logout"
        )
        if bug:
            bugs.append(bug)

        # After logout, the session should be invalid -----------------------
        # Re-create session for subsequent scenarios (orchestrator will handle
        # this, but we sanity-check the post-logout state here).
        resp_after = client.get("/api/auth/validate")
        data_after = client.parse(resp_after)
        if data_after.get("valid"):
            bugs.append(self._bug(
                title="Session still valid after logout",
                severity=BugSeverity.HIGH,
                category=BugCategory.AUTH,
                endpoint="/api/auth/validate",
                method="GET",
                expected='"valid": false after POST /api/auth/logout',
                actual='"valid": true — session not invalidated',
                response=resp_after,
            ))

        # Re-create session so subsequent scenarios in this run still work.
        client.create_session("harness_auth_restore")

        return bugs
