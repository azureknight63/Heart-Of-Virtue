"""
Simple test to verify combat adapter initialization
"""
import sys
sys.path.insert(0, 'c:/Users/azure/PycharmProjects/Heart-Of-Virtue')

# Mock the player and NPC
class MockMove:
    def __init__(self, name="Attack"):
        self.name = name
        self.fatigue_cost = 10
        self.current_stage = 0
        self.beats_left = 0
        self.targeted = False
        self.instant = False
        
    def advance(self, user):
        pass

class MockNPC:
    def __init__(self, name="Slime"):
        self.name = name
        self.hp = 20
        self.maxhp = 20
        self.speed = 5
        self.friend = False
        self.known_moves = [MockMove()]
        self.current_move = None
        self.combat_delay = 0
        
    def is_alive(self):
        return self.hp > 0
    
    def cycle_states(self):
        pass
    
    def select_move(self):
        self.current_move = self.known_moves[0]
    
    def die(self):
        pass

class MockPlayer:
    def __init__(self):
        self.name = "Jean"
        self.hp = 100
        self.maxhp = 100
        self.fatigue = 100
        self.maxfatigue = 100
        self.speed = 10
        self.heat = 1.0
        self.known_moves = [MockMove("Check"), MockMove("Wait")]
        self.current_move = None
        self.combat_exp = {"combat": 0}
        self.in_combat = False
        
    def is_alive(self):
        return self.hp > 0
    
    def cycle_states(self):
        pass
    
    def refresh_moves(self):
        return self.known_moves
    
    def gain_exp(self, amount, exp_type="combat"):
        pass

# Test the adapter
try:
    from src.api.combat_adapter import ApiCombatAdapter
    
    print("Creating mock player and enemy...")
    player = MockPlayer()
    enemy = MockNPC("Test Slime")
    
    print("Creating combat adapter...")
    adapter = ApiCombatAdapter(player)
    
    print("Initializing combat...")
    result = adapter.initialize_combat([enemy])
    
    print("\n=== RESULT ===")
    if "error" in result:
        print(f"ERROR: {result['error']}")
        if "details" in result:
            print(f"Details: {result['details']}")
    else:
        print(f"Combat Active: {result.get('combat_active')}")
        print(f"Awaiting Input: {result.get('battle_state', {}).get('awaiting_input')}")
        print(f"Input Type: {result.get('battle_state', {}).get('input_type')}")
        print(f"Available Options: {len(result.get('battle_state', {}).get('available_options', []))}")
        print(f"Log Entries: {len(result.get('log', []))}")
        
        if result.get('log'):
            print("\nCombat Log:")
            for entry in result['log']:
                print(f"  - {entry.get('message')}")
    
    print("\n=== TEST PASSED ===")
    
except Exception as e:
    import traceback
    print(f"\n=== TEST FAILED ===")
    print(f"Error: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
