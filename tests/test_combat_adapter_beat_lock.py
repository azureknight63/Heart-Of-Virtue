"""``ApiCombatAdapter._beat_lock`` serializes the two beat-driving entry points.

``src/api/app.py`` builds SocketIO with ``async_mode="threading"``, so requests
really do run concurrently. Two of them reach the same adapter:

* ``POST /api/combat/move`` -> ``_execute_move``;
* the next scheduled ``GET /api/combat/status`` -> ``GameService`` resume
  branch -> ``adapter._execute_move(player.current_move)``, on the SAME ``Move``
  object the first request is mid-``advance()`` on.

Unserialized, that interleaves ``_executing_move``'s save and restore and can
leave the flag stuck True. Every later ``initialize_combat(reinit=True)`` then
early-returns -- silently skipping the issue-#344 resume and losing the
``combat:started`` emit, which is not gated on ``reinit``.

The lock is REENTRANT because the legitimate same-thread nesting is real:
``_execute_move`` -> ``Move.advance`` -> ``functions.add_enemies_to_combat`` ->
``initialize_combat(reinit=True)``. A plain ``Lock`` would deadlock the request
thread on the first reinforcement spawn. (A ``threading.local()`` flag was
considered and rejected -- see ``_beat_lock``'s comment.)
"""

import threading

import pytest

import src.positions as positions
from src.api.combat_adapter import ApiCombatAdapter
from src.npc import CaveBat
from src.player import Player

_DEADLINE_SECONDS = 10


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setattr(positions, "initialize_combat_positions", lambda **kw: None)
    player = Player()
    player.in_combat = True
    player.combat_list = []
    player.combat_list_allies = [player]
    player.combat_proximity = {}
    player.combat_log = []
    player.combat_beat = 1
    return ApiCombatAdapter(player)


def test_the_beat_lock_is_reentrant(adapter):
    """A plain Lock here would deadlock the mid-beat reinforcement path."""
    with adapter._beat_lock:
        assert adapter._beat_lock.acquire(blocking=False), (
            "_beat_lock must be an RLock: _execute_move -> Move.advance -> "
            "add_enemies_to_combat -> initialize_combat(reinit=True) re-enters "
            "it on the same thread"
        )
        adapter._beat_lock.release()


def _held_during(adapter, run):
    """Whether ``_beat_lock`` is held while ``run(adapter)`` executes its body.

    Checked from ANOTHER thread: ``RLock`` is reentrant, so a same-thread probe
    would succeed whether or not the caller holds it.
    """
    held = []

    def probe():
        got = adapter._beat_lock.acquire(blocking=False)
        held.append(not got)
        if got:
            adapter._beat_lock.release()

    def observe(*args, **kwargs):
        worker = threading.Thread(target=probe, daemon=True)
        worker.start()
        worker.join(_DEADLINE_SECONDS)
        return {}

    run(adapter, observe)
    assert held, "the observed body never ran"
    return held[0]


def test_execute_move_holds_the_beat_lock(adapter):
    def run(adp, observe):
        adp._execute_move_inner = observe
        adp._execute_move(object())

    assert _held_during(adapter, run), (
        "_execute_move must hold _beat_lock for its whole body, or a "
        "concurrent status poll can interleave _executing_move's save/restore"
    )


def test_initialize_combat_holds_the_beat_lock(adapter):
    def run(adp, observe):
        adp._initialize_combat_locked = observe
        adp.initialize_combat([CaveBat()])

    assert _held_during(adapter, run), (
        "initialize_combat must hold _beat_lock for its whole body"
    )


def test_a_second_thread_cannot_drive_a_beat_while_one_is_running(adapter):
    """The end the lock exists for: no two threads inside a beat at once."""
    entered = threading.Event()
    release = threading.Event()

    def slow_inner(move, resume=False):
        entered.set()
        release.wait(_DEADLINE_SECONDS)
        return {}

    adapter._execute_move_inner = slow_inner
    worker = threading.Thread(
        target=lambda: adapter._execute_move(object()), daemon=True
    )
    worker.start()
    try:
        assert entered.wait(_DEADLINE_SECONDS), "the beat body never started"
        got_in = adapter._beat_lock.acquire(blocking=False)
        if got_in:
            adapter._beat_lock.release()
    finally:
        release.set()
        worker.join(_DEADLINE_SECONDS)

    assert not got_in, (
        "a second thread entered the beat path while the first was inside it"
    )


def test_the_lock_is_released_even_when_the_beat_raises(adapter):
    """``_execute_move`` swallows the exception; it must not swallow the lock."""

    def boom(move, resume=False):
        raise RuntimeError("beat exploded")

    adapter._execute_move_inner = boom
    result = adapter._execute_move(object())

    assert "error" in result
    assert adapter._beat_lock.acquire(blocking=False)
    adapter._beat_lock.release()
    # ...and the call-stack marker is back down, so a later reinit still
    # reaches the resume branch.
    assert adapter._executing_move is False
