"""Save, load, list and delete — the persistence surface of GameService.

History
-------
21 of this file's 28 tests asserted only ``isinstance(result, dict/list)``, and
the four "save/load" classes it advertised tested nothing but ``hasattr``::

    def test_save_game_gets_saves_dir(self, game_service):
        with patch.object(game_service, "_get_saves_dir", return_value="/tmp") as mock_dir:
            assert hasattr(game_service, "_get_saves_dir")
            mock_dir()
            mock_dir.assert_called()      # asserts the test called its own mock

It also defined ``test_apply_tile_modifications_no_mods`` and
``test_apply_tile_modifications_missing_key`` **twice each in the same class**,
so half of them never ran at all, and ``test_interact_with_target_basic_call``
swallowed its assertion in ``except (TypeError, AttributeError): pass``.

Those subjects (search, tile modifications, exploration, get_tile,
get_current_room, trigger_combat_events) are covered properly in
``test_game_service_methods.py``, ``test_game_service_world.py`` and
``test_game_service_combat.py``. What nothing covered was the thing the file
*claimed* to cover: persistence. That is now this file's job, driven with a real
``Player`` so the pickle payload and its ``HOVS`` integrity header are the real
ones — the pre-existing save tests in ``test_game_service_tier5_coverage.py``
patch ``pickle.dumps`` away, so nothing verified the header until now.

The Turso client is the only thing stubbed; every assertion is on the bytes and
the SQL parameters that actually reach it.
"""

import hashlib
import struct

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.secure_pickle import HEADER_MAGIC, HEADER_SIZE, HEADER_VERSION
from tests._gs_fixtures import GRID_3X3, live_world


@pytest.fixture
def world():
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


@pytest.fixture
def db():
    """A stubbed Turso client whose ``execute`` results the test scripts."""
    stub = AsyncMock()
    stub.execute.return_value = MagicMock(rows=[], rows_affected=0)
    with patch("src.api.db.db", stub):
        yield stub


class TransientState:
    """A combat-scoped status effect: cleared at combat end, so not on load."""

    persistent = False
    name = "Rattled"


class LastingState:
    """A world-persistent status effect (Poisoned, Slimed, ...): survives a load."""

    persistent = True
    name = "Poisoned"


def _result(rows=(), rows_affected=0):
    return MagicMock(rows=list(rows), rows_affected=rows_affected)


def _saved_blob(db_stub):
    """The ``data`` column value from the INSERT/UPDATE the save issued."""
    sql, params = db_stub.execute.call_args_list[-1].args
    return params[3] if "INSERT" in sql else params[0]


@pytest.mark.asyncio
class TestSaveGameIntegrity:
    """A new save is a ``HOVS`` header + pickle, and it must verify."""

    async def test_payload_carries_the_hovs_magic_and_version(
        self, game_service, player, db
    ):
        db.execute.side_effect = [_result(rows=[[0]]), _result()]

        await game_service.save_game(player, "MySave", "user123")

        blob = _saved_blob(db)
        assert blob[:4] == HEADER_MAGIC == b"HOVS"
        assert blob[4] == HEADER_VERSION

    async def test_header_digest_matches_the_payload(self, game_service, player, db):
        """The sha256 is what ``load_game`` checks; a wrong one bricks the save."""
        db.execute.side_effect = [_result(rows=[[0]]), _result()]

        await game_service.save_game(player, "MySave", "user123")

        blob = _saved_blob(db)
        _magic, _version, digest = struct.Struct(">4sB32s").unpack(blob[:HEADER_SIZE])
        assert digest == hashlib.sha256(blob[HEADER_SIZE:]).digest()

    async def test_the_saved_bytes_load_back_into_an_equivalent_player(
        self, game_service, player, db
    ):
        import io

        from src.functions import _safe_pickle_load

        player.hp = 42
        player.location_x, player.location_y = 1, 0
        db.execute.side_effect = [_result(rows=[[0]]), _result()]

        await game_service.save_game(player, "MySave", "user123")

        restored = _safe_pickle_load(io.BytesIO(_saved_blob(db)))
        assert restored.name == player.name
        assert restored.hp == 42
        assert (restored.location_x, restored.location_y) == (1, 0)

    async def test_a_tampered_payload_is_rejected_on_load(
        self, game_service, player, db
    ):
        """The digest is what makes the header worth writing.

        ``_safe_pickle_load`` converts the ``SaveIntegrityError`` into ``None``
        (the loader must not crash the request), and ``load_game`` turns that
        into ``None`` too — so a tampered save reads as "no save", never as a
        half-restored player.
        """
        db.execute.side_effect = [_result(rows=[[0]]), _result()]
        await game_service.save_game(player, "MySave", "user123")

        blob = bytearray(_saved_blob(db))
        blob[-1] ^= 0xFF  # flip a bit in the pickle body

        db.execute.side_effect = None
        db.execute.return_value = _result(rows=[[bytes(blob)]])

        assert await game_service.load_game("save-id", "user123") is None

    async def test_the_combat_adapter_is_stripped_then_restored(
        self, game_service, player, db
    ):
        """It holds a closure and a ``threading.Lock`` — neither is picklable."""
        adapter = object()
        player._combat_adapter = adapter
        db.execute.side_effect = [_result(rows=[[0]]), _result()]

        await game_service.save_game(player, "MySave", "user123")

        assert player._combat_adapter is adapter
        assert b"combat_adapter" not in _saved_blob(db)


@pytest.mark.asyncio
class TestSaveGameMetadata:
    """The row's denormalised columns drive the Load Game list."""

    async def test_manual_save_writes_location_and_level(
        self, game_service, player, db
    ):
        player.level = 5
        player.time_elapsed = 120
        db.execute.side_effect = [_result(rows=[[1]]), _result()]

        save_id = await game_service.save_game(player, "MySave", "user123")

        sql, params = db.execute.call_args_list[-1].args
        assert "INSERT INTO saves" in sql
        assert params[0] == save_id
        assert params[1] == "user123"
        assert params[2] == "MySave"
        assert params[4] is False  # is_autosave
        assert params[5] == 5
        assert params[6] == "gs-test-map"
        assert params[8] == 120

    async def test_room_title_humanises_the_tile_class_name(
        self, game_service, player, db
    ):
        db.execute.side_effect = [_result(rows=[[0]]), _result()]
        await game_service.save_game(player, "MySave", "user123")
        _sql, params = db.execute.call_args_list[-1].args
        assert params[7] == "Map Tile"

    async def test_manual_save_limit_is_enforced(self, game_service, player, db):
        db.execute.return_value = _result(rows=[[20]])
        with pytest.raises(ValueError, match="Maximum number of manual saves reached"):
            await game_service.save_game(player, "MySave", "user123")
        # Nothing was written.
        assert db.execute.call_count == 1

    async def test_the_limit_applies_only_to_manual_saves(
        self, game_service, player, db
    ):
        """The autosave path never counts manual rows."""
        db.execute.side_effect = [_result(rows=[]), _result()]
        assert await game_service.save_game(player, "Auto", "user123", is_autosave=True)
        counted_sql = db.execute.call_args_list[0].args[0]
        assert "COUNT(*)" not in counted_sql


@pytest.mark.asyncio
class TestAutosave:
    """One autosave row per user, UPSERTed."""

    async def test_creates_a_row_when_none_exists(self, game_service, player, db):
        db.execute.side_effect = [_result(rows=[]), _result()]

        save_id = await game_service.save_game(player, "Auto", "user123", is_autosave=True)

        sql, params = db.execute.call_args_list[-1].args
        assert "INSERT INTO saves" in sql
        assert params[0] == save_id
        assert params[4] is True

    async def test_updates_the_existing_row_in_place(self, game_service, player, db):
        db.execute.side_effect = [_result(rows=[["existing-save-id"]]), _result()]

        save_id = await game_service.save_game(player, "Auto", "user123", is_autosave=True)

        assert save_id == "existing-save-id"
        sql, params = db.execute.call_args_list[-1].args
        assert "UPDATE saves" in sql
        assert params[-1] == "existing-save-id"

    async def test_disabled_autosave_touches_nothing(self, game_service, player, db):
        """Issue #450: ``GameConfig.autosave_enabled=False`` is a hard skip."""
        from src.config_manager import GameConfig

        player.game_config = GameConfig(autosave_enabled=False)

        assert (
            await game_service.save_game(player, "Auto", "user123", is_autosave=True)
            is None
        )
        db.execute.assert_not_called()

    async def test_disabled_autosave_does_not_block_manual_saves(
        self, game_service, player, db
    ):
        from src.config_manager import GameConfig

        player.game_config = GameConfig(autosave_enabled=False)
        db.execute.side_effect = [_result(rows=[[0]]), _result()]

        assert await game_service.save_game(player, "Manual", "user123") is not None


@pytest.mark.asyncio
class TestLoadGame:
    """``load_game`` restores a player and scrubs transient combat state."""

    @staticmethod
    async def _round_trip(game_service, player, db):
        db.execute.side_effect = [_result(rows=[[0]]), _result()]
        await game_service.save_game(player, "S", "user123")
        blob = _saved_blob(db)
        db.execute.side_effect = None
        db.execute.return_value = _result(rows=[[blob]])
        return await game_service.load_game("save-id", "user123")

    async def test_restores_the_player_state(self, game_service, player, db):
        player.hp = 33
        loaded = await self._round_trip(game_service, player, db)
        assert loaded.name == player.name
        assert loaded.hp == 33

    async def test_scopes_the_query_to_the_owning_user(self, game_service, db):
        db.execute.return_value = _result(rows=[])
        await game_service.load_game("save-id", "user123")
        sql, params = db.execute.call_args.args
        assert "WHERE id = ? AND user_id = ?" in sql
        assert params == ["save-id", "user123"]

    async def test_a_missing_save_returns_none(self, game_service, db):
        db.execute.return_value = _result(rows=[])
        assert await game_service.load_game("nope", "user123") is None

    async def test_a_corrupt_payload_returns_none_instead_of_raising(
        self, game_service, db
    ):
        db.execute.return_value = _result(rows=[[b"not a pickle at all"]])
        assert await game_service.load_game("save-id", "user123") is None

    async def test_never_resumes_mid_fight(self, game_service, player, db):
        """A save taken during combat must load out of combat, not into a phantom one."""
        player.in_combat = True

        loaded = await self._round_trip(game_service, player, db)

        assert loaded.in_combat is False
        assert loaded.combat_list == []
        assert loaded.current_move is None

    async def test_non_persistent_states_are_stripped(self, game_service, player, db):
        player.states = [TransientState(), LastingState()]

        loaded = await self._round_trip(game_service, player, db)

        assert [s.name for s in loaded.states] == ["Poisoned"]

    async def test_the_party_list_always_starts_with_the_player(
        self, game_service, player, db
    ):
        loaded = await self._round_trip(game_service, player, db)
        assert loaded.combat_list_allies[0] is loaded

    async def test_current_room_is_rebound_to_the_live_tile(
        self, game_service, player, db
    ):
        player.location_x, player.location_y = 1, 0
        loaded = await self._round_trip(game_service, player, db)
        assert loaded.current_room is loaded.universe.get_tile(1, 0)


@pytest.mark.asyncio
class TestListSaves:
    """``list_saves`` denormalises rows for the Load Game screen."""

    ROW = (
        "abc-123",
        "MySave",
        "2026-04-23 22:15:00",
        0,
        7,
        "Dark Grotto",
        "Entry Hall",
        3600,
    )

    async def test_maps_columns_onto_the_wire_fields(self, game_service, db):
        db.execute.return_value = _result(rows=[self.ROW])

        saves = await game_service.list_saves("user123", timezone="UTC")

        assert saves[0]["id"] == "abc-123"
        assert saves[0]["name"] == "MySave"
        assert saves[0]["is_autosave"] is False
        assert saves[0]["level"] == 7
        assert saves[0]["map_name"] == "Dark Grotto"
        assert saves[0]["room_title"] == "Entry Hall"
        assert saves[0]["playtime"] == 3600

    async def test_timestamp_ms_is_display_timezone_independent(self, game_service, db):
        """The epoch key is derived before the display conversion (see localSave.js).

        ``Date.parse`` cannot read most non-US timezone abbreviations, which is
        why the frontend sorts on ``timestamp_ms`` rather than the display string.
        """
        db.execute.return_value = _result(rows=[self.ROW])

        utc = await game_service.list_saves("user123", timezone="UTC")
        tokyo = await game_service.list_saves("user123", timezone="Asia/Tokyo")

        # 2026-04-23 22:15:00 UTC as epoch milliseconds.
        assert utc[0]["timestamp_ms"] == tokyo[0]["timestamp_ms"] == 1776982500000
        assert utc[0]["timestamp"] != tokyo[0]["timestamp"]

    async def test_display_timestamp_is_localised(self, game_service, db):
        db.execute.return_value = _result(rows=[self.ROW])
        saves = await game_service.list_saves("user123", timezone="UTC")
        assert saves[0]["timestamp"] == "2026-04-23 22:15:00 UTC"

    async def test_an_unparseable_timestamp_falls_back_without_a_sort_key(
        self, game_service, db
    ):
        row = list(self.ROW)
        row[2] = "sometime last tuesday"
        db.execute.return_value = _result(rows=[row])

        saves = await game_service.list_saves("user123")

        assert saves[0]["timestamp"] == "sometime last tuesday"
        assert saves[0]["timestamp_ms"] is None

    async def test_an_unknown_timezone_falls_back_to_the_default(self, game_service, db):
        db.execute.return_value = _result(rows=[self.ROW])
        saves = await game_service.list_saves("user123", timezone="Mars/Olympus_Mons")
        assert saves[0]["timestamp"].endswith("EDT")

    async def test_missing_columns_get_placeholders(self, game_service, db):
        row = list(self.ROW)
        row[4] = row[5] = row[6] = row[7] = None
        db.execute.return_value = _result(rows=[row])

        saves = await game_service.list_saves("user123")

        assert saves[0]["level"] == "?"
        assert saves[0]["map_name"] == "Unknown"
        assert saves[0]["room_title"] == "Unknown"
        assert saves[0]["playtime"] == 0

    async def test_no_saves_yields_an_empty_list(self, game_service, db):
        db.execute.return_value = _result(rows=[])
        assert await game_service.list_saves("user123") == []

    async def test_query_is_ordered_newest_first(self, game_service, db):
        db.execute.return_value = _result(rows=[])
        await game_service.list_saves("user123")
        sql, params = db.execute.call_args.args
        assert "ORDER BY timestamp DESC" in sql
        assert params == ["user123"]


@pytest.mark.asyncio
class TestDeleteSave:
    """``delete_save`` reports whether a row actually went away."""

    async def test_reports_true_when_a_row_was_removed(self, game_service, db):
        db.execute.return_value = _result(rows_affected=1)
        assert await game_service.delete_save("abc", "user123") is True

    async def test_reports_false_when_nothing_matched(self, game_service, db):
        db.execute.return_value = _result(rows_affected=0)
        assert await game_service.delete_save("abc", "user123") is False

    async def test_deletion_is_scoped_to_the_owning_user(self, game_service, db):
        """Without the user_id predicate one player could delete another's saves."""
        db.execute.return_value = _result(rows_affected=1)
        await game_service.delete_save("abc", "user123")
        sql, params = db.execute.call_args.args
        assert "DELETE FROM saves WHERE id = ? AND user_id = ?" in sql
        assert params == ["abc", "user123"]


class TestSavesDirectory:
    """``_get_saves_dir`` is the on-disk fallback location."""

    def test_returns_an_existing_saves_directory(self, game_service):
        import os

        path = game_service._get_saves_dir()
        assert os.path.basename(path) == "saves"
        assert os.path.isdir(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
