"""Regression tests for issue #506 — combat-effect events leaking between fights.

``player.combat_events`` is process-wide, was never cleared by any combat
teardown, and persists into saves. The Chapter 1 rumbler chain's gates are pure
global predicates ("no enemies left", "HP under 30%"), so once the player left
that fight by any door other than finishing the chain, the events stayed armed
and fired in whatever unrelated fight came next — spawning rock rumblers in the
wrong room and narrating Gorran's rescue over someone else's fight.

Nothing asserted that a ``combat_effect`` event stops applying once its fight is
over or the player has left its room. These tests do.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.events import Event, purge_orphaned_combat_events, tile_identity
from src.story.ch01 import (
    RUMBLER_FIGHT_FLAG,
    Ch01PostRumbler,
    Ch01PostRumbler2,
    Ch01PostRumbler3,
    Ch01PostRumblerRep,
)


class FakeTile:
    """The minimum of a tile that ``tile_identity`` reads: a map and (x, y)."""

    def __init__(self, x, y, map_name="dark-grotto"):
        self.map = {"name": map_name}
        self.x = x
        self.y = y
        self.npcs_here = []
        self.events_here = []
        self.spawn_npc = MagicMock(return_value=MagicMock())


@pytest.fixture
def rooms():
    """Two rooms in the same map — the armed one and an unrelated one."""
    return FakeTile(3, 4), FakeTile(9, 1)


@pytest.fixture
def player(rooms):
    """A player standing in the armed room, mid-fight, at full health."""
    armed_room, _ = rooms
    p = MagicMock()
    p.current_room = armed_room
    p.combat_list = []
    p.combat_list_allies = []
    p.combat_events = []
    p.universe.story = {}
    p.get_hp_pcnt.return_value = 0.1
    p.completed = False
    return p


def _chain_events(player, tile):
    """One instance of each event in the chain, armed on ``tile``."""
    return [
        Ch01PostRumbler(player=player, tile=tile),
        Ch01PostRumblerRep(player=player, tile=tile),
        Ch01PostRumbler2(player=player, tile=tile),
        Ch01PostRumbler3(player=player, tile=tile),
    ]


class TestTileIdentity:
    def test_identifies_a_positioned_tile_by_map_and_coordinates(self):
        assert tile_identity(FakeTile(3, 4)) == ("dark-grotto", 3, 4)

    def test_same_coordinates_in_different_maps_are_different_rooms(self):
        assert tile_identity(FakeTile(3, 4)) != tile_identity(
            FakeTile(3, 4, map_name="verdette-caverns")
        )

    @pytest.mark.parametrize(
        "tile",
        [None, MagicMock(), FakeTile(None, None)],
        ids=["missing", "test-double", "unpositioned"],
    )
    def test_unidentifiable_tiles_report_unknown_rather_than_guessing(self, tile):
        """``None`` means *unknown*; callers must not treat it as a mismatch."""
        assert tile_identity(tile) is None


class TestChainGates:
    """The chain must only ever fire in the fight that armed it."""

    def test_every_event_fires_in_the_room_it_was_armed_in(self, player, rooms):
        armed_room, _ = rooms
        for event in _chain_events(player, armed_room):
            with patch.object(event, "pass_conditions_to_process") as fired:
                event.check_combat_conditions()
            assert fired.called, f"{event.name} must still fire in its own fight"

    def test_no_event_fires_in_another_room(self, player, rooms):
        armed_room, elsewhere = rooms
        events = _chain_events(player, armed_room)
        player.current_room = elsewhere  # Jean fled and walked off

        for event in events:
            with patch.object(event, "pass_conditions_to_process") as fired:
                event.check_combat_conditions()
            assert not fired.called, f"{event.name} leaked into an unrelated fight"

    def test_no_event_fires_once_the_chain_is_resolved(self, player, rooms):
        armed_room, _ = rooms
        events = _chain_events(player, armed_room)
        player.universe.story[RUMBLER_FIGHT_FLAG] = "0"  # Gorran's rescue ran

        for event in events:
            with patch.object(event, "pass_conditions_to_process") as fired:
                event.check_combat_conditions()
            assert not fired.called, f"{event.name} fired after the chain ended"

    def test_an_unknown_current_room_stays_permissive(self, player, rooms):
        """A save or session that cannot say where Jean is must not soft-lock
        the rescue — the gate blocks only a *positive* mismatch."""
        armed_room, _ = rooms
        player.current_room = None

        for event in _chain_events(player, armed_room):
            with patch.object(event, "pass_conditions_to_process") as fired:
                event.check_combat_conditions()
            assert fired.called, f"{event.name} was disabled by an unknown room"

    def test_a_pre_fix_event_with_no_room_stamp_stays_permissive(
        self, player, rooms
    ):
        """Events unpickled from a save made before #506 carry no stamp."""
        armed_room, elsewhere = rooms
        event = Ch01PostRumbler2(player=player, tile=armed_room)
        del event.origin_tile_key
        player.current_room = elsewhere

        with patch.object(event, "pass_conditions_to_process") as fired:
            event.check_combat_conditions()
        assert fired.called


class TestPurgeOrphanedCombatEvents:
    def test_drops_events_armed_in_a_room_the_player_has_left(self, player, rooms):
        armed_room, elsewhere = rooms
        stale = Event("Stale", player=player, tile=armed_room, combat_effect=True)
        player.combat_events = [stale]
        player.current_room = elsewhere

        assert purge_orphaned_combat_events(player) == [stale]
        assert player.combat_events == []

    def test_keeps_events_armed_in_the_room_the_player_is_in(self, player, rooms):
        """A wave transition re-enters teardown-adjacent code mid-chain."""
        armed_room, _ = rooms
        live = Event("Live", player=player, tile=armed_room, combat_effect=True)
        player.combat_events = [live]

        assert purge_orphaned_combat_events(player) == []
        assert player.combat_events == [live]

    def test_leaves_non_combat_events_alone(self, player, rooms):
        armed_room, elsewhere = rooms
        tile_event = Event("Tile", player=player, tile=armed_room)
        player.combat_events = [tile_event]
        player.current_room = elsewhere

        assert purge_orphaned_combat_events(player) == []

    def test_leaves_events_of_unknown_origin_alone(self, player, rooms):
        _, elsewhere = rooms
        unknown = Event("Unknown", player=player, tile=None, combat_effect=True)
        player.combat_events = [unknown]
        player.current_room = elsewhere

        assert purge_orphaned_combat_events(player) == []

    def test_does_nothing_when_the_current_room_is_unknown(self, player, rooms):
        armed_room, _ = rooms
        stale = Event("Stale", player=player, tile=armed_room, combat_effect=True)
        player.combat_events = [stale]
        player.current_room = None

        assert purge_orphaned_combat_events(player) == []
        assert player.combat_events == [stale]


class TestTriggerCombatEventsScoping:
    """The end-to-end path: ``trigger_combat_events`` runs after every beat."""

    def test_a_leaked_chain_event_is_not_processed_in_another_fight(
        self, game_service, player, rooms
    ):
        armed_room, elsewhere = rooms
        leaked = Ch01PostRumbler2(player=player, tile=armed_room)
        player.combat_events = [leaked]
        player.current_room = elsewhere
        elsewhere.events_here = []

        with patch.object(leaked, "process") as process:
            triggered = game_service.trigger_combat_events(player, session_data={})

        assert triggered == []
        process.assert_not_called()
        elsewhere.spawn_npc.assert_not_called()


class TestFleeClosesTheDoor:
    """Fleeing tore down everything about a fight except ``combat_events``."""

    def test_flee_purges_events_armed_in_other_rooms(
        self, game_service, make_spec_player, rooms
    ):
        armed_room, elsewhere = rooms
        p = make_spec_player(
            in_combat=True,
            combat_list=[],
            combat_events=[],
            current_room=elsewhere,
            states=[],
        )
        p.combat_list_allies = [p]
        stale = Event("Stale", player=p, tile=armed_room, combat_effect=True)
        here = Event("Here", player=p, tile=elsewhere, combat_effect=True)
        p.combat_events = [stale, here]

        result = game_service.flee_combat(p)

        assert result["fled"] is True
        assert p.combat_events == [here]
