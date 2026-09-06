"""
Coverage-gap tests for API routes.

Targets:
- src/api/routes/saves.py  (42% -> ~90%)
- src/api/routes/equipment.py  (88% -> ~100%)
- src/api/routes/logs.py  (79% -> ~100%)

Strategy: minimal Flask app using mocked session_manager and game_service,
mirroring the pattern in test_api_routes_and_serializers.py.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from flask import Flask

# ---------------------------------------------------------------------------
# Shared helpers (mirror test_api_routes_and_serializers.py)
# ---------------------------------------------------------------------------


def _make_player():
    p = MagicMock()
    p.name = "Jean Claire"
    p.hp = 100
    p.maxhp = 100
    p.level = 1
    return p


def _make_game_service():
    gs = MagicMock()
    gs.list_saves = AsyncMock(return_value=[{"id": "s1", "name": "Save 1"}])
    gs.save_game = AsyncMock(return_value="new_save_id")
    gs.load_game = AsyncMock(return_value=MagicMock())
    gs.delete_save = AsyncMock(return_value=True)
    gs.get_equipment.return_value = {"head": None, "body": None}
    gs.equip_item.return_value = {"item_id": "sword_01", "stat_changes": {}}
    gs.unequip_item.return_value = {"slot": "hands", "stat_changes": {}}
    return gs


AUTH = {"Authorization": "Bearer sid_001"}
NO_AUTH = {}
BAD_AUTH = {"Authorization": "NotBearer sid_001"}


@pytest.fixture
def minimal_app(make_stub_session, make_stub_session_manager):
    """Build a one-blueprint Flask app on the shared session/manager stubs.

    ``make_stub_session`` returns a *real* ``Session`` rather than a MagicMock,
    so an attribute the routes read but ``Session`` does not define raises here
    instead of being invented; ``make_stub_session_manager`` is
    ``spec``-constrained for the same reason. Blueprint registration stays
    local because these routes mount under a ``/api`` prefix and the shared
    ``make_route_app`` registers at the app root.
    """

    def _minimal_app(bp, prefix=None):
        session = make_stub_session(
            session_id="sid_001",
            db_user_id="db_user_1",
            timezone="America/New_York",
        )
        player = _make_player()
        sm = make_stub_session_manager(session, player)
        gs = _make_game_service()

        app = Flask(__name__)
        app.config["TESTING"] = True
        if prefix is None:
            app.register_blueprint(bp)
        else:
            app.register_blueprint(bp, url_prefix=prefix)

        app.session_manager = sm
        app.game_service = gs
        app._test_session = session
        app._test_player = player
        app._test_sm = sm
        app._test_gs = gs
        return app

    return _minimal_app


# ===========================================================================
# saves.py
# ===========================================================================


class TestSavesRoutes:
    """Tests for routes/saves.py."""

    @pytest.fixture
    def app(self, minimal_app):
        from src.api.routes.saves import saves_bp

        return minimal_app(saves_bp, prefix="/api")

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    # ---- list_saves ----

    def test_list_saves_success(self, client):
        rv = client.get("/api/saves", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert isinstance(data["saves"], list)

    def test_list_saves_no_auth(self, client):
        rv = client.get("/api/saves", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_list_saves_bad_auth(self, client):
        rv = client.get("/api/saves", headers=BAD_AUTH)
        assert rv.status_code == 401

    def test_list_saves_no_db_user_id(self, app, make_stub_session):
        """Session without db_user_id returns empty saves list."""
        session = make_stub_session(session_id="sid_002", db_user_id=None)
        app._test_sm.get_session.return_value = session
        with app.test_client() as c:
            rv = c.get("/api/saves", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["saves"] == []

    def test_list_saves_invalid_session(self, app):
        app._test_sm.get_session.return_value = None
        with app.test_client() as c:
            rv = c.get("/api/saves", headers=AUTH)
        assert rv.status_code == 401

    def test_list_saves_player_not_found(self, app):
        app._test_sm.get_player.return_value = None
        with app.test_client() as c:
            rv = c.get("/api/saves", headers=AUTH)
        assert rv.status_code == 404

    def test_list_saves_exception(self, app):
        app._test_gs.list_saves = AsyncMock(side_effect=RuntimeError("DB down"))
        with app.test_client() as c:
            rv = c.get("/api/saves", headers=AUTH)
        assert rv.status_code == 500

    # ---- create_save ----

    def test_create_save_success(self, client):
        rv = client.post(
            "/api/saves",
            headers=AUTH,
            json={"name": "My Save"},
        )
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["success"] is True
        assert "save_id" in data

    def test_create_save_autosave(self, client):
        rv = client.post(
            "/api/saves",
            headers=AUTH,
            json={"is_autosave": True},
        )
        assert rv.status_code == 201
        data = rv.get_json()
        assert "autosave" in data["message"].lower()

    def test_create_save_no_db_user(self, app, make_stub_session):
        session = make_stub_session(session_id="sid_002", db_user_id=None)
        app._test_sm.get_session.return_value = session
        with app.test_client() as c:
            rv = c.post("/api/saves", headers=AUTH, json={"name": "X"})
        assert rv.status_code == 403

    def test_create_save_missing_body(self, client):
        rv = client.post("/api/saves", headers=AUTH, json={})
        assert rv.status_code == 400

    def test_create_save_value_error_limit(self, app):
        app._test_gs.save_game = AsyncMock(side_effect=ValueError("Too many saves"))
        with app.test_client() as c:
            rv = c.post("/api/saves", headers=AUTH, json={"name": "Extra"})
        assert rv.status_code == 403
        data = rv.get_json()
        assert "Too many saves" in data["error"]

    def test_create_save_no_auth(self, client):
        rv = client.post("/api/saves", headers=NO_AUTH, json={"name": "X"})
        assert rv.status_code == 401

    def test_create_save_exception(self, app):
        app._test_gs.save_game = AsyncMock(side_effect=RuntimeError("crash"))
        with app.test_client() as c:
            rv = c.post("/api/saves", headers=AUTH, json={"name": "X"})
        assert rv.status_code == 500

    # ---- create_save: name validation (issue #523) ----
    #
    # The comprehensive version of this contract lives in
    # tests/api/test_routes_saves_comprehensive.py, but tests/api/ is excluded
    # from the default pytest run (and from the pre-commit hook), so the rules
    # are re-asserted here against the mocked-session_manager app. Without
    # this, a regression in validate_save_name would only surface in the
    # separate CI job that walks tests/api/ one file per process.

    @pytest.mark.parametrize(
        "bad_name", ["", "   ", "\t\n ", "\x00", "\u200b", "\ufeff", "  \x00  "]
    )
    def test_create_save_blank_name_rejected(self, client, bad_name):
        """Blank names 400 rather than being auto-named.

        "Blank" is visibility-based, not whitespace-based: NUL, U+200B and the
        BOM all survive ``.strip()`` yet still render as the empty load-list row
        issue #523 reports.
        """
        rv = client.post("/api/saves", headers=AUTH, json={"name": bad_name})
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False
        assert data["error"] == "Save name is required"

    @pytest.mark.parametrize("bad_name", [None, 42, 3.5, True, ["a"], {"a": 1}])
    def test_create_save_non_string_name_rejected(self, client, bad_name):
        """Non-string names 400 -- no coercion.

        ``None`` in particular used to be stored verbatim and then rendered by
        ``list_saves`` (which does ``str(row[1])``) as the literal "None".
        """
        rv = client.post("/api/saves", headers=AUTH, json={"name": bad_name})
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False
        assert data["error"] == "Save name must be a string"

    def test_create_save_over_max_length_rejected_not_truncated(self, client, app):
        """A too-long name 400s and nothing is written.

        Truncating would silently discard the player's intent, so the route
        refuses; asserting ``save_game`` was never awaited is what proves no
        truncated row reached the database.
        """
        from src.api.routes.saves import MAX_SAVE_NAME_LENGTH

        rv = client.post(
            "/api/saves",
            headers=AUTH,
            json={"name": "a" * (MAX_SAVE_NAME_LENGTH + 1)},
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False
        assert str(MAX_SAVE_NAME_LENGTH) in data["error"]
        app._test_gs.save_game.assert_not_awaited()

    def test_create_save_at_max_length_accepted(self, client):
        """Exactly MAX_SAVE_NAME_LENGTH characters is allowed (boundary)."""
        from src.api.routes.saves import MAX_SAVE_NAME_LENGTH

        rv = client.post(
            "/api/saves",
            headers=AUTH,
            json={"name": "a" * MAX_SAVE_NAME_LENGTH},
        )
        assert rv.status_code == 201

    def test_create_save_strips_name_before_storing(self, client, app):
        """Surrounding whitespace is removed before validating and storing."""
        rv = client.post("/api/saves", headers=AUTH, json={"name": "  Padded  "})
        assert rv.status_code == 201
        assert rv.get_json()["message"] == "Game saved: Padded"
        # The stored name is the stripped one, not what the client sent.
        assert app._test_gs.save_game.await_args.args[1] == "Padded"

    def test_an_unnamed_autosave_is_not_labelled_a_manual_save(self, client, app):
        """The default name must match the kind of save actually written.

        A body of just ``{"is_autosave": true}`` carries the flag through to
        ``save_game``, so naming it "Manual Save" put a row in the load list
        describing itself as the opposite of what it is -- the same class of
        bogus save-list label this validation work set out to remove.
        """
        from src.api.routes.saves import DEFAULT_AUTOSAVE_NAME, DEFAULT_SAVE_NAME

        rv = client.post("/api/saves", headers=AUTH, json={"is_autosave": True})
        assert rv.status_code == 201
        name = app._test_gs.save_game.await_args.args[1]
        assert name == DEFAULT_AUTOSAVE_NAME
        assert name != DEFAULT_SAVE_NAME
        assert app._test_gs.save_game.await_args.kwargs["is_autosave"] is True

    def test_create_save_autosave_name_survives_validation(self, client, app):
        """The literal name useAutosave sends is never rejected.

        ``frontend/src/hooks/useApi.js`` posts ``{"name": "Autosave",
        "is_autosave": true}``; that is the only save written during active
        play, so validation must not be able to refuse it.
        """
        rv = client.post(
            "/api/saves", headers=AUTH, json={"name": "Autosave", "is_autosave": True}
        )
        assert rv.status_code == 201
        assert app._test_gs.save_game.await_args.args[1] == "Autosave"

    def test_create_save_absent_name_uses_default(self, client, app):
        """A manual save with no "name" key gets the server's own name.

        A server-generated name bypasses validation by construction, which is
        what keeps the rules from being able to reject a save the client did
        not name. The autosave branch has its own default -- see
        test_an_unnamed_autosave_is_not_labelled_a_manual_save.
        """
        from src.api.routes.saves import DEFAULT_SAVE_NAME

        rv = client.post("/api/saves", headers=AUTH, json={"is_autosave": False})
        assert rv.status_code == 201
        assert app._test_gs.save_game.await_args.args[1] == DEFAULT_SAVE_NAME

    # ---- load_save ----

    def test_load_save_success(self, client):
        rv = client.post("/api/saves/s1/load", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_load_save_no_db_user(self, app, make_stub_session):
        session = make_stub_session(session_id="sid_002", db_user_id=None)
        app._test_sm.get_session.return_value = session
        with app.test_client() as c:
            rv = c.post("/api/saves/s1/load", headers=AUTH)
        assert rv.status_code == 403

    def test_load_save_not_found(self, app):
        app._test_gs.load_game = AsyncMock(return_value=None)
        with app.test_client() as c:
            rv = c.post("/api/saves/s1/load", headers=AUTH)
        assert rv.status_code == 404

    def test_load_save_no_auth(self, client):
        rv = client.post("/api/saves/s1/load", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_load_save_exception(self, app):
        app._test_gs.load_game = AsyncMock(side_effect=RuntimeError("DB error"))
        with app.test_client() as c:
            rv = c.post("/api/saves/s1/load", headers=AUTH)
        assert rv.status_code == 500

    # ---- delete_save ----

    def test_delete_save_success(self, client):
        rv = client.delete("/api/saves/s1", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_delete_save_not_found(self, app):
        app._test_gs.delete_save = AsyncMock(return_value=False)
        with app.test_client() as c:
            rv = c.delete("/api/saves/s1", headers=AUTH)
        assert rv.status_code == 404

    def test_delete_save_no_db_user(self, app, make_stub_session):
        session = make_stub_session(session_id="sid_002", db_user_id=None)
        app._test_sm.get_session.return_value = session
        with app.test_client() as c:
            rv = c.delete("/api/saves/s1", headers=AUTH)
        assert rv.status_code == 403

    def test_delete_save_no_auth(self, client):
        rv = client.delete("/api/saves/s1", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_delete_save_exception(self, app):
        app._test_gs.delete_save = AsyncMock(side_effect=RuntimeError("crash"))
        with app.test_client() as c:
            rv = c.delete("/api/saves/s1", headers=AUTH)
        assert rv.status_code == 500

    # ---- new_game ----

    def test_new_game_success(self, client):
        rv = client.post("/api/game/new", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_new_game_failure(self, app):
        app._test_sm.start_new_game.return_value = False
        with app.test_client() as c:
            rv = c.post("/api/game/new", headers=AUTH)
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False

    def test_new_game_no_auth(self, client):
        rv = client.post("/api/game/new", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_new_game_exception(self, app):
        app._test_sm.start_new_game.side_effect = RuntimeError("bad state")
        with app.test_client() as c:
            rv = c.post("/api/game/new", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# npc.py
# ===========================================================================


# ===========================================================================
# logs.py
# ===========================================================================


class TestLogsRoutes:
    """Tests for routes/logs.py."""

    @pytest.fixture
    def app(self, minimal_app):
        from src.api.routes.logs import logs_bp

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(logs_bp, url_prefix="/api/logs")
        return app

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    # ---- receive_browser_logs ----

    def test_receive_logs_success(self, client, tmp_path):
        payload = {
            "logs": [
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "level": "LOG",
                    "message": "hello",
                    "url": "http://localhost:3000",
                }
            ],
            "session_id": "test_session",
        }
        with (
            patch("src.api.routes.logs.LOGS_DIR", tmp_path),
            patch("src.api.routes.logs.cleanup_manager") as mock_cm,
        ):
            mock_cm.cleanup.return_value = {}
            rv = client.post("/api/logs/browser", json=payload)
        assert rv.status_code == 200
        data = rv.get_json()
        assert "1 log" in data["message"]

    def test_receive_logs_no_logs_key(self, client):
        rv = client.post("/api/logs/browser", json={"session_id": "x"})
        assert rv.status_code == 400

    def test_receive_logs_empty_logs(self, client):
        rv = client.post("/api/logs/browser", json={"logs": [], "session_id": "x"})
        assert rv.status_code == 200
        data = rv.get_json()
        assert "No logs" in data["message"]

    def test_receive_logs_no_body(self, client):
        # No body triggers an exception in Flask's get_json() which the outer
        # except catches and returns 500 (not 400, since data check isn't reached)
        rv = client.post("/api/logs/browser")
        assert rv.status_code in (400, 500)

    def test_receive_logs_cleanup_failure(self, client, tmp_path):
        payload = {
            "logs": [{"timestamp": "T", "level": "LOG", "message": "m", "url": "u"}],
            "session_id": "sess",
        }
        with (
            patch("src.api.routes.logs.LOGS_DIR", tmp_path),
            patch("src.api.routes.logs.cleanup_manager") as mock_cm,
        ):
            mock_cm.cleanup.side_effect = RuntimeError("cleanup fail")
            rv = client.post("/api/logs/browser", json=payload)
        # Should still succeed even if cleanup fails
        assert rv.status_code == 200

    def test_receive_logs_write_exception(self, client, tmp_path):
        payload = {
            "logs": [{"timestamp": "T", "level": "LOG", "message": "m", "url": "u"}],
            "session_id": "sess",
        }
        with (
            patch("src.api.routes.logs.LOGS_DIR", tmp_path),
            patch("builtins.open", side_effect=OSError("Permission denied")),
        ):
            rv = client.post("/api/logs/browser", json=payload)
        assert rv.status_code == 500

    # ---- list_browser_log_files ----

    def test_list_log_files_empty_dir(self, client, tmp_path):
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = client.get("/api/logs/browser/files")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["files"] == []

    def test_list_log_files_with_files(self, client, tmp_path):
        (tmp_path / "2026-01-01_session.log").write_text("log content")
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = client.get("/api/logs/browser/files")
        assert rv.status_code == 200
        data = rv.get_json()
        assert len(data["files"]) == 1
        assert data["files"][0]["filename"].endswith(".log")

    def test_list_log_files_nonexistent_dir(self, client, tmp_path):
        nonexistent = tmp_path / "nonexistent"
        with patch("src.api.routes.logs.LOGS_DIR", nonexistent):
            rv = client.get("/api/logs/browser/files")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["files"] == []

    def test_list_log_files_exception(self, client):
        with patch("src.api.routes.logs.LOGS_DIR") as mock_dir:
            mock_dir.exists.side_effect = RuntimeError("FS error")
            rv = client.get("/api/logs/browser/files")
        assert rv.status_code == 500

    # ---- get_browser_log_file ----

    def test_get_log_file_success(self, client, tmp_path):
        log_file = tmp_path / "2026-01-01_sess.log"
        log_file.write_text("log line 1\nlog line 2")
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = client.get("/api/logs/browser/files/2026-01-01_sess.log")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "log line 1" in data["content"]

    def test_get_log_file_not_found(self, client, tmp_path):
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = client.get("/api/logs/browser/files/nonexistent.log")
        assert rv.status_code == 404

    def test_get_log_file_exception(self, client, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("data")
        with (
            patch("src.api.routes.logs.LOGS_DIR", tmp_path),
            patch("builtins.open", side_effect=OSError("read error")),
        ):
            rv = client.get("/api/logs/browser/files/test.log")
        assert rv.status_code == 500

    # ---- cleanup_logs ----

    def test_cleanup_logs_success(self, client):
        with patch("src.api.routes.logs.LogCleanupManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.cleanup.return_value = {"deleted": 2}
            mock_cls.return_value = mock_mgr
            rv = client.post(
                "/api/logs/browser/cleanup",
                json={"retention_days": 3, "max_size_mb": 50},
            )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["result"]["deleted"] == 2

    def test_cleanup_logs_no_body(self, client):
        with patch("src.api.routes.logs.LogCleanupManager") as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.cleanup.return_value = {}
            mock_cls.return_value = mock_mgr
            with patch("src.api.routes.logs.cleanup_manager") as mock_cm:
                mock_cm.retention_days = 7
                mock_cm.max_size_bytes = 104857600
                rv = client.post("/api/logs/browser/cleanup")
        assert rv.status_code == 200

    def test_cleanup_logs_exception(self, client):
        with patch("src.api.routes.logs.LogCleanupManager") as mock_cls:
            mock_cls.side_effect = RuntimeError("crash")
            with patch("src.api.routes.logs.cleanup_manager") as mock_cm:
                mock_cm.retention_days = 7
                mock_cm.max_size_bytes = 104857600
                rv = client.post("/api/logs/browser/cleanup", json={})
        assert rv.status_code == 500

    # ---- get_log_stats ----

    def test_get_log_stats_success(self, client):
        with patch("src.api.routes.logs.cleanup_manager") as mock_cm:
            mock_cm.get_stats.return_value = {"file_count": 5, "total_size": 1024}
            mock_cm.retention_days = 7
            mock_cm.max_size_bytes = 104857600
            rv = client.get("/api/logs/browser/stats")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "stats" in data
        assert data["stats"]["file_count"] == 5

    def test_get_log_stats_exception(self, client):
        with patch("src.api.routes.logs.cleanup_manager") as mock_cm:
            mock_cm.get_stats.side_effect = RuntimeError("stats error")
            rv = client.get("/api/logs/browser/stats")
        assert rv.status_code == 500

    # ---- delete_browser_log_file ----

    def test_delete_log_file_success(self, client, tmp_path):
        log_file = tmp_path / "2026-01-01_sess.log"
        log_file.write_text("data")
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = client.delete("/api/logs/browser/files/2026-01-01_sess.log")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "deleted" in data["message"].lower()

    def test_delete_log_file_not_found(self, client, tmp_path):
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            rv = client.delete("/api/logs/browser/files/missing.log")
        assert rv.status_code == 404

    def test_delete_log_file_exception(self, client, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("data")
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            with patch.object(type(log_file), "unlink", side_effect=OSError("perm")):
                rv = client.delete("/api/logs/browser/files/test.log")
        assert rv.status_code == 500
