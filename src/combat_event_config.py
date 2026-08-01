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

    # List of (ally_type_name, count) tuples. These join the fight as full,
    # AI-controlled combatants but are NOT added to the player's persistent
    # party — they don't follow Jean between rooms, don't gain exp, and are
    # dropped from combat_list_allies once this encounter ends (see the
    # `event_temp_ally` marker set on them in events.CombatEvent).
    ally_list: List[Tuple[str, int]] = field(default_factory=list)

    # Optional override for grid size (width, height)
    # If None, uses dynamic sizing based on combatant count
    grid_size_override: Optional[Tuple[int, int]] = None

    # Scenario type: "standard" (allies left, enemies right — the default),
    # "pincer" (allies center, enemies split to left/right flanks), "melee"
    # (everyone scattered at random), "ambush" (opposite of pincer: allies
    # split to left/right flanks, enemies center), or "boss_arena" (standard,
    # but tighter — forces melee range). Applied verbatim as an explicit
    # override for this scripted encounter, taking precedence over the
    # heuristic ApiCombatAdapter otherwise uses.
    scenario_type: str = "standard"

    # Narrative text to display when the event is triggered (narrative bridge to combat)
    narrative_text: str = ""

    # Optional narration shown as its own conversation dialog immediately
    # before the victory dialog (see ApiCombatAdapter._handle_victory).
    on_victory_text: str = ""
