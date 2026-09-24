"""Regression coverage for GitHub issue #582 (Grondia Eastern Gate farewell).

The ticket's diagnosis: the only route from Grondia into eastern-descent is
the "Eastern Gate" Passageway's object teleport, and ``Passageway.
_commit_teleport`` (src/objects.py) supposedly "never evaluates the
destination tile's events_here" -- so ``GorranGestureEvent`` (attached to
eastern-descent's (0, 2) tile, src/story/ch03.py) can never fire, on either
arrival path: not via the teleport (destination events allegedly never
checked) and not via walking in from (1, 2) (correctly rejected by the #547
previous_tile-is-Grondia guard, since that path isn't the farewell).

Investigating against the current code (verification step required before
implementing either of the two suggested fix shapes) shows the diagnosis does
NOT hold here: ``Passageway._commit_teleport`` calls ``player.teleport(...)``
(src/player/_movement.py), and that method has -- since commit 34305386,
"feat: passageway transition with confirmation UI", which predates this
ticket's own QA pass by over a month -- iterated the destination tile's
``events_here`` and called ``check_conditions()`` on each one immediately
after arrival specifically so intro/arrival-gated events fire without
requiring the player to step off and back on. ``GorranGestureEvent`` already
gates on ``previous_tile`` (#547), so it fires correctly through this
existing mechanism on the real Grondia -> Eastern Gate -> eastern-descent
route: confirmed here by loading the real map JSON and driving the actual
``Passageway.enter()`` / ``_commit_teleport()`` crossing, not a synthetic
fixture.

This file exists to close the coverage gap that let the misdiagnosis stand:
neither ``test_issue_547_gorran_gesture_guard.py`` (constructs the event by
hand and calls ``check_conditions()`` directly, never touching a Passageway
or a teleport) nor ``tools/harness/scenarios/ch03_events.py`` (force-attaches
the event to ``tile.events_here`` and calls the API's generic tile-events
endpoint directly, bypassing the Passageway/teleport machinery entirely) ever
exercised the real object-teleport arrival path end to end. If this
mechanism ever regresses (e.g. someone "simplifies" ``Player.teleport()`` and
drops the destination-events loop), this is the test that will fail.
"""

from src.events import set_story_gate
from src.narration import capture_narration
from tests._real_map_helpers import (
    build_universe,
    find_passage_on_map,
)


def _build_universe():
    return build_universe("grondia.json", "eastern-descent.json")


class TestGorranFarewellFiresOnRealEasternGateTeleportArrival:
    def test_fires_when_crossing_the_eastern_gate_from_grondia(self):
        """Reproduces issue #582's steps 1-3 against the real map data: walk
        Grondia (14, 5) -> (15, 5), then cross the Eastern Gate passageway
        (mirrors both the direct ``enter()`` path and the API's
        PassagewayTransitionEvent-confirm path, since both call
        ``Passageway._commit_teleport`` -> ``player.teleport()``). The
        farewell scene must fire and set ``gorran_gesture_done``.
        """
        universe, player = _build_universe()
        grondia = next(m for m in universe.maps if m.get("name") == "grondia")

        leaving_tile = grondia[(14, 5)]
        arrival_tile = grondia[(15, 5)]

        # Mirror GameService.move_player (#377): previous_tile is set to the
        # tile being left, immediately before the position updates.
        player.map = grondia
        player.location_x, player.location_y = 14, 5
        player.current_room = leaving_tile
        player.previous_tile = player.current_room
        player.location_x, player.location_y = 15, 5
        player.current_room = arrival_tile

        found = find_passage_on_map(grondia, "Eastern Gate")
        assert found, "Eastern Gate passage not found on Grondia (15, 5)"
        _, _, passage = found

        # Issue #669: the Eastern Gate now declines until Votha Krr's second
        # conversation has happened (``locked_until_flag`` on the shipped
        # placement). Satisfying that gate is orthogonal to what this test
        # covers -- whether Gorran's farewell fires on arrival -- so it is
        # set directly rather than replayed through ch02's story events.
        set_story_gate(player, passage.locked_until_flag)

        with capture_narration() as messages:
            passage.enter(player)

        assert (player.map.get("name"), (player.location_x, player.location_y)) == (
            "eastern-descent",
            (0, 2),
        )
        assert player.universe.story.get("gorran_gesture_done") == "1"
        narrated_text = " ".join(m["text"] for m in messages)
        assert "Gorran paused at the gate" in narrated_text

    def test_does_not_fire_on_walk_in_from_within_eastern_descent(self):
        """The #547 guard's other half, exercised on the real map data:
        walking (1, 2) -> (0, 2) inside eastern-descent (never having crossed
        the Grondia gate this session) must not fire the scene."""
        universe, player = _build_universe()
        eastern_descent = next(
            m for m in universe.maps if m.get("name") == "eastern-descent"
        )

        gate_tile = eastern_descent[(0, 2)]
        east_tile = eastern_descent[(1, 2)]

        player.map = eastern_descent
        player.location_x, player.location_y = 0, 2
        player.current_room = gate_tile

        # Wander east, then back west -- previous_tile ends up as an
        # eastern-descent tile, never a Grondia one.
        player.previous_tile = player.current_room
        player.location_x, player.location_y = 1, 2
        player.current_room = east_tile
        player.previous_tile = player.current_room
        player.location_x, player.location_y = 0, 2
        player.current_room = gate_tile

        with capture_narration():
            for event in list(gate_tile.events_here):
                event.check_conditions()

        assert player.universe.story.get("gorran_gesture_done") is None
