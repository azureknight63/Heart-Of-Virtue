#!/usr/bin/env python3
"""Test to verify battlefield window colors are displaying correctly."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import tkinter as tk
from src.combat_battlefield import CombatBattlefieldWindow
from src.positions import CombatPosition


def test_battlefield_colors():
    """Create a battlefield window and verify combatant colors."""
    window = CombatBattlefieldWindow("Test Battlefield Colors")
    window.create_window()  # Initialize the window
    
    # Add some test combatants at different health levels
    test_combatants = [
        {
            "name": "Jean",
            "position": CombatPosition(x=10, y=10),
            "is_player": True,
            "is_ally": False,
            "is_alive": True,
            "health_percent": 1.0,  # Healthy - should be green
            "facing": 0,  # North
        },
        {
            "name": "Ally1",
            "position": CombatPosition(x=12, y=10),
            "is_player": False,
            "is_ally": True,
            "is_alive": True,
            "health_percent": 0.5,  # Injured - should be orange
            "facing": 90,  # East
        },
        {
            "name": "Enemy1",
            "position": CombatPosition(x=8, y=10),
            "is_player": False,
            "is_ally": False,
            "is_alive": True,
            "health_percent": 0.2,  # Critical - should be red
            "facing": 180,  # South
        },
        {
            "name": "DeadEnemy",
            "position": CombatPosition(x=6, y=10),
            "is_player": False,
            "is_ally": False,
            "is_alive": False,
            "health_percent": 0.0,  # Dead - should be gray
            "facing": 270,  # West
        },
    ]
    
    for combatant in test_combatants:
        window.set_combatant(
            name=combatant["name"],
            position=combatant["position"],
            is_player=combatant["is_player"],
            is_ally=combatant["is_ally"],
            is_alive=combatant["is_alive"],
            health_percent=combatant["health_percent"],
            facing_value=combatant["facing"],
        )
    
    window.update_display()
    
    # Print out the text widget content for visual inspection
    print("=" * 60)
    print("BATTLEFIELD DISPLAY TEST")
    print("=" * 60)
    
    if window.text_widget:
        content = window.text_widget.get("1.0", tk.END)
        print(content)
        
        # Check tags at specific positions
        print("\n" + "=" * 60)
        print("TAG VERIFICATION")
        print("=" * 60)
        
        # Find and check Jean (player)
        jean_pos = window.text_widget.search("J", "1.0", tk.END)
        if jean_pos:
            tags = window.text_widget.tag_names(jean_pos)
            print(f"Jean position: {jean_pos}, Tags: {tags}")
            if "player" in tags:
                tag_config = window.text_widget.tag_configure("player")
                print(f"  Player tag color: {tag_config.get('foreground')}")
        
        # Find and check first Ally
        ally_pos = window.text_widget.search("A", "1.0", tk.END)
        if ally_pos:
            tags = window.text_widget.tag_names(ally_pos)
            print(f"Ally position: {ally_pos}, Tags: {tags}")
            if tags:
                tag_config = window.text_widget.tag_configure(tags[0])
                print(f"  Ally tag color: {tag_config.get('foreground')}")
        
        # Find and check first Enemy
        enemy_pos = window.text_widget.search("E", "1.0", tk.END)
        if enemy_pos:
            tags = window.text_widget.tag_names(enemy_pos)
            print(f"Enemy position: {enemy_pos}, Tags: {tags}")
            if tags:
                tag_config = window.text_widget.tag_configure(tags[0])
                print(f"  Enemy tag color: {tag_config.get('foreground')}")
    
    print("\n" + "=" * 60)
    print("VISUAL INSPECTION")
    print("=" * 60)
    print("Window is now open. Verify:")
    print("  - J (Jean): Should be GREEN (healthy player)")
    print("  - A (Ally): Should be ORANGE (injured)")
    print("  - E (Enemy): Should be RED (critical)")
    print("  - e (DeadEnemy): Should be GRAY (dead)")
    print("\nClose the window when ready.")
    print("=" * 60)
    
    # Keep window open for visual inspection
    window.window.mainloop()


if __name__ == "__main__":
    test_battlefield_colors()
