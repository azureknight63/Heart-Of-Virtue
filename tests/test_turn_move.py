"""Test suite for the Turn move."""
import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.player import Player
from src.moves import Turn
from src.positions import Direction, CombatPosition
from src.npc import NPC


class MockCombatant:
    """Mock combatant for testing."""
    def __init__(self, name, x, y, is_friend=False):
        self.name = name
        self.combat_position = CombatPosition(x=x, y=y, facing=Direction.N)
        self.friend = is_friend
        self.is_alive = True
        self.combat_proximity = {}


def test_turn_is_viable_with_combat_position():
    """Test that Turn is viable when player has combat_position."""
    player = Player()
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    
    turn = Turn(player)
    assert turn.viable() is True


def test_turn_is_not_viable_without_combat_position():
    """Test that Turn is not viable when player lacks combat_position."""
    player = Player()
    # Don't set combat_position
    
    turn = Turn(player)
    assert turn.viable() is False


def test_turn_direction_calculation_north():
    """Test calculating direction to a target due north."""
    player = Player()
    player.name = "Test Player"
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.S)
    
    turn = Turn(player)
    
    # Create a target to the north
    target = MockCombatant("Target", x=25, y=10)
    
    direction = turn._calculate_direction_to_target(target)
    assert direction.value == Direction.N.value


def test_turn_direction_calculation_east():
    """Test calculating direction to a target due east."""
    player = Player()
    player.name = "Test Player"
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    
    turn = Turn(player)
    
    # Create a target to the east
    target = MockCombatant("Target", x=40, y=25)
    
    direction = turn._calculate_direction_to_target(target)
    assert direction.value == Direction.E.value


def test_turn_direction_calculation_southeast():
    """Test calculating direction to a target to the southeast."""
    player = Player()
    player.name = "Test Player"
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    
    turn = Turn(player)
    
    # Create a target to the southeast
    target = MockCombatant("Target", x=35, y=35)
    
    direction = turn._calculate_direction_to_target(target)
    assert direction.value == Direction.SE.value


def test_turn_direction_calculation_same_position():
    """Test that Turn defaults to current facing when target is at same position."""
    player = Player()
    player.name = "Test Player"
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.W)
    
    turn = Turn(player)
    
    # Create a target at same position
    target = MockCombatant("Target", x=25, y=25)
    
    direction = turn._calculate_direction_to_target(target)
    assert direction.value == Direction.W.value  # Should maintain current facing


def test_turn_execute_updates_facing():
    """Test that Turn.execute() updates the player's facing direction."""
    player = Player()
    player.name = "Test Player"
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    player.fatigue = 100
    
    turn = Turn(player)
    turn.target_direction = Direction.S
    
    turn.execute(player)
    
    assert player.combat_position.facing.value == Direction.S.value


def test_turn_execute_without_target_direction():
    """Test that Turn.execute() handles missing target_direction gracefully."""
    player = Player()
    player.name = "Test Player"
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    player.fatigue = 100
    
    turn = Turn(player)
    turn.target_direction = None
    
    turn.execute(player)
    
    # Should not crash and facing should remain unchanged
    assert player.combat_position.facing.value == Direction.N.value


def test_turn_cast_calls_super():
    """Test that Turn.cast() properly initializes the move."""
    player = Player()
    player.name = "Other NPC"  # Not Jean Claire
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    
    turn = Turn(player)
    turn.cast()
    
    # Check that move is initialized
    assert turn.current_stage == 0
    assert turn.beats_left == 0  # prep stage beats


def test_turn_move_fatigue_cost_is_zero():
    """Test that Turn move has no fatigue cost."""
    player = Player()
    turn = Turn(player)
    
    assert turn.fatigue_cost == 0


def test_turn_move_description():
    """Test that Turn move has appropriate description."""
    player = Player()
    turn = Turn(player)
    
    assert turn.name == "Turn"
    assert "direction" in turn.description.lower()
