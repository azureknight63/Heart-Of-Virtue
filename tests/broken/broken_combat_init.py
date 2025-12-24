"""Test combat initialization when moving to a tile with aggressive NPCs"""
import sys
sys.path.insert(0, 'c:/Users/azure/PycharmProjects/Heart-Of-Virtue')

# Mock the universe and player
class MockNPC:
    def __init__(self, name="TestEnemy", aggro=True, awareness=5):
        self.name = name
        self.friend = False
        self.aggro = aggro
        self.awareness = awareness
        self.alert_message = "attacks!"
        self.in_combat = False
        self.hp = 50
        self.maxhp = 50
        self.speed = 5

class MockTile:
    def __init__(self, has_enemy=False):
        self.npcs_here = [MockNPC()] if has_enemy else []
        self.items_here = []
        self.objects_here = []
        self.name = "Test Tile"
        self.description = "A test tile"

class MockUniverse:
    def get_tile(self, x, y):
        # Return a tile with an enemy at (4, 2)
        return MockTile(has_enemy=(x == 4 and y == 2))

class MockPlayer:
    def __init__(self):
        self.finesse = 3  # Low finesse to ensure combat triggers
        self.finesse_base = 3
        self.location_x = 3
        self.location_y = 2
        self.current_room = None
        self.known_moves = []
        self.hp = 100
        self.maxhp = 100
        self.speed = 10
        self.inventory = []

# Test the game service
from src.api.services.game_service import GameService

universe = MockUniverse()
game_service = GameService(universe)
player = MockPlayer()

# Move to a tile with an enemy
print("Moving player from (3,2) to (4,2)...")
result = game_service.move_player(player, "east")

print(f"\nResult: {result.get('success')}")
print(f"Combat started: {result.get('combat_started')}")
print(f"Player in combat: {player.in_combat}")

if result.get('combat_state'):
    print(f"\nCombat state:")
    print(f"  Round: {result['combat_state'].get('round')}")
    print(f"  Turn index: {result['combat_state'].get('current_turn_index')}")
    print(f"  Turn order: {result['combat_state'].get('turn_order')}")
    
if hasattr(player, 'combat_log') and player.combat_log:
    print(f"\nCombat log ({len(player.combat_log)} entries):")
    for entry in player.combat_log:
        print(f"  - {entry.get('message')}")
else:
    print("\nNo combat log found!")
