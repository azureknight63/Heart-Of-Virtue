"""Regression tests for GitHub issue #547 (note attached to the ticket).

BUG: ``GorranGestureEvent.check_conditions`` only required
``player.previous_tile`` to be non-None. Per its own docstring ("Jean and
Gorran exit Grondia through the Eastern Gate... This is Gorran's first step
into the world beyond the stone city") and the note in
``config_eastern_descent_test.ini`` ("The event fires only when
player.previous_tile carries a Grondia title"), the scene is meant to fire
specifically when the player arrived from Grondia -- but the guard never
checked WHICH map/tile ``previous_tile`` actually pointed at, just that it
was set to *something*.

Verified while reading the code: ``previous_tile`` is set in exactly one
place in the whole engine -- ``GameService.move_player``
(``src/api/services/game_service.py``) -- and is never cleared between
maps. ``Player.teleport()`` (``src/player/_movement.py``) never touches it
at all. So once any move has happened this session, ``previous_tile`` holds
*some* tile forever, regardless of which map the player is currently
wandering. Because this event is one-shot (it sets the
``gorran_gesture_done`` story flag and removes itself), a single incidental
false-positive fire -- triggered by a previous_tile left over from anywhere
else, e.g. the player's own current tile on a same-map revisit, exactly the
shape of the self-reference ``tools/harness/scenarios/ch03_events.py`` used
to poke this event (``player.previous_tile = tile``) -- permanently
consumes the one-shot flag and silently prevents the real scene from ever
playing when the player genuinely does arrive from Grondia later.

Fix: the guard now also checks that ``previous_tile.map`` resolves to a
Grondia map name (``"grondia"`` -- the exact ``grondia.json`` stem the map
loader uses for ``map["name"]`` -- or one of its ``"grondia-*"`` sub-area
maps), not just that *some* previous tile was recorded.
"""

from unittest.mock import MagicMock

import pytest

from src.player import Player
from src.story.ch03 import GorranGestureEvent
from src.tiles import MapTile
from src.universe import Universe


@pytest.fixture
def gate_world():
    """A minimal two-map universe: a Grondia tile and the eastern-descent gate tile.

    Mirrors the real geometry: ``grondia.json``'s Eastern Gate passageway
    teleports the player onto ``eastern-descent.json``'s ``(0, 2)`` tile,
    titled "GrondiaEasternGate" and carrying the ``GorranGestureEvent``.
    """
    player = Player()
    universe = Universe(player=player)

    grondia_map = {"name": "grondia"}
    grondia_tile = MapTile(
        universe, grondia_map, 14, 5, description="The Eastern Gate approach."
    )
    grondia_map[(14, 5)] = grondia_tile

    descent_map = {"name": "eastern-descent"}
    gate_tile = MapTile(
        universe, descent_map, 0, 2, description="Beyond the sealed gate."
    )
    descent_map[(0, 2)] = gate_tile

    universe.maps = [grondia_map, descent_map]
    player.universe = universe
    player.map = descent_map
    player.location_x, player.location_y = 0, 2
    player.current_room = gate_tile

    return player, grondia_tile, gate_tile


def _attach_event(player, gate_tile):
    event = GorranGestureEvent(player, gate_tile, repeat=False)
    event.process = MagicMock()
    gate_tile.events_here = [event]
    return event


class TestGorranGestureEventArrivalGuard:
    def test_fires_when_previous_tile_is_on_grondia(self, gate_world):
        player, grondia_tile, gate_tile = gate_world
        player.previous_tile = grondia_tile
        event = _attach_event(player, gate_tile)

        event.check_conditions()

        event.process.assert_called_once()

    def test_does_not_fire_when_previous_tile_is_not_on_grondia(self, gate_world):
        """The false-positive case: a non-None previous_tile that is NOT
        from Grondia must not fire the scene.

        Before the fix, any truthy previous_tile satisfied the guard --
        this reproduces the harness's own ``player.previous_tile = tile``
        self-reference (tools/harness/scenarios/ch03_events.py), which sits
        on the eastern-descent map, not Grondia.
        """
        player, grondia_tile, gate_tile = gate_world
        player.previous_tile = gate_tile  # same tile/map, NOT Grondia
        event = _attach_event(player, gate_tile)

        event.check_conditions()

        event.process.assert_not_called()

    def test_does_not_fire_when_previous_tile_is_none(self, gate_world):
        """Sanity check: the pre-existing None guard must still hold."""
        player, grondia_tile, gate_tile = gate_world
        player.previous_tile = None
        event = _attach_event(player, gate_tile)

        event.check_conditions()

        event.process.assert_not_called()

    def test_one_shot_flag_is_not_consumed_by_a_non_grondia_fire(self, gate_world):
        """The scenario the issue actually cares about: an early false-positive
        fire must not burn the one-shot ``gorran_gesture_done`` flag, or the
        real scene silently never plays when the player later genuinely
        arrives from Grondia.
        """
        player, grondia_tile, gate_tile = gate_world
        story = player.universe.story

        # First: an incidental, non-Grondia previous_tile (must NOT fire or
        # consume the flag).
        player.previous_tile = gate_tile
        event = _attach_event(player, gate_tile)
        event.check_conditions()
        assert story.get("gorran_gesture_done") != "1"
        assert event in gate_tile.events_here, (
            "a rejected check must leave the one-shot event in place for a "
            "later, legitimate check_conditions() call"
        )

        # Then: the player genuinely arrives from Grondia -- the scene must
        # still be able to fire.
        player.previous_tile = grondia_tile
        event.check_conditions()
        event.process.assert_called_once()
