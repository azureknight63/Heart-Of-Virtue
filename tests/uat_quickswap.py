"""
UAT Script: QuickSwap Move - Manual Testing
Performs User Acceptance Testing by simulating combat scenarios
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Suppress game output
import io
old_stdout = sys.stdout
sys.stdout = io.StringIO()

try:
    from src.moves import QuickSwap  # type: ignore
    from src.positions import CombatPosition, Direction  # type: ignore
    from src.player import Player  # type: ignore
    from src.npc import NPC  # type: ignore
    from unittest.mock import Mock
    
    sys.stdout = old_stdout
    
    print("\n" + "="*80)
    print("UAT: QuickSwap Move - Manual Testing")
    print("="*80 + "\n")
    
    # Test Scenario 1: Basic Position Swap
    print("SCENARIO 1: Basic Position Swap")
    print("-" * 80)
    
    player = Mock()
    player.name = "Jean"
    player.is_alive.return_value = True
    player.fatigue = 100
    player.combat_list_allies = []
    player.combat_proximity = {}
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    
    ally = Mock()
    ally.name = "Knight"
    ally.is_alive.return_value = True
    ally.combat_position = CombatPosition(x=27, y=25, facing=Direction.E)
    ally.combat_proximity = {}
    
    player.combat_list_allies = [ally]
    
    quickswap = QuickSwap(player)
    
    print(f"Initial State:")
    print(f"  Jean position: ({player.combat_position.x}, {player.combat_position.y}), facing {player.combat_position.facing.name}")
    print(f"  Knight position: ({ally.combat_position.x}, {ally.combat_position.y}), facing {ally.combat_position.facing.name}")
    print(f"  QuickSwap viable: {quickswap.viable()}")
    
    # Execute swap
    quickswap.execute(player)
    
    print(f"\nAfter QuickSwap:")
    print(f"  Jean position: ({player.combat_position.x}, {player.combat_position.y}), facing {player.combat_position.facing.name}")
    print(f"  Knight position: ({ally.combat_position.x}, {ally.combat_position.y}), facing {ally.combat_position.facing.name}")
    print(f"  Fatigue deducted: {100 - player.fatigue} (expected: 10)")
    
    # Verify swap was successful
    assert player.combat_position.x == 27, "Player should be at x=27"
    assert player.combat_position.y == 25, "Player should be at y=25"
    assert ally.combat_position.x == 25, "Ally should be at x=25"
    assert ally.combat_position.y == 25, "Ally should be at y=25"
    assert player.combat_position.facing == Direction.E, "Player should face East"
    assert ally.combat_position.facing == Direction.N, "Ally should face North"
    
    print("\n✅ SCENARIO 1 PASSED: Basic position swap works correctly\n")
    
    # Test Scenario 2: Distance Recalculation
    print("SCENARIO 2: Distance Recalculation with Enemy")
    print("-" * 80)
    
    enemy = Mock()
    enemy.name = "Bandit"
    enemy.combat_position = CombatPosition(x=40, y=25, facing=Direction.W)
    enemy.combat_proximity = {}
    
    # Set initial distances
    player.combat_proximity = {enemy: 15}
    ally.combat_proximity = {enemy: 13}
    enemy.combat_proximity = {player: 15, ally: 13}
    
    # Reset positions for clean test
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    ally.combat_position = CombatPosition(x=27, y=25, facing=Direction.E)
    
    print(f"Before swap:")
    print(f"  Jean to Bandit distance: {player.combat_proximity[enemy]} ft")
    print(f"  Knight to Bandit distance: {ally.combat_proximity[enemy]} ft")
    
    quickswap._execute_coordinate_based(player, ally)
    
    print(f"\nAfter swap (distances recalculated):")
    print(f"  Jean to Bandit distance: {player.combat_proximity[enemy]} ft")
    print(f"  Knight to Bandit distance: {ally.combat_proximity[enemy]} ft")
    
    # Verify recalculation happened
    assert player.combat_proximity[enemy] != 15, "Jean's distance should change"
    print(f"  Distance change for Jean: {15} -> {player.combat_proximity[enemy]}")
    print(f"  Bidirectional sync: Bandit sees Jean at {enemy.combat_proximity.get(player, 'N/A')} ft")
    
    print("\n✅ SCENARIO 2 PASSED: Distance recalculation works correctly\n")
    
    # Test Scenario 3: Range Detection
    print("SCENARIO 3: Out-of-Range Ally Detection")
    print("-" * 80)
    
    # Create fresh mocks for this scenario
    player3 = Mock()
    player3.name = "Jean"
    player3.is_alive.return_value = True
    player3.fatigue = 100
    player3.combat_list_allies = []
    player3.combat_proximity = {}
    player3.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    
    knight3 = Mock()
    knight3.name = "Knight"
    knight3.is_alive.return_value = True
    knight3.combat_position = CombatPosition(x=27, y=25, facing=Direction.E)
    knight3.combat_proximity = {}
    
    distant_ally = Mock()
    distant_ally.name = "Distant Knight"
    distant_ally.is_alive.return_value = True
    distant_ally.combat_position = CombatPosition(x=10, y=10, facing=Direction.S)
    
    player3.combat_list_allies = [knight3, distant_ally]
    
    quickswap2 = QuickSwap(player3)
    nearby = quickswap2._get_nearby_allies()
    
    print(f"Available allies:")
    print(f"  Knight at ({knight3.combat_position.x}, {knight3.combat_position.y})")
    print(f"  Distant Knight at ({distant_ally.combat_position.x}, {distant_ally.combat_position.y})")
    
    print(f"\nDistance calculations:")
    from src.positions import distance_from_coords  # type: ignore
    dist_knight = distance_from_coords(player3.combat_position, knight3.combat_position)
    dist_distant = distance_from_coords(player3.combat_position, distant_ally.combat_position)
    print(f"  Knight distance: {dist_knight} ft (should be in range 1-4)")
    print(f"  Distant Knight distance: {dist_distant} ft (should be out of range)")
    print(f"  QuickSwap mvrange: {quickswap2.mvrange}")
    
    print(f"\nNearby allies (within 1-4 squares):")
    for a in nearby:
        print(f"  - {a.name}")
    
    assert knight3 in nearby, f"Knight should be in range (dist={dist_knight}, range={quickswap2.mvrange})"
    assert distant_ally not in nearby, "Distant Knight should be out of range"
    
    print(f"\n✅ SCENARIO 3 PASSED: Range detection works correctly\n")
    
    # Test Scenario 4: Dead Ally Exclusion
    print("SCENARIO 4: Dead Ally Exclusion")
    print("-" * 80)
    
    # Create fresh mocks for this scenario
    player4 = Mock()
    player4.name = "Jean"
    player4.is_alive.return_value = True
    player4.fatigue = 100
    player4.combat_list_allies = []
    player4.combat_proximity = {}
    player4.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    
    knight4 = Mock()
    knight4.name = "Knight"
    knight4.is_alive.return_value = True
    knight4.combat_position = CombatPosition(x=26, y=26, facing=Direction.E)
    knight4.combat_proximity = {}
    
    dead_ally = Mock()
    dead_ally.name = "Dead Knight"
    dead_ally.is_alive.return_value = False
    dead_ally.combat_position = CombatPosition(x=27, y=27, facing=Direction.NE)
    
    player4.combat_list_allies = [knight4, dead_ally]
    quickswap3 = QuickSwap(player4)
    nearby = quickswap3._get_nearby_allies()
    
    print(f"Allies in combat:")
    print(f"  Knight (alive) at ({knight4.combat_position.x}, {knight4.combat_position.y})")
    print(f"  Dead Knight (dead) at ({dead_ally.combat_position.x}, {dead_ally.combat_position.y})")
    
    print(f"\nSwappable allies:")
    for a in nearby:
        print(f"  - {a.name}")
    
    assert knight4 in nearby, "Living Knight should be available"
    assert dead_ally not in nearby, "Dead Knight should be excluded"
    assert len(nearby) == 1, "Only living allies should be available"
    
    print(f"\n✅ SCENARIO 4 PASSED: Dead allies correctly excluded\n")
    
    # Test Scenario 5: No Viable Swap When Isolated
    print("SCENARIO 5: No Viable Swap When Isolated")
    print("-" * 80)
    
    # Create fresh mock for this scenario
    player5 = Mock()
    player5.name = "Jean"
    player5.is_alive.return_value = True
    player5.fatigue = 100
    player5.combat_list_allies = []
    player5.combat_proximity = {}
    player5.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    
    quickswap4 = QuickSwap(player5)
    
    print(f"Jean combat_list_allies: {len(player5.combat_list_allies)}")
    print(f"QuickSwap viable: {quickswap4.viable()}")
    
    assert not quickswap4.viable(), "QuickSwap should not be viable without allies"
    
    print(f"\n✅ SCENARIO 5 PASSED: QuickSwap correctly unavailable when isolated\n")
    
    # Summary
    print("="*80)
    print("UAT TEST RESULTS")
    print("="*80)
    print(f"\n✅ SCENARIO 1: Basic Position Swap - PASSED")
    print(f"✅ SCENARIO 2: Distance Recalculation - PASSED")
    print(f"✅ SCENARIO 3: Out-of-Range Detection - PASSED")
    print(f"✅ SCENARIO 4: Dead Ally Exclusion - PASSED")
    print(f"✅ SCENARIO 5: Isolated State Handling - PASSED")
    print(f"\n{'='*80}")
    print(f"TOTAL: 5/5 UAT Scenarios PASSED ✅")
    print(f"{'='*80}\n")
    
    print("📋 UAT VERDICT: READY FOR INTEGRATION\n")
    
except Exception as e:
    sys.stdout = old_stdout
    print(f"\n❌ ERROR during UAT: {e}\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)

sys.stdout = old_stdout
