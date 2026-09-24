"""Jambo's tent: wayfinding (#663) and first-entry introduction (#664),
through the real API.

#663 half (runs first):
  a. Ch02GuideToCitadel, driven stage by stage through /api/world/events and
     /api/world/events/input, ends with Jean on the tent's exterior tile,
     grondia (12, 4).
  b. Crossing eastern-descent -> nomad camp through the real passageway plays
     the camp's arrival beats and then the Jambo's-tent notice, in that
     order, and sets ``nomad_camp_jambo_tent_noticed``.

#664 half:

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

from src.story.ch02 import JAMBO_TENT_EXTERIOR, JamboShopIntroEvent  # noqa: E402
from src.story.ch03 import JamboTentNoticeEvent  # noqa: E402

# The engine's own names, so the harness cannot drift from them.
_INTRO_GATE = JamboShopIntroEvent.GATE_KEY
_NOTICE_GATE = JamboTentNoticeEvent.GATE_KEY

#: (label, exterior map, exterior coords, tent map)
_TENTS = (
    ("Grondia", *JAMBO_TENT_EXTERIOR, "grondia-jambos_shop"),
    ("Nomad Camp", "eastern-descent-nomad-camp", (3, 0), "eastern-descent-jambos-tent"),
)


class JamboTentScenario(Scenario):
    name = "jambo_tent"
    description = (
        "Votha Krr and the camp arrival point Jean at Jambo's tent (#663); "
        "entering it plays Jambo's introduction once (#664)."
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

        if "grondia" in map_names:
            self._check_votha_sends_jean_to_the_tent(client, bugs, player, universe)
        if {"eastern-descent", "eastern-descent-nomad-camp"} <= map_names:
            self._check_camp_arrival_points_at_the_tent(client, bugs, player, universe)

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
    # #663
    # ------------------------------------------------------------------

    def _check_votha_sends_jean_to_the_tent(self, client, bugs, player, universe):
        from src.story.ch02 import Ch02GuideToCitadel

        # skip_dialog takes Ch02GuideToCitadel's fast path (no staged
        # segments, no input), which would read as "did not start".
        player.skip_dialog = False
        player.teleport("grondia", (7, 5))
        tile = player.current_room
        tile.events_here = [Ch02GuideToCitadel(player, tile, params=None)]
        client._session_manager.save_session(client.session_id)
        resp = client.post("/api/world/events")
        bug = self._check_status(resp, 200, "/api/world/events", "POST", "Votha: trigger")
        if bug:
            bugs.append(bug)
            return
        pending = [
            e for e in client.parse(resp).get("events", [])
            if e.get("needs_input") and e.get("event_id")
        ]
        if not pending:
            bugs.append(self._bug(
                title="Votha: Ch02GuideToCitadel did not start",
                severity=BugSeverity.HIGH, category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/events", method="POST",
                expected="a needs_input event", actual=str(client.parse(resp))[:400],
            ))
            return
        event, saw_jambo_named = pending[0], False
        for _ in range(12):
            # First offered option each stage (the quest choice takes "a").
            options = event.get("input_options") or [{"value": "continue"}]
            body = {"event_id": event["event_id"], "user_input": options[0]["value"]}
            resp = client.post("/api/world/events/input", json=body)
            bug = self._check_status(
                resp, 200, "/api/world/events/input", "POST", "Votha: advance",
                request_body=body,
            )
            if bug:
                bugs.append(bug)
                return
            data = client.parse(resp)
            if "Jambo" in str(data.get("event", {}).get("segments", "")) or \
                    "Jambo" in str(data.get("segments", "")):
                saw_jambo_named = True
            if not data.get("needs_input"):
                break
            event = data["event"]
        where = (player.map.get("name"), (player.location_x, player.location_y))
        if where != JAMBO_TENT_EXTERIOR:
            bugs.append(self._bug(
                title="Votha: Ch02GuideToCitadel did not leave Jean outside Jambo's tent",
                severity=BugSeverity.HIGH, category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/events/input", method="POST",
                expected=str(JAMBO_TENT_EXTERIOR), actual=str(where),
            ))
        if not saw_jambo_named:
            bugs.append(self._bug(
                title="Votha: farewell never names Jambo",
                severity=BugSeverity.MEDIUM, category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/events/input", method="POST",
                expected="a staged segment mentioning Jambo", actual="none",
            ))

    def _check_camp_arrival_points_at_the_tent(self, client, bugs, player, universe):
        descent = next(m for m in universe.maps if m.get("name") == "eastern-descent")
        found = next(
            (
                (c, o.name)
                for c, t in descent.items()
                if isinstance(c, tuple)
                for o in getattr(t, "objects_here", [])
                if type(o).__name__ == "Passageway"
                and getattr(o, "teleport_map", None) == "eastern-descent-nomad-camp"
            ),
            None,
        )
        if found is None:
            bugs.append(self._bug(
                title="Camp: no eastern-descent passage into the nomad camp",
                severity=BugSeverity.HIGH, category=BugCategory.WRONG_RESPONSE,
                endpoint="universe", method="SETUP",
                expected="a Passageway to eastern-descent-nomad-camp", actual="none",
            ))
            return
        coords, passage_name = found
        player.teleport("eastern-descent", coords)
        client._session_manager.save_session(client.session_id)
        data = self._cross(client, bugs, passage_name, "Camp: arrive")
        if data is None:
            return
        text = str(data)
        liss, sign = text.find("My name's Liss"), text.find("Jambo Heals U")
        if sign == -1 or liss == -1 or sign < liss:
            bugs.append(self._bug(
                title="Camp: Jambo's-tent notice missing or out of order",
                severity=BugSeverity.MEDIUM, category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/events/input", method="POST",
                expected="greeting (Liss) then the 'Jambo Heals U' notice",
                actual=f"liss@{liss} sign@{sign}",
            ))
        if universe.story.get(_NOTICE_GATE) != "1":
            bugs.append(self._bug(
                title=f"Camp: story gate '{_NOTICE_GATE}' not set",
                severity=BugSeverity.MEDIUM, category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/events/input", method="POST",
                expected="'1'", actual=repr(universe.story.get(_NOTICE_GATE)),
            ))

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
