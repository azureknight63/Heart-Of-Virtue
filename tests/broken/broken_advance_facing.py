#!/usr/bin/env python3
"""Quick test to verify Advance move updates facing direction."""

import sys
from pathlib import Path

# Setup path - MUST load conftest-style to match test environment
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Load src modules into sys.modules before importing
import src.positions
import src.npc
import src.player
import src.moves

sys.modules['positions'] = src.positions
sys.modules['npc'] = src.npc
sys.modules['player'] = src.player
sys.modules['moves'] = src.moves

from src.npc import NPC
from src.player import Player
from src import positions
from src.moves import Advance


def test_advance_facing_update():
    """Test that Advance move properly updates facing toward target."""
    print("\n=== Testing Advance Move Facing Update ===\n")

    # Create player and enemy
    player = Player()
    player.name = "Jean"
    enemy = NPC(name="Slime", description="A slimy foe", damage=10, aggro=50, exp_award=25)

    # Initialize combat positions
    # Player at (10, 10) facing North
    player.combat_position = positions.CombatPosition(x=10, y=10, facing=positions.Direction.N)
    # Enemy at (10, 20) - directly North
    enemy.combat_position = positions.CombatPosition(x=10, y=20, facing=positions.Direction.S)

    print(f"Initial state:")
    print(f"  Player pos: ({player.combat_position.x}, {player.combat_position.y})")
    print(f"  Player facing: {player.combat_position.facing.name}")
    print(f"  Enemy pos: ({enemy.combat_position.x}, {enemy.combat_position.y})")
    print(f"  Enemy facing: {enemy.combat_position.facing.name}")

    # Create Advance move
    advance = Advance(player)
    advance.target = enemy

    # Set up proximity for viability
    player.combat_proximity = {enemy: 10}
    enemy.combat_proximity = {player: 10}

    print(f"\nInitial distance: {player.combat_proximity[enemy]} ft")
    print(f"Advance viable: {advance.viable()}")

    # Now rotate player to face East (wrong direction)
    player.combat_position.facing = positions.Direction.E
    print(f"\nBefore Advance:")
    print(f"  Player facing: {player.combat_position.facing.name} (E - WRONG)")
    print(f"  Facing type: {type(player.combat_position.facing)}")
    print(f"  Is Direction: {isinstance(player.combat_position.facing, positions.Direction)}")

    # Execute advance
    print(f"\nExecuting Advance...")
    advance.execute(player)

    # Check result
    print(f"\nAfter Advance:")
    print(f"  Player pos: ({player.combat_position.x}, {player.combat_position.y})")
    print(f"  Player facing: {player.combat_position.facing.name}")
    print(f"  Expected facing: N (toward enemy)")
    print(f"  Distance: {positions.distance_from_coords(player.combat_position, enemy.combat_position)} ft")

    # Verify
    if player.combat_position.facing == positions.Direction.N:
        print("\n✅ PASS: Facing correctly updated to N")
        return True
    else:
        print(f"\n❌ FAIL: Facing is {player.combat_position.facing.name}, expected N")
        return False


def test_advance_diagonal():
    """Test Advance with diagonal movement."""
    print("\n=== Testing Advance with Diagonal Movement ===\n")

    player = Player()
    player.name = "Jean"
    enemy = NPC(name="Goblin", description="A green goblin", damage=12, aggro=60, exp_award=30)

    # Player at (10, 10), enemy at (20, 25) - Northeast
    player.combat_position = positions.CombatPosition(x=10, y=10, facing=positions.Direction.S)
    enemy.combat_position = positions.CombatPosition(x=20, y=25, facing=positions.Direction.NW)

    print(f"Initial state:")
    print(f"  Player pos: ({player.combat_position.x}, {player.combat_position.y})")
    print(f"  Player facing: {player.combat_position.facing.name} (S - WRONG)")
    print(f"  Enemy pos: ({enemy.combat_position.x}, {enemy.combat_position.y})")

    advance = Advance(player)
    advance.target = enemy
    player.combat_proximity = {enemy: 15}
    enemy.combat_proximity = {player: 15}

    print(f"\nExecuting Advance...")
    advance.execute(player)

    print(f"\nAfter Advance:")
    print(f"  Player pos: ({player.combat_position.x}, {player.combat_position.y})")
    print(f"  Player facing: {player.combat_position.facing.name}")
    print(f"  Expected facing: NE (toward enemy)")

    if player.combat_position.facing == positions.Direction.NE:
        print("\n✅ PASS: Facing correctly updated to NE")
        return True
    else:
        print(f"\n❌ FAIL: Facing is {player.combat_position.facing.name}, expected NE")
        return False


if __name__ == "__main__":
    try:
        result1 = test_advance_facing_update()
        result2 = test_advance_diagonal()

        print("\n" + "=" * 50)
        if result1 and result2:
            print("All tests PASSED ✅")
        else:
            print("Some tests FAILED ❌")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
