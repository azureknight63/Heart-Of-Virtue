"""Phase 3 route checks: reputation, NPC, quests, and dialogue.

These routes were historically misregistered at /api/* instead of their
intended prefixes.  This scenario verifies they are now reachable at the
correct paths and do not crash on bad input.

Registered prefixes (fixed in b16c05a):
  - reputation  → /api/reputation/
  - npc         → /api/npc/
  - quests      → /api/quests/
  - quest-chains → /api/quest-chains/
  - npc_availability / dialogue_context → /api/ (were always correct)
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity

_BAD_ID = "harness_nonexistent_id"


class Phase3Scenario(Scenario):
    name = "phase3"
    description = (
        "Verify Phase 3 routes (reputation, NPC, quests, dialogue) are "
        "reachable at their correct prefixes and do not crash on bad input."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # ------------------------------------------------------------------
        # Reputation  (/api/reputation/)
        # ------------------------------------------------------------------

        # GET /api/reputation/player — player reputation summary
        resp = client.get("/api/reputation/player")
        bug = self._check_status(
            resp, 200, "/api/reputation/player", "GET", "Reputation player summary"
        )
        if bug:
            # 404 here would mean the route isn't registered — real bug
            if resp.status_code == 404:
                bug.title = "Reputation player summary: route not found (prefix misconfiguration?)"
                bug.severity = BugSeverity.HIGH
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"],
                "/api/reputation/player", "GET", "Reputation player summary", resp,
            )

        # GET /api/reputation/npc/<bad_id> — must not 500
        resp = client.get(f"/api/reputation/npc/{_BAD_ID}")
        bug = self._check_no_crash(resp, f"/api/reputation/npc/{_BAD_ID}", "GET",
                                   "Reputation for unknown NPC")
        if bug:
            bugs.append(bug)

        # ------------------------------------------------------------------
        # NPC  (/api/npc/)
        # ------------------------------------------------------------------

        # GET /api/npc/quests/active — list active quests from all NPCs
        resp = client.get("/api/npc/quests/active")
        bug = self._check_status(
            resp, 200, "/api/npc/quests/active", "GET", "Active NPC quests"
        )
        if bug:
            if resp.status_code == 404:
                bug.title = "NPC quests/active: route not found (prefix misconfiguration?)"
                bug.severity = BugSeverity.HIGH
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"],
                "/api/npc/quests/active", "GET", "Active NPC quests", resp,
            )

        # GET /api/npc/<bad_id>/state — must gracefully 404, not 500
        resp = client.get(f"/api/npc/{_BAD_ID}/state")
        bug = self._check_no_crash(resp, f"/api/npc/{_BAD_ID}/state", "GET",
                                   "NPC state for unknown NPC")
        if bug:
            bugs.append(bug)

        # GET /api/npc/<bad_id>/profile — must gracefully 404, not 500
        resp = client.get(f"/api/npc/{_BAD_ID}/profile")
        bug = self._check_no_crash(resp, f"/api/npc/{_BAD_ID}/profile", "GET",
                                   "NPC profile for unknown NPC")
        if bug:
            bugs.append(bug)

        # ------------------------------------------------------------------
        # Quest rewards  (/api/quests/)
        # ------------------------------------------------------------------

        # GET /api/quests/progression — overall quest progression
        resp = client.get("/api/quests/progression")
        bug = self._check_status(
            resp, 200, "/api/quests/progression", "GET", "Quest progression"
        )
        if bug:
            if resp.status_code == 404:
                bug.title = "Quest progression: route not found (prefix misconfiguration?)"
                bug.severity = BugSeverity.HIGH
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"],
                "/api/quests/progression", "GET", "Quest progression", resp,
            )

        # GET /api/quests/<bad_id>/rewards — must not 500
        resp = client.get(f"/api/quests/{_BAD_ID}/rewards")
        bug = self._check_no_crash(resp, f"/api/quests/{_BAD_ID}/rewards", "GET",
                                   "Rewards for unknown quest")
        if bug:
            bugs.append(bug)

        # ------------------------------------------------------------------
        # Quest chains  (/api/quest-chains/)
        # ------------------------------------------------------------------

        # GET /api/quest-chains/progress — overall chain progress
        resp = client.get("/api/quest-chains/progress")
        bug = self._check_status(
            resp, 200, "/api/quest-chains/progress", "GET", "Quest chain progress"
        )
        if bug:
            if resp.status_code == 404:
                bug.title = "Quest chain progress: route not found (prefix misconfiguration?)"
                bug.severity = BugSeverity.HIGH
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"],
                "/api/quest-chains/progress", "GET", "Quest chain progress", resp,
            )

        # GET /api/quest-chains/<bad_id>/progress — must not 500
        resp = client.get(f"/api/quest-chains/{_BAD_ID}/progress")
        bug = self._check_no_crash(resp, f"/api/quest-chains/{_BAD_ID}/progress", "GET",
                                   "Progress for unknown chain")
        if bug:
            bugs.append(bug)

        # ------------------------------------------------------------------
        # Dialogue  (/api/ — npc_availability_bp prefix is /api already)
        # ------------------------------------------------------------------

        # GET /api/dialogue/node/<bad_id> — must not 500
        resp = client.get(f"/api/dialogue/node/{_BAD_ID}")
        bug = self._check_no_crash(resp, f"/api/dialogue/node/{_BAD_ID}", "GET",
                                   "Dialogue node for unknown ID")
        if bug:
            bugs.append(bug)

        # GET /api/npc/<bad_id>/dialogue/history — must not 500
        resp = client.get(f"/api/npc/{_BAD_ID}/dialogue/history")
        bug = self._check_no_crash(resp, f"/api/npc/{_BAD_ID}/dialogue/history", "GET",
                                   "Dialogue history for unknown NPC")
        if bug:
            bugs.append(bug)

        # GET /api/npcs/<bad_id>/status (npc_availability) — must not 500
        resp = client.get(f"/api/npcs/{_BAD_ID}/status")
        bug = self._check_no_crash(resp, f"/api/npcs/{_BAD_ID}/status", "GET",
                                   "NPC availability status for unknown NPC")
        if bug:
            bugs.append(bug)

        return bugs
