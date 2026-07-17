"""Player stats, skills, and full-state endpoint checks."""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport


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
        bug = self._check_no_crash(resp, "/api/skills/learn", "POST",
                                   "Learn unknown skill", request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/level-up/allocate — no pending points, should not 500 ---
        # Jean starts with no unspent attribute points, so this is expected to
        # fail gracefully (400 "no points to allocate" or similar), never 500.
        body = {"attribute": "strength_base", "amount": 1}
        resp = client.post("/api/level-up/allocate", json=body)
        bug = self._check_no_crash(resp, "/api/level-up/allocate", "POST",
                                   "Allocate level-up point with none pending",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/level-up/allocate — bad attribute name, must not 500 -----
        body = {"attribute": "harness_nonexistent_attribute", "amount": 1}
        resp = client.post("/api/level-up/allocate", json=body)
        bug = self._check_no_crash(resp, "/api/level-up/allocate", "POST",
                                   "Allocate level-up point with unknown attribute",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        return bugs
