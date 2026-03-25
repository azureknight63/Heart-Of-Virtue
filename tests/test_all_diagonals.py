"""Test all diagonal directions for breadcrumb rendering."""
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

def test_all_diagonals():
    """Test all 4 diagonal directions."""

    # SE: down-right (dx=1, dy=1) - uses backslash
    print("SE Diagonal (down-right, uses \\):")
    window1 = CombatBattlefieldWindow()
    window1.set_combatant("e1", MockPosition(10, 10), is_player=False, is_ally=False)
    window1.set_combatant("e1", MockPosition(15, 15), is_player=False, is_ally=False)
    print(window1.render_grid())
    print()

    # NW: up-left (dx=-1, dy=-1) - uses backslash
    print("NW Diagonal (up-left, uses \\):")
    window2 = CombatBattlefieldWindow()
    window2.set_combatant("e2", MockPosition(30, 30), is_player=False, is_ally=False)
    window2.set_combatant("e2", MockPosition(25, 25), is_player=False, is_ally=False)
    print(window2.render_grid())
    print()

    # SW: down-left (dx=-1, dy=1) - uses forward slash
    print("SW Diagonal (down-left, uses /):")
    window3 = CombatBattlefieldWindow()
    window3.set_combatant("e3", MockPosition(30, 10), is_player=False, is_ally=False)
    window3.set_combatant("e3", MockPosition(25, 15), is_player=False, is_ally=False)
    print(window3.render_grid())
    print()

    # NE: up-right (dx=1, dy=-1) - uses forward slash
    print("NE Diagonal (up-right, uses /):")
    window4 = CombatBattlefieldWindow()
    window4.set_combatant("e4", MockPosition(10, 30), is_player=False, is_ally=False)
    window4.set_combatant("e4", MockPosition(15, 25), is_player=False, is_ally=False)
    print(window4.render_grid())
    print()

    print("✓ All diagonal directions tested!")

if __name__ == "__main__":
    test_all_diagonals()
