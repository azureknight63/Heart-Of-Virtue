"""Victory loot — win a fight, walk away, then collect the drops (#610, #621).

Requires the arena config:

    CONFIG_FILE=tests/acceptance/victory-loot/config.ini \
      python tools/bug_hunt.py --scenario victory_loot

Flow:
  1. Stack the Fodder Pit through the test-only debug endpoints: two extra
     Slimes, every enemy aggro and at 1 HP, so the fight is short, and every
     enemy's drop pinned to one ``_PINNED_DROP`` (``/api/debug/arena/loot``,
     #642), so the fight always drops a name Jean also carries.
  2. Fight to victory and read the drops from ``end_state.items_dropped``.
  3. Plant a twin: Jean drops his own object of a dropped name on the fight
     tile (#621).
  4. Provoke a restack there: drop and re-take a bait item. Every pickup
     restacks its floor, and the newer twin would fold INTO the older drop
     unless the fight tile is frozen while the victory is open (#621).
  5. Move one tile away from the fight.
  6. Collect every drop. Each must be delivered — the loot lies on the tile
     the fight ended on, not the one Jean now stands in — and once collected,
     ``/api/combat/status`` must stop serving ``end_state``, or every reload
     re-opens the VICTORY dialog.
  7. Walk back and check, by wire id, that exactly the fight's objects left
     the tile and the twin did not (#621).

Steps 3, 4 and 7 need a twin candidate among the drops. The pinned drop is
one: the config starts Jean carrying a single ``_PINNED_DROP``. A run that
still finds none (the config changed under the scenario) prints that the
identity half was not exercised.
"""

import os
from typing import List, Optional

from .base import ARENA_MAP, Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_ARENA = "Fodder Pit"
_EXTRA_SLIMES = 2
_MAX_ROUNDS = 50
#: Back to the Proving Grounds (0, 0) from the Fodder Pit (1, 0).
_WALK_AWAY = "west"
#: And the return trip.
_BACK_TO_THE_FIGHT = "east"
#: The item class every Fodder Pit enemy is pinned to drop. It must be one
#: the victory-loot config starts Jean carrying exactly one of, so he can plant
#: his own as the twin (steps 3, 4 and 7).
_PINNED_DROP = "Restorative"


class VictoryLootScenario(Scenario):
    name = "victory_loot"
    description = (
        "Win a fight, move one tile, then collect the loot -- and only the "
        "fight's own objects (issues #610, #621)."
    )

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
                    expected=f"Jean at (0, 0) on map {ARENA_MAP!r}",
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
            return bugs

        read_bugs, drop_names = self._read_victory_drops(client)
        bugs += read_bugs
        if drop_names is None:
            return bugs

        # 3. Plant a twin the fight did not drop ---------------------------
        floor_before = self._floor(client)
        fight_drop_ids = {
            item_id: name
            for item_id, name in (floor_before or {}).items()
            if name in drop_names
        }
        twin_id, twin_bugs = self._plant_a_twin(client, drop_names, floor_before)
        bugs += twin_bugs

        # 4. Provoke a restack on the fight tile ---------------------------
        if twin_id is not None:
            bugs += self._provoke_a_restack(client, drop_names)

        # 5. Walk away -----------------------------------------------------
        bug, _ = self._move(client, _WALK_AWAY, "Walk away from the won fight")
        if bug:
            bugs.append(bug)
            return bugs

        # 6. Collect -------------------------------------------------------
        collect_bugs, resolved = self._collect_and_verify(client, drop_names)
        bugs += collect_bugs
        if not resolved:
            return bugs

        # 7. Identity ------------------------------------------------------
        bugs += self._check_only_the_fights_objects_left(
            client, fight_drop_ids, twin_id
        )

        if not drop_names:
            print(
                "[VictoryLootScenario] Nothing dropped this run, so only the "
                "victory resolve was checked, not loot delivery."
            )
        return bugs

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _read_victory_drops(self, client: GameClient):
        """Step 2's read-back: ``(bugs, sorted drop names)`` from the victory
        ``end_state``, or ``(bugs, None)`` when there is no victory to read --
        bugs first, like the other steps."""
        resp = client.get("/api/combat/status")
        bug = self._check_status(resp, 200, "/api/combat/status", "GET",
                                 "Combat status after the victory")
        if bug:
            return [bug], None
        end_state = client.parse(resp).get("end_state") or {}
        if end_state.get("status") != "victory":
            return [self._bug(
                title="No victory end_state after winning a fight",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/status",
                method="GET",
                expected="end_state.status == 'victory' until the loot is resolved",
                actual=f"end_state = {end_state!r}",
                response=resp,
            )], None
        drop_names = sorted({
            d["name"] for d in end_state.get("items_dropped", []) if d.get("name")
        })
        return [], drop_names

    def _collect_and_verify(self, client: GameClient, drop_names):
        """Step 6: collect every drop from one tile away, then check it was
        delivered, is in the inventory, and closed the victory.

        Returns ``(bugs, resolved)``; ``resolved`` is False only when the
        collect request itself failed, which leaves nothing for step 7.
        """
        bugs: List[BugReport] = []
        body = {"item_names": drop_names}
        resp = client.post("/api/combat/collect-loot", json=body)
        bug = self._check_status(resp, 200, "/api/combat/collect-loot", "POST",
                                 "Collect loot after walking away", request_body=body)
        if bug:
            return [bug], False
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
        held, bug = self._inventory_names(client)
        if bug:
            bugs.append(bug)
        missing = [n for n in drop_names if held is not None and n not in held]
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
        bug = self._check_status(resp, 200, "/api/combat/status", "GET",
                                 "Combat status after collect-loot")
        if bug:
            bugs.append(bug)
        elif "end_state" in client.parse(resp):
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
        return bugs, True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _in_the_arena(self, client: GameClient) -> bool:
        room = self._room(client)
        if room is None:
            return False
        return (
            room.get("map_name") == ARENA_MAP
            and (room.get("x"), room.get("y")) == (0, 0)
        )

    def _stack_the_pit(self, client: GameClient) -> List[BugReport]:
        """Add Slimes; every Fodder Pit enemy to 1 HP (aggro) with its drop
        pinned to ``_PINNED_DROP``; restore Jean."""
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
            bug = self._pin_the_drop(client, index)
            if bug:
                return [bug]

        # Jean spawns below his maximum fatigue, and the shared move picker
        # never Rests, so top him up for one swing per enemy (plus misses).
        resp = client.post("/api/debug/player/restore")
        bug = self._check_status(resp, 200, "/api/debug/player/restore", "POST",
                                 "Restore Jean before the fight")
        return [bug] if bug else []

    def _pin_the_drop(self, client: GameClient, index: int) -> Optional[BugReport]:
        """Pin the enemy at ``index`` to drop one ``_PINNED_DROP`` (#642).

        A rolled table can drop only Gold or a random equipment piece, and
        neither has a twin Jean could plant, so an unpinned run could skip the
        identity half entirely.
        """
        body = {"arena": _ARENA, "index": index, "item": _PINNED_DROP}
        resp = client.post("/api/debug/arena/loot", json=body)
        bug = self._check_status(resp, 200, "/api/debug/arena/loot", "POST",
                                 "Pin a Fodder Pit enemy's drop", request_body=body)
        if bug:
            return bug
        if not client.parse(resp).get("success"):
            return self._bug(
                title="Pinning a Fodder Pit enemy's drop was refused",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/debug/arena/loot",
                method="POST",
                expected=f"success pinning {_PINNED_DROP}",
                actual=f"{client.parse(resp)!r}",
                response=resp,
                request_body=body,
            )
        return None

    def _floor(self, client: GameClient) -> Optional[dict]:
        """``{wire id: name}`` for everything on the tile Jean stands on.

        Ids, not names: the whole point of the identity half of this scenario
        is that two objects can share a name (issue #621).
        """
        room = self._room(client)
        if room is None:
            return None
        return {
            i["id"]: i.get("name")
            for i in room.get("items", [])
            if isinstance(i, dict) and i.get("id")
        }

    def _plant_a_twin(self, client: GameClient, drop_names, floor_before):
        """Leave a second object of a dropped name on the fight tile.

        Jean is still standing where the fight ended, and this config starts
        him carrying one each of the level-0 table's consumables, so he drops
        his own — and the tile then holds two objects of one name: the one the
        fight dropped, and one it never did. Collecting that name must move
        the fight's object and leave Jean's.

        Returns ``(twin id, bugs)``. ``(None, [])`` means the setup could not
        be arranged this run — the loot roll is random, and a run that drops
        only Gold (which cannot be dropped) or a random equipment piece has no
        twin candidate. That is not a defect, so it is printed, not reported.
        """
        candidates = {n for n in drop_names if n and n != "Gold"}
        if not candidates or floor_before is None:
            print(
                "[VictoryLootScenario] No twin candidate this run (drops: "
                f"{drop_names}); collect-loot identity not exercised."
            )
            return None, []

        # A single unit: dropping a stack restacks the whole floor, which
        # would merge the twin into the drop instead of leaving it beside it.
        # ``quantity`` is the inventory serializer's spelling of ``count``.
        held, bug = self._inventory_items(client, "Inventory before planting a twin")
        if bug:
            return None, [bug]
        carried = next(
            (
                i
                for i in held
                if isinstance(i, dict)
                and i.get("name") in candidates
                and i.get("quantity") == 1
            ),
            None,
        )
        if carried is None:
            print(
                "[VictoryLootScenario] Jean carries no single spare of a "
                f"dropped name (drops: {drop_names}); identity not exercised."
            )
            return None, []

        body = {"item_id": carried["id"]}
        resp = client.post("/api/inventory/drop", json=body)
        bug = self._check_status(resp, 200, "/api/inventory/drop", "POST",
                                 "Drop the twin on the fight tile", request_body=body)
        if bug:
            return None, [bug]

        planted = [
            item_id
            for item_id, name in (self._floor(client) or {}).items()
            if item_id not in floor_before and name == carried.get("name")
        ]
        if len(planted) != 1:
            print(
                "[VictoryLootScenario] The twin did not land as its own object "
                f"({len(planted)} new of that name); identity not exercised."
            )
            return None, []
        return planted[0], []

    def _walk_back_to_the_fight(self, client: GameClient) -> List[BugReport]:
        bug, _ = self._move(client, _BACK_TO_THE_FIGHT, "Walk back to the fight tile")
        return [bug] if bug else []

    def _check_only_the_fights_objects_left(
        self, client: GameClient, fight_drop_ids: dict, twin_id: Optional[str]
    ) -> List[BugReport]:
        """The collect moved the objects the fight spawned — and only those.

        Resolving a requested name against the tile instead of against the
        fight's own objects handed over whatever of that name was lying there
        (issue #621), which is what the planted twin stands in for.
        """
        if twin_id is None:
            return []
        bugs = self._walk_back_to_the_fight(client)
        if bugs:
            return bugs
        floor_after = self._floor(client)
        if floor_after is None:
            return [self._bug(
                title="The fight tile could not be read back after collect-loot",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world",
                method="GET",
                expected="The fight tile's items, to check which objects left",
                actual="GET /api/world failed",
            )]

        if twin_id not in floor_after:
            bugs.append(self._bug(
                title="collect-loot took an object the fight never dropped",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/collect-loot",
                method="POST",
                expected="Only the objects the fight spawned leave the tile; "
                         "a same-named object Jean left there stays",
                actual=f"the planted twin {twin_id} is gone from the tile",
            ))
        still_there = [i for i in fight_drop_ids if i in floor_after]
        if still_there:
            bugs.append(self._bug(
                title="collect-loot left the fight's own drop behind",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/combat/collect-loot",
                method="POST",
                expected=f"the fight's drops {sorted(fight_drop_ids.values())} collected",
                actual=f"still on the tile: {[fight_drop_ids[i] for i in still_there]}",
            ))
        return bugs

    def _roster(self, client: GameClient) -> Optional[list]:
        resp = client.get("/api/debug/arena")
        if resp.status_code != 200:
            return None
        pit = client.parse(resp).get("rosters", {}).get(_ARENA, {})
        return pit.get("npcs") if pit.get("loaded") else None

    def _inventory_items(self, client: GameClient, why: str):
        """``(items, bug)``: the inventory's item dicts, or ``None`` and the
        bug when the request failed -- a failed request is not an empty pack."""
        resp = client.get("/api/inventory")
        bug = self._check_status(resp, 200, "/api/inventory", "GET", why)
        if bug:
            return None, bug
        items = client.parse(resp).get("inventory", {}).get("items", [])
        return [i for i in items if isinstance(i, dict)], None

    def _inventory_names(self, client: GameClient):
        """``(names, bug)``: the inventory's item names after collect-loot."""
        items, bug = self._inventory_items(client, "Inventory after collect-loot")
        if bug:
            return None, bug
        return {i.get("name") for i in items}, None

    def _provoke_a_restack(self, client: GameClient, drop_names) -> List[BugReport]:
        """Drop a bait item on the fight tile and take it back.

        The take restacks the floor it came from, which is exactly what used
        to fold the twin planted beside the drop INTO the drop (the older
        pile keeps its identity). With the fight tile frozen while the
        victory is open (#621) both stay separate objects, and step 7 checks
        that by wire id. The bait is anything Jean carries whose name the
        fight did not drop, so it cannot itself be mistaken for loot.
        """
        held, bug = self._inventory_items(client, "Inventory before the restack bait")
        if bug:
            return [bug]
        bait = next(
            (i for i in held if i.get("id") and i.get("name") not in drop_names
             and i.get("name") != "Gold"),
            None,
        )
        if bait is None:
            print("[VictoryLootScenario] No bait item to provoke a restack; "
                  "the freeze was not exercised.")
            return []
        body = {"item_id": bait["id"]}
        resp = client.post("/api/inventory/drop", json=body)
        bug = self._check_status(resp, 200, "/api/inventory/drop", "POST",
                                 "Drop the restack bait on the fight tile",
                                 request_body=body)
        if bug:
            return [bug]
        landed = [i for i, name in (self._floor(client) or {}).items()
                  if name == bait.get("name")]
        if not landed:
            return [self._bug(
                title="A dropped item did not land on the fight tile",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/inventory/drop",
                method="POST",
                expected=f"{bait.get('name')} on the floor after dropping it",
                actual="not on the floor",
                request_body=body,
            )]
        body = {"target_id": landed[0], "action": "take"}
        resp = client.post("/api/world/interact", json=body)
        bug = self._check_status(resp, 200, "/api/world/interact", "POST",
                                 "Take the restack bait back", request_body=body)
        return [bug] if bug else []
