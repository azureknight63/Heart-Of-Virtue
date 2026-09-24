"""Issue #586 part B: King Slime's Tidal Surge must be survivable when warned.

The severity work in part A made the wind-up legible (a "deadly" badge, its
own log entry type). Part B is the balance half: at 2.5x, a max-roll surge
(50 dmg x 1.2 x 2.5 = 150 raw, ~130 after the beta's leather set) killed a
full-HP Jean at the level the beta reaches the Grondelith arena outright, so
the warning was a countdown to a death the player could not act on. The
retune to 1.8x (72-108 raw) keeps the move the hardest hit in the game while
leaving a full-HP arena Jean standing after the worst roll.

Nothing here is hand-typed: the band comes from ``NpcAttack``'s power roll
and ``TidalSurge``'s multiplier via the move's own ``evaluate()``, Jean is a
real ``Player`` levelled through ``_level_up_api()`` and dressed by the same
``SessionManager`` path the beta config dresses him through, and the hit is
the real ``execute()`` with the roll forced to its ceiling. Every roll is
seeded or pinned (CLAUDE.md: never assert on an unseeded roll).
"""

from unittest.mock import patch

import pytest

import src.functions as functions
from src.api.services.session_manager import SessionManager
from src.moves import TidalSurge
from src.npc._enemies import KingSlime
from src.npc_level_tables import REGION_ENEMY_LEVELS, apply_enemy_level
from src.player import Player
from tests._combat_fixtures import seeded

#: The config the beta ships; ``SessionManager`` reads ``CONFIG_FILE`` and
#: exposes its ``starting_equipment`` specs, so the loadout is the one the app
#: applies rather than a copy of it.
_BETA_CONFIG_NAME = "config_grondia_beta.ini"

#: The level a beta play-through reaches the arena at (maintainer's call on
#: #586). Two level-ups from the beta's level-1 start.
_ARENA_LEVEL = 3


def _beta_arena_jean(monkeypatch):
    """A full-HP Jean as the beta produces him at the arena.

    Levelled through the engine's own ``_level_up_api()`` (seeded, so the
    random stat bonuses are reproducible) with the awarded attribute points
    left UNSPENT: no allocation can lower ``maxhp``, so this is the floor of
    what a level-3 Jean can bring to the fight, and a guard that holds here
    holds for every build.
    """
    monkeypatch.setenv("CONFIG_FILE", _BETA_CONFIG_NAME)
    with patch("builtins.print"):
        manager = SessionManager()
        jean = Player()
        manager._apply_starting_equipment(jean)
        with seeded():
            while jean.level < _ARENA_LEVEL:
                jean._level_up_api()
        functions.refresh_stat_bonuses(jean)
    jean.hp = jean.maxhp
    jean.combat_list = []
    jean.combat_list_allies = [jean]
    jean.combat_proximity = {}
    return jean


def _engaged_king_slime(jean):
    slime = KingSlime()
    slime.target = jean
    slime.combat_proximity = {jean: 1}
    jean.combat_proximity[slime] = 1
    jean.combat_list = [slime]
    return slime


def _max_roll_surge(slime):
    """A ``TidalSurge`` whose power is the ceiling of its own band.

    ``NpcAttack.evaluate`` rolls ``uniform(_POWER_ROLL_MIN, _POWER_ROLL_MAX)``
    and ``TelegraphedSurge.evaluate`` multiplies that by
    ``_DAMAGE_MULTIPLIER``; pinning ``uniform`` to its upper bound yields the
    hardest hit the move can land without retyping either number.
    """
    with patch("builtins.print"):
        surge = TidalSurge(slime)
        with patch("random.uniform", side_effect=lambda lo, hi: hi):
            surge.evaluate()
    return surge


@pytest.fixture
def jean(monkeypatch):
    return _beta_arena_jean(monkeypatch)


def test_arena_jean_fixture_is_the_beta_jean(jean):
    """Positive control: the guard below is only meaningful against the
    Jean the beta actually fields — levelled, armoured and at full HP."""
    assert jean.level == _ARENA_LEVEL
    assert jean.hp == jean.maxhp > 0
    # The beta's starting_equipment must have landed, or the damage line
    # below is tested against a Jean in tattered cloth.
    assert jean.protection > Player().protection


def test_max_roll_power_is_the_declared_band_ceiling(jean):
    """The raw band ceiling the retune is stated in terms of (72-108 at
    1.8x) is ``damage x roll ceiling x multiplier`` and nothing else."""
    slime = _engaged_king_slime(jean)
    surge = _max_roll_surge(slime)

    assert surge.power == pytest.approx(
        slime.damage * surge._POWER_ROLL_MAX * surge._DAMAGE_MULTIPLIER
    )


def test_max_roll_surge_leaves_full_hp_arena_jean_standing(jean):
    """A warned hit must be survivable: the worst Tidal Surge roll, landing
    clean (no glance, no facing bonus), does not take a full-HP arena Jean
    to 0. At the pre-#586 2.5x this hit for more than his whole bar."""
    slime = _engaged_king_slime(jean)
    surge = _max_roll_surge(slime)

    # randint -> 0 is the to-hit roll that always lands and never glances
    # (a glance needs ``hit_chance - roll < 10``); the seed covers the
    # Slimed inflict roll inside ``hit()``.
    with patch("builtins.print"), seeded(), patch("random.randint", return_value=0):
        surge.execute(slime)

    assert jean.hp > 0, (
        f"max-roll Tidal Surge ({surge.power:.0f} raw at "
        f"{surge._DAMAGE_MULTIPLIER}x) took a full-HP level-{jean.level} Jean "
        f"({jean.maxhp} HP, {jean.protection:.1f} protection) to {jean.hp}"
    )
    # And it really was the boss's signature blow, not a whiff: the bar moved.
    assert jean.hp < jean.maxhp


def test_tidal_surge_stays_deadly_after_the_retune():
    """The retune changes the number, not the warning: the wind-up still
    telegraphs as the game's one "deadly" move (part A of #586)."""
    assert TidalSurge.telegraph_severity == "deadly"


# --- #655: the guard above at the level the table actually spawns him at ----
#
# The tests above build a level-1 King Slime (50 damage), which is the fight
# #586 tuned the 1.8x multiplier against. #617 then gave him a region level
# and a growth profile, and at the draft level 6 (100 damage) a max-roll
# surge was 216 raw -- more than Jean's whole bar (docs/qa/
# 2026-09-24-balance-baseline.md). These rebuild the boss through the real
# spawn path at whatever level REGION_ENEMY_LEVELS gives him, so a future
# table edit that brings the one-shot back fails here.

#: The config production ships (beta 2): Jean starts at level 4 with the
#: chapter-1 kit (Jean alone, as in the Pools).
_PROD_CONFIG_NAME = "config_prod.ini"

#: King Slime's home region -- the map his placement lives on.
_KING_SLIME_REGION = "grondelith-mineral-pools"

#: The levels Jean realistically fights King Slime at: prod starts him at 4,
#: and the Pools' spawns pay roughly 1,000 exp before the boss, so he usually
#: arrives at 5 (the baseline report's "Assumptions" table).
_KING_SLIME_JEAN_LEVELS = (4, 5)


def _prod_jean_at(monkeypatch, level):
    """A full-HP Jean as production fields him at ``level``.

    Dressed by ``SessionManager`` from ``config_prod.ini`` and climbed through
    ``apply_starting_level`` (seeded) with the ``even`` allocation -- the
    baseline report's model of a player who has spent the LEVEL UP points
    the prod start hands him before he reaches the Pools.
    """
    monkeypatch.setenv("CONFIG_FILE", _PROD_CONFIG_NAME)
    with patch("builtins.print"):
        manager = SessionManager()
        jean = Player()
        manager._apply_starting_equipment(jean)
        with seeded():
            jean.apply_starting_level(level, allocation="even")
        functions.refresh_stat_bonuses(jean)
    jean.hp = jean.maxhp
    jean.combat_list = []
    jean.combat_list_allies = [jean]
    jean.combat_proximity = {}
    return jean


def _region_king_slime(jean):
    """King Slime built by the real spawn path for his home region.

    ``apply_enemy_level`` resolves the level from ``REGION_ENEMY_LEVELS`` and,
    since he is a boss, never rolls it -- so this is exactly the King Slime
    the map places, not a literal level typed into the test.
    """
    slime = _engaged_king_slime(jean)
    with seeded():
        apply_enemy_level(slime, _KING_SLIME_REGION)
    return slime


@pytest.mark.parametrize("jean_level", _KING_SLIME_JEAN_LEVELS)
def test_region_king_slime_is_built_at_its_table_level(monkeypatch, jean_level):
    """Positive control: the boss below really is the table's King Slime,
    levelled and grown, not a level-1 stand-in."""
    jean = _prod_jean_at(monkeypatch, jean_level)
    slime = _region_king_slime(jean)

    expected = REGION_ENEMY_LEVELS[_KING_SLIME_REGION]["KingSlime"]
    assert jean.level == jean_level
    assert slime.level == expected
    assert expected > 1, "the table stopped levelling King Slime; this control needs one"
    assert slime.damage > KingSlime().damage


@pytest.mark.parametrize("jean_level", _KING_SLIME_JEAN_LEVELS)
def test_max_roll_surge_from_region_king_slime_leaves_full_hp_jean_standing(
    monkeypatch, jean_level
):
    """#586's promise at the level the map spawns him: the worst Tidal
    Surge, landing clean, does not take a full-HP Jean at a realistic level
    to 0."""
    jean = _prod_jean_at(monkeypatch, jean_level)
    slime = _region_king_slime(jean)
    surge = _max_roll_surge(slime)

    with patch("builtins.print"), seeded(), patch("random.randint", return_value=0):
        surge.execute(slime)

    assert jean.hp > 0, (
        f"max-roll Tidal Surge from a level-{slime.level} King Slime "
        f"({slime.damage} damage, {surge.power:.0f} raw) took a full-HP "
        f"level-{jean.level} Jean ({jean.maxhp} HP, "
        f"{jean.protection:.1f} protection) to {jean.hp}"
    )
    assert jean.hp < jean.maxhp
