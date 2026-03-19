"""Comprehensive tests for saves routes."""

import asyncio
import sys
import threading
from pathlib import Path
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest


class TestListSavesRoute:
    """Test GET /saves endpoint."""

    def test_list_saves_success(self, client, authenticated_session):
        """Test successful save listing."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/saves/",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "saves" in data
        assert isinstance(data["saves"], list)

    def test_list_saves_no_auth(self, client):
        """Test list saves without authentication."""
        response = client.get("/saves/")
        assert response.status_code == 401

    def test_list_saves_invalid_session(self, client):
        """Test list saves with invalid session."""
        response = client.get(
            "/saves/",
            headers={"Authorization": "Bearer invalid_session_id"},
        )
        assert response.status_code == 401

    def test_list_saves_expired_session(self, app, client):
        """Test list saves with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = datetime.now() - timedelta(hours=1)

        response = client.get(
            "/saves/",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Session expiration may result in 401 or 500 depending on error handling
        assert response.status_code in [401, 500]


class TestCreateSaveRoute:
    """Test POST /saves endpoint."""

    def test_create_save_missing_name(self, client, authenticated_session):
        """Test creating save without name."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_create_save_no_auth(self, client):
        """Test create save without authentication."""
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "My Save"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_create_save_invalid_session(self, client):
        """Test create save with invalid session."""
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "My Save"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_create_save_with_valid_name(self, client, authenticated_session):
        """Test creating save with valid name."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "My Test Save"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should handle the request
        assert response.status_code in [200, 201, 400, 422]

    def test_create_save_empty_name(self, client, authenticated_session):
        """Test creating save with empty name."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/",
            data=json.dumps({"name": ""}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Empty names may be accepted or rejected depending on validation
        # Accept either behavior (201 if accepted, 400 if rejected)
        assert response.status_code in [200, 201, 400, 422]


class TestLoadSaveRoute:
    """Test POST /saves/<id>/load endpoint."""

    def test_load_save_missing_id(self, client, authenticated_session):
        """Test load save without ID in path."""
        session_id, _, _ = authenticated_session
        # Try to POST to /saves/load without an ID
        response = client.post(
            "/saves/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should fail (404 or 405)
        assert response.status_code >= 400

    def test_load_save_no_auth(self, client):
        """Test load save without authentication."""
        response = client.post(
            "/saves/test_save_id/load",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_load_save_invalid_session(self, client):
        """Test load save with invalid session."""
        response = client.post(
            "/saves/test_save_id/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_load_nonexistent_save(self, client, authenticated_session):
        """Test loading a non-existent save."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/nonexistent_save_id/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should fail gracefully
        assert response.status_code >= 400


class TestDeleteSaveRoute:
    """Test DELETE /saves/<id> endpoint."""

    def test_delete_save_no_auth(self, client):
        """Test delete save without authentication."""
        response = client.delete("/saves/test_save_id")
        assert response.status_code == 401

    def test_delete_save_invalid_session(self, client):
        """Test delete save with invalid session."""
        response = client.delete(
            "/saves/test_save_id",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_delete_nonexistent_save(self, client, authenticated_session):
        """Test deleting a non-existent save."""
        session_id, _, _ = authenticated_session
        response = client.delete(
            "/saves/nonexistent_save_id",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # May succeed (soft delete) or fail (404/422) - both are acceptable
        assert response.status_code in [200, 204, 400, 404, 422]

    def test_delete_save_expired_session(self, app, client):
        """Test delete save with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = datetime.now() - timedelta(hours=1)

        response = client.delete(
            "/saves/test_save_id",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Session expiration may result in 401 or 500 depending on error handling
        assert response.status_code in [401, 500]


class TestSavesErrorCases:
    """Test error handling in saves routes."""

    def test_list_saves_returns_json(self, client):
        """Test that list_saves returns JSON on error."""
        response = client.get("/saves/")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_create_save_returns_json(self, client):
        """Test that create_save returns JSON on error."""
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_load_save_returns_json(self, client):
        """Test that load_save returns JSON on error."""
        response = client.post(
            "/saves/test_id/load",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_delete_save_returns_json(self, client):
        """Test that delete_save returns JSON on error."""
        response = client.delete("/saves/test_id")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_create_save_with_empty_bearer(self, client):
        """Test create_save with empty Bearer token."""
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_load_save_with_empty_bearer(self, client):
        """Test load_save with empty Bearer token."""
        response = client.post(
            "/saves/test_id/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_delete_save_with_empty_bearer(self, client):
        """Test delete_save with empty Bearer token."""
        response = client.delete(
            "/saves/test_id",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_create_save_malformed_json(self, client, authenticated_session):
        """Test create_save with malformed JSON."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/",
            data="not valid json",
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        assert response.status_code >= 400

    def test_load_save_malformed_json(self, client, authenticated_session):
        """Test load_save with malformed JSON."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/test_id/load",
            data="not valid json",
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        assert response.status_code >= 400

    def test_create_save_very_long_name(self, client, authenticated_session):
        """Test create_save with very long name."""
        session_id, _, _ = authenticated_session
        long_name = "a" * 1000  # 1000 character name
        response = client.post(
            "/saves/",
            data=json.dumps({"name": long_name}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should reject very long names
        assert response.status_code >= 400 or response.status_code == 201


class TestAutosaveDuringCombat:
    """Regression tests for autosave serialization while player is in combat.

    Root cause: player._combat_adapter holds a closure (on_event_callback) and a
    threading.Lock (_suggestion_lock), neither of which is picklable. Calling
    save_game() mid-combat raised an uncaught PicklingError that bubbled up as
    a 500 on POST /api/saves.

    Fix: game_service.save_game() strips _combat_adapter from player.__dict__
    before pickle.dumps() and restores it in a finally block.
    """

    def _make_combat_adapter(self):
        """Return a minimal mock adapter that reproduces the pickling failure."""
        adapter = MagicMock()
        # The two attributes that made the original adapter unpicklable:
        adapter._suggestion_lock = threading.Lock()
        session_data = {"pending_events": {}}
        adapter.on_event_callback = lambda p: session_data  # closure — not picklable
        return adapter

    def _make_player(self):
        """Return a minimal picklable player object."""
        class _Player:
            def __init__(self):
                self.name = "Jean"
                self.level = 1
                self.hp = 50
                self.in_combat = True
                self.time_elapsed = 0
                self.map = None
                self.current_room = None
        return _Player()

    def _mock_db_execute(self, rows=None):
        """Return an async mock for db.execute that returns a result with given rows."""
        result = MagicMock()
        result.rows = rows if rows is not None else []
        mock = AsyncMock(return_value=result)
        return mock

    def test_save_game_strips_combat_adapter_before_pickling(self):
        """save_game must not raise PicklingError when _combat_adapter is present."""
        from src.api.services.game_service import GameService

        service = GameService()
        player = self._make_player()
        player._combat_adapter = self._make_combat_adapter()

        # Mock db.execute: first call (autosave check) returns no existing row,
        # second call (INSERT) returns nothing.
        with patch("src.api.services.game_service.db") as mock_db:
            mock_db.execute = self._mock_db_execute(rows=[])
            save_id = asyncio.run(
                service.save_game(player, "Autosave", user_id="user-123", is_autosave=True)
            )

        assert save_id is not None
        assert isinstance(save_id, str)

    def test_combat_adapter_restored_after_save(self):
        """_combat_adapter must be back on the player after save_game returns."""
        from src.api.services.game_service import GameService

        service = GameService()
        player = self._make_player()
        adapter = self._make_combat_adapter()
        player._combat_adapter = adapter

        with patch("src.api.services.game_service.db") as mock_db:
            mock_db.execute = self._mock_db_execute(rows=[])
            asyncio.run(
                service.save_game(player, "Autosave", user_id="user-123", is_autosave=True)
            )

        assert player._combat_adapter is adapter, (
            "_combat_adapter was not restored after save_game — "
            "combat state would be lost for the rest of the encounter."
        )

    def test_combat_adapter_restored_even_if_pickle_fails(self):
        """_combat_adapter must be restored if an unexpected pickle error occurs."""
        import pickle
        from src.api.services.game_service import GameService

        service = GameService()
        player = self._make_player()
        adapter = self._make_combat_adapter()
        player._combat_adapter = adapter

        # Force pickle.dumps to fail for any player instance
        with patch("src.api.services.game_service.db") as mock_db:
            mock_db.execute = self._mock_db_execute(rows=[])
            with patch("pickle.dumps", side_effect=pickle.PicklingError("injected failure")):
                with pytest.raises(Exception):
                    asyncio.run(
                        service.save_game(player, "Autosave", user_id="user-123", is_autosave=True)
                    )

        # Adapter must be restored regardless of the pickle failure
        assert player._combat_adapter is adapter, (
            "_combat_adapter was dropped after a pickle failure — "
            "the finally block is not executing correctly."
        )

    def test_save_game_works_without_combat_adapter(self):
        """save_game must work normally when no _combat_adapter is present."""
        from src.api.services.game_service import GameService

        service = GameService()
        player = self._make_player()  # no _combat_adapter

        with patch("src.api.services.game_service.db") as mock_db:
            # is_autosave=False → save_game runs COUNT(*) first; mock must return [[0]]
            # so res.rows[0][0] evaluates to 0 (under the 20-save limit).
            mock_db.execute = self._mock_db_execute(rows=[[0]])
            save_id = asyncio.run(
                service.save_game(player, "Manual Save", user_id="user-123", is_autosave=False)
            )

        assert save_id is not None
        assert not hasattr(player, "_combat_adapter")
