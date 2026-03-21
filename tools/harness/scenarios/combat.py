"""Combat loop checks — start, execute moves, status, log."""

from typing import List, Optional, Tuple

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_MAX_ROUNDS = 20  # safety cap to avoid infinite loops

# Arena tile navigation: direction sequence from (0,0) to each scenario tile.
_SCENARIO_NAV = {
    "fodder":       ["east"],           # (0,0) → (1,0) Fodder Pit
    "boss":         ["east", "east"],   # (0,0) → (2,0) The Crucible
    "ally":         ["south"],          # (0,0) → (0,1) Ally Courtyard
    "status_dummy": ["south", "east"],  # (0,0) → (1,1) Status Chamber
    "custom":       ["east"],           # (0,0) → (1,0) Fodder Pit (custom roster)
}


class CombatScenario(Scenario):
    name = "combat"
    description = "Simulate a full combat encounter: start, moves, status, log."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # Navigate to the correct arena tile.  The game always starts at (0,0)
        # (Proving Grounds) which only has TheAdjutant — not a valid enemy.
        # Move to the scenario tile before searching for combatants.
        nav_bugs = self._navigate_to_scenario_tile(client)
        bugs += nav_bugs
        if nav_bugs:
            # Navigation failed — fall back to invalid-start check so the
            # harness still exercises the combat API rather than silently passing.
            bugs += self._check_invalid_start(client)
            return bugs

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

        # Flag duplicate player in combatants list (known bug: Jean appears
        # as both 'player' and 'ally_*' simultaneously).
        combatants = data.get("combatants", [])
        jean_entries = [c for c in combatants if c.get("is_player") or c.get("id") == "player"]
        ally_jeans = [c for c in combatants if c.get("is_ally") and c.get("name") == "Jean"]
        if ally_jeans:
            bugs.append(self._bug(
                title="Duplicate Jean in combatants: player appears as both 'player' and 'ally_*'",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/start",
                method="POST",
                expected="Jean listed exactly once (as player, not as ally)",
                actual=f"Jean appears {len(jean_entries)} time(s) as player + {len(ally_jeans)} time(s) as ally: {[c['id'] for c in ally_jeans]}",
                response=resp,
                request_body=body,
            ))

        # Combat loop -------------------------------------------------------
        for round_num in range(1, _MAX_ROUNDS + 1):
            status_bugs, active = self._check_status_endpoint(client, round_num)
            bugs += status_bugs
            if not active:
                break

            # Pick the best available move for this round.
            move_bugs, ended = self._execute_best_move(client, round_num)
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

    def _navigate_to_scenario_tile(self, client: GameClient) -> List[BugReport]:
        """Move from the starting tile to the scenario combat tile.

        Reads the active_scenario from the CONFIG_FILE ini (if set) and
        translates it to a sequence of direction moves.  Falls back to
        the ``fodder`` route when the config is unavailable.
        """
        import configparser
        import os

        scenario = "fodder"
        config_path = os.environ.get("CONFIG_FILE", "")
        if config_path:
            cfg = configparser.ConfigParser()
            try:
                cfg.read(config_path)
                scenario = cfg.get("scenario", "active_scenario", fallback="fodder").strip()
            except Exception:
                pass

        directions = _SCENARIO_NAV.get(scenario, _SCENARIO_NAV["fodder"])
        bugs = []
        for direction in directions:
            body = {"direction": direction}
            resp = client.post("/api/world/move", json=body)
            bug = self._check_status(
                resp, 200, "/api/world/move", "POST",
                f"Arena navigation: move {direction} toward {scenario} tile",
                request_body=body,
            )
            if bug:
                bugs.append(bug)
                break  # stop on first nav failure
        return bugs

    def _find_enemy(self, client: GameClient) -> Optional[str]:
        """Return the first hostile NPC ID from the current room, or None."""
        resp = client.get("/api/world")
        if resp.status_code != 200:
            return None
        data = client.parse(resp)
        room = data.get("room", {})
        npcs = room.get("npcs", [])
        for npc in npcs:
            if isinstance(npc, dict):
                # Skip friendly/ally NPCs
                if npc.get("friend") or npc.get("is_ally"):
                    continue
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
    ) -> Tuple[List[BugReport], bool]:
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

    def _get_available_options(self, client: GameClient) -> List[dict]:
        """Return the current available_options list from combat status."""
        resp = client.get("/api/combat/status")
        if resp.status_code != 200:
            return []
        data = client.parse(resp)
        battle = data.get("battle_state", {})
        return battle.get("available_options", [])

    def _execute_best_move(self, client: GameClient, round_num: int) -> Tuple[List[BugReport], bool]:
        """Pick and execute the best available move for Jean's turn.

        Priority:
        1. First available offensive move with viable targets (attack range).
        2. Advance toward a target if no offensive move is in range.
        3. Wait as a safe fallback.

        Returns (bugs, combat_ended).
        """
        bugs = []
        options = self._get_available_options(client)

        move_index = None
        target_id = None

        # Preference order: offensive → advance → wait
        advance_opt = None
        wait_opt = None
        for opt in options:
            if not opt.get("available"):
                continue
            name = opt.get("name", "")
            category = opt.get("category", "")
            if category == "Offensive" and opt.get("viable_targets"):
                # Ranged or melee attack that has targets in range — use it.
                move_index = opt.get("index")
                target_id = opt["viable_targets"][0]["id"]
                break
            if name == "Advance" and advance_opt is None:
                advance_opt = opt
            if name == "Wait" and wait_opt is None:
                wait_opt = opt

        if move_index is None:
            # No offensive move in range — advance toward enemy.
            chosen = advance_opt or wait_opt
            if chosen:
                move_index = chosen.get("index")
                targets = chosen.get("viable_targets", [])
                if targets:
                    target_id = targets[0]["id"]

        if move_index is None:
            # Nothing usable — skip (shouldn't happen in a healthy combat).
            return bugs, False

        body: dict = {"move_type": "move", "move_id": str(move_index)}
        if target_id:
            body["target_id"] = target_id

        resp = client.post("/api/combat/move", json=body)
        bug = self._check_status(
            resp, 200, "/api/combat/move", "POST",
            f"Execute move (round {round_num})", request_body=body,
        )
        if bug:
            bugs.append(bug)
            return bugs, True  # stop loop on HTTP error

        data = client.parse(resp)
        bugs += self._check_fields(
            data, ["success"],
            "/api/combat/move", "POST",
            f"Move response round {round_num}", resp,
        )

        if not data.get("success") and not data.get("error", "").startswith("Not awaiting"):
            # Log unexpected move failures as medium bugs (not every failure is critical).
            bugs.append(self._bug(
                title=f"Combat move returned success=False (round {round_num}): {data.get('error', '')}",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/move",
                method="POST",
                expected="success=True for a valid available move",
                actual=f"success=False: {data.get('error', data.get('message', ''))}",
                response=resp,
                request_body=body,
            ))

        # Detect combat-ended signals in the response.
        ended = (
            not data.get("combat_active", True)
            or data.get("combat_ended")
            or data.get("victory")
            or data.get("defeated")
        )
        return bugs, bool(ended)
