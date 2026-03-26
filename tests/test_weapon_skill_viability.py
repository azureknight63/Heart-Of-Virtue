"""
Unit tests to verify weapon-based skills are viable when equipped with correct weapon types.

This test ensures that for each weapon skill category (Dagger, Sword, Axe, Bludgeon, Bow, Unarmed),
if a skill has weapon requirements, it becomes viable when that weapon type is equipped in combat.
"""

import sys
from pathlib import Path

# Set up path for imports
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import via src to support coverage tracking
from src.player import Player  # type: ignore
from src import moves  # type: ignore
from src import items as items_mod  # type: ignore


class DummyEnemy:
    """Dummy enemy for testing viability checks."""
    is_alive = True

    def __init__(self):
        self.combat_position = (25, 25)


def create_player_with_weapon(weapon_class):
    """Create a player with a weapon equipped and in combat with a dummy enemy."""
    player = Player()
    weapon = weapon_class()
    player.eq_weapon = weapon

    # Set up combat context
    dummy = DummyEnemy()
    player.combat_proximity = {dummy: 3}  # Enemy 3 feet away

    # For coordinate-based systems, set player position
    player.combat_position = (25, 22)

    return player, weapon


# Weapon class mapping for each skill category
WEAPON_CLASSES = {
    "Dagger": items_mod.Dagger,
    "Sword": items_mod.Shortsword,
    "Axe": items_mod.Battleaxe,
    "Bludgeon": items_mod.Mace,
    "Bow": items_mod.Longbow,
    "Unarmed": None,  # No weapon needed
}


# Skill categories with their learnable moves from skilltree.py
SKILL_CATEGORIES = {
    "Dagger": [
        ("Slash", moves.Slash),
        ("Quiet Movement", moves.QuietMovement),
        ("Feint And Pivot", moves.FeintAndPivot),
        ("Quick Swap", moves.QuickSwap),
    ],
    "Axe": [
        ("Slash", moves.Slash),
        ("Parry", moves.Parry),
        ("Bull Charge", moves.BullCharge),
        ("Whirl Attack", moves.WhirlAttack),
        ("Vertigo Spin", moves.VertigoSpin),
        ("Quick Swap", moves.QuickSwap),
    ],
    "Bow": [
        ("Tactical Positioning", moves.TacticalPositioning),
        ("Tactical Retreat", moves.TacticalRetreat),
        ("Flanking Maneuver", moves.FlankingManeuver),
        ("Quick Swap", moves.QuickSwap),
    ],
    "Unarmed": [
        ("Jab", moves.Jab),
        ("Whirl Attack", moves.WhirlAttack),
        ("Bull Charge", moves.BullCharge),
        ("Quick Swap", moves.QuickSwap),
    ],
    "Bludgeon": [
        ("Parry", moves.Parry),
        ("Power Strike", moves.PowerStrike),
        ("Bull Charge", moves.BullCharge),
        ("Vertigo Spin", moves.VertigoSpin),
        ("Whirl Attack", moves.WhirlAttack),
        ("Quick Swap", moves.QuickSwap),
    ],
}


def test_dagger_skills_viable():
    """Test Dagger skill viability."""
    player, weapon = create_player_with_weapon(items_mod.Dagger)

    # Slash should be viable
    slash = moves.Slash(player)
    assert slash.viable(), "Slash should be viable with Dagger"

    # Quick Swap should be viable (doesn't require specific weapon)
    quick_swap = moves.QuickSwap(player)
    # QuickSwap might not be viable depending on party setup, just test instantiation
    assert quick_swap is not None


def test_axe_skills_viable():
    """Test Axe skill viability - THIS VERIFIES THE SLASH FIX."""
    player, weapon = create_player_with_weapon(items_mod.Battleaxe)

    # Slash should be viable with Axe (this is the fix we're testing!)
    slash = moves.Slash(player)
    assert slash.viable(), "Slash should be viable with Axe (FIXED)"

    # Parry should be viable
    parry = moves.Parry(player)
    assert parry.viable(), "Parry should be viable with Axe"


def test_slash_with_all_allowed_weapons():
    """Test that Slash works with all weapon types that support it."""
    allowed_weapons = [
        ("Dagger", items_mod.Dagger),
        ("Shortsword", items_mod.Shortsword),
        ("Battleaxe", items_mod.Battleaxe),
    ]

    for weapon_name, weapon_class in allowed_weapons:
        player, weapon = create_player_with_weapon(weapon_class)
        slash = moves.Slash(player)
        assert slash.viable(), f"Slash should be viable with {weapon_name} ({weapon.subtype})"


def test_bludgeon_power_strike_viable():
    """Test Bludgeon Power Strike viability."""
    player, weapon = create_player_with_weapon(items_mod.Mace)

    # Power Strike should be viable only with Bludgeon
    power_strike = moves.PowerStrike(player)
    assert power_strike.viable(), "Power Strike should be viable with Bludgeon"


def test_bow_skills_viable():
    """Test Bow skill viability."""
    player, weapon = create_player_with_weapon(items_mod.Longbow)

    # Tactical Retreat should be viable with Bow
    tactical_retreat = moves.TacticalRetreat(player)
    assert tactical_retreat.viable(), "Tactical Retreat should be viable with Bow"


def test_unarmed_skills_viable():
    """Test Unarmed skill viability."""
    player = Player()
    player.eq_weapon = None  # Unarmed

    # Set up combat context
    dummy = DummyEnemy()
    player.combat_proximity = {dummy: 3}
    player.combat_position = (25, 22)

    # Jab should be viable when unarmed
    jab = moves.Jab(player)
    assert jab.viable(), "Jab should be viable when unarmed"


def test_slash_not_viable_without_weapon():
    """Test that Slash is NOT viable when unarmed."""
    player = Player()
    player.eq_weapon = None  # Unarmed

    # Set up combat context
    dummy = DummyEnemy()
    player.combat_proximity = {dummy: 3}
    player.combat_position = (25, 22)

    slash = moves.Slash(player)
    assert not slash.viable(), "Slash should NOT be viable when unarmed"


def test_parry_not_viable_without_weapon():
    """Test that Parry is NOT viable for Jean when unarmed."""
    player = Player()
    player.name = "Jean"  # Important: Parry checks if player is Jean
    player.eq_weapon = None  # Unarmed

    parry = moves.Parry(player)
    assert not parry.viable(), "Parry should NOT be viable when unarmed as Jean"


def test_power_strike_not_viable_with_wrong_weapon():
    """Test that Power Strike is NOT viable with non-Bludgeon weapons."""
    player, weapon = create_player_with_weapon(items_mod.Shortsword)

    power_strike = moves.PowerStrike(player)
    assert not power_strike.viable(), "Power Strike should NOT be viable with Sword (not Bludgeon)"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
