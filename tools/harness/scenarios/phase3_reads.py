"""Phase 3 supplemental read-endpoint checks.

Covers the remaining read endpoints from the reputation, npc_availability,
and dialogue_context blueprints that weren't probed by the original phase3
scenario.  All checks use _check_no_crash — any non-5xx is acceptable.

Endpoints covered:
  GET  /api/locations/<id>/npcs                  (npc_availability_bp)
  GET  /api/npcs/<id>/timeline                   (npc_availability_bp)
  POST /api/npcs/<id>/check-availability         (npc_availability_bp)
  POST /api/npcs/<id>/location                   (npc_availability_bp — bad body)
  GET  /api/npc/<id>/dialogue/available          (dialogue_context_bp)
  POST /api/dialogue/start                       (dialogue_context_bp — missing fields)
  POST /api/dialogue/select                      (dialogue_context_bp — missing fields)
  GET  /api/reputation/dialogue/<npc>/<node>     (reputation_bp)
  GET  /api/reputation/quest/<npc>/<type>        (reputation_bp)
  PUT  /api/reputation/npc/<id>                  (reputation_bp)
  GET  /api/npc/quests/<id>/status               (npc_bp)
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
        # NPC availability — untested endpoints
        # ------------------------------------------------------------------

        # GET /api/locations/<id>/npcs
        resp = client.get(f"/api/locations/{_BAD_ID}/npcs")
        bug = self._check_no_crash(resp, f"/api/locations/{_BAD_ID}/npcs", "GET",
                                   "Get NPCs at unknown location")
        if bug:
            bugs.append(bug)

        # GET /api/npcs/<id>/timeline
        resp = client.get(f"/api/npcs/{_BAD_ID}/timeline")
        bug = self._check_no_crash(resp, f"/api/npcs/{_BAD_ID}/timeline", "GET",
                                   "Get timeline for unknown NPC")
        if bug:
            bugs.append(bug)

        # POST /api/npcs/<id>/check-availability — empty body
        resp = client.post(f"/api/npcs/{_BAD_ID}/check-availability", json={})
        bug = self._check_no_crash(resp, f"/api/npcs/{_BAD_ID}/check-availability", "POST",
                                   "Check availability of unknown NPC")
        if bug:
            bugs.append(bug)

        # POST /api/npcs/<id>/location — missing new_location_id
        resp = client.post(f"/api/npcs/{_BAD_ID}/location", json={})
        bug = self._check_no_crash(resp, f"/api/npcs/{_BAD_ID}/location", "POST",
                                   "Update location of unknown NPC with no body")
        if bug:
            bugs.append(bug)

        # ------------------------------------------------------------------
        # Dialogue context — untested endpoints
        # ------------------------------------------------------------------

        # GET /api/npc/<id>/dialogue/available
        resp = client.get(f"/api/npc/{_BAD_ID}/dialogue/available")
        bug = self._check_no_crash(resp, f"/api/npc/{_BAD_ID}/dialogue/available", "GET",
                                   "Get available dialogues for unknown NPC")
        if bug:
            bugs.append(bug)

        # POST /api/dialogue/start — missing required fields
        resp = client.post("/api/dialogue/start", json={})
        bug = self._check_no_crash(resp, "/api/dialogue/start", "POST",
                                   "Start dialogue with empty body")
        if bug:
            bugs.append(bug)

        # POST /api/dialogue/start — valid fields, bad NPC/dialogue ID
        body = {"npc_id": _BAD_ID, "dialogue_id": _BAD_ID}
        resp = client.post("/api/dialogue/start", json=body)
        bug = self._check_no_crash(resp, "/api/dialogue/start", "POST",
                                   "Start dialogue with unknown NPC/dialogue IDs",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/dialogue/select — missing required fields
        resp = client.post("/api/dialogue/select", json={})
        bug = self._check_no_crash(resp, "/api/dialogue/select", "POST",
                                   "Select dialogue choice with empty body")
        if bug:
            bugs.append(bug)

        # POST /api/dialogue/select — bad conversation/choice IDs
        body = {"conversation_id": _BAD_ID, "choice_id": _BAD_ID}
        resp = client.post("/api/dialogue/select", json=body)
        bug = self._check_no_crash(resp, "/api/dialogue/select", "POST",
                                   "Select unknown dialogue choice",
                                   request_body=body)
        if bug:
            bugs.append(bug)

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

        # ------------------------------------------------------------------
        # NPC quest status
        # ------------------------------------------------------------------

        # GET /api/npc/quests/<id>/status
        resp = client.get(f"/api/npc/quests/{_BAD_ID}/status")
        bug = self._check_no_crash(resp, f"/api/npc/quests/{_BAD_ID}/status", "GET",
                                   "Get status of unknown NPC quest")
        if bug:
            bugs.append(bug)

        return bugs
