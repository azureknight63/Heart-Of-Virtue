
import sys
import os
import random

# Add project root and src to path
root_path = os.path.abspath(".")
sys.path.append(root_path)
sys.path.append(os.path.join(root_path, "src"))

# Mock flask and other things
from unittest.mock import MagicMock
sys.modules['flask'] = MagicMock()
sys.modules['flask_cors'] = MagicMock()
sys.modules['flask_socketio'] = MagicMock()

try:
    from src.api.combat_adapter import ApiCombatAdapter
    from src.player import Player
    from src.npc import NPC
    import src.moves as moves

    # Create a real player
    player = Player()
    
    # Create an NPC 
    enemy = NPC("Slime", "A slimy slime", 10, True, 10, speed=20)
    
    # Create a move with a BAD user string
    print("Creating move with string 'NPC_NAME' as user...")
    bad_move = moves.NpcAttack(enemy)
    bad_move.user = "NPC_NAME" # Force string user
    enemy.known_moves = [bad_move]
    
    # Set combat_list
    player.combat_list = [enemy]
    player.combat_list_allies = [player]
    
    adapter = ApiCombatAdapter(player)
    
    print("Starting combat initialization (this should trigger _process_npc)...")
    adapter.initialize_combat([enemy])
    
    print("\nVerifying bad_move.user...")
    print(f"bad_move.user type: {type(bad_move.user)}")
    if not isinstance(bad_move.user, str):
        print("SUCCESS: bad_move.user was successfully updated to an object during advance()!")
    else:
        print("FAILURE: bad_move.user is still a string.")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
