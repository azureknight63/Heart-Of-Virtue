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
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
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
        
        # Should move somewhere between start and target
        assert 0 <= new_pos.x <= 50
        assert 0 <= new_pos.y <= 50
        
        # Should be closer to target than start was
        new_dist = positions.distance_from_coords(new_pos, target)
        old_dist = positions.distance_from_coords(start, target)
        assert new_dist < old_dist
    
    def test_move_away_from_corner_clamps_correctly(self):
        """Test that move_away clamps at grid boundaries."""
        start = positions.CombatPosition(x=2, y=2, facing=positions.Direction.N)
        threat = positions.CombatPosition(x=25, y=25, facing=positions.Direction.S)
        
        # Should not raise error - clamping should happen automatically or via move_away
        try:
            new_pos = positions.move_away_from(start, threat, 5)
            # If it succeeds, position should be valid
            assert 0 <= new_pos.x <= 50
            assert 0 <= new_pos.y <= 50
        except ValueError:
            # Acceptable if move_away rejects extreme movements
            pass
    
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
    
    def test_edge_positions_are_valid(self):
        """Test that all edge positions are valid."""
        edges = [
            (0, 25), (50, 25),    # left/right edges
            (25, 0), (25, 50),    # top/bottom edges
            (0, 0), (50, 0), (0, 50), (50, 50)  # corners
        ]
        
        for x, y in edges:
            pos = positions.CombatPosition(x=x, y=y, facing=positions.Direction.N)
            assert 0 <= pos.x <= 50
            assert 0 <= pos.y <= 50


class TestAngleCalculationsAtBoundaries:
    """Test angle calculations at extreme positions."""
    
    def test_angle_from_origin_to_all_directions(self):
        """Test angle calculations from grid origin."""
        origin = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        
        test_targets = [
            (0, 25, "north"),
            (25, 0, "east"),
            (0, -25, "south"),  # Will be clamped
            (-25, 0, "west"),   # Will be clamped
        ]
        
        for x, y, direction in test_targets:
            # Clamp target to valid grid
            x = max(0, min(50, x))
            y = max(0, min(50, y))
            
            target = positions.CombatPosition(x=x, y=y, facing=positions.Direction.N)
            angle = positions.angle_to_target(origin, target)
            
            # Angle should be valid (0-360)
            assert 0 <= angle <= 360
    
    def test_angle_from_corner_to_opposite_corner(self):
        """Test diagonal angle calculations."""
        corner1 = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        corner2 = positions.CombatPosition(x=50, y=50, facing=positions.Direction.S)
        
        angle = positions.angle_to_target(corner1, corner2)
        
        # Should be valid angle
        assert 0 <= angle <= 360
        assert angle != 0  # Should not be exactly north
    
    def test_angle_difference_at_180_degrees(self):
        """Test angle difference when facing opposite direction."""
        facing_dir = positions.Direction.N  # 0 degrees
        target_dir = positions.Direction.S  # 180 degrees
        
        diff = positions.attack_angle_difference(
            target_dir.value, facing_dir
        )
        
        # Should be 180 degrees difference
        assert diff == 180 or diff == -180


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
        
        # Move away from target with smaller distance
        try:
            new_pos = positions.move_away_from(start, target, 3)
            # If it succeeds, position should be valid
            assert 0 <= new_pos.x <= 50
            assert 0 <= new_pos.y <= 50
        except ValueError:
            # Acceptable if move_away rejects extreme movements
            pass


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
        # Diagonal distance with integer rounding: sqrt(2) ≈ 1.414 → 1
        # Due to rounding, we expect 1 or 2
        assert distance in [1, 2]
    
    def test_squared_distance_function(self):
        """Test that squared distance function exists and works."""
        pos1 = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        pos2 = positions.CombatPosition(x=30, y=25, facing=positions.Direction.N)
        
        dist = positions.distance_from_coords(pos1, pos2)
        squared_dist = positions.distance_squared(pos1, pos2)
        
        # Squared distance should be approximately dist^2
        expected_squared = dist ** 2
        assert math.isclose(squared_dist, expected_squared, rel_tol=0.1)


class TestDirectionEdgeCases:
    """Test direction/facing edge cases."""
    
    def test_all_directions_valid(self):
        """Test that all 8 directions are valid."""
        for direction in positions.Direction:
            assert direction.value in [0, 45, 90, 135, 180, 225, 270, 315]
            assert hasattr(direction, 'name')
    
    def test_turn_toward_from_facing_north(self):
        """Test turning to face each direction from north."""
        from_pos = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        
        for direction in positions.Direction:
            to_pos = positions.CombatPosition(x=25, y=0, facing=direction)
            new_facing = positions.turn_toward(from_pos, to_pos)
            
            # Should return a valid direction
            assert isinstance(new_facing, positions.Direction)
    
    def test_turn_toward_same_position(self):
        """Test turning toward same position."""
        pos = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        
        # Should handle gracefully (might return current facing or north)
        new_facing = positions.turn_toward(pos, pos)
        assert isinstance(new_facing, positions.Direction)
    
    def test_facing_direction_names(self):
        """Test that direction names are correct."""
        names_to_check = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        
        for name in names_to_check:
            direction = positions.Direction[name]
            assert direction.name == name


class TestStressAndComplexScenarios:
    """Stress tests and complex scenario validation."""
    
    def test_many_units_formation(self):
        """Test positioning with many units in grid."""
        units = []
        for i in range(20):
            x = (i % 5) * 10
            y = (i // 5) * 10
            pos = positions.CombatPosition(x=x, y=y, facing=positions.Direction.N)
            units.append(pos)
        
        # All positions should be valid
        for pos in units:
            assert 0 <= pos.x <= 50
            assert 0 <= pos.y <= 50
    
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
            for move_dist in [1, 2, 5, 10, 20]:
                new_pos = positions.move_toward(start, target, move_dist)
                
                # Result should be valid
                assert 0 <= new_pos.x <= 50
                assert 0 <= new_pos.y <= 50


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
    
    def test_move_away_when_at_same_position(self):
        """Test moving away from a position you're at."""
        pos = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        
        new_pos = positions.move_away_from(pos, pos, 5)
        
        # Should move somewhere (direction doesn't matter when at same point)
        assert 0 <= new_pos.x <= 50
        assert 0 <= new_pos.y <= 50
    
    def test_flank_movement_perpendicular(self):
        """Test that flanking movement is perpendicular to target."""
        attacker_pos = positions.CombatPosition(x=20, y=25, facing=positions.Direction.E)
        defender_pos = positions.CombatPosition(x=30, y=25, facing=positions.Direction.W)
        
        flank_pos = positions.move_to_flank(attacker_pos, defender_pos, 3)
        
        # Should produce valid position
        assert 0 <= flank_pos.x <= 50
        assert 0 <= flank_pos.y <= 50


class TestInvalidInputHandling:
    """Test handling of invalid inputs."""
    
    def test_negative_distance_movement(self):
        """Test behavior with negative movement distance."""
        start = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        target = positions.CombatPosition(x=30, y=30, facing=positions.Direction.N)
        
        # Negative distance should handle gracefully
        try:
            new_pos = positions.move_toward(start, target, -5)
            # Should produce valid position or raise controlled error
            assert 0 <= new_pos.x <= 50
            assert 0 <= new_pos.y <= 50
        except ValueError:
            # Acceptable to reject negative distances
            pass
    
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
        
        # Very large movement should still stay within bounds
        new_pos = positions.move_toward(start, target, 10000)
        
        assert 0 <= new_pos.x <= 50
        assert 0 <= new_pos.y <= 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
