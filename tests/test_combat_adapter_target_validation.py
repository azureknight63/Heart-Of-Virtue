"""Target-validation regression tests for ``ApiCombatAdapter``.

A combat command arrives from the client, so ``target_id`` is untrusted input.
The adapter publishes the legal target set for a move via
``_get_available_targets`` (alive, inside the move's effective ``mvrange``, and
friendly only when the move sets ``accepts_ally_target``) -- but both selection
entry points used to resolve the id against ``combat_list + combat_list_allies``
instead, each with its own copy of the lookup. A crafted ``select_target`` could
therefore land ``Disrupt`` (``mvrange=(0, 5)``, load-bearing per its docstring)
on an enemy 40 tiles away, or on a friendly NPC.

These tests use real ``Player``/``NPC``/``Move``/``ApiCombatAdapter`` objects but
no Flask app, session manager or universe, so they belong in the default tree
rather than ``tests/api/`` -- nothing here mutates the module-level item/merchant
registries that CLAUDE.md keeps full-app session tests out of the default run to
protect. (This mirrors ``tests/test_combat_adapter_coverage.py``.) The real
objects are the point: a mocked combatant answers every attribute the test asks
for, and would happily agree with a wrong ``mvrange`` or a missing
``accepts_ally_target``.
"""

import threading
import time
from contextlib import contextmanager
from unittest.mock import patch

import pytest

import src.moves as moves
from src.api.combat_adapter import ApiCombatAdapter
from src.npc import NPC
from src.api.serializers.combat import CombatantSerializer
from src.combatant import combatant_handle
from tests._combat_fixtures import (
    forced_roll,
    make_adapter,
    make_npc,
    make_player,
    place,
    repair_proximity,
    seeded,
)

#: Disrupt rolls ``random.randint(0, 100)`` in ``src.moves._utility`` against
#: its own ``preview_hit_chance``. Any assertion that a legal target actually
#: took damage must force the roll, or the test fails whenever the dice miss.
_ALWAYS_HITS = dict(value=0, module="src.moves._utility")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build(move_cls=moves.Disrupt, ally_distance=3):
    """A real fight: two in-range enemies, one far enemy, one ally.

    Two enemies sit inside ``Disrupt``'s ``mvrange`` so the adapter genuinely
    enters ``target_selection`` (a single viable target auto-resolves instead).

    Built under ``seeded``: ``_ALWAYS_HITS`` forces the to-hit roll, but the
    DAMAGE roll downstream of it is unseeded, and
    ``test_valid_in_range_enemy_still_resolves`` asserts the target actually
    lost HP. It was observed failing once in a full run and passing in
    isolation and across a 15-seed sweep -- which is the signature of an
    unseeded assertion with a narrow margin, not of a real defect, and is
    exactly what CLAUDE.md says to seed rather than loosen.
    """
    with seeded(20260909):
        return _build_unseeded(move_cls, ally_distance)


def _build_unseeded(move_cls, ally_distance):
    player = make_player(
        weapon="Sword", strength=20, finesse=20, endurance=20, speed=20
    )
    move = move_cls(player)
    player.known_moves = [move]

    near = make_npc(NPC, name="NearEnemy", hp=100, maxhp=100)
    second = make_npc(NPC, name="SecondEnemy", hp=100, maxhp=100)
    far = make_npc(NPC, name="FarEnemy", hp=100, maxhp=100)
    ally = make_npc(NPC, name="Friendly", hp=100, maxhp=100)
    ally.friend = True

    adapter = make_adapter(player, enemies=[near, second, far], allies=[ally])

    place(player, 0, 0)
    place(near, 2, 0)
    place(second, 3, 0)
    place(far, 40, 0)
    place(ally, ally_distance, 0)
    repair_proximity([player, near, second, far, ally])

    return {
        "player": player,
        "adapter": adapter,
        "move": move,
        "near": near,
        "second": second,
        "far": far,
        "ally": ally,
    }


@pytest.fixture
def fight():
    return _build()


def _commit_disrupt_on(fight):
    """Send the pending ``Disrupt`` at ``near`` with the to-hit roll forced."""
    adapter, near = fight["adapter"], fight["near"]
    with forced_roll(**_ALWAYS_HITS):
        result = adapter.process_command(
            {"type": "select_target", "target_id": CombatantSerializer.stream_id(near)}
        )
    assert "error" not in result
    return result


def _select_disrupt_on(fight):
    """Select ``Disrupt`` and land it on ``near``: the legitimate happy path."""
    fight["adapter"].process_command({"type": "select_move", "move_index": 0})
    return _commit_disrupt_on(fight)


def _snapshot(adapter, fight):
    """The state that must survive a rejected target selection untouched."""
    return {
        "awaiting_input": adapter.awaiting_input,
        "input_type": adapter.input_type,
        "pending_move_index": adapter.pending_move_index,
        "options": [o["id"] for o in adapter.available_options],
        "hp": {c["key"]: c["obj"].hp for c in _combatants(fight)},
        "fatigue": fight["player"].fatigue,
        "beat": fight["player"].combat_beat,
    }


def _combatants(fight):
    return [
        {"key": key, "obj": fight[key]}
        for key in ("player", "near", "second", "far", "ally")
    ]


# ---------------------------------------------------------------------------
# The published option set is what makes a target legal
# ---------------------------------------------------------------------------


def test_published_options_exclude_out_of_range_enemy_and_ally(fight):
    """Sanity check on the option set the rejections are measured against."""
    options = fight["adapter"]._get_available_targets(fight["move"])
    names = {o["name"] for o in options}

    assert fight["move"].mvrange == (0, 5)
    assert names == {"NearEnemy", "SecondEnemy"}
    assert getattr(fight["move"], "accepts_ally_target", False) is False


def test_select_target_rejects_out_of_range_enemy(fight):
    adapter, far = fight["adapter"], fight["far"]
    adapter.process_command({"type": "select_move", "move_index": 0})
    assert adapter.input_type == "target_selection"

    result = adapter.process_command(
        {"type": "select_target", "target_id": CombatantSerializer.stream_id(far)}
    )

    assert "error" in result
    assert "not a valid target" in result["error"]
    assert far.hp == 100
    assert fight["move"].target is not far


def test_select_target_rejects_ally_for_move_without_ally_targeting(fight):
    adapter, ally = fight["adapter"], fight["ally"]
    adapter.process_command({"type": "select_move", "move_index": 0})

    result = adapter.process_command(
        {"type": "select_target", "target_id": CombatantSerializer.stream_id(ally)}
    )

    assert "error" in result
    assert ally.hp == 100
    assert fight["move"].target is not ally


def test_combined_selection_rejects_out_of_range_enemy(fight):
    adapter, far = fight["adapter"], fight["far"]

    result = adapter.process_command(
        {
            "type": "select_move_and_target",
            "move_name": "Disrupt",
            "target_id": CombatantSerializer.stream_id(far),
        }
    )

    assert "error" in result
    assert far.hp == 100
    assert adapter.player.current_move is None


def test_combined_selection_rejects_ally(fight):
    adapter, ally = fight["adapter"], fight["ally"]

    result = adapter.process_command(
        {
            "type": "select_move_and_target",
            "move_name": "Disrupt",
            "target_id": CombatantSerializer.stream_id(ally),
        }
    )

    assert "error" in result
    assert ally.hp == 100


# ---------------------------------------------------------------------------
# Rejection must not corrupt combat state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["far", "ally"])
def test_rejected_target_leaves_combat_state_untouched(fight, bad):
    """No half-applied move, no stale awaiting_input/pending_move_index.

    After a rejection the client must be able to simply re-send a legal target:
    the adapter is still awaiting a target selection for the same pending move,
    with the same option set.
    """
    adapter = fight["adapter"]
    adapter.process_command({"type": "select_move", "move_index": 0})
    before = _snapshot(adapter, fight)

    prefix = "enemy" if bad == "far" else "ally"
    result = adapter.process_command(
        {"type": "select_target", "target_id": f"{prefix}_{combatant_handle(fight[bad])}"}
    )

    assert "error" in result
    assert _snapshot(adapter, fight) == before
    assert before["awaiting_input"] is True
    assert before["input_type"] == "target_selection"
    assert before["pending_move_index"] == 0


def test_client_can_retry_with_a_legal_target_after_rejection(fight):
    adapter, near, far = fight["adapter"], fight["near"], fight["far"]
    adapter.process_command({"type": "select_move", "move_index": 0})
    adapter.process_command(
        {"type": "select_target", "target_id": CombatantSerializer.stream_id(far)}
    )

    _commit_disrupt_on(fight)

    assert fight["move"].target is near
    assert near.hp < 100
    assert adapter.pending_move_index is None


# ---------------------------------------------------------------------------
# Legitimate flows must keep working
# ---------------------------------------------------------------------------


def test_valid_in_range_enemy_still_resolves(fight):
    near = fight["near"]

    _select_disrupt_on(fight)

    assert fight["move"].target is near
    assert near.hp < 100


def test_ally_accepted_for_move_that_declares_accepts_ally_target():
    """``Advance`` closes distance on an ally deliberately (e.g. to heal)."""
    fight = _build(move_cls=moves.Advance)
    adapter, ally, move = fight["adapter"], fight["ally"], fight["move"]

    assert move.accepts_ally_target is True
    assert CombatantSerializer.stream_id(ally) in {
        o["id"] for o in adapter._get_available_targets(move)
    }

    result = adapter.process_command(
        {
            "type": "select_move_and_target",
            "move_name": "Advance",
            "target_id": CombatantSerializer.stream_id(ally),
        }
    )

    assert "error" not in result
    assert move.target is ally


def test_unknown_target_id_still_falls_back_to_auto_resolution():
    """An id naming nobody in the fight is not the exploit path.

    It resolves to no combatant at all, so ``_resolve_move_target`` treats it as
    "no explicit target given" exactly as before -- and auto-resolution only
    ever picks from the viable set. Pinned so the strictness added for real-but-
    illegal targets is not quietly widened into a behaviour change here (the
    repeat-last-move flow can carry a stale id).
    """
    fight = _build()
    # Only one enemy in range, so the no-target path auto-resolves.
    place(fight["second"], 40, 0)
    repair_proximity(
        [fight["player"], fight["near"], fight["second"], fight["far"], fight["ally"]]
    )
    adapter = fight["adapter"]

    result = adapter.process_command(
        {
            "type": "select_move_and_target",
            "move_name": "Disrupt",
            "target_id": "enemy_999999999",
        }
    )

    assert "error" not in result
    assert fight["move"].target is fight["near"]


def test_untargeted_move_never_consults_the_target_option_set():
    """A non-targeted move self-targets; validation must not touch it."""
    fight = _build()
    player, adapter = fight["player"], fight["adapter"]
    dodge = moves.Dodge(player)
    dodge.user = player
    player.known_moves = [dodge]
    assert dodge.targeted is False and dodge.viable() is True

    with patch.object(
        adapter,
        "_resolve_target_from_options",
        wraps=adapter._resolve_target_from_options,
    ) as validator:
        result = adapter.process_command(
            {
                "type": "select_move_and_target",
                "move_name": "Dodge",
                "target_id": CombatantSerializer.stream_id(fight['ally']),
            }
        )

    assert "error" not in result
    validator.assert_not_called()
    assert dodge.target is player


# ---------------------------------------------------------------------------
# Move readiness: the same preconditions on both entry points
# ---------------------------------------------------------------------------
#
# ``select_move_and_target`` is what the React client sends for essentially
# every combat action (LeftPanel.jsx, useCombatCoordinator.js), yet it carried
# no ``current_stage`` check -- only ``select_move`` did. Since ``cast()``
# unconditionally resets ``current_stage`` to 0, re-selecting a move that was
# still in recoil or cooldown erased the remainder of its cycle, making every
# move free to spam through the primary UI path. Both entry points now share
# ``_check_move_preconditions``.


def _cooling_dodge():
    """A fight whose only move is a Dodge stuck mid-cooldown."""
    fight = _build()
    player = fight["player"]
    dodge = moves.Dodge(player)
    dodge.user = player
    player.known_moves = [dodge]
    dodge.current_stage = 3  # cooldown
    dodge.beats_left = 2
    fight["move"] = dodge
    return fight


@pytest.mark.parametrize(
    "command",
    [
        {"type": "select_move", "move_index": 0},
        {"type": "select_move_and_target", "move_name": "Dodge"},
    ],
    ids=["select_move", "select_move_and_target"],
)
def test_cooling_move_is_rejected_by_both_entry_points(command):
    fight = _cooling_dodge()
    adapter, dodge, player = fight["adapter"], fight["move"], fight["player"]

    result = adapter.process_command(command)

    assert result.get("error") == "Move not ready yet"
    # The cooldown must survive the rejection -- cast() would have zeroed it.
    assert dodge.current_stage == 3
    assert dodge.beats_left == 2
    assert player.current_move is None
    # ... and the adapter is still cleanly awaiting a fresh move selection.
    assert adapter.awaiting_input is True
    assert adapter.input_type == "move_selection"
    assert adapter.pending_move_index is None


@pytest.mark.parametrize(
    "command",
    [
        {"type": "select_move", "move_index": 0},
        {"type": "select_move_and_target", "move_name": "Dodge"},
    ],
    ids=["select_move", "select_move_and_target"],
)
def test_ready_move_still_works_through_both_entry_points(command):
    fight = _cooling_dodge()
    adapter, dodge, player = fight["adapter"], fight["move"], fight["player"]
    dodge.current_stage = 0
    dodge.beats_left = 0
    assert dodge.viable() is True

    result = adapter.process_command(command)

    assert "error" not in result
    # Dodge resolves inside the beats this request processes, so current_move is
    # already cleared again by the time it returns; the log entry the adapter
    # writes when a move is accepted is the durable evidence it actually ran.
    assert any(
        "Dodge" in entry.get("message", "")
        for entry in getattr(player, "combat_log", [])
    )


# ---------------------------------------------------------------------------
# Issue #569:the tactical-advisor worker must never touch engine move state
# ---------------------------------------------------------------------------
#
# ``refresh_suggestions`` runs at the end of ``initialize_combat`` and of every
# ``_execute_move``, and used to build the strategist context on its daemon
# thread. That walk (``_get_available_moves`` -> ``_build_target_entry`` ->
# ``Move._viable_for``) swaps ``move.target`` in and out per candidate on the
# player's REAL move instance, so a worker still running from the previous
# beat could flip the target a request thread had just committed. The test
# above sampled ``fight["move"].target`` while that was happening (~1% flake);
# in a live game the same swap can land under ``Disrupt.execute``.

#: How many times the race pin rebuilds the fight and samples the target.
#: Every attempt widens the worker's window by ``_WORKER_STALL_S`` per
#: viability check, and the pre-fix defect showed on nearly every attempt.
_RACE_ATTEMPTS = 5
#: How long an off-thread viability check is stalled, and how often the
#: sampler reads the target meanwhile. The stall must exceed the poll
#: interval or the sampler could never land a read inside a swapped window.
_WORKER_STALL_S = 0.002
_POLL_S = 0.0005
#: How long the sampler keeps reading while any worker is alive.
_SETTLE_DEADLINE_S = 1.0
#: Total budget for joining every tracked worker on block exit.
_JOIN_DEADLINE_S = 5.0


@contextmanager
def _tracked_threads():
    """Record every thread started inside the block, and join them on exit.

    Joining ``threading.enumerate()`` is not an option: under xdist the worker
    process owns execnet IO threads that never finish.

    The join runs on every exit, so a worker never outlives the patches the
    block's body installed; the liveness assertion runs only on the normal
    exit, so it cannot mask the body's own failure.
    """
    started = []
    real_thread = threading.Thread

    class _Tracked(real_thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            started.append(self)

    with patch("threading.Thread", _Tracked):
        try:
            yield started
        finally:
            deadline = time.monotonic() + _JOIN_DEADLINE_S
            for thread in started:
                thread.join(max(0, deadline - time.monotonic()))
    assert not any(t.is_alive() for t in started), "worker did not settle"


def test_suggestion_worker_never_touches_engine_move_state():
    """Contract: every ``viable``/``_viable_for`` call runs on the request thread."""
    request_thread = threading.current_thread()
    callers = []
    real_viable_for = moves.Move._viable_for
    real_viable = moves.Disrupt.viable

    def recording_viable_for(self, target):
        callers.append(threading.current_thread())
        return real_viable_for(self, target)

    def recording_viable(self):
        callers.append(threading.current_thread())
        return real_viable(self)

    # A with-tuple exits right to left, so the thread tracker goes LAST: its
    # join then happens while the recorders are still installed, and a
    # worker that finishes late is still seen.
    with (
        patch.object(moves.Move, "_viable_for", recording_viable_for),
        patch.object(moves.Disrupt, "viable", recording_viable),
        _tracked_threads() as started,
    ):
        fight = _build()
        _select_disrupt_on(fight)
        assert started, "no suggestion worker started"

    assert callers, "recorder saw no viability checks at all"
    off_thread = [t.name for t in callers if t is not request_thread]
    assert off_thread == [], f"engine move state touched off the request thread: {off_thread}"


@pytest.mark.real_sleep
def test_move_target_survives_a_still_running_suggestion_worker():
    """Direct race pin: widen the worker's window and sample the target at once.

    ``real_sleep`` because ``tests/conftest.py`` no-ops ``time.sleep`` for
    every test by default; a no-op sleep never releases the GIL, so the worker
    would finish its swaps inside one interpreter slice and the poll below
    could not observe them.
    """
    request_thread = threading.current_thread()
    real_viable = moves.Disrupt.viable

    def slow_off_thread(self):
        if threading.current_thread() is not request_thread:
            time.sleep(_WORKER_STALL_S)
        return real_viable(self)

    with patch.object(moves.Disrupt, "viable", slow_off_thread):
        for attempt in range(_RACE_ATTEMPTS):
            with _tracked_threads() as started:
                fight = _build()
                _select_disrupt_on(fight)
                assert started, "no suggestion worker started"
                # The committed target must be stable from the moment the
                # command returns until the next command -- sample it at once,
                # then keep sampling while any worker is still alive.
                observed = {fight["move"].target}
                deadline = time.monotonic() + _SETTLE_DEADLINE_S
                while any(t.is_alive() for t in started) and time.monotonic() < deadline:
                    observed.add(fight["move"].target)
                    time.sleep(_POLL_S)
                names = {getattr(t, "name", t) for t in observed}
                assert names == {"NearEnemy"}, (
                    f"attempt {attempt}: move.target drifted through {names}"
                )
                assert fight["near"].hp < 100


def test_suggestions_still_populate_from_the_snapshot_context():
    """Negative control: moving the context build off the worker must not
    starve it -- the strategist still gets a full context and its answer still
    lands on the player, and the adapter keeps the thread handle so callers
    can join it."""
    stub = [{"move_name": "Disrupt", "score": 90, "reasoning": "stub"}]
    with _tracked_threads() as started:
        fight = _build()
        adapter, player = fight["adapter"], fight["player"]
        with patch.object(
            adapter.strategist, "get_suggestions", return_value=stub
        ) as get_suggestions:
            adapter.refresh_suggestions()
            thread = adapter._suggestion_thread
            assert thread is started[-1]
            thread.join(timeout=_JOIN_DEADLINE_S)

    assert player.suggested_moves == stub
    assert player.suggestions_loading is False
    ctx = get_suggestions.call_args.args[0]
    assert {m["name"] for m in ctx["available_moves"]} == {"Disrupt"}
    assert {e["name"] for e in ctx["enemies"]} == {"NearEnemy", "SecondEnemy", "FarEnemy"}


# ---------------------------------------------------------------------------
# Issue #569, second path: the status poll walks the same move instances
# ---------------------------------------------------------------------------
#
# The worker was not the only off-thread walker. ``GET /api/combat/status``
# runs ``get_combat_state`` -> ``_get_available_moves`` on its own request
# thread every few seconds, and ``game_service.get_combat_status`` walks it
# directly on the resume and move-selection branches too. None of those held
# ``_beat_lock``, so the same ``_viable_for`` target swap could land under a
# ``select_move_and_target`` the player's request thread was committing --
# that command keeps ``input_type == "move_selection"`` for its whole handler,
# which is exactly the condition the poll rebuilds the option list on.

#: How long each side of the handshake below waits for the other. Once the
#: walk is locked the poll can never reach its half while a command holds the
#: lock, so the request side times out here and the test still passes.
_HANDSHAKE_S = 0.5


def _poll_forever(adapter, stop, errors):
    """The status poll, reduced to its engine call: ``get_combat_state`` in
    a loop until told to stop. Exceptions are kept, not raised -- the poll
    thread has no assertion of its own to fail."""
    while not stop.is_set():
        try:
            adapter.get_combat_state()
        except Exception as exc:  # pragma: no cover - diagnostic only
            errors.append(repr(exc))


def test_move_target_survives_a_concurrent_status_poll():
    """Deterministic pin of the poll race, staged as a handshake.

    ``_viable_for`` swaps ``move.target`` in, calls ``viable()``, and restores
    what it found. Two threads doing that on one move interleave as: request
    swaps A in (saving the real target), poll swaps B in (saving A), request
    restores, poll restores A -- and the committed target is gone. The
    handshake forces exactly that order: the request thread's swapped-in
    ``viable()`` waits until the poll thread is inside its own swap, and the
    poll thread's stays there until the command has returned.

    The command commits ``SecondEnemy`` while the walk's first candidate --
    the A above -- is ``NearEnemy``, so the stale restore is visible: were
    the committed target also the first candidate, the clobber would put
    back the right combatant by coincidence.
    """
    request_thread = threading.current_thread()
    real_viable_for = moves.Move._viable_for
    real_viable = moves.Disrupt.viable
    in_swap = threading.local()
    request_in_window = threading.Event()
    poll_in_window = threading.Event()
    command_returned = threading.Event()

    def tracking_viable_for(self, target):
        in_swap.active = True
        try:
            return real_viable_for(self, target)
        finally:
            in_swap.active = False

    def handshake_viable(self):
        if getattr(in_swap, "active", False):
            if threading.current_thread() is request_thread:
                if not request_in_window.is_set():
                    request_in_window.set()
                    poll_in_window.wait(_HANDSHAKE_S)
            elif request_in_window.is_set() and not poll_in_window.is_set():
                poll_in_window.set()
                command_returned.wait(_HANDSHAKE_S)
        return real_viable(self)

    fight = _build()
    adapter, second = fight["adapter"], fight["second"]
    stop = threading.Event()
    errors = []

    with (
        patch.object(moves.Move, "_viable_for", tracking_viable_for),
        patch.object(moves.Disrupt, "viable", handshake_viable),
        _tracked_threads(),
    ):
        poller = threading.Thread(
            target=_poll_forever, args=(adapter, stop, errors), daemon=True
        )
        poller.start()
        try:
            with forced_roll(**_ALWAYS_HITS):
                result = adapter.process_command(
                    {
                        "type": "select_move_and_target",
                        "move_name": "Disrupt",
                        "target_id": CombatantSerializer.stream_id(second),
                    }
                )
        finally:
            command_returned.set()
            stop.set()

    assert "error" not in result
    assert request_in_window.is_set(), "fixture never walked the option set"
    assert fight["move"].target is second, (
        f"move.target is {getattr(fight['move'].target, 'name', fight['move'].target)!r} "
        f"after the command committed SecondEnemy (poll errors: {errors})"
    )
    assert second.hp < 100


def test_every_viability_walk_holds_the_beat_lock():
    """Contract behind the pin above: ``Move._viable_for`` never runs on this
    adapter unless the calling thread owns ``_beat_lock`` -- through
    ``initialize_combat``, the status poll's ``get_combat_state`` and a
    ``process_command`` alike. ``RLock._is_owned`` is the check because the
    lock is reentrant: a non-blocking ``acquire`` would succeed for the owner
    and for nobody else only on a plain Lock."""
    real_viable_for = moves.Move._viable_for
    real_init = ApiCombatAdapter.__init__
    holder = {}
    phase = {"name": "initialize_combat"}
    walks = []

    def capturing_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        holder["adapter"] = self

    def recording_viable_for(self, target):
        adapter = holder.get("adapter")
        if adapter is not None:
            walks.append((phase["name"], adapter._beat_lock._is_owned()))
        return real_viable_for(self, target)

    with (
        patch.object(ApiCombatAdapter, "__init__", capturing_init),
        patch.object(moves.Move, "_viable_for", recording_viable_for),
        _tracked_threads(),
    ):
        fight = _build()
        phase["name"] = "get_combat_state"
        fight["adapter"].get_combat_state()
        phase["name"] = "process_command"
        with forced_roll(**_ALWAYS_HITS):
            result = fight["adapter"].process_command(
                {
                    "type": "select_move_and_target",
                    "move_name": "Disrupt",
                    "target_id": CombatantSerializer.stream_id(fight["near"]),
                }
            )
        assert "error" not in result

    # ``initialize_combat`` is recorded but cannot be required: the fixture
    # places the combatants after it runs, so its walk finds nothing in range
    # and never reaches ``_viable_for``.
    phases_seen = {name for name, _owned in walks}
    assert {"get_combat_state", "process_command"} <= phases_seen, (
        f"recorder did not see every phase walk the option set: {phases_seen}"
    )
    unlocked = sorted({name for name, owned in walks if not owned})
    assert unlocked == [], f"_viable_for ran without _beat_lock in: {unlocked}"
