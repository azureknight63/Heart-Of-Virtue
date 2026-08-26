"""Cooldown-drain behaviour of the real beat loop in ``ApiCombatAdapter``.

The fix (d0876dd) changed the beat loop so that when ``current_move`` is None:
  - if ANY known move is at stage 0 (ready) -> break and return control
  - if ALL moves are in cooldown (stage > 0) -> keep advancing beats

so the player is never handed a turn with zero available actions.

What changed and why
--------------------
Every test in this file used to run against ``_simulate_beat_exit`` -- a
*reimplementation* of that loop living in this file. It re-derived the exit
condition in ten lines of test-local code and then asserted that those ten lines
behaved as the docstring described. Deleting the guard from
``src/api/combat_adapter.py`` entirely would not have failed a single
assertion, and CLAUDE.md's architecture rule ("the API layer adapts; it does not
reimplement") applies to its tests as much as to the code.

The simulation is gone. These tests now drive
``ApiCombatAdapter._execute_move_inner`` over a real ``Player`` and a real
``Slime``, and read the number of beats the engine actually processed off the
``beat_states`` list it publishes.
"""

import pytest

from src.api.combat_adapter import ApiCombatAdapter
from src.npc import Slime
from src.player import Player
from tests._combat_fixtures import engage


class _StubMove:
    """A move that cools down by exactly one stage per ``advance()``.

    Deliberately hand-rolled rather than a real engine move: the point is to
    control the stage numbers precisely. Everything the adapter reads off a move
    while serializing the beat is present, so nothing about the loop is faked.
    """

    passive = False
    targeted = False
    instant = False
    needs_duration = False
    accepts_ally_target = False
    web_animation = "attack"
    category = "Attack"
    description = ""
    fatigue_cost = 0
    beats_left = 0
    stage_beat = (1, 1, 1, 3)

    def __init__(self, name, stage=0):
        self.name = name
        self.display_name = name
        self.current_stage = stage
        self.target = None
        self.user = None

    def advance(self, user):
        if self.current_stage > 0:
            self.current_stage -= 1

    def viable(self):
        return self.current_stage == 0

    def cast(self):
        pass


@pytest.fixture
def drain():
    """Run one move through the real beat loop; return (beats, final stages).

    ``drain([_StubMove("Slash", 4)])`` builds a fresh encounter whose enemy
    cannot die or kill, so the only thing that ends the loop is the
    cooldown-drain guard under test.
    """

    def _drain(cooling_moves):
        player = Player()
        slime = Slime()
        slime.hp = slime.maxhp = 9999  # survives the whole drain
        slime.damage = 0  # ...and cannot end it by killing Jean
        engage(player, [slime])

        adapter = ApiCombatAdapter(player)
        adapter.initialize_combat([slime])
        player.known_moves = list(cooling_moves)
        player.current_move = None

        result = adapter._execute_move_inner(_StubMove("Active", stage=0))
        return len(result["beat_states"]), [m.current_stage for m in cooling_moves]

    return _drain


def test_all_cooldown_advances_until_one_ready(drain):
    """All moves cooling -> the loop keeps burning beats until one opens up."""
    moves = [_StubMove("Slash", stage=4), _StubMove("Shield Bash", stage=2)]

    beats, stages = drain(moves)

    # Shield Bash is the first to open, two beats in; Slash is left at 2.
    assert beats == 2
    assert stages == [2, 0]
    assert any(m.current_stage == 0 for m in moves)


def test_move_already_ready_stops_after_the_first_beat(drain):
    """With something already castable the loop must not drain further.

    One beat always resolves (the move that was just used has to advance); the
    guard's job is to stop *after* it rather than burning the whole 20-beat
    safety budget.
    """
    moves = [_StubMove("Attack", stage=0), _StubMove("Wait", stage=3)]

    beats, stages = drain(moves)

    assert beats == 1
    # Wait ticked once with everything else, and Attack was never cooling.
    assert stages == [0, 2]


def test_longer_cooldown_drains_fully(drain):
    """A lone move at stage 5 costs exactly 5 beats to become available."""
    moves = [_StubMove("Heavy Strike", stage=5)]

    beats, stages = drain(moves)

    assert beats == 5
    assert stages == [0]


def test_shortest_cooldown_wins(drain):
    """The loop exits on the *first* move to open, not the last."""
    moves = [_StubMove("Slash", stage=4), _StubMove("Quick Jab", stage=1)]

    beats, stages = drain(moves)

    assert beats == 1
    assert stages == [3, 0]


def test_no_known_moves_does_not_burn_the_safety_budget(drain):
    """The `not self.player.known_moves` guard: an empty move list must break
    immediately rather than spinning to the 20-beat cap."""
    beats, stages = drain([])

    assert beats == 1
    assert stages == []
