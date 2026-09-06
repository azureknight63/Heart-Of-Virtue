"""Comprehensive tests for saves routes.

Every URL literal in this file is contract-checked by
``tests/api/test_route_prefix_contract.py``: a URL with no rule in
``app.url_map`` fails there, and so does a request whose verb the matching
rule does not serve -- ``test_delete_rule_rejects_a_post_to_saves_load``
below is the one deliberate exception, registered in that guard's
``ALLOWED_METHOD_MISMATCH``.
"""

import asyncio
import sys
import threading
from pathlib import Path
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent.parent


import pytest


class _SavePlayer:
    """Minimal picklable stand-in for a Player in save_game tests.

    Must live at module scope: pickle records a class by import path, so a
    class defined inside a test method cannot be pickled at all -- which is
    what these tests used to trip over before they reached the behaviour they
    are actually about.
    """

    def __init__(self):
        self.name = "Jean"
        self.level = 1
        self.hp = 50
        self.in_combat = True
        self.time_elapsed = 0
        self.map = None
        self.current_room = None


def _db_stub(rows=None, rows_affected=0):
    """An AsyncMock standing in for `src.api.db.db`.

    `game_service` imports `db` inside each method (`from src.api.db import
    db`), so `src.api.db.db` -- not a module attribute on game_service -- is
    the only patchable target.
    """
    result = MagicMock()
    result.rows = rows if rows is not None else []
    result.rows_affected = rows_affected
    stub = MagicMock()
    stub.execute = AsyncMock(return_value=result)
    return stub


@pytest.fixture
def cloud_session(app):
    """A session linked to a DB user, so cloud-save routes run for real.

    A plain test session has no `db_user_id` and every saves route 403s before
    doing anything (see CLAUDE.md, "How auth works"). Tests that want the
    actual save/load/delete behaviour need this.
    """
    session_manager = app.session_manager
    session_id, _ = session_manager.create_session("clouduser")
    session = session_manager.get_session(session_id)
    session.db_user_id = "user-123"
    return session_id


class TestListSavesRoute:
    """Test GET /saves endpoint."""

    def test_list_saves_success(self, client, cloud_session):
        """Test successful save listing."""
        row = ("save-1", "My Save", "2026-04-23 18:15:00", False, 3, "dark-grotto", "Cave", 120)
        with patch("src.api.db.db", _db_stub(rows=[row])):
            response = client.get(
                "/api/saves",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert isinstance(data["saves"], list)
        assert len(data["saves"]) == 1
        save = data["saves"][0]
        assert save["id"] == "save-1"
        assert save["name"] == "My Save"
        assert save["level"] == 3
        # timestamp_ms is the display-timezone-independent sort key the save
        # list orders on (see compareSavesByRecency).
        assert save["timestamp_ms"] == 1776968100000  # 2026-04-23T18:15:00Z

    def test_list_saves_without_db_account(self, client, authenticated_session):
        """A session with no db_user_id gets an empty list, not an error.

        Only reachable through the test-session bypass (QA/Inquisitor runs).
        """
        session_id, _, _ = authenticated_session
        response = client.get(
            "/api/saves",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["saves"] == []

    def test_list_saves_no_auth(self, client):
        """Test list saves without authentication."""
        response = client.get("/api/saves")
        assert response.status_code == 401

    def test_list_saves_invalid_session(self, client):
        """Test list saves with invalid session."""
        response = client.get(
            "/api/saves",
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
            "/api/saves",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Deterministically 401: resolve_session answers "Session not found or
        # already expired" (src/api/middleware/auth.py:84) for an unknown or
        # expired session id. The only 500 on that path is a missing session
        # manager -- a server fault, not an auth outcome -- so accepting 500
        # here would let a real regression that leaked one through pass.
        assert response.status_code == 401


class TestCreateSaveRoute:
    """Test POST /saves endpoint."""

    def test_create_save_missing_name(self, client, cloud_session):
        """Test creating save without name."""
        response = client.post(
            "/api/saves",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {cloud_session}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_create_save_without_db_account(self, client, authenticated_session):
        """Cloud saves are refused for a session with no registered account."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/saves",
            data=json.dumps({"name": "My Save"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data["success"] is False

    def test_create_save_no_auth(self, client):
        """Test create save without authentication."""
        response = client.post(
            "/api/saves",
            data=json.dumps({"name": "My Save"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_create_save_invalid_session(self, client):
        """Test create save with invalid session."""
        response = client.post(
            "/api/saves",
            data=json.dumps({"name": "My Save"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_create_save_with_valid_name(self, client, cloud_session):
        """Test creating save with valid name."""
        # rows=[[0]] -> the manual-save COUNT(*) sees 0 existing saves.
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": "My Test Save"}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["save_id"]
        assert "My Test Save" in data["message"]

    def test_create_save_autosave_without_name_uses_default(self, client, cloud_session):
        """An autosave POSTed as just {"is_autosave": true} still succeeds.

        The name is then internally generated (DEFAULT_SAVE_NAME), so
        validate_save_name is never reached -- issue #523's validation must not
        be able to reject a save whose name the server chose itself.
        """
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"is_autosave": True}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["success"] is True

    def test_create_save_autosave_literal_name_accepted(self, client, cloud_session):
        """The name useAutosave actually sends ("Autosave") passes validation.

        frontend/src/hooks/useApi.js posts `{"name": "Autosave",
        "is_autosave": true}`. Guards against a validation rule that would
        silently break the only save written during active play.
        """
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": "Autosave", "is_autosave": True}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 201
        assert json.loads(response.data)["success"] is True


class TestCreateSaveNameValidation:
    """POST /saves save-name validation (issue #523).

    These tests replace three that deliberately pinned the *unvalidated*
    behaviour ("", a 1000-char name and `None` were all stored verbatim, and
    list_saves rendered `None` as the literal string "None"). Their docstrings
    said a future cap should make them fail so they could be updated
    deliberately -- this is that update. They now assert the new contract
    explicitly rather than whatever the route happens to do.

    The rules are deliberately conservative and are all sourced from
    `src.api.routes.saves`: reject rather than repair, so a mistake is
    reported instead of being silently rewritten.
    """

    @pytest.mark.parametrize(
        "bad_name, reason",
        [
            ("", "empty string"),
            ("   ", "whitespace only"),
            ("\t\n ", "whitespace-only control characters"),
            ("\x00", "NUL, which str.strip() does not remove"),
            ("\u200b", "ZERO WIDTH SPACE, which str.strip() does not remove"),
            ("\ufeff", "BOM, which str.strip() does not remove"),
            ("  \x00\u200b  ", "padding around invisible codepoints"),
        ],
    )
    def test_blank_name_rejected(self, client, cloud_session, bad_name, reason):
        """Blank names 400 rather than being auto-named.

        Auto-naming would hide a player mistake; a blank row in the load list
        is exactly the symptom issue #523 reports.

        "Blank" means "renders as nothing", not "is whitespace-only": the last
        four cases survive ``.strip()`` intact but still display as an empty
        row, so validate_string_field's rule is visibility-based (see
        ``has_visible_characters``).
        """
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": bad_name}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 400, reason
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"] == "Save name is required"

    @pytest.mark.parametrize("bad_name", [None, 42, 3.5, True, ["a"], {"a": 1}])
    def test_non_string_name_rejected(self, client, cloud_session, bad_name):
        """Non-string names 400 -- no coercion.

        `None` in particular used to be stored verbatim and rendered by
        list_saves as the literal string "None".
        """
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": bad_name}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"] == "Save name must be a string"

    def test_name_at_max_length_accepted(self, client, cloud_session):
        """Exactly MAX_SAVE_NAME_LENGTH characters is allowed (boundary)."""
        from src.api.routes.saves import MAX_SAVE_NAME_LENGTH

        name = "a" * MAX_SAVE_NAME_LENGTH
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": name}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 201
        assert json.loads(response.data)["success"] is True

    def test_name_one_over_max_length_rejected(self, client, cloud_session):
        """One character past the cap is refused (boundary)."""
        from src.api.routes.saves import MAX_SAVE_NAME_LENGTH

        name = "a" * (MAX_SAVE_NAME_LENGTH + 1)
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": name}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert str(MAX_SAVE_NAME_LENGTH) in data["error"]

    def test_very_long_name_rejected_not_truncated(self, client, cloud_session):
        """A 1000-character name 400s instead of being silently truncated.

        Truncation would discard the player's intent without telling them.
        The 201 this used to return is the defect in issue #523.
        """
        long_name = "a" * 1000
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": long_name}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        # The rejection names the offending length so the player can see how
        # far over the cap they were.
        assert "1000" in data["error"]

    def test_name_is_stripped_before_storing(self, client, cloud_session):
        """Surrounding whitespace is removed before validating and storing.

        The echoed message carries the stored name, so it is the observable
        proof that the padded form was not persisted.
        """
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": "   Padded Save   "}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["message"] == "Game saved: Padded Save"

    def test_stripping_can_bring_a_name_under_the_cap(self, client, cloud_session):
        """Length is measured after stripping, not before."""
        from src.api.routes.saves import MAX_SAVE_NAME_LENGTH

        name = " " * 50 + "a" * MAX_SAVE_NAME_LENGTH + " " * 50
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": name}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 201
        assert json.loads(response.data)["success"] is True

    def test_blank_name_is_rejected_even_for_an_autosave(self, client, cloud_session):
        """A caller-supplied blank name is refused regardless of is_autosave.

        Validation applies to what the *caller* sent; only a name the server
        generates itself (no "name" key at all) skips it.
        """
        with patch("src.api.db.db", _db_stub(rows=[[0]])):
            response = client.post(
                "/api/saves",
                data=json.dumps({"name": "  ", "is_autosave": True}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 400
        assert json.loads(response.data)["success"] is False


class TestLoadSaveRoute:
    """Test POST /saves/<id>/load endpoint."""

    def test_delete_rule_rejects_a_post_to_saves_load(
        self, client, authenticated_session
    ):
        """POST /api/saves/load is a 405 from the DELETE-only rule.

        Nothing here reaches the load endpoint: ``/api/saves/load`` matches
        ``/api/saves/<save_id>`` with ``save_id="load"``, and that rule serves
        DELETE only, so Werkzeug refuses the verb while routing and the view
        never runs. Named ``test_load_save_missing_id`` while it asserted
        ``>= 400``, which said neither what it hit nor why.
        """
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/saves/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        assert response.status_code == 405
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"] == "Method not allowed"

    def test_load_save_no_auth(self, client):
        """Test load save without authentication."""
        response = client.post(
            "/api/saves/test_save_id/load",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_load_save_invalid_session(self, client):
        """Test load save with invalid session."""
        response = client.post(
            "/api/saves/test_save_id/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_load_nonexistent_save(self, client, cloud_session):
        """Test loading a non-existent save."""
        with patch("src.api.db.db", _db_stub(rows=[])):
            response = client.post(
                "/api/saves/nonexistent_save_id/load",
                data=json.dumps({}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_load_save_without_db_account(self, client, authenticated_session):
        """Loading a cloud save is refused without a registered account."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/saves/any_save_id/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 403


class TestDeleteSaveRoute:
    """Test DELETE /saves/<id> endpoint."""

    def test_delete_save_no_auth(self, client):
        """Test delete save without authentication."""
        response = client.delete("/api/saves/test_save_id")
        assert response.status_code == 401

    def test_delete_save_invalid_session(self, client):
        """Test delete save with invalid session."""
        response = client.delete(
            "/api/saves/test_save_id",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_delete_nonexistent_save(self, client, cloud_session):
        """Deleting a save that is not there (or not yours) is a 404."""
        with patch("src.api.db.db", _db_stub(rows_affected=0)):
            response = client.delete(
                "/api/saves/nonexistent_save_id",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_delete_existing_save(self, client, cloud_session):
        """A row actually removed reports success."""
        with patch("src.api.db.db", _db_stub(rows_affected=1)):
            response = client.delete(
                "/api/saves/save-1",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_delete_save_expired_session(self, app, client):
        """Test delete save with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = datetime.now() - timedelta(hours=1)

        response = client.delete(
            "/api/saves/test_save_id",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Deterministically 401: resolve_session answers "Session not found or
        # already expired" (src/api/middleware/auth.py:84) for an unknown or
        # expired session id. The only 500 on that path is a missing session
        # manager -- a server fault, not an auth outcome -- so accepting 500
        # here would let a real regression that leaked one through pass.
        assert response.status_code == 401


class TestSavesErrorCases:
    """Test error handling in saves routes."""

    def test_list_saves_returns_json(self, client):
        """Test that list_saves returns JSON on error."""
        response = client.get("/api/saves")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_create_save_returns_json(self, client):
        """Test that create_save returns JSON on error."""
        response = client.post(
            "/api/saves",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_load_save_returns_json(self, client):
        """Test that load_save returns JSON on error."""
        response = client.post(
            "/api/saves/test_id/load",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_delete_save_returns_json(self, client):
        """Test that delete_save returns JSON on error."""
        response = client.delete("/api/saves/test_id")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_create_save_with_empty_bearer(self, client):
        """Test create_save with empty Bearer token."""
        response = client.post(
            "/api/saves",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_load_save_with_empty_bearer(self, client):
        """Test load_save with empty Bearer token."""
        response = client.post(
            "/api/saves/test_id/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_delete_save_with_empty_bearer(self, client):
        """Test delete_save with empty Bearer token."""
        response = client.delete(
            "/api/saves/test_id",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_create_save_malformed_json(self, client, cloud_session):
        """Malformed JSON is a 400, not a crash.

        (These three used a session with no db_user_id, so they never got past
        the 403 guard -- `>= 400` was satisfied by the 403 alone and the route
        body never ran.)
        """
        response = client.post(
            "/api/saves",
            data="not valid json",
            content_type="application/json",
            headers={"Authorization": f"Bearer {cloud_session}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_load_save_malformed_json(self, client, cloud_session):
        """load_save never reads the request body, so a bad one is harmless.

        The save id comes from the URL; the 404 here is the missing save, not
        the unparseable body.
        """
        with patch("src.api.db.db", _db_stub(rows=[])):
            response = client.post(
                "/api/saves/test_id/load",
                data="not valid json",
                content_type="application/json",
                headers={"Authorization": f"Bearer {cloud_session}"},
            )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False


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
        return _SavePlayer()

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
        with patch("src.api.db.db") as mock_db:
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

        with patch("src.api.db.db") as mock_db:
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
        with patch("src.api.db.db") as mock_db:
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

        with patch("src.api.db.db") as mock_db:
            # is_autosave=False → save_game runs COUNT(*) first; mock must return [[0]]
            # so res.rows[0][0] evaluates to 0 (under the 20-save limit).
            mock_db.execute = self._mock_db_execute(rows=[[0]])
            save_id = asyncio.run(
                service.save_game(player, "Manual Save", user_id="user-123", is_autosave=False)
            )

        assert save_id is not None
        assert not hasattr(player, "_combat_adapter")
