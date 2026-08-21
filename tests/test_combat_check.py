"""Behavioural tests for ``src.functions.check_for_combat``.

This file used to be a script: it built three hand-rolled mock classes at
import time, called ``check_for_combat`` once, and ``print``ed the result.
pytest collected zero tests from it, so every branch of the aggro/awareness
roll below was completely unguarded -- the function could have returned an
empty list unconditionally and the suite would have stayed green.

The roll is RNG-driven, so each test that depends on it pins ``random.randint``
to an exact value rather than asserting a range. Tests that do not care about
the roll's value force it low enough to always trip the awareness check.
"""

from types import SimpleNamespace
from unittest.mock import patch

from src.functions import check_for_combat
from src.npc import NPC


def make_npc(name="Enemy", aggro=True, friend=False, awareness=10):
    npc = NPC(
        name=name,
        description=f"{name} lurks here.",
        damage=5,
        aggro=aggro,
        exp_award=10,
        awareness=awareness,
        friend=friend,
    )
    npc.in_combat = False
    return npc


def make_walker(npcs=(), finesse=10, known_moves=(), game_config=None):
    """A minimal stand-in for whoever walks into the room.

    ``check_for_combat`` reads exactly four things off the walker
    (``game_config``, ``current_room.npcs_here``, ``finesse``,
    ``known_moves``), so a namespace pins that surface precisely -- a
    ``MagicMock`` would answer any attribute and hide a rename.
    """
    return SimpleNamespace(
        finesse=finesse,
        known_moves=list(known_moves),
        game_config=game_config,
        current_room=SimpleNamespace(npcs_here=list(npcs)),
    )


def roll(value):
    """Force the finesse check to land on ``value`` exactly."""
    return patch("src.functions.random.randint", return_value=value)


class TestEngagement:
    def test_aggro_npc_below_awareness_is_engaged(self):
        enemy = make_npc(awareness=10)
        player = make_walker([enemy])

        with roll(5):
            result = check_for_combat(player)

        assert result == [enemy]

    def test_engaged_npc_is_flagged_in_combat(self):
        enemy = make_npc(awareness=10)
        player = make_walker([enemy])

        with roll(5):
            check_for_combat(player)

        assert enemy.in_combat is True

    def test_roll_exactly_equal_to_awareness_still_engages(self):
        # The comparison is `finesse_check <= awareness`, so the boundary
        # belongs to the enemy. Flipping it to `<` would silently make every
        # perfectly-matched sneak succeed.
        enemy = make_npc(awareness=10)
        player = make_walker([enemy])

        with roll(10):
            result = check_for_combat(player)

        assert result == [enemy]

    def test_roll_one_above_awareness_sneaks_past(self):
        enemy = make_npc(awareness=10)
        player = make_walker([enemy])

        with roll(11):
            result = check_for_combat(player)

        assert result == []
        assert enemy.in_combat is False


class TestNonCombatants:
    def test_friendly_npc_is_never_engaged(self):
        ally = make_npc(name="Gorran", friend=True, awareness=10)
        player = make_walker([ally])

        with roll(0):
            result = check_for_combat(player)

        assert result == []
        assert ally.in_combat is False

    def test_passive_npc_is_never_engaged(self):
        critter = make_npc(name="Critter", aggro=False, awareness=10)
        player = make_walker([critter])

        with roll(0):
            result = check_for_combat(player)

        assert result == []
        assert critter.in_combat is False

    def test_empty_room_returns_empty_list(self):
        assert check_for_combat(make_walker([])) == []

    def test_room_without_npcs_here_returns_empty_list(self):
        player = SimpleNamespace(
            finesse=10, known_moves=[], game_config=None, current_room=None
        )

        assert check_for_combat(player) == []


class TestAlliesJoinTheAlarm:
    def test_other_aggro_npcs_join_the_fight(self):
        alerted = make_npc(name="Sentry", awareness=10)
        bystander = make_npc(name="Brute", awareness=0)
        player = make_walker([alerted, bystander])

        with roll(5):
            result = check_for_combat(player)

        # Brute's own awareness of 0 would never have caught the player, but
        # the alarm drags it in anyway.
        assert result == [alerted, bystander]
        assert bystander.in_combat is True

    def test_friendly_and_passive_npcs_do_not_join_the_alarm(self):
        alerted = make_npc(name="Sentry", awareness=10)
        ally = make_npc(name="Gorran", friend=True, awareness=0)
        critter = make_npc(name="Critter", aggro=False, awareness=0)
        player = make_walker([alerted, ally, critter])

        with roll(5):
            result = check_for_combat(player)

        assert result == [alerted]
        assert ally.in_combat is False
        assert critter.in_combat is False

    def test_scanning_stops_after_the_first_alarm(self):
        # Two independently-alerted sentries must not each drag in the whole
        # room; the loop breaks after the first, so the second appears exactly
        # once (as a joiner) rather than twice.
        first = make_npc(name="First", awareness=10)
        second = make_npc(name="Second", awareness=10)
        player = make_walker([first, second])

        with roll(5):
            result = check_for_combat(player)

        assert result == [first, second]
        assert result.count(second) == 1


QUIET_MOVEMENT = [SimpleNamespace(name="Quiet Movement")]


class TestQuietMovement:
    """The passive scales the roll by 1.2, and engagement is
    ``finesse_check <= awareness`` -- so a *higher* roll sneaks past."""

    def test_the_same_roll_sneaks_past_with_quiet_movement_but_not_without(self):
        # Roll 9 against awareness 9: 9 <= 9, so an unaided Jean is spotted.
        loud_enemy = make_npc(awareness=9)
        with roll(9):
            assert check_for_combat(make_walker([loud_enemy])) == [loud_enemy]

        # With the passive the same roll becomes int(9 * 1.2) == 10, which
        # clears awareness 9 and slips by.
        quiet_enemy = make_npc(awareness=9)
        with roll(9):
            result = check_for_combat(
                make_walker([quiet_enemy], known_moves=QUIET_MOVEMENT)
            )

        assert result == []
        assert quiet_enemy.in_combat is False

    def test_scaling_truncates_rather_than_rounding(self):
        # int(9 * 1.2) == 10 (not 11), so a 10-awareness sentry still catches
        # Jean. Rounding up here would hand the passive a free extra point.
        enemy = make_npc(awareness=10)
        player = make_walker([enemy], known_moves=QUIET_MOVEMENT)

        with roll(9):
            assert check_for_combat(player) == [enemy]

    def test_an_unrelated_known_move_does_not_grant_the_bonus(self):
        enemy = make_npc(awareness=9)
        player = make_walker(
            [enemy], known_moves=[SimpleNamespace(name="Power Strike")]
        )

        with roll(9):
            assert check_for_combat(player) == [enemy]


class TestSkipCombatFlag:
    def test_skip_combat_bypasses_engagement_entirely(self):
        enemy = make_npc(awareness=100)
        player = make_walker(
            [enemy], game_config=SimpleNamespace(skip_combat=True)
        )

        with roll(0):
            result = check_for_combat(player)

        assert result == []
        assert enemy.in_combat is False, "skip_combat must not flag NPCs in combat"

    def test_skip_combat_false_leaves_engagement_alone(self):
        enemy = make_npc(awareness=10)
        player = make_walker(
            [enemy], game_config=SimpleNamespace(skip_combat=False)
        )

        with roll(5):
            assert check_for_combat(player) == [enemy]


class TestFinesseRollRange:
    """The roll itself: ``randint(int(finesse*0.6), int(finesse*1.4))``."""

    def test_roll_bounds_derive_from_finesse(self):
        player = make_walker([make_npc()], finesse=10)

        with patch("src.functions.random.randint", return_value=5) as randint:
            check_for_combat(player)

        randint.assert_called_once_with(6, 14)

    def test_negative_finesse_bounds_are_swapped_not_left_inverted(self):
        # int(-10*0.6) == -6 and int(-10*1.4) == -14, i.e. low > high, which
        # randint rejects. The function swaps them rather than raising.
        player = make_walker([make_npc()], finesse=-10)

        with patch("src.functions.random.randint", return_value=-8) as randint:
            check_for_combat(player)

        randint.assert_called_once_with(-14, -6)

    def test_unusable_finesse_falls_back_to_a_zero_to_ten_roll(self):
        player = make_walker([make_npc()], finesse="not a number")

        with patch("src.functions.random.randint", return_value=5) as randint:
            check_for_combat(player)

        randint.assert_called_once_with(0, 10)
