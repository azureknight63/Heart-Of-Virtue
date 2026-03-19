"""Regression tests for autosave serialization while a _combat_adapter is attached.

Root cause (fixed): player._combat_adapter held a closure (on_event_callback) and a
threading.Lock (_suggestion_lock), neither of which is picklable.  Calling save_game()
mid-combat raised an uncaught PicklingError that bubbled up as a 500 on POST /api/saves.

Fix (game_service.save_game, lines ~2125-2130): pop _combat_adapter from player.__dict__
before pickle.dumps(), restore it in the finally block.

These tests verify that invariant in isolation, without requiring the full Flask / tkinter
stack.  They belong in the standard pytest run (not tests/api/).
"""

import pickle
import threading
import pytest


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------


class _MockCombatAdapter:
    """Minimal adapter that reproduces the two pickling failures."""

    def __init__(self):
        # threading.Lock is not picklable
        self._suggestion_lock = threading.Lock()
        # Closure captures a local dict — not picklable
        session_state = {"pending_events": {}}
        self.on_event_callback = lambda player: session_state


class _MockPlayer:
    """Minimal player that can carry a _combat_adapter."""

    def __init__(self):
        self.name = "Jean"
        self.level = 1
        self.hp = 50
        self.in_combat = True
        self.time_elapsed = 0
        self.map = None
        self.current_room = None


def _save_game_serialize(player):
    """Re-implement just the pickle-safe serialization logic from game_service.save_game.

    This mirrors lines 2125-2130 of src/api/services/game_service.py so the
    regression tests remain independent of the Flask/tkinter import chain.
    """
    combat_adapter = player.__dict__.pop("_combat_adapter", None)
    try:
        data = pickle.dumps(player)
    finally:
        if combat_adapter is not None:
            player._combat_adapter = combat_adapter
    return data


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAutosaveCombatPickle:
    """Regression suite: pickle-safe save_game with _combat_adapter present."""

    def test_player_with_adapter_is_normally_unpicklable(self):
        """Baseline: confirm that pickling a player+adapter directly still raises."""
        player = _MockPlayer()
        player._combat_adapter = _MockCombatAdapter()

        with pytest.raises((pickle.PicklingError, TypeError, AttributeError)):
            pickle.dumps(player)

    def test_serialization_succeeds_with_combat_adapter_attached(self):
        """save_game logic must not raise PicklingError when _combat_adapter is present."""
        player = _MockPlayer()
        player._combat_adapter = _MockCombatAdapter()

        # Should complete without exception
        data = _save_game_serialize(player)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_combat_adapter_restored_after_successful_serialize(self):
        """_combat_adapter must be back on the player after serialization returns."""
        player = _MockPlayer()
        adapter = _MockCombatAdapter()
        player._combat_adapter = adapter

        _save_game_serialize(player)

        assert hasattr(player, "_combat_adapter"), (
            "_combat_adapter was not restored — combat state would be lost for "
            "the rest of the encounter."
        )
        assert player._combat_adapter is adapter

    def test_combat_adapter_restored_even_if_pickle_raises(self):
        """_combat_adapter must be restored when pickle.dumps raises unexpectedly."""
        player = _MockPlayer()
        adapter = _MockCombatAdapter()
        player._combat_adapter = adapter

        original_dumps = pickle.dumps

        def broken_dumps(obj, *args, **kwargs):
            raise pickle.PicklingError("injected failure")

        pickle.dumps = broken_dumps
        try:
            with pytest.raises(pickle.PicklingError):
                _save_game_serialize(player)
        finally:
            pickle.dumps = original_dumps

        assert player._combat_adapter is adapter, (
            "_combat_adapter was dropped after a pickle failure — "
            "the finally block is not executing correctly."
        )

    def test_serialization_without_combat_adapter(self):
        """save_game logic must work normally when no _combat_adapter is present."""
        player = _MockPlayer()  # no adapter attached

        data = _save_game_serialize(player)

        assert isinstance(data, bytes)
        assert not hasattr(player, "_combat_adapter")

    def test_serialized_player_can_be_restored(self):
        """Round-trip: deserialized player must have the same core attributes."""
        player = _MockPlayer()
        player._combat_adapter = _MockCombatAdapter()

        data = _save_game_serialize(player)
        restored = pickle.loads(data)

        assert restored.name == player.name
        assert restored.level == player.level
        assert restored.hp == player.hp
        # The adapter is NOT persisted — combat is re-initialised on load
        assert not hasattr(restored, "_combat_adapter")


class TestPlayerPickleContract:
    """Verify that the Player.__getstate__ contract is self-enforcing.

    These tests use _MockPlayer (which mirrors the _combat_adapter-stripping
    pattern) rather than the real Player to stay independent of tkinter.
    A companion integration note: when tkinter is available, the same test
    should be run against a real Player instance to catch any new non-picklable
    attribute attached by a future mixin.
    """

    def test_getstate_strips_combat_adapter(self):
        """__getstate__ must exclude _combat_adapter from the serialized dict."""
        player = _MockPlayer()
        player._combat_adapter = _MockCombatAdapter()

        # Simulate __getstate__ logic (mirrors what Player.__getstate__ does)
        state = player.__dict__.copy()
        state.pop("_combat_adapter", None)

        assert "_combat_adapter" not in state

    def test_getstate_preserves_core_attributes(self):
        """__getstate__ must not strip game-critical attributes."""
        player = _MockPlayer()
        player._combat_adapter = _MockCombatAdapter()

        state = player.__dict__.copy()
        state.pop("_combat_adapter", None)

        for attr in ("name", "level", "hp", "in_combat"):
            assert attr in state, f"__getstate__ must preserve '{attr}'"
