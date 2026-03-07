"""Combat loop checks — start, execute moves, status, log."""

from typing import List, Optional

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_MAX_ROUNDS = 8  # safety cap to avoid infinite loops


class CombatScenario(Scenario):
    name = "combat"
    description = "Simulate a full combat encounter: start, moves, status, log."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # Find an NPC in the current room to fight.
        enemy_id = self._find_enemy(client)
        if not enemy_id:
            # No enemy available — verify the API gracefully rejects a bad ID.
            bugs += self._check_invalid_start(client)
            return bugs

        # Start combat ------------------------------------------------------
        body = {"enemy_id": enemy_id}
        resp = client.post("/api/combat/start", json=body)
        bug = self._check_status(
            resp, 201, "/api/combat/start", "POST",
            "Start combat", request_body=body,
        )
        if bug:
            bugs.append(bug)
            return bugs

        data = client.parse(resp)
        bugs += self._check_fields(
            data, ["success", "combat_id", "combatants", "turn_order"],
            "/api/combat/start", "POST", "Start combat response", resp,
        )

        # Combat loop -------------------------------------------------------
        for round_num in range(1, _MAX_ROUNDS + 1):
            status_bugs, active = self._check_status_endpoint(client, round_num)
            bugs += status_bugs
            if not active:
                break

            # Execute a basic attack.
            move_bugs, ended = self._execute_attack(client, round_num)
            bugs += move_bugs
            if ended:
                break

        # Combat log --------------------------------------------------------
        resp = client.get("/api/combat/log")
        bug = self._check_status(
            resp, 200, "/api/combat/log", "GET", "Get combat log"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "log"],
                "/api/combat/log", "GET", "Combat log", resp,
            )
            if not isinstance(data.get("log"), list):
                bugs.append(self._bug(
                    title="Combat log: 'log' field is not a list",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/combat/log",
                    method="GET",
                    expected='"log" is a JSON array',
                    actual=f'"log" is {type(data.get("log")).__name__}',
                    response=resp,
                ))

        return bugs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_enemy(self, client: GameClient) -> Optional[str]:
        """Return the first NPC ID from the current room, or None."""
        resp = client.get("/api/world")
        if resp.status_code != 200:
            return None
        data = client.parse(resp)
        room = data.get("room", {})
        npcs = room.get("npcs", [])
        if npcs and isinstance(npcs, list):
            npc = npcs[0]
            # NPC may be a dict with 'id' or 'npc_id', or just a string.
            if isinstance(npc, dict):
                return npc.get("id") or npc.get("npc_id") or npc.get("name")
            return str(npc)
        return None

    def _check_invalid_start(self, client: GameClient) -> List[BugReport]:
        """Verify the API gracefully handles a non-existent enemy_id."""
        bugs = []
        body = {"enemy_id": "harness_nonexistent_enemy"}
        resp = client.post("/api/combat/start", json=body)
        if resp.status_code == 500:
            bugs.append(self._bug(
                title="Start combat with unknown enemy_id returns 500",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/combat/start",
                method="POST",
                expected="HTTP 400 (graceful rejection of unknown enemy)",
                actual="HTTP 500 (unhandled exception)",
                response=resp,
                request_body=body,
            ))
        return bugs

    def _check_status_endpoint(
        self, client: GameClient, round_num: int
    ):
        """Check GET /api/combat/status. Returns (bugs, is_active)."""
        bugs = []
        resp = client.get("/api/combat/status")
        bug = self._check_status(
            resp, 200, "/api/combat/status", "GET",
            f"Combat status (round {round_num})",
        )
        if bug:
            bugs.append(bug)
            return bugs, False

        data = client.parse(resp)
        bugs += self._check_fields(
            data, ["success", "combat_active"],
            "/api/combat/status", "GET",
            f"Combat status round {round_num}", resp,
        )
        return bugs, bool(data.get("combat_active"))

    def _execute_attack(self, client: GameClient, round_num: int):
        """Execute a basic attack move. Returns (bugs, combat_ended)."""
        bugs = []
        body = {"move_type": "attack", "move_id": "attack"}
        resp = client.post("/api/combat/move", json=body)
        bug = self._check_status(
            resp, 200, "/api/combat/move", "POST",
            f"Execute attack (round {round_num})", request_body=body,
        )
        if bug:
            bugs.append(bug)
            return bugs, True  # stop loop on error

        data = client.parse(resp)
        bugs += self._check_fields(
            data, ["success"],
            "/api/combat/move", "POST",
            f"Attack response round {round_num}", resp,
        )
        # Detect combat-ended signals in the response.
        ended = (
            not data.get("combat_active", True)
            or data.get("combat_ended")
            or data.get("victory")
            or data.get("defeated")
        )
        return bugs, bool(ended)
