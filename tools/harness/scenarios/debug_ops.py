"""Debug/combat-testing endpoint checks (debug_bp) not covered elsewhere.

`/api/debug/player` (GET), `/api/debug/player/level`, `/api/debug/allies`,
and `/api/debug/allies/progression` are already exercised by
AllyProgressionScenario. This scenario covers the remaining player-stat and
arena-management routes on TheAdjutant (src/npc/_adjutant.py). These
endpoints only exist when app.config["TESTING"] is true, which is exactly
the mode bug_hunt.py runs under, so real (not just bad-input) requests are
safe to fire here.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_ARENA = "Fodder Pit"
_BAD_ARENA = "harness_nonexistent_arena"


class DebugOpsScenario(Scenario):
    name = "debug_ops"
    description = (
        "Verify the remaining /api/debug player-stat and arena-management "
        "endpoints (hp, attributes, heat, restore, learn-skills, skills, "
        "arena CRUD)."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # POST /api/debug/player/hp ------------------------------------------
        body = {"hp": 50, "maxhp": 100}
        resp = client.post("/api/debug/player/hp", json=body)
        bug = self._check_status(
            resp, 200, "/api/debug/player/hp", "POST", "Set player hp",
            request_body=body,
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "hp", "maxhp"],
                "/api/debug/player/hp", "POST", "Set player hp", resp,
            )

        # POST /api/debug/player/hp — missing fields, must be 400 not 500 ----
        resp = client.post("/api/debug/player/hp", json={})
        bug = self._check_no_crash(
            resp, "/api/debug/player/hp", "POST", "Set player hp with empty body",
        )
        if bug:
            bugs.append(bug)

        # POST /api/debug/player/attributes -----------------------------------
        body = {"attributes": {"speed": 5, "strength_base": 6}}
        resp = client.post("/api/debug/player/attributes", json=body)
        bug = self._check_status(
            resp, 200, "/api/debug/player/attributes", "POST", "Set player attributes",
            request_body=body,
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "updated"],
                "/api/debug/player/attributes", "POST", "Set player attributes", resp,
            )

        # POST /api/debug/player/heat ------------------------------------------
        body = {"heat": 2.0}
        resp = client.post("/api/debug/player/heat", json=body)
        bug = self._check_status(
            resp, 200, "/api/debug/player/heat", "POST", "Set player heat",
            request_body=body,
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "heat"],
                "/api/debug/player/heat", "POST", "Set player heat", resp,
            )

        # POST /api/debug/player/restore ---------------------------------------
        resp = client.post("/api/debug/player/restore", json={})
        bug = self._check_status(
            resp, 200, "/api/debug/player/restore", "POST", "Restore player"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "hp", "fatigue"],
                "/api/debug/player/restore", "POST", "Restore player", resp,
            )

        # POST /api/debug/player/learn-skills -----------------------------------
        resp = client.post("/api/debug/player/learn-skills", json={})
        bug = self._check_status(
            resp, 200, "/api/debug/player/learn-skills", "POST", "Learn all skills"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "known_moves"],
                "/api/debug/player/learn-skills", "POST", "Learn all skills", resp,
            )

        # GET /api/debug/player/skills ------------------------------------------
        resp = client.get("/api/debug/player/skills")
        bug = self._check_status(
            resp, 200, "/api/debug/player/skills", "GET", "List player skills"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["skills"],
                "/api/debug/player/skills", "GET", "List player skills", resp,
            )
            if not isinstance(data.get("skills"), list):
                bugs.append(self._bug(
                    title="Debug player/skills: 'skills' field is not a list",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/debug/player/skills",
                    method="GET",
                    expected='"skills" is a JSON array',
                    actual=f'"skills" is {type(data.get("skills")).__name__}',
                    response=resp,
                ))

        # GET /api/debug/arena ----------------------------------------------------
        resp = client.get("/api/debug/arena")
        bug = self._check_status(resp, 200, "/api/debug/arena", "GET", "Arena rosters")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["rosters"],
                "/api/debug/arena", "GET", "Arena rosters", resp,
            )

        # POST /api/debug/arena/add — unknown class, graceful error ------------
        body = {"arena": _ARENA, "cls_name": "HarnessNonexistentClass"}
        resp = client.post("/api/debug/arena/add", json=body)
        bug = self._check_status(
            resp, 200, "/api/debug/arena/add", "POST", "Add unknown combatant class",
            request_body=body,
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            if data.get("success"):
                bugs.append(self._bug(
                    title="Arena add with unknown cls_name returned success=True",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/debug/arena/add",
                    method="POST",
                    expected="success=False (unknown class)",
                    actual="success=True",
                    response=resp,
                    request_body=body,
                ))

        # POST /api/debug/arena/add — real combatant class ----------------------
        body = {"arena": _ARENA, "cls_name": "Slime"}
        resp = client.post("/api/debug/arena/add", json=body)
        bug = self._check_status(
            resp, 200, "/api/debug/arena/add", "POST", "Add real combatant (Slime)",
            request_body=body,
        )
        added_index = None
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"],
                "/api/debug/arena/add", "POST", "Add real combatant (Slime)", resp,
            )
            if data.get("success"):
                roster_resp = client.get("/api/debug/arena")
                if roster_resp.status_code == 200:
                    rosters = client.parse(roster_resp).get("rosters", {})
                    npcs = rosters.get(_ARENA, {}).get("npcs", [])
                    if npcs:
                        added_index = len(npcs) - 1

        # POST /api/debug/arena/stats — edit the combatant we just added --------
        if added_index is not None:
            body = {"arena": _ARENA, "index": added_index, "stats": {"hp": 1}}
            resp = client.post("/api/debug/arena/stats", json=body)
            bug = self._check_status(
                resp, 200, "/api/debug/arena/stats", "POST", "Edit combatant stats",
                request_body=body,
            )
            if bug:
                bugs.append(bug)

        # POST /api/debug/arena/stats — bad arena/index, must not 500 -----------
        body = {"arena": _BAD_ARENA, "index": 0, "stats": {"hp": 1}}
        resp = client.post("/api/debug/arena/stats", json=body)
        bug = self._check_no_crash(
            resp, "/api/debug/arena/stats", "POST", "Edit stats on unknown arena",
            request_body=body,
        )
        if bug:
            bugs.append(bug)

        # POST /api/debug/arena/remove — the combatant we just added -----------
        if added_index is not None:
            body = {"arena": _ARENA, "index": added_index}
            resp = client.post("/api/debug/arena/remove", json=body)
            bug = self._check_status(
                resp, 200, "/api/debug/arena/remove", "POST", "Remove real combatant",
                request_body=body,
            )
            if bug:
                bugs.append(bug)

        # POST /api/debug/arena/remove — invalid index, must not 500 ------------
        body = {"arena": _ARENA, "index": 999}
        resp = client.post("/api/debug/arena/remove", json=body)
        bug = self._check_no_crash(
            resp, "/api/debug/arena/remove", "POST", "Remove combatant at invalid index",
            request_body=body,
        )
        if bug:
            bugs.append(bug)

        # POST /api/debug/arena/clear — unknown arena, graceful error -----------
        body = {"arena": _BAD_ARENA}
        resp = client.post("/api/debug/arena/clear", json=body)
        bug = self._check_status(
            resp, 200, "/api/debug/arena/clear", "POST", "Clear unknown arena",
            request_body=body,
        )
        if bug:
            bugs.append(bug)

        return bugs
