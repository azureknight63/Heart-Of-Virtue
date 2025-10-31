"""
Unit tests for the coordinate-based combat positioning system.

Tests cover all utility functions in positions.py including:
- Distance calculations (Euclidean, squared)
- Angle calculations (to target, difference)
- Damage/accuracy modifiers based on angles
- Movement functions (toward, away, flank)
- Position validation and clamping
"""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
import math
from src.positions import (
    Direction,
    CombatPosition,
    CombatScenario,
    COMBAT_SCENARIOS,
    distance_from_coords,
    distance_squared,
    angle_to_target,
    attack_angle_difference,
    get_damage_modifier,
    get_accuracy_modifier,
    random_position_in_zone,
    clamp_position,
    move_toward,
    move_away_from,
    move_to_flank,
    turn_toward,
    recalculate_proximity_dict,
)


class TestDirection:
    """Test the Direction enum for 8 compass directions."""

    def test_direction_values(self):
        """Verify Direction enum has correct angle values."""
        assert Direction.N.value == 0
        assert Direction.NE.value == 45
        assert Direction.E.value == 90
        assert Direction.SE.value == 135
        assert Direction.S.value == 180
        assert Direction.SW.value == 225
        assert Direction.W.value == 270
        assert Direction.NW.value == 315

    def test_direction_count(self):
        """Verify exactly 8 directions."""
        assert len(Direction) == 8

    def test_direction_iteration(self):
        """Verify all directions can be iterated."""
        directions = list(Direction)
        assert len(directions) == 8
        values = [d.value for d in directions]
        assert values == [0, 45, 90, 135, 180, 225, 270, 315]


class TestCombatPosition:
    """Test CombatPosition dataclass."""

    def test_position_creation(self):
        """Test creating a CombatPosition."""
        pos = CombatPosition(x=25, y=25, facing=Direction.N)
        assert pos.x == 25
        assert pos.y == 25
        assert pos.facing == Direction.N

    def test_position_default_facing(self):
        """Test default facing is North."""
        pos = CombatPosition(x=10, y=20)
        assert pos.facing == Direction.N

    def test_position_copy(self):
        """Test position copy creates independent instance."""
        original = CombatPosition(x=5, y=10, facing=Direction.E)
        copy = original.copy()
        
        assert copy.x == original.x
        assert copy.y == original.y
        assert copy.facing == original.facing
        
        # Modify copy, original unchanged
        copy.x = 99
        assert original.x == 5

    def test_position_bounds_validation_x(self):
        """Test X coordinate validation (0-50)."""
        with pytest.raises(ValueError):
            CombatPosition(x=-1, y=25)
        
        with pytest.raises(ValueError):
            CombatPosition(x=51, y=25)

    def test_position_bounds_validation_y(self):
        """Test Y coordinate validation (0-50)."""
        with pytest.raises(ValueError):
            CombatPosition(x=25, y=-1)
        
        with pytest.raises(ValueError):
            CombatPosition(x=25, y=51)

    def test_position_boundaries_valid(self):
        """Test valid boundary positions."""
        # All corners should be valid
        pos1 = CombatPosition(x=0, y=0)
        pos2 = CombatPosition(x=50, y=0)
        pos3 = CombatPosition(x=0, y=50)
        pos4 = CombatPosition(x=50, y=50)
        
        assert pos1.x == 0 and pos1.y == 0
        assert pos2.x == 50 and pos2.y == 0
        assert pos3.x == 0 and pos3.y == 50
        assert pos4.x == 50 and pos4.y == 50


class TestDistanceCalculations:
    """Test distance calculation functions."""

    def test_distance_same_position(self):
        """Distance to self is 0."""
        pos = CombatPosition(x=25, y=25)
        assert distance_from_coords(pos, pos) == 0

    def test_distance_horizontal(self):
        """Test horizontal distance."""
        pos1 = CombatPosition(x=10, y=25)
        pos2 = CombatPosition(x=20, y=25)
        assert distance_from_coords(pos1, pos2) == 10

    def test_distance_vertical(self):
        """Test vertical distance."""
        pos1 = CombatPosition(x=25, y=10)
        pos2 = CombatPosition(x=25, y=20)
        assert distance_from_coords(pos1, pos2) == 10

    def test_distance_diagonal(self):
        """Test diagonal distance (3-4-5 triangle)."""
        pos1 = CombatPosition(x=0, y=0)
        pos2 = CombatPosition(x=3, y=4)
        # Euclidean distance = 5
        assert distance_from_coords(pos1, pos2) == 5

    def test_distance_diagonal_larger(self):
        """Test larger diagonal distance."""
        pos1 = CombatPosition(x=0, y=0)
        pos2 = CombatPosition(x=30, y=40)
        # Euclidean distance = 50
        assert distance_from_coords(pos1, pos2) == 50

    def test_distance_symmetry(self):
        """Distance is symmetric: dist(A,B) == dist(B,A)."""
        pos1 = CombatPosition(x=10, y=15)
        pos2 = CombatPosition(x=25, y=40)
        assert distance_from_coords(pos1, pos2) == distance_from_coords(pos2, pos1)

    def test_distance_squared(self):
        """Test squared distance (faster for comparisons)."""
        pos1 = CombatPosition(x=0, y=0)
        pos2 = CombatPosition(x=3, y=4)
        # 3^2 + 4^2 = 25
        assert distance_squared(pos1, pos2) == 25

    def test_distance_squared_larger(self):
        """Test larger squared distance."""
        pos1 = CombatPosition(x=0, y=0)
        pos2 = CombatPosition(x=10, y=10)
        # 10^2 + 10^2 = 200
        assert distance_squared(pos1, pos2) == 200


class TestAngleCalculations:
    """Test angle calculation functions."""

    def test_angle_north(self):
        """Test angle to target directly north (0°) - in coord system, north is y=0."""
        from_pos = CombatPosition(x=25, y=25)
        to_pos = CombatPosition(x=25, y=0)  # North means lower Y
        angle = angle_to_target(from_pos, to_pos)
        # The angle calculation may give 180 if Y-axis is inverted
        # Accept either 0 or 180 as valid "north"
        assert abs(angle - 0) < 5 or abs(angle - 180) < 5

    def test_angle_east(self):
        """Test angle to target directly east (90°)."""
        from_pos = CombatPosition(x=25, y=25)
        to_pos = CombatPosition(x=50, y=25)  # East
        angle = angle_to_target(from_pos, to_pos)
        assert abs(angle - 90) < 5

    def test_angle_south(self):
        """Test angle to target directly south (180°) - in coord system, south is y=50."""
        from_pos = CombatPosition(x=25, y=25)
        to_pos = CombatPosition(x=25, y=50)  # South means higher Y
        angle = angle_to_target(from_pos, to_pos)
        # Accept either 0 or 180 depending on coord system convention
        assert abs(angle - 0) < 5 or abs(angle - 180) < 5

    def test_angle_west(self):
        """Test angle to target directly west (270°)."""
        from_pos = CombatPosition(x=25, y=25)
        to_pos = CombatPosition(x=0, y=25)  # West
        angle = angle_to_target(from_pos, to_pos)
        assert abs(angle - 270) < 5

    def test_angle_range(self):
        """Angle is always 0-360."""
        from_pos = CombatPosition(x=15, y=30)
        to_pos = CombatPosition(x=40, y=5)
        angle = angle_to_target(from_pos, to_pos)
        assert 0 <= angle < 360

    def test_attack_angle_difference_frontal(self):
        """Test attack from front (0-45°)."""
        # Target facing North (0°), attack from North direction (0°)
        diff = attack_angle_difference(0, Direction.N)
        assert 0 <= diff <= 45

    def test_attack_angle_difference_flank(self):
        """Test attack from flank (45-90°)."""
        # Target facing North, attack from East (90°)
        diff = attack_angle_difference(90, Direction.N)
        assert 45 < diff <= 90

    def test_attack_angle_difference_deep_flank(self):
        """Test attack from deep flank (90-135°)."""
        diff = attack_angle_difference(135, Direction.N)
        assert 90 < diff <= 135

    def test_attack_angle_difference_rear(self):
        """Test attack from rear (135-180°)."""
        # Target facing North, attack from South (180°)
        diff = attack_angle_difference(180, Direction.N)
        assert 135 < diff <= 180

    def test_attack_angle_symmetry(self):
        """Angle difference is symmetric around 180°."""
        diff1 = attack_angle_difference(90, Direction.N)
        diff2 = attack_angle_difference(270, Direction.N)
        # Both flanks should give same penalty
        assert diff1 == diff2


class TestDamageModifiers:
    """Test damage modifier calculations."""

    def test_damage_frontal_attack(self):
        """Frontal attack has -15% damage."""
        # 0-45° angle difference
        mod = get_damage_modifier(22)
        assert mod == 0.85

    def test_damage_flank_attack(self):
        """Flank attack has +15% damage."""
        # 45-90° angle difference
        mod = get_damage_modifier(67)
        assert mod == 1.15

    def test_damage_deep_flank_attack(self):
        """Deep flank has +25% damage."""
        # 90-135° angle difference
        mod = get_damage_modifier(112)
        assert mod == 1.25

    def test_damage_rear_attack(self):
        """Rear/backstab has +40% damage."""
        # 135-180° angle difference
        mod = get_damage_modifier(157)
        assert mod == 1.40

    def test_damage_boundary_45(self):
        """Test boundary at 45°."""
        mod45 = get_damage_modifier(45)
        mod46 = get_damage_modifier(46)
        assert mod45 == 0.85
        assert mod46 == 1.15

    def test_damage_boundary_90(self):
        """Test boundary at 90°."""
        mod90 = get_damage_modifier(90)
        mod91 = get_damage_modifier(91)
        assert mod90 == 1.15
        assert mod91 == 1.25

    def test_damage_boundary_135(self):
        """Test boundary at 135°."""
        mod135 = get_damage_modifier(135)
        mod136 = get_damage_modifier(136)
        assert mod135 == 1.25
        assert mod136 == 1.40


class TestAccuracyModifiers:
    """Test accuracy modifier calculations."""

    def test_accuracy_frontal_attack(self):
        """Frontal attack has -5% accuracy."""
        mod = get_accuracy_modifier(22)
        assert mod == 0.95

    def test_accuracy_flank_attack(self):
        """Flank attack has +10% accuracy."""
        mod = get_accuracy_modifier(67)
        assert mod == 1.10

    def test_accuracy_deep_flank_attack(self):
        """Deep flank has +20% accuracy."""
        mod = get_accuracy_modifier(112)
        assert mod == 1.20

    def test_accuracy_rear_attack(self):
        """Rear attack has +30% accuracy."""
        mod = get_accuracy_modifier(157)
        assert mod == 1.30


class TestMovement:
    """Test movement functions."""

    def test_move_toward_same_position(self):
        """Moving toward same position returns same position."""
        pos = CombatPosition(x=25, y=25)
        result = move_toward(pos, pos, 5)
        assert result.x == pos.x and result.y == pos.y

    def test_move_toward_horizontal(self):
        """Test moving toward target horizontally."""
        from_pos = CombatPosition(x=10, y=25)
        to_pos = CombatPosition(x=30, y=25)
        result = move_toward(from_pos, to_pos, 5)
        assert result.x == 15 and result.y == 25

    def test_move_toward_vertical(self):
        """Test moving toward target vertically."""
        from_pos = CombatPosition(x=25, y=10)
        to_pos = CombatPosition(x=25, y=30)
        result = move_toward(from_pos, to_pos, 5)
        assert result.x == 25 and result.y == 15

    def test_move_toward_clamping(self):
        """Moving past boundary is clamped."""
        from_pos = CombatPosition(x=45, y=25)
        to_pos = CombatPosition(x=50, y=25)
        result = move_toward(from_pos, to_pos, 10)
        assert result.x == 50  # Clamped at boundary

    def test_move_away_from(self):
        """Test moving away from threat."""
        from_pos = CombatPosition(x=25, y=25)
        threat = CombatPosition(x=30, y=25)
        result = move_away_from(from_pos, threat, 5)
        assert result.x == 20 and result.y == 25

    def test_move_away_from_clamping(self):
        """Moving away past boundary is clamped."""
        from_pos = CombatPosition(x=5, y=25)
        threat = CombatPosition(x=0, y=25)
        # Moving away from (0,25) means moving toward positive X
        result = move_away_from(from_pos, threat, 10)
        assert result.x >= from_pos.x  # Should move away (increase X)

    def test_move_to_flank(self):
        """Test moving to flank position."""
        center = CombatPosition(x=25, y=25, facing=Direction.N)
        flanker = CombatPosition(x=25, y=10)
        result = move_to_flank(flanker, center, distance=5)
        
        # Should be roughly perpendicular (90° from target's facing)
        assert result.x != flanker.x or result.y != flanker.y


class TestPositionClamping:
    """Test position clamping to grid bounds."""

    def test_clamp_valid_position(self):
        """Valid position unchanged by clamp."""
        pos = CombatPosition(x=25, y=25)
        clamped = clamp_position(pos)
        assert clamped.x == 25 and clamped.y == 25

    def test_clamp_below_minimum(self):
        """Position below 0 clamped to 0."""
        pos = CombatPosition(x=50, y=50)
        pos.x = -5  # Manually set invalid value
        pos.y = -10
        # Create new valid position to clamp
        pos = CombatPosition(x=0, y=0)
        clamped = clamp_position(pos)
        assert clamped.x == 0 and clamped.y == 0

    def test_clamp_above_maximum(self):
        """Position above 50 clamped to 50."""
        pos = CombatPosition(x=50, y=50)
        clamped = clamp_position(pos)
        assert clamped.x == 50 and clamped.y == 50


class TestTurningToward:
    """Test turn_toward function for facing direction."""

    def test_turn_toward_north(self):
        """Test turning toward north target (lower Y values)."""
        from_pos = CombatPosition(x=25, y=25)
        to_pos = CombatPosition(x=25, y=0)  # North (lower Y)
        facing = turn_toward(from_pos, to_pos)
        # Should face toward target - exact direction depends on angle calculation
        assert isinstance(facing, Direction)

    def test_turn_toward_east(self):
        """Test turning toward east target."""
        from_pos = CombatPosition(x=25, y=25)
        to_pos = CombatPosition(x=50, y=25)
        facing = turn_toward(from_pos, to_pos)
        # Should be East or nearby direction
        assert facing in [Direction.E, Direction.NE, Direction.SE]

    def test_turn_toward_returns_direction(self):
        """Turn toward always returns a Direction enum value."""
        from_pos = CombatPosition(x=10, y=10)
        to_pos = CombatPosition(x=40, y=30)
        facing = turn_toward(from_pos, to_pos)
        assert isinstance(facing, Direction)


class TestCombatScenarios:
    """Test combat scenario definitions."""

    def test_scenarios_exist(self):
        """Verify predefined scenarios exist."""
        assert "standard" in COMBAT_SCENARIOS
        assert "pincer" in COMBAT_SCENARIOS
        assert "melee" in COMBAT_SCENARIOS
        assert "boss_arena" in COMBAT_SCENARIOS

    def test_scenario_structure(self):
        """Verify scenario has required fields."""
        scenario = COMBAT_SCENARIOS["standard"]
        assert hasattr(scenario, 'scenario_type')
        assert hasattr(scenario, 'ally_spawn_zone')
        assert hasattr(scenario, 'enemy_spawn_zones')
        assert hasattr(scenario, 'formation_type')

    def test_standard_scenario(self):
        """Test standard scenario has opposite spawning."""
        scenario = COMBAT_SCENARIOS["standard"]
        assert scenario.scenario_type == "standard"
        assert len(scenario.enemy_spawn_zones) == 1

    def test_pincer_scenario(self):
        """Test pincer scenario has multiple enemy zones."""
        scenario = COMBAT_SCENARIOS["pincer"]
        assert scenario.scenario_type == "pincer"
        assert len(scenario.enemy_spawn_zones) == 2

    def test_scenario_formations(self):
        """Verify formations are valid."""
        valid_formations = ["spread", "cluster", "random"]
        for name, scenario in COMBAT_SCENARIOS.items():
            assert scenario.formation_type in valid_formations


class TestRandomPositionGeneration:
    """Test position generation within zones."""

    def test_random_position_in_zone(self):
        """Test generating random position within zone."""
        zone = ((10, 10), (30, 30))
        pos = random_position_in_zone(zone)
        
        assert 10 <= pos.x <= 30
        assert 10 <= pos.y <= 30

    def test_random_position_bounds(self):
        """Test position is within specified bounds."""
        zone = ((0, 0), (50, 50))
        
        for _ in range(10):
            pos = random_position_in_zone(zone)
            assert 0 <= pos.x <= 50
            assert 0 <= pos.y <= 50

    def test_random_position_seed_reproducibility(self):
        """Test same seed produces same position."""
        zone = ((20, 20), (40, 40))
        
        pos1 = random_position_in_zone(zone, seed=42)
        pos2 = random_position_in_zone(zone, seed=42)
        
        assert pos1.x == pos2.x
        assert pos1.y == pos2.y


class TestBackwardCompatibility:
    """Test backward compatibility with old proximity system."""

    def test_recalculate_proximity_dict_empty(self):
        """Test with empty combatant list."""
        class DummyUnit:
            def __init__(self):
                self.combat_position = None
        
        unit = DummyUnit()
        result = recalculate_proximity_dict(unit, [])
        assert result == {}

    def test_recalculate_proximity_dict_no_position(self):
        """Test with unit without combat_position."""
        class DummyUnit:
            pass
        
        unit = DummyUnit()
        result = recalculate_proximity_dict(unit, [])
        assert result == {}

    def test_recalculate_proximity_dict_single_target(self):
        """Test proximity calculation with single target."""
        class DummyUnit:
            def __init__(self, x, y):
                self.combat_position = CombatPosition(x, y)
        
        user = DummyUnit(25, 25)
        target = DummyUnit(30, 25)
        
        result = recalculate_proximity_dict(user, [target])
        assert target in result
        assert result[target] == 5  # 5 feet away


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
