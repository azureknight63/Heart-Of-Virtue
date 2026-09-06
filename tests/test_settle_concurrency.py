"""Ending a fight is serialized and idempotent, however many callers arrive.

``settle_victory`` has four call sites and only ONE of them (the move loop in
``_execute_move_inner``) already holds ``_beat_lock``. The other three are in
``GameService``, two of them on the status poll the client hits every three
seconds:

* ``get_combat_status`` — "all enemies defeated after an event finished"
* ``get_combat_status`` — the issue #519 abandoned-deferral rescue
* ``process_event_input`` — a deferred wave transition that resolved without
  enrolling anything

``app.py`` builds SocketIO with ``async_mode="threading"``, so an in-flight
``POST /api/combat/move`` really does overlap the next scheduled
``GET /api/combat/status``: a poll thread and a move thread can be inside the
victory tail at the same time. Two consequences, both traced through the code
rather than guessed at:

* ``_handle_victory`` READS ``player.combat_exp`` and then ZEROES it, entry by
  entry, and writes ``combat_end_summary`` from what it read. A second pass
  reads the already-zeroed dict and rewrites the summary with
  ``exp_gained={}`` and ``level_ups=[]`` — the player silently loses the exp
  and level-up display for a fight they just won. Nothing raises.
* ``_teardown_combat_roster`` reassigns ``combat_list``/``combat_list_allies``,
  which a concurrent ``_execute_move_inner`` may be iterating.

``_terminal_event_emitted`` guards only the socket emit, not ``_handle_victory``,
so it was never protection against either.

The fix is both halves and they are not redundant: the lock makes the pass
atomic, and the ``in_combat`` early return makes a *later* call a no-op rather
than a second settlement.
"""

import threading

import pytest

from src.api.combat_adapter import ApiCombatAdapter
from src.npc import Slime
from tests._combat_fixtures import engage, make_npc, make_player


def build_adapter(exp=None):
    player = make_player()
    slime = make_npc(Slime, name="Test Slime", hp=20, maxhp=20)
    engage(player, [slime])
    adapter = ApiCombatAdapter(player)
    adapter.initialize_combat([slime])
    player._combat_adapter = adapter
    player.combat_exp = dict(exp or {"Unarmed": 40})
    player.combat_list.clear()
    return adapter, player


def record_streams(adapter):
    streamed = []

    def _record(state, beats, ended=False):
        streamed.append((list(beats), ended))

    adapter._stream_combat_result = _record
    return streamed


class TestTwoThreadsRacingTheVictoryTail:
    """A genuine race: two threads, one adapter, released together."""

    def test_the_exp_summary_survives_a_concurrent_second_settler(self):
        adapter, player = build_adapter({"Unarmed": 40, "Sword": 15})
        streamed = record_streams(adapter)

        # Widen the window the race needs without changing what is being
        # tested: the real gain_exp does file I/O-free arithmetic in
        # microseconds, so an unlocked second thread would usually — not
        # always — slip past it. Sleeping inside the exp loop makes "usually"
        # into "every time", and it sits INSIDE the critical section, so with
        # the lock in place it is exactly what the second thread has to wait
        # on.
        real_gain_exp = player.gain_exp
        exp_awarded = []

        def slow_gain_exp(amount, *args, **kwargs):
            exp_awarded.append(amount)
            threading.Event().wait(0.05)
            return real_gain_exp(amount, *args, **kwargs)

        player.gain_exp = slow_gain_exp

        start = threading.Barrier(2)
        results = {}
        errors = []

        def settle(tag):
            try:
                start.wait(timeout=5)
                results[tag] = adapter.settle_victory([])
            except Exception as exc:  # pragma: no cover - failure path
                errors.append((tag, exc))

        threads = [
            threading.Thread(target=settle, args=(tag,)) for tag in ("move", "poll")
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive(), "a settle_victory thread never returned"

        assert errors == [], f"settle_victory raised under contention: {errors}"

        summary = player.combat_end_summary
        assert summary["status"] == "victory"
        assert exp_awarded == [40, 15], (
            f"gain_exp was called {exp_awarded} — a second unserialized pass "
            "read combat_exp before the first had zeroed it and banked the "
            "same fight's exp twice"
        )
        assert summary["exp_gained"] == {"Unarmed": 40, "Sword": 15}, (
            "a second concurrent pass through the victory tail read the "
            "already-zeroed combat_exp and rewrote combat_end_summary with an "
            "empty exp_gained — the player loses the exp and level-up display "
            "for a fight they just won"
        )
        assert [ended for _beats, ended in streamed] == [True], (
            "the fight ended once, so exactly one terminal stream may go out"
        )
        for tag, state in results.items():
            assert state["combat_active"] is False, f"{tag} got a live-combat state"

    def test_the_roster_teardown_runs_once_per_fight(self):
        """``_teardown_combat_roster`` reassigns both rosters in place.

        A concurrent ``_execute_move_inner`` iterating ``combat_list`` while
        this runs is the ``RuntimeError``-into-500 half of the race; the
        second run is also what discards a second set of animation channels
        and re-purges combat events. Counted rather than inferred from the
        resulting roster, which happens to be idempotent and so cannot fail.
        """
        adapter, player = build_adapter()
        record_streams(adapter)
        calls = []
        real_teardown = adapter._teardown_combat_roster

        def counting_teardown():
            calls.append(1)
            return real_teardown()

        adapter._teardown_combat_roster = counting_teardown

        adapter.settle_victory([])
        adapter.settle_victory([])

        assert calls == [1], (
            f"the roster teardown ran {len(calls)} times for one fight; a "
            "concurrent move loop iterating combat_list sees it mutate "
            "underneath itself"
        )


class TestSettlingTwiceIsANoOp:
    """The deterministic half — no threads, same guarantee."""

    def test_a_second_victory_call_does_not_re_award_or_re_stream(self):
        adapter, player = build_adapter({"Unarmed": 40})
        streamed = record_streams(adapter)

        first = adapter.settle_victory([])
        summary_id = player.combat_end_summary["id"]
        exp_after_first = player.exp

        second = adapter.settle_victory([])

        assert player.combat_end_summary["id"] == summary_id, (
            "the second call minted a fresh combat_end_summary; the client "
            "keys the victory dialog on this id and would re-open it"
        )
        assert player.combat_end_summary["exp_gained"] == {"Unarmed": 40}
        assert player.exp == exp_after_first, "exp was awarded twice"
        assert [ended for _beats, ended in streamed] == [True]
        assert first["combat_active"] is False
        assert second["combat_active"] is False

    def test_a_second_defeat_call_does_not_re_log_or_re_stream(self):
        adapter, player = build_adapter()
        streamed = record_streams(adapter)
        player.hp = 0

        adapter.settle_defeat([])
        summary_id = player.combat_end_summary["id"]
        defeat_lines = sum(
            1
            for entry in player.combat_log
            if "defeated" in str(entry.get("message", "")).lower()
        )

        adapter.settle_defeat([])

        assert player.combat_end_summary["id"] == summary_id
        assert [ended for _beats, ended in streamed] == [True]
        assert (
            sum(
                1
                for entry in player.combat_log
                if "defeated" in str(entry.get("message", "")).lower()
            )
            == defeat_lines
        )

    def test_the_second_call_still_returns_the_queued_post_combat_event(self):
        """The early return is not a bare ``return None``.

        Its callers use the result: ``process_event_input`` reads
        ``battle_state`` off it and returns that to the client. A no-op that
        answered ``None`` would 500 there rather than settle anything.
        """
        adapter, player = build_adapter()
        record_streams(adapter)
        adapter.settle_victory([])
        player.combat_adapter_state["events_triggered"] = [{"name": "AfterTheFight"}]

        state = adapter.settle_victory([])

        assert state["combat_active"] is False
        assert state.get("events_triggered") == [{"name": "AfterTheFight"}]
        assert player.combat_adapter_state.get("events_triggered") == [
            {"name": "AfterTheFight"}
        ]


def test_the_settle_pair_takes_the_lock_rather_than_trusting_its_callers():
    """Structural: the lock lives IN the pair, not at three of four call sites.

    Asserted on the source because the behavioural tests above can only show
    that today's callers are safe. The property is that a *new* exit path —
    which by construction will not know to take the lock — is safe too.
    """
    import ast
    import inspect
    import textwrap

    for name in ("settle_victory", "settle_defeat"):
        tree = ast.parse(
            textwrap.dedent(inspect.getsource(getattr(ApiCombatAdapter, name)))
        )
        locked = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.With)
            and any(
                isinstance(item.context_expr, ast.Attribute)
                and item.context_expr.attr == "_beat_lock"
                for item in node.items
            )
        ]
        assert locked, f"{name} no longer acquires _beat_lock itself"


@pytest.mark.parametrize("method", ["settle_victory", "settle_defeat"])
def test_the_lock_is_reentrant_so_the_in_lock_caller_still_works(method):
    """The move loop calls the pair from INSIDE ``_beat_lock`` already.

    A plain ``Lock`` here would deadlock every fight that ends through the move
    loop — i.e. almost all of them — so the reentrancy is load-bearing, not a
    stylistic choice.
    """
    adapter, player = build_adapter()
    record_streams(adapter)
    if method == "settle_defeat":
        player.hp = 0

    with adapter._beat_lock:
        state = getattr(adapter, method)([])

    assert state["combat_active"] is False
