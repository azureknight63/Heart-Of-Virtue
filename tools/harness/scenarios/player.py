"""Player stats, skills, and full-state endpoint checks."""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class PlayerScenario(Scenario):
    name = "player"
    description = "Verify /status, /stats, /skills, and /full-state endpoints."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # GET /api/status ---------------------------------------------------
        resp = client.get("/api/status")
        bug = self._check_status(resp, 200, "/api/status", "GET", "Player status")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "status"], "/api/status", "GET", "Player status", resp
            )
            status = data.get("status", {})
            bugs += self._check_fields(
                status, ["name", "level", "hp", "max_hp"],
                "/api/status", "GET", "Player status object", resp,
            )

        # GET /api/stats ----------------------------------------------------
        resp = client.get("/api/stats")
        bug = self._check_status(resp, 200, "/api/stats", "GET", "Player stats")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"], "/api/stats", "GET", "Player stats response", resp
            )

        # GET /api/skills ---------------------------------------------------
        resp = client.get("/api/skills")
        bug = self._check_status(resp, 200, "/api/skills", "GET", "Player skills")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"], "/api/skills", "GET", "Player skills response", resp
            )

        # GET /api/full-state -----------------------------------------------
        resp = client.get("/api/full-state")
        bug = self._check_status(resp, 200, "/api/full-state", "GET", "Full game state")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"], "/api/full-state", "GET", "Full state response", resp
            )

        # POST /api/skills/learn — unknown skill should 400/404, not 500 ----
        body = {"skill_name": "harness_nonexistent_skill", "category": "combat"}
        resp = client.post("/api/skills/learn", json=body)
        if resp.status_code == 500:
            bugs.append(self._bug(
                title="Learn unknown skill returns 500",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/skills/learn",
                method="POST",
                expected="HTTP 400 (graceful rejection of unknown skill)",
                actual="HTTP 500 (unhandled exception)",
                response=resp,
                request_body=body,
            ))

        return bugs
