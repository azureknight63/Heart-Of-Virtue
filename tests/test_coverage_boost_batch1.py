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

    def test_blocked_destination_retries_shorter_distances(self):
        """A blocked 2-square retreat is not abandoned -- the 1-square retreat
        is tried next, and only a fully blocked corridor returns ``current``."""
        current = _cp(5, 5)
        threat = _cp(3, 5)
        # Retreat bearing is due east, so distance 2 -> (7,5) and 1 -> (6,5).
        assert move_away_constrained(current, threat, 2, [_cp(7, 5)]) .x == 6
        blocked = move_away_constrained(current, threat, 2, [_cp(7, 5), _cp(6, 5)])
        assert (blocked.x, blocked.y) == (5, 5)

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
        """With nothing occupied the constrained form is identical to move_to_flank."""
        from src.positions import move_to_flank

        current = _cp(5, 25)
        target = _cp(25, 25, Direction.E)
        result = move_to_flank_constrained(current, target, 3, [])
        expected = move_to_flank(current, target, 3)
        assert (result.x, result.y) == (expected.x, expected.y)
        # Target faces east, so its blind sides are due north/south of it.
        assert result.x == target.x
        assert abs(result.y - target.y) == 3

    def test_blocked_primary_flank_uses_the_other_blind_side(self):
        """A blocked flank never degrades into a head-on approach."""
        current = _cp(25, 20)  # north of the target
        target = _cp(25, 25, Direction.E)
        result = move_to_flank_constrained(current, target, 3, [_cp(25, 22)])
        # North blind side (25,22) is taken -> take the south one, still a flank.
        assert (result.x, result.y) == (25, 28)

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
        """Zero displacement resolves to North, not to the current facing."""
        current = _cp(5, 5, Direction.S)
        target = _cp(5, 5, Direction.S)
        assert turn_toward(current, target) is Direction.N

    @pytest.mark.parametrize(
        "dx, dy, expected",
        [
            (1, 0, Direction.E),
            (-1, 0, Direction.W),
            (0, 1, Direction.N),   # +y is North (angle_to_target: 0 deg = +y)
            (0, -1, Direction.S),
            (1, 1, Direction.NE),
            (-1, 1, Direction.NW),
            (1, -1, Direction.SE),
            (-1, -1, Direction.SW),
        ],
    )
    def test_turn_toward_cardinal_directions(self, dx, dy, expected):
        current = _cp(10, 10)
        target = _cp(10 + dx * 5, 10 + dy * 5)
        assert turn_toward(current, target) is expected


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

    @staticmethod
    def _assert_in_zone(pos, zone):
        (x_min, y_min), (x_max, y_max) = zone
        assert x_min <= pos.x <= x_max, pos
        assert y_min <= pos.y <= y_max, pos

    def test_cluster_formation(self):
        """Cluster puts the first unit dead centre and the rest adjacent to it."""
        units = [self._make_unit() for _ in range(3)]
        zone = ((5, 5), (15, 15))
        _spawn_units_in_zone(units, zone, formation_type="cluster")
        first = units[0].combat_position
        assert (first.x, first.y) == (10, 10)  # centre of the zone
        for u in units:
            self._assert_in_zone(u.combat_position, zone)
        # "Clustered" is a real claim, but the spiral re-anchors on the running
        # cluster centre (_calculate_center_position of everyone placed so far),
        # not on the zone centre -- so a later unit can sit >4 from (10, 10)
        # while still being tightly clustered. Assert the bound the algorithm
        # actually gives: each unit lands within the spiral's max radius of the
        # centre as it stood when that unit was placed.
        from src.positions import _calculate_center_position

        placed = [units[0].combat_position]
        for u in units[1:]:
            centre = _calculate_center_position(placed)
            assert abs(u.combat_position.x - centre.x) <= 4
            assert abs(u.combat_position.y - centre.y) <= 4
            placed.append(u.combat_position)

    def test_random_formation(self):
        """Random placement still respects the zone boundary."""
        units = [self._make_unit() for _ in range(3)]
        zone = ((5, 5), (20, 20))
        _spawn_units_in_zone(units, zone, formation_type="random")
        for u in units:
            self._assert_in_zone(u.combat_position, zone)

    def test_spread_formation_is_deterministic_for_a_given_seed(self):
        """The seed argument must actually reproduce the same layout."""
        zone = ((0, 0), (10, 10))

        def layout():
            units = [self._make_unit() for _ in range(3)]
            _spawn_units_in_zone(
                units, zone, formation_type="spread", min_spacing=2, seed=42
            )
            return [(u.combat_position.x, u.combat_position.y) for u in units]

        first, second = layout(), layout()
        assert first == second
        for pos in first:
            assert 0 <= pos[0] <= 10 and 0 <= pos[1] <= 10
        # min_spacing=2 in a 10x10 zone is satisfiable, so no two units overlap.
        assert len(set(first)) == 3


class TestFindSpacedPositionFallback:
    """Line 876: _find_spaced_position fallback when constrained."""

    def test_fallback_when_zone_is_tiny(self):
        """An unsatisfiable spacing constraint still yields an in-zone square."""
        zone = ((5, 5), (6, 6))  # Very small zone
        # Fill with many occupied positions to force fallback
        occupied = [_cp(x, y) for x in range(0, 51) for y in range(0, 51)]
        result = _find_spaced_position(zone, occupied, min_spacing=10)
        assert 5 <= result.x <= 6
        assert 5 <= result.y <= 6


class TestFindClusteredPosition:
    """Lines 911, 915-925: _find_clustered_position spiral search."""

    def test_first_unit_goes_to_center(self):
        zone = ((0, 0), (10, 10))
        result = _find_clustered_position(zone, [], min_spacing=1)
        assert result.x == 5
        assert result.y == 5

    def test_subsequent_unit_near_first(self):
        """The spiral starts at radius 1, so unit two lands on the ring around unit one."""
        zone = ((0, 0), (10, 10))
        first = _cp(5, 5)
        result = _find_clustered_position(zone, [first], min_spacing=1)
        dx = abs(result.x - 5)
        dy = abs(result.y - 5)
        assert max(dx, dy) == 1
        assert (result.x, result.y) != (5, 5)

    def test_min_spacing_pushes_the_next_unit_further_out(self):
        """min_spacing is honoured within the cluster, not just the zone."""
        zone = ((0, 0), (30, 30))
        first = _cp(15, 15)
        result = _find_clustered_position(zone, [first], min_spacing=3)
        from src.positions import distance_from_coords

        assert distance_from_coords(result, first) >= 3

    def test_cluster_fallback_when_no_valid_position(self):
        """Unsatisfiable spacing falls back to a random *in-zone* square."""
        zone = ((5, 5), (6, 6))
        occupied = [_cp(x, y) for x in range(0, 51) for y in range(0, 51)]
        result = _find_clustered_position(zone, occupied, min_spacing=5)
        assert 5 <= result.x <= 6
        assert 5 <= result.y <= 6


class TestInitializeCombatPositions:
    """Integration: initialize_combat_positions sets positions on all units."""

    def _make_combatant(self):
        c = MagicMock()
        c.combat_position = None
        c.combat_proximity = {}
        return c

    @pytest.mark.parametrize("scenario", ["standard", "pincer", "boss_arena"])
    def test_every_unit_is_placed_facing_the_enemy_with_proximity_wired(
        self, scenario
    ):
        """Placement is only half the job: facing and combat_proximity must be set too."""
        from src.positions import distance_from_coords

        allies = [self._make_combatant() for _ in range(2)]
        enemies = [self._make_combatant() for _ in range(2)]
        initialize_combat_positions(allies, enemies, scenario_type=scenario)

        everyone = allies + enemies
        for c in everyone:
            assert isinstance(c.combat_position, CombatPosition)
            assert isinstance(c.combat_position.facing, Direction)
            # Proximity is keyed by every *other* combatant, and the distances
            # agree with the coordinates that were just assigned.
            assert set(c.combat_proximity) == {o for o in everyone if o is not c}
            for other, dist in c.combat_proximity.items():
                assert dist == distance_from_coords(
                    c.combat_position, other.combat_position
                )

    def test_allies_and_enemies_start_on_opposite_sides(self):
        """The standard scenario is a face-off, not a scrum."""
        allies = [self._make_combatant() for _ in range(2)]
        enemies = [self._make_combatant() for _ in range(2)]
        initialize_combat_positions(allies, enemies, scenario_type="standard")
        # The standard face-off separates the teams along X: allies spawn in
        # x in [0, 10], enemies in x in [20, 30], and the two share an identical
        # y range -- so a Y-axis assertion here would be testing nothing.
        ally_xs = [a.combat_position.x for a in allies]
        enemy_xs = [e.combat_position.x for e in enemies]
        assert max(ally_xs) < min(enemy_xs)

    def test_pincer_splits_enemies_across_two_zones(self):
        """"Pincer" must actually pincer -- enemies straddle the allies."""
        allies = [self._make_combatant()]
        enemies = [self._make_combatant() for _ in range(2)]
        initialize_combat_positions(allies, enemies, scenario_type="pincer")
        # Pincer straddles along X: the two enemy zones are x in [0, 7] and
        # x in [43, 50], with the allies boxed between them in x in [18, 32].
        ally_x = allies[0].combat_position.x
        enemy_xs = sorted(e.combat_position.x for e in enemies)
        assert enemy_xs[0] < ally_x < enemy_xs[-1]


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

    def test_available_actions_includes_the_default_action_set(self):
        # Movement is dispatched via GameService.move_player, not Action
        # classes -- the directional-move Action subclasses no longer exist.
        tile = self._make_tile()
        acts = tile.available_actions()
        action_types = [type(a).__name__ for a in acts]
        assert {"Search", "Menu", "Save"}.issubset(action_types)


# ---------------------------------------------------------------------------
# src/player/_movement.py — uncovered lines
# ---------------------------------------------------------------------------


class TestPlayerMovementMixin:
    """Lines 109, 118-119: teleport/recall_friends edge cases."""

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
