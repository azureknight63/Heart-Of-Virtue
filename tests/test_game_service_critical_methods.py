"""``GameService.move_player`` — the canonical movement tests.

History
-------
``move_player`` was tested in nine separate files, and this one held five of the
weakest copies: ``test_move_player_east``/``_south``/``_west``/``_returns_dict``/
``_with_valid_direction`` each called the method against a ``MagicMock`` universe
whose ``get_tile`` returned the *same* tile for every coordinate, then asserted
``isinstance(result, dict)`` or ``result is not None``. Because the mock answered
every direction identically, none of them could tell "moved east" from "moved
west", and none noticed that the player's position never changed.

This file is now the single home for movement behaviour, driven on a real
3x3 map: position updates, exit gating, ``previous_tile`` bookkeeping (#377),
the mandatory ``universe.game_tick_events()`` call that map-entry spawners
depend on, the stale-chat-marker self-heal (#336), and the negative proof that
walking around does **not** drain combat-move cooldowns.

Weaker duplicates removed elsewhere as part of this consolidation are named in
each class docstring.
"""

import pytest

from src.api.services.game_service import GameService
from src.items import Gold
from tests._gs_fixtures import GRID_3X3, live_world


@pytest.fixture(scope="session")
def game_service():
    """``GameService.__init__`` is ``pass`` — the service is stateless."""
    return GameService()


@pytest.fixture
def world():
    """A real player at the centre of a real 3x3 map."""
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


@pytest.fixture
def game_map(world):
    return world[1]


class TestMoveDirections:
    """Every compass direction lands on the tile it names.

    Replaces ``test_move_player_east``/``_south``/``_west``/``_north``, which
    existed (asserting only ``is not None``) in this file, in
    ``test_game_service_methods.py`` and in ``test_game_service_coverage.py``.
    """

    @pytest.mark.parametrize(
        "direction,expected",
        [
            ("north", (0, -1)),
            ("south", (0, 1)),
            ("east", (1, 0)),
            ("west", (-1, 0)),
            ("northeast", (1, -1)),
            ("northwest", (-1, -1)),
            ("southeast", (1, 1)),
            ("southwest", (-1, 1)),
        ],
    )
    def test_position_updates_to_the_named_neighbour(
        self, game_service, player, game_map, direction, expected
    ):
        result = game_service.move_player(player, direction)

        assert result["success"] is True
        assert result["new_position"] == {"x": expected[0], "y": expected[1]}
        assert (player.location_x, player.location_y) == expected
        assert player.current_room is game_map[expected]

    def test_direction_is_case_insensitive(self, game_service, player):
        assert game_service.move_player(player, "NoRtH")["success"] is True
        assert (player.location_x, player.location_y) == (0, -1)

    def test_room_payload_describes_the_destination(self, game_service, player, game_map):
        game_map[(1, 0)].description = "The eastern ledge."
        room = game_service.move_player(player, "east")["room"]
        assert room["x"] == 1 and room["y"] == 0
        assert room["description"] == "The eastern ledge."

    def test_previous_tile_records_the_tile_left_behind(
        self, game_service, player, game_map
    ):
        """#377: story events gate on ``previous_tile`` to detect arrival."""
        origin = game_map[(0, 0)]
        game_service.move_player(player, "east")
        assert player.previous_tile is origin


class TestMoveRejections:
    """Movement that must not happen, and the exact error each yields.

    Replaces the ``is not None`` invalid-direction copies in
    ``test_game_service_coverage.py`` and ``test_game_service_high_roi.py``;
    the defensive ``universe``/``location`` checks stay in
    ``test_hardening_fixes.py``, which owns that FIX-5 hardening story.
    """

    @pytest.mark.parametrize("direction", ["up", "", "nrth", "northeasterly", "0"])
    def test_unknown_direction_is_rejected_without_moving(
        self, game_service, player, direction
    ):
        result = game_service.move_player(player, direction)
        assert result == {"error": f"Invalid direction: {direction}"}
        assert (player.location_x, player.location_y) == (0, 0)

    def test_no_neighbour_in_that_direction(self, game_service):
        lonely, _ = live_world([(0, 0)])
        assert lonely.location_x == 0
        assert game_service.move_player(lonely, "north") == {
            "error": "Cannot go north from here"
        }
        assert (lonely.location_x, lonely.location_y) == (0, 0)

    def test_blocked_exit_prevents_the_move(self, game_service, player, game_map):
        game_map[(0, 0)].block_exit = ["north"]
        assert game_service.move_player(player, "north") == {
            "error": "Cannot go north from here"
        }
        assert (player.location_x, player.location_y) == (0, 0)
        # A direction that isn't blocked still works.
        assert game_service.move_player(player, "south")["success"] is True

    def test_impassable_destination_is_refused(self, game_service, player, game_map):
        game_map[(1, 0)].is_passable = False
        assert game_service.move_player(player, "east") == {
            "error": "Cannot move east - path is blocked"
        }
        assert (player.location_x, player.location_y) == (0, 0)

    def test_player_off_the_map_cannot_move(self, game_service, player):
        player.location_x, player.location_y = 50, 50
        assert game_service.move_player(player, "north") == {
            "error": "Cannot move from this location"
        }


class TestMoveSideEffects:
    """Everything a move must do besides changing coordinates."""

    def test_game_tick_events_runs_on_every_move(self, game_service, player):
        """Map-entry NPC spawners (e.g. the Lurker) only fire from this call.

        The terminal loop ran ``game_tick_events`` on every action; the API must
        mirror it or spawners never trigger. Asserted on the real universe's tick
        counter rather than a mock call count, so it also proves the *engine* side
        ran (``game_tick`` is incremented inside ``game_tick_events``).
        """
        assert player.universe.game_tick == 0

        game_service.move_player(player, "north")
        assert player.universe.game_tick == 1

        game_service.move_player(player, "south")
        assert player.universe.game_tick == 2

    def test_game_tick_events_failure_does_not_abort_the_move(
        self, game_service, player
    ):
        def boom():
            raise RuntimeError("spawner exploded")

        player.universe.game_tick_events = boom

        result = game_service.move_player(player, "east")

        assert result["success"] is True
        assert (player.location_x, player.location_y) == (1, 0)

    def test_arriving_tile_is_recorded_as_explored(self, game_service, player):
        game_service.move_player(player, "east")
        assert "gs-test-map:1,0" in player.explored_tiles

    def test_stale_active_chat_marker_is_cleared(self, game_service, player):
        """#336: a dialog dismissed without /npc/chat/end must not wedge loquacity."""
        player.__dict__["_active_chat_npc_id"] = "Gorran"
        game_service.move_player(player, "north")
        assert "_active_chat_npc_id" not in player.__dict__

    def test_no_combat_starts_on_an_empty_tile(self, game_service, player):
        result = game_service.move_player(player, "north")
        assert result["combat_started"] is False
        assert result["combat_state"] is None

    def test_destination_events_fire_on_arrival(self, game_service, player, game_map):
        from src.events import Event

        class ArrivalEvent(Event):
            def __init__(self):
                super().__init__(name="Arrival")
                self.fired = 0

            def check_conditions(self):
                self.fired += 1

        event = ArrivalEvent()
        game_map[(1, 0)].events_here = [event]

        result = game_service.move_player(player, "east")

        assert event.fired == 1
        assert [e["name"] for e in result["events_triggered"]] == ["Arrival"]

    def test_origin_events_do_not_fire(self, game_service, player, game_map):
        """Only the tile being *entered* runs its entry events."""
        from src.events import Event

        class OriginEvent(Event):
            def __init__(self):
                super().__init__(name="Origin")
                self.fired = 0

            def check_conditions(self):
                self.fired += 1

        event = OriginEvent()
        game_map[(0, 0)].events_here = [event]

        game_service.move_player(player, "east")

        assert event.fired == 0

    def test_session_state_is_persisted_for_the_new_tile(
        self, game_service, player, game_map
    ):
        game_map[(1, 0)].block_exit = ["north"]
        session_data = {}

        game_service.move_player(player, "east", session_data)

        assert session_data["tile_modifications"]["1,0"]["block_exit"] == ["north"]


class TestCooldownsDoNotDrainOutsideCombat:
    """Move cooldowns tick only on combat beats — never on world actions.

    A drain call on a non-combat path silently corrupts move availability (the
    player finds a move "ready" that should still be recovering, or vice versa).
    Each of these walks a real world action past a move that is mid-cooldown and
    asserts the counter is untouched.
    """

    @staticmethod
    def _arm_cooldown(player, beats=3):
        """Put the player's first real move into a cooldown-like state."""
        move = player.known_moves[0]
        move.current_stage = 3
        move.beats_left = beats
        return move

    def test_moving_does_not_drain_cooldowns(self, game_service, player):
        move = self._arm_cooldown(player)
        game_service.move_player(player, "north")
        assert (move.current_stage, move.beats_left) == (3, 3)

    def test_a_long_walk_does_not_drain_cooldowns(self, game_service, player):
        move = self._arm_cooldown(player, beats=2)
        for direction in ("north", "south", "east", "west", "north", "south"):
            game_service.move_player(player, direction)
        assert move.beats_left == 2

    def test_reading_room_state_does_not_drain_cooldowns(self, game_service, player):
        move = self._arm_cooldown(player)
        game_service.get_current_room(player)
        game_service.get_player_status(player)
        game_service.get_inventory(player)
        assert move.beats_left == 3

    def test_searching_does_not_drain_cooldowns(self, game_service, player):
        move = self._arm_cooldown(player)
        game_service.search(player)
        assert move.beats_left == 3

    def test_dropping_an_item_does_not_drain_cooldowns(self, game_service, player):
        move = self._arm_cooldown(player)
        gold = Gold(amt=5)
        player.inventory.append(gold)
        game_service.drop_item(player, gold)
        assert move.beats_left == 3

    def test_advancing_a_beat_is_what_drains_it(self, game_service, player):
        """The positive control: the drain does exist, on the combat path only.

        ``Move.advance`` is what the combat loop calls once per beat
        (``combat_adapter`` line ~1276, ``for m in player.known_moves``); the
        world paths above must never reach it.
        """
        move = self._arm_cooldown(player)
        player.current_move = move
        move.advance(player)
        assert move.beats_left == 2


class TestServiceHelpers:
    """``_story`` / ``_game_tick`` — universe access without ``self.universe``."""

    def test_story_returns_the_live_story_dict(self, game_service, player):
        player.universe.story["chapter_1_complete"] = True
        assert game_service._story(player) is player.universe.story
        assert game_service._story(player)["chapter_1_complete"] is True

    def test_story_without_a_universe_is_empty(self, game_service, player):
        player.universe = None
        assert game_service._story(player) == {}

    def test_game_tick_reports_the_universe_counter(self, game_service, player):
        player.universe.game_tick = 42
        assert game_service._game_tick(player) == 42

    def test_game_tick_without_a_universe_is_zero(self, game_service, player):
        player.universe = None
        assert game_service._game_tick(player) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
