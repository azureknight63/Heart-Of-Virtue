"""Ally NPC static progression — exp mirroring, level cap, skill schedule.

Requires the ally-progression config so Gorran starts in the party:

    CONFIG_FILE=tests/acceptance/ally-progression/config.ini \
      python tools/bug_hunt.py --scenario ally_progression

Flow:
  1. Verify Gorran is a party ally with progression enabled and level-synced
     to Jean (the starting_party_members join path calls sync_level).
  2. Raise Jean's level via the debug endpoint and prime Gorran's exp just
     below his next threshold.
  3. Fight to victory in the Fodder Pit.
  4. Assert Gorran banked exp / leveled, never exceeds Jean's level, and the
     level-3 skill-schedule grant (Parry weight 3) applied.
"""

from typing import List, Optional, Tuple

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_MAX_ROUNDS = 50


class AllyProgressionScenario(Scenario):
    name = "ally_progression"
    description = "Ally static progression: exp mirror on victory, level cap, skill schedule."

    def run(self, client: GameClient) -> List[BugReport]:
        import os

        bugs = []

        # This scenario needs its dedicated config (starting_party_members =
        # Gorran on the arena map).  In a full-suite run without it, skip
        # cleanly rather than reporting setup noise as bugs.
        config_path = os.environ.get("CONFIG_FILE", "")
        if "ally-progression" not in config_path:
            print(
                "[AllyProgressionScenario] Skipped — set "
                "CONFIG_FILE=tests/acceptance/ally-progression/config.ini to run."
            )
            return bugs

        # 1. Party + sync-level checks -----------------------------------
        gorran = self._get_gorran(client)
        if gorran is None:
            bugs.append(self._bug(
                title="Gorran not in party — run with CONFIG_FILE=tests/acceptance/ally-progression/config.ini",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/debug/allies",
                method="GET",
                expected="Gorran present in combat_list_allies (starting_party_members)",
                actual="No party ally of class Gorran",
            ))
            return bugs

        if not gorran.get("progression_enabled"):
            bugs.append(self._bug(
                title="Gorran progression disabled (growth_profile missing)",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/debug/allies",
                method="GET",
                expected="progression_enabled=True for Gorran",
                actual=str(gorran),
            ))
            return bugs

        resp = client.get("/api/debug/player")
        player = client.parse(resp)
        jean_level = int(player.get("level", 0))
        if gorran["level"] != jean_level:
            bugs.append(self._bug(
                title="Gorran did not level-sync to Jean on party join",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/debug/allies",
                method="GET",
                expected=f"Gorran level == Jean level ({jean_level})",
                actual=f"Gorran level {gorran['level']}",
            ))

        # 2. Prime: Jean 2 levels ahead, Gorran one landed hit from leveling.
        body = {"level": jean_level + 2, "exp": 0}
        resp = client.post("/api/debug/player/level", json=body)
        bug = self._check_status(resp, 200, "/api/debug/player/level", "POST",
                                 "Raise Jean's level", request_body=body)
        if bug:
            bugs.append(bug)
            return bugs

        primed_exp = max(0, int(gorran["exp_to_level"]) - 5)
        body = {"name": "Gorran", "exp": primed_exp}
        resp = client.post("/api/debug/allies/progression", json=body)
        bug = self._check_status(resp, 200, "/api/debug/allies/progression", "POST",
                                 "Prime Gorran's exp", request_body=body)
        if bug:
            bugs.append(bug)
            return bugs
        pre_fight = self._get_gorran(client)

        # 3. Fight to victory in the Fodder Pit ---------------------------
        fight_bugs, won = self._fight_in_fodder_pit(client)
        bugs += fight_bugs
        if not won:
            bugs.append(self._bug(
                title="Ally progression fight did not reach victory",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/move",
                method="POST",
                expected=f"Victory within {_MAX_ROUNDS} rounds in the Fodder Pit",
                actual="Combat still active or errored — progression asserts skipped",
            ))
            return bugs

        # 4. Post-victory assertions --------------------------------------
        post_fight = self._get_gorran(client)
        if post_fight is None:
            bugs.append(self._bug(
                title="Gorran missing from party after victory",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/debug/allies",
                method="GET",
                expected="Gorran still in combat_list_allies",
                actual="Gorran absent",
            ))
            return bugs

        progressed = (
            post_fight["level"] > pre_fight["level"]
            or post_fight["exp"] > pre_fight["exp"]
        )
        if not progressed:
            bugs.append(self._bug(
                title="Gorran gained no exp from a victory he fought in",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/debug/allies",
                method="GET",
                expected=f"level > {pre_fight['level']} or exp > {pre_fight['exp']}",
                actual=f"level {post_fight['level']}, exp {post_fight['exp']}",
            ))

        resp = client.get("/api/debug/player")
        jean_level = int(client.parse(resp).get("level", 0))
        if post_fight["level"] > jean_level:
            bugs.append(self._bug(
                title="Ally leveled past Jean (level cap violated)",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/debug/allies",
                method="GET",
                expected=f"Gorran level <= Jean level ({jean_level})",
                actual=f"Gorran level {post_fight['level']}",
            ))

        # Skill schedule: at level >= 3 Gorran's Parry weight is raised to 3.
        if post_fight["level"] >= 3:
            parry = next(
                (m for m in post_fight.get("known_moves", []) if m["name"] == "Parry"),
                None,
            )
            if not parry or parry.get("weight") != 3:
                bugs.append(self._bug(
                    title="Gorran's level-3 skill grant (Parry weight 3) not applied",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/debug/allies",
                    method="GET",
                    expected="Parry present with weight 3 at level >= 3",
                    actual=str(parry),
                ))

        return bugs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_gorran(self, client: GameClient) -> Optional[dict]:
        resp = client.get("/api/debug/allies")
        if resp.status_code != 200:
            return None
        data = client.parse(resp)
        for ally in data.get("allies", []):
            if ally.get("class") == "Gorran":
                return ally
        return None

    def _fight_in_fodder_pit(self, client: GameClient) -> Tuple[List[BugReport], bool]:
        """Move east to the Fodder Pit, fight the first enemy to victory."""
        bugs = []
        body = {"direction": "east"}
        resp = client.post("/api/world/move", json=body)
        bug = self._check_status(resp, 200, "/api/world/move", "POST",
                                 "Move to Fodder Pit", request_body=body)
        if bug:
            return [bug], False

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

        for round_num in range(1, _MAX_ROUNDS + 1):
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

    def _find_enemy(self, client: GameClient) -> Optional[str]:
        resp = client.get("/api/world")
        if resp.status_code != 200:
            return None
        room = client.parse(resp).get("room", {})
        for npc in room.get("npcs", []):
            if isinstance(npc, dict):
                if npc.get("friend") or npc.get("is_ally"):
                    continue
                return npc.get("id") or npc.get("npc_id") or npc.get("name")
        return None

    def _execute_move(self, client: GameClient) -> bool:
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

    def _response_ended(self, client: GameClient, resp) -> bool:
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
