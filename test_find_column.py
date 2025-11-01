"""Test finding correct column for combatant character"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition, Direction
import tkinter as tk

window = CombatBattlefieldWindow("Debug Test")
window.create_window()

# Add player at (5, 5)
window.set_combatant(
    "Jean",
    CombatPosition(5, 5, Direction.N),
    is_alive=True,
    is_player=True,
    health_percent=0.95,
    facing_value=0
)

window.update_display()

# Get the full text
text_content = window.text_widget.get(1.0, tk.END)
print("Raw text content (with visible spaces):")
for i, line in enumerate(text_content.split('\n')[:5], 1):
    print(f"  Line {i}: {repr(line)}")

print("\nSearching for 'J' in widget:")
result = window.text_widget.search('J', '1.0')
print(f"  Found at: {result}")

print("\nGetting characters from that line:")
if result:
    line_num = result.split('.')[0]
    # Get 15 characters starting from pos 1
    for i in range(1, 16):
        char = window.text_widget.get(f'{line_num}.{i}', f'{line_num}.{i+1}')
        if char:
            print(f"  Col {i}: {repr(char)}")
        else:
            break

print("\nTesting tag retrieval at J position:")
if result:
    tags = window.text_widget.tag_names(result)
    print(f"  Tags at {result}: {tags}")

window.close()
