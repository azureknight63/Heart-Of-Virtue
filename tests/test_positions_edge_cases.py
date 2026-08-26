"""
Phase 3.4: Edge Case and Boundary Stress Testing

Comprehensive boundary condition and edge case tests for coordinate positioning system:
- Grid boundary conditions (movement at edges/corners)
- Position clamping and boundary enforcement
- Extreme scenarios (many units, unequal forces)
- Direction facing edge cases
- Multiple threats and complex scenarios
- Invalid input handling

Tests verify:
1. Grid edge movement doesn't break positioning
2. Clamping works correctly at boundaries
3. Distance calculations at extremes
4. Angle calculations at boundaries
5. Formation spacing with many units
6. Stress tests with high unit counts
"""

import sys
import os
from pathlib import Path
import math
import random

# Setup sys.path for imports
ROOT = Path(__file__).resolve().parent.parent


import pytest
from unittest.mock import patch

from src.player import Player
from src.npc import NPC
import src.positions as positions


class TestGridBoundaryConditions:
    """Test behavior at grid boundaries."""

    def test_position_at_grid_origin(self):
        """Test position at (0, 0)."""
        pos = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        assert pos.x == 0
        assert pos.y == 0
        assert pos.facing == positions.Direction.N

    def test_position_at_max_coordinates(self):
        """Test position at grid maximum (50, 50)."""
        pos = positions.CombatPosition(x=50, y=50, facing=positions.Direction.S)
        assert pos.x == 50
        assert pos.y == 50
        assert pos.facing == positions.Direction.S

    def test_distance_from_origin_to_opposite_corner(self):
        """Test maximum distance across grid."""
        pos1 = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        pos2 = positions.CombatPosition(x=50, y=50, facing=positions.Direction.S)

        distance = positions.distance_from_coords(pos1, pos2)
        expected = math.sqrt(50**2 + 50**2)

        assert math.isclose(distance, expected, rel_tol=0.01)

    def test_move_toward_from_corner_to_corner(self):
        """Test movement from one corner toward opposite corner."""
        start = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        target = positions.CombatPosition(x=50, y=50, facing=positions.Direction.S)

        new_pos = positions.move_toward(start, target, 5)

        # Bearing to the opposite corner is 45 deg, so a 5-square step lands at
        # round(0 + sin(45)*5) = 4 on both axes. An in-bounds assertion would
        # equally accept (0, 0) or a step in the wrong direction entirely.
        assert (new_pos.x, new_pos.y) == (4, 4)
        assert new_pos.facing is positions.Direction.N  # facing is preserved

        new_dist = positions.distance_from_coords(new_pos, target)
        old_dist = positions.distance_from_coords(start, target)
        assert (old_dist, new_dist) == (71, 65)

    def test_move_away_from_corner_clamps_correctly(self):
        """Test that move_away clamps at grid boundaries."""
        start = positions.CombatPosition(x=2, y=2, facing=positions.Direction.N)
        threat = positions.CombatPosition(x=25, y=25, facing=positions.Direction.S)

        new_pos = positions.move_away_from(start, threat, 5)

        # Bearing away from (25,25) is 225 deg, so the ideal destination is
        # round(2 - sin(45)*5) = -2 on both axes; the grid clamp pulls it to the
        # corner. The try/except this replaces swallowed any failure, and the
        # in-bounds assertion could not tell a clamp from a no-op.
        assert (new_pos.x, new_pos.y) == (0, 0)

    def test_clamp_position_at_corners(self):
        """Test clamping of positions at grid corners."""
        # Test valid corners
        corner1 = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        corner2 = positions.CombatPosition(x=50, y=50, facing=positions.Direction.S)
        corner3 = positions.CombatPosition(x=0, y=50, facing=positions.Direction.N)
        corner4 = positions.CombatPosition(x=50, y=0, facing=positions.Direction.S)

        # Should create without error (already within bounds)
        assert corner1.x == 0 and corner1.y == 0
        assert corner2.x == 50 and corner2.y == 50
        assert corner3.x == 0 and corner3.y == 50
        assert corner4.x == 50 and corner4.y == 0

    @pytest.mark.parametrize(
        "x, y",
        [
            (0, 25), (50, 25),                   # left/right edges
            (25, 0), (25, 50),                   # top/bottom edges
            (0, 0), (50, 0), (0, 50), (50, 50),  # corners
        ],
    )
    def test_edge_positions_are_accepted_by_the_validator(self, x, y):
        """Coordinates exactly on the bound are inclusive, not rejected.

        The previous version asserted `0 <= pos.x <= 50` on coordinates it had
        just supplied itself -- true by construction. What actually matters is
        that ``__post_init__`` accepts the boundary rather than raising.
        """
        pos = positions.CombatPosition(x=x, y=y, facing=positions.Direction.N)
        assert (pos.x, pos.y) == (x, y)

    @pytest.mark.parametrize("x, y", [(-1, 25), (51, 25), (25, -1), (25, 51)])
    def test_positions_one_step_outside_the_bound_are_rejected(self, x, y):
        with pytest.raises(ValueError, match="between 0 and 50"):
            positions.CombatPosition(x=x, y=y, facing=positions.Direction.N)


class TestAngleCalculationsAtBoundaries:
    """Test angle calculations at extreme positions."""

    def test_angle_from_origin_to_all_directions(self):
        """Test angle calculations from grid origin."""
        origin = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)

        test_targets = [
            (0, 25, 0.0),     # due north
            (25, 0, 90.0),    # due east
            (25, 25, 45.0),   # north-east diagonal
            (0, 0, 0.0),      # same square -> atan2(0, 0) is 0.0, not an error
        ]

        for x, y, expected_angle in test_targets:
            target = positions.CombatPosition(x=x, y=y, facing=positions.Direction.N)
            angle = positions.angle_to_target(origin, target)

            # 0 deg is North (+y) and 90 deg is East (+x). The old assertion
            # (0 <= angle <= 360) held for every possible return value.
            assert angle == expected_angle, f"({x}, {y}) -> {angle}"

    def test_angle_from_corner_to_opposite_corner(self):
        """Test diagonal angle calculations."""
        corner1 = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        corner2 = positions.CombatPosition(x=50, y=50, facing=positions.Direction.S)

        angle = positions.angle_to_target(corner1, corner2)

        # (0,0) -> (50,50) is exactly the north-east diagonal.
        assert angle == 45.0

    def test_angle_difference_at_180_degrees(self):
        """Test angle difference when facing opposite direction."""
        facing_dir = positions.Direction.N  # 0 degrees
        target_dir = positions.Direction.S  # 180 degrees

        diff = positions.attack_angle_difference(
            target_dir.value, facing_dir
        )

        # Facing North, attacked from due South: a textbook rear attack.
        assert diff == 180
        assert positions.get_damage_modifier(diff) == 1.40
        assert positions.get_accuracy_modifier(diff) == 1.30


class TestPositionClamping:
    """Test position clamping behavior."""

    def test_clamp_preserves_valid_coordinates(self):
        """Test that clamping doesn't change valid coordinates."""
        valid_pos = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        clamped = positions.clamp_position(valid_pos)

        assert clamped.x == 25
        assert clamped.y == 25

    def test_valid_boundary_positions(self):
        """Test that boundary positions are valid."""
        # Test all 4 corners
        corners = [
            (0, 0), (0, 50), (50, 0), (50, 50)
        ]

        for x, y in corners:
            pos = positions.CombatPosition(x=x, y=y, facing=positions.Direction.N)
            assert pos.x == x
            assert pos.y == y

    def test_clamping_with_position_after_movement(self):
        """Test that movement results are properly clamped."""
        start = positions.CombatPosition(x=1, y=1, facing=positions.Direction.N)
        target = positions.CombatPosition(x=5, y=5, facing=positions.Direction.S)

        new_pos = positions.move_away_from(start, target, 3)

        # Bearing away is 225 deg -> round(1 - sin(45)*3) = -1 on both axes,
        # clamped to the (0, 0) corner rather than raising or wrapping.
        assert (new_pos.x, new_pos.y) == (0, 0)


class TestExtremeDistances:
    """Test distance calculations at extreme scenarios."""

    def test_distance_same_position(self):
        """Test distance when positions are identical."""
        pos = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        distance = positions.distance_from_coords(pos, pos)
        assert distance == 0

    def test_distance_one_square_apart(self):
        """Test distance for adjacent positions."""
        pos1 = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        pos2 = positions.CombatPosition(x=26, y=25, facing=positions.Direction.N)

        distance = positions.distance_from_coords(pos1, pos2)
        assert math.isclose(distance, 1.0, abs_tol=0.01)

    def test_distance_diagonal_one_square(self):
        """Test distance for diagonally adjacent positions."""
        pos1 = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        pos2 = positions.CombatPosition(x=26, y=26, facing=positions.Direction.N)

        distance = positions.distance_from_coords(pos1, pos2)
        # sqrt(2) = 1.414..., and the function rounds to the nearest integer.
        assert distance == 1


class TestDirectionEdgeCases:
    """Test direction/facing edge cases."""

    def test_all_directions_valid(self):
        """Test that all 8 directions are valid."""
        for direction in positions.Direction:
            assert direction.value in [0, 45, 90, 135, 180, 225, 270, 315]
            assert hasattr(direction, 'name')

    @pytest.mark.parametrize(
        "to_xy, expected",
        [
            ((25, 45), positions.Direction.N),
            ((45, 45), positions.Direction.NE),
            ((45, 25), positions.Direction.E),
            ((45, 5), positions.Direction.SE),
            ((25, 5), positions.Direction.S),
            ((5, 5), positions.Direction.SW),
            ((5, 25), positions.Direction.W),
            ((5, 45), positions.Direction.NW),
        ],
    )
    def test_turn_toward_resolves_every_compass_bearing(self, to_xy, expected):
        """The old loop pointed at the same square eight times (it varied only
        the *target's* facing, which turn_toward ignores) and asserted the
        result was some Direction -- true of all eight possible answers."""
        from_pos = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        to_pos = positions.CombatPosition(x=to_xy[0], y=to_xy[1])

        assert positions.turn_toward(from_pos, to_pos) is expected

    def test_turn_toward_same_position_defaults_to_north(self):
        """atan2(0, 0) is 0.0, so a self-referential turn resolves to North."""
        pos = positions.CombatPosition(x=25, y=25, facing=positions.Direction.SW)

        assert positions.turn_toward(pos, pos) is positions.Direction.N

    def test_facing_direction_names(self):
        """Test that direction names are correct."""
        names_to_check = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

        for name in names_to_check:
            direction = positions.Direction[name]
            assert direction.name == name


class TestStressAndComplexScenarios:
    """Stress tests and complex scenario validation."""

    def test_many_units_formation_keeps_every_unit_on_a_distinct_square(self):
        """The old version built 20 positions from hardcoded coordinates and
        asserted they were in bounds -- true by construction, and it would not
        have noticed two units stacked on the same square."""
        units = [
            positions.CombatPosition(
                x=(i % 5) * 10, y=(i // 5) * 10, facing=positions.Direction.N
            )
            for i in range(20)
        ]

        assert len({(p.x, p.y) for p in units}) == 20
        assert min(p.x for p in units) == 0 and max(p.x for p in units) == 40
        assert min(p.y for p in units) == 0 and max(p.y for p in units) == 30

    def test_damage_modifier_for_angle_ranges(self):
        """Test damage modifiers for different angle ranges."""
        # Test frontal attack (0-45 degrees)
        mod_front = positions.get_damage_modifier(30)
        assert mod_front == 0.85

        # Test flanking attack (45-90 degrees)
        mod_flank = positions.get_damage_modifier(70)
        assert mod_flank == 1.15

        # Test deep flank (90-135 degrees)
        mod_deep = positions.get_damage_modifier(110)
        assert mod_deep == 1.25

        # Test rear attack (135-180 degrees)
        mod_rear = positions.get_damage_modifier(160)
        assert mod_rear == 1.40

    def test_accuracy_modifier_for_angle_ranges(self):
        """Test accuracy modifiers for different angle ranges."""
        # Test frontal attack (0-45 degrees)
        mod_front = positions.get_accuracy_modifier(30)
        assert mod_front == 0.95

        # Test flanking attack (45-90 degrees)
        mod_flank = positions.get_accuracy_modifier(70)
        assert mod_flank == 1.10

        # Test deep flank (90-135 degrees)
        mod_deep = positions.get_accuracy_modifier(110)
        assert mod_deep == 1.20

        # Test rear attack (135-180 degrees)
        mod_rear = positions.get_accuracy_modifier(160)
        assert mod_rear == 1.30

    def test_movement_distance_bounds(self):
        """Test that movement distances stay within reasonable bounds."""
        for _ in range(20):
            start = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
            target = positions.CombatPosition(
                x=random.randint(0, 50),
                y=random.randint(0, 50),
                facing=positions.Direction.N
            )

            # Move toward with various distances
            start_dist = positions.distance_from_coords(start, target)
            for move_dist in [1, 2, 5, 10, 20]:
                new_pos = positions.move_toward(start, target, move_dist)

                # The real invariant: a step of N never travels more than N
                # squares, and never overshoots the target. Bounds-only checks
                # would pass even if move_toward teleported to the target.
                travelled = positions.distance_from_coords(start, new_pos)
                assert travelled <= move_dist + 1, (start_dist, move_dist, travelled)
                remaining = positions.distance_from_coords(new_pos, target)
                assert remaining <= start_dist


class TestScenarioDefinitions:
    """Test scenario definitions and initialization."""

    def test_all_scenarios_defined(self):
        """Test that all combat scenarios are properly defined."""
        scenarios = positions.COMBAT_SCENARIOS

        # Should have at least 4 scenarios
        assert len(scenarios) >= 4

        # Each scenario should be a CombatScenario object
        for scenario_type, scenario in scenarios.items():
            assert hasattr(scenario, 'scenario_type')
            assert hasattr(scenario, 'ally_spawn_zone')
            assert hasattr(scenario, 'enemy_spawn_zones')
            assert scenario.scenario_type == scenario_type

    def test_standard_scenario_exists(self):
        """Test that standard scenario is defined."""
        scenarios = positions.COMBAT_SCENARIOS
        assert 'standard' in scenarios
        scenario = scenarios['standard']
        assert scenario.scenario_type == 'standard'


class TestMovementEdgeCases:
    """Test edge cases in movement calculations."""

    def test_move_toward_when_already_at_target(self):
        """Test moving toward a position you're already at."""
        pos = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)

        new_pos = positions.move_toward(pos, pos, 5)

        # Should stay at same position or very close
        dist = positions.distance_from_coords(pos, new_pos)
        assert dist < 1  # Allow tiny floating point error

    def test_move_away_when_at_same_position_picks_one_of_four_axis_steps(self):
        """Degenerate case: the bearing is undefined, so the engine picks a
        random cardinal step of exactly ``distance``. The old test asserted only
        that the result was on the grid, which a no-op (25, 25) also satisfies.
        """
        pos = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        expected = {(30, 25), (20, 25), (25, 30), (25, 20)}

        # random.choice is the only nondeterminism; drive it across all 4 arms.
        seen = set()
        for index in range(4):
            with patch(
                "src.positions.random.choice", side_effect=lambda seq, i=index: seq[i]
            ):
                moved = positions.move_away_from(pos, pos, 5)
            seen.add((moved.x, moved.y))
            assert moved.facing is positions.Direction.N

        assert seen == expected

    def test_flank_movement_perpendicular(self):
        """Test that flanking movement is perpendicular to target."""
        attacker_pos = positions.CombatPosition(x=20, y=25, facing=positions.Direction.E)
        defender_pos = positions.CombatPosition(x=30, y=25, facing=positions.Direction.W)

        flank_pos = positions.move_to_flank(attacker_pos, defender_pos, 3)

        # The defender faces West (270 deg), so its blind sides are due North
        # (0 deg) and due South (180 deg); the approach bearing ties and the
        # first blind side wins, putting the flanker 3 squares north of it.
        assert (flank_pos.x, flank_pos.y) == (30, 28)
        assert flank_pos.facing is positions.Direction.E  # attacker keeps facing

        # And it really is a flank, not a head-on approach.
        approach = positions.angle_to_target(flank_pos, defender_pos)
        diff = positions.attack_angle_difference(approach, defender_pos.facing)
        assert 45 < diff <= 135


class TestInvalidInputHandling:
    """Test handling of invalid inputs."""

    def test_negative_distance_movement(self):
        """Test behavior with negative movement distance."""
        start = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        target = positions.CombatPosition(x=30, y=30, facing=positions.Direction.N)

        new_pos = positions.move_toward(start, target, -5)

        # Documented current behaviour: negative distances are NOT rejected --
        # min(-5, 7) is -5, so the unit walks 5 squares backwards along the
        # bearing. No caller passes a negative distance today; this pins the
        # behaviour so a future guard is a deliberate, visible change.
        assert (new_pos.x, new_pos.y) == (21, 21)

    def test_zero_distance_movement(self):
        """Test movement with zero distance."""
        start = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        target = positions.CombatPosition(x=30, y=30, facing=positions.Direction.N)

        new_pos = positions.move_toward(start, target, 0)

        # Should stay at start
        assert new_pos.x == start.x
        assert new_pos.y == start.y

    def test_very_large_movement_distance(self):
        """Test movement with very large distance."""
        start = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        target = positions.CombatPosition(x=30, y=30, facing=positions.Direction.N)

        # A huge step must stop *at* the target, not merely somewhere on grid.
        new_pos = positions.move_toward(start, target, 10000)

        assert (new_pos.x, new_pos.y) == (target.x, target.y)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
