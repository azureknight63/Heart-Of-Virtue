"""Integration test: verify NPCs don't advance repeatedly when already at striking distance."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.npc import NPC
from src.moves import Advance


def test_advance_move_integration():
    """
    Simulate NPC combat scenario: 
    - NPC starts far from target
    - Should be able to advance (viable=True)
    - Once within striking distance (distance <= 1)
    - Should NOT be able to advance anymore (viable=False)
    """
    npc = NPC(name="Enemy", description="Test Enemy", damage=20, aggro=80, exp_award=50)
    player = NPC(name="Player", description="Test Player", damage=15, aggro=50, exp_award=0, friend=True)
    
    # NPC knows how to advance
    advance_move = Advance(npc)
    advance_move.target = player
    
    # Step 1: Initial distance is far (15 ft)
    npc.combat_proximity[player] = 15
    player.combat_proximity[npc] = 15
    
    print(f"Initial distance: {npc.combat_proximity[player]} ft")
    assert advance_move.viable() is True, "Should be able to advance from 15 ft"
    
    # Step 2: Advance move executes and gets closer
    # Simulate the advance move's execute() reducing distance
    distance_gained = 8
    npc.combat_proximity[player] -= distance_gained
    player.combat_proximity[npc] = npc.combat_proximity[player]
    
    print(f"After advance: {npc.combat_proximity[player]} ft")
    assert advance_move.viable() is True, "Should be able to advance from 7 ft"
    
    # Step 3: Advance again and get even closer
    distance_gained = 5
    npc.combat_proximity[player] -= distance_gained
    player.combat_proximity[npc] = npc.combat_proximity[player]
    
    print(f"After second advance: {npc.combat_proximity[player]} ft")
    assert advance_move.viable() is True, "Should be able to advance from 2 ft"
    
    # Step 4: One more advance gets to striking distance
    distance_gained = 1
    npc.combat_proximity[player] -= distance_gained
    player.combat_proximity[npc] = npc.combat_proximity[player]
    
    print(f"After third advance: {npc.combat_proximity[player]} ft (striking distance)")
    assert advance_move.viable() is False, "Should NOT be able to advance when already at striking distance (1 ft)"
    
    print("✓ NPC correctly stops advancing when within striking distance")


if __name__ == "__main__":
    test_advance_move_integration()
