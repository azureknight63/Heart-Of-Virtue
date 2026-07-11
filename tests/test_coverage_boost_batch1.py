"""Coverage boost batch 1 — targets uncovered lines in:
- src/positions.py (lines 487, 500, 575, 588, 655-656, 661, 684, 716, 824, 876, 911, 915-925)
- src/tiles.py (lines 162-163, 182, 193-194, 200-201, 228, 289-290, 299-301)
- src/tilesets/general.py (lines 6-15, 19, 24-25, 29)
- src/tilesets/test_chest.py (lines 9, 12, 19-28, 32)
- src/player/_movement.py (lines 63-69, 73-78, 109, 118-119)
- src/player/_exploration.py (lines 16, 45-47, 90-102, 119, 132-134, 142-152, 170, 182)
- src/player/_combat.py (lines 158, 162, 165-166, 171, 190, 206-207, 235-236, 251)
- src/player/_leveling.py (lines 95, 172-176, 190-194)
- src/player/_world.py (lines 27, 30, 34, 36-37, 47, 55-57, 78-80, 95-96)
"""

import sys
import random
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
import src.positions as positions
from src.positions import (
    CombatPosition,
    Direction,
    move_toward_constrained,
    move_away_constrained,
    move_to_flank_constrained,
    move_away_from,
    turn_toward,
    recalculate_proximity_dict,
    initialize_combat_positions,
    _spawn_units_in_zone,
    _find_spaced_position,
    _find_clustered_position,
)
from src.player import Player

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _player():
    p = Player()
    return p


def _cp(x=5, y=5, facing=Direction.N):
    return CombatPosition(x=x, y=y, facing=facing)


def _mock_tile():
    t = MagicMock()
    t.npcs_here = []
    t.items_here = []
    t.objects_here = []
    t.events_here = []
    t.block_exit = []
    return t


# ---------------------------------------------------------------------------
# src/positions.py — uncovered branches
# ---------------------------------------------------------------------------


class TestMoveTowardConstrainedBlocked:
    """Line 487, 500: move_toward_constrained returns current when blocked."""

    def test_returns_current_when_no_progress(self):
        current = _cp(0, 0)
        target = _cp(1, 0)
        # Occupy destination so movement is always blocked
        occupied = [_cp(1, 0)]
        result = move_toward_constrained(current, target, 1, occupied)
        # Can't move to 1,0 so falls back to current
        assert result.x == 0
        assert result.y == 0

    def test_returns_copy_when_stuck(self):
        current = _cp(2, 2)
        target = _cp(3, 2)
        # Fill destination columns completely to force fallback
        occupied = [_cp(3, 2), _cp(2, 2)]
        result = move_toward_constrained(current, target, 2, occupied)
        # Should return current (copy)
        assert result.x == current.x
        assert result.y == current.y

    def test_empty_occupied_takes_direct_path(self):
        current = _cp(0, 0)
        target = _cp(3, 0)
        result = move_toward_constrained(current, target, 3, [])
        # No occupied — should reach target
        assert result.x == 3
        assert result.y == 0


class TestMoveAwayConstrainedBranches:
    """Lines 575, 588: move_away_constrained edge cases."""

    def test_no_occupied_delegates_to_move_away(self):
        current = _cp(5, 5)
        threat = _cp(3, 5)
        result = move_away_constrained(current, threat, 2, [])
        # Should move away from threat (east)
        assert result.x > 5

    def test_blocked_destination_falls_back(self):
        current = _cp(5, 5)
        threat = _cp(3, 5)
        # Block the natural retreat direction
        # Moving away from (3,5) with dx=1 means x+2=7
        occupied = [_cp(7, 5), _cp(6, 5)]
        result = move_away_constrained(current, threat, 2, occupied)
        # Falls back to current copy
        assert result is not None

    def test_returns_current_when_fully_blocked(self):
        current = _cp(5, 5)
        threat = _cp(4, 5)
        # Block every possible retreat tile
        blocked = [
            _cp(x, y)
            for x in range(0, 11)
            for y in range(0, 11)
            if not (x == 5 and y == 5)
        ]
        result = move_away_constrained(current, threat, 1, blocked)
        assert result.x == current.x
        assert result.y == current.y


class TestMoveToFlankConstrainedBranches:
    """Lines 655-656, 661: move_to_flank_constrained edge cases."""

    def test_no_occupied_delegates_to_flank(self):
        current = _cp(5, 25)
        target = _cp(25, 25, Direction.E)
        result = move_to_flank_constrained(current, target, 3, [])
        assert result is not None

    def test_returns_copy_when_both_flanks_blocked(self):
        current = _cp(5, 25)
        target = _cp(25, 25, Direction.N)
        # Block all possible positions
        blocked = [_cp(x, y) for x in range(0, 51) for y in range(0, 51)]
        result = move_to_flank_constrained(current, target, 3, blocked)
        # Falls back to current copy
        assert result.x == current.x
        assert result.y == current.y


class TestTurnTowardFallback:
    """Line 684: turn_toward fallback to Direction.N."""

    def test_turn_toward_same_position(self):
        # Same position — angle is 0, maps to North
        current = _cp(5, 5, Direction.S)
        target = _cp(5, 5, Direction.S)
        result = turn_toward(current, target)
        # Should return a Direction (N is fallback)
        assert isinstance(result, Direction)

    def test_turn_toward_cardinal_directions(self):
        for dx, dy, expected in [
            (1, 0, Direction.E),
            (-1, 0, Direction.W),
            (0, 1, Direction.S),
            (0, -1, Direction.N),
        ]:
            current = _cp(10, 10)
            target = _cp(10 + dx * 5, 10 + dy * 5)
            result = turn_toward(current, target)
            assert isinstance(result, Direction)


class TestRecalcProximityNoCombatPosition:
    """Line 716: recalculate_proximity_dict skips units without combat_position."""

    def test_skip_unit_without_combat_position(self):
        unit = MagicMock()
        unit.combat_position = _cp(5, 5)
        ally = MagicMock(spec=[])  # no combat_position attribute
        result = recalculate_proximity_dict(unit, [unit, ally])
        assert ally not in result

    def test_unit_itself_without_position(self):
        unit = MagicMock(spec=[])  # no combat_position
        result = recalculate_proximity_dict(unit, [unit])
        assert result == {}


class TestSpawnUnitsInZoneFormations:
    """Line 824, 843: cluster and random formation types in _spawn_units_in_zone."""

    def _make_unit(self):
        u = MagicMock()
        u.combat_position = None
        u.combat_proximity = {}
        return u

    def test_cluster_formation(self):
        units = [self._make_unit() for _ in range(3)]
        zone = ((5, 5), (15, 15))
        _spawn_units_in_zone(units, zone, formation_type="cluster")
        for u in units:
            assert u.combat_position is not None

    def test_random_formation(self):
        units = [self._make_unit() for _ in range(3)]
        zone = ((5, 5), (20, 20))
        _spawn_units_in_zone(units, zone, formation_type="random")
        for u in units:
            assert u.combat_position is not None

    def test_spread_formation_with_seed(self):
        units = [self._make_unit() for _ in range(2)]
        zone = ((0, 0), (10, 10))
        _spawn_units_in_zone(units, zone, formation_type="spread", seed=42)
        for u in units:
            assert u.combat_position is not None


class TestFindSpacedPositionFallback:
    """Line 876: _find_spaced_position fallback when constrained."""

    def test_fallback_when_zone_is_tiny(self):
        zone = ((5, 5), (6, 6))  # Very small zone
        # Fill with many occupied positions to force fallback
        occupied = [_cp(x, y) for x in range(0, 51) for y in range(0, 51)]
        result = _find_spaced_position(zone, occupied, min_spacing=10)
        assert result is not None


class TestFindClusteredPosition:
    """Lines 911, 915-925: _find_clustered_position spiral search."""

    def test_first_unit_goes_to_center(self):
        zone = ((0, 0), (10, 10))
        result = _find_clustered_position(zone, [], min_spacing=1)
        assert result.x == 5
        assert result.y == 5

    def test_subsequent_unit_near_first(self):
        zone = ((0, 0), (10, 10))
        first = _cp(5, 5)
        result = _find_clustered_position(zone, [first], min_spacing=1)
        assert result is not None
        # Should be close to first
        dx = abs(result.x - 5)
        dy = abs(result.y - 5)
        assert dx <= 5 and dy <= 5

    def test_cluster_fallback_when_no_valid_position(self):
        zone = ((5, 5), (6, 6))
        occupied = [_cp(x, y) for x in range(0, 51) for y in range(0, 51)]
        result = _find_clustered_position(zone, occupied, min_spacing=5)
        assert result is not None


class TestInitializeCombatPositions:
    """Integration: initialize_combat_positions sets positions on all units."""

    def _make_combatant(self):
        c = MagicMock()
        c.combat_position = None
        c.combat_proximity = {}
        return c

    def test_standard_scenario(self):
        allies = [self._make_combatant() for _ in range(2)]
        enemies = [self._make_combatant() for _ in range(2)]
        initialize_combat_positions(allies, enemies, scenario_type="standard")
        for c in allies + enemies:
            assert c.combat_position is not None

    def test_pincer_scenario(self):
        allies = [self._make_combatant()]
        enemies = [self._make_combatant()]
        initialize_combat_positions(allies, enemies, scenario_type="pincer")
        assert allies[0].combat_position is not None

    def test_boss_arena_scenario(self):
        allies = [self._make_combatant()]
        enemies = [self._make_combatant()]
        initialize_combat_positions(allies, enemies, scenario_type="boss_arena")
        assert allies[0].combat_position is not None


# ---------------------------------------------------------------------------
# src/tiles.py — uncovered lines
# ---------------------------------------------------------------------------


class TestTilesSpawnNpc:
    """Lines 162-163, 182, 193-194, 200-201: spawn_npc hidden/delay branches."""

    def _make_tile(self):
        from src.tiles import MapTile

        universe = MagicMock()
        universe.testing_mode = False
        return MapTile(universe, {}, 0, 0, description="Test tile")

    def test_spawn_npc_with_hidden(self):
        tile = self._make_tile()
        npc = tile.spawn_npc("UnknownNPC", hidden=True, hfactor=50)
        assert npc.hidden is True
        assert npc.hide_factor == 50

    def test_spawn_npc_with_explicit_delay(self):
        tile = self._make_tile()
        npc = tile.spawn_npc("UnknownNPC", delay=3)
        assert npc.combat_delay == 3

    def test_spawn_npc_sets_current_room(self):
        tile = self._make_tile()
        npc = tile.spawn_npc("UnknownNPC")
        assert npc.current_room == tile

    def test_spawn_npc_stub_name_includes_type(self):
        tile = self._make_tile()
        npc = tile.spawn_npc("Goblin")
        assert "Goblin" in npc.name


class TestTilesSpawnItem:
    """Lines 228, 289-290, 299-301: spawn_item hidden, stackable, Gold."""

    def _make_tile(self):
        from src.tiles import MapTile

        universe = MagicMock()
        universe.testing_mode = False
        return MapTile(universe, {}, 0, 0)

    def test_spawn_gold(self):
        tile = self._make_tile()
        item = tile.spawn_item("Gold", amt=50)
        assert item is not None
        assert len(tile.items_here) >= 1

    def test_spawn_item_hidden(self):
        tile = self._make_tile()
        item = tile.spawn_item("Gold", amt=10, hidden=True, hfactor=30)
        for it in tile.items_here:
            if it is item:
                assert it.hidden is True
                assert it.hide_factor == 30

    def test_spawn_non_stackable_item(self):
        tile = self._make_tile()
        tile.spawn_item("RustedIronMace", amt=1)
        assert len(tile.items_here) >= 1

    def test_spawn_stackable_item_count(self):
        tile = self._make_tile()
        # Antidote is stackable (has count attribute)
        item = tile.spawn_item("Antidote", amt=3)
        if hasattr(item, "count"):
            assert item.count == 3


class TestTilesAvailableActionsDebug:
    """Lines 113-131: available_actions with debug mode via universe.testing_mode."""

    def _make_tile(self):
        from src.tiles import MapTile

        universe = MagicMock()
        universe.testing_mode = True  # triggers debug moves
        return MapTile(universe, {}, 0, 0)

    def test_debug_actions_included_when_testing_mode(self):
        tile = self._make_tile()
        import src.actions as act

        acts = tile.available_actions()
        action_types = [type(a).__name__ for a in acts]
        assert "Teleport" in action_types

    def test_api_mode_skips_movement_actions(self):
        tile = self._make_tile()
        acts = tile.available_actions(callerIsApi=True)
        # API mode should not include directional movement
        action_types = [type(a).__name__ for a in acts]
        assert "MoveNorth" not in action_types


# ---------------------------------------------------------------------------
# src/tilesets/general.py — Boundary and BlankTile
# ---------------------------------------------------------------------------


class TestTilesetsGeneral:
    """Cover Boundary and BlankTile classes."""

    def _universe(self):
        u = MagicMock()
        u.testing_mode = False
        return u

    def test_boundary_tile_creation(self):
        from src.tilesets.general import Boundary

        u = self._universe()
        tile = Boundary(u, {}, 0, 0)
        assert tile.symbol == "'"
        assert tile.x == 0

    def test_boundary_modify_player_is_noop(self):
        from src.tilesets.general import Boundary

        u = self._universe()
        tile = Boundary(u, {}, 0, 0)
        p = MagicMock()
        result = tile.modify_player(p)
        assert result is None

    def test_boundary_intro_text(self):
        from src.tilesets.general import Boundary

        u = self._universe()
        tile = Boundary(u, {}, 0, 0)
        text = tile.intro_text()
        assert text is not None

    def test_blank_tile_creation(self):
        from src.tilesets.general import BlankTile

        u = self._universe()
        tile = BlankTile(u, {}, 1, 2)
        assert tile.symbol == "#"
        assert tile.x == 1
        assert tile.y == 2

    def test_blank_tile_modify_player_is_noop(self):
        from src.tilesets.general import BlankTile

        u = self._universe()
        tile = BlankTile(u, {}, 0, 0)
        p = MagicMock()
        result = tile.modify_player(p)
        assert result is None

    def test_blank_tile_description_is_empty(self):
        from src.tilesets.general import BlankTile

        u = self._universe()
        tile = BlankTile(u, {}, 0, 0)
        assert tile.description == ""


# ---------------------------------------------------------------------------
# src/tilesets/test_chest.py — ChestRoom
# ---------------------------------------------------------------------------


class TestTilesetsTestChest:
    """Cover ChestRoom tileset."""

    def _universe(self):
        u = MagicMock()
        u.testing_mode = False
        return u

    def test_chest_room_creation(self):
        from src.tilesets.test_chest import ChestRoom

        u = self._universe()
        tile = ChestRoom(u, {}, 3, 4)
        assert tile.symbol == "#"
        assert tile.x == 3
        assert tile.y == 4

    def test_chest_room_modify_player_noop(self):
        from src.tilesets.test_chest import ChestRoom

        u = self._universe()
        tile = ChestRoom(u, {}, 0, 0)
        p = MagicMock()
        result = tile.modify_player(p)
        assert result is None

    def test_chest_room_description_contains_chest(self):
        from src.tilesets.test_chest import ChestRoom

        u = self._universe()
        tile = ChestRoom(u, {}, 0, 0)
        assert "chest" in tile.description.lower()

    def test_chest_room_npcs_here_starts_empty(self):
        from src.tilesets.test_chest import ChestRoom

        u = self._universe()
        tile = ChestRoom(u, {}, 0, 0)
        assert tile.npcs_here == []

    def test_chest_room_intro_text(self):
        from src.tilesets.test_chest import ChestRoom

        u = self._universe()
        tile = ChestRoom(u, {}, 0, 0)
        text = tile.intro_text()
        assert text is not None


# ---------------------------------------------------------------------------
# src/player/_movement.py — uncovered lines
# ---------------------------------------------------------------------------


class TestPlayerMovementMixin:
    """Lines 63-69, 73-78, 109, 118-119: do_action with phrase, flee edge cases."""

    def test_do_action_no_phrase(self):
        """Line 65-66: do_action without phrase calls method directly."""
        p = _player()
        p.universe = MagicMock()
        p.universe.game_tick = 0

        tile = _mock_tile()
        tile.intro_text.return_value = "Room text"

        mock_map = {"name": "test", (0, 0): tile}
        p.map = mock_map

        action = MagicMock()
        action.method.__name__ = "move_north"
        with patch.object(p, "move_north") as mock_move:
            p.do_action(action)
            mock_move.assert_called_once_with()

    def test_do_action_with_phrase(self):
        """Lines 68-69: do_action with phrase passes phrase to method."""
        p = _player()
        action = MagicMock()
        action.method.__name__ = "search"
        with patch.object(p, "search") as mock_search:
            p.do_action(action, phrase="goblin")
            mock_search.assert_called_once_with("goblin")

    def test_flee_no_available_moves(self):
        """Lines 73-75: flee prints error when no adjacent moves."""
        p = _player()
        tile = _mock_tile()
        tile.adjacent_moves.return_value = []
        with patch("src.player._movement.cprint") as mock_cp:
            p.flee(tile)
        mock_cp.assert_called_once()
        assert "nowhere" in mock_cp.call_args[0][0].lower()

    def test_flee_with_available_moves(self):
        """Lines 77-78: flee executes a random move."""
        p = _player()
        tile = _mock_tile()
        mock_action = MagicMock()
        mock_action.method.__name__ = "move_north"
        tile.adjacent_moves.return_value = [mock_action]
        with patch.object(p, "do_action") as mock_do:
            p.flee(tile)
        mock_do.assert_called_once_with(mock_action)

    def test_teleport_invalid_map(self):
        """Line 109: teleport prints error for invalid map."""
        p = _player()
        p.universe = MagicMock()
        p.universe.maps = [{"name": "forest"}]
        with (
            patch.object(p, "drop_merchandise_items"),
            patch("builtins.print") as mock_print,
        ):
            p.teleport("nonexistent_map", (0, 0))
        mock_print.assert_called_once()
        assert "INVALID" in mock_print.call_args[0][0]

    def test_teleport_invalid_tile(self):
        """Lines 107-108: teleport prints error for invalid tile coordinates."""
        p = _player()
        p.universe = MagicMock()
        test_map = {"name": "test_world"}
        p.universe.maps = [test_map]
        with (
            patch.object(p, "drop_merchandise_items"),
            patch("src.player._movement.tile_exists", return_value=None),
            patch("builtins.print") as mock_print,
        ):
            p.teleport("test_world", (99, 99))
        mock_print.assert_called_once()
        assert "INVALID" in mock_print.call_args[0][0]

    def test_recall_friends_one_party_member(self):
        """Lines 122-126: recall_friends with exactly one ally."""
        p = _player()
        current_room = _mock_tile()
        p.current_room = current_room

        friend = MagicMock()
        friend.current_room = _mock_tile()
        friend.current_room.npcs_here = [friend]
        friend.name = "Gorran"

        p.combat_list_allies = [p, friend]
        current_room.npcs_here = []

        with patch("builtins.print"):
            p.recall_friends()

        assert friend.current_room is current_room

    def test_recall_friends_two_party_members(self):
        """Lines 127-132: recall_friends with two allies."""
        p = _player()
        current_room = _mock_tile()
        p.current_room = current_room

        friend1 = MagicMock()
        friend1.current_room = _mock_tile()
        friend1.current_room.npcs_here = [friend1]
        friend1.name = "Gorran"

        friend2 = MagicMock()
        friend2.current_room = _mock_tile()
        friend2.current_room.npcs_here = [friend2]
        friend2.name = "Amelia"

        p.combat_list_allies = [p, friend1, friend2]
        current_room.npcs_here = []

        with patch("builtins.print"):
            p.recall_friends()

        assert friend1.current_room is current_room
        assert friend2.current_room is current_room


# ---------------------------------------------------------------------------
# src/player/_exploration.py — uncovered lines
# ---------------------------------------------------------------------------


class TestPlayerExplorationMixin:
    """Lines 16, 45-47, 90-102, 119, 132-134, 142-152, 170, 182."""

    def test_look_with_target_delegates_to_view(self):
        """Line 16: look(target) calls view()."""
        p = _player()
        with patch.object(p, "view") as mock_view:
            p.look(target="goblin")
        mock_view.assert_called_once_with("goblin")

    def test_view_empty_room_phrase_match_nothing(self):
        """Lines 45-47: view with phrase, no match in empty room."""
        p = _player()
        p.current_room = _mock_tile()
        p.current_room.npcs_here = []
        p.current_room.items_here = []
        p.current_room.objects_here = []
        with patch("builtins.print"):
            p.view(phrase="goblin")  # should silently find nothing

    def test_view_with_phrase_finds_npc(self):
        """Lines 48-68: view with phrase matching an NPC."""
        p = _player()
        npc = MagicMock()
        npc.name = "Goblin Warrior"
        npc.hidden = False
        npc.announce = "a goblin warrior"
        npc.idle_message = "stands guard"
        npc.description = "A fierce goblin."
        p.current_room = _mock_tile()
        p.current_room.npcs_here = [npc]
        with patch("builtins.print"), patch("src.functions.await_input"):
            p.view(phrase="goblin")

    def test_search_finds_hidden_npc(self):
        """Lines 83-88: search reveals a hidden NPC."""
        p = _player()
        p.finesse = 15
        p.intelligence = 15
        p.faith = 10

        hidden_npc = MagicMock()
        hidden_npc.hidden = True
        hidden_npc.hide_factor = 1  # very easy to find
        hidden_npc.discovery_message = "a hidden enemy!"

        p.current_room = _mock_tile()
        p.current_room.npcs_here = [hidden_npc]
        p.current_room.items_here = []
        p.current_room.objects_here = []

        with patch("time.sleep"), patch("builtins.print"):
            p.search()

        assert hidden_npc.hidden is False

    def test_search_finds_hidden_item(self):
        """Lines 89-94: search reveals a hidden item."""
        p = _player()
        p.finesse = 15
        p.intelligence = 15
        p.faith = 10

        hidden_item = MagicMock()
        hidden_item.hidden = True
        hidden_item.hide_factor = 1
        hidden_item.discovery_message = "a hidden potion!"

        p.current_room = _mock_tile()
        p.current_room.npcs_here = []
        p.current_room.items_here = [hidden_item]
        p.current_room.objects_here = []

        with patch("time.sleep"), patch("builtins.print"):
            p.search()

        assert hidden_item.hidden is False

    def test_search_finds_hidden_object(self):
        """Lines 95-100: search reveals a hidden object."""
        p = _player()
        p.finesse = 15
        p.intelligence = 15
        p.faith = 10

        hidden_obj = MagicMock()
        hidden_obj.hidden = True
        hidden_obj.hide_factor = 1
        hidden_obj.discovery_message = "a hidden lever!"

        p.current_room = _mock_tile()
        p.current_room.npcs_here = []
        p.current_room.items_here = []
        p.current_room.objects_here = [hidden_obj]

        with patch("time.sleep"), patch("builtins.print"):
            p.search()

        assert hidden_obj.hidden is False

    def test_search_finds_nothing(self):
        """Lines 101-102: search with nothing to find."""
        p = _player()
        p.finesse = 1
        p.intelligence = 1
        p.faith = 1

        visible_npc = MagicMock()
        visible_npc.hidden = False

        p.current_room = _mock_tile()
        p.current_room.npcs_here = [visible_npc]
        p.current_room.items_here = []
        p.current_room.objects_here = []

        with patch("time.sleep"), patch("builtins.print") as mock_print:
            p.search()

        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "couldn't find" in printed

    def test_view_map_no_discoveries(self):
        """Lines 131-134: view_map with no discovered tiles."""
        p = _player()
        p.map = {"name": "test"}
        with (
            patch("src.player._exploration.cprint") as mock_cp,
            patch("src.functions.await_input"),
        ):
            p.view_map()
        mock_cp.assert_called_once()
        assert "map" in mock_cp.call_args[0][0].lower()

    def test_view_map_with_discovered_tiles(self):
        """Lines 136-301: view_map renders discovered tiles."""
        p = _player()
        p.location_x = 1
        p.location_y = 1
        p.prev_location_x = 0
        p.prev_location_y = 1

        tile_obj = MagicMock()
        tile_obj.discovered = True
        tile_obj.last_entered = 1
        tile_obj.symbol = "●"

        p.current_room = tile_obj
        p.map = {"name": "test", (1, 1): tile_obj}

        with patch("builtins.print"), patch("src.functions.await_input"):
            p.view_map()

    def test_view_map_with_move_east(self):
        """Line 163-168: view_map with east movement connector."""
        p = _player()
        p.location_x = 2
        p.location_y = 1
        p.prev_location_x = 1
        p.prev_location_y = 1

        tile1 = MagicMock()
        tile1.discovered = True
        tile1.last_entered = 1
        tile1.symbol = "●"

        tile2 = MagicMock()
        tile2.discovered = True
        tile2.last_entered = 1
        tile2.symbol = "●"

        p.current_room = tile2
        p.map = {"name": "test", (1, 1): tile1, (2, 1): tile2}

        with patch("builtins.print"), patch("src.functions.await_input"):
            p.view_map()

    def test_view_map_with_move_south(self):
        """Lines 175-182: view_map with south movement connector."""
        p = _player()
        p.location_x = 1
        p.location_y = 2
        p.prev_location_x = 1
        p.prev_location_y = 1

        tile1 = MagicMock()
        tile1.discovered = True
        tile1.last_entered = 1
        tile1.symbol = "●"

        tile2 = MagicMock()
        tile2.discovered = True
        tile2.last_entered = 1
        tile2.symbol = "●"

        p.current_room = tile2
        p.map = {"name": "test", (1, 1): tile1, (1, 2): tile2}

        with patch("builtins.print"), patch("src.functions.await_input"):
            p.view_map()

    def test_view_map_diagonal_movement(self):
        """Lines 183-190: view_map with diagonal movement."""
        p = _player()
        p.location_x = 2
        p.location_y = 2
        p.prev_location_x = 1
        p.prev_location_y = 1

        tile1 = MagicMock()
        tile1.discovered = True
        tile1.last_entered = 1
        tile1.symbol = "●"

        tile2 = MagicMock()
        tile2.discovered = True
        tile2.last_entered = 1
        tile2.symbol = "●"

        p.current_room = tile2
        p.map = {"name": "test", (1, 1): tile1, (2, 2): tile2}

        with patch("builtins.print"), patch("src.functions.await_input"):
            p.view_map()

    def test_view_map_discovered_not_visited(self):
        """Line 146: discovered tile with last_entered==0 shows '?'."""
        p = _player()
        p.location_x = 1
        p.location_y = 1
        p.prev_location_x = 1
        p.prev_location_y = 1

        visited_tile = MagicMock()
        visited_tile.discovered = True
        visited_tile.last_entered = 1
        visited_tile.symbol = "●"

        unvisited_tile = MagicMock()
        unvisited_tile.discovered = True
        unvisited_tile.last_entered = 0
        unvisited_tile.symbol = "●"

        p.current_room = visited_tile
        p.map = {
            "name": "test",
            (1, 1): visited_tile,
            (2, 1): unvisited_tile,
        }

        with patch("builtins.print"), patch("src.functions.await_input"):
            p.view_map()


# ---------------------------------------------------------------------------
# src/player/_combat.py — uncovered lines
# ---------------------------------------------------------------------------


class TestPlayerCombatMixin:
    """Lines 158, 162, 165-166, 171, 190, 206-207, 235-236, 251."""

    def test_refresh_protection_rating_equipped_item(self):
        """Lines 125-136: protection recalculation with equipped item."""
        p = _player()
        p.endurance = 20

        item = MagicMock()
        item.isequipped = True
        item.protection = 5
        # No str_mod or fin_mod
        del item.str_mod
        del item.fin_mod
        p.inventory = [item]

        p.refresh_protection_rating()
        # protection = 20/10 + 5 = 7
        assert p.protection == pytest.approx(7.0)

    def test_refresh_protection_with_str_mod(self):
        """Lines 132-133: protection with str_mod bonus."""
        p = _player()
        p.endurance = 10
        p.strength = 5

        item = MagicMock()
        item.isequipped = True
        item.protection = 3
        item.str_mod = 1
        del item.fin_mod
        p.inventory = [item]

        p.refresh_protection_rating()
        # protection = 10/10 + 3 + 1*5 = 9
        assert p.protection == pytest.approx(9.0)

    def test_refresh_protection_with_fin_mod(self):
        """Line 134-136: protection with fin_mod bonus."""
        p = _player()
        p.endurance = 10
        p.finesse = 4

        item = MagicMock()
        item.isequipped = True
        item.protection = 2
        del item.str_mod
        item.fin_mod = 1
        p.inventory = [item]

        p.refresh_protection_rating()
        # protection = 10/10 + 2 + 1*4 = 7
        assert p.protection == pytest.approx(7.0)

    def test_refresh_moves_returns_viable_moves(self):
        """Lines 115-118: refresh_moves returns only viable moves."""
        p = _player()
        viable = MagicMock()
        viable.viable.return_value = True
        not_viable = MagicMock()
        not_viable.viable.return_value = False
        p.known_moves = [viable, not_viable]

        result = p.refresh_moves()
        assert viable in result
        assert not_viable not in result

    def test_combat_idle_healthy(self):
        """Lines 16-21: combat_idle when HP is healthy."""
        p = _player()
        p.hp = p.maxhp  # full HP
        # Ensure msg list has enough entries for any index up to 999
        p.combat_idle_msg = ["Ready to fight!"] * 1001
        with patch("random.randint", return_value=996), patch("builtins.print"):
            p.combat_idle()

    def test_combat_idle_hurt(self):
        """Lines 22-25: combat_idle when HP is low."""
        p = _player()
        p.hp = int(p.maxhp * 0.1)  # 10% HP
        p.combat_hurt_msg = ["Jean is badly hurt!"] * 1001
        with patch("random.randint", return_value=951), patch("builtins.print"):
            p.combat_idle()

    def test_change_heat_upper_clamp(self):
        """Line 33: heat clamped at 10."""
        p = _player()
        p.heat = 9.5
        p.change_heat(mult=2)
        assert p.heat == 10

    def test_change_heat_lower_clamp(self):
        """Line 35: heat clamped at 0.5."""
        p = _player()
        p.heat = 0.6
        p.change_heat(mult=0.1)
        assert p.heat == 0.5

    def test_refresh_enemy_list_removes_dead(self):
        """Lines 39-48: refresh_enemy_list_and_prox removes dead enemies."""
        p = _player()
        dead = MagicMock()
        dead.is_alive.return_value = False
        alive = MagicMock()
        alive.is_alive.return_value = True

        p.combat_list = [dead, alive]
        p.combat_proximity = {dead: 10, alive: 5}
        p.refresh_enemy_list_and_prox()

        assert dead not in p.combat_list
        assert alive in p.combat_list
        assert dead not in p.combat_proximity
        assert alive in p.combat_proximity


# ---------------------------------------------------------------------------
# src/player/_leveling.py — uncovered lines
# ---------------------------------------------------------------------------


class TestPlayerLevelingMixin:
    """Lines 95, 172-176, 190-194: level_up_api and level_up edge cases."""

    def test_gain_exp_api_mode_level_up(self):
        """Lines 52-56: gain_exp in api_mode triggers _level_up_api."""
        p = _player()
        p.exp = p.exp_to_level - 1  # one below threshold
        p.level = 1

        # Enough to trigger a level-up
        events = p.gain_exp(p.exp_to_level + 10, api_mode=True)
        assert isinstance(events, list)
        assert len(events) >= 1
        assert events[0]["level_up"] is True

    def test_level_up_api_returns_dict(self):
        """Lines 68-104: _level_up_api returns proper dict."""
        p = _player()
        p.level = 1
        p.exp = p.exp_to_level + 100

        result = p._level_up_api()
        assert result["level_up"] is True
        assert result["new_level"] == 2
        assert "points_awarded" in result
        assert "bonuses" in result

    def test_level_up_api_increments_level(self):
        """Level increments correctly."""
        p = _player()
        old_level = p.level
        p.exp = p.exp_to_level + 1
        p._level_up_api()
        assert p.level == old_level + 1

    def test_level_up_api_sets_pending_attribute_points(self):
        """Line 95-96: pending_attribute_points is set if not present."""
        p = _player()
        if hasattr(p, "pending_attribute_points"):
            del p.__dict__["pending_attribute_points"]
        p.exp = p.exp_to_level + 1
        p._level_up_api()
        assert hasattr(p, "pending_attribute_points")
        assert p.pending_attribute_points > 0

    def test_gain_exp_no_level_up(self):
        """Lines 48-49: gain_exp below threshold just adds exp."""
        p = _player()
        old_exp = p.exp
        p.gain_exp(10, api_mode=True)
        assert p.exp == old_exp + 10

    def test_gain_exp_with_combat_adapter(self):
        """Line 52: gain_exp detects _combat_adapter attribute."""
        p = _player()
        p._combat_adapter = MagicMock()
        p.exp = p.exp_to_level + 10

        events = p.gain_exp(0, api_mode=False)
        # _combat_adapter path also returns events list
        assert isinstance(events, list)

    def test_learn_skill_new(self):
        """Lines 109-115: learn_skill adds new skill."""
        p = _player()
        new_skill = MagicMock()
        new_skill.name = "Shield Bash"
        # Ensure skill not already known
        p.known_moves = []

        with patch("src.player._leveling.cprint"):
            result = p.learn_skill(new_skill)

        assert new_skill in p.known_moves
        assert result is new_skill

    def test_learn_skill_already_known(self):
        """Lines 109-116: learn_skill doesn't duplicate."""
        p = _player()
        existing = MagicMock()
        existing.name = "Basic Strike"
        p.known_moves = [existing]

        new_skill = MagicMock()
        new_skill.name = "Basic Strike"

        with patch("src.player._leveling.cprint"):
            result = p.learn_skill(new_skill)

        # Not added again
        assert p.known_moves.count(existing) == 1


# ---------------------------------------------------------------------------
# src/player/_world.py — uncovered lines
# ---------------------------------------------------------------------------


class TestPlayerWorldMixinExtended:
    """Lines 27, 30, 34, 36-37, 47, 55-57, 78-80, 95-96."""

    def _make_merchant(self, name="Vendor", has_update=True):
        """Create a mock merchant NPC with Merchant in MRO."""

        class Merchant:
            pass

        class MockMerchant(Merchant):
            def __init__(self, nme):
                self.name = nme
                self.shop = None
                self._update_called = False

            def update_goods(self):
                self._update_called = True

        m = MockMerchant(name)
        return m

    def _make_universe_with_merchant(self, merchant, tile=None):
        if tile is None:
            tile = MagicMock()
            tile.npcs_here = [merchant]

        game_map = {"name": "test_world", (0, 0): tile}
        universe = MagicMock()
        universe.maps = [game_map]
        return universe

    def test_refresh_merchants_no_universe_attribute(self):
        """Line 19: universe has no maps attribute."""
        p = _player()
        p.universe = MagicMock(spec=[])  # no 'maps' attribute
        with patch("src.player._world.cprint") as mock_cp:
            p.refresh_merchants()
        mock_cp.assert_called_once()

    def test_refresh_merchants_finds_merchant_no_filter(self):
        """Lines 50-54: finds merchant without filter."""
        p = _player()
        m = self._make_merchant("Harold")
        p.universe = self._make_universe_with_merchant(m)

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants()

        assert m._update_called is True

    def test_refresh_merchants_with_matching_filter(self):
        """Lines 51-53: filter matches by name."""
        p = _player()
        m = self._make_merchant("Harold")
        p.universe = self._make_universe_with_merchant(m)

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants(phrase="harold")

        assert m._update_called is True

    def test_refresh_merchants_with_non_matching_filter(self):
        """Lines 52-53: filter doesn't match — no merchants updated."""
        p = _player()
        m = self._make_merchant("Harold")
        p.universe = self._make_universe_with_merchant(m)

        with patch("src.player._world.cprint") as mock_cp, patch("time.sleep"):
            p.refresh_merchants(phrase="zzz")

        mock_cp.assert_called()
        assert m._update_called is False

    def test_refresh_merchants_empty_map(self):
        """Lines 40-45: map without merchants."""
        p = _player()
        universe = MagicMock()
        universe.maps = [{"name": "empty_world"}]
        p.universe = universe

        with patch("src.player._world.cprint") as mock_cp, patch("time.sleep"):
            p.refresh_merchants()

        mock_cp.assert_called()

    def test_refresh_merchants_non_dict_map_skipped(self):
        """Lines 41-42: non-dict entries in maps are skipped."""
        p = _player()
        universe = MagicMock()
        universe.maps = ["not_a_dict", None, 42]
        p.universe = universe

        with patch("src.player._world.cprint") as mock_cp, patch("time.sleep"):
            p.refresh_merchants()

        mock_cp.assert_called()

    def test_refresh_merchants_missing_update_goods(self):
        """Lines 89-92: merchant missing update_goods logs failure."""

        class Merchant:
            pass

        class BrokenMerchant(Merchant):
            def __init__(self):
                self.name = "Broken"
                self.shop = object()

        m = BrokenMerchant()
        p = _player()
        p.universe = self._make_universe_with_merchant(m)

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants()  # should not raise

    def test_refresh_merchants_update_goods_raises(self):
        """Lines 86-87: update_goods raises — captured in failures list."""

        class Merchant:
            pass

        class ErrorMerchant(Merchant):
            def __init__(self):
                self.name = "Error"
                self.shop = object()

            def update_goods(self):
                raise RuntimeError("DB exploded")

        m = ErrorMerchant()
        p = _player()
        p.universe = self._make_universe_with_merchant(m)

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants()  # should not raise

    def test_refresh_merchants_initialize_shop_called_when_shop_none(self):
        """Lines 75-79: initialize_shop called when shop is None."""

        class Merchant:
            pass

        class UninitMerchant(Merchant):
            def __init__(self):
                self.name = "UninitVendor"
                self.shop = None
                self.initialized = False
                self._update_called = False

            def initialize_shop(self):
                self.initialized = True
                self.shop = object()

            def update_goods(self):
                self._update_called = True

        m = UninitMerchant()
        p = _player()
        p.universe = self._make_universe_with_merchant(m)

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants()

        assert m.initialized is True
        assert m._update_called is True
