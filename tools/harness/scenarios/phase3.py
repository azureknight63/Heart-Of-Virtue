"""Phase 3 route checks: NPC.

These routes were historically misregistered at /api/* instead of their
intended prefixes.  This scenario verifies they are now reachable at the
correct paths and do not crash on bad input.

Registered prefixes (fixed in b16c05a):
  - npc         → /api/npc/

Note: the quest-rewards, quest-chains, dialogue-context, and
npc-availability blueprints (and their routes) were removed as dead/mocked
endpoints (#236); the reputation blueprint was removed as a dead/unused
endpoint (#252) — do not re-add probes for them here.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport

_BAD_ID = "harness_nonexistent_id"


class Phase3Scenario(Scenario):
    name = "phase3"
    description = (
        "Verify Phase 3 routes (NPC) are reachable at their "
        "correct prefixes and do not crash on bad input."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # ------------------------------------------------------------------
        # NPC  (/api/npc/)
        # ------------------------------------------------------------------

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

        # GET /api/npc/<bad_id>/dialogue — must gracefully 404, not 500
        resp = client.get(f"/api/npc/{_BAD_ID}/dialogue")
        bug = self._check_no_crash(resp, f"/api/npc/{_BAD_ID}/dialogue", "GET",
                                   "Dialogue options for unknown NPC")
        if bug:
            bugs.append(bug)

        # POST /api/npc/<bad_id>/dialogue — missing option_id, must not 500
        resp = client.post(f"/api/npc/{_BAD_ID}/dialogue", json={})
        bug = self._check_no_crash(resp, f"/api/npc/{_BAD_ID}/dialogue", "POST",
                                   "Select dialogue option with missing option_id")
        if bug:
            bugs.append(bug)

        # POST /api/npc/<bad_id>/dialogue — valid option_id, bad NPC
        body = {"option_id": 0}
        resp = client.post(f"/api/npc/{_BAD_ID}/dialogue", json=body)
        bug = self._check_no_crash(resp, f"/api/npc/{_BAD_ID}/dialogue", "POST",
                                   "Select dialogue option on unknown NPC",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        return bugs
