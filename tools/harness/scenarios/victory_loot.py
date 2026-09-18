"""Victory loot — win a fight, walk away, then collect the drops (issue #610).

Requires the arena config:

    CONFIG_FILE=tests/acceptance/victory-loot/config.ini \
      python tools/bug_hunt.py --scenario victory_loot

Flow:
  1. Stack the Fodder Pit through the test-only debug endpoints: two extra
     Slimes, every enemy aggro and at 1 HP, so the fight is short and at least
     one drop is all but certain (Slime loot is rolled, not scripted).
  2. Fight to victory and read the drops from ``end_state.items_dropped``.
  3. Move one tile away from the fight.
  4. Collect every drop. Each must be delivered — the loot lies on the tile
     the fight ended on, not the one Jean now stands in — and once collected,
     ``/api/combat/status`` must stop serving ``end_state``, or every reload
     re-opens the VICTORY dialog.
"""

import os
from typing import List, Optional

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_ARENA = "Fodder Pit"
_EXTRA_SLIMES = 2
_MAX_ROUNDS = 50
#: Back to the Proving Grounds (0, 0) from the Fodder Pit (1, 0).
_WALK_AWAY = "west"


class VictoryLootScenario(Scenario):
    name = "victory_loot"
    description = "Win a fight, move one tile, then collect the loot (issue #610)."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs: List[BugReport] = []

        # Capability probe: this needs the combat-testing arena. Absent it,
        # decide by intent, as ally_progression does: the dedicated config
        # being active means broken setup; any other config means this
        # scenario simply isn't provisioned in this run.
        if not self._in_the_arena(client):
            if "victory-loot" in os.environ.get("CONFIG_FILE", ""):
                bugs.append(self._bug(
                    title="Victory-loot config did not start Jean in the combat-testing arena",
                    severity=BugSeverity.HIGH,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world",
                    method="GET",
                    expected="Jean at (0, 0) on map 'combat-testing-arena'",
                    actual="Some other map or tile",
                ))
            else:
                print(
                    "[VictoryLootScenario] Skipped: not in the combat-testing arena; "
                    "run with CONFIG_FILE=tests/acceptance/victory-loot/config.ini."
                )
            return bugs

        # 1. Stack the pit -------------------------------------------------
        bugs += self._stack_the_pit(client)
        if bugs:
            return bugs

        # 2. Win -----------------------------------------------------------
        fight_bugs, won = self._fight_in_fodder_pit(client, _MAX_ROUNDS)
        bugs += fight_bugs
        if not won:
            bugs.append(self._bug(
                title="Victory-loot fight did not reach victory",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/move",
                method="POST",
                expected=f"Victory within {_MAX_ROUNDS} rounds in the Fodder Pit",
                actual="Combat still active or errored — loot checks skipped",
            ))
            return bugs

        resp = client.get("/api/combat/status")
        end_state = client.parse(resp).get("end_state") or {}
        if end_state.get("status") != "victory":
            bugs.append(self._bug(
                title="No victory end_state after winning a fight",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/status",
                method="GET",
                expected="end_state.status == 'victory' until the loot is resolved",
                actual=f"end_state = {end_state!r}",
                response=resp,
            ))
            return bugs
        drop_names = sorted({
            d["name"] for d in end_state.get("items_dropped", []) if d.get("name")
        })

        # 3. Walk away -----------------------------------------------------
        body = {"direction": _WALK_AWAY}
        resp = client.post("/api/world/move", json=body)
        bug = self._check_status(resp, 200, "/api/world/move", "POST",
                                 "Walk away from the won fight", request_body=body)
        if bug:
            bugs.append(bug)
            return bugs

        # 4. Collect -------------------------------------------------------
        body = {"item_names": drop_names}
        resp = client.post("/api/combat/collect-loot", json=body)
        bug = self._check_status(resp, 200, "/api/combat/collect-loot", "POST",
                                 "Collect loot after walking away", request_body=body)
        if bug:
            bugs.append(bug)
            return bugs
        result = client.parse(resp)
        collected = set(result.get("collected", []))
        if not result.get("success") or collected != set(drop_names):
            bugs.append(self._bug(
                title="Loot collected after walking away from the fight was not delivered",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/collect-loot",
                method="POST",
                expected=f"success and every drop collected: {drop_names}",
                actual=f"success={result.get('success')!r}, collected={sorted(collected)}, "
                       f"skipped={result.get('skipped')!r}, error={result.get('error')!r}",
                response=resp,
                request_body=body,
            ))

        # Presence only, so a name Jean already carried (his starting Gold)
        # passes regardless; the ``collected`` check above is the real one.
        missing = [n for n in drop_names if n not in self._inventory_names(client)]
        if missing:
            bugs.append(self._bug(
                title="Collected loot is not in the inventory",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/inventory",
                method="GET",
                expected=f"{drop_names} present after collect-loot",
                actual=f"missing {missing}",
            ))

        resp = client.get("/api/combat/status")
        if "end_state" in client.parse(resp):
            bugs.append(self._bug(
                title="A resolved victory still serves end_state (the VICTORY dialog returns on reload)",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/status",
                method="GET",
                expected="No end_state once collect-loot has resolved the victory",
                actual="end_state still present",
                response=resp,
            ))

        if not drop_names:
            print(
                "[VictoryLootScenario] Nothing dropped this run, so only the "
                "victory resolve was checked, not loot delivery."
            )
        return bugs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _in_the_arena(self, client: GameClient) -> bool:
        resp = client.get("/api/world")
        if resp.status_code != 200:
            return False
        room = client.parse(resp).get("room", {})
        return (
            room.get("map_name") == "combat-testing-arena"
            and (room.get("x"), room.get("y")) == (0, 0)
        )

    def _stack_the_pit(self, client: GameClient) -> List[BugReport]:
        """Add Slimes, drop every Fodder Pit enemy to 1 HP (aggro), restore Jean."""
        for _ in range(_EXTRA_SLIMES):
            body = {"arena": _ARENA, "cls_name": "Slime"}
            resp = client.post("/api/debug/arena/add", json=body)
            bug = self._check_status(resp, 200, "/api/debug/arena/add", "POST",
                                     "Add a Slime to the Fodder Pit", request_body=body)
            if bug:
                return [bug]

        roster = self._roster(client)
        if roster is None:
            return [self._bug(
                title="Fodder Pit roster unavailable",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/debug/arena",
                method="GET",
                expected="A loaded Fodder Pit roster",
                actual="Roster missing or not loaded",
            )]
        for index, npc in enumerate(roster):
            if npc.get("friend"):
                continue
            body = {"arena": _ARENA, "index": index,
                    "stats": {"hp": 1, "maxhp": 1, "aggro": True}}
            resp = client.post("/api/debug/arena/stats", json=body)
            bug = self._check_status(resp, 200, "/api/debug/arena/stats", "POST",
                                     "Weaken a Fodder Pit enemy", request_body=body)
            if bug:
                return [bug]

        # Jean spawns below his maximum fatigue, and the shared move picker
        # never Rests, so top him up for one swing per enemy (plus misses).
        resp = client.post("/api/debug/player/restore")
        bug = self._check_status(resp, 200, "/api/debug/player/restore", "POST",
                                 "Restore Jean before the fight")
        return [bug] if bug else []

    def _roster(self, client: GameClient) -> Optional[list]:
        resp = client.get("/api/debug/arena")
        if resp.status_code != 200:
            return None
        pit = client.parse(resp).get("rosters", {}).get(_ARENA, {})
        return pit.get("npcs") if pit.get("loaded") else None

    def _inventory_names(self, client: GameClient) -> set:
        resp = client.get("/api/inventory")
        if resp.status_code != 200:
            return set()
        items = client.parse(resp).get("inventory", {}).get("items", [])
        return {i.get("name") for i in items if isinstance(i, dict)}
