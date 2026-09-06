"""One victory tail, one defeat tail, and names that say which is which (#520).

The adapter had three end-of-fight entry points at three abstraction levels
wearing two interchangeable-looking names:

===================  =================  ======================  =========
method               exp + summary      streams ``combat:ended``  returns
===================  =================  ======================  =========
``_handle_victory``  yes                **no**                  ``None``
``_handle_defeat``   yes                yes                     result
``settle_victory``   yes (delegates)    yes                     result
===================  =================  ======================  =========

``_handle_victory``/``_handle_defeat`` read as a pair. They were not one: the
victory half publishes nothing, so any new exit path that reached for the
name-alike would ship a victory the client is never told to end on, leaving the
battlefield rendered over a finished fight with no error anywhere.

The fix is a rename PLUS a de-duplication, and both halves need holding down:

* ``settle_defeat`` mirrors ``settle_victory`` in name and in
  ``(beat_states) -> result`` shape, and ``_handle_victory`` is private and
  named unlike either, so there is no longer a plausible-looking wrong choice.
* the move loop's inline ``_handle_victory()`` + ``get_combat_state()`` +
  ``_stream_combat_result(..., ended=True)`` triple is gone, folded into
  ``settle_victory(beat_states)``. It differed from the helper only by the
  beats it injected and by restoring ``events_triggered`` — the restore is the
  part that is easy to lose in a fold, so it is asserted directly.

These drive a real ``Player``, real ``NPC``s and a real ``ApiCombatAdapter``:
the property under test is "exactly one terminal stream per fight ending", and
a mocked adapter would only ever prove that the mock was called.
"""

import inspect
import types

import pytest

from src.api.combat_adapter import ApiCombatAdapter
from src.npc import Slime
from tests._ast_helpers import called_names as _method_calls, source_calls
from tests._combat_fixtures import engage, make_npc, make_player

#: Every module that may reach an end-of-fight entry point. The adapter is not
#: enough on its own: three of settle_victory's four call sites live in
#: game_service, so a scan of ``vars(ApiCombatAdapter)`` alone would stay green
#: while a new exit path in the service called ``_handle_victory`` directly --
#: which is exactly the mistake issue #520 is about.
END_OF_FIGHT_MODULES = (
    "src/api/combat_adapter.py",
    "src/api/services/game_service.py",
    "src/api/routes/combat.py",
)


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


def record_streams(adapter):
    """Replace the stream publisher with a recorder of ``(beats, ended)``."""
    streamed = []

    def _record(state, beats, ended=False):
        streamed.append((list(beats), ended))

    adapter._stream_combat_result = _record
    return streamed


class TestExactlyOneTerminalStreamPerEnding:
    """A fight ends once, so ``combat:ended`` goes out once.

    Two streams mean the client is told twice, and the seq guard in
    ``_stream_combat_result`` only suppresses the second on a shared streamer —
    zero means the battlefield stays rendered over a finished fight forever.
    Both are invisible to any test that only checks ``in_combat``.
    """

    def test_the_move_loop_streams_the_victory_ending_exactly_once(
        self, adapter, player
    ):
        streamed = record_streams(adapter)
        player.combat_list.clear()

        adapter._execute_move(_wait_move(player))

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "victory"
        assert [ended for _beats, ended in streamed] == [True], (
            "the victory ending must publish one terminal stream and no "
            "non-terminal one alongside it"
        )

    def test_the_move_loop_streams_the_defeat_ending_exactly_once(
        self, adapter, player
    ):
        streamed = record_streams(adapter)
        player.hp = 0

        adapter._execute_move(_wait_move(player))

        assert player.in_combat is False
        assert player.combat_end_summary["status"] == "defeat"
        assert [ended for _beats, ended in streamed] == [True]

    def test_a_directly_settled_victory_streams_exactly_once(self, adapter, player):
        # The between-requests exits (status poll, event resolution) reach the
        # same tail without a move loop around it.
        streamed = record_streams(adapter)
        player.combat_list.clear()

        adapter.settle_victory()

        assert [ended for _beats, ended in streamed] == [True]


class TestTheFoldedTailKeptEverythingTheInlineCopyDid:
    """The move loop's inline triple is gone; nothing it did may be gone with it."""

    def test_the_victory_result_carries_the_beats_of_the_move_that_ended_it(
        self, adapter, player
    ):
        """The KILLING move's beats, not merely *a* list.

        ``settle_victory`` always sets the key (``[]`` when it is handed
        nothing), so "the key is present and is a list" is satisfied by a fold
        that forgot to pass ``beat_states`` through at all — which is precisely
        the regression the message claims to catch. Pinned instead to what the
        publisher was handed: the result and the stream carry the same,
        non-empty beats.
        """
        streamed = record_streams(adapter)
        player.combat_list.clear()

        result = adapter._execute_move(_wait_move(player))

        (published_beats, ended), = streamed
        assert ended is True
        assert published_beats, (
            "the killing move produced no beat snapshots at all, so this test "
            "can no longer tell a dropped beat_states from an empty one"
        )
        assert result["beat_states"] == published_beats, (
            "the folded tail dropped beat_states; the client replays the "
            "killing beat from this key"
        )

    def test_the_defeat_result_carries_the_beats_of_the_move_that_ended_it(
        self, adapter, player
    ):
        """The same pin on the defeat half — it folds the same tail."""
        streamed = record_streams(adapter)
        player.hp = 0

        result = adapter._execute_move(_wait_move(player))

        (published_beats, ended), = streamed
        assert ended is True
        assert published_beats
        assert result["beat_states"] == published_beats

    def test_the_beats_reach_the_stream_and_not_just_the_result(
        self, adapter, player
    ):
        streamed = record_streams(adapter)
        player.combat_list.clear()
        sentinel = [{"beat": 1, "sentinel": True}]

        adapter.settle_victory(sentinel)

        assert streamed == [(sentinel, True)], (
            "settle_victory must publish the beats it was given, not []"
        )

    def test_a_post_combat_event_survives_the_state_capture(self, adapter, player):
        """``get_combat_state`` CONSUMES ``events_triggered``; the tail restores it.

        A post-combat event queued on the killing beat is popped out of adapter
        state by the terminal ``get_combat_state()``. Without the restore it is
        gone for every later reader — the status poll that follows the move
        would report an empty ``events_triggered`` and the dialog would never
        be shown. This is the one behaviour the inline copy had that a careless
        fold into ``settle_victory`` would drop.
        """
        player.combat_list.clear()
        player.combat_adapter_state["events_triggered"] = [{"name": "AfterTheFight"}]

        result = adapter._execute_move(_wait_move(player))

        assert result.get("events_triggered") == [{"name": "AfterTheFight"}], (
            "the terminal result must carry the queued post-combat event"
        )
        assert player.combat_adapter_state.get("events_triggered") == [
            {"name": "AfterTheFight"}
        ], "the queued post-combat event was consumed and never restored"

    def test_the_restore_reaches_the_between_requests_exits_too(
        self, adapter, player
    ):
        """settle_victory's other callers discard its return value.

        Without the restore living inside the helper the event is dropped on
        the floor for all three of them.

        Asserted against the RETURNED state as well as the store: writing the
        literal key and then reading the same literal back would keep passing
        after a rename of the source key, since the test would be checking its
        own write rather than anything the adapter produced.
        """
        player.combat_list.clear()
        player.combat_adapter_state["events_triggered"] = [{"name": "AfterTheFight"}]

        state = adapter.settle_victory()

        assert state.get("events_triggered") == [{"name": "AfterTheFight"}], (
            "settle_victory's own result no longer carries the queued event"
        )
        assert player.combat_adapter_state.get("events_triggered") == state.get(
            "events_triggered"
        ), "the queued post-combat event was consumed and never restored"


class TestThereIsOnlyOneVictoryTail:
    """Structural: the move loop must not grow a second copy of the pair.

    The inline triple and ``settle_victory`` drifted apart once already — the
    move loop streamed the terminal state while the helper did not restore
    ``events_triggered``. Asserted on the call graph rather than on behaviour,
    because a re-inlined copy that happens to behave identically today is
    exactly the state this issue is about.
    """

    def test_the_move_loop_ends_a_victory_through_settle_victory(self):
        calls = _method_calls(ApiCombatAdapter._execute_move_inner)
        assert "settle_victory" in calls, (
            "_execute_move_inner no longer routes victory through settle_victory"
        )
        assert "_handle_victory" not in calls, (
            "_execute_move_inner calls the exp/summary half directly again — "
            "that is the inline second victory tail issue #520 removed"
        )

    def test_settle_victory_is_the_only_caller_of_the_exp_half_anywhere(self):
        """Scanned across every module that can end a fight, not just the class.

        Three of the four victory exits live in ``game_service``, so a scan of
        ``vars(ApiCombatAdapter)`` alone stays green while a new service-side
        exit calls ``adapter._handle_victory()`` — the exact mistake #520 is
        about, one file away from where the old scan was looking.
        """
        assert "_handle_victory" in _method_calls(ApiCombatAdapter.settle_victory)
        callers = {
            f"{module}::{func}"
            for module in END_OF_FIGHT_MODULES
            for func in source_calls(module, "_handle_victory")
            if func != "settle_victory"
        }
        assert callers == set(), (
            f"{sorted(callers)} call _handle_victory directly; it publishes no "
            "terminal stream, so every exit path must go through settle_victory"
        )

    def test_that_cross_module_scan_can_actually_see_the_other_modules(self):
        """Positive control — an empty result must not be able to mean 'no scan'."""
        assert source_calls(
            "src/api/services/game_service.py", "settle_victory"
        ), (
            "the cross-module scan finds no settle_victory caller in "
            "game_service, so its empty _handle_victory result proves nothing"
        )

    def test_the_move_loop_ends_a_defeat_through_settle_defeat(self):
        assert "settle_defeat" in _method_calls(
            ApiCombatAdapter._execute_move_inner
        ), "_execute_move_inner no longer routes defeat through settle_defeat"

    def test_the_walker_can_actually_find_calls(self):
        """Positive control for ``_method_calls`` — an empty set proves nothing."""

        def sample(self):
            self.alpha()
            beta()

        assert _method_calls(sample) == {"alpha", "beta"}


class TestTheSettlePairHasOneShape:
    """The two complete tails must stay interchangeable at the call site.

    The whole failure mode was choosing the wrong end-of-fight method. Matching
    names that take different arguments and return different things would put
    the trap straight back.
    """

    def test_both_settle_methods_take_beat_states_and_return_the_result(self):
        """FULL signatures, defaults included.

        Parameter names alone let the two drift where it matters most: the
        defeat half took ``beat_states`` as REQUIRED while the victory half
        defaulted it, so ``settle_defeat()`` raised ``TypeError`` at a call
        site where ``settle_victory()`` worked — for a pair whose whole job is
        to be interchangeable, and whose docstring called them exact mirrors.
        """
        victory = inspect.signature(ApiCombatAdapter.settle_victory)
        defeat = inspect.signature(ApiCombatAdapter.settle_defeat)
        assert (
            str(victory) == str(defeat) == "(self, beat_states=None) -> Dict[str, Any]"
        ), (
            f"settle_victory{victory} and settle_defeat{defeat} are no longer "
            "interchangeable at the call site"
        )

    def test_both_settle_methods_can_be_called_with_no_beats(self, adapter, player):
        """The signature check above, exercised. A default that is never
        called is a default that can be removed without anything failing."""
        record_streams(adapter)
        player.combat_list.clear()
        assert adapter.settle_victory()["combat_active"] is False

        fresh_player = make_player()
        slime = make_npc(Slime, name="Test Slime", hp=20, maxhp=20)
        engage(fresh_player, [slime])
        fresh = ApiCombatAdapter(fresh_player)
        fresh.initialize_combat([slime])
        fresh_player._combat_adapter = fresh
        record_streams(fresh)

        assert fresh.settle_defeat()["combat_active"] is False

    def test_the_incomplete_half_is_private_and_not_named_like_the_pair(self):
        # Every method whose name claims an end-of-fight outcome. The unrelated
        # ``_handle_*_selection`` input handlers are excluded by the outcome
        # words, not by an exclusion list that a new one could slip past.
        entry_points = {
            name
            for name, member in vars(ApiCombatAdapter).items()
            if inspect.isfunction(member)
            and ("victory" in name or "defeat" in name)
        }
        assert entry_points == {
            "settle_victory",
            "settle_defeat",
            "_handle_victory",
        }, (
            "an end-of-fight entry point was added or renamed; keep the "
            "complete tails as the settle_* pair and the incomplete half "
            "private and unlike them (issue #520)"
        )

    def test_both_settle_methods_return_a_terminal_state(self, adapter, player):
        record_streams(adapter)
        player.combat_list.clear()

        victory_state = adapter.settle_victory([])

        assert victory_state["combat_active"] is False

        # A fresh fight for the defeat half: the adapter above is spent.
        fresh_player = make_player()
        slime = make_npc(Slime, name="Test Slime", hp=20, maxhp=20)
        engage(fresh_player, [slime])
        fresh = ApiCombatAdapter(fresh_player)
        fresh.initialize_combat([slime])
        fresh_player._combat_adapter = fresh
        record_streams(fresh)

        defeat_state = fresh.settle_defeat([])

        assert defeat_state["combat_active"] is False
        assert fresh_player.combat_end_summary["status"] == "defeat"


def test_no_caller_anywhere_still_reaches_for_the_old_defeat_name():
    """``_handle_defeat`` is gone from the class AND unreferenced by any caller.

    ``not hasattr`` alone is a rename check, not a caller check: a service-side
    exit could still spell ``adapter._handle_defeat(beats)`` and fail only at
    runtime, on the defeat path, which no route test drives.
    """
    assert not hasattr(ApiCombatAdapter, "_handle_defeat")
    assert isinstance(
        inspect.getattr_static(ApiCombatAdapter, "settle_defeat"), types.FunctionType
    )
    stragglers = {
        f"{module}::{func}"
        for module in END_OF_FIGHT_MODULES
        for func in source_calls(module, "_handle_defeat")
    }
    assert stragglers == set(), (
        f"{sorted(stragglers)} still call the removed _handle_defeat name"
    )
