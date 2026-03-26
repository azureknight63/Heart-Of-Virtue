
import sys
import os
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.getcwd())

# We need to mock some modules that might be imported by GameService and cause issues
sys.modules['src.universe'] = MagicMock()
sys.modules['src.player'] = MagicMock()
sys.modules['neotermcolor'] = MagicMock()

# Now import GameService
# We might need to mock serializers if they import heavy stuff
from src.api.services.game_service import GameService

def test_interact_fix():
    print("Setting up test...")

    # Mock Universe and Tile
    mock_universe = MagicMock()
    mock_tile = MagicMock()
    mock_tile.items_here = []
    mock_universe.get_tile.return_value = mock_tile

    # Mock Player
    mock_player = MagicMock()
    mock_player.location_x = 0
    mock_player.location_y = 0
    mock_player.current_room = None # Initially None

    # Mock Item
    mock_item = MagicMock()
    mock_item.name = "Test Item"
    mock_item.keywords = ["take"]

    # Mock the take method to simulate the error condition
    def take_side_effect(player):
        if player.current_room is None:
            raise AttributeError("'NoneType' object has no attribute 'items_here'")
        print("Item taken successfully! player.current_room is set.")

    mock_item.take = MagicMock(side_effect=take_side_effect)

    # Add item to tile
    mock_tile.items_here.append(mock_item)

    # Initialize GameService
    service = GameService(mock_universe)

    # Try to interact
    target_id = str(id(mock_item))

    print(f"Attempting to take item with ID: {target_id}")

    # This call should now set player.current_room = mock_tile before calling mock_item.take(player)
    result = service.interact_with_target(mock_player, target_id, "take")

    print("Result:", result)

    if result["success"]:
        print("SUCCESS: Interaction completed without error.")
    else:
        print(f"FAILURE: {result.get('message')}")
        # Check if it failed with the specific error
        if "NoneType" in str(result.get("message")):
            print("VERIFICATION FAILED: The fix did not prevent the NoneType error.")

if __name__ == "__main__":
    try:
        test_interact_fix()
    except Exception as e:
        print(f"Test script error: {e}")
