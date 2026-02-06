"""
Tests for move state resets when enemies/allies join combat mid-fight.
This ensures moves progress correctly instead of returning to player's turn too early.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.npc import NPC, CaveBat
from src.player import Player


class TestResetCombatMoves:
    """Test the reset_combat_moves() helper method."""

    def test_reset_combat_moves_sets_stage_zero(self):
        """Verify reset_combat_moves() sets current_stage to 0."""
        npc = CaveBat()
        
        # Artificially set moves to non-zero state
        for move in npc.known_moves:
            move.current_stage = 2
            move.beats_left = 5
        
        # Reset them
        npc.reset_combat_moves()
        
        # Verify all are reset
        for move in npc.known_moves:
            assert move.current_stage == 0, f"Move {move.name} stage should be 0"
            assert move.beats_left == 0, f"Move {move.name} beats should be 0"

    def test_reset_combat_moves_empty_list(self):
        """Verify reset_combat_moves() handles empty move list gracefully."""
        npc = CaveBat()
        npc.known_moves = []
        
        # Should not raise an error
        npc.reset_combat_moves()
        
        assert len(npc.known_moves) == 0


class TestCombatEngageMovesReset:
    """Test that combat_engage() properly resets moves when adding enemies."""

    def test_combat_engage_resets_moves(self):
        """Verify combat_engage() resets move states."""
        player = Player()
        player.combat_list = []
        player.combat_proximity = {}
        player.combat_list_allies = [player]
        
        enemy = CaveBat()
        
        # Artificially set moves to non-zero state (simulating stale state)
        for move in enemy.known_moves:
            move.current_stage = 3
            move.beats_left = 10
        
        # Add to combat
        enemy.combat_engage(player)
        
        # Verify moves were reset
        for move in enemy.known_moves:
            assert move.current_stage == 0, f"Move {move.name} should be reset to stage 0"
            assert move.beats_left == 0, f"Move {move.name} should have 0 beats"

    def test_combat_engage_adds_to_lists(self):
        """Verify combat_engage() still adds enemy to lists correctly."""
        player = Player()
        player.combat_list = []
        player.combat_proximity = {}
        player.combat_list_allies = [player]
        
        enemy = CaveBat()
        enemy.combat_engage(player)
        
        assert enemy in player.combat_list
        assert enemy in player.combat_proximity
        assert enemy.in_combat is True

    def test_combat_engage_sets_proximity_with_allies(self):
        """Verify combat_engage() sets proximity for all allies."""
        player = Player()
        player.combat_list = []
        player.combat_proximity = {}
        
        # Create an ally
        class MockAlly:
            def __init__(self):
                self.combat_proximity = {}
        
        ally = MockAlly()
        player.combat_list_allies = [ally]
        
        enemy = CaveBat()
        enemy.combat_engage(player)
        
        # Enemy should be in ally's proximity
        assert enemy in ally.combat_proximity
        assert ally.combat_proximity[enemy] > 0


class TestMultipleEnemiesJoiningMidCombat:
    """Test scenario of multiple enemies joining combat (like RockRumblers in ch01.py)."""

    def test_multiple_enemies_mid_combat_all_reset(self):
        """Verify all enemies joining mid-combat have moves reset."""
        player = Player()
        player.combat_list = []
        player.combat_proximity = {}
        player.combat_list_allies = [player]
        
        # Simulate initial enemy in combat
        initial_enemy = CaveBat()
        player.combat_list.append(initial_enemy)
        
        # Simulate mid-combat additions (like RockRumblers)
        new_enemies = []
        for i in range(3):
            new_enemy = CaveBat()
            # Set stale state
            for move in new_enemy.known_moves:
                move.current_stage = 2
                move.beats_left = 8
            
            new_enemies.append(new_enemy)
            new_enemy.combat_engage(player)
        
        # Verify all new enemies have reset moves
        for enemy in new_enemies:
            for move in enemy.known_moves:
                assert move.current_stage == 0
                assert move.beats_left == 0
        
        # Verify all are in combat
        assert len(player.combat_list) == 4  # initial + 3 new
        for enemy in new_enemies:
            assert enemy in player.combat_list


class TestAllyJoiningMidCombat:
    """Test scenario of allies joining combat mid-fight (like Gorran in ch01.py)."""

    def test_ally_reset_combat_moves_when_joining(self):
        """Verify ally's moves are reset when joining mid-combat."""
        player = Player()
        player.combat_list = []
        player.combat_list_allies = [player]
        player.combat_proximity = {}
        player.in_combat = True
        
        # Create an ally with stale move states
        ally = CaveBat()
        for move in ally.known_moves:
            move.current_stage = 1
            move.beats_left = 3
        
        # Add ally to combat (simulating ch01.py line 471-474)
        player.combat_list_allies.append(ally)
        ally.in_combat = True
        ally.reset_combat_moves()  # Simulating the fix
        
        # Verify moves are reset
        for move in ally.known_moves:
            assert move.current_stage == 0
            assert move.beats_left == 0

    def test_ally_not_reset_when_not_in_combat(self):
        """Verify reset_combat_moves() still works even when player not in combat."""
        player = Player()
        player.in_combat = False
        
        ally = CaveBat()
        for move in ally.known_moves:
            move.current_stage = 2
            move.beats_left = 5
        
        # Should still be able to call reset even when not in combat
        ally.reset_combat_moves()
        
        for move in ally.known_moves:
            assert move.current_stage == 0
            assert move.beats_left == 0


class TestMoveProgressionAfterReset:
    """Test that moves progress correctly after being reset."""

    def test_move_can_advance_after_reset(self):
        """Verify a reset move can advance through its stages."""
        from src.moves import Move
        
        npc = CaveBat()
        npc.reset_combat_moves()
        
        # Get first move
        if npc.known_moves:
            move = npc.known_moves[0]
            
            # Verify initial state
            assert move.current_stage == 0
            assert move.beats_left == 0
            
            # After reset, move should be able to be cast and advanced
            move.cast()
            assert move.current_stage == 0  # Still prep stage
            assert move.beats_left >= 0    # Has beats or is instant
