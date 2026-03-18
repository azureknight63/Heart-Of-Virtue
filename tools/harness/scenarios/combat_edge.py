"""Combat edge-case checks.

Tests combat endpoints in out-of-band conditions:
- Status/log when no combat is active (must not 500)
- Move when no combat is active (must not 500)
- Move with missing or malformed body (must return 400, not 500)
- Start combat on a room with no enemies (must return graceful error)
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class CombatEdgeScenario(Scenario):
    name = "combat_edge"
    description = (
        "Verify combat endpoints handle out-of-band calls and bad input "
        "gracefully (no 5xx)."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # GET /api/combat/status — no active combat -------------------------
        # Expect a valid JSON response (probably in_combat: false), never 500.
        resp = client.get("/api/combat/status")
        bug = self._check_no_crash(resp, "/api/combat/status", "GET",
                                   "Combat status with no active combat")
        if bug:
            bugs.append(bug)

        # GET /api/combat/log — no active combat ----------------------------
        resp = client.get("/api/combat/log")
        bug = self._check_no_crash(resp, "/api/combat/log", "GET",
                                   "Combat log with no active combat")
        if bug:
            bugs.append(bug)

        # POST /api/combat/move — no active combat --------------------------
        body = {"move_type": "attack", "move_id": "attack"}
        resp = client.post("/api/combat/move", json=body)
        bug = self._check_no_crash(resp, "/api/combat/move", "POST",
                                   "Combat move with no active combat",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/combat/move — missing move_type -------------------------
        body = {"move_id": "attack"}
        resp = client.post("/api/combat/move", json=body)
        if resp.status_code == 500:
            bugs.append(self._bug(
                title="Combat move missing move_type returns 500",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/combat/move",
                method="POST",
                expected="HTTP 400 (validation error)",
                actual="HTTP 500 (unhandled exception)",
                response=resp,
                request_body=body,
            ))

        # POST /api/combat/move — empty body --------------------------------
        resp = client.post("/api/combat/move", json={})
        if resp.status_code == 500:
            bugs.append(self._bug(
                title="Combat move with empty body returns 500",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/combat/move",
                method="POST",
                expected="HTTP 400 (validation error)",
                actual="HTTP 500 (unhandled exception)",
                response=resp,
                request_body={},
            ))

        # POST /api/combat/start — no enemy target specified ----------------
        body = {}
        resp = client.post("/api/combat/start", json=body)
        bug = self._check_no_crash(resp, "/api/combat/start", "POST",
                                   "Combat start with empty body",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        return bugs
