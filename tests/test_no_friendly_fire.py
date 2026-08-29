"""Contract: no player move may damage Jean's own allies.

Area moves used to iterate ``self.user.combat_proximity`` directly. That dict
holds BOTH sides of a fight, so every arc and spin dealt full damage to Jean's
allies -- silently, with no warning, no distinct log line, and no way for a
player watching Gorran's HP fall to learn they were the cause.

It was never a decision. Blood of Martyrs was the one area move that got it
right, purely because its author happened to reach for ``combat_list``
(hostiles) instead. Measured before the fix, with Gorran and a Slime both
adjacent: Whirl Attack dealt **27** to Gorran and **23** to the Slime -- more
to the ally than to the enemy it was aimed at.

The design decision is that friendly fire is off. Jean does not command his
allies -- Gorran and Mara pick their own moves, and both carry ``Advance`` --
and combat is beat-based, so an ally can walk into a swing during its wind-up.
That is damage the player could not have avoided or predicted, which is noise
rather than difficulty. Every game in the genre that ships friendly fire
(Divinity: Original Sin 2, Baldur's Gate, Final Fantasy Tactics, XCOM, Battle
Brothers) gives the player full control of every unit that can be hit, plus a
commit-time preview. Heart of Virtue has neither.

This file is the guard. The behavioural half proves no move harms an ally; the
structural half fails a move that walks ``combat_proximity`` unfiltered, so the
next area move added cannot reintroduce it by reaching for the wrong variable.
"""

import inspect
import pathlib
import random
import re
import sys
from unittest.mock import patch

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.items as items  # noqa: E402
import src.moves as moves  # noqa: E402
import src.npc as npc  # noqa: E402
import src.positions as positions  # noqa: E402
from src.moves._base import Move, PassiveMove  # noqa: E402
from src.narration import capture_narration  # noqa: E402
from src.player import Player  # noqa: E402

#: Every area move, with a weapon its tree accepts. These are the ones that
#: resolve against several combatants in one cast, i.e. the only ones that can
#: catch an ally without the player naming them.
AREA_MOVES = [
    ("WhirlAttack", items.Longsword),
    ("Reap", items.Scythe),
    ("Sweep", items.Pole),
    ("HalberdSpin", items.Pole),
]

#: The unfiltered spelling. ``combat_proximity`` holds both sides; a damage loop
#: that walks it directly is the bug. ``_hostiles_in_proximity()`` is the shared
#: filter that reads the same dict and drops same-side entries.
_UNFILTERED = re.compile(r"for\s+\w+\s+in\s+list\(\s*self\.user\.combat_proximity")


def _engaged(weapon_cls):
    """Jean, one enemy and one ally, all adjacent and all in reach."""
    player = Player()
    weapon = weapon_cls()
    player.inventory.append(weapon)
    weapon.isequipped = True
    player.eq_weapon = weapon
    player.combat_exp.setdefault(weapon.subtype, 0)

    enemy = npc.Slime()
    enemy.name = "Slime"
    enemy.maxhp = enemy.hp = 500
    ally = npc.Gorran()
    ally.name = "Gorran"
    ally.friend = True
    ally.maxhp = ally.hp = 500

    player.combat_list = [enemy]
    player.combat_list_allies = [player, ally]
    player.combat_proximity = {enemy: 2, ally: 2}
    player.in_combat = True
    # Everyone due NORTH of Jean, who faces north. Reap and Sweep are frontal-arc
    # moves, so a combatant placed to the side falls outside the cone and the
    # test would pass for the wrong reason. The ally sits BETWEEN Jean and the
    # enemy -- directly in the swing path -- which is the strongest possible
    # placement for the property being asserted.
    player.combat_position = positions.CombatPosition(10, 10, positions.Direction.N)
    ally.combat_position = positions.CombatPosition(10, 11, positions.Direction.N)
    enemy.combat_position = positions.CombatPosition(10, 12, positions.Direction.N)
    return player, enemy, ally


def _pinned_dice():
    """Force every per-target roll to land.

    These moves roll to-hit **per enemy**, so with live dice a second target can
    simply miss and a coverage assertion fails for a reason that has nothing to
    do with what it asserts. Pinning leaves the ally filter as the only thing
    that varies between runs.
    """
    return (
        patch.object(random, "randint", return_value=0),
        patch.object(random, "uniform", return_value=1.0),
        patch("src.functions.check_parry", return_value=False),
    )


@pytest.mark.parametrize("move_name,weapon_cls", AREA_MOVES)
def test_area_moves_never_harm_an_ally(move_name, weapon_cls):
    """The behavioural half, with the ally standing where the enemy stands."""
    player, enemy, ally = _engaged(weapon_cls)
    move = getattr(moves, move_name)(player)
    move.evaluate()
    move.target = player

    ally_before, enemy_before = ally.hp, enemy.hp
    a, b, c = _pinned_dice()
    with capture_narration(), a, b, c:
        move.execute(player)

    assert ally.hp == ally_before, (
        f"{move_name} dealt {ally_before - ally.hp} damage to an ally standing "
        "the same distance away as the enemy -- friendly fire is off by design"
    )
    assert enemy.hp < enemy_before, (
        f"{move_name} hit nobody; the fixture is wrong, not the move"
    )


@pytest.mark.parametrize("move_name,weapon_cls", AREA_MOVES)
def test_area_moves_still_reach_every_hostile(move_name, weapon_cls):
    """Filtering allies out must not also drop a second enemy.

    The obvious wrong fix -- resolving against ``self.target`` only -- would
    pass the test above while quietly turning every area move single-target.
    """
    player, first, ally = _engaged(weapon_cls)
    second = npc.Slime()
    second.name = "Second Slime"
    second.maxhp = second.hp = 500
    second.combat_position = positions.CombatPosition(10, 13, positions.Direction.N)
    player.combat_list.append(second)
    player.combat_proximity[second] = 2

    move = getattr(moves, move_name)(player)
    move.evaluate()
    move.target = player
    a, b, c = _pinned_dice()
    with capture_narration(), a, b, c:
        move.execute(player)

    assert first.hp < first.maxhp and second.hp < second.maxhp, (
        f"{move_name} reached {sum(e.hp < e.maxhp for e in (first, second))} of "
        "2 hostiles -- an area move must still hit every enemy in its band"
    )
    assert ally.hp == ally.maxhp


def _damage_loops_over_proximity():
    """Every move whose ``execute()`` walks ``combat_proximity`` unfiltered."""
    offenders = []
    package_dir = pathlib.Path(moves.__file__).parent
    for path in sorted(package_dir.glob("*.py")):
        if path.stem == "__init__":
            continue
        module = __import__(f"src.moves.{path.stem}", fromlist=["*"])
        for name, obj in vars(module).items():
            if not isinstance(obj, type) or not issubclass(obj, Move):
                continue
            if obj.__module__ != module.__name__ or issubclass(obj, PassiveMove):
                continue
            try:
                source = inspect.getsource(obj.execute)
            except (OSError, TypeError):
                continue
            if _UNFILTERED.search(source):
                offenders.append(f"{module.__name__}.{name}")
    return offenders


def test_no_execute_walks_proximity_unfiltered():
    """The structural half: catch the next one before it ships.

    ``combat_proximity`` is the natural variable to reach for and the wrong
    one -- it is how all four area moves acquired friendly fire independently.
    A move needing every nearby hostile should call
    ``self._hostiles_in_proximity()``, which reads the same dict and drops
    same-side entries.
    """
    offenders = _damage_loops_over_proximity()
    assert not offenders, (
        "these execute() bodies iterate combat_proximity unfiltered, so they "
        "will hit Jean's allies:\n  " + "\n  ".join(offenders) + "\n"
        "Use self._hostiles_in_proximity() instead."
    )


def test_the_structural_scan_can_actually_find_something():
    """A regex guard that matches nothing passes forever."""
    assert _UNFILTERED.search(
        "        for enemy in list(self.user.combat_proximity.keys()):"
    ), "the offender pattern no longer matches the shape it was written for"
