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

from typing import List, Optional

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

        # 1. Party + sync-level checks -----------------------------------
        # Capability probe: this scenario needs a Gorran party ally
        # (starting_party_members in the dedicated config).  If he's absent,
        # decide by intent: the ally config being active means broken setup
        # (real bug); any other config means this scenario simply isn't
        # provisioned in this run — skip cleanly.
        gorran = self._get_gorran(client)
        if gorran is None:
            config_path = os.environ.get("CONFIG_FILE", "")
            if "ally-progression" in config_path:
                bugs.append(self._bug(
                    title="Gorran not in party despite ally-progression config (starting_party_members broken)",
                    severity=BugSeverity.HIGH,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/debug/allies",
                    method="GET",
                    expected="Gorran present in combat_list_allies (starting_party_members)",
                    actual="No party ally of class Gorran",
                ))
            else:
                print(
                    "[AllyProgressionScenario] Skipped — no Gorran party ally; run with "
                    "CONFIG_FILE=tests/acceptance/ally-progression/config.ini."
                )
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
        fight_bugs, won = self._fight_in_fodder_pit(client, _MAX_ROUNDS)
        bugs += fight_bugs
        if not won:
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
