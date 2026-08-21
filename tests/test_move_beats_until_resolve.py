"""``Move.beats_until_resolve`` must agree with what ``advance`` actually does.

The battlefield countdown badge renders this number, and it previously
rendered ``beats_left`` — which is beats left in the *current stage*, so a
PowerStrike telegraphing "3" actually landed 9 beats later. Telling a player
they have 3 beats to block when they have 9 mis-times every reaction, so the
prediction is pinned against the real stage machine here rather than against
a hand-computed constant.
"""

import pytest

from src.moves import Check, PowerStrike, Wait
from src.npc._enemies import Slime
from src.player import Player


def _combat_pair():
    player = Player()
    player.combat_exp = {}
    enemy = Slime()
    player.combat_list = [enemy]
    player.combat_list_allies = [player]
    player.combat_proximity = {enemy: 1}
    return player, enemy


def _beats_until_execute(move_cls, stage, beats_left):
    """Drive the real ``advance`` loop and report when ``execute`` fires."""
    player, enemy = _combat_pair()
    move = move_cls(player)
    move.target = enemy
    player.current_move = move
    move.current_stage = stage
    move.beats_left = beats_left

    predicted = move.beats_until_resolve()

    fired = {}
    move.execute = lambda *a, **k: fired.setdefault("beat", beat)
    for beat in range(1, 60):
        move.advance(player)
        if fired:
            break
    return predicted, fired.get("beat")


@pytest.mark.parametrize(
    "move_cls, stage, beats_left",
    [
        (PowerStrike, 0, 3),   # the case that exposed the bug
        (PowerStrike, 0, 0),   # prep already drained
        (PowerStrike, 1, 4),   # mid-execute
        (PowerStrike, 1, 0),   # lands on the very next beat
        # stage_beat[1] == 0: advance's `while beats_left == 0` loop runs prep
        # and execute in the SAME beat, so a naive "+2" is wrong for these.
        (Wait, 0, 2),
        (Check, 0, 1),
    ],
)
def test_prediction_matches_the_real_advance_loop(move_cls, stage, beats_left):
    predicted, actual = _beats_until_execute(move_cls, stage, beats_left)
    assert actual is not None, "fixture never reached execute()"
    assert predicted == actual, (
        f"{move_cls.__name__} at stage {stage} with beats_left={beats_left}: "
        f"beats_until_resolve() says {predicted} but execute() fired on beat {actual}"
    )


def test_prediction_exceeds_beats_left_for_a_windup_move():
    """Guards the specific regression: the two must not be interchangeable."""
    player, _ = _combat_pair()
    move = PowerStrike(player)
    move.current_stage = 0
    move.beats_left = 3
    assert move.beats_until_resolve() > move.beats_left


@pytest.mark.parametrize("stage", [2, 3])
def test_no_countdown_once_the_move_has_already_resolved(stage):
    player, _ = _combat_pair()
    move = PowerStrike(player)
    move.current_stage = stage
    move.beats_left = 4
    assert move.beats_until_resolve() is None
