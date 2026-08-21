"""

Comprehensive test coverage for remaining high-value modules (Tier 4).

Target modules:
- src/universe.py (362 lines, ~70% → 95%+)
- src/combatant.py (91 lines, complete coverage)
- src/interface.py (1377 lines, complete coverage on core methods)
- src/player.py (selected critical methods)

This test file aims for 95%+ coverage on these modules by testing:
1. All public methods with multiple code paths
2. All edge cases and error conditions
3. State transitions and side effects
4. Integration between methods
"""

import pytest
import copy
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call, mock_open
import json
import sys
from io import StringIO

# Set up path for imports

# Import core modules
from src.universe import Universe, tile_exists
from src.combatant import Combatant, _DEFAULT_RESISTANCE, _DEFAULT_STATUS_RESISTANCE
from src.player import Player
from src.npc import NPC
from src.items import Item, Gold
from src.states import State
import src.functions as functions
import src.states as states


class TestCombatantResistances:
    """Test Combatant base class resistance initialization."""

    def test_init_resistances_creates_default_dict(self):
        """Verify _init_resistances() creates all canonical defaults."""
        player = Player()
        assert hasattr(player, 'resistance')
        assert hasattr(player, 'resistance_base')
        assert hasattr(player, 'status_resistance')
        assert hasattr(player, 'status_resistance_base')

        # Check all keys are present
        assert set(player.resistance.keys()) == set(_DEFAULT_RESISTANCE.keys())
        assert set(player.status_resistance.keys()) == set(_DEFAULT_STATUS_RESISTANCE.keys())

    def test_init_resistances_isolation(self):
        """Verify each combatant gets its own resistance dict copy."""
        p1 = Player()
        p2 = Player()

        p1.resistance['fire'] = 0.5
        assert p2.resistance['fire'] == 1.0
        assert p1.resistance is not p2.resistance

    def test_all_resistance_types_present(self):
        """Verify all expected damage types are in resistance dict."""
        player = Player()
        expected_types = {
            'fire', 'ice', 'shock', 'earth', 'light', 'dark',
            'piercing', 'slashing', 'crushing', 'spiritual', 'pure'
        }
        assert expected_types.issubset(set(player.resistance.keys()))

    def test_all_status_types_present(self):
        """Verify all expected status effects are in status_resistance dict."""
        player = Player()
        expected_statuses = {
            'generic', 'stun', 'poison', 'enflamed', 'sloth', 'apathy',
            'blind', 'incoherence', 'mute', 'enraged', 'enchanted',
            'ethereal', 'berserk', 'slow', 'sleep', 'confusion',
            'cursed', 'stop', 'stone', 'frozen', 'doom', 'death', 'disoriented'
        }
        assert expected_statuses.issubset(set(player.status_resistance.keys()))


class TestCombatantMethods:
    """Test Combatant public methods."""

    def test_is_alive_true(self):
        """Test is_alive() returns True when hp > 0."""
        player = Player()
        player.hp = 10
        assert player.is_alive() is True

    def test_is_alive_false(self):
        """Test is_alive() returns False when hp <= 0."""
        player = Player()
        player.hp = 0
        assert player.is_alive() is False

        player.hp = -5
        assert player.is_alive() is False

    def test_is_alive_edge_case_one_hp(self):
        """Test is_alive() at hp boundary."""
        player = Player()
        player.hp = 1
        assert player.is_alive() is True

    def test_cycle_states_ticks_a_real_state_down_and_removes_it_when_spent(self):
        """Out of combat a world state burns `steps_left`, then unregisters."""
        player = Player()
        player.in_combat = False
        player.states = []
        poison = states.Poisoned(player)
        player.states.append(poison)
        poison.steps_max = 2
        poison.steps_left = 2

        player.cycle_states()
        assert poison.steps_left == 1
        assert player.states == [poison]

        player.cycle_states()
        assert poison.steps_left == 0
        assert player.states == []

    def test_cycle_states_empty(self):
        """No states means no work and no crash — the list stays empty."""
        player = Player()
        player.states = []

        player.cycle_states()

        assert player.states == []

    def test_cycle_states_processes_all(self):
        """Test cycle_states() processes each state."""
        player = Player()

        state1 = Mock()
        state1.process = Mock()
        state2 = Mock()
        state2.process = Mock()

        player.states = [state1, state2]
        player.cycle_states()

        state1.process.assert_called_once_with(player)
        state2.process.assert_called_once_with(player)

    def test_cycle_states_uses_snapshot(self):
        """Test cycle_states() uses snapshot to avoid skipped entries."""
        player = Player()

        state1 = Mock()
        state2 = Mock()

        def remove_self(p):
            player.states.remove(state1)

        state1.process = remove_self
        state2.process = Mock()

        player.states = [state1, state2]
        player.cycle_states()

        # state2 should still be called even though state1 removed itself
        state2.process.assert_called_once()

    def test_get_equipped_items_none(self):
        """Test get_equipped_items() with no equipped items."""
        player = Player()
        item1 = Mock()
        item1.isequipped = False
        player.inventory = [item1]

        equipped = player.get_equipped_items()
        assert equipped == []

    def test_get_equipped_items_mixed(self):
        """Test get_equipped_items() with mixed equipped/unequipped."""
        player = Player()

        item1 = Mock()
        item1.isequipped = True
        item2 = Mock()
        item2.isequipped = False
        item3 = Mock()
        item3.isequipped = True

        player.inventory = [item1, item2, item3]

        equipped = player.get_equipped_items()
        assert len(equipped) == 2
        assert item1 in equipped
        assert item3 in equipped

    def test_get_equipped_items_missing_attr(self):
        """Test get_equipped_items() with items lacking isequipped attr."""
        player = Player()

        item1 = Mock(spec=[])  # No isequipped attribute
        item2 = Mock()
        item2.isequipped = True

        player.inventory = [item1, item2]

        equipped = player.get_equipped_items()
        assert len(equipped) == 1
        assert item2 in equipped

    def test_refresh_moves_returns_viable_only(self):
        """Test refresh_moves() returns only viable moves."""
        player = Player()

        move1 = Mock()
        move1.viable = Mock(return_value=True)
        move2 = Mock()
        move2.viable = Mock(return_value=False)
        move3 = Mock()
        move3.viable = Mock(return_value=True)

        player.known_moves = [move1, move2, move3]

        viable = player.refresh_moves()
        assert len(viable) == 2
        assert move1 in viable
        assert move3 in viable

    def test_get_hp_pcnt_full(self):
        """Test get_hp_pcnt() at full health."""
        player = Player()
        player.hp = 100
        player.maxhp = 100

        pcnt = player.get_hp_pcnt()
        assert pcnt == 1.0

    def test_get_hp_pcnt_half(self):
        """Test get_hp_pcnt() at 50% health."""
        player = Player()
        player.hp = 50
        player.maxhp = 100

        pcnt = player.get_hp_pcnt()
        assert pcnt == 0.5

    def test_get_hp_pcnt_zero(self):
        """Test get_hp_pcnt() at 0 HP."""
        player = Player()
        player.hp = 0
        player.maxhp = 100

        pcnt = player.get_hp_pcnt()
        assert pcnt == 0.0

    def test_get_hp_pcnt_over_max(self):
        """Test get_hp_pcnt() when hp exceeds maxhp (temporary buff)."""
        player = Player()
        player.hp = 150
        player.maxhp = 100

        pcnt = player.get_hp_pcnt()
        assert pcnt == 1.5


# ---------------------------------------------------------------------------
# Universe.__init__, tile_exists, get_tile, _deserialize_saved_instance,
# game_tick_events and _evaluate_map_entry_spawners used to be re-tested here,
# weaker than (and duplicating) tests/test_world_systems_tier2.py. Two of those
# copies could not fail at all: test_deserialize_class_type_marker asserted
# `result is not None or result is None`, and four spawner tests asserted
# nothing whatsoever. They now live once, with real assertions, in
# test_world_systems_tier2.py. What is left below is unique to this file.
# ---------------------------------------------------------------------------


class TestUniverseBuild:
    """Test Universe.build method."""

    @patch('src.universe.Universe._load_all_json_maps')
    def test_build_with_save_data(self, mock_load):
        """Test build with save data uses saved maps."""
        u = Universe()
        player = Mock()
        player.saveuniv = [{'name': 'saved_map'}]
        player.savestat = {'key': 'value'}
        player.game_config = None

        u.build(player)

        mock_load.assert_not_called()
        assert u.maps == [{'name': 'saved_map'}]

    @patch('src.universe.Universe._load_all_json_maps')
    def test_build_without_save_data(self, mock_load):
        """A new game loads the JSON maps for this player, not saved ones."""
        u = Universe()
        player = Mock()
        player.saveuniv = None
        player.savestat = None
        player.game_config = None

        mock_load.return_value = 1

        u.build(player)

        mock_load.assert_called_once_with(player)

    @patch('src.universe.Universe._load_all_json_maps')
    def test_build_sets_player(self, mock_load):
        """Test build sets player reference."""
        u = Universe()
        player = Mock()
        player.saveuniv = None
        player.savestat = None
        player.game_config = None

        u.build(player)

        assert u.player is player

    @patch('src.universe.Universe._load_all_json_maps')
    @pytest.mark.parametrize("game_config", [None, False])
    def test_build_leaves_coordinate_config_unset_without_a_game_config(
        self, mock_load, game_config
    ):
        u = Universe()
        player = Mock()
        player.saveuniv = None
        player.savestat = None
        player.game_config = game_config

        u.build(player)

        assert u.coordinate_config is None

    @patch('src.universe.Universe._load_all_json_maps')
    def test_build_derives_a_coordinate_config_from_the_players_game_config(
        self, mock_load
    ):
        """A fresh Universe has coordinate_config None; build() populates it."""
        from src.coordinate_config import CoordinateSystemConfig

        u = Universe()
        player = Mock()
        player.saveuniv = None
        player.savestat = None
        player.game_config = Mock()
        assert u.coordinate_config is None

        u.build(player)

        assert isinstance(u.coordinate_config, CoordinateSystemConfig)


class TestUniverseLoadAllJsonMaps:
    """Test Universe._load_all_json_maps method."""

    @patch('src.universe.Universe._load_single_json_map')
    @patch('src.universe.Universe._json_maps_root_candidates')
    def test_load_all_json_maps_empty_dirs(self, mock_candidates, mock_load_single):
        """Test _load_all_json_maps with empty directories."""
        u = Universe()
        player = Mock()

        mock_candidates.return_value = []

        loaded = u._load_all_json_maps(player)

        assert loaded == 0
        mock_load_single.assert_not_called()

    @patch('src.universe.Universe._load_single_json_map')
    @patch('src.universe.Universe._json_maps_root_candidates')
    def test_load_all_json_maps_exception_handling(self, mock_candidates, mock_load_single):
        """Test _load_all_json_maps continues on exceptions."""
        u = Universe()
        player = Mock()

        # Create a proper mock path that returns sortable Mock objects
        mock_file1 = Mock()
        mock_file1.__lt__ = Mock(return_value=True)
        mock_file2 = Mock()
        mock_file2.__lt__ = Mock(return_value=False)

        mock_root = Mock()
        mock_root.glob.return_value = [mock_file2, mock_file1]
        mock_candidates.return_value = [mock_root]

        mock_load_single.side_effect = Exception("test error")

        # Should not raise
        loaded = u._load_all_json_maps(player)

        assert loaded == 0


# Integration tests combining multiple methods

class TestUniverseIntegration:
    """Integration tests for Universe module."""

    def test_game_tick_event_cycle(self):
        """Test full game tick cycle."""
        u = Universe()
        player = Mock()
        player.refresh_merchants = Mock()
        player.map = {'name': 'test'}
        u.player = player

        for i in range(5):
            u.game_tick_events()

        assert u.game_tick == 5
        player.refresh_merchants.assert_not_called()  # < 1000 ticks

    def test_universe_story_modification(self):
        """Test story dict can be modified."""
        u = Universe()

        u.story['gorran_first'] = '1'
        assert u.story['gorran_first'] == '1'

        u.story['custom_key'] = 'custom_value'
        assert u.story['custom_key'] == 'custom_value'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
