"""
Tests for the Chapter 1 Gorran rescue beat (``Ch01PostRumbler3``).

This is a combat-effect event: it fires mid-fight once Jean has cleared the
first wave, then recruits Gorran as an ally and spawns a second wave. Getting
the wiring wrong here is invisible in prose but fatal in play — an ally whose
combat lists point at the wrong rosters attacks nobody, and enemies appended
straight to ``combat_list`` never receive battlefield positions.
"""

from unittest.mock import Mock, patch

import pytest

from src.player import Player
from src.tiles import MapTile
from src.story.ch01 import Ch01PostRumbler3, AfterTheRumblerFight


@pytest.fixture
def player():
    p = Mock(spec=Player)
    p.combat_list = []
    p.combat_list_allies = [p]
    p.in_combat = True
    p.level = 4
    p.current_room = Mock(spec=MapTile)
    p.combat_events = []
    return p


@pytest.fixture
def gorran():
    npc = Mock()
    npc.name = "Gorran"
    npc.in_combat = False
    return npc


@pytest.fixture
def rumblers():
    wave = []
    for i in range(5):
        rumbler = Mock()
        rumbler.name = f"RockRumbler{i}"
        rumbler.in_combat = False
        wave.append(rumbler)
    return wave


@pytest.fixture
def tile(gorran, rumblers):
    t = Mock(spec=MapTile)
    t.spawn_npc = Mock(side_effect=[gorran] + rumblers)
    t.events_here = []
    return t


@pytest.fixture
def event(player, tile):
    return Ch01PostRumbler3(player=player, tile=tile)


def _rescue(event, choice="a"):
    """Run stage 1 (prompt) then stage 2 (the rescue), with I/O stubbed."""
    with (
        patch('src.story.ch01.time.sleep'),
        patch('src.functions.add_enemies_to_combat') as mock_add_enemies,
    ):
        event.process(user_input=None)
        event.process(user_input=choice)
    return mock_add_enemies


class TestRescueWiring:
    def test_stage_one_only_prompts(self, event, player, tile):
        """The first pass must not spawn anything — it just asks the question."""
        with patch('src.story.ch01.time.sleep'):
            event.process(user_input=None)

        assert event.needs_input is True
        assert [o["value"] for o in event.input_options] == ["a"]
        assert "rock-man is still standing" in event.description
        tile.spawn_npc.assert_not_called()
        assert player.combat_list_allies == [player]
        assert event.completed is False

    def test_gorran_joins_the_party_and_shares_the_players_rosters(
        self, event, player, gorran
    ):
        _rescue(event)

        assert gorran in player.combat_list_allies
        assert gorran.in_combat is True
        # Same objects, not copies: Gorran must see the player's live rosters
        # or he will keep swinging at a stale enemy list.
        assert gorran.combat_list is player.combat_list
        assert gorran.combat_list_allies is player.combat_list_allies
        # He arrives scaled to Jean and with a clean move set.
        gorran.sync_level.assert_called_once_with(4)
        gorran.reset_combat_moves.assert_called_once_with()

    def test_second_wave_goes_through_add_enemies_to_combat(
        self, event, player, tile, rumblers
    ):
        """Enemies must be routed through the helper that assigns positions."""
        mock_add_enemies = _rescue(event)

        mock_add_enemies.assert_called_once()
        added_player, added_enemies = mock_add_enemies.call_args[0]
        assert added_player is player
        assert added_enemies == rumblers
        # The event must not shortcut the helper by appending directly.
        assert player.combat_list == []
        assert tile.spawn_npc.call_args_list[0] == (("Gorran",), {"delay": 0})
        assert all(
            c.args == ("RockRumbler",) and "delay" in c.kwargs
            for c in tile.spawn_npc.call_args_list[1:]
        )

    def test_event_retires_and_queues_the_follow_up_scene(
        self, event, player, tile
    ):
        player.combat_events.append(event)

        _rescue(event)

        assert event.completed is True
        assert event.needs_input is False
        # combat_effect events aren't on the tile, so they must clear themselves
        # out of player.combat_events or they re-fire every beat.
        assert event not in player.combat_events
        assert any(
            isinstance(e, AfterTheRumblerFight) for e in tile.events_here
        )

    def test_gorran_already_in_the_party_is_reused_not_duplicated(
        self, player, tile, rumblers
    ):
        """Starting the chapter with Gorran in the party must not clone him."""

        class Gorran:  # name is what the event matches on
            def __init__(self):
                self.in_combat = False
                self.sync_level = Mock()
                self.reset_combat_moves = Mock()

        existing = Gorran()
        player.combat_list_allies = [player, existing]
        tile.spawn_npc = Mock(side_effect=rumblers)

        event = Ch01PostRumbler3(player=player, tile=tile)
        _rescue(event)

        assert player.combat_list_allies == [player, existing]
        assert existing.in_combat is True
        existing.sync_level.assert_called_once_with(4)
        # Only the five rumblers were spawned — no second Gorran.
        assert [c.args[0] for c in tile.spawn_npc.call_args_list] == [
            "RockRumbler"
        ] * 5


class TestRescueTrigger:
    def test_fires_only_once_the_first_wave_is_cleared(self, event, player):
        """The rescue must wait for an empty combat_list, and never re-fire."""
        event.pass_conditions_to_process = Mock()

        player.combat_list = [Mock()]
        event.check_combat_conditions()
        event.pass_conditions_to_process.assert_not_called()

        player.combat_list = []
        event.check_combat_conditions()
        event.pass_conditions_to_process.assert_called_once()

        event.completed = True
        event.check_combat_conditions()
        event.pass_conditions_to_process.assert_called_once()
