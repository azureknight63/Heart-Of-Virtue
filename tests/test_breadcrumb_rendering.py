"""Quick test to verify breadcrumb rendering with direction tracking."""
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

def test_breadcrumb_direction_tracking():
    """Test that breadcrumb directions are tracked correctly."""
    window = CombatBattlefieldWindow()
    
    # Test horizontal movement
    pos1 = MockPosition(10, 10)
    pos2 = MockPosition(15, 10)
    
    window.set_combatant("enemy1", pos1, is_player=False, is_ally=False)
    window.set_combatant("enemy1", pos2, is_player=False, is_ally=False)
    
    # Render grid
    grid_text = window.render_grid()
    print("Breadcrumb test (horizontal movement 10,10 -> 15,10):")
    print(grid_text)
    print("\n")
    
    # Test diagonal movement
    window2 = CombatBattlefieldWindow()
    pos3 = MockPosition(20, 20)
    pos4 = MockPosition(25, 25)
    
    window2.set_combatant("enemy2", pos3, is_player=False, is_ally=False)
    window2.set_combatant("enemy2", pos4, is_player=False, is_ally=False)
    
    grid_text2 = window2.render_grid()
    print("Breadcrumb test (diagonal movement 20,20 -> 25,25):")
    print(grid_text2)
    print("\n")
    
    print("✓ Breadcrumb rendering test completed (no errors)")

if __name__ == "__main__":
    test_breadcrumb_direction_tracking()
