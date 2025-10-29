"""Test to verify that NPCs don't advance when already within striking distance of their target."""
import pytest
import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules (e.g., `import genericng`) resolve.
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.npc import NPC  # type: ignore
from src.moves import Advance  # type: ignore


def test_advance_viable_current_target_at_distance():
    """Advance should be viable if current target is at distance > 1"""
    attacker = NPC(name="Attacker", description="Test NPC", damage=10, aggro=50, exp_award=10)
    target = NPC(name="Target", description="Test NPC", damage=10, aggro=50, exp_award=10)
    
    advance = Advance(attacker)
    advance.target = target
    
    # Set distance to target as > 1 (out of striking range)
    attacker.combat_proximity[target] = 5
    target.combat_proximity[attacker] = 5
    
    assert advance.viable() is True, "Advance should be viable when target is out of striking distance"


def test_advance_not_viable_current_target_in_striking_distance():
    """Advance should NOT be viable if current target is already at distance <= 1 (striking distance)"""
    attacker = NPC(name="Attacker", description="Test NPC", damage=10, aggro=50, exp_award=10)
    target = NPC(name="Target", description="Test NPC", damage=10, aggro=50, exp_award=10)
    
    advance = Advance(attacker)
    advance.target = target
    
    # Set distance to target as 1 (at striking distance)
    attacker.combat_proximity[target] = 1
    target.combat_proximity[attacker] = 1
    
    assert advance.viable() is False, "Advance should NOT be viable when target is already at striking distance"


def test_advance_not_viable_current_target_at_zero_distance():
    """Advance should NOT be viable if current target is at distance 0"""
    attacker = NPC(name="Attacker", description="Test NPC", damage=10, aggro=50, exp_award=10)
    target = NPC(name="Target", description="Test NPC", damage=10, aggro=50, exp_award=10)
    
    advance = Advance(attacker)
    advance.target = target
    
    # Set distance to target as 0 (adjacent/melee range)
    attacker.combat_proximity[target] = 0
    target.combat_proximity[attacker] = 0
    
    assert advance.viable() is False, "Advance should NOT be viable when target is at melee range"


def test_advance_with_multiple_enemies_but_target_close():
    """
    Advance should NOT be viable if current target is at striking distance,
    even if there are other enemies further away.
    """
    attacker = NPC(name="Attacker", description="Test NPC", damage=10, aggro=50, exp_award=10)
    target1 = NPC(name="Target1", description="Test NPC", damage=10, aggro=50, exp_award=10)
    target2 = NPC(name="Target2", description="Test NPC", damage=10, aggro=50, exp_award=10)
    
    advance = Advance(attacker)
    advance.target = target1  # Current target is target1
    
    # Current target is at striking distance
    attacker.combat_proximity[target1] = 1
    target1.combat_proximity[attacker] = 1
    
    # But there's another enemy far away
    attacker.combat_proximity[target2] = 10
    target2.combat_proximity[attacker] = 10
    
    # Advance should NOT be viable because current target is already within striking distance
    assert advance.viable() is False, \
        "Advance should NOT be viable when current target is at striking distance, even if other enemies are far away"


def test_advance_no_valid_targets():
    """Advance should NOT be viable if there are no targets"""
    attacker = NPC(name="Attacker", description="Test NPC", damage=10, aggro=50, exp_award=10)
    
    advance = Advance(attacker)
    advance.target = None
    
    # No combat proximity entries
    attacker.combat_proximity = {}
    
    assert advance.viable() is False, "Advance should NOT be viable if there are no targets"
