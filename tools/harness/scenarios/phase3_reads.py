"""Phase 3 supplemental read-endpoint checks.

Covers the remaining read endpoints from the reputation blueprint that
weren't probed by the original phase3 scenario.  All checks use
_check_no_crash — any non-5xx is acceptable.

Endpoints covered:
  GET  /api/reputation/dialogue/<npc>/<node>     (reputation_bp)
  GET  /api/reputation/quest/<npc>/<type>        (reputation_bp)
  PUT  /api/reputation/npc/<id>                  (reputation_bp)
  POST /api/reputation/npc/<id>/flag/<flag>      (reputation_bp)

Note: the npc_availability_bp and dialogue_context_bp blueprints (and the
npc_bp quest-status route) were removed as dead/mocked endpoints (#236) —
do not re-add probes for them here.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_BAD_ID = "harness_nonexistent_99"


class Phase3ReadsScenario(Scenario):
    name = "phase3_reads"
    description = (
        "Verify remaining Phase 3 read/write endpoints do not crash "
        "on unknown IDs or missing body fields."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # ------------------------------------------------------------------
        # Reputation — untested endpoints
        # ------------------------------------------------------------------

        # GET /api/reputation/dialogue/<npc_id>/<dialogue_node>
        resp = client.get(f"/api/reputation/dialogue/{_BAD_ID}/{_BAD_ID}")
        bug = self._check_no_crash(resp, f"/api/reputation/dialogue/{_BAD_ID}/{_BAD_ID}", "GET",
                                   "Get reputation for unknown dialogue node")
        if bug:
            bugs.append(bug)

        # GET /api/reputation/quest/<npc_id>/<quest_type>
        resp = client.get(f"/api/reputation/quest/{_BAD_ID}/{_BAD_ID}")
        bug = self._check_no_crash(resp, f"/api/reputation/quest/{_BAD_ID}/{_BAD_ID}", "GET",
                                   "Get reputation for unknown quest type")
        if bug:
            bugs.append(bug)

        # PUT /api/reputation/npc/<id> — empty body
        resp = client._client.put(
            f"/api/reputation/npc/{_BAD_ID}",
            json={},
            headers=client._auth_headers(),
            content_type="application/json",
        )
        bug = self._check_no_crash(resp, f"/api/reputation/npc/{_BAD_ID}", "PUT",
                                   "Update reputation for unknown NPC with empty body")
        if bug:
            bugs.append(bug)

        # POST /api/reputation/npc/<id>/flag/<flag> — empty body
        resp = client.post(f"/api/reputation/npc/{_BAD_ID}/flag/{_BAD_ID}", json={})
        bug = self._check_no_crash(resp, f"/api/reputation/npc/{_BAD_ID}/flag/{_BAD_ID}", "POST",
                                   "Set unknown reputation flag with empty body")
        if bug:
            bugs.append(bug)

        return bugs
