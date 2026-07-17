"""Combat loop checks — start, execute moves, status, log."""

from typing import List, Tuple

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

        # Combat log ----------------------------------------------------------
        # There is no standalone /api/combat/log route — the log is embedded
        # in the /api/combat/status response (see combat_adapter.py:2208).
        resp = client.get("/api/combat/status")
        bug = self._check_status(
            resp, 200, "/api/combat/status", "GET", "Get combat status (for log)"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "log"],
                "/api/combat/status", "GET", "Combat status log field", resp,
            )
            if not isinstance(data.get("log"), list):
                bugs.append(self._bug(
                    title="Combat status: 'log' field is not a list",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/combat/status",
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
            except Exception as e:
                print(f"[CombatScenario] Warning: failed to read CONFIG_FILE={config_path!r}: {e}. Falling back to 'fodder'.")

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

    # _find_enemy is inherited from Scenario (base.py).

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

    def _get_battle_state(self, client: GameClient) -> dict:
        """Return the current battle_state dict from combat status."""
        resp = client.get("/api/combat/status")
        if resp.status_code != 200:
            return {}
        data = client.parse(resp)
        return data.get("battle_state", {})

    def _execute_best_move(self, client: GameClient, round_num: int) -> Tuple[List[BugReport], bool]:
        """Pick and execute the best available move for Jean's turn.

        ``available_options`` changes shape depending on ``input_type``
        (see combat_adapter.py: _handle_move_selection/_handle_target_selection/
        _handle_direction_selection/_handle_number_selection):
          - "move_selection"      -> list[dict] (the normal move menu)
          - "target_selection"    -> list[dict] (viable targets)
          - "direction_selection" -> list[str]  (e.g. ["north", ...])
          - "number_input"        -> dict with "min"/"max"/"default"

        Priority for the normal move menu:
        1. First available offensive move with viable targets (attack range).
        2. Advance toward a target if no offensive move is in range.
        3. Wait as a safe fallback.

        Returns (bugs, combat_ended).
        """
        bugs = []
        battle = self._get_battle_state(client)
        options = battle.get("available_options", [])
        input_type = battle.get("input_type", "move_selection")

        # Sub-stage prompts: a previously selected move may be awaiting a
        # direction, a target, or a numeric value before it executes.
        if input_type == "direction_selection":
            direction = options[0] if isinstance(options, list) and options else "north"
            body = {"move_type": "direction", "direction": direction}
            return self._post_move(client, body, round_num)

        if input_type == "number_input":
            default = options.get("default", 5) if isinstance(options, dict) else 5
            body = {"move_type": "number", "move_id": str(default)}
            return self._post_move(client, body, round_num)

        if input_type == "target_selection":
            targets = [o for o in options if isinstance(o, dict) and o.get("id")]
            if not targets:
                return bugs, False
            body = {"move_type": "target", "target_id": targets[0]["id"]}
            return self._post_move(client, body, round_num)

        # Normal move-selection menu — options should be a list of dicts.
        # A non-dict entry here means the server sent input_type="move_selection"
        # (or "target_selection") but available_options doesn't match that shape
        # (e.g. leftover direction/number strings) — a real API contract
        # violation. Report it instead of silently dropping it, or the harness
        # loses the ability to catch this class of bug entirely.
        clean_options = [o for o in options if isinstance(o, dict)]
        if len(clean_options) != len(options):
            bugs.append(self._bug(
                title=f"available_options contains non-dict entries for input_type={input_type!r}",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/status",
                method="GET",
                expected="available_options is list[dict] when input_type is move_selection/target_selection",
                actual=f"options={options!r}",
            ))
        options = clean_options

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

        return self._post_move(client, body, round_num)

    def _post_move(
        self, client: GameClient, body: dict, round_num: int
    ) -> Tuple[List[BugReport], bool]:
        """POST /api/combat/move with the given body and interpret the result."""
        bugs = []
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
