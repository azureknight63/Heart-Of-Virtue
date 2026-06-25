"""
Coverage-gap tests for API routes.

Targets:
- src/api/routes/saves.py  (42% -> ~90%)
- src/api/routes/equipment.py  (88% -> ~100%)
- src/api/routes/npc.py  (87% -> ~100%)
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


def _make_session(session_id="sid_001", db_user_id="db_user_1"):
    s = MagicMock()
    s.session_id = session_id
    s.db_user_id = db_user_id
    s.data = {"timezone": "America/New_York"}
    return s


def _make_session_no_db(session_id="sid_002"):
    """Session without a registered (cloud) account."""
    s = MagicMock()
    s.session_id = session_id
    s.db_user_id = None
    s.data = {}
    return s


def _make_player():
    p = MagicMock()
    p.name = "Jean Claire"
    p.hp = 100
    p.maxhp = 100
    p.level = 1
    return p


def _make_session_manager(session, player):
    sm = MagicMock()
    sm.get_session.return_value = session
    sm.get_player.return_value = player
    sm.save_session.return_value = None
    sm.set_player.return_value = None
    sm.start_new_game.return_value = True
    return sm


def _make_game_service():
    gs = MagicMock()
    gs.list_saves = AsyncMock(return_value=[{"id": "s1", "name": "Save 1"}])
    gs.save_game = AsyncMock(return_value="new_save_id")
    gs.load_game = AsyncMock(return_value=MagicMock())
    gs.delete_save = AsyncMock(return_value=True)
    gs.get_equipment.return_value = {"head": None, "body": None}
    gs.equip_item.return_value = {"item_id": "sword_01", "stat_changes": {}}
    gs.unequip_item.return_value = {"slot": "hands", "stat_changes": {}}
    gs.get_npc_state.return_value = {"success": True, "state": {}}
    gs.get_npc_dialogue.return_value = {"success": True, "dialogue": []}
    gs.select_dialogue_option.return_value = {"success": True, "dialogue": []}
    gs.get_npc_behavior_profile.return_value = {"success": True, "profile": {}}
    return gs


AUTH = {"Authorization": "Bearer sid_001"}
NO_AUTH = {}
BAD_AUTH = {"Authorization": "NotBearer sid_001"}


def _minimal_app(bp, prefix=None):
    """Create a fresh Flask test app with one blueprint."""
    session = _make_session()
    player = _make_player()
    sm = _make_session_manager(session, player)
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


# ===========================================================================
# saves.py
# ===========================================================================


class TestSavesRoutes:
    """Tests for routes/saves.py."""

    @pytest.fixture
    def app(self):
        from src.api.routes.saves import saves_bp

        return _minimal_app(saves_bp, prefix="/api")

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

    def test_list_saves_no_db_user_id(self, app):
        """Session without db_user_id returns empty saves list."""
        session = _make_session_no_db()
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

    def test_create_save_no_db_user(self, app):
        session = _make_session_no_db()
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

    # ---- load_save ----

    def test_load_save_success(self, client):
        rv = client.post("/api/saves/s1/load", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_load_save_no_db_user(self, app):
        session = _make_session_no_db()
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

    def test_delete_save_no_db_user(self, app):
        session = _make_session_no_db()
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
# equipment.py
# ===========================================================================


class TestEquipmentRoutes:
    """Tests for routes/equipment.py (covers remaining ~12% gap)."""

    @pytest.fixture
    def app(self):
        from src.api.routes.equipment import equipment_bp

        return _minimal_app(equipment_bp, prefix="/api")

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_get_equipment_success(self, client):
        rv = client.get("/api/equipment", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_get_equipment_no_auth(self, client):
        rv = client.get("/api/equipment", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_get_equipment_no_game_service(self, app):
        app.game_service = None
        with app.test_client() as c:
            rv = c.get("/api/equipment", headers=AUTH)
        assert rv.status_code == 500

    def test_get_equipment_exception(self, app):
        app._test_gs.get_equipment.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/api/equipment", headers=AUTH)
        assert rv.status_code == 500

    def test_equip_item_success(self, client):
        rv = client.post(
            "/api/equipment/equip", headers=AUTH, json={"item_id": "sword_01"}
        )
        assert rv.status_code == 200

    def test_equip_item_missing_item_id(self, client):
        rv = client.post("/api/equipment/equip", headers=AUTH, json={})
        assert rv.status_code == 400

    def test_equip_item_error_result(self, app):
        app._test_gs.equip_item.return_value = {"error": "Item not found"}
        with app.test_client() as c:
            rv = c.post("/api/equipment/equip", headers=AUTH, json={"item_id": "x"})
        assert rv.status_code == 400

    def test_equip_item_no_auth(self, client):
        rv = client.post("/api/equipment/equip", headers=NO_AUTH, json={"item_id": "x"})
        assert rv.status_code == 401

    def test_unequip_item_success(self, client):
        rv = client.post("/api/equipment/unequip", headers=AUTH, json={"slot": "hands"})
        assert rv.status_code == 200

    def test_unequip_item_missing_slot(self, client):
        rv = client.post("/api/equipment/unequip", headers=AUTH, json={})
        assert rv.status_code == 400

    def test_unequip_item_error_result(self, app):
        app._test_gs.unequip_item.return_value = {"error": "Slot empty"}
        with app.test_client() as c:
            rv = c.post("/api/equipment/unequip", headers=AUTH, json={"slot": "head"})
        assert rv.status_code == 400

    def test_unequip_item_no_auth(self, client):
        rv = client.post(
            "/api/equipment/unequip", headers=NO_AUTH, json={"slot": "head"}
        )
        assert rv.status_code == 401


# ===========================================================================
# npc.py
# ===========================================================================


class TestNPCRoutes:
    """Tests for routes/npc.py (covers remaining ~13% gap)."""

    @pytest.fixture
    def app(self):
        from src.api.routes.npc import npc_bp

        return _minimal_app(npc_bp)

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    # ---- get_npc_state ----

    def test_get_npc_state_success(self, client):
        rv = client.get("/api/npc/npc_001/state", headers=AUTH)
        assert rv.status_code == 200

    def test_get_npc_state_no_auth(self, client):
        rv = client.get("/api/npc/npc_001/state", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_get_npc_state_invalid_npc_id(self, client):
        # NPC ID that exceeds the 100-char limit triggers the validator
        long_id = "x" * 101
        rv = client.get(f"/api/npc/{long_id}/state", headers=AUTH)
        assert rv.status_code == 400

    def test_get_npc_state_npc_not_found(self, app):
        app._test_gs.get_npc_state.return_value = {"success": False}
        with app.test_client() as c:
            rv = c.get("/api/npc/npc_999/state", headers=AUTH)
        assert rv.status_code == 404

    # ---- get_npc_dialogue ----

    def test_get_npc_dialogue_success(self, client):
        rv = client.get("/api/npc/npc_001/dialogue", headers=AUTH)
        assert rv.status_code == 200

    def test_get_npc_dialogue_no_auth(self, client):
        rv = client.get("/api/npc/npc_001/dialogue", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_get_npc_dialogue_not_found(self, app):
        app._test_gs.get_npc_dialogue.return_value = {"success": False}
        with app.test_client() as c:
            rv = c.get("/api/npc/npc_999/dialogue", headers=AUTH)
        assert rv.status_code == 404

    # ---- select_dialogue_option ----

    def test_select_dialogue_option_success(self, client):
        rv = client.post(
            "/api/npc/npc_001/dialogue",
            headers=AUTH,
            json={"option_id": 0},
        )
        assert rv.status_code == 200

    def test_select_dialogue_option_missing_option_id(self, client):
        rv = client.post(
            "/api/npc/npc_001/dialogue",
            headers=AUTH,
            json={},
        )
        assert rv.status_code == 400

    def test_select_dialogue_option_negative(self, client):
        rv = client.post(
            "/api/npc/npc_001/dialogue",
            headers=AUTH,
            json={"option_id": -1},
        )
        assert rv.status_code == 400

    def test_select_dialogue_option_invalid_type(self, client):
        rv = client.post(
            "/api/npc/npc_001/dialogue",
            headers=AUTH,
            json={"option_id": "abc"},
        )
        assert rv.status_code == 400

    def test_select_dialogue_option_no_auth(self, client):
        rv = client.post(
            "/api/npc/npc_001/dialogue",
            headers=NO_AUTH,
            json={"option_id": 0},
        )
        assert rv.status_code == 401

    # ---- get_npc_profile ----

    def test_get_npc_profile_success(self, client):
        rv = client.get("/api/npc/npc_001/profile", headers=AUTH)
        assert rv.status_code == 200

    def test_get_npc_profile_not_found(self, app):
        app._test_gs.get_npc_behavior_profile.return_value = {"success": False}
        with app.test_client() as c:
            rv = c.get("/api/npc/npc_001/profile", headers=AUTH)
        assert rv.status_code == 404


# ===========================================================================
# logs.py
# ===========================================================================


class TestLogsRoutes:
    """Tests for routes/logs.py."""

    @pytest.fixture
    def app(self):
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
