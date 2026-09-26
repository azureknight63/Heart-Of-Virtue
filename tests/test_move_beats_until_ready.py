"""``Move.beats_until_ready`` must agree with the real beat loop (#700).

The Tactical Advisor needs "if Jean casts this now, how many beats until he is
asked again" to stop recommending a move that carries him past the only beat a
Dodge could still meet a telegraphed surge. Every expectation here is MEASURED
by casting the real move on a real Player and driving the engine's own
``advance`` loop the way ``ApiCombatAdapter`` does (every known move advances
each beat; control returns once ``current_move`` clears) -- never a hand table.
"""

import random

import pytest

import src.states as states
from src.items import Shortsword
from src.moves import CleaveInstinct
from src.npc._enemies import Slime
from src.player import Player

# Generous ceiling: the longest stock cast (Dodge) frees Jean in 10 beats.
_BEAT_CEILING = 60


def _jean_in_a_fight(weapon=None, distance=3):
    player = Player()
    player.in_combat = True
    if weapon is not None:
        player.eq_weapon = weapon
        player.combat_exp.setdefault(weapon.subtype, 0)
        for m in player.known_moves:
            m.evaluate()
    enemy = Slime()
    player.combat_list = [enemy]
    player.combat_list_allies = [player]
    player.combat_proximity = {enemy: distance}
    enemy.combat_proximity = {player: distance}
    return player, enemy


def _move(player, name, target):
    move = next(m for m in player.known_moves if m.name == name)
    move.target = target
    return move


def _beats_until_asked_again(player, move):
    """Cast ``move`` and count the beats the adapter's loop would run.

    Mirrors ``ApiCombatAdapter._execute_move_inner``: an instant move resolves
    every stage with no beat passing; anything else runs whole beats (all
    known moves advance) until Jean's ``current_move`` clears.
    """
    player.current_move = move
    move.cast()
    if move.instant:
        for _ in range(_BEAT_CEILING):
            move.advance(player)
            if player.current_move is None:
                return 0
        raise AssertionError(f"instant {move.name} never released Jean")
    for beat in range(1, _BEAT_CEILING):
        for m in player.known_moves:
            m.advance(player)
        if player.current_move is None:
            return beat
    raise AssertionError(f"{move.name} never released Jean")


@pytest.mark.parametrize(
    "name, weapon, duration",
    [
        ("Dodge", None, None),
        ("Withdraw", None, None),
        ("Advance", None, None),
        ("Attack", None, None),
        ("Attack", Shortsword, None),
        ("Rest", None, None),
        ("Use Item", None, None),
        ("Swap Weapon", None, None),
        ("Crusader's Oath", None, None),
        ("Check", None, None),
        # Wait's stage beats are all zero until execute() reads `duration`.
        ("Wait", None, None),
        ("Wait", None, 3),
        ("Wait", None, 1),
        ("Wait", None, 9),
    ],
)
def test_prediction_matches_the_real_beat_loop(name, weapon, duration):
    random.seed(700)
    player, enemy = _jean_in_a_fight(weapon() if weapon else None)
    move = _move(player, name, enemy)
    if duration is not None:
        move.duration = duration

    predicted = move.beats_until_ready()
    actual = _beats_until_asked_again(player, move)

    assert predicted == actual, (
        f"{name} (stage_beat={move.stage_beat}): beats_until_ready() said "
        f"{predicted} but the beat loop freed Jean after {actual}"
    )


def test_check_is_instant():
    player, enemy = _jean_in_a_fight()
    assert _move(player, "Check", enemy).beats_until_ready() == 0


def test_staggered_prep_penalty_is_counted_and_not_consumed():
    random.seed(700)
    player, enemy = _jean_in_a_fight()
    stagger = states.Staggered(player)
    player.states.append(stagger)
    move = _move(player, "Dodge", enemy)
    unstaggered = _move(Player(), "Dodge", None).beats_until_ready()

    predicted = move.beats_until_ready()

    assert stagger.penalty_consumed is False, "the query consumed the stagger"
    assert predicted == unstaggered + stagger.prep_penalty
    assert predicted == _beats_until_asked_again(player, move)
    assert stagger.penalty_consumed is True  # ...and cast() still does


def test_cleave_instinct_prep_is_counted_and_not_consumed():
    random.seed(700)
    player, enemy = _jean_in_a_fight()
    player.known_moves.append(CleaveInstinct(player))
    player._cleave_instinct_pending = True
    move = _move(player, "Crusader's Oath", enemy)  # prep 2 -> 1

    predicted = move.beats_until_ready()

    assert player._cleave_instinct_pending is True, "the query consumed the pending cleave"
    assert predicted == _beats_until_asked_again(player, move)
    assert player._cleave_instinct_pending is False  # ...and cast() still does


def test_none_while_the_move_is_in_progress():
    player, enemy = _jean_in_a_fight()
    move = _move(player, "Dodge", enemy)
    player.current_move = move
    move.cast()
    assert move.beats_until_ready() is None
    for m in player.known_moves:
        m.advance(player)
    assert move.beats_until_ready() is None


@pytest.mark.parametrize("stage", [1, 2, 3])
def test_none_outside_rest(stage):
    player, enemy = _jean_in_a_fight()
    move = _move(player, "Dodge", enemy)
    move.current_stage = stage
    move.beats_left = 2
    assert move.beats_until_ready() is None


def test_none_for_a_fractional_stage():
    """The engine strands a fractional stage (see standard_evaluate_attack);
    there is no honest beat count to publish for it."""
    player, enemy = _jean_in_a_fight()
    move = _move(player, "Dodge", enemy)
    move.stage_beat = [1, 1.5, 5, 2]
    assert move.beats_until_ready() is None


def test_a_whole_float_stage_counts_like_the_integer():
    """3.0 drains to exactly 0.0, so the engine does finish it."""
    random.seed(700)
    player, enemy = _jean_in_a_fight()
    move = _move(player, "Dodge", enemy)
    move.stage_beat = [1.0, 1.0, 5.0, 2]
    predicted = move.beats_until_ready()
    assert predicted == _beats_until_asked_again(player, move)


@pytest.mark.parametrize("prep", ["1", None, [1], {"beats": 1}])
@pytest.mark.parametrize("name", ["Dodge", "Wait"])
def test_none_for_a_non_numeric_prep_stage(name, prep):
    """A degraded stage_beat must read "no opinion", not raise.

    ``_effective_prep`` compares ``prep > 0`` before ``_beats_to_free`` can
    reject the value, so a non-numeric prep raised TypeError out of the move
    listing -- a 500 on every combat poll offering the move -- where every
    other unfinishable stage answers None.
    """
    player, enemy = _jean_in_a_fight()
    move = _move(player, name, enemy)
    move.stage_beat = [prep] + list(move.stage_beat[1:])
    assert move.beats_until_ready() is None
