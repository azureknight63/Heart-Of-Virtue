"""
Configuration dataclasses for parameterized combat events.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class CombatEventConfig:
    """Configuration for a parameterized combat event.

    Allows defining specific enemies, allies, grid size, and scenario type
    for a combat encounter initiated via an event.
    """

    # List of (enemy_type_name, count) tuples
    # e.g. [("RockRumbler", 2), ("FeralWolf", 3)]
    enemy_list: List[Tuple[str, int]] = field(default_factory=list)

    # List of (ally_type_name, count) tuples
    ally_list: List[Tuple[str, int]] = field(default_factory=list)

    # Optional override for grid size (width, height)
    # If None, uses dynamic sizing based on combatant count
    grid_size_override: Optional[Tuple[int, int]] = None

    # Scenario type ("standard", "pincer", "melee", "boss_arena")
    scenario_type: str = "standard"

    # Narrative text to display when the event is triggered (narrative bridge to combat)
    narrative_text: str = ""

    # Optional text to display upon victory
    on_victory_text: str = ""
