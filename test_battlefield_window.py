"""Quick test of the enhanced combat battlefield window"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition, Direction

# Create window
window = CombatBattlefieldWindow("Test Battlefield - Enhanced Features")
window.create_window()

# Add some test combatants with different health levels and facing directions
window.set_combatant(
    "Player", 
    CombatPosition(25, 35, Direction.N), 
    is_alive=True, 
    is_player=True, 
    is_ally=True,
    health_percent=0.95,  # Healthy
    facing_value=0  # Facing North
)

window.set_combatant(
    "Ally1", 
    CombatPosition(22, 30, Direction.NE), 
    is_alive=True, 
    is_player=False, 
    is_ally=True,
    health_percent=0.65,  # Injured
    facing_value=45  # Facing Northeast
)

window.set_combatant(
    "Enemy1", 
    CombatPosition(40, 20, Direction.S), 
    is_alive=True, 
    is_player=False, 
    is_ally=False,
    health_percent=0.80,  # Mostly healthy
    facing_value=180  # Facing South
)

window.set_combatant(
    "Enemy2", 
    CombatPosition(38, 25, Direction.E), 
    is_alive=False, 
    is_player=False, 
    is_ally=False,
    health_percent=0.0,  # Dead
    facing_value=90
)

window.set_combatant(
    "Enemy3",
    CombatPosition(42, 18, Direction.W),
    is_alive=True,
    is_player=False,
    is_ally=False,
    health_percent=0.20,  # Critical
    facing_value=270  # Facing West
)

# Simulate some movement by updating positions a few times
import time

for beat in range(1, 6):
    window.set_beat(beat)
    
    # Move player slightly
    new_pos = CombatPosition(25 + beat, 35, Direction.N)
    window.set_combatant(
        "Player", new_pos,
        is_alive=True, is_player=True, is_ally=True,
        health_percent=max(0.5, 0.95 - beat * 0.05),  # Gradually injure
        facing_value=0
    )
    
    # Move enemy 1
    new_enemy_pos = CombatPosition(40 - beat, 20, Direction.S)
    window.set_combatant(
        "Enemy1", new_enemy_pos,
        is_alive=True, is_player=False, is_ally=False,
        health_percent=0.80, facing_value=180
    )
    
    window.update_display()
    time.sleep(1)

# Keep final frame displayed for 2 more seconds
time.sleep(2)
window.close()

print("Test complete! Features demonstrated:")
print("- Square grid layout")
print("- Facing direction indicators (↑↗→↘↓↙←↖)")
print("- Health-based coloring (green=healthy, orange=injured, red=critical, gray=dead)")
print("- Movement breadcrumb trails (·)")
print("- No scrollbars, window expands with content")
