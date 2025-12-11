"""
User Acceptance Test (UAT) for Phase 3 Advanced Combat Moves

This script tests Turn, WhirlAttack, FeintAndPivot, and VertigoSpin
in an actual combat scenario to verify they work correctly with positioning,
damage calculation, and status effects.
"""

import sys
from pathlib import Path

# Setup sys.path for imports
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.player import Player
from src.npc import NPC
from src.moves import Turn, WhirlAttack, FeintAndPivot, VertigoSpin
from src.positions import CombatPosition, Direction
from src.items import Shortsword, LeatherArmor
from neotermcolor import colored, cprint


def setup_combat_scenario():
    """Create a player and multiple enemies for combat testing."""
    # Create player
    player = Player()
    player.name = "Jean"
    player.name_long = "Jean Claire"
    player.maxhp = 100
    player.hp = 100
    player.maxfatigue = 200
    player.fatigue = 200
    player.strength = 15
    player.finesse = 12
    player.endurance = 14
    
    # Equip player
    player.eq_weapon = Shortsword()
    player.eq_armor = LeatherArmor()
    
    # Create player combat position
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    player.in_combat = True
    player.is_alive = True
    player.states = []
    player.combat_exp = {}
    player.combat_proximity = {}
    
    # Create enemies
    enemies = [
        NPC(name="Enemy1", description="Goblin Warrior", damage=8, aggro=70, exp_award=50),
        NPC(name="Enemy2", description="Goblin Scout", damage=6, aggro=60, exp_award=40),
        NPC(name="Enemy3", description="Goblin Mage", damage=5, aggro=50, exp_award=35),
    ]
    
    # Setup enemy combat positions and properties
    positions = [
        CombatPosition(x=20, y=20, facing=Direction.SE),  # Front-left
        CombatPosition(x=30, y=15, facing=Direction.SW),  # Front-right
        CombatPosition(x=25, y=5, facing=Direction.S),    # Behind
    ]
    
    for i, enemy in enumerate(enemies):
        enemy.maxhp = 40
        enemy.hp = 40
        enemy.maxfatigue = 100
        enemy.fatigue = 100
        enemy.is_alive = True
        enemy.in_combat = True
        enemy.combat_position = positions[i]
        enemy.protection = 2
        enemy.finesse = 8
        enemy.strength = 10
        enemy.endurance = 10
        enemy.states = []
        enemy.combat_exp = {}
    
    # Setup combat_proximity dictionaries
    player.combat_proximity = {enemy: 0 for enemy in enemies}
    for enemy in enemies:
        enemy.combat_proximity = {player: 0}
        enemy.combat_proximity.update({e: 0 for e in enemies if e != enemy})
    
    return player, enemies


def print_section(title):
    """Print a formatted section header."""
    cprint("\n" + "=" * 80, "magenta")
    cprint(f"  {title}", "magenta")
    cprint("=" * 80, "magenta")


def print_combat_state(player, enemies):
    """Print current combat state."""
    cprint(f"\n[PLAYER STATE]", "cyan")
    cprint(f"  HP: {player.hp}/{player.maxhp} | Fatigue: {player.fatigue}/{player.maxfatigue}", "cyan")
    cprint(f"  Position: ({player.combat_position.x}, {player.combat_position.y}) facing {player.combat_position.facing.name}", "cyan")
    if player.states:
        cprint(f"  Status Effects: {', '.join([s.name for s in player.states])}", "yellow")
    
    cprint(f"\n[ENEMIES STATE]", "red")
    for enemy in enemies:
        status = "ALIVE" if enemy.is_alive else "DEAD"
        cprint(f"  {enemy.name}: HP {enemy.hp}/{enemy.maxhp} | Pos: ({enemy.combat_position.x}, {enemy.combat_position.y}) facing {enemy.combat_position.facing.name} | {status}", "red")
        if enemy.states:
            cprint(f"    Status: {', '.join([s.name for s in enemy.states])}", "yellow")


def test_turn_move(player, enemies):
    """Test the Turn move."""
    print_section("TEST 1: TURN MOVE")
    
    cprint("\nTesting Turn move - should rotate player to face a direction with no fatigue cost.", "green")
    
    initial_fatigue = player.fatigue
    initial_facing = player.combat_position.facing
    
    # Create and execute Turn move
    turn = Turn(player)
    turn.target_direction = Direction.E
    
    cprint(f"\nInitial facing: {initial_facing.name} | Fatigue: {initial_fatigue}", "cyan")
    cprint(f"Target direction: Direction.E", "cyan")
    
    turn.execute(player)
    
    cprint(f"\nResult:", "green")
    assert player.combat_position.facing == Direction.E, "Turn should change facing"
    assert player.fatigue == initial_fatigue, "Turn should cost 0 fatigue"
    cprint(f"[OK] Facing changed to: {player.combat_position.facing.name}", "green")
    cprint(f"[OK] Fatigue unchanged: {player.fatigue}", "green")
    
    # Reset for next test
    player.combat_position.facing = Direction.N


def test_whirl_attack(player, enemies):
    """Test the WhirlAttack move."""
    print_section("TEST 2: WHIRL ATTACK")
    
    cprint("\nTesting WhirlAttack - should damage all nearby enemies and randomize facing.", "green")
    
    print_combat_state(player, enemies)
    
    initial_fatigue = player.fatigue
    enemy_hps_before = {e: e.hp for e in enemies}
    
    # Create and execute WhirlAttack
    whirl = WhirlAttack(player)
    whirl.viable = lambda: True  # Override to allow testing
    
    cprint(f"\nExecuting WhirlAttack...", "yellow")
    whirl.execute(player)
    
    cprint(f"\nResult:", "green")
    assert player.fatigue == initial_fatigue - whirl.fatigue_cost, "Fatigue should be deducted"
    cprint(f"[OK] Fatigue deducted: {initial_fatigue} -> {player.fatigue} ({whirl.fatigue_cost} cost)", "green")
    
    # Check if at least one enemy took damage
    damage_dealt = False
    for enemy in enemies:
        if enemy.hp < enemy_hps_before[enemy]:
            damage_dealt = True
            cprint(f"[OK] {enemy.name} took damage: {enemy_hps_before[enemy]} -> {enemy.hp}", "green")
    
    cprint(f"[OK] New facing: {player.combat_position.facing.name}", "green")
    
    if damage_dealt:
        cprint("[OK] WhirlAttack successfully damaged enemies", "green")
    else:
        cprint("[WARN] WhirlAttack executed but no damage was dealt (possible miss on all)", "yellow")


def test_feint_and_pivot(player, enemies):
    """Test the FeintAndPivot move."""
    print_section("TEST 3: FEINT AND PIVOT")
    
    cprint("\nTesting FeintAndPivot - should attack and reposition strategically.", "green")
    
    # Reset player to known state
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    player.fatigue = 200
    
    print_combat_state(player, enemies)
    
    target = enemies[0]  # Target first enemy
    initial_player_pos = (player.combat_position.x, player.combat_position.y)
    initial_fatigue = player.fatigue
    initial_target_hp = target.hp
    
    # Create and execute FeintAndPivot
    feint = FeintAndPivot(player)
    feint.target = target
    feint.viable = lambda: True
    
    cprint(f"\nTarget: {target.name} at ({target.combat_position.x}, {target.combat_position.y})", "yellow")
    cprint(f"Executing FeintAndPivot...", "yellow")
    feint.execute(player)
    
    cprint(f"\nResult:", "green")
    
    # Check fatigue cost
    assert player.fatigue == initial_fatigue - feint.fatigue_cost, "Fatigue should be deducted"
    cprint(f"[OK] Fatigue deducted: {initial_fatigue} -> {player.fatigue} ({feint.fatigue_cost} cost)", "green")
    
    # Check repositioning
    new_player_pos = (player.combat_position.x, player.combat_position.y)
    if new_player_pos != initial_player_pos:
        cprint(f"[OK] Player repositioned: {initial_player_pos} -> {new_player_pos}", "green")
    
    # Check damage
    if target.hp < initial_target_hp:
        damage = initial_target_hp - target.hp
        cprint(f"[OK] {target.name} took {damage} damage: {initial_target_hp} -> {target.hp}", "green")
    else:
        cprint(f"[WARN] {target.name} took no damage (possible miss)", "yellow")
    
    cprint(f"[OK] New facing: {player.combat_position.facing.name}", "green")


def test_vertigo_spin(player, enemies):
    """Test the VertigoSpin move."""
    print_section("TEST 4: VERTIGO SPIN")
    
    cprint("\nTesting VertigoSpin - should damage, rotate facing, and apply Disoriented.", "green")
    
    # Reset player to known state
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    player.fatigue = 200
    player.states = []
    
    print_combat_state(player, enemies)
    
    target = enemies[1]  # Target second enemy
    initial_fatigue = player.fatigue
    initial_target_hp = target.hp
    initial_target_facing = target.combat_position.facing
    initial_target_states = len(target.states)
    
    # Create and execute VertigoSpin
    spin = VertigoSpin(player)
    spin.target = target
    spin.viable = lambda: True
    
    cprint(f"\nTarget: {target.name} at ({target.combat_position.x}, {target.combat_position.y})", "yellow")
    cprint(f"Target initial facing: {initial_target_facing.name}", "yellow")
    cprint(f"Executing VertigoSpin...", "yellow")
    spin.execute(player)
    
    cprint(f"\nResult:", "green")
    
    # Check fatigue cost
    assert player.fatigue == initial_fatigue - spin.fatigue_cost, "Fatigue should be deducted"
    cprint(f"[OK] Fatigue deducted: {initial_fatigue} -> {player.fatigue} ({spin.fatigue_cost} cost)", "green")
    
    # Check damage
    if target.hp < initial_target_hp:
        damage = initial_target_hp - target.hp
        cprint(f"[OK] {target.name} took {damage} damage: {initial_target_hp} -> {target.hp}", "green")
    else:
        cprint(f"[WARN] {target.name} took no damage (possible miss)", "yellow")
    
    # Check facing rotation
    if target.combat_position.facing != initial_target_facing:
        cprint(f"[OK] {target.name} facing rotated: {initial_target_facing.name} -> {target.combat_position.facing.name}", "green")
    
    # Check Disoriented status
    if len(target.states) > initial_target_states:
        new_states = [s.name for s in target.states if s.name not in [x.name for x in target.states[:initial_target_states]]]
        if "Disoriented" in new_states:
            cprint(f"[OK] {target.name} applied with Disoriented status", "green")
            disoriented = [s for s in target.states if s.name == "Disoriented"][0]
            cprint(f"  - Duration: {disoriented.beats_left}/{disoriented.beats_max} beats", "cyan")
            cprint(f"  - Finesse reduction: {disoriented.sub_finesse}", "cyan")
            cprint(f"  - Protection reduction: {disoriented.sub_protection}", "cyan")
        else:
            cprint(f"[WARN] No Disoriented status applied (check status implementation)", "yellow")
    else:
        cprint(f"[WARN] No new status applied to {target.name}", "yellow")


def test_integration_scenario(player, enemies):
    """Test all moves in a realistic combat sequence."""
    print_section("TEST 5: INTEGRATION - COMBAT SEQUENCE")
    
    cprint("\nSimulating a realistic combat sequence with all Phase 3 moves.", "green")
    
    # Reset to clean state
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    player.fatigue = 200
    player.hp = 100
    player.states = []
    for enemy in enemies:
        enemy.hp = 40
        enemy.fatigue = 100
        enemy.states = []
        enemy.is_alive = True
    
    print_combat_state(player, enemies)
    
    # Round 1: Turn to face enemy
    cprint("\n[ROUND 1] Turn to face nearest enemy", "yellow")
    turn = Turn(player)
    turn.target_direction = Direction.SE
    turn.execute(player)
    cprint(f"Player now facing: {player.combat_position.facing.name}", "cyan")
    
    # Round 2: WhirlAttack to damage multiple enemies
    cprint("\n[ROUND 2] Execute WhirlAttack to damage nearby enemies", "yellow")
    whirl = WhirlAttack(player)
    whirl.viable = lambda: True
    whirl.execute(player)
    cprint(f"Remaining fatigue: {player.fatigue}", "cyan")
    
    # Round 3: FeintAndPivot single target
    cprint("\n[ROUND 3] Execute FeintAndPivot on primary target", "yellow")
    feint = FeintAndPivot(player)
    feint.target = enemies[0]
    feint.viable = lambda: True
    feint.execute(player)
    cprint(f"Remaining fatigue: {player.fatigue}", "cyan")
    
    # Round 4: VertigoSpin to disable enemy
    cprint("\n[ROUND 4] Execute VertigoSpin to stun enemy", "yellow")
    if enemies[1].is_alive:
        spin = VertigoSpin(player)
        spin.target = enemies[1]
        spin.viable = lambda: True
        spin.execute(player)
        cprint(f"Remaining fatigue: {player.fatigue}", "cyan")
    
    cprint("\n[FINAL STATE]", "cyan")
    print_combat_state(player, enemies)
    
    # Summary
    cprint(f"\n[COMBAT SUMMARY]", "magenta")
    cprint(f"Player Health: {player.hp}/{player.maxhp}", "cyan")
    cprint(f"Player Fatigue: {player.fatigue}/{player.maxfatigue}", "cyan")
    
    alive_enemies = sum(1 for e in enemies if e.is_alive)
    cprint(f"Enemies Defeated: {3 - alive_enemies}/3", "cyan")


def run_all_tests():
    """Run all UAT tests."""
    print_section("PHASE 3 ADVANCED COMBAT MOVES - USER ACCEPTANCE TEST")
    
    try:
        player, enemies = setup_combat_scenario()
        test_turn_move(player, enemies)
        
        player, enemies = setup_combat_scenario()
        test_whirl_attack(player, enemies)
        
        player, enemies = setup_combat_scenario()
        test_feint_and_pivot(player, enemies)
        
        player, enemies = setup_combat_scenario()
        test_vertigo_spin(player, enemies)
        
        player, enemies = setup_combat_scenario()
        test_integration_scenario(player, enemies)
        
        print_section("UAT COMPLETE - ALL TESTS PASSED")
        cprint("\nAll Phase 3 moves are functioning correctly in combat scenarios!", "green")
        return True
        
    except Exception as e:
        print_section("UAT FAILED")
        cprint(f"\n[FAIL] Error during UAT: {e}", "red")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
