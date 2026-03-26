#!/usr/bin/env python3
"""Simple verification that battlefield colors are working."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import tkinter as tk
from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition


def verify_colors_working():
    """Verify that all color tags are correctly applied to combatants."""
    window = CombatBattlefieldWindow("Verification")
    window.create_window()

    # Add test combatants
    combatants = [
        ("Player", 10, 10, True, False, 1.0, 0, "player"),
        ("Ally1", 12, 10, True, True, 0.5, 90, "ally_injured"),
        ("Enemy1", 8, 10, True, False, 0.2, 180, "enemy_critical"),
        ("DeadEnemy", 6, 10, False, False, 0.0, 270, "dead"),
    ]

    for name, x, y, is_alive, is_ally, health, facing, expected_tag in combatants:
        is_player = (name == "Player")
        window.set_combatant(
            name=name,
            position=CombatPosition(x=x, y=y),
            is_alive=is_alive,
            is_ally=is_ally,
            is_player=is_player,
            health_percent=health,
            facing_value=facing,
        )

    window.update_display()

    print("=" * 60)
    print("BATTLEFIELD COLOR VERIFICATION")
    print("=" * 60)

    # Verify each combatant has correct tag
    results = []
    for name, x, y, is_alive, is_ally, health, facing, expected_tag in combatants:
        is_player = (name == "Player")

        # Determine character to search for
        if is_alive:
            if is_player:
                char = "J"
            elif is_ally:
                char = "A"
            else:
                char = "E"
        else:
            if is_player:
                char = "j"
            elif is_ally:
                char = "a"
            else:
                char = "e"

        # Find the character in the text widget
        pos = window.text_widget.search(char, "1.0", tk.END)
        if pos:
            tags = window.text_widget.tag_names(pos)
            tag_match = expected_tag in tags if tags else False

            # Get tag color
            if tags and tags[0]:
                color_config = window.text_widget.tag_configure(tags[0])
                color = color_config.get('foreground')
            else:
                color = "NONE"

            results.append({
                'name': name,
                'char': char,
                'pos': pos,
                'tags': tags,
                'expected': expected_tag,
                'match': tag_match,
                'color': color,
            })
        else:
            results.append({
                'name': name,
                'char': char,
                'pos': "NOT_FOUND",
                'tags': (),
                'expected': expected_tag,
                'match': False,
                'color': "N/A",
            })

    # Print results
    all_pass = True
    for r in results:
        status = "✓ PASS" if r['match'] else "✗ FAIL"
        print(f"{status} {r['name']:15} | Char: {r['char']} | Tag: {r['tags']} | Expected: {r['expected']} | Color: {r['color']}")
        all_pass = all_pass and r['match']

    print("=" * 60)
    if all_pass:
        print("SUCCESS! All combatant colors are working correctly!")
    else:
        print("ERROR! Some combatants don't have correct tags.")
    print("=" * 60)

    # Close without mainloop
    window.window.destroy()
    return all_pass


if __name__ == "__main__":
    success = verify_colors_working()
    sys.exit(0 if success else 1)
