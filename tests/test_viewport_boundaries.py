"""Test viewport boundaries with padding."""
import sys
from pathlib import Path
from dataclasses import dataclass

# Setup path
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import after path setup
from src.combat_battlefield import CombatBattlefieldWindow

@dataclass
class MockPosition:
    """Mock position object for testing."""
    x: float
    y: float

    def copy(self):
        return MockPosition(self.x, self.y)

def test_left_boundary():
    """Test combatant at left boundary has proper viewport."""
    window = CombatBattlefieldWindow()

    # Place combatant very close to left edge (x=1)
    window.set_combatant("enemy1", MockPosition(1, 25), is_player=False, is_ally=False)

    # Check viewport
    window._update_viewport()
    print(f"Combatant at (1, 25)")
    print(f"Viewport: x=[{window.viewport_x_min}, {window.viewport_x_max}], y=[{window.viewport_y_min}, {window.viewport_y_max}]")
    print(f"Expected x_min: max(0, 1-2) = 0 or less = 0")
    print(f"Expected x_max: min(49, 1+2) = 3")
    print()

    grid = window.render_grid()
    print("Rendered grid:")
    print(grid)
    print()

def test_right_boundary():
    """Test combatant at right boundary has proper viewport."""
    window = CombatBattlefieldWindow()

    # Place combatant near right edge (x=48)
    window.set_combatant("enemy1", MockPosition(48, 25), is_player=False, is_ally=False)

    # Check viewport
    window._update_viewport()
    print(f"Combatant at (48, 25)")
    print(f"Viewport: x=[{window.viewport_x_min}, {window.viewport_x_max}], y=[{window.viewport_y_min}, {window.viewport_y_max}]")
    print(f"Expected x_min: max(0, 48-2) = 46")
    print(f"Expected x_max: min(49, 48+2) = 49")
    print()

if __name__ == "__main__":
    test_left_boundary()
    test_right_boundary()
