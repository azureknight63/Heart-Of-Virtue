"""Debug test to see what's actually being rendered"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition, Direction

window = CombatBattlefieldWindow("Debug Test")
window.create_window()

# Add one simple player
print("Setting player at (5, 5)...")
window.set_combatant(
    "Jean",
    CombatPosition(5, 5, Direction.N),
    is_alive=True,
    is_player=True,
    is_ally=True,
    health_percent=0.95,
    facing_value=0
)

print(f"\nCombatants data: {window.combatants_data}")
print(f"\nCombatant Jean data:")
jean_data = window.combatants_data.get("Jean", {})
for key, val in jean_data.items():
    print(f"  {key}: {val}")

print("\nCalling update_display()...")
window.update_display()

print(f"\nViewport: x=[{window.viewport_x_min}, {window.viewport_x_max}], y=[{window.viewport_y_min}, {window.viewport_y_max}]")

# Get the rendered grid text
import tkinter as tk
grid_text = window.text_widget.get(1.0, tk.END)
print(f"\nGrid text ({len(grid_text)} chars):")
lines = grid_text.split('\n')
print(f"Total lines: {len(lines)}")

# Show first 10 lines with character codes
for i, line in enumerate(lines[:10]):
    print(f"Line {i}: {repr(line)}")
    if 'J' in line or 'E' in line:
        print(f"  Characters: {[f'{c}({ord(c)})' for c in line]}")

# Look for J character
for i, line in enumerate(lines):
    if 'J' in line:
        print(f"\nFound 'J' in line {i}: {repr(line)}")
        print(f"  Position in line: {line.index('J')}")

window.close()
