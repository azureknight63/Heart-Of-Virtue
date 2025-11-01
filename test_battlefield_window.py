"""Quick test of the enhanced combat battlefield window with terminal output"""

import sys
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition, Direction

def log_status(message, prefix=""):
    """Print formatted status message to terminal"""
    timestamp = time.strftime("%H:%M:%S")
    if prefix:
        print(f"[{timestamp}] {prefix}: {message}")
    else:
        print(f"[{timestamp}] {message}")

log_status("Initializing combat battlefield test...", "TEST")

# Create window
window = CombatBattlefieldWindow("Test Battlefield - Enhanced Features")
window.create_window()
log_status("Combat window created", "WINDOW")

# Add some test combatants with different health levels and facing directions
log_status("Spawning test combatants...", "SETUP")

window.set_combatant(
    "Player", 
    CombatPosition(25, 35, Direction.N), 
    is_alive=True, 
    is_player=True, 
    is_ally=True,
    health_percent=0.95,  # Healthy
    facing_value=0  # Facing North
)
log_status("Player: (25, 35) | Facing: N | Health: 95%", "SPAWN")

window.set_combatant(
    "Ally1", 
    CombatPosition(22, 30, Direction.NE), 
    is_alive=True, 
    is_player=False, 
    is_ally=True,
    health_percent=0.65,  # Injured (! marker)
    facing_value=45  # Facing Northeast
)
log_status("Ally1: (22, 30) | Facing: NE | Health: 65% (injured) - SHOWS !", "SPAWN")

window.set_combatant(
    "Enemy1", 
    CombatPosition(40, 20, Direction.S), 
    is_alive=True, 
    is_player=False, 
    is_ally=False,
    health_percent=0.80,  # Mostly healthy
    facing_value=180  # Facing South
)
log_status("Enemy1: (40, 20) | Facing: S | Health: 80%", "SPAWN")

window.set_combatant(
    "Enemy2", 
    CombatPosition(38, 25, Direction.E), 
    is_alive=False, 
    is_player=False, 
    is_ally=False,
    health_percent=0.0,  # Dead
    facing_value=90
)
log_status("Enemy2: (38, 25) | Facing: E | Health: 0% (DEAD)", "SPAWN")

window.set_combatant(
    "Enemy3",
    CombatPosition(42, 18, Direction.W),
    is_alive=True,
    is_player=False,
    is_ally=False,
    health_percent=0.20,  # Critical (!! marker)
    facing_value=270  # Facing West
)
log_status("Enemy3: (42, 18) | Facing: W | Health: 20% (CRITICAL) - SHOWS !!", "SPAWN")
log_status("Combatant setup complete. 5 units spawned.", "SETUP")

# Simulate some movement by updating positions a few times
log_status("Starting 5-beat movement simulation...", "SIMULATION")
print()

for beat in range(1, 6):
    log_status(f"--- BEAT {beat} ---", "BEAT")
    window.set_beat(beat)
    
    # Move player slightly
    new_pos = CombatPosition(25 + beat, 35, Direction.N)
    window.set_combatant(
        "Player", new_pos,
        is_alive=True, is_player=True, is_ally=True,
        health_percent=max(0.5, 0.95 - beat * 0.05),  # Gradually injure
        facing_value=0
    )
    new_health = int((max(0.5, 0.95 - beat * 0.05)) * 100)
    log_status(f"Player moves to ({25 + beat}, 35) | Health: {new_health}%", "MOVE")
    
    # Move enemy 1
    new_enemy_pos = CombatPosition(40 - beat, 20, Direction.S)
    window.set_combatant(
        "Enemy1", new_enemy_pos,
        is_alive=True, is_player=False, is_ally=False,
        health_percent=0.80, facing_value=180
    )
    log_status(f"Enemy1 moves to ({40 - beat}, 20)", "MOVE")
    
    window.update_display()
    log_status(f"Battlefield rendered", "RENDER")
    
    # Calculate distance between player and enemy1
    player_x, player_y = 25 + beat, 35
    enemy_x, enemy_y = 40 - beat, 20
    distance = int(((player_x - enemy_x) ** 2 + (player_y - enemy_y) ** 2) ** 0.5)
    log_status(f"Distance Player↔Enemy1: {distance} units", "INFO")
    print()
    
    time.sleep(1)

# Keep final frame displayed for 2 more seconds
log_status("Holding final frame for 2 seconds...", "DISPLAY")
time.sleep(2)

log_status("Closing battlefield window...", "CLEANUP")
window.close()

print("\n" + "="*50)
print("Test complete! Features demonstrated:")
print("="*50)
print("✓ Square grid layout (50×50 coordinate space)")
print("✓ Dynamic viewport cropping with 2-square margin")
print("✓ 8-direction compass facing indicators (↑↗→↘↓↙←↖)")
print("✓ Combatant type display (P=Player, A=Ally, E=Enemy)")
print("✓ Color-coded health status (Green/Orange/Red/Gray)")
print("✓ Movement breadcrumb trails showing path history")
print("✓ Real-time position and facing updates")
print("✓ Terminal monitoring output")
print("="*50)
print("- Facing direction indicators (↑↗→↘↓↙←↖)")
print("- Health-based coloring (green=healthy, orange=injured, red=critical, gray=dead)")
print("- Movement breadcrumb trails (·)")
print("- No scrollbars, window expands with content")
