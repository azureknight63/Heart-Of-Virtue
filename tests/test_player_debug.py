"""Test to debug missing player on battlefield"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition, Direction

def test_missing_player():
    """Test if player can be displayed on battlefield"""
    print("Testing player display on battlefield...")

    # Create window
    window = CombatBattlefieldWindow("Player Debug Test")
    try:
        window.create_window()

        # Test 1: Player at various positions
        test_positions = [
            (0, 0, "Top-left corner"),
            (25, 25, "Center"),
            (49, 49, "Bottom-right corner"),
            (10, 10, "Upper-left area"),
        ]

        for x, y, desc in test_positions:
            print(f"\n  Test: {desc} ({x}, {y})")

            # Add player
            window.set_combatant(
                "Jean",
                CombatPosition(x, y, Direction.S),
                is_alive=True,
                is_player=True,
                is_ally=True,
                health_percent=0.8,
                facing_value=180
            )

            # Add 3 enemies around the player
            for i, (ex, ey) in enumerate([(x+5, y), (x-5, y), (x, y+5)]):
                if 0 <= ex < 50 and 0 <= ey < 50:
                    window.set_combatant(
                        f"Enemy{i}",
                        CombatPosition(ex, ey, Direction.N),
                        is_alive=True,
                        is_player=False,
                        is_ally=False,
                        health_percent=0.5 + (i*0.1),
                        facing_value=0
                    )

            # Check viewport and combatants
            print(f"    Viewport: x=[{window.viewport_x_min}, {window.viewport_x_max}], y=[{window.viewport_y_min}, {window.viewport_y_max}]")
            print(f"    Combatants in data: {len(window.combatants_data)}")

            # Update display
            window.update_display()

            # Verify player was added
            assert "Jean" in window.combatants_data, f"Jean NOT found in combatants_data at {desc}!"
            jean_data = window.combatants_data["Jean"]
            assert jean_data['position'].x == x and jean_data['position'].y == y, f"Jean position mismatch at {desc}!"

            # Clear for next test
            window.combatants_data.clear()
            window.movement_history.clear()
    finally:
        window.close()

if __name__ == "__main__":
    # This allows running the file directly if needed, though pytest is preferred
    import pytest
    pytest.main([__file__])
