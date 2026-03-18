
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath("c:/Users/azure/PycharmProjects/Heart-Of-Virtue"))

# Mock flask before importing anything else
sys.modules['flask'] = MagicMock()
sys.modules['flask_cors'] = MagicMock()
sys.modules['flask_socketio'] = MagicMock()

# Now import the adapter
from src.api.combat_adapter import ApiCombatAdapter
from src.player import Player
from src.npc import NPC

class TestCombatCrash(unittest.TestCase):
    def setUp(self):
        # Create a real-ish player
        self.player = Player()
        self.player.name = "Jean"
        self.player.speed = 10
        self.player.fatigue = 100
        self.player.maxfatigue = 100
        self.player.heat = 1.0
        self.player.combat_exp = {"combat": 0}
        self.player.known_moves = []
        self.player.combat_list = []
        self.player.combat_list_allies = [self.player]
        
        # Create a real-ish NPC
        self.enemy = NPC("Slime Alpha")
        self.enemy.speed = 5
        self.enemy.hp = 20
        self.enemy.maxhp = 20
        self.enemy.known_moves = []
        self.enemy.combat_delay = 0
        
        self.adapter = ApiCombatAdapter(self.player)

    def test_crash(self):
        print("\nAttempting to initialize combat...")
        try:
            result = self.adapter.initialize_combat([self.enemy])
            if "error" in result:
                print(f"Caught error in result: {result['error']}")
                if "details" in result:
                    print(f"Details: {result['details']}")
            else:
                print("Success!")
        except Exception as e:
            print(f"CRASHED: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    unittest.main()
