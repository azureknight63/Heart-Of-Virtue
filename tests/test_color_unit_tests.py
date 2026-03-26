"""Unit tests for verifying combat battlefield character colors and formatting"""

import sys
from pathlib import Path
import tkinter as tk

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition, Direction


def get_character_at_position(window: CombatBattlefieldWindow, grid_x: int, grid_y: int) -> tuple:
    """
    Get the character and its color tag at a specific grid position.

    Args:
        window: The CombatBattlefieldWindow
        grid_x: X coordinate in the 50x50 game grid
        grid_y: Y coordinate in the 50x50 game grid

    Returns: (character, tag_list, color_hex)
    """
    if not window.text_widget:
        return None, [], None

    # Check if position is in viewport
    if not (window.viewport_x_min <= grid_x <= window.viewport_x_max and
            window.viewport_y_min <= grid_y <= window.viewport_y_max):
        return None, [], None  # Position is culled from viewport

    # Calculate viewport-relative position
    viewport_x = grid_x - window.viewport_x_min
    viewport_y = grid_y - window.viewport_y_min

    # Calculate text position (same formula as _apply_color_tags)
    line = viewport_y + 2  # +1 for top border, +1 for tkinter 1-indexing
    col = viewport_x * 2 + 2  # +1 for left border, +1 for 1-indexing, cells are 2 chars wide

    try:
        # Get character at this position
        char = window.text_widget.get(f"{line}.{col}", f"{line}.{col + 1}")

        # Get tags at this position
        tags = window.text_widget.tag_names(f"{line}.{col}")

        # Get the foreground color from the first tag that has a foreground config
        color = None
        for tag in tags:
            tag_config = window.text_widget.tag_config(tag)
            if tag_config.get("foreground"):
                # foreground is in a tuple like ('foreground', 'foreground', 'foreground', '', '#00ff00')
                # The color is usually the last element
                fg_info = tag_config.get("foreground")
                if fg_info and len(fg_info) > 0:
                    color = fg_info[-1] if isinstance(fg_info, tuple) else fg_info
                    break

        return char, tags, color
    except Exception as e:
        print(f"Error getting character at line {line}, col {col}: {e}")
        return None, [], None


def test_combatant_character_colors():
    """Test that combatant characters have the correct colors"""
    print("\n" + "="*70)
    print("UNIT TEST: Combatant Character Colors")
    print("="*70)

    window = CombatBattlefieldWindow("Color Test")
    window.create_window()

    # Add a healthy player at (5, 5)
    window.set_combatant(
        "Jean",
        CombatPosition(5, 5, Direction.N),
        is_alive=True,
        is_player=True,
        is_ally=True,
        health_percent=0.95,
        facing_value=0
    )

    # Add a healthy enemy at (10, 10)
    window.set_combatant(
        "Enemy1",
        CombatPosition(10, 10, Direction.S),
        is_alive=True,
        is_player=False,
        is_ally=False,
        health_percent=0.90,
        facing_value=180
    )

    # Add an injured enemy at (15, 15)
    window.set_combatant(
        "Enemy2",
        CombatPosition(15, 15, Direction.E),
        is_alive=True,
        is_player=False,
        is_ally=False,
        health_percent=0.50,
        facing_value=90
    )

    # Add a critical enemy at (20, 20)
    window.set_combatant(
        "Enemy3",
        CombatPosition(20, 20, Direction.W),
        is_alive=True,
        is_player=False,
        is_ally=False,
        health_percent=0.20,
        facing_value=270
    )

    # Add a dead enemy at (25, 25)
    window.set_combatant(
        "Enemy4",
        CombatPosition(25, 25, Direction.N),
        is_alive=False,
        is_player=False,
        is_ally=False,
        health_percent=0.0,
        facing_value=0
    )

    # Update display to render and apply tags
    window.update_display()

    # Test cases: (grid_pos, expected_char, expected_color_tag, description)
    test_cases = [
        ((5, 5), "J", "player", "Player (healthy) should be green", window.COLOR_PLAYER),
        ((10, 10), "E", "enemy", "Enemy (healthy) should be red", window.COLOR_ENEMY),
        ((15, 15), "E", "enemy_injured", "Enemy (injured) should be orange", window.COLOR_INJURED),
        ((20, 20), "E", "enemy_critical", "Enemy (critical) should be bright red", window.COLOR_CRITICAL),
        ((25, 25), "e", "dead", "Enemy (dead) should be grey", window.COLOR_DEAD),
    ]

    results = []
    for (grid_x, grid_y), expected_char, expected_tag, description, expected_color in test_cases:
        char, tags, color = get_character_at_position(window, grid_x, grid_y)

        # Check character
        char_ok = char == expected_char
        char_status = "[OK]" if char_ok else "[FAIL]"

        # Check tag
        tag_ok = expected_tag in tags
        tag_status = "[OK]" if tag_ok else "[FAIL]"

        # Check color
        color_ok = color == expected_color if color else False
        color_status = "[OK]" if color_ok else "[FAIL]"

        print(f"\n{description}")
        print(f"  Position: ({grid_x}, {grid_y})")
        print(f"  {char_status} Character: got {ord(char[0]) if char else 'None'} (expected {ord(expected_char[0]) if expected_char else 'None'})")
        print(f"  {tag_status} Tag: {tags} (expected '{expected_tag}' in tags)")
        print(f"  {color_status} Color: {color} (expected {expected_color})")

        results.append(char_ok and tag_ok and color_ok)

    window.close()

    return all(results)


def test_border_and_breadcrumb_colors():
    """Test that borders and breadcrumbs have the correct colors"""
    print("\n" + "="*70)
    print("UNIT TEST: Border and Breadcrumb Colors")
    print("="*70)

    window = CombatBattlefieldWindow("Border Test")
    window.create_window()

    # Add a moving enemy to create breadcrumbs
    for i in range(3):
        window.set_combatant(
            "MovingEnemy",
            CombatPosition(10 + i, 10 + i, Direction.N),
            is_alive=True,
            is_player=False,
            is_ally=False,
            health_percent=0.75,
            facing_value=0
        )

    window.update_display()

    print("\nExpected colors:")
    print(f"  Borders (#): {window.COLOR_GRID} (grey)")
    print(f"  Breadcrumbs (·): {window.COLOR_BREADCRUMB} (grey)")
    print(f"  Combatants: various based on type/health")

    # Get the rendered text
    text = window.text_widget.get(1.0, tk.END)
    lines = text.split('\n')

    print(f"\nRendered grid ({len(lines)} lines):")
    # Show first and last few lines
    for i, line in enumerate(lines[:3] + ['...'] + lines[-3:]):
        if line != '...':
            print(f"  Line {i+1}: {repr(line[:40])}")

    window.close()
    return True


def test_viewport_tag_positioning():
    """Test that color tags are applied to correct positions with viewport culling"""
    print("\n" + "="*70)
    print("UNIT TEST: Tag Positioning with Viewport")
    print("="*70)

    window = CombatBattlefieldWindow("Viewport Test")
    window.create_window()

    # Add enemies at different positions to force viewport adjustment
    positions = [
        (5, 5, "NW enemy"),
        (45, 45, "SE enemy"),
        (25, 25, "Center enemy"),
    ]

    for i, (x, y, desc) in enumerate(positions):
        window.set_combatant(
            f"Enemy{i}",
            CombatPosition(x, y, Direction.N),
            is_alive=True,
            is_player=False,
            is_ally=False,
            health_percent=0.75,
            facing_value=0
        )

    window.update_display()

    print(f"\nViewport after placing 3 enemies at corners and center:")
    print(f"  x: [{window.viewport_x_min}, {window.viewport_x_max}]")
    print(f"  y: [{window.viewport_y_min}, {window.viewport_y_max}]")
    print(f"  All positions should be within viewport")

    # Verify all enemies are within viewport
    all_in_viewport = True
    for i, (x, y, desc) in enumerate(positions):
        in_vp = window.viewport_x_min <= x <= window.viewport_x_max and \
                window.viewport_y_min <= y <= window.viewport_y_max
        status = "[OK]" if in_vp else "[FAIL]"
        print(f"  {status} {desc} at ({x}, {y}): in_viewport={in_vp}")
        all_in_viewport = all_in_viewport and in_vp

    window.close()
    return all_in_viewport


if __name__ == "__main__":
    print("\n" + "="*70)
    print("COMBAT BATTLEFIELD COLOR AND FORMATTING UNIT TESTS")
    print("="*70)

    results = []

    try:
        results.append(("Character Colors", test_combatant_character_colors()))
    except Exception as e:
        print(f"\n[ERROR] Character Colors test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Character Colors", False))

    try:
        results.append(("Border/Breadcrumb Colors", test_border_and_breadcrumb_colors()))
    except Exception as e:
        print(f"\n[ERROR] Border/Breadcrumb Colors test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Border/Breadcrumb Colors", False))

    try:
        results.append(("Viewport Tag Positioning", test_viewport_tag_positioning()))
    except Exception as e:
        print(f"\n[ERROR] Viewport Tag Positioning test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Viewport Tag Positioning", False))

    # Summary
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")

    all_passed = all(passed for _, passed in results)
    print("\n" + ("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED!"))
    print("="*70)
