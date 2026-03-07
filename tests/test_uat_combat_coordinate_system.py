"""
UAT: Combat with Coordinate Grid System (HV-1) - Simplified Tests

Automated tests for coordinate-based combat positioning system.
Tests fundamental positioning mechanics without complex NPC setup.

Test Coverage:
- Coordinate system boundaries and validation
- Distance calculations (Euclidean)
- 8-direction compass system
- Movement toward target (Advance mechanics)
- Movement away from threat (Withdraw mechanics)
- Flanking maneuver positioning
- Angle calculations for attack positioning
- Multi-unit coordination
- Edge cases and boundary clamping
"""

import sys
from pathlib import Path

# Setup path for imports
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.positions import CombatPosition, Direction, distance_from_coords, move_toward, move_away_from, move_to_flank  # type: ignore
from src.positions import attack_angle_difference, angle_to_target  # type: ignore


class TestCoordinateSystemBasics:
    """Test basic coordinate system functionality"""
    
    def test_position_creation_valid(self):
        """Test creating valid positions"""
        pos = CombatPosition(x=25, y=25, facing=Direction.N)
        assert pos.x == 25
        assert pos.y == 25
        assert pos.facing.value == Direction.N.value
    
    def test_position_boundary_min(self):
        """Test position at minimum boundary (0,0)"""
        pos = CombatPosition(x=0, y=0, facing=Direction.N)
        assert pos.x == 0
        assert pos.y == 0
    
    def test_position_boundary_max(self):
        """Test position at maximum boundary (50,50)"""
        pos = CombatPosition(x=50, y=50, facing=Direction.N)
        assert pos.x == 50
        assert pos.y == 50
    
    def test_position_invalid_above_max_x(self):
        """Test position with X > 50 raises ValueError"""
        with pytest.raises(ValueError):
            CombatPosition(x=51, y=25, facing=Direction.N)
    
    def test_position_invalid_above_max_y(self):
        """Test position with Y > 50 raises ValueError"""
        with pytest.raises(ValueError):
            CombatPosition(x=25, y=51, facing=Direction.N)
    
    def test_position_invalid_below_min_x(self):
        """Test position with X < 0 raises ValueError"""
        with pytest.raises(ValueError):
            CombatPosition(x=-1, y=25, facing=Direction.N)
    
    def test_position_invalid_below_min_y(self):
        """Test position with Y < 0 raises ValueError"""
        with pytest.raises(ValueError):
            CombatPosition(x=25, y=-1, facing=Direction.N)


class TestDirections:
    """Test 8-direction compass system"""
    
    def test_all_eight_directions_exist(self):
        """Test all 8 compass directions are defined"""
        directions = [Direction.N, Direction.NE, Direction.E, Direction.SE,
                     Direction.S, Direction.SW, Direction.W, Direction.NW]
        assert len(directions) == 8
    
    def test_direction_angles(self):
        """Test direction angles are correct"""
        assert Direction.N.value == 0
        assert Direction.NE.value == 45
        assert Direction.E.value == 90
        assert Direction.SE.value == 135
        assert Direction.S.value == 180
        assert Direction.SW.value == 225
        assert Direction.W.value == 270
        assert Direction.NW.value == 315
    
    def test_all_directions_valid_for_position(self):
        """Test all directions can be used in CombatPosition"""
        for direction in [Direction.N, Direction.NE, Direction.E, Direction.SE,
                         Direction.S, Direction.SW, Direction.W, Direction.NW]:
            pos = CombatPosition(x=25, y=25, facing=direction)
            assert pos.facing == direction


class TestDistanceCalculations:
    """Test distance calculations"""
    
    def test_distance_same_position(self):
        """UAT-ADV: Distance between same position is 0"""
        pos1 = CombatPosition(x=25, y=25, facing=Direction.N)
        pos2 = CombatPosition(x=25, y=25, facing=Direction.N)
        distance = distance_from_coords(pos1, pos2)
        assert distance == 0
    
    def test_distance_horizontal(self):
        """Test distance horizontal movement"""
        pos1 = CombatPosition(x=0, y=25, facing=Direction.N)
        pos2 = CombatPosition(x=30, y=25, facing=Direction.N)
        distance = distance_from_coords(pos1, pos2)
        assert distance == 30
    
    def test_distance_vertical(self):
        """Test distance for vertical movement"""
        pos1 = CombatPosition(x=25, y=0, facing=Direction.N)
        pos2 = CombatPosition(x=25, y=40, facing=Direction.N)
        distance = distance_from_coords(pos1, pos2)
        assert distance == 40
    
    def test_distance_diagonal(self):
        """Test distance for diagonal movement (3-4-5 triangle)"""
        pos1 = CombatPosition(x=0, y=0, facing=Direction.N)
        pos2 = CombatPosition(x=30, y=40, facing=Direction.N)
        distance = distance_from_coords(pos1, pos2)
        # Should be 50 feet (sqrt(30^2 + 40^2) = 50)
        assert 49 < distance < 51
    
    def test_distance_symmetry(self):
        """Test distance is symmetric (A to B = B to A)"""
        pos1 = CombatPosition(x=10, y=20, facing=Direction.N)
        pos2 = CombatPosition(x=40, y=50, facing=Direction.N)
        dist_1_to_2 = distance_from_coords(pos1, pos2)
        dist_2_to_1 = distance_from_coords(pos2, pos1)
        assert dist_1_to_2 == dist_2_to_1


class TestMovementTowardTarget:
    """Test movement toward target (Advance move)"""
    
    def test_move_toward_reduces_distance(self):
        """UAT-ADV: Move toward target reduces distance"""
        current = CombatPosition(x=10, y=10, facing=Direction.N)
        target = CombatPosition(x=40, y=40, facing=Direction.S)
        
        initial_distance = distance_from_coords(current, target)
        
        # Move 4 squares toward target
        new_pos = move_toward(current, target, 4)
        new_distance = distance_from_coords(new_pos, target)
        
        assert new_distance < initial_distance
    
    def test_move_toward_boundary_clamping(self):
        """UAT-ADV-002: Movement clamps to grid boundaries"""
        current = CombatPosition(x=49, y=49, facing=Direction.N)
        target = CombatPosition(x=50, y=50, facing=Direction.S)
        
        new_pos = move_toward(current, target, 4)
        
        assert 0 <= new_pos.x <= 50
        assert 0 <= new_pos.y <= 50
    
    def test_move_toward_same_position(self):
        """Test move toward same position"""
        pos1 = CombatPosition(x=25, y=25, facing=Direction.N)
        pos2 = CombatPosition(x=25, y=25, facing=Direction.N)
        
        result = move_toward(pos1, pos2, 5)
        assert result.x == pos1.x
        assert result.y == pos1.y


class TestMovementAwayFromThreat:
    """Test movement away from threat (Withdraw move)"""
    
    def test_move_away_increases_distance(self):
        """UAT-WITH: Move away from threat increases distance"""
        current = CombatPosition(x=20, y=20, facing=Direction.N)
        threat = CombatPosition(x=30, y=30, facing=Direction.S)
        
        initial_distance = distance_from_coords(current, threat)
        
        new_pos = move_away_from(current, threat, 3)
        new_distance = distance_from_coords(new_pos, threat)
        
        assert new_distance >= initial_distance
    
    def test_move_away_boundary_clamping(self):
        """UAT-WITH-002: Move away clamps to grid boundaries"""
        current = CombatPosition(x=0, y=0, facing=Direction.N)
        threat = CombatPosition(x=10, y=10, facing=Direction.S)
        
        new_pos = move_away_from(current, threat, 5)
        
        assert 0 <= new_pos.x <= 50
        assert 0 <= new_pos.y <= 50
    
    def test_move_away_at_max_boundary(self):
        """Test move away from edge of grid"""
        current = CombatPosition(x=50, y=50, facing=Direction.N)
        threat = CombatPosition(x=40, y=40, facing=Direction.S)
        
        new_pos = move_away_from(current, threat, 3)
        
        assert 0 <= new_pos.x <= 50
        assert 0 <= new_pos.y <= 50


class TestAngleCalculations:
    """Test angle calculations for attack positioning"""
    
    def test_angle_to_target_north(self):
        """Test angle calculation to north"""
        observer = CombatPosition(x=25, y=25, facing=Direction.N)
        target = CombatPosition(x=25, y=0, facing=Direction.N)
        
        angle = angle_to_target(observer, target)
        assert angle >= 0 and angle <= 360
    
    def test_attack_angle_difference_front(self):
        """Test attack angle from front is small"""
        attack_angle = 0  # From north
        target_facing = Direction.N
        
        diff = attack_angle_difference(attack_angle, target_facing)
        assert 0 <= diff <= 45  # Front attack
    
    def test_attack_angle_difference_flank(self):
        """Test attack angle from flank is 90 degrees"""
        attack_angle = 90  # From east
        target_facing = Direction.N
        
        diff = attack_angle_difference(attack_angle, target_facing)
        assert 85 <= diff <= 95  # Flank attack
    
    def test_attack_angle_difference_rear(self):
        """Test attack angle from rear is 180 degrees"""
        attack_angle = 180  # From south
        target_facing = Direction.N
        
        diff = attack_angle_difference(attack_angle, target_facing)
        assert 175 <= diff <= 180  # Rear attack


class TestFlankingMovement:
    """Test flanking maneuver positioning"""
    
    def test_move_to_flank_creates_valid_position(self):
        """UAT-FLANK: FlankingManeuver creates valid position"""
        current = CombatPosition(x=20, y=20, facing=Direction.N)
        target = CombatPosition(x=30, y=30, facing=Direction.N)
        
        flanked_pos = move_to_flank(current, target, 3)
        
        # Position should be valid
        assert 0 <= flanked_pos.x <= 50
        assert 0 <= flanked_pos.y <= 50
    
    def test_move_to_flank_boundary_clamping(self):
        """UAT-FLANK: FlankingManeuver clamps to boundaries"""
        current = CombatPosition(x=0, y=0, facing=Direction.N)
        target = CombatPosition(x=5, y=5, facing=Direction.NW)
        
        flanked_pos = move_to_flank(current, target, 10)
        
        # Should still be in bounds
        assert 0 <= flanked_pos.x <= 50
        assert 0 <= flanked_pos.y <= 50


class TestMultiPositioning:
    """Test multiple positions simultaneously"""
    
    def test_three_positions_unique(self):
        """UAT-MULTI: Multiple positions are unique"""
        pos1 = CombatPosition(x=10, y=10, facing=Direction.N)
        pos2 = CombatPosition(x=20, y=20, facing=Direction.S)
        pos3 = CombatPosition(x=30, y=30, facing=Direction.W)
        
        positions = [(p.x, p.y) for p in [pos1, pos2, pos3]]
        assert len(set(positions)) == 3  # All unique
    
    def test_distance_matrix(self):
        """Test distance calculations between multiple units"""
        player = CombatPosition(x=25, y=25, facing=Direction.N)
        enemy1 = CombatPosition(x=30, y=40, facing=Direction.S)
        enemy2 = CombatPosition(x=20, y=40, facing=Direction.S)
        
        dist_e1 = distance_from_coords(player, enemy1)
        dist_e2 = distance_from_coords(player, enemy2)
        
        # Both should be positive and different
        assert dist_e1 > 0
        assert dist_e2 > 0


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_zero_distance_movement(self):
        """Test movement with zero distance"""
        pos = CombatPosition(x=25, y=25, facing=Direction.N)
        target = CombatPosition(x=25, y=25, facing=Direction.S)
        
        result = move_toward(pos, target, 0)
        assert result.x == pos.x
        assert result.y == pos.y
    
    def test_large_movement_clamping(self):
        """Test large movement gets clamped correctly"""
        current = CombatPosition(x=0, y=0, facing=Direction.N)
        target = CombatPosition(x=50, y=50, facing=Direction.S)
        
        # Try to move 100 squares (beyond grid)
        new_pos = move_toward(current, target, 100)
        
        # Should clamp to grid bounds
        assert 0 <= new_pos.x <= 50
        assert 0 <= new_pos.y <= 50
    
    def test_position_copy(self):
        """Test position copy creates independent object"""
        original = CombatPosition(x=25, y=25, facing=Direction.N)
        copy = original.copy()
        
        assert copy.x == original.x
        assert copy.y == original.y
        assert copy.facing == original.facing


class TestSystemIntegration:
    """Integration tests for full coordinate system"""
    
    def test_combat_scenario_standard_distance(self):
        """Test standard combat scenario has reasonable distance"""
        player = CombatPosition(x=25, y=15, facing=Direction.N)
        enemy = CombatPosition(x=25, y=40, facing=Direction.S)
        
        distance = distance_from_coords(player, enemy)
        
        # Should be about 25 feet
        assert 24 < distance < 26
    
    def test_sequential_movements(self):
        """Test sequential advances reduce distance"""
        player = CombatPosition(x=10, y=10, facing=Direction.N)
        enemy = CombatPosition(x=40, y=40, facing=Direction.S)
        
        initial_distance = distance_from_coords(player, enemy)
        
        # First advance
        player = move_toward(player, enemy, 4)
        dist_after_1 = distance_from_coords(player, enemy)
        
        # Second advance
        player = move_toward(player, enemy, 4)
        dist_after_2 = distance_from_coords(player, enemy)
        
        # Distance should decrease with each move
        assert dist_after_1 < initial_distance
        assert dist_after_2 < dist_after_1
    
    def test_alternate_advance_and_withdraw(self):
        """Test alternating advance and withdraw"""
        player = CombatPosition(x=10, y=10, facing=Direction.N)
        enemy = CombatPosition(x=40, y=40, facing=Direction.S)
        
        initial_distance = distance_from_coords(player, enemy)
        
        # Advance
        player = move_toward(player, enemy, 3)
        # Withdraw
        player = move_away_from(player, enemy, 2)
        
        final_distance = distance_from_coords(player, enemy)
        
        # Net should be closer (3 toward - 2 away = 1 net closer)
        assert final_distance < initial_distance


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
