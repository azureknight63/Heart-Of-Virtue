
import sys
import os
from unittest.mock import patch

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

import universe as universe_module
import player as player_module
from api.services.game_service import GameService

def test_wall_switch_bug():
    # Setup
    uni = universe_module.Universe()
    player = player_module.Player()
    player.universe = uni
    uni.build(player)
    
    # Starting tile is (2, 2) in dark-grotto.json
    # Wall switch is at (3, 2)
    player.location_x = 3
    player.location_y = 2
    tile = uni.get_tile(3, 2)
    player.current_room = tile
    
    service = GameService()
    session_data = {}
    
    print(f"Initial block_exit: {tile.block_exit}")
    
    # 1. Interact with Wall Depression
    # Find the target id
    target = None
    for obj in tile.objects_here:
        if obj.name == "Wall Depression":
            target = obj
            break
            
    if not target:
        print("Error: Wall Depression not found!")
        return
        
    target_id = str(id(target))
    
    print("\nPressing wall switch...")
    result = service.interact_with_target(player, target_id, "press", session_data=session_data)
    
    print(f"Interaction result message: {result['message']}")
    print(f"Events triggered: {[e['name'] for e in result['events_triggered']]}")
    
    # Check block_exit on the tile instance
    print(f"Tile block_exit after interaction: {tile.block_exit}")
    
    # Check block_exit in session_data
    tile_key = "3,2"
    stored_block_exit = session_data.get('tile_modifications', {}).get(tile_key, {}).get('block_exit')
    print(f"Stored block_exit in session: {stored_block_exit}")
    
    if 'east' in stored_block_exit:
        print("\nBUG REPRODUCED: 'east' still in stored block_exit!")
    else:
        print("\nSUCCESS: 'east' removed from stored block_exit.")

if __name__ == "__main__":
    test_wall_switch_bug()
