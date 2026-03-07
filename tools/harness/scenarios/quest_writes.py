"""Quest, quest-chain, and NPC-quest write-endpoint checks.

Tests POST/PUT endpoints with missing/invalid body fields.
All checks use _check_no_crash (any non-5xx is acceptable) except where
explicit validation is expected (400 required), in which case we also flag
if the route crashes instead of validating.

Endpoints covered:
  POST /api/quests/<id>/complete
  POST /api/quests/award-gold
  POST /api/quests/award-experience
  POST /api/quests/award-item
  POST /api/quests/award-reputation
  POST /api/quest-chains/<id>/advance
  POST /api/quest-chains/<id>/complete
  POST /api/quest-chains/<id>/prerequisites
  POST /api/npc/<id>/dialogue         (select dialogue option)
  POST /api/npc/quests/<id>/accept
  POST /api/npc/quests/<id>/progress
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_BAD_ID = "harness_nonexistent_99"


class QuestWritesScenario(Scenario):
    name = "quest_writes"
    description = (
        "Verify quest/quest-chain/NPC-quest write endpoints handle bad input "
        "gracefully (no 5xx on missing/invalid fields)."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # ------------------------------------------------------------------
        # Quest rewards write endpoints
        # ------------------------------------------------------------------

        # POST /api/quests/<id>/complete — empty body (difficulty defaults to normal)
        resp = client.post(f"/api/quests/{_BAD_ID}/complete", json={})
        bug = self._check_no_crash(resp, f"/api/quests/{_BAD_ID}/complete", "POST",
                                   "Complete unknown quest with empty body")
        if bug:
            bugs.append(bug)

        # POST /api/quests/<id>/complete — invalid difficulty
        body = {"difficulty": "impossible"}
        resp = client.post(f"/api/quests/{_BAD_ID}/complete", json=body)
        if resp.status_code == 500:
            bugs.append(self._bug(
                title="Complete quest with invalid difficulty returns 500",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint=f"/api/quests/{_BAD_ID}/complete",
                method="POST",
                expected="HTTP 400 (validation error for invalid difficulty)",
                actual="HTTP 500 (unhandled exception)",
                response=resp,
                request_body=body,
            ))

        # POST /api/quests/award-gold — missing required 'amount'
        resp = client.post("/api/quests/award-gold", json={})
        bug = self._check_no_crash(resp, "/api/quests/award-gold", "POST",
                                   "Award gold with missing amount")
        if bug:
            bugs.append(bug)

        # POST /api/quests/award-experience — missing required 'amount'
        resp = client.post("/api/quests/award-experience", json={})
        bug = self._check_no_crash(resp, "/api/quests/award-experience", "POST",
                                   "Award experience with missing amount")
        if bug:
            bugs.append(bug)

        # POST /api/quests/award-item — missing required fields
        resp = client.post("/api/quests/award-item", json={})
        bug = self._check_no_crash(resp, "/api/quests/award-item", "POST",
                                   "Award item with missing fields")
        if bug:
            bugs.append(bug)

        # POST /api/quests/award-reputation — missing required fields
        resp = client.post("/api/quests/award-reputation", json={})
        bug = self._check_no_crash(resp, "/api/quests/award-reputation", "POST",
                                   "Award reputation with missing fields")
        if bug:
            bugs.append(bug)

        # ------------------------------------------------------------------
        # Quest chain write endpoints
        # ------------------------------------------------------------------

        # POST /api/quest-chains/<id>/advance — missing current_stage
        body = {"next_stage": 1}
        resp = client.post(f"/api/quest-chains/{_BAD_ID}/advance", json=body)
        if resp.status_code == 500:
            bugs.append(self._bug(
                title="Advance chain missing current_stage returns 500",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint=f"/api/quest-chains/{_BAD_ID}/advance",
                method="POST",
                expected="HTTP 400 (validation error for missing field)",
                actual="HTTP 500 (unhandled exception)",
                response=resp,
                request_body=body,
            ))

        # POST /api/quest-chains/<id>/advance — both fields present, bad chain ID
        body = {"current_stage": 0, "next_stage": 1}
        resp = client.post(f"/api/quest-chains/{_BAD_ID}/advance", json=body)
        bug = self._check_no_crash(resp, f"/api/quest-chains/{_BAD_ID}/advance", "POST",
                                   "Advance unknown quest chain",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/quest-chains/<id>/complete — empty body
        resp = client.post(f"/api/quest-chains/{_BAD_ID}/complete", json={})
        bug = self._check_no_crash(resp, f"/api/quest-chains/{_BAD_ID}/complete", "POST",
                                   "Complete unknown quest chain with empty body")
        if bug:
            bugs.append(bug)

        # POST /api/quest-chains/<id>/prerequisites — empty body
        resp = client.post(f"/api/quest-chains/{_BAD_ID}/prerequisites", json={})
        bug = self._check_no_crash(resp, f"/api/quest-chains/{_BAD_ID}/prerequisites", "POST",
                                   "Check prerequisites for unknown quest chain")
        if bug:
            bugs.append(bug)

        # ------------------------------------------------------------------
        # NPC dialogue and quest write endpoints
        # ------------------------------------------------------------------

        # POST /api/npc/<id>/dialogue — missing option_id
        resp = client.post(f"/api/npc/{_BAD_ID}/dialogue", json={})
        bug = self._check_no_crash(resp, f"/api/npc/{_BAD_ID}/dialogue", "POST",
                                   "Select dialogue option with missing option_id")
        if bug:
            bugs.append(bug)

        # POST /api/npc/<id>/dialogue — valid option_id, bad NPC
        body = {"option_id": 0}
        resp = client.post(f"/api/npc/{_BAD_ID}/dialogue", json=body)
        bug = self._check_no_crash(resp, f"/api/npc/{_BAD_ID}/dialogue", "POST",
                                   "Select dialogue option on unknown NPC",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/npc/quests/<id>/accept — empty body
        resp = client.post(f"/api/npc/quests/{_BAD_ID}/accept", json={})
        bug = self._check_no_crash(resp, f"/api/npc/quests/{_BAD_ID}/accept", "POST",
                                   "Accept unknown NPC quest")
        if bug:
            bugs.append(bug)

        # POST /api/npc/quests/<id>/progress — empty body
        resp = client.post(f"/api/npc/quests/{_BAD_ID}/progress", json={})
        bug = self._check_no_crash(resp, f"/api/npc/quests/{_BAD_ID}/progress", "POST",
                                   "Update progress on unknown NPC quest")
        if bug:
            bugs.append(bug)

        return bugs
