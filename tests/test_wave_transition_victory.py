"""Victory must not fire on a wave transition (issue #514).

The rock-rumbler ambush chain announces its next wave from a queued combat
event and only enrolls it a stage or two later, on a separate request. The beat
in between therefore has an empty ``combat_list`` while the fight is still very
much running, and the adapter used to read that as the end of the fight: it
awarded exp, wrote a ``combat_end_summary`` and streamed a terminal state, and
the player got a victory dialog mid-ambush. ``add_enemies_to_combat`` then
reinitialized the *same* fight (``reinit=True``), restoring ``in_combat`` and
leaving the victory summary behind, stale.

The fix is a single signal from the engine, ``player.combat_wave_pending``, armed
through ``functions.signal_combat_wave_pending`` from two places so that ONE flag
with ONE consumption rule covers the whole chain:

* ``add_enemies_to_combat`` arms it once a wave has actually joined the roster --
  that is waves 2 and later.
* ``GameService.trigger_combat_events`` arms it as soon as a ``combat_effect``
  event passes ``check_combat_conditions`` asking for input -- that is the FIRST
  roster wipe, the one the issue was filed about, which no enrolment precedes.

Either way the roster wipe is recognised as a wave transition **before** the
terminal path is entered, so nothing has to be retracted afterwards.

Everything here drives a real ``Player``, real ``NPC``s and a real
``ApiCombatAdapter`` — a mocked combatant cannot catch a regression in which
attribute the engine actually reads.
"""

import types

import pytest

import src.functions as functions
from src.api.combat_adapter import ApiCombatAdapter
from src.api.services.game_service import GameService
from src.events import Event
from src.narration import narrate
from src.npc import Slime
from tests._combat_fixtures import engage, make_npc, make_player


def make_room(name="TestRoom"):
    """A minimal positioned room: enough for tile_identity and event removal."""
    return types.SimpleNamespace(
        events_here=[],
        npcs_here=[],
        items_here=[],
        objects_here=[],
        x=0,
        y=0,
        map={"name": name},
    )


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


class PostFightNarrationEvent(Event):
    """A queued combat event shaped like a genuine *post*-fight beat.

    It fires on the empty roster, narrates, and completes in one pass without
    ever asking for input — so it is not a chain holding the beat and must not
    buy the fight a victory deferral. ``Ch01PostRumbler2`` has this shape
    (``check_combat_conditions`` fires on the killing blow, ``process`` never
    sets ``needs_input``), which is why the arming predicate requires
    ``needs_input`` rather than "a combat_effect event fired".
    """

    def __init__(self, player=None, tile=None):
        # A real room, not None: Event.pass_conditions_to_process removes a
        # completed non-repeating event from its tile, and a tile-less double
        # would blow up there instead of exercising the path under test.
        super().__init__(
            name="PostFightNarration",
            player=player,
            tile=tile if tile is not None else make_room(),
            combat_effect=True,
        )
        self.fired = False

    def check_combat_conditions(self):
        if not self.fired and not self.player.combat_list:
            self.fired = True
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        narrate("The dust settles over the empty chamber.")
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
    """Wire ``event`` in as the adapter's combat-event callback.

    A hand-rolled stand-in for ``GameService.trigger_combat_events`` that keeps
    the unit tests below independent of the service layer. The end-to-end tests
    in :class:`TestTheFirstWipeOfAChainIsCoveredToo` wire the *real*
    ``trigger_combat_events`` instead, because the new arming site lives there
    and a hand-rolled callback would never reach it.

    ``event`` must expose a ``fired`` flag it sets when its gate passes: that is
    what stands in for the service layer's "did this event do anything" test.
    """

    event.player = adapter.player

    def callback(_player):
        event.check_combat_conditions()
        if event.fired:
            return [{"name": event.name, "needs_input": bool(event.needs_input)}]
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

    def test_victory_fires_for_an_event_that_does_not_hold_the_beat(
        self, adapter, player
    ):
        # A post-combat event that fires on the empty roster and completes
        # without asking for input is not a chain holding the beat: it narrates
        # over a fight that really is finished. Victory must still fire — the
        # frontend needs combat_end_summary to know combat ended.
        #
        # This test used to assert the opposite of the fix, under the name
        # test_victory_fires_before_any_wave_has_landed: it armed a *staged*
        # (needs_input) event on the first roster wipe and required victory to
        # fire anyway, which is precisely the bug issue #514 was filed about.
        # Only the half of its intent that is still true survives here.
        arm_event(adapter, PostFightNarrationEvent())
        wipe_roster(player)

        result = adapter._execute_move(_wait_move(player))

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"
        # The narration still reaches the client alongside the terminal state.
        assert result.get("events_triggered")

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


class FirstWaveChainEvent(Event):
    """A ``Ch01PostRumbler``-shaped chain event: announce first, enroll later.

    Stage 1 fires on ``not combat_list`` and asks for input; stage 2 runs on the
    player's dismissal, a separate request later, and only then enrolls the
    wave. Nothing has been enrolled into the fight before stage 1, so this is
    exactly the first-roster-wipe case ``add_enemies_to_combat``'s signal cannot
    reach.
    """

    def __init__(self, player=None, tile=None, wave=None):
        super().__init__(
            name="FirstWaveChain", player=player, tile=tile, combat_effect=True
        )
        self.wave = list(wave or [])
        self.input_type = "choice"
        self.input_options = [{"value": "continue", "label": "Continue"}]
        self._stage = 1

    def check_combat_conditions(self):
        if not self.completed and not self.player.combat_list:
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        if self._stage == 1:
            self.needs_input = True
            self.input_prompt = "The ground quivers as more creatures appear!"
            self.description = "Low rumbles vibrate through the stone floor!"
            self._stage = 2
            return
        # Stage 2: the player dismissed the announcement -- enroll the wave.
        if self.wave:
            functions.add_enemies_to_combat(self.player, self.wave)
        self.needs_input = False
        self.completed = True


def wire_real_callback(adapter, player, event, session_data=None):
    """Drive the adapter through the **real** ``trigger_combat_events``.

    The new arming site lives inside that method, so a hand-rolled callback (see
    :func:`arm_event`) cannot reach it -- these tests would pass against the
    unfixed engine if they used one.
    """
    if session_data is None:
        session_data = {"pending_events": {}}
    room = make_room()
    player.current_room = room
    player.universe = types.SimpleNamespace(get_tile=lambda x, y: room)
    event.player = player
    event.tile = room
    player.combat_events.append(event)
    service = GameService()
    adapter.on_event_callback = lambda p: service.trigger_combat_events(
        p, session_data=session_data
    )
    return session_data


class TestTheFirstWipeOfAChainIsCoveredToo:
    """The reported scenario: no wave has landed, and victory still must not fire.

    ``add_enemies_to_combat`` can only speak for a fight that has *already*
    produced a wave, so on its own it protected waves 2+ and left wave 1 -- the
    case issue #514 describes -- firing victory, banking exp and streaming a
    terminal state that the wave then landed on top of. These tests run the real
    ``GameService.trigger_combat_events``, because that is where the first wipe
    is now armed.
    """

    def test_the_first_roster_wipe_of_a_chain_does_not_fire_victory(
        self, adapter, player
    ):
        assert player.combat_wave_pending is False, "precondition: no wave has landed"
        wire_real_callback(
            adapter, player, FirstWaveChainEvent(wave=[make_npc(Slime, name="Wave1")])
        )
        wipe_roster(player, exp=10)
        streamed = []
        adapter._stream_combat_result = (
            lambda state, beats, ended=False: streamed.append(ended)
        )

        adapter._execute_move(_wait_move(player))

        assert player.in_combat is True, "the fight was ended before its first wave"
        assert player.combat_end_summary is None
        # Exp banked here could not be taken back: the player would bank the
        # ambush's opening half twice.
        assert player.combat_exp["Sword"] == 10
        assert True not in streamed, "streamed combat:ended in the middle of a fight"

    def test_the_announcement_still_reaches_the_client(self, adapter, player):
        wire_real_callback(adapter, player, FirstWaveChainEvent())
        wipe_roster(player)

        result = adapter._execute_move(_wait_move(player))

        # Deferring victory must not swallow the dialog that explains why the
        # battlefield is empty -- that would soft-lock the player.
        assert result.get("events_triggered")

    def test_the_first_wave_lands_in_the_same_fight(self, adapter, player):
        combat_id_before = adapter.combat_id
        event = FirstWaveChainEvent(wave=[make_npc(Slime, name="Wave1", hp=20)])
        session_data = wire_real_callback(adapter, player, event)
        wipe_roster(player, exp=10)
        streamed = []
        adapter._stream_combat_result = (
            lambda state, beats, ended=False: streamed.append(ended)
        )
        adapter._execute_move(_wait_move(player))
        beat_before = player.combat_beat
        log_before = list(player.combat_log)

        # The player dismisses the announcement; stage 2 enrolls the wave.
        GameService().process_event_input(
            player, event.api_event_id, "continue", session_data
        )

        assert player.in_combat is True
        assert adapter.combat_id == combat_id_before, "the wave started a new fight"
        assert player.combat_beat == beat_before, "the wave reset the beat"
        assert player.combat_end_summary is None
        assert [e.name for e in player.combat_list] == ["Wave1"]
        assert player.combat_log[: len(log_before)] == log_before, "the log was wiped"
        # The reinit tidies combat_end_summary away afterwards, so the summary
        # assertion above passes with or without the fix. These two do not: exp
        # banked and a combat:ended already on the wire cannot be retracted, and
        # they are what the player actually saw in issue #514.
        assert player.combat_exp["Sword"] == 10, "the fight's exp was banked mid-ambush"
        assert True not in streamed, "streamed combat:ended before the wave landed"

    def test_the_signal_is_consumed_by_the_transition_it_covers(self, adapter, player):
        wire_real_callback(adapter, player, FirstWaveChainEvent())
        wipe_roster(player)

        adapter._execute_move(_wait_move(player))

        # One arming, one deferral. A signal left standing is how a fight gets
        # stranded with nothing to fight (cf. issue #506's uncleared
        # player.combat_events).
        assert player.combat_wave_pending is False

    def test_an_event_that_never_asks_for_input_does_not_arm_the_signal(
        self, adapter, player
    ):
        # Ch01PostRumbler2's shape: it fires on the killing blow and repopulates
        # inline, so it needs no deferral. needs_input is the conjunct that
        # excludes it -- without it the predicate would suppress victory for
        # every combat_effect event that ever fires on an empty roster.
        wire_real_callback(adapter, player, PostFightNarrationEvent())
        wipe_roster(player)

        adapter._execute_move(_wait_move(player))

        assert player.combat_wave_pending is False
        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"


class TestTheWiderPredicateCannotStrandAFight:
    """The one regression a wider arming predicate introduces, pinned down.

    Arming on ``needs_input`` rather than on enrolment means a future
    ``combat_effect`` event could arm the signal and then resolve without ever
    calling ``add_enemies_to_combat``. Nothing in the adapter would end that
    fight: the deferral is bounded only by ``settle_victory``. These tests hold
    both of its call sites -- the event-resolution path and the status poll --
    to that job.
    """

    def test_a_chain_event_that_arms_and_never_enrolls_still_ends_the_fight(
        self, adapter, player
    ):
        # No wave: stage 2 completes the event with an empty roster.
        event = FirstWaveChainEvent(wave=[])
        session_data = wire_real_callback(adapter, player, event)
        wipe_roster(player)
        adapter._execute_move(_wait_move(player))
        assert player.in_combat is True, "precondition: victory was deferred"
        assert player.combat_wave_pending is False

        GameService().process_event_input(
            player, event.api_event_id, "continue", session_data
        )

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"

    def test_the_status_poll_settles_a_deferral_left_by_a_vanished_event(
        self, adapter, player
    ):
        event = FirstWaveChainEvent(wave=[])
        wire_real_callback(adapter, player, event)
        wipe_roster(player)
        adapter._execute_move(_wait_move(player))
        assert player.in_combat is True, "precondition: victory was deferred"

        # Now reach the *other* backstop. get_combat_status only resumes a
        # fight that has no adapter turn outstanding, which a deferral normally
        # does have — so this is the rebuilt-adapter shape (server restart or
        # session rehydrate drops combat_adapter_state's awaiting_input) with
        # the event no longer around to resolve itself. It is a guard on
        # settle_victory's second call site, not a second reproduction of the
        # reported bug.
        adapter.awaiting_input = False
        player.combat_events.clear()
        GameService().get_combat_status(player, session_data={"pending_events": {}})

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"


class TestAnAbandonedDeferralIsRescuedByThePoll:
    """A deferral the player walks away from (issue #519).

    ``process_event_input`` is the only backstop that can reach a live
    deferral: the poll's resume block is gated on ``not awaiting_input``, and a
    deferral leaves ``awaiting_input`` True because the dialog holding the beat
    has not been dismissed. In normal play the dialog is always resolved through
    that path, so the gap never shows. A session dropped mid-dialog -- browser
    closed, container recycled -- resolves nothing: the pending event is gone
    from the store while ``in_combat`` and ``awaiting_input`` ride back in on
    the pickled player, and the fight is stranded with an empty battlefield and
    nothing to dismiss.

    The rescue keys on the deferral itself (``victory_deferred``), the empty
    roster, and an empty pending-event store. The resume gate below it is
    untouched, so the interrupted-move resume of issue #344 cannot be caught by
    the widening.
    """

    def _defer(self, adapter, player, wave=None):
        """Drive a real chain event to the deferred beat and return the session."""
        event = FirstWaveChainEvent(wave=wave or [])
        session_data = wire_real_callback(adapter, player, event)
        wipe_roster(player)
        adapter._execute_move(_wait_move(player))
        assert player.in_combat is True, "precondition: victory was deferred"
        assert adapter.victory_deferred is True, "precondition: deferral recorded"
        assert (
            adapter.awaiting_input is True
        ), "precondition: the dialog still holds the beat"
        assert session_data["pending_events"], "precondition: the dialog is stored"
        return event, session_data

    def test_the_poll_settles_a_deferral_whose_event_was_abandoned(
        self, adapter, player
    ):
        self._defer(adapter, player)

        # The player never dismisses the dialog. The rehydrated session has no
        # pending event left to resolve, so nothing but the poll can end this.
        player.combat_events.clear()
        GameService().get_combat_status(player, session_data={"pending_events": {}})

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"
        assert adapter.victory_deferred is False

    def test_the_rescue_publishes_the_terminal_stream(self, adapter, player):
        self._defer(adapter, player)
        player.combat_events.clear()
        streamed = []
        adapter._stream_combat_result = (
            lambda state, beats, ended=False: streamed.append(ended)
        )

        GameService().get_combat_status(player, session_data={"pending_events": {}})

        # Both halves or neither: a victory the client is never told to end on
        # leaves the battlefield rendered over a finished fight.
        assert streamed == [True]

    def test_the_poll_leaves_a_deferral_that_still_has_its_dialog(
        self, adapter, player
    ):
        # The ordinary mid-ambush poll: the announcement is still pending, the
        # wave has not arrived. Ending the fight here is the very bug #514
        # fixed, so the rescue must require an empty pending-event store.
        _event, session_data = self._defer(
            adapter, player, wave=[make_npc(Slime, name="Wave1", hp=20)]
        )

        GameService().get_combat_status(player, session_data=session_data)

        assert player.in_combat is True, "the poll ended a fight mid-ambush"
        assert player.combat_end_summary is None
        assert adapter.victory_deferred is True

    def test_a_landed_wave_clears_the_deferral(self, adapter, player):
        event, session_data = self._defer(
            adapter, player, wave=[make_npc(Slime, name="Wave1", hp=20)]
        )

        GameService().process_event_input(
            player, event.api_event_id, "continue", session_data
        )

        # The reinit that carries the wave resolves the deferral. A flag left
        # standing would let a later empty-roster poll settle a fight that is
        # merely between waves.
        assert player.in_combat is True
        assert adapter.victory_deferred is False

    def test_a_caller_without_the_session_store_must_not_settle(
        self, adapter, player
    ):
        """No store is "I cannot see", not "there is nothing" (review catch).

        ``GameService.get_combat_state`` calls ``get_combat_status(player)`` with
        no ``session_data`` at all. Reading that absence as an empty
        pending-event store would end a fight whose announcement dialog is alive
        and whose wave has not landed -- issue #514, reintroduced through the
        very backstop meant to bound it. The rescue must decline to act when it
        cannot check.
        """
        self._defer(adapter, player, wave=[make_npc(Slime, name="Wave1", hp=20)])

        GameService().get_combat_status(player, session_data=None)

        assert player.in_combat is True, (
            "the poll ended a fight it could not see the pending events of"
        )
        assert player.combat_end_summary is None
        assert adapter.victory_deferred is True

    def test_the_interrupted_move_resume_is_untouched(self, adapter, player):
        # Issue #344's path: awaiting_input False with a live roster and a move
        # left mid-execution. The rescue is a separate branch gated on
        # awaiting_input True, so it cannot reach this even with a deferral flag
        # standing. NEGATIVE CONTROL -- this passes with or without the rescue.
        adapter.awaiting_input = False
        adapter.victory_deferred = True
        move = _wait_move(player)
        player.current_move = move
        resumed = []
        adapter._execute_move = lambda m, **kw: (resumed.append(m), {"resumed": True})[
            1
        ]

        result = GameService().get_combat_status(
            player, session_data={"pending_events": {}}
        )

        assert resumed == [move]
        assert result == {"resumed": True}
