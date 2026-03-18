"""
Test to reproduce the issue where newly added enemies in combat don't progress their moves.
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from unittest.mock import MagicMock
sys.modules['flask'] = MagicMock()
sys.modules['flask_cors'] = MagicMock()
sys.modules['flask_socketio'] = MagicMock()

try:
    from src.npc import NPC
    from src.player import Player
    import src.moves as moves
    
    print("=" * 70)
    print("TESTING: Moves don't progress when enemy joins combat mid-fight")
    print("=" * 70)
    
    # Create a player
    player = Player()
    player.in_combat = True
    player.combat_list = []
    player.combat_list_allies = [player]
    player.combat_proximity = {}
    
    # Create an enemy OUTSIDE of combat
    enemy = NPC("TestEnemy", "A test enemy", 10, True, 10, speed=10)
    
    # Check initial move state (should NOT be reset since combat_engage wasn't called yet)
    print("\n1. Enemy BEFORE combat_engage() - move state:")
    if enemy.known_moves:
        first_move = enemy.known_moves[0]
        print(f"   first_move.current_stage = {first_move.current_stage}")
        print(f"   first_move.beats_left = {first_move.beats_left}")
    
    # Now add the enemy to combat mid-fight using combat_engage
    print("\n2. Calling combat_engage() to add enemy mid-combat...")
    enemy.combat_engage(player)
    print(f"   Enemy added to combat_list")
    print(f"   Number of enemies in combat: {len(player.combat_list)}")
    
    # Check move state after combat_engage
    print("\n3. Enemy AFTER combat_engage() - move state:")
    if enemy.known_moves:
        first_move = enemy.known_moves[0]
        print(f"   first_move.current_stage = {first_move.current_stage}")
        print(f"   first_move.beats_left = {first_move.beats_left}")
        
        # Verify the fix
        if first_move.current_stage == 0 and first_move.beats_left == 0:
            print(f"\n   ✅ SUCCESS: Moves are now properly reset!")
            print(f"   Moves will progress correctly when the enemy takes their turn.")
        else:
            print(f"\n   ❌ ISSUE: Moves should have been reset to stage 0, beats_left = 0!")
            print(f"   But they still have old values from before combat_engage() was called.")
    
    # Show what SHOULD happen
    print("\n4. What SHOULD happen (showing reset logic from combat.py lines 211-216):")
    print("   for move in enemy.known_moves:")
    print("       move.current_stage = 0")
    print("       move.beats_left = 0")
    
    print("\n" + "=" * 70)
    print("CONCLUSION: combat_engage() must reset move states!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
