"""``weight_tolerance`` is recomputed, never accumulated (issue: refresh stacking).

``refresh_stat_bonuses`` recomputes carry capacity as
``weight_tolerance_base + round((STR + END) / 2, 2)`` with a plain assignment.
An earlier version used ``+=``, so every refresh (equip, unequip, level-up,
save/load) silently inflated Jean's capacity.
"""

import pytest

from src.player import Player
import src.functions as functions


@pytest.fixture
def jean():
    return Player()


def test_weight_tolerance_is_not_stacked_on_refresh(jean):
    base = jean.weight_tolerance_base

    functions.refresh_stat_bonuses(jean)
    first = jean.weight_tolerance
    for _ in range(5):
        functions.refresh_stat_bonuses(jean)

    # Repeated refreshes must be idempotent -- the original bug only showed up
    # after the *second* call, so one extra call is the minimum useful probe.
    assert jean.weight_tolerance == first
    assert first == base + round((jean.strength + jean.endurance) / 2, 2)


def test_weight_tolerance_default_is_thirty_point_five(jean):
    """Pins the concrete shipped number so a change to the base or the
    STR/END weighting is visible, rather than being re-derived by the test
    from the same formula the code uses."""
    functions.refresh_stat_bonuses(jean)

    assert jean.weight_tolerance_base == 20.00
    assert (jean.strength, jean.endurance) == (10, 11)
    assert jean.weight_tolerance == 30.5


def test_weight_tolerance_tracks_the_underlying_attribute_base(jean):
    """Raising STR raises capacity by half the increase.

    Note the increase must go on ``strength_base``: ``refresh_stat_bonuses``
    rebuilds ``strength`` from base + equipment first, so a direct write to
    ``player.strength`` is overwritten before the capacity line runs.
    """
    functions.refresh_stat_bonuses(jean)
    before = jean.weight_tolerance

    jean.strength_base += 10
    functions.refresh_stat_bonuses(jean)

    assert jean.strength == 20
    assert jean.weight_tolerance == before + 5.0


def test_weight_tolerance_recalculation_is_jean_only(jean):
    """The capacity formula sits inside a ``name == "Jean"`` branch, so a
    combatant that is not Jean keeps whatever tolerance it was given."""
    other = Player()
    other.name = "Gorran"
    other.strength_base += 10

    functions.refresh_stat_bonuses(other)

    assert other.weight_tolerance == other.weight_tolerance_base == 20.00
