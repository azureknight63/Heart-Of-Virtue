"""Base class for all exploration scenarios."""

import json
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class Scenario(ABC):
    name: str = "base"
    description: str = ""

    @abstractmethod
    def run(self, client: GameClient) -> List[BugReport]:
        """Run this scenario and return any bugs found."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_enemy(self, client: "GameClient"):
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

    def _bug(
        self,
        title: str,
        severity: BugSeverity,
        category: BugCategory,
        endpoint: str,
        method: str,
        expected: str,
        actual: str,
        response=None,
        request_body: dict = None,
        traceback: str = "",
    ) -> BugReport:
        status = 0
        body = {}
        if response is not None:
            status = response.status_code
            try:
                body = json.loads(response.data)
            except Exception:
                body = {"_raw": response.data.decode("utf-8", errors="replace")}
        return BugReport(
            title=title,
            severity=severity,
            category=category,
            scenario=self.name,
            endpoint=endpoint,
            method=method,
            expected=expected,
            actual=actual,
            request_body=request_body or {},
            response_status=status,
            response_body=body,
            traceback=traceback,
        )

    def _check_status(
        self,
        response,
        expected_status: int,
        endpoint: str,
        method: str,
        context: str,
        request_body: dict = None,
        severity: BugSeverity = BugSeverity.HIGH,
    ) -> Optional[BugReport]:
        """Return a BugReport if the response status doesn't match."""
        if response.status_code == expected_status:
            return None
        if response.status_code >= 500:
            category = BugCategory.CRASH
            severity = BugSeverity.CRITICAL
        elif response.status_code in (401, 403):
            category = BugCategory.AUTH
        else:
            category = BugCategory.WRONG_RESPONSE
        return self._bug(
            title=f"{context}: expected HTTP {expected_status}, got {response.status_code}",
            severity=severity,
            category=category,
            endpoint=endpoint,
            method=method,
            expected=f"HTTP {expected_status}",
            actual=f"HTTP {response.status_code}",
            response=response,
            request_body=request_body,
        )

    def _check_no_crash(
        self,
        response,
        endpoint: str,
        method: str,
        context: str,
        request_body: dict = None,
    ) -> Optional[BugReport]:
        """Return a HIGH BugReport if the response is a 5xx server crash.

        Use this for endpoints where any non-5xx response (including 400/404)
        is acceptable — the only bug we're hunting is an unhandled exception.
        """
        if response.status_code < 500:
            return None
        try:
            body = json.loads(response.data)
        except Exception:
            body = {"_raw": response.data.decode("utf-8", errors="replace")}
        return BugReport(
            title=f"{context}: server crash (HTTP {response.status_code})",
            severity=BugSeverity.HIGH,
            category=BugCategory.CRASH,
            scenario=self.name,
            endpoint=endpoint,
            method=method,
            expected="HTTP 4xx (graceful rejection)",
            actual=f"HTTP {response.status_code} (server error)",
            request_body=request_body or {},
            response_status=response.status_code,
            response_body=body,
        )

    def _check_rejected(
        self,
        response,
        endpoint: str,
        method: str,
        title: str,
        expected: str,
        allowed: tuple = (400, 422),
        severity: BugSeverity = BugSeverity.LOW,
        request_body: dict = None,
    ) -> Optional[BugReport]:
        """Return a BugReport if a bad/missing-input request wasn't rejected.

        Use this for "missing required field" probes where the endpoint must
        respond with one of ``allowed`` (typically 400/422) rather than
        silently accepting the request or crashing.
        """
        if response.status_code in allowed:
            return None
        return self._bug(
            title=title,
            severity=severity,
            category=BugCategory.WRONG_RESPONSE,
            endpoint=endpoint,
            method=method,
            expected=expected,
            actual=f"HTTP {response.status_code}",
            response=response,
            request_body=request_body,
        )

    def _check_fields(
        self,
        data: dict,
        required_fields: List[str],
        endpoint: str,
        method: str,
        context: str,
        response=None,
    ) -> List[BugReport]:
        """Return BugReports for any missing required fields."""
        bugs = []
        for f in required_fields:
            if f not in data:
                bugs.append(
                    self._bug(
                        title=f"{context}: missing field '{f}'",
                        severity=BugSeverity.MEDIUM,
                        category=BugCategory.MISSING_FIELD,
                        endpoint=endpoint,
                        method=method,
                        expected=f"Response includes '{f}'",
                        actual=f"'{f}' absent. Keys present: {sorted(data.keys())}",
                        response=response,
                    )
                )
        return bugs

    # ------------------------------------------------------------------
    # Arena combat: fight a Fodder Pit enemy to victory
    # ------------------------------------------------------------------

    def _fight_in_fodder_pit(
        self, client: "GameClient", max_rounds: int
    ) -> Tuple[List[BugReport], bool]:
        """Move east to the Fodder Pit, fight the first enemy to victory.

        Assumes the combat-testing arena with the player on the Proving
        Grounds (0, 0). Returns ``(bugs, won)``.
        """
        bugs = []
        body = {"direction": "east"}
        resp = client.post("/api/world/move", json=body)
        bug = self._check_status(resp, 200, "/api/world/move", "POST",
                                 "Move to Fodder Pit", request_body=body)
        if bug:
            return [bug], False

        # An aggro enemy can spot Jean on the way in and start the fight
        # itself; /api/combat/start then answers 200, not 201.
        started = client.parse(client.get("/api/combat/status")).get("combat_active")
        if not started:
            enemy_id = self._find_enemy(client)
            if not enemy_id:
                bugs.append(self._bug(
                    title="No enemy found in the Fodder Pit",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world",
                    method="GET",
                    expected="Slime/CaveBat present at (1, 0)",
                    actual="No hostile NPCs in room",
                ))
                return bugs, False

            body = {"enemy_id": enemy_id}
            resp = client.post("/api/combat/start", json=body)
            bug = self._check_status(resp, 201, "/api/combat/start", "POST",
                                     "Start combat", request_body=body)
            if bug:
                return [bug], False

        for round_num in range(1, max_rounds + 1):
            resp = client.get("/api/combat/status")
            if resp.status_code != 200:
                bugs.append(self._check_status(
                    resp, 200, "/api/combat/status", "GET",
                    f"Combat status (round {round_num})"))
                return bugs, False
            data = client.parse(resp)
            if not data.get("combat_active"):
                return bugs, True
            ended = self._execute_move(client)
            if ended:
                return bugs, True
        return bugs, False

    def _execute_move(self, client: "GameClient") -> bool:
        """Execute the best available move. Returns True when combat ended."""
        resp = client.get("/api/combat/status")
        if resp.status_code != 200:
            return True
        battle = client.parse(resp).get("battle_state", {})
        options = battle.get("available_options", [])
        input_type = battle.get("input_type", "move_selection")

        # Multi-step prompts: a previously chosen move may be awaiting a
        # number (Wait duration — options is a dict), a direction (options is
        # a list of strings), or a target (options is a list of target dicts).
        if input_type == "number_input":
            default = options.get("default", 5) if isinstance(options, dict) else 5
            resp = client.post(
                "/api/combat/move",
                json={"move_type": "number", "move_id": str(default)},
            )
            return self._response_ended(client, resp)
        if input_type == "direction_selection":
            direction = options[0] if options else "north"
            resp = client.post(
                "/api/combat/move",
                json={"move_type": "direction", "direction": direction},
            )
            return self._response_ended(client, resp)
        if input_type == "target_selection":
            targets = [o for o in options if isinstance(o, dict) and o.get("id")]
            if not targets:
                return False
            resp = client.post(
                "/api/combat/move",
                json={"move_type": "target", "target_id": targets[0]["id"]},
            )
            return self._response_ended(client, resp)

        options = [o for o in options if isinstance(o, dict)]
        move_index = None
        target_id = None
        advance_opt = None
        wait_opt = None
        for opt in options:
            if not opt.get("available"):
                continue
            if opt.get("category") == "Offensive" and opt.get("viable_targets"):
                move_index = opt.get("index")
                target_id = opt["viable_targets"][0]["id"]
                break
            if opt.get("name") == "Advance" and advance_opt is None:
                advance_opt = opt
            if opt.get("name") == "Wait" and wait_opt is None:
                wait_opt = opt

        if move_index is None:
            chosen = advance_opt or wait_opt
            if chosen is None:
                return False
            move_index = chosen.get("index")
            targets = chosen.get("viable_targets", [])
            if targets:
                target_id = targets[0]["id"]

        body: dict = {"move_type": "move", "move_id": str(move_index)}
        if target_id:
            body["target_id"] = target_id
        resp = client.post("/api/combat/move", json=body)
        return self._response_ended(client, resp)

    def _response_ended(self, client: "GameClient", resp) -> bool:
        """True when the move response signals combat has ended (or errored)."""
        if resp.status_code != 200:
            return True
        data = client.parse(resp)
        return bool(
            not data.get("combat_active", True)
            or data.get("combat_ended")
            or data.get("victory")
            or data.get("defeated")
        )
