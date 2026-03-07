"""Save/load game state endpoint checks.

NOTE: The saves endpoints require a cloud-linked session (db_user_id on the
session object), which is only set when a player logs in through the full
auth flow (POST /auth/login with Turso credentials).  Sessions created
directly via SessionManager.create_session() — as the harness does — will
receive a 401 "not linked to cloud account" from the cloud-storage endpoints.

This scenario therefore only checks for:
  1. Hard crashes (500s) — a cloud-auth check should never produce a 500.
  2. Clean JSON error responses (not raw tracebacks or empty bodies).
  3. The /game/new endpoint, which does not require cloud auth.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

# These saves endpoints return 401 in the test context (no db_user_id).
# Any status in this set is acceptable — only 500 is a bug.
_ACCEPTABLE_NO_CLOUD = (200, 201, 400, 401, 403, 404)


class SavesScenario(Scenario):
    name = "saves"
    description = (
        "Verify saves endpoints don't crash (500) without cloud auth; "
        "verify /game/new works."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # GET /api/saves — must not 500 (cloud 401 is expected in test ctx) -
        resp = client.get("/api/saves")
        if resp.status_code not in _ACCEPTABLE_NO_CLOUD:
            bugs.append(self._bug(
                title=f"List saves: unexpected HTTP {resp.status_code}",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH if resp.status_code >= 500 else BugCategory.WRONG_RESPONSE,
                endpoint="/api/saves",
                method="GET",
                expected="HTTP 200 (logged in) or 401 (no cloud session)",
                actual=f"HTTP {resp.status_code}",
                response=resp,
            ))
        else:
            data = client.parse(resp)
            if "_raw" in data:
                bugs.append(self._bug(
                    title="List saves: response body is not valid JSON",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/saves",
                    method="GET",
                    expected="JSON response body",
                    actual="Non-JSON body",
                    response=resp,
                ))

        # POST /api/saves — same: 401 expected in test ctx ------------------
        body = {"name": "harness_test_save", "is_autosave": False}
        resp = client.post("/api/saves", json=body)
        if resp.status_code not in _ACCEPTABLE_NO_CLOUD:
            bugs.append(self._bug(
                title=f"Create save: unexpected HTTP {resp.status_code}",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH if resp.status_code >= 500 else BugCategory.WRONG_RESPONSE,
                endpoint="/api/saves",
                method="POST",
                expected="HTTP 201 (logged in) or 401 (no cloud session)",
                actual=f"HTTP {resp.status_code}",
                response=resp,
                request_body=body,
            ))

        # POST /api/saves/bad_id/load — must not 500 ------------------------
        resp = client.post("/api/saves/harness_bad_id/load")
        if resp.status_code == 500:
            bugs.append(self._bug(
                title="Load save with invalid ID returns 500",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/saves/harness_bad_id/load",
                method="POST",
                expected="HTTP 401 or 404 (graceful rejection)",
                actual="HTTP 500 (unhandled exception)",
                response=resp,
            ))

        # POST /api/game/new — does NOT require cloud auth ------------------
        resp = client.post("/api/game/new")
        bug = self._check_status(resp, 200, "/api/game/new", "POST", "New game")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"], "/api/game/new", "POST", "New game response", resp
            )

        return bugs
