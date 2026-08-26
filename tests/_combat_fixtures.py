"""Canonical combat-domain test factories (moves, states, positions, adapter).

Why this module exists
----------------------
The combat slice of the suite (~54 files, ~28k lines) rebuilt its combatants by
hand in almost every test: a ``MagicMock`` player with fifteen attributes pinned
on it, a ``MagicMock`` enemy with ten more, and a fresh hand-rolled move class.
Those copies drifted, and — worse — a mock combatant cannot catch the failure
mode CLAUDE.md names as this codebase's dominant bug class, because the mock
answers every attribute the test asks for whether or not the real ``Player``
has it. (``player.health``, ``player.stamina`` and ``player.evasion`` do not
exist; a ``MagicMock`` will happily serve all three.)

Building a real ``Player`` costs ~1.3 ms and a real ``NPC`` ~0.1 ms, so there is
no performance reason to mock either one. Prefer :func:`make_player` /
:func:`make_npc` and reach for a mock only to force a state a real object cannot
reach (a method that raises, a missing attribute).

These are plain functions rather than ``@pytest.fixture`` definitions on
purpose: this file is not a ``conftest.py`` (agent A8 owns those), so fixtures
declared here would not be auto-discovered. Each test module wraps whichever
factory it needs in a one-line local fixture. **These should be promoted to
``tests/conftest.py``.**
"""

import random
from contextlib import contextmanager

import src.items as items
import src.positions as positions
from src.npc import NPC
from src.player import Player

__all__ = [
    "make_player",
    "make_npc",
    "make_weapon",
    "engage",
    "place",
    "repair_proximity",
    "make_adapter",
    "seeded",
    "forced_roll",
    "WEAPON_BY_SUBTYPE",
]

#: One instantiable weapon per subtype the moves package branches on. Keyed by
#: the ``subtype`` string the engine actually compares against (``eq_weapon
#: .subtype``), so a test says what it means -- ``make_weapon("Sword")`` --
#: rather than encoding the incidental class name of whichever sword was handy.
WEAPON_BY_SUBTYPE = {
    "Unarmed": "Fists",
    "Dagger": "Dagger",
    "Sword": "Longsword",
    "Axe": "Battleaxe",
    "Bludgeon": "Hammer",
    "Spear": "Spear",
    "Scythe": "Scythe",
    "Pick": "Pickaxe",
    "Polearm": "Pole",
    "Halberd": "Halberd",
    "Bow": "Shortbow",
    "Crossbow": "Crossbow",
}


def make_weapon(subtype="Sword", **overrides):
    """Return a real weapon item of the given ``subtype``.

    ``overrides`` are applied as attributes after construction so a test can pin
    ``damage=0`` to make a hit's hp delta fully predictable without inventing a
    fake weapon class that would skip the real ``subtype``/``weight`` wiring.
    """
    try:
        cls = getattr(items, WEAPON_BY_SUBTYPE[subtype])
    except KeyError:  # pragma: no cover - guards a typo in a test, not prod
        raise KeyError(
            f"No weapon registered for subtype {subtype!r}; "
            f"known: {sorted(WEAPON_BY_SUBTYPE)}"
        ) from None
    weapon = cls()
    for key, value in overrides.items():
        setattr(weapon, key, value)
    return weapon


def make_player(weapon=None, moves=None, **stats):
    """Return a real :class:`~src.player.Player` with ``stats`` applied.

    ``weapon`` may be a subtype string (``"Sword"``), an item instance, or
    ``None`` to leave the default loadout alone. ``moves`` replaces
    ``known_moves`` outright when given.

    Every keyword in ``stats`` is checked against the real ``Player`` before it
    is set: silently accepting ``hp=...`` alongside a typo'd ``health=...``
    is exactly how a test ends up asserting on an attribute the engine never
    reads.
    """
    player = Player()
    _apply_stats(player, stats)
    if weapon is not None:
        player.eq_weapon = make_weapon(weapon) if isinstance(weapon, str) else weapon
    if moves is not None:
        player.known_moves = list(moves)
    return player


#: Constructor arguments for the bare ``NPC`` base. Concrete enemies
#: (``Slime``, ``RockRumbler``, ...) supply their own, so these are only used
#: when a test asks for the generic "a combatant that is not Jean".
_BASE_NPC_ARGS = dict(
    name="Dummy",
    description="A featureless training dummy.",
    damage=5,
    aggro=True,
    exp_award=10,
)


def make_npc(cls=NPC, weapon=None, moves=None, **stats):
    """Return a real NPC instance of ``cls`` with ``stats`` applied.

    ``cls`` defaults to the plain ``NPC`` base so a test that only needs "a
    combatant that is not Jean" does not accidentally inherit a concrete
    enemy's move list or resistances. Constructor-only arguments of the base
    class (``name``, ``damage``, ``exp_award``, ...) may be passed in ``stats``
    and are routed to ``__init__`` rather than set afterwards.
    """
    if cls is NPC:
        ctor = dict(_BASE_NPC_ARGS)
        ctor.update({k: stats.pop(k) for k in list(stats) if k in _BASE_NPC_ARGS})
        npc = cls(**ctor)
    else:
        npc = cls()
    _apply_stats(npc, stats)
    if weapon is not None:
        npc.eq_weapon = make_weapon(weapon) if isinstance(weapon, str) else weapon
    if moves is not None:
        npc.known_moves = list(moves)
    return npc


#: Attributes a test may create even though a freshly-built combatant lacks
#: them, because the engine itself creates them lazily during combat.
_LAZY_ATTRS = frozenset(
    {
        "combat_position",
        "combat_proximity",
        "combat_list",
        "combat_list_allies",
        "current_move",
        "combat_delay",
        "combat_exp",
        "target",
        "friend",
        "aggro",
        "in_combat",
    }
)


def _apply_stats(combatant, stats):
    for key, value in stats.items():
        if not hasattr(combatant, key) and key not in _LAZY_ATTRS:
            raise AttributeError(
                f"{type(combatant).__name__} has no attribute {key!r}. "
                "Real engine objects do not answer arbitrary attributes -- "
                "check the spelling against the class (e.g. hp, not health)."
            )
        setattr(combatant, key, value)


def engage(player, enemies=(), allies=(), with_positions=True, grid=None):
    """Wire a real combat encounter between ``player``, ``enemies``, ``allies``.

    Sets each side's ``combat_list``/``combat_list_allies``, marks everyone
    ``in_combat``, and (unless ``with_positions`` is false) runs the real
    :func:`src.positions.initialize_combat_positions` so ``combat_position``
    and ``combat_proximity`` hold engine-computed values rather than numbers a
    test made up.

    Returns ``(player_side, enemy_side)`` as two lists.
    """
    enemies = list(enemies)
    allies = list(allies)
    player_side = [player] + allies
    for member in player_side:
        member.friend = True
        member.in_combat = True
        member.combat_list = list(enemies)
        member.combat_list_allies = list(player_side)
    player.friend = True
    for enemy in enemies:
        enemy.friend = False
        enemy.in_combat = True
        enemy.combat_list = list(player_side)
        enemy.combat_list_allies = list(enemies)
    if with_positions and enemies:
        if grid is not None:
            positions.CombatPosition.set_grid_bounds(*grid)
        positions.initialize_combat_positions(player_side, enemies)
    return player_side, enemies


def place(combatant, x, y, facing=None):
    """Pin ``combatant`` at an exact grid coordinate.

    Positional tests need deterministic coordinates;
    ``initialize_combat_positions`` deliberately randomises spawn points, so a
    test that asserts on distance/angle must place its combatants explicitly.
    """
    pos = positions.CombatPosition(x=x, y=y)
    if facing is not None:
        pos.facing = facing
    combatant.combat_position = pos
    return pos


def repair_proximity(combatants):
    """Recompute every combatant's ``combat_proximity`` from live coordinates."""
    everyone = list(combatants)
    for unit in everyone:
        unit.combat_proximity = positions.recalculate_proximity_dict(unit, everyone)


def make_adapter(player, enemies=(), allies=(), initialize=True, **engage_kwargs):
    """Build a real ``ApiCombatAdapter`` over real combatants.

    Imported lazily so the moves/states/positions tests that never touch the API
    layer do not pay for the Flask import chain.
    """
    from src.api.combat_adapter import ApiCombatAdapter

    engage(player, enemies, allies, **engage_kwargs)
    adapter = ApiCombatAdapter(player)
    if initialize:
        adapter.initialize_combat(list(enemies) + list(allies))
    return adapter


@contextmanager
def seeded(seed=1234):
    """Run a block against a seeded global RNG, restoring state afterwards.

    RNG-dependent combat tests must pin the exact outcome, not merely a range.
    Restoring the previous state keeps the seeding from leaking into whatever
    test happens to run next under ``pytest-randomly``.
    """
    state = random.getstate()
    random.seed(seed)
    try:
        yield
    finally:
        random.setstate(state)


@contextmanager
def forced_roll(value, module="src.moves._base"):
    """Force ``random.randint`` inside ``module`` to return ``value``.

    ``value`` may be an int (every roll) or an iterable (consumed in order,
    with the last entry repeating). Patches the ``random`` module object the
    move module imported, so only that module's rolls are affected.
    """
    from unittest.mock import patch

    if isinstance(value, int):
        rolls = None

        def _roll(*_args, **_kwargs):
            return value
    else:
        rolls = list(value)

        def _roll(*_args, **_kwargs):
            return rolls.pop(0) if len(rolls) > 1 else rolls[0]

    with patch(f"{module}.random.randint", side_effect=_roll) as patched:
        yield patched
