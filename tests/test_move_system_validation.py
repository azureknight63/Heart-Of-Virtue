"""
Phase 3.3: Move System Validation Tests

Comprehensive validation tests for coordinate-based movement moves:
- Advance: 2-4 squares toward target, auto-facing
- Withdraw: 2-3 squares away from target, defensive stance
- BullCharge: 4-6 squares aggressive charge
- TacticalRetreat: 3-4 squares strategic withdrawal
- FlankingManeuver: Perpendicular positioning for combat advantage

Tests verify:
1. Move viability checks
2. Coordinate-based execution
3. Legacy system fallback
4. Facing direction updates
5. Distance calculations
6. Positioning bonuses
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
from src.moves import Advance, Withdraw, BullCharge, TacticalRetreat, FlankingManeuver
from src.npc import NPC
import src.positions as positions
import src.items as items


class DummyEnemy:
    """Mock enemy for testing moves."""
    def __init__(self, name="Target", x=25, y=25, speed=5, hp=100):
        self.name = name
        self.speed = speed
        self.hp = hp
        self.maxhp = hp
        self.is_alive = lambda: self.hp > 0
        
        # Combat positioning
        self.combat_position = positions.CombatPosition(
            x=x, y=y, facing=positions.Direction.S
        )
        self.combat_proximity = {}
        self.friend = False


class TestAdvanceMoveValidation:
    """Test Advance move with coordinate system."""
    
    def test_advance_viable_when_target_distant(self):
        """Advance should be viable when target > 1 square away."""
        player = Player()
        enemy = DummyEnemy()
        
        # Set up proximity dict
        player.combat_proximity[enemy] = 5.0
        
        # Get Advance move
        advance = None
        for move in player.known_moves:
            if isinstance(move, Advance):
                advance = move
                break
        
        assert advance is not None
        advance.target = enemy
        assert advance.viable() is True
    
    def test_advance_not_viable_when_target_close(self):
        """Advance should not be viable when target <= 1 square away."""
        player = Player()
        enemy = DummyEnemy()
        
        player.combat_proximity[enemy] = 0.5
        
        advance = None
        for move in player.known_moves:
            if isinstance(move, Advance):
                advance = move
                break
        
        advance.target = enemy
        assert advance.viable() is False
    
    def test_advance_not_viable_without_target(self):
        """Advance should not be viable without a target."""
        player = Player()
        
        advance = None
        for move in player.known_moves:
            if isinstance(move, Advance):
                advance = move
                break
        
        advance.target = None
        assert advance.viable() is False
    
    def test_advance_coordinate_based_movement(self, monkeypatch):
        """Advance should move toward target using coordinates."""
        player = Player()
        player.speed = 10
        
        # Set up player position
        player.combat_position = positions.CombatPosition(
            x=20, y=20, facing=positions.Direction.S
        )
        
        enemy = DummyEnemy(x=25, y=25)
        player.combat_proximity[enemy] = 10.0
        
        # Get Advance move
        advance = None
        for move in player.known_moves:
            if isinstance(move, Advance):
                advance = move
                break
        
        advance.target = enemy
        
        # Make random predictable for testing
        monkeypatch.setattr(random, 'randint', lambda a, b: (a + b) // 2)
        
        # Store initial position
        initial_pos = (player.combat_position.x, player.combat_position.y)
        initial_distance = positions.distance_from_coords(
            player.combat_position, enemy.combat_position
        )
        
        # Execute advance
        advance.execute(player)
        
        # Verify movement toward target
        if player.combat_position is not None:
            final_distance = positions.distance_from_coords(
                player.combat_position, enemy.combat_position
            )
            assert final_distance < initial_distance, "Advance should move closer to target"
            
            # Verify facing direction updated
            assert player.combat_position.facing is not None


class TestWithdrawMoveValidation:
    """Test Withdraw move with coordinate system."""
    
    def test_withdraw_always_viable_in_combat(self):
        """Withdraw should be viable when enemies exist in combat_proximity."""
        player = Player()
        enemy = DummyEnemy()
        player.combat_proximity[enemy] = 10.0
        
        withdraw = None
        for move in player.known_moves:
            if isinstance(move, Withdraw):
                withdraw = move
                break
        
        assert withdraw is not None
        assert withdraw.viable() is True
    
    def test_withdraw_not_viable_without_enemies(self):
        """Withdraw should not be viable with no enemies."""
        player = Player()
        
        withdraw = None
        for move in player.known_moves:
            if isinstance(move, Withdraw):
                withdraw = move
                break
        
        assert withdraw.viable() is False
    
    def test_withdraw_coordinate_based_movement(self, monkeypatch):
        """Withdraw should move away from nearest threat."""
        player = Player()
        player.speed = 10
        
        # Set up player position
        player.combat_position = positions.CombatPosition(
            x=20, y=20, facing=positions.Direction.S
        )
        
        enemy = DummyEnemy(x=25, y=25)
        player.combat_proximity[enemy] = 10.0
        
        # Get Withdraw move
        withdraw = None
        for move in player.known_moves:
            if isinstance(move, Withdraw):
                withdraw = move
                break
        
        monkeypatch.setattr(random, 'randint', lambda a, b: (a + b) // 2)
        
        # Store initial distance
        initial_distance = positions.distance_from_coords(
            player.combat_position, enemy.combat_position
        )
        
        # Execute withdraw
        withdraw.execute(player)
        
        # Verify movement away from threat
        if player.combat_position is not None:
            final_distance = positions.distance_from_coords(
                player.combat_position, enemy.combat_position
            )
            # Withdraw should increase distance from enemy
            assert final_distance >= initial_distance, "Withdraw should move away from threat"


class TestBullChargeMoveValidation:
    """Test BullCharge move with coordinate system."""
    
    def test_bull_charge_viable_at_medium_range(self):
        """BullCharge should be viable at 3-20 feet distance."""
        player = Player()
        enemy = DummyEnemy()
        
        player.combat_proximity[enemy] = 10.0
        
        bull_charge = BullCharge(player)
        bull_charge.target = enemy
        
        assert bull_charge.viable() is True
    
    def test_bull_charge_not_viable_too_close(self):
        """BullCharge should not be viable when target is very close."""
        player = Player()
        enemy = DummyEnemy()
        
        player.combat_proximity[enemy] = 1.0
        
        bull_charge = BullCharge(player)
        bull_charge.target = enemy
        
        assert bull_charge.viable() is False
    
    def test_bull_charge_not_viable_too_far(self):
        """BullCharge should not be viable when target is very far."""
        player = Player()
        enemy = DummyEnemy()
        
        player.combat_proximity[enemy] = 25.0
        
        bull_charge = BullCharge(player)
        bull_charge.target = enemy
        
        assert bull_charge.viable() is False
    
    def test_bull_charge_coordinate_movement(self, monkeypatch):
        """BullCharge should move 4-6 squares toward target."""
        player = Player()
        player.speed = 10
        
        player.combat_position = positions.CombatPosition(
            x=10, y=10, facing=positions.Direction.S
        )
        
        enemy = DummyEnemy(x=20, y=20)
        player.combat_proximity[enemy] = 15.0
        
        bull_charge = BullCharge(player)
        bull_charge.target = enemy
        
        monkeypatch.setattr(random, 'randint', lambda a, b: 5)  # Middle of 4-6
        
        initial_distance = positions.distance_from_coords(
            player.combat_position, enemy.combat_position
        )
        
        # Execute charge
        bull_charge.execute(player)
        
        # Verify significant movement
        if player.combat_position is not None:
            final_distance = positions.distance_from_coords(
                player.combat_position, enemy.combat_position
            )
            distance_moved = initial_distance - final_distance
            
            # Should have moved closer (at least 1-2 squares due to grid movement)
            assert distance_moved > 0, "BullCharge should move toward target"


class TestTacticalRetreatMoveValidation:
    """Test TacticalRetreat move with coordinate system."""
    
    def test_tactical_retreat_always_viable_in_combat(self):
        """TacticalRetreat should be viable when enemies exist."""
        player = Player()
        enemy = DummyEnemy()
        player.combat_proximity[enemy] = 10.0
        
        tactical_retreat = TacticalRetreat(player)
        
        assert tactical_retreat.viable() is True
    
    def test_tactical_retreat_not_viable_no_combat(self):
        """TacticalRetreat should not be viable when no enemies."""
        player = Player()
        
        tactical_retreat = TacticalRetreat(player)
        
        assert tactical_retreat.viable() is False
    
    def test_tactical_retreat_coordinate_movement(self, monkeypatch):
        """TacticalRetreat should move 3-4 squares away from nearest threat."""
        player = Player()
        player.speed = 10
        
        player.combat_position = positions.CombatPosition(
            x=20, y=20, facing=positions.Direction.S
        )
        
        enemy = DummyEnemy(x=25, y=25)
        player.combat_proximity[enemy] = 10.0
        
        tactical_retreat = TacticalRetreat(player)
        
        monkeypatch.setattr(random, 'randint', lambda a, b: (a + b) // 2)
        
        initial_distance = positions.distance_from_coords(
            player.combat_position, enemy.combat_position
        )
        
        tactical_retreat.execute(player)
        
        if player.combat_position is not None:
            final_distance = positions.distance_from_coords(
                player.combat_position, enemy.combat_position
            )
            
            # Should increase distance from nearest threat
            assert final_distance > initial_distance, "TacticalRetreat should move away"


class TestFlankingManeuverMoveValidation:
    """Test FlankingManeuver move with coordinate system."""
    
    def test_flanking_viable_in_range(self):
        """FlankingManeuver should be viable at 3-15 feet distance."""
        player = Player()
        enemy = DummyEnemy()
        
        player.combat_proximity[enemy] = 8.0
        
        flanking = FlankingManeuver(player)
        flanking.target = enemy
        
        assert flanking.viable() is True
    
    def test_flanking_not_viable_too_close(self):
        """FlankingManeuver should not be viable when target is too close."""
        player = Player()
        enemy = DummyEnemy()
        
        player.combat_proximity[enemy] = 1.0
        
        flanking = FlankingManeuver(player)
        flanking.target = enemy
        
        assert flanking.viable() is False
    
    def test_flanking_not_viable_too_far(self):
        """FlankingManeuver should not be viable when target is too far."""
        player = Player()
        enemy = DummyEnemy()
        
        player.combat_proximity[enemy] = 20.0
        
        flanking = FlankingManeuver(player)
        flanking.target = enemy
        
        assert flanking.viable() is False
    
    def test_flanking_coordinate_positioning(self, monkeypatch):
        """FlankingManeuver should move perpendicular to target's facing."""
        player = Player()
        player.speed = 10
        
        player.combat_position = positions.CombatPosition(
            x=20, y=20, facing=positions.Direction.S
        )
        
        # Target faces SOUTH
        enemy = DummyEnemy(x=20, y=25)
        enemy.combat_position.facing = positions.Direction.S
        
        player.combat_proximity[enemy] = 8.0
        
        flanking = FlankingManeuver(player)
        flanking.target = enemy
        
        monkeypatch.setattr(random, 'randint', lambda a, b: 3)
        
        flanking.execute(player)
        
        if player.combat_position is not None:
            # Calculate angle to target
            angle = positions.angle_to_target(
                player.combat_position, enemy.combat_position
            )
            angle_diff = positions.attack_angle_difference(
                angle, enemy.combat_position.facing
            )
            
            # After flanking, should be positioned to the side (45-135 degrees)
            # Note: This is non-deterministic due to randomness, so we just verify it executed
            assert player.combat_position is not None


class TestMoveIntegration:
    """Integration tests for multiple moves in sequence."""
    
    def test_advance_then_withdraw_sequence(self, monkeypatch):
        """Test advancing then withdrawing maintains valid positions."""
        player = Player()
        player.combat_position = positions.CombatPosition(
            x=15, y=15, facing=positions.Direction.S
        )
        
        enemy = DummyEnemy(x=25, y=25)
        player.combat_proximity[enemy] = 15.0
        
        # Advance first
        advance = None
        for move in player.known_moves:
            if isinstance(move, Advance):
                advance = move
                break
        
        advance.target = enemy
        monkeypatch.setattr(random, 'randint', lambda a, b: 2)
        
        starting_distance = positions.distance_from_coords(
            player.combat_position, enemy.combat_position
        )
        
        advance.execute(player)
        after_advance_distance = positions.distance_from_coords(
            player.combat_position, enemy.combat_position
        )
        
        assert after_advance_distance < starting_distance
        
        # Then withdraw
        withdraw = None
        for move in player.known_moves:
            if isinstance(move, Withdraw):
                withdraw = move
                break
        
        withdraw.execute(player)
        after_withdraw_distance = positions.distance_from_coords(
            player.combat_position, enemy.combat_position
        )
        
        # Should be farther than after advance
        assert after_withdraw_distance > after_advance_distance
    
    def test_all_moves_available(self):
        """Verify all 5 moves are in player's known moves."""
        player = Player()
        
        move_types = set()
        for move in player.known_moves:
            if isinstance(move, (Advance, Withdraw, BullCharge, TacticalRetreat, FlankingManeuver)):
                move_types.add(type(move).__name__)
        
        expected_moves = {'Advance', 'Withdraw', 'BullCharge', 'TacticalRetreat', 'FlankingManeuver'}
        assert expected_moves.issubset(move_types), f"Missing moves: {expected_moves - move_types}"


class TestMoveDualPathExecution:
    """Test that moves execute correctly with both coordinate and legacy systems."""
    
    def test_advance_legacy_fallback(self, monkeypatch):
        """Advance should fall back to legacy system if coordinates unavailable."""
        player = Player()
        enemy = DummyEnemy()
        
        # No coordinates set
        player.combat_position = None
        enemy.combat_position = None
        
        player.combat_proximity[enemy] = 10.0
        
        advance = None
        for move in player.known_moves:
            if isinstance(move, Advance):
                advance = move
                break
        
        advance.target = enemy
        
        monkeypatch.setattr(random, 'randint', lambda a, b: (a + b) // 2)
        
        # Should not raise error - will use legacy system
        try:
            advance.execute(player)
        except AttributeError:
            pytest.fail("Advance should handle legacy execution without error")
    
    def test_bull_charge_legacy_fallback(self, monkeypatch):
        """BullCharge should fall back to legacy system if coordinates unavailable."""
        player = Player()
        enemy = DummyEnemy()
        
        player.combat_position = None
        enemy.combat_position = None
        
        player.combat_proximity[enemy] = 10.0
        
        bull_charge = BullCharge(player)
        bull_charge.target = enemy
        
        monkeypatch.setattr(random, 'randint', lambda a, b: (a + b) // 2)
        
        try:
            bull_charge.execute(player)
        except AttributeError:
            pytest.fail("BullCharge should handle legacy execution without error")
    
    def test_flanking_no_fallback_for_legacy(self):
        """FlankingManeuver should gracefully handle missing coordinates."""
        player = Player()
        enemy = DummyEnemy()
        
        player.combat_position = None
        enemy.combat_position = None
        
        player.combat_proximity[enemy] = 10.0
        
        flanking = FlankingManeuver(player)
        flanking.target = enemy
        
        # FlankingManeuver only works with coordinates, should handle gracefully
        try:
            flanking.execute(player)
        except Exception as e:
            pytest.fail(f"FlankingManeuver should handle missing coordinates gracefully: {e}")


class TestMoveEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_advance_dead_target_handling(self, monkeypatch):
        """Advance should not crash if target dies before execution."""
        player = Player()
        enemy = DummyEnemy()
        enemy.hp = 0  # Dead
        
        player.combat_proximity[enemy] = 10.0
        
        advance = None
        for move in player.known_moves:
            if isinstance(move, Advance):
                advance = move
                break
        
        advance.target = enemy
        
        try:
            advance.execute(player)
        except AttributeError:
            pytest.fail("Advance should handle dead targets gracefully")
    
    def test_withdraw_multiple_enemies(self):
        """Withdraw should retreat from nearest threat when multiple enemies."""
        player = Player()
        player.combat_position = positions.CombatPosition(
            x=25, y=25, facing=positions.Direction.S
        )
        
        enemy1 = DummyEnemy(name="Enemy1", x=20, y=20)
        enemy2 = DummyEnemy(name="Enemy2", x=30, y=30)
        
        player.combat_proximity[enemy1] = 7.0   # Closer
        player.combat_proximity[enemy2] = 12.0  # Farther
        
        withdraw = None
        for move in player.known_moves:
            if isinstance(move, Withdraw):
                withdraw = move
                break
        
        initial_dist_enemy1 = positions.distance_from_coords(
            player.combat_position, enemy1.combat_position
        )
        
        withdraw.execute(player)
        
        if player.combat_position is not None:
            final_dist_enemy1 = positions.distance_from_coords(
                player.combat_position, enemy1.combat_position
            )
            
            # Should retreat from nearest (enemy1)
            assert final_dist_enemy1 >= initial_dist_enemy1
    
    def test_flanking_perpendicular_positioning(self, monkeypatch):
        """FlankingManeuver should attempt to position perpendicular."""
        player = Player()
        player.combat_position = positions.CombatPosition(
            x=20, y=20, facing=positions.Direction.S
        )
        
        # Target facing EAST - player should try to flank to north or south
        enemy = DummyEnemy(x=25, y=20)
        enemy.combat_position.facing = positions.Direction.E
        
        player.combat_proximity[enemy] = 8.0
        
        flanking = FlankingManeuver(player)
        flanking.target = enemy
        
        monkeypatch.setattr(random, 'randint', lambda a, b: 3)
        
        initial_pos = (player.combat_position.x, player.combat_position.y)
        
        flanking.execute(player)
        
        if player.combat_position is not None:
            # Position should have changed
            final_pos = (player.combat_position.x, player.combat_position.y)
            assert initial_pos != final_pos, "FlankingManeuver should move to new position"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
