"""Beta 2's opening, through the real API.

Needs the production config, which is beta 2:

    CONFIG_FILE=config_prod.ini python tools/bug_hunt.py --scenario beta2_start

Checks, in the order a player meets them:
  1. Jean is at the config's starting level (4; tests/test_prod_config.py pins
     it) on the briefing tile, with every point the climb awarded pending and
     the climb's level-ups for the LEVEL UP dialog to list.
  2. Gorran joined level-synced to him.
  3. BetaTesterBriefing fires on the start tile and completes (Continue, Begin).
  4. Spending every point, on strength and endurance (the two that raise a
     maximum), leaves Jean at full health and fatigue.

Under any other config the scenario is skipped: it would be checking a
different start. The route's end, the Ferry Landing, is covered by
tests/test_ferry_demo_end.py and tests/test_prod_config.py.
"""

import os
from typing import List, Optional

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

PROD_CONFIG = "config_prod.ini"
#: The briefing's two stages, answered in order.
BRIEFING_ANSWERS = ("continue", "begin")


class Beta2StartScenario(Scenario):
    name = "beta2_start"
    description = "Beta 2 opening: level-4 start, the briefing, then the player's stat allocation."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs: List[BugReport] = []
        config_file = os.path.basename(os.environ.get("CONFIG_FILE", "").strip("'\""))
        if config_file != PROD_CONFIG:
            print(f"[Beta2StartScenario] Skipped: run with CONFIG_FILE={PROD_CONFIG}.")
            return bugs
        # The level the server loaded, not a copy of it.
        starting_level = client._session_manager.game_config.starting_level

        # 1. The opening state -------------------------------------------
        opening = self._status(client, bugs, "Read the opening state")
        if opening is None:
            return bugs
        points = int(opening.get("pending_attribute_points") or 0)
        level_ups = opening.get("pending_level_ups") or []
        climbed = [level_up.get("new_level") for level_up in level_ups]
        awarded = sum(int(level_up.get("points_awarded") or 0) for level_up in level_ups)
        if opening.get("level") != starting_level or climbed != list(range(2, starting_level + 1)):
            bugs.append(self._wrong(
                "Beta 2 does not open at its starting level with the level-ups listed",
                "/api/full-state", "GET",
                f"level {starting_level}, pending_level_ups for levels 2..{starting_level}",
                f"level {opening.get('level')}, pending_level_ups for {climbed}",
            ))
        if points <= 0 or points != awarded:
            bugs.append(self._wrong(
                "Beta 2's starting points are not all left for the player",
                "/api/full-state", "GET",
                f"pending_attribute_points == points awarded ({awarded}) > 0",
                f"pending_attribute_points {points}",
            ))

        # 2. Gorran ------------------------------------------------------
        gorran = self._gorran(client)
        if gorran is None or gorran.get("level") != starting_level:
            bugs.append(self._wrong(
                "Gorran is not in the party at Jean's starting level",
                "/api/debug/allies", "GET",
                f"Gorran, level {starting_level}",
                "absent" if gorran is None else f"level {gorran.get('level')}",
            ))

        # 3. The briefing ------------------------------------------------
        resp = client.post("/api/world/events")
        bug = self._check_no_crash(resp, "/api/world/events", "POST", "Trigger the start tile's events")
        if bug:
            bugs.append(bug)
            return bugs
        briefing = next(
            (event for event in client.parse(resp).get("events", [])
             if event.get("type") == "BetaTesterBriefing" and event.get("event_id")),
            None,
        )
        if briefing is None:
            bugs.append(self._wrong(
                "BetaTesterBriefing did not fire on beta 2's start tile",
                "/api/world/events", "POST",
                "a BetaTesterBriefing event awaiting input",
                str([event.get("type") for event in client.parse(resp).get("events", [])]),
            ))
            return bugs
        event_id = briefing["event_id"]
        for answer in BRIEFING_ANSWERS:
            body = {"event_id": event_id, "user_input": answer}
            resp = client.post("/api/world/events/input", json=body)
            bug = self._check_status(resp, 200, "/api/world/events/input", "POST",
                                     f"Answer the briefing: {answer}", request_body=body)
            if bug:
                bugs.append(bug)
                return bugs
            data = client.parse(resp)
            event_id = (data.get("event") or {}).get("event_id") or event_id
        if data.get("needs_input"):
            bugs.append(self._wrong(
                "BetaTesterBriefing still wants input after Begin",
                "/api/world/events/input", "POST",
                "needs_input false",
                str(data.get("event")),
            ))

        # 4. The player's allocation -------------------------------------
        if points <= 1:
            return bugs
        for attribute, amount in (("strength_base", points - 1), ("endurance_base", 1)):
            body = {"attribute": attribute, "amount": amount}
            resp = client.post("/api/level-up/allocate", json=body)
            bug = self._check_status(resp, 200, "/api/level-up/allocate", "POST",
                                     f"Spend {amount} on {attribute}", request_body=body)
            if bug:
                bugs.append(bug)
                return bugs
        after = self._status(client, bugs, "Read the state after allocating")
        if after is None:
            return bugs
        if int(after.get("pending_attribute_points") or 0) != 0 or after.get("pending_level_ups"):
            bugs.append(self._wrong(
                "Points or level-ups still pending after spending them all",
                "/api/full-state", "GET",
                "pending_attribute_points 0, pending_level_ups []",
                f"{after.get('pending_attribute_points')}, {after.get('pending_level_ups')}",
            ))
        if not after.get("max_hp", 0) > opening.get("max_hp", 0):
            bugs.append(self._wrong(
                "Spending on strength did not raise max HP",
                "/api/full-state", "GET",
                f"max_hp above {opening.get('max_hp')}",
                f"max_hp {after.get('max_hp')}",
            ))
        if (after.get("hp"), after.get("fatigue")) != (after.get("max_hp"), after.get("max_fatigue")):
            bugs.append(self._wrong(
                "Beta 2 opens below full health after the starting allocation",
                "/api/full-state", "GET",
                "hp == max_hp and fatigue == max_fatigue",
                (f"hp {after.get('hp')}/{after.get('max_hp')}, "
                 f"fatigue {after.get('fatigue')}/{after.get('max_fatigue')}"),
            ))
        return bugs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _status(self, client: GameClient, bugs: List[BugReport], label: str) -> Optional[dict]:
        resp = client.get("/api/full-state")
        bug = self._check_status(resp, 200, "/api/full-state", "GET", label)
        if bug:
            bugs.append(bug)
            return None
        return client.parse(resp).get("status") or {}

    def _gorran(self, client: GameClient) -> Optional[dict]:
        resp = client.get("/api/debug/allies")
        if resp.status_code != 200:
            return None
        return next(
            (ally for ally in client.parse(resp).get("allies", []) if ally.get("class") == "Gorran"),
            None,
        )

    def _wrong(self, title: str, endpoint: str, method: str, expected: str, actual: str) -> BugReport:
        return self._bug(
            title=title,
            severity=BugSeverity.HIGH,
            category=BugCategory.WRONG_RESPONSE,
            endpoint=endpoint,
            method=method,
            expected=expected,
            actual=actual,
        )
