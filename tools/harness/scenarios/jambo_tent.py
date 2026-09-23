"""Jambo's tent: first-entry introduction (#664) through the real API.

Drives the crossing a player actually makes -- ``/api/world/interact`` on the
tent's Passageway, then ``/api/world/events/input`` to confirm "Step
through" -- rather than force-attaching the event to a tile and poking
``/api/world/events`` (the ch02/ch03 scenarios' shortcut). The introduction
fires from inside the confirmed teleport, so only this route can show that
its staged conversation actually reaches the client.

Checks, per tent (Grondia's and the nomad camp's):
  1. Entering lands on the tent entrance (2, 2) and the response carries
     staged conversation segments in which Jambo speaks.
  2. ``jambo_shop_intro_done`` is set.
  3. Leaving through the Tent Flap and entering again plays no dialogue.

The camp tent is walked with the gate already set by the Grondia visit, so it
checks the other half of the contract: one introduction covers both tents.

Setup (placing Jean on the tent's exterior tile) is done in-process with
``player.teleport``, the same way the ch02/ch03 scenarios stage their events.
"""

from typing import List, Optional

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_INTRO_GATE = "jambo_shop_intro_done"

#: (label, exterior map, exterior coords, tent map)
_TENTS = (
    ("Grondia", "grondia", (12, 4), "grondia-jambos_shop"),
    ("Nomad Camp", "eastern-descent-nomad-camp", (3, 0), "eastern-descent-jambos-tent"),
)


class JamboTentScenario(Scenario):
    name = "jambo_tent"
    description = (
        "Enter Jambo's tents through the real passageway flow and verify the "
        "first-entry introduction plays once (#664)."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs: List[BugReport] = []

        sm = client._session_manager
        player = sm.get_player(client.session_id)
        universe = getattr(player, "universe", None)
        if universe is None:
            return bugs  # MinimalPlayer: no maps to walk (harness limitation)
        map_names = {m.get("name") for m in universe.maps}
        player.in_combat = False
        player.combat_list = []

        for label, outer_map, exterior, tent_map in _TENTS:
            if outer_map not in map_names or tent_map not in map_names:
                bugs.append(self._bug(
                    title=f"jambo_tent: {label} maps not loaded",
                    severity=BugSeverity.HIGH,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="universe", method="SETUP",
                    expected=f"{outer_map} and {tent_map} in universe.maps",
                    actual=sorted(n for n in map_names if n),
                ))
                continue
            # Arrival beats on the exterior (the camp's) are not under test.
            self._clear_exterior_events(universe, outer_map, exterior)
            player.teleport(outer_map, exterior)
            sm.save_session(client.session_id)
            first_entry = label == "Grondia"

            data = self._cross(client, bugs, "Jambo's Tent", f"{label}: enter tent")
            if data is None:
                continue
            where = (player.map.get("name"), (player.location_x, player.location_y))
            if where != (tent_map, (2, 2)):
                bugs.append(self._bug(
                    title=f"{label}: entering Jambo's Tent landed on the wrong tile",
                    severity=BugSeverity.HIGH,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world/events/input", method="POST",
                    expected=f"{tent_map} (2, 2)", actual=str(where),
                ))
                continue
            speakers = self._speakers(data)
            if first_entry and "Jambo" not in speakers:
                bugs.append(self._bug(
                    title=f"{label}: no Jambo introduction on first entry",
                    severity=BugSeverity.HIGH,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world/events/input", method="POST",
                    expected="staged segments with speaker 'Jambo'",
                    actual=f"speakers={sorted(speakers)}",
                ))
            if not first_entry and speakers:
                bugs.append(self._bug(
                    title=f"{label}: introduction replayed after Jambo was already met",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world/events/input", method="POST",
                    expected="no dialogue", actual=f"speakers={sorted(speakers)}",
                ))
            if universe.story.get(_INTRO_GATE) != "1":
                bugs.append(self._bug(
                    title=f"{label}: story gate '{_INTRO_GATE}' not set",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world/events/input", method="POST",
                    expected="'1'", actual=repr(universe.story.get(_INTRO_GATE)),
                ))

            # Out through the flap and straight back in: nothing replays.
            if self._cross(client, bugs, "Tent Flap", f"{label}: leave tent") is None:
                continue
            again = self._cross(client, bugs, "Jambo's Tent", f"{label}: re-enter tent")
            if again is not None and self._speakers(again):
                bugs.append(self._bug(
                    title=f"{label}: introduction replayed on re-entry",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world/events/input", method="POST",
                    expected="no dialogue",
                    actual=f"speakers={sorted(self._speakers(again))}",
                ))
        return bugs

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clear_exterior_events(universe, map_name, coords):
        area = next(m for m in universe.maps if m.get("name") == map_name)
        area[coords].events_here = []

    def _cross(self, client, bugs, passage_name, label) -> Optional[dict]:
        """Interact with ``passage_name`` on Jean's tile and confirm the
        crossing. Returns the confirmation's response body, or None after
        recording a bug."""
        resp = client.get("/api/world")
        bug = self._check_status(resp, 200, "/api/world", "GET", f"{label}: fetch room")
        if bug:
            bugs.append(bug)
            return None
        objects = client.parse(resp).get("room", {}).get("objects", [])
        target = next((o for o in objects if o.get("name") == passage_name), None)
        if target is None:
            bugs.append(self._bug(
                title=f"{label}: '{passage_name}' not on the current tile",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world", method="GET",
                expected=f"room.objects contains {passage_name!r}",
                actual=[o.get("name") for o in objects],
            ))
            return None
        body = {"target_id": target["id"], "action": "enter"}
        resp = client.post("/api/world/interact", json=body)
        bug = self._check_status(
            resp, 200, "/api/world/interact", "POST", f"{label}: interact", request_body=body
        )
        if bug:
            bugs.append(bug)
            return None
        data = client.parse(resp)
        pending = [
            e for e in (data.get("events_triggered") or data.get("events") or [])
            if e.get("needs_input") and e.get("event_id")
        ]
        if not pending:
            bugs.append(self._bug(
                title=f"{label}: no 'Step through' confirmation armed",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/interact", method="POST",
                expected="a needs_input passageway event", actual=str(data)[:400],
            ))
            return None
        body = {"event_id": pending[0]["event_id"], "user_input": "continue"}
        resp = client.post("/api/world/events/input", json=body)
        bug = self._check_status(
            resp, 200, "/api/world/events/input", "POST", f"{label}: confirm",
            request_body=body,
        )
        if bug:
            bugs.append(bug)
            return None
        return client.parse(resp)

    @staticmethod
    def _speakers(data) -> set:
        """Every speaker in any staged segment anywhere in ``data``."""
        found = set()

        def walk(node):
            if isinstance(node, dict):
                segs = node.get("segments")
                if isinstance(segs, list):
                    for seg in segs:
                        if isinstance(seg, dict) and seg.get("speaker"):
                            found.add(seg["speaker"])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(data)
        return found
