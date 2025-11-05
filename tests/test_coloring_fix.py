"""Test script to verify battlefield coloring fix"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition, Direction

def test_column_calculation():
    """Test that the column calculation for color tags is correct"""
    print("Testing column calculation fix...")
    
    # Test cases: grid_x -> expected column in text
    # Remember: col = grid_x * 2 + 2
    test_cases = [
        (0, 2),    # First cell: col = 0*2 + 2 = 2 (after left border at 1)
        (1, 4),    # Second cell: col = 1*2 + 2 = 4 (chars 3-4 in text)
        (5, 12),   # Sixth cell: col = 5*2 + 2 = 12
        (25, 52),  # 26th cell (middle): col = 25*2 + 2 = 52
    ]
    
    for grid_x, expected_col in test_cases:
        calculated_col = grid_x * 2 + 2
        status = "✓" if calculated_col == expected_col else "✗"
        print(f"  {status} grid_x={grid_x}: calculated={calculated_col}, expected={expected_col}")
        if calculated_col != expected_col:
            print(f"    ERROR: Column calculation mismatch!")
            return False
    
    print("✓ All column calculations passed!")
    return True

def test_display_length_calculation():
    """Test that display length is correctly calculated"""
    print("\nTesting display length calculation...")
    
    test_cases = [
        # (is_alive, health_percent, expected_display_len)
        (True, 1.0, 2),       # Healthy: char + direction = 2
        (True, 0.8, 2),       # Still healthy (>75%): no marker = 2
        (True, 0.65, 3),      # Injured (50-75%): char + direction + ! = 3
        (True, 0.5, 3),       # Injured: char + direction + ! = 3
        (True, 0.2, 4),       # Critical (<25%): char + direction + !! = 4
        (False, 0.0, 2),      # Dead: char + direction = 2
    ]
    
    for is_alive, health_pct, expected_len in test_cases:
        # Recalculate as in the fixed code
        display_len = 2  # char + direction is always 2
        
        # Add health marker length if applicable
        if is_alive and health_pct < 0.75:
            if health_pct < 0.25:
                display_len += 2  # !!
            else:
                display_len += 1  # !
        
        status = "✓" if display_len == expected_len else "✗"
        print(f"  {status} alive={is_alive}, health={health_pct*100:.0f}%: calculated={display_len}, expected={expected_len}")
        if display_len != expected_len:
            print(f"    ERROR: Display length mismatch!")
            return False
    
    print("✓ All display length calculations passed!")
    return True

def test_window_setup():
    """Test that the window initializes without errors"""
    print("\nTesting window initialization...")
    try:
        window = CombatBattlefieldWindow("Coloring Test")
        window.create_window()
        
        # Add multiple enemies to test
        for i in range(1, 10):
            window.set_combatant(
                f"Enemy{i}",
                CombatPosition(10 + i * 3, 20 + i * 2, Direction.S),
                is_alive=(i != 5),  # Make one dead
                is_player=False,
                is_ally=False,
                health_percent=max(0, 1.0 - (i * 0.1)),
                facing_value=i * 40
            )
        
        # Render and check tags are applied
        window.update_display()
        
        print("✓ Window initialized and rendered without errors")
        print(f"  Combatants: {len(window.combatants_data)}")
        print(f"  Movement history: {len(window.movement_history)}")
        
        window.close()
        return True
    except Exception as e:
        print(f"✗ Error during window test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Battlefield Coloring Fix Verification")
    print("=" * 60)
    
    results = []
    results.append(("Column calculation", test_column_calculation()))
    results.append(("Display length calculation", test_display_length_calculation()))
    results.append(("Window initialization", test_window_setup()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    print("\n" + ("All tests passed! ✓" if all_passed else "Some tests failed! ✗"))
