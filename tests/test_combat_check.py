import sys
sys.path.insert(0, 'c:/Users/azure/PycharmProjects/Heart-Of-Virtue')

from src.functions import check_for_combat

# Create a mock player with a room containing an aggressive NPC
class MockNPC:
    def __init__(self):
        self.friend = False
        self.aggro = True
        self.awareness = 10
        self.name = "TestEnemy"
        self.alert_message = "attacks!"
        self.in_combat = False

class MockRoom:
    def __init__(self):
        self.npcs_here = [MockNPC()]

class MockPlayer:
    def __init__(self):
        self.finesse = 5
        self.current_room = MockRoom()
        self.known_moves = []

player = MockPlayer()
result = check_for_combat(player)
print(f"Result: {result}")
print(f"Length: {len(result) if result else 0}")
print(f"Result type: {type(result)}")
if result:
    for enemy in result:
        print(f"  - {enemy.name}")
