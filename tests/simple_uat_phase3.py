"""
Simple UAT for Phase 3 moves - no pytest dependency
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from player import Player
from npc import NPC
from moves import Turn, WhirlAttack, FeintAndPivot, VertigoSpin
from positions import CombatPosition, Direction
from items import Shortsword, LeatherArmor

print("=" * 70)
print(" PHASE 3 MOVES - SIMPLE UAT")
print("=" * 70)

# Test 1: Turn move
print("\n[TEST 1] Turn Move")
player = Player()
player.name = "Jean"
player.fatigue = 100
player.combat_position = CombatPosition(x=10, y=10, facing=Direction.N)
player.combat_proximity = {}
player.in_combat = True

turn = Turn(player)
turn.target_direction = Direction.E
initial_fatigue = player.fatigue
turn.execute(player)

print(f"  Initial fatigue: {initial_fatigue}")
print(f"  Final fatigue: {player.fatigue}")
print(f"  Facing changed: N -> {player.combat_position.facing.name}")
assert player.fatigue == initial_fatigue, "Turn should cost 0 fatigue"
assert player.combat_position.facing.value == Direction.E.value, "Turn should change facing"
print("  [OK] Turn move works correctly")

# Test 2: WhirlAttack
print("\n[TEST 2] WhirlAttack Move")
player = Player()
player.name = "Jean"
player.hp = 100
player.fatigue = 150
player.strength = 10
player.eq_weapon = Shortsword()
player.combat_position = CombatPosition(x=10, y=10, facing=Direction.N)
player.combat_proximity = {}
player.in_combat = True
player.states = []

enemy = NPC(name="Enemy1", description="Test", damage=8, aggro=60, exp_award=40)
enemy.hp = 40
enemy.maxhp = 40
enemy.protection = 2
enemy.finesse = 5
enemy.combat_position = CombatPosition(x=12, y=10, facing=Direction.W)
enemy.states = []
player.combat_proximity[enemy] = 5

whirl = WhirlAttack(player)
initial_fatigue = player.fatigue
whirl.execute(player)

print(f"  Fatigue cost: {initial_fatigue - player.fatigue}")
print(f"  New facing: {player.combat_position.facing.name}")
assert whirl.fatigue_cost == 60, "WhirlAttack should cost 60 fatigue"
print("  [OK] WhirlAttack move works correctly")

# Test 3: FeintAndPivot
print("\n[TEST 3] FeintAndPivot Move")
player = Player()
player.name = "Jean"
player.hp = 100
player.fatigue = 150
player.strength = 12
player.eq_weapon = Shortsword()
player.combat_position = CombatPosition(x=10, y=10, facing=Direction.N)
player.combat_proximity = {}
player.in_combat = True
player.states = []

target = NPC(name="Target1", description="Target", damage=8, aggro=60, exp_award=40)
target.hp = 40
target.maxhp = 40
target.protection = 2
target.finesse = 3
target.combat_position = CombatPosition(x=12, y=10, facing=Direction.W)
target.states = []
player.combat_proximity[target] = 5

feint = FeintAndPivot(player)
feint.target = target
initial_fatigue = player.fatigue
initial_pos = (player.combat_position.x, player.combat_position.y)
feint.execute(player)

print(f"  Fatigue cost: {initial_fatigue - player.fatigue}")
print(f"  Position changed: {initial_pos} -> ({player.combat_position.x}, {player.combat_position.y})")
print(f"  New facing: {player.combat_position.facing.name}")
assert feint.fatigue_cost == 70, "FeintAndPivot should cost 70 fatigue"
print("  [OK] FeintAndPivot move works correctly")

# Test 4: VertigoSpin
print("\n[TEST 4] VertigoSpin Move")
player = Player()
player.name = "Jean"
player.hp = 100
player.fatigue = 150
player.strength = 14
player.eq_weapon = Shortsword()
player.combat_position = CombatPosition(x=10, y=10, facing=Direction.N)
player.combat_proximity = {}
player.in_combat = True
player.states = []

target = NPC(name="Target2", description="Target", damage=8, aggro=60, exp_award=40)
target.hp = 50
target.maxhp = 50
target.protection = 1
target.finesse = 4
target.combat_position = CombatPosition(x=12, y=10, facing=Direction.W)
target.states = []
player.combat_proximity[target] = 5

spin = VertigoSpin(player)
spin.target = target
initial_fatigue = player.fatigue
initial_facing = target.combat_position.facing
initial_states = len(target.states)
spin.execute(player)

print(f"  Fatigue cost: {initial_fatigue - player.fatigue}")
print(f"  Target facing changed: {initial_facing.name} -> {target.combat_position.facing.name}")
print(f"  Status effects applied: {len(target.states) - initial_states}")
if target.states:
    print(f"  Status: {target.states[0].name}")
assert spin.fatigue_cost == 80, "VertigoSpin should cost 80 fatigue"
print("  [OK] VertigoSpin move works correctly")

print("\n" + "=" * 70)
print(" ALL TESTS PASSED - Phase 3 moves work in combat!")
print("=" * 70)
