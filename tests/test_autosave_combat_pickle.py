"""Saving mid-combat must not choke on the attached ``_combat_adapter``.

Root cause (fixed): ``player._combat_adapter`` holds a closure
(``on_event_callback``) and a ``threading.Lock`` (``_suggestion_lock``),
neither of which is picklable. Calling ``save_game()`` mid-combat raised an
uncaught ``PicklingError`` that surfaced as a 500 on ``POST /api/saves``.

There are two independent defences, and both are exercised here against the
real code:

1. ``Player.__getstate__`` drops ``_combat_adapter`` (and the transient
   ``suggestions_paused``) from the pickled state.
2. ``GameService.save_game`` pops the adapter off ``player.__dict__`` before
   serializing and restores it in a ``finally``.

The previous version of this file proved neither. It defined a local
``_save_game_serialize()`` that *re-implemented* save_game's pop/restore, plus
a ``_MockPlayer`` with no ``__getstate__``, and asserted against those — so
deleting the pop/restore from ``game_service.py``, or the exclusion list from
``Player.__getstate__``, left every test green. Two of them went further and
built a dict with ``state.pop("_combat_adapter", None)`` inside the test body
before asserting the key was absent, which is a statement about ``dict.pop``.
"""

import pickle
import threading
from unittest.mock import patch

import pytest

from src.api.services.game_service import GameService
from src.player import Player
from src.secure_pickle import serialize_for_save


class _UnpicklableCombatAdapter:
    """Reproduces the two real pickling failures the adapter carries."""

    def __init__(self):
        self._suggestion_lock = threading.Lock()  # locks are not picklable
        session_state = {"pending_events": {}}
        self.on_event_callback = lambda player: session_state  # nor are closures


@pytest.fixture
def player_in_combat():
    player = Player()
    player.name = "Jean"
    player.level = 5
    player.time_elapsed = 3600
    player.in_combat = True
    player.map = {"name": "Dark Grotto"}
    player._combat_adapter = _UnpicklableCombatAdapter()
    player.suggestions_paused = True
    return player


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows


class _FakeDb:
    """Records every (sql, params) pair; answers the two SELECTs save_game makes."""

    def __init__(self, existing_autosave_id=None, manual_save_count=0):
        self.calls = []
        self._existing_autosave_id = existing_autosave_id
        self._manual_save_count = manual_save_count

    async def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if "COUNT(*)" in sql:
            return _FakeResult([[self._manual_save_count]])
        if "SELECT id FROM saves" in sql:
            return _FakeResult(
                [[self._existing_autosave_id]] if self._existing_autosave_id else []
            )
        return _FakeResult([])


class TestPlayerPickleContract:
    """Player.__getstate__ — defence #1, exercised on a real Player."""

    def test_adapter_is_excluded_from_the_pickled_state(self, player_in_combat):
        state = player_in_combat.__getstate__()

        assert "_combat_adapter" not in state
        assert "suggestions_paused" not in state
        # ...and the live player is untouched: __getstate__ copies, not mutates.
        assert isinstance(player_in_combat._combat_adapter, _UnpicklableCombatAdapter)
        assert player_in_combat.suggestions_paused is True

    def test_core_attributes_survive(self, player_in_combat):
        state = player_in_combat.__getstate__()

        for attr in ("name", "level", "hp", "in_combat", "inventory", "map"):
            assert attr in state, f"__getstate__ dropped '{attr}'"
        assert state["level"] == 5
        assert state["map"] == {"name": "Dark Grotto"}

    def test_a_real_player_with_an_adapter_attached_pickles_and_round_trips(
        self, player_in_combat
    ):
        data = pickle.dumps(player_in_combat)
        restored = pickle.loads(data)

        assert restored.name == "Jean"
        assert restored.level == 5
        assert restored.in_combat is True
        # Combat is re-initialised on load, so the adapter must not persist.
        assert not hasattr(restored, "_combat_adapter")
        assert not hasattr(restored, "suggestions_paused")

    def test_the_adapter_really_is_unpicklable_on_its_own(self):
        """Anti-vacuity: if the adapter ever became picklable, the tests above
        would pass for the wrong reason."""
        with pytest.raises((pickle.PicklingError, TypeError, AttributeError)):
            pickle.dumps(_UnpicklableCombatAdapter())

    def test_serialize_for_save_wraps_the_stripped_state_in_the_hovs_header(
        self, player_in_combat
    ):
        blob = serialize_for_save(player_in_combat)

        assert blob.startswith(b"HOVS")
        assert player_in_combat._combat_adapter is not None


class TestSaveGameStripsAndRestoresTheAdapter:
    """GameService.save_game — defence #2, driven with a fake DB."""

    @staticmethod
    async def _save(player, db, **kwargs):
        with patch("src.api.db.db", db):
            return await GameService().save_game(
                player, kwargs.pop("name", "slot 1"), "user-1", **kwargs
            )

    @pytest.mark.asyncio
    async def test_manual_save_persists_the_blob_and_restores_the_adapter(
        self, player_in_combat
    ):
        adapter = player_in_combat._combat_adapter
        db = _FakeDb()

        save_id = await self._save(player_in_combat, db)

        assert save_id
        insert_sql, params = db.calls[-1]
        assert insert_sql.startswith("INSERT INTO saves")
        assert params[0] == save_id
        assert params[1] == "user-1"
        assert params[2] == "slot 1"
        assert isinstance(params[3], bytes) and params[3].startswith(b"HOVS")
        assert params[4] is False           # is_autosave
        assert params[5] == 5               # level
        assert params[6] == "Dark Grotto"   # map_name
        assert params[8] == 3600            # playtime
        # The adapter is back, so combat continues after the save.
        assert player_in_combat._combat_adapter is adapter

    @pytest.mark.asyncio
    async def test_the_saved_blob_really_round_trips_back_into_a_player(
        self, player_in_combat
    ):
        """The bytes handed to the DB are a loadable save, not an empty stub —
        and the adapter is absent from the restored player."""
        import io

        from src.functions import _safe_pickle_load

        db = _FakeDb()

        await self._save(player_in_combat, db)

        _, params = db.calls[-1]
        restored = _safe_pickle_load(io.BytesIO(params[3]))

        assert isinstance(restored, Player)
        assert restored.name == "Jean"
        assert restored.level == 5
        assert not hasattr(restored, "_combat_adapter")

    @pytest.mark.asyncio
    async def test_the_adapter_is_restored_even_when_serialization_raises(
        self, player_in_combat
    ):
        adapter = player_in_combat._combat_adapter
        db = _FakeDb()

        with patch(
            "src.secure_pickle.serialize_for_save",
            side_effect=pickle.PicklingError("injected failure"),
        ):
            with pytest.raises(pickle.PicklingError):
                await self._save(player_in_combat, db)

        assert player_in_combat._combat_adapter is adapter, (
            "_combat_adapter was dropped after a serialization failure — the "
            "finally block in save_game is not executing."
        )

    @pytest.mark.asyncio
    async def test_a_player_with_no_adapter_saves_and_gains_no_attribute(self):
        player = Player()
        player.level = 2
        player.map = {"name": "Dark Grotto"}
        db = _FakeDb()

        await self._save(player, db)

        assert not hasattr(player, "_combat_adapter")

    @pytest.mark.asyncio
    async def test_autosave_upserts_the_single_existing_autosave_row(
        self, player_in_combat
    ):
        db = _FakeDb(existing_autosave_id="autosave-42")

        save_id = await self._save(player_in_combat, db, is_autosave=True)

        assert save_id == "autosave-42"
        update_sql, params = db.calls[-1]
        assert update_sql.startswith("UPDATE saves")
        assert params[-1] == "autosave-42"
        assert player_in_combat._combat_adapter is not None

    @pytest.mark.asyncio
    async def test_manual_save_limit_of_twenty_is_enforced(self, player_in_combat):
        db = _FakeDb(manual_save_count=20)

        with pytest.raises(ValueError, match="Maximum number of manual saves"):
            await self._save(player_in_combat, db)

        # Nothing was written, and the adapter was never stripped.
        assert all(not sql.startswith("INSERT") for sql, _ in db.calls)
        assert player_in_combat._combat_adapter is not None
