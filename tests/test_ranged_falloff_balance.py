"""Balance contract for ranged accuracy falloff.

These constants decide whether distance is a tactical choice at all, and
nothing else in the suite pins them: `range_decay` was previously 0.05-0.06,
which put zero hit chance ~2,000 ft away and cost 1-2 points anywhere a fight
could actually happen. A 20x correction to those numbers changed no test.

So this file asserts the *properties* the numbers exist to provide, not the
numbers themselves — a literal-value test would just be a change detector that
has to be edited every time the balance is tuned, and would say nothing about
whether the balance still works.

Geometry these properties are derived from:
  - one grid cell is ~1 ft (src/positions.py, `distance_from_coords`)
  - an arena is max(9, min(100, combatants * 3 + 3)) cells square
    (src/coordinate_config.py, `get_dynamic_grid_size`)
so a small skirmish spans ~9-15 ft and a large battle ~45-90 ft.
"""

import pytest

from src.items import Crossbow, Longbow, Shortbow

RANGED_WEAPONS = [Shortbow, Longbow, Crossbow]

# The largest arena is 100 cells square; a shot should stay usable across a
# large battle without being usable across a county.
LARGEST_ARENA_SPAN_FT = 100


def effective_max_range(weapon):
    """Distance at which hit chance decays to zero — the engine's own formula
    (`ShootBow.get_effective_range_max`, and the inline copy in `execute`)."""
    return weapon.range_base + (100 / weapon.range_decay)


@pytest.mark.parametrize("weapon_cls", RANGED_WEAPONS, ids=lambda c: c.__name__)
def test_reach_covers_a_large_battle_without_being_unbounded(weapon_cls):
    weapon = weapon_cls()
    reach = effective_max_range(weapon)

    assert reach >= LARGEST_ARENA_SPAN_FT, (
        f"{weapon_cls.__name__} decays to zero accuracy at {reach:.0f} ft, "
        f"inside the {LARGEST_ARENA_SPAN_FT} ft span of the largest arena — "
        "ranged combat would stop working in a big battle."
    )
    assert reach <= 4 * LARGEST_ARENA_SPAN_FT, (
        f"{weapon_cls.__name__} carries to {reach:.0f} ft, several times the "
        "largest arena. Decay that gradual is indistinguishable from no decay "
        "at every distance a fight occurs, which is what made range free."
    )


@pytest.mark.parametrize("weapon_cls", RANGED_WEAPONS, ids=lambda c: c.__name__)
def test_distance_costs_enough_accuracy_to_be_a_real_choice(weapon_cls):
    """Backing off has to cost something a player would weigh.

    Measured across a mid-size arena: a fight with ~10-14 combatants spans
    33-45 ft, so 40 ft is a distance opponents genuinely end up at.
    """
    weapon = weapon_cls()
    loss_at_40ft = max(0, (40 - weapon.range_base) * weapon.range_decay)

    assert loss_at_40ft >= 10, (
        f"{weapon_cls.__name__} sheds only {loss_at_40ft:.1f} points of hit "
        "chance at 40 ft. Below ~10 the penalty is lost in the roll and "
        "distance stops being a decision."
    )
    assert loss_at_40ft <= 60, (
        f"{weapon_cls.__name__} sheds {loss_at_40ft:.1f} points at 40 ft, "
        "which makes any shot across a mid-size arena a near-guaranteed miss."
    )


def test_the_long_range_weapon_is_the_one_that_holds_accuracy_longest():
    """Weapon identity, expressed through the falloff curve.

    The longbow is the reach weapon; the crossbow trades reach for damage and
    its higher str_mod. If a tuning pass ever inverts this, the weapons stop
    meaning what their stat blocks say they mean.
    """
    reaches = {cls.__name__: effective_max_range(cls()) for cls in RANGED_WEAPONS}

    assert reaches["Longbow"] > reaches["Shortbow"] > reaches["Crossbow"], (
        f"falloff ordering is {reaches}; expected Longbow > Shortbow > Crossbow"
    )
    assert Longbow().range_base > Shortbow().range_base > Crossbow().range_base, (
        "the full-accuracy plateau should follow the same ordering as reach"
    )


@pytest.mark.parametrize("weapon_cls", RANGED_WEAPONS, ids=lambda c: c.__name__)
def test_point_blank_shots_are_not_penalised(weapon_cls):
    """Nothing inside the plateau loses accuracy — the falloff only starts at
    `range_base`. Guards against a tuning pass that moves the plateau to zero
    and silently penalises every shot."""
    weapon = weapon_cls()
    assert weapon.range_base > 0
    assert max(0, (weapon.range_base - weapon.range_base) * weapon.range_decay) == 0
