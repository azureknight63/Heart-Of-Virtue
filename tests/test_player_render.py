"""Test to debug missing player on battlefield - detailed version"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition, Direction

def test_player_rendering():
    """Test if player appears on battlefield grid"""
    print("Testing player rendering on battlefield grid...")

    # Create window
    window = CombatBattlefieldWindow("Player Rendering Test")
    try:
        window.create_window()

        # Add ONLY the player, no enemies
        window.set_combatant(
            "Jean",
            CombatPosition(25, 25, Direction.S),
            is_alive=True,
            is_player=True,
            is_ally=True,
            health_percent=0.8,
            facing_value=180
        )

        print(f"\nBefore render:")
        print(f"  Combatants: {window.combatants_data.keys()}")
        print(f"  Movement history: {window.movement_history.keys()}")

        # Get the grid text
        grid_text = window.render_grid()

        print(f"\nViewport: x=[{window.viewport_x_min}, {window.viewport_x_max}], y=[{window.viewport_y_min}, {window.viewport_y_max}]")

        # Count P characters in grid
        p_count = grid_text.count('P')
        print(f"'P' characters in grid: {p_count}")
        assert p_count > 0, "Player 'P' not found in grid!"

        # Print first few lines of grid
        lines = grid_text.split('\n')
        print(f"\nGrid (first 15 lines):")
        for i, line in enumerate(lines[:15]):
            print(f"  {i}: {line}")

        # Look for the P
        found_p = False
        for i, line in enumerate(lines):
            if 'P' in line:
                print(f"\nFound 'P' at line {i}: {line}")
                found_p = True
                break
        assert found_p, "Player 'P' not found in any line!"
    finally:
        window.close()

if __name__ == "__main__":
    # This allows running the file directly if needed, though pytest is preferred
    import pytest
    pytest.main([__file__])
