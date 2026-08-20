"""Contract test for the ``Player`` attribute surface.

This file used to be a script: a module-level ``try/except`` that imported
``Player``, printed "Player imported successfully!", and swallowed every
exception into a traceback dump. It contained no test functions at all, so
pytest collected zero tests from it and a broken ``src.player`` would still have
produced a green run. It also did ``sys.path.insert(0, tests/)`` at import time,
polluting the path for every other test in the session.

What replaces it pins the two things the old script gestured at and the
attribute traps CLAUDE.md documents:

* ``Player()`` constructs, with its documented starting stats.
* The attributes tests keep inventing — ``health``, ``stamina``, ``defense``,
  ``accuracy``, ``evasion`` — genuinely do not exist. A ``MagicMock`` player
  answers all of them, which is exactly how a test ends up asserting a field the
  engine never had.
* The terminal verbs deleted in the terminal-mode teardown stay deleted.
"""

import pytest

from src.player import Player


@pytest.fixture(scope="module")
def fresh_player():
    """A default ``Player``. Module-scoped; tests here must not mutate it."""
    return Player()


def test_player_constructs_with_its_documented_starting_stats(fresh_player):
    assert fresh_player.name == "Jean"
    assert (fresh_player.hp, fresh_player.maxhp) == (100, 100)
    assert (fresh_player.fatigue, fresh_player.maxfatigue) == (190, 190)
    assert fresh_player.level == 1
    assert fresh_player.exp == 0


@pytest.mark.parametrize(
    "attribute, expected",
    [
        ("strength", 10),
        ("finesse", 11),
        ("speed", 10),
        ("endurance", 11),
        ("charisma", 9),
        ("intelligence", 10),
        ("faith", 11),
    ],
)
def test_starting_attributes(fresh_player, attribute, expected):
    assert getattr(fresh_player, attribute) == expected


def test_starting_inventory_contents(fresh_player):
    """Jean starts with his ring, the relic, cloth armour and a purse."""
    names = sorted(type(item).__name__ for item in fresh_player.inventory)
    assert names == [
        "ClothHood",
        "Gold",
        "JeanWeddingBand",
        "Relic",
        "TatteredCloth",
    ]


@pytest.mark.parametrize(
    "trap",
    ["health", "stamina", "defense", "accuracy", "evasion", "reputation", "attack"],
)
def test_attribute_traps_do_not_exist(fresh_player, trap):
    """CLAUDE.md's documented traps.

    A test that sets one of these on a ``MagicMock`` player and reads it back is
    asserting a field the engine has never had. ``hp`` is the real health
    attribute; ``fatigue`` the real stamina one; protection is the real
    damage-reduction stat.
    """
    assert not hasattr(fresh_player, trap)


def test_the_real_names_behind_the_traps(fresh_player):
    assert isinstance(fresh_player.hp, int)
    assert isinstance(fresh_player.fatigue, int)
    assert fresh_player.protection == pytest.approx(4.1)


@pytest.mark.parametrize(
    "verb",
    [
        "take",
        "print_inventory",
        "attack",
        "move",
        "move_north",
        "move_south",
        "move_east",
        "move_west",
        "move_northeast",
        "move_northwest",
        "move_southeast",
        "move_southwest",
        "look",
        "view",
        "flee",
        "commands",
    ],
)
def test_removed_terminal_verbs_stay_removed(fresh_player, verb):
    """The terminal-mode teardown deleted these; nothing may resurrect them."""
    assert not hasattr(fresh_player, verb)


def test_spec_mock_inherits_the_same_refusals():
    """``Mock(spec=Player)`` is the cheap way to keep the traps trapped."""
    from unittest.mock import MagicMock, Mock

    speced = Mock(spec=Player)
    with pytest.raises(AttributeError):
        speced.health
    # ...whereas a bare MagicMock happily invents it, which is the bug.
    assert MagicMock().health is not None
