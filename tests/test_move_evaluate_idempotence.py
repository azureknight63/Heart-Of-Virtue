"""Contract test: ``Move.evaluate()`` must be idempotent for every move.

``Move.advance()`` calls ``evaluate()`` once per beat for *every* move in
``known_moves`` — used or not, viable or not. ``evaluate()``'s documented job
is to "adjust the move's attributes to match the current game state", i.e. it
is a pure recomputation from the user's stats and equipment. So for a fixed
game state, calling it N times must land on the same numbers as calling it
once.

A move that instead feeds its own previous output back into its input drifts
silently and without bound. That is exactly what ``PommelStrike`` did: it
passed ``self.power`` as ``standard_evaluate_attack``'s ``base_power``, and
since that helper computes ``weapon.damage + base_power + str*str_mod +
fin*fin_mod``, each beat added the running total to itself — 51 -> 102 -> 153
-> ... on a Longsword, turning a documented "quick strike ... to fill in gap
time" into the strongest attack in the game by beat five. Nothing failed, no
exception was raised, and no existing test noticed, because every move's
``evaluate()`` was only ever exercised once per test.

Randomness is neutralised rather than banned: some moves legitimately roll a
damage spread every beat (``PowerStrike`` uses ``random.uniform(1.5, 2.5)``).
Re-seeding ``random`` to the same value before each call keeps those moves
deterministic under test while leaving genuine state accumulation — which does
not depend on the RNG — fully visible.
"""

import inspect
import pathlib
import random
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.items as items  # noqa: E402
import src.npc as npc  # noqa: E402
from src import moves  # noqa: E402
from src.moves import Move, PassiveMove  # noqa: E402
from src.player import Player  # noqa: E402

#: Attributes ``evaluate()`` owns. Each is a pure function of game state, so
#: each must be stable under repeated evaluation.
_EVALUATED_ATTRS = ("power", "fatigue_cost", "stage_beat", "mvrange", "base_damage_type")

#: Number of extra ``evaluate()`` calls after the baseline snapshot. Compounding
#: bugs are geometric, so even a handful of beats makes the drift unmistakable.
_REPEATS = 5

#: Fixed RNG seed re-applied before every ``evaluate()`` call.
_SEED = 20260828

#: Moves whose ``evaluate()`` is known to be non-idempotent and which live in a
#: file this test's owner does not control. Keys are ``"<module>.<ClassName>"``;
#: values are the reason, surfaced in the xfail output. Empty is the goal state:
#: an entry here is a live bug, not an exemption. Delete the entry when the
#: owning file is fixed — the strict xfail below fails loudly if a listed move
#: starts passing, so this list cannot rot into a lie.
_KNOWN_NON_IDEMPOTENT = {}


def _castable_move_classes():
    """Every concrete, castable move class re-exported by ``src.moves``.

    Passives are excluded: ``PassiveMove`` is flag-only, never castable, and
    its ``evaluate()`` is a no-op by construction.
    """
    for name in moves.__all__:
        obj = getattr(moves, name)
        if not (inspect.isclass(obj) and issubclass(obj, Move)):
            continue
        if obj in (Move, PassiveMove) or issubclass(obj, PassiveMove):
            continue
        yield f"{obj.__module__}.{name}", obj


def _build_combatants():
    """A player and a hostile NPC, wired into each other's proximity maps.

    Several moves read ``combat_proximity`` / ``combat_list`` during
    construction or evaluation, so both sides must be populated for every move
    class to build.
    """
    player = Player()
    player.eq_weapon = items.Longsword()
    enemy = npc.Slime()
    player.combat_proximity = {enemy: 1}
    player.combat_list = [enemy]
    enemy.combat_proximity = {player: 1}
    enemy.combat_list = [player]
    return player, enemy


def _snapshot(move):
    """Repr-based snapshot of the attributes ``evaluate()`` writes.

    ``repr`` rather than the values themselves so that mutable containers
    (``stage_beat`` is a list the move rewrites in place) are compared by
    content at snapshot time instead of by a shared reference that would always
    look equal to itself.
    """
    return {
        attr: repr(getattr(move, attr, "<attribute absent>"))
        for attr in _EVALUATED_ATTRS
    }


def _drift(move):
    """Return ``{attr: (after_first_call, after_repeats)}`` for anything that moved."""
    random.seed(_SEED)
    move.evaluate()
    first = _snapshot(move)
    for _ in range(_REPEATS):
        random.seed(_SEED)
        move.evaluate()
    later = _snapshot(move)
    return {a: (first[a], later[a]) for a in _EVALUATED_ATTRS if first[a] != later[a]}


_MOVE_CASES = sorted(_castable_move_classes())


def _case_params():
    for qualname, cls in _MOVE_CASES:
        reason = _KNOWN_NON_IDEMPOTENT.get(qualname)
        marks = (
            [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
        )
        yield pytest.param(qualname, cls, marks=marks, id=qualname)


def test_move_case_list_is_populated():
    """Guard the enumeration itself.

    If ``moves.__all__`` or the filter ever breaks, the parametrised sweep below
    would silently collect zero cases and pass — the same class of invisible
    failure it exists to catch.
    """
    assert len(_MOVE_CASES) > 50, f"only {len(_MOVE_CASES)} castable moves found"


def test_known_non_idempotent_entries_still_exist():
    """Every waiver names a move that is actually present."""
    known = set(_KNOWN_NON_IDEMPOTENT)
    present = {qualname for qualname, _ in _MOVE_CASES}
    assert known <= present, f"waivers name unknown moves: {sorted(known - present)}"


@pytest.mark.parametrize("qualname, move_cls", list(_case_params()))
def test_evaluate_is_idempotent(qualname, move_cls):
    """Repeated ``evaluate()`` on an unchanged game state must not move a number."""
    player, enemy = _build_combatants()
    user = enemy if move_cls.__module__ == "src.moves._npc" else player

    random.seed(_SEED)
    move = move_cls(user)

    drift = _drift(move)
    assert not drift, (
        f"{qualname}.evaluate() is not idempotent — "
        f"{_REPEATS + 1} calls on an unchanged game state produced different "
        f"results than the first: "
        + "; ".join(
            f"{attr}: {before} -> {after}" for attr, (before, after) in sorted(drift.items())
        )
        + ". evaluate() must recompute from game state, never fold its own "
        "previous output back into its input (advance() calls it every beat)."
    )


def test_pommel_strike_power_does_not_compound():
    """Named regression for the bug this whole file exists to prevent.

    ``PommelStrike.evaluate()`` used to pass ``self.power`` as
    ``standard_evaluate_attack``'s ``base_power``, doubling its own power every
    beat. Pinned separately from the sweep so the failure names the culprit
    directly if it ever regresses.
    """
    player, _ = _build_combatants()
    move = moves.PommelStrike(player)

    readings = [move.power]
    for _ in range(10):
        move.evaluate()
        readings.append(move.power)

    assert len(set(readings)) == 1, (
        f"PommelStrike.power drifted across evaluate() calls: {readings}"
    )
    assert readings[0] > 0, "PommelStrike should deal damage with a weapon equipped"

    # It is a weak filler, not a finisher: strictly less powerful than the
    # basic swing it is meant to fill gap time around, and cheaper to throw.
    basic = moves.Attack(player)
    assert move.power < basic.power, (
        f"Pommel Strike ({move.power}) should hit for less than Attack ({basic.power})"
    )
    assert move.fatigue_cost < basic.fatigue_cost, (
        f"Pommel Strike ({move.fatigue_cost} fatigue) should cost less than "
        f"Attack ({basic.fatigue_cost} fatigue)"
    )
    assert move.stage_beat[0] <= basic.stage_beat[0], (
        "Pommel Strike should wind up at least as fast as Attack"
    )
