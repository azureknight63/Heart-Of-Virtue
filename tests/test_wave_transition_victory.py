"""Victory must not fire on a wave transition (issue #514).

The rock-rumbler ambush chain announces its next wave from a queued combat
event and only enrolls it a stage or two later, on a separate request. The beat
in between therefore has an empty ``combat_list`` while the fight is still very
much running, and the adapter used to read that as the end of the fight: it
awarded exp, wrote a ``combat_end_summary`` and streamed a terminal state, and
the player got a victory dialog mid-ambush. ``add_enemies_to_combat`` then
reinitialized the *same* fight (``reinit=True``), restoring ``in_combat`` and
leaving the victory summary behind, stale.

The fix is a signal from the engine: ``add_enemies_to_combat`` records that this
fight produces waves, so the next roster wipe that happens while a queued combat
event is holding the beat is recognised as a wave transition **before** the
terminal path is entered.

Everything here drives a real ``Player``, real ``NPC``s and a real
``ApiCombatAdapter`` — a mocked combatant cannot catch a regression in which
attribute the engine actually reads.
"""

import types

import pytest

import src.functions as functions
from src.api.combat_adapter import ApiCombatAdapter
from src.events import Event
from src.npc import Slime
from tests._combat_fixtures import engage, make_npc, make_player


class StagedWaveEvent(Event):
    """A queued combat event shaped like ``Ch01PostRumbler``.

    A real ``Event`` subclass, not a hand-rolled double: ``process_event_input``
    serializes it and calls ``process()`` on it, so a stub would exercise a
    different branch than the story events this fix exists for.

    Its first stage announces and asks for input; the wave itself is only
    enrolled once the player dismisses the dialog, on a later request. That gap
    is the whole of issue #514. This double never enrolls one — the tests that
    need a wave call ``add_enemies_to_combat`` themselves, so the two halves of
    the signal stay independently observable.
    """

    def __init__(self, player=None):
        super().__init__(
            name="StagedWave", player=player, tile=None, combat_effect=True
        )
        self.fired = False

    def check_combat_conditions(self):
        if not self.fired:
            self.fired = True
            self.needs_input = True

    def process(self, user_input=None):
        self.needs_input = False
        self.completed = True


def _wait_move(player):
    return next(m for m in player.known_moves if m.name == "Wait")


@pytest.fixture
def player():
    return make_player()


@pytest.fixture
def adapter(player):
    slime = make_npc(Slime, name="Test Slime", hp=20, maxhp=20)
    engage(player, [slime])
    adapter = ApiCombatAdapter(player)
    adapter.initialize_combat([slime])
    player._combat_adapter = adapter
    return adapter


def arm_event(adapter, event):
    """Wire ``event`` in as the adapter's combat-event callback."""

    def callback(_player):
        event.check_combat_conditions()
        if event.needs_input:
            return [{"name": "StagedWave", "needs_input": True}]
        return []

    adapter.on_event_callback = callback
    return event


def wipe_roster(player, exp=10):
    """Kill everything the player was fighting, with exp banked for the fight."""
    player.combat_list.clear()
    player.combat_exp["Sword"] = exp
    player.current_move = None


class TestWaveTransition:
    """A roster wipe on a beat a queued event is holding is not the end."""

    def test_victory_does_not_fire_on_a_wave_transition(self, adapter, player):
        player.combat_wave_pending = True
        arm_event(adapter, StagedWaveEvent())
        wipe_roster(player)

        adapter._execute_move(_wait_move(player))

        assert player.in_combat is True, "the fight was ended mid-ambush"
        assert player.combat_end_summary is None

    def test_exp_is_not_awarded_on_a_wave_transition(self, adapter, player):
        player.combat_wave_pending = True
        arm_event(adapter, StagedWaveEvent())
        wipe_roster(player, exp=10)

        adapter._execute_move(_wait_move(player))

        # _handle_victory banks and zeroes combat_exp; an unspent pool is the
        # proof it never ran. Exp awarded here could not be taken back — the
        # player would bank the ambush's first half twice.
        assert player.combat_exp["Sword"] == 10

    def test_the_terminal_stream_is_not_published_on_a_wave_transition(
        self, adapter, player
    ):
        player.combat_wave_pending = True
        arm_event(adapter, StagedWaveEvent())
        wipe_roster(player)
        streamed = []
        adapter._stream_combat_result = (
            lambda state, beats, ended=False: streamed.append(ended)
        )

        adapter._execute_move(_wait_move(player))

        assert True not in streamed, "streamed combat:ended in the middle of a fight"

    def test_the_pending_event_still_reaches_the_client(self, adapter, player):
        player.combat_wave_pending = True
        arm_event(adapter, StagedWaveEvent())
        wipe_roster(player)

        result = adapter._execute_move(_wait_move(player))

        # Suppressing victory must not swallow the announcement that explains
        # why the battlefield is empty.
        assert result.get("events_triggered")

    def test_the_wave_lands_in_the_same_fight_with_no_stale_summary(
        self, adapter, player
    ):
        combat_id_before = adapter.combat_id
        player.combat_wave_pending = True
        arm_event(adapter, StagedWaveEvent())
        wipe_roster(player)
        adapter._execute_move(_wait_move(player))
        beat_before = player.combat_beat

        functions.add_enemies_to_combat(
            player, [make_npc(Slime, name="Wave2", hp=20, maxhp=20)]
        )

        assert adapter.combat_id == combat_id_before
        assert player.combat_beat == beat_before, "the wave reset the beat"
        assert player.combat_end_summary is None
        assert [e.name for e in player.combat_list] == ["Wave2"]


class TestVictoryStillFires:
    """The deferral is narrow: everything else still ends the fight."""

    def test_victory_fires_when_no_event_is_holding_the_beat(self, adapter, player):
        player.combat_wave_pending = True
        wipe_roster(player)

        adapter._execute_move(_wait_move(player))

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"

    def test_victory_fires_before_any_wave_has_landed(self, adapter, player):
        # No add_enemies_to_combat has run in this fight, so a post-combat
        # event pending on the beat does not suppress victory — the frontend
        # needs combat_end_summary to know the fight ended.
        arm_event(adapter, StagedWaveEvent())
        wipe_roster(player)

        adapter._execute_move(_wait_move(player))

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"

    def test_the_signal_covers_exactly_one_transition(self, adapter, player):
        player.combat_wave_pending = True
        arm_event(adapter, StagedWaveEvent())
        wipe_roster(player)
        adapter._execute_move(_wait_move(player))
        assert player.in_combat is True

        # The event resolved without enrolling anything: the signal is spent,
        # so the next roster wipe ends the fight normally instead of hanging
        # the player in a combat with nothing left to fight.
        arm_event(adapter, StagedWaveEvent())
        wipe_roster(player)
        adapter._execute_move(_wait_move(player))

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"

    def test_ending_the_fight_clears_the_signal(self, adapter, player):
        player.combat_wave_pending = True
        wipe_roster(player)

        adapter._execute_move(_wait_move(player))

        assert player.combat_wave_pending is False


class TestAddEnemiesToCombatSignalsContinuation:
    """``add_enemies_to_combat`` is where the signal comes from."""

    def test_enrolling_a_wave_marks_the_fight_as_continuing(self, adapter, player):
        assert player.combat_wave_pending is False

        functions.add_enemies_to_combat(
            player, [make_npc(Slime, name="Wave2", hp=20, maxhp=20)]
        )

        assert player.combat_wave_pending is True

    def test_enrolling_nothing_does_not_mark_a_wave(self, adapter, player):
        # A call that adds no one buys no deferral: the next roster wipe would
        # otherwise skip a victory the player has earned.
        functions.add_enemies_to_combat(player, [])

        assert player.combat_wave_pending is False

    def test_a_reinit_clears_a_stale_end_of_combat_summary(self, adapter, player):
        player.combat_end_summary = {"status": "victory", "message": "Victory!"}

        adapter.initialize_combat([make_npc(Slime, name="Wave2")], reinit=True)

        assert player.combat_end_summary is None

    def test_a_new_fight_starts_with_no_wave_outstanding(self, adapter, player):
        player.combat_wave_pending = True

        adapter.initialize_combat(list(player.combat_list))

        assert player.combat_wave_pending is False


class TestDeferredVictoryIsSettledWhenTheEventResolves:
    """A deferral is never allowed to strand the player."""

    def test_settle_victory_ends_the_fight_and_publishes_the_terminal_stream(
        self, adapter, player
    ):
        # Both halves or neither: victory state the client is never told to end
        # on leaves the battlefield rendered over a finished fight.
        streamed = []
        adapter._stream_combat_result = (
            lambda state, beats, ended=False: streamed.append(ended)
        )
        player.combat_list.clear()

        terminal_state = adapter.settle_victory()

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"
        assert streamed == [True]
        assert terminal_state["combat_active"] is False

    def test_an_event_that_resolves_without_a_wave_settles_the_victory(
        self, adapter, player
    ):
        from src.api.services.game_service import GameService

        player.combat_wave_pending = True
        event = arm_event(adapter, StagedWaveEvent())
        wipe_roster(player)
        adapter._execute_move(_wait_move(player))
        assert player.in_combat is True, "precondition: victory was deferred"

        # The player dismisses the dialog; the event's process() completes it
        # without enrolling a wave after all.
        player.universe = types.SimpleNamespace(get_tile=lambda x, y: None)
        session_data = {
            "pending_events": {
                "evt-1": {"event": event, "event_data": {"needs_input": True}}
            }
        }

        GameService().process_event_input(player, "evt-1", "continue", session_data)

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"
