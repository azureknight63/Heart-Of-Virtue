"""Combat loop checks — start, execute moves, status, log."""

from typing import List, Tuple

from .base import ARENA_MAP, Scenario
from ..client import GameClient
from ..move_picker import SUB_STAGE_INPUT_TYPES, pick_move_body
from ..reporter import BugReport, BugSeverity, BugCategory

_MAX_ROUNDS = 20  # safety cap to avoid infinite loops

#: Arena routes from the Proving Grounds (0, 0) to each scenario tile, as
#: ``(direction, arena tile the step enters)``. Tile names are the Adjutant's
#: ``ARENA_TILES`` keys, which the debug roster ops take. The arena has no
#: path to the Crucible that avoids the Fodder Pit, so a route's transit
#: tiles are pacified rather than walked around (#642).
_SCENARIO_NAV = {
    "fodder":       [("east", "Fodder Pit")],
    "boss":         [("east", "Fodder Pit"), ("east", "The Crucible")],
    "ally":         [("south", "Ally Courtyard")],
    "status_dummy": [("south", "Ally Courtyard"), ("east", "Status Chamber")],
    "custom":       [("east", "Fodder Pit")],  # the Fodder Pit, custom roster
}


class CombatScenario(Scenario):
    name = "combat"
    description = "Simulate a full combat encounter: start, moves, status, log."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # Navigate to the scenario's arena tile. The arena starts Jean at
        # (0,0) (Proving Grounds), which only has TheAdjutant — not a valid
        # enemy.
        nav_bugs, started_on_arrival = self._navigate_to_scenario_tile(client)
        bugs += nav_bugs
        if nav_bugs:
            # Navigation failed — fall back to invalid-start check so the
            # harness still exercises the combat API rather than silently passing.
            bugs += self._check_invalid_start(client)
            return bugs

        if started_on_arrival:
            # The tile's aggro roster spotted Jean as he walked in
            # (check_for_combat's stealth roll), so the move itself opened
            # the fight. A move can also report combat_started while a
            # narrative pause holds the fight back; only a live fight counts.
            arrival_bugs, started_on_arrival = self._check_arrival_fight(client)
            bugs += arrival_bugs
        if started_on_arrival:
            print("[CombatScenario] Combat started on arrival; "
                  "driving it without POST /api/combat/start.")
        else:
            start_bugs, started = self._start_combat(client)
            bugs += start_bugs
            if not started:
                return bugs

        # Weapon swap (#671) --------------------------------------------------
        bugs += self._check_weapon_swap(client)

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

    def _start_combat(self, client: GameClient) -> Tuple[List[BugReport], bool]:
        """POST /combat/start against the room's first enemy.

        Returns ``(bugs, started)``. With no enemy in the room it checks that
        a bogus id is rejected gracefully instead, and reports not started.
        """
        bugs = []
        enemy_id = self._find_enemy(client)
        if not enemy_id:
            # No enemy available — verify the API gracefully rejects a bad ID.
            bugs += self._check_invalid_start(client)
            return bugs, False

        body = {"enemy_id": enemy_id}
        resp = client.post("/api/combat/start", json=body)
        bug = self._check_status(
            resp, 201, "/api/combat/start", "POST",
            "Start combat", request_body=body,
        )
        if bug:
            bugs.append(bug)
            return bugs, False

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
        return bugs, True

    def _check_arrival_fight(self, client: GameClient) -> Tuple[List[BugReport], bool]:
        """A fight opened by the arrival move gets the checks POST
        /combat/start would have made: it is live, and Jean appears once.

        Returns ``(bugs, live)``. Not live (a narrative pause) means the caller
        falls back to POST /combat/start, so that path keeps its coverage.
        """
        resp = client.get("/api/combat/status")
        bug = self._check_status(resp, 200, "/api/combat/status", "GET",
                                 "Combat status after a fight opened on arrival")
        if bug:
            return [bug], False
        data = client.parse(resp)
        if not data.get("combat_active"):
            return [], False
        state = data.get("battle_state") or data
        ally_jeans = [a for a in state.get("allies") or [] if a.get("name") == "Jean"]
        if ally_jeans:
            return [self._bug(
                title="Duplicate Jean in combat: player appears as an ally too",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/status",
                method="GET",
                expected="Jean listed only as the player",
                actual=f"Jean appears as ally: {[a.get('id') for a in ally_jeans]}",
                response=resp,
            )], True
        return [], True

    def _active_scenario(self) -> str:
        """``[scenario] active_scenario`` from the CONFIG_FILE ini, else ``fodder``."""
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
        return scenario

    def _in_the_arena(self, client: GameClient) -> bool:
        # The arena routes below are written for ARENA_MAP; on any other map
        # they name nothing, so the scenario fights wherever Jean starts.
        room = self._room(client)
        return room is not None and room.get("map_name") == ARENA_MAP

    def _navigate_to_scenario_tile(
        self, client: GameClient
    ) -> Tuple[List[BugReport], bool]:
        """Walk from the Proving Grounds to the active scenario's arena tile.

        Returns ``(bugs, combat started on arrival)``.

        The routes are arena coordinates, so off the arena map (a config whose
        ``startmap`` is a world map, or the default config) Jean stays where
        he starts. Every tile a route passes THROUGH is pacified first: an
        aggro roster there that spots Jean opens a fight, and the #543 guard
        then refuses the next step. The final step may open the fight itself
        for the same reason; that is reported, not treated as a failure.
        """
        if not self._in_the_arena(client):
            return [], False

        scenario = self._active_scenario()
        route = _SCENARIO_NAV.get(scenario, _SCENARIO_NAV["fodder"])
        bugs = []
        for _direction, transit_tile in route[:-1]:
            bugs += self._pacify(client, transit_tile)
        if bugs:
            return bugs, False

        started = False
        for direction, _tile in route:
            bug, resp = self._move(
                client, direction,
                f"Arena navigation: move {direction} toward {scenario} tile",
            )
            if bug:
                return [bug], False  # stop on first nav failure
            started = bool(client.parse(resp).get("combat_started"))
        return [], started

    def _pacify(self, client: GameClient, arena: str) -> List[BugReport]:
        """Set every hostile on arena tile ``arena`` to non-aggro."""
        resp = client.get("/api/debug/arena")
        bug = self._check_status(resp, 200, "/api/debug/arena", "GET",
                                 f"Arena rosters (to pacify {arena})")
        if bug:
            return [bug]
        roster = client.parse(resp).get("rosters", {}).get(arena, {})
        for index, npc in enumerate(roster.get("npcs", [])):
            if npc.get("friend"):
                continue
            body = {"arena": arena, "index": index, "stats": {"aggro": False}}
            resp = client.post("/api/debug/arena/stats", json=body)
            bug = self._check_status(resp, 200, "/api/debug/arena/stats", "POST",
                                     f"Pacify a {arena} enemy en route",
                                     request_body=body)
            if bug:
                return [bug]
        return []

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

    def _check_weapon_swap(self, client: GameClient) -> List[BugReport]:
        """Mid-combat weapon change goes through the Swap Weapon move (#671).

        Always: the card is offered, and a swap naming a weapon the pack does
        not hold is refused as a game-logic error, not a crash. When the pack
        holds a spare (the arena loadout does): the free /inventory/equip route
        refuses it mid-fight -- otherwise the swap's beat cost is optional --
        and the swap itself then succeeds.
        """
        bugs = []
        options = self._get_battle_state(client).get("available_options", [])
        swap = next(
            (o for o in options if isinstance(o, dict) and o.get("name") == "Swap Weapon"),
            None,
        )
        if swap is None or not isinstance(swap.get("weapon_options"), list):
            bugs.append(self._bug(
                title="Swap Weapon card missing (or has no weapon_options list) in combat",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/status",
                method="GET",
                expected="a 'Swap Weapon' move with a weapon_options list",
                actual=f"swap card: {swap!r}",
            ))
            return bugs

        body = {"move_type": "swap_weapon", "item_id": "not-a-weapon-handle"}
        resp = client.post("/api/combat/move", json=body)
        bug = self._check_no_crash(resp, "/api/combat/move", "POST", "Swap to a bogus weapon", request_body=body)
        if bug:
            bugs.append(bug)
            return bugs
        if client.parse(resp).get("success") is not False:
            bugs.append(self._bug(
                title="Swap Weapon accepted a weapon id not in the pack",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/move",
                method="POST",
                expected="success=False for an item_id outside weapon_options",
                actual=str(client.parse(resp))[:300],
                response=resp,
                request_body=body,
            ))
            return bugs

        choices = swap["weapon_options"]
        if not (swap.get("available") and choices):
            return bugs
        item_id = choices[0].get("id")

        body = {"item_id": item_id}
        resp = client.post("/api/inventory/equip", json=body)
        if resp.status_code != 400:
            bugs.append(self._bug(
                title="Free /inventory/equip changed weapons mid-combat, bypassing Swap Weapon's beat cost",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/inventory/equip",
                method="POST",
                expected="HTTP 400 refusal for a weapon while in combat",
                actual=f"HTTP {resp.status_code}",
                response=resp,
                request_body=body,
            ))
            return bugs

        body = {"move_type": "swap_weapon", "item_id": item_id}
        resp = client.post("/api/combat/move", json=body)
        bug = self._check_status(resp, 200, "/api/combat/move", "POST", "Swap weapon", request_body=body)
        if bug:
            bugs.append(bug)
        elif client.parse(resp).get("success") is not True:
            bugs.append(self._bug(
                title="Swap Weapon refused a weapon it offered",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/move",
                method="POST",
                expected="success=True for an item_id from weapon_options",
                actual=str(client.parse(resp))[:300],
                response=resp,
                request_body=body,
            ))
        return bugs

    def _get_battle_state(self, client: GameClient) -> dict:
        """Return the current battle_state dict from combat status."""
        resp = client.get("/api/combat/status")
        if resp.status_code != 200:
            return {}
        data = client.parse(resp)
        return data.get("battle_state", {})

    def _execute_best_move(self, client: GameClient, round_num: int) -> Tuple[List[BugReport], bool]:
        """Pick and execute the best available move for Jean's turn.

        The choice itself is ``move_picker.pick_move_body`` (the shape of
        ``available_options`` per ``input_type`` and the offensive -> Advance
        -> Wait priority are documented there). This wrapper adds the one check
        the shared picker leaves to its callers: a move menu carrying non-dict
        entries is an API contract violation, reported as a bug.

        Returns (bugs, combat_ended).
        """
        bugs = []
        battle = self._get_battle_state(client)
        options = battle.get("available_options", [])
        input_type = battle.get("input_type", "move_selection")

        # Normal move-selection menu -- options should be a list of dicts.
        # A non-dict entry here means the server sent input_type="move_selection"
        # but available_options doesn't match that shape (e.g. leftover
        # direction/number strings) -- a real API contract violation. Report it
        # instead of silently dropping it, or the harness loses the ability to
        # catch this class of bug entirely.
        if input_type not in SUB_STAGE_INPUT_TYPES:
            if any(not isinstance(o, dict) for o in options):
                bugs.append(self._bug(
                    title=f"available_options contains non-dict entries for input_type={input_type!r}",
                    severity=BugSeverity.HIGH,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/combat/status",
                    method="GET",
                    expected="available_options is list[dict] when input_type is move_selection",
                    actual=f"options={options!r}",
                ))

        body = pick_move_body(battle)
        if body is None:
            # Nothing usable -- skip (shouldn't happen in a healthy combat).
            return bugs, False
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
