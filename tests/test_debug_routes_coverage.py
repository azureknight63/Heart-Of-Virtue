"""
Coverage tests for src/api/routes/debug.py — the TESTING-only debug/combat
testing blueprint (`debug_bp`).

Per CLAUDE.md, this blueprint is test-infrastructure-only (registered only
when ``app.config["TESTING"]`` is true), so testing it via a real Flask test
client in a normal ``tests/`` file (not ``tests/api/``) matches how the other
route modules are tested elsewhere in the default suite.

The adjutant (``src.npc._adjutant.TheAdjutant``) is owned by a different
work-stream, so its methods are mocked here rather than exercised for real —
these tests only verify the route wiring: auth resolution, request-body
parsing, status codes, and error handling in ``_run``.
"""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.api.routes.debug import debug_bp
import src.api.routes.debug as debug_module


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(debug_bp, url_prefix="/api/debug")
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _reset_adjutant_singleton():
    """Ensure the module-level adjutant cache doesn't leak between tests."""
    debug_module._adjutant_instance = None
    yield
    debug_module._adjutant_instance = None


def _mock_auth_success(player=None):
    """Patch get_session_and_player to succeed with a dummy player."""
    player = player or MagicMock(name="player")
    return patch(
        "src.api.routes.debug.get_session_and_player",
        return_value=(MagicMock(), MagicMock(), player, None),
    )


def _mock_auth_failure():
    """Patch get_session_and_player to return an auth error tuple."""
    error = ({"success": False, "error": "no auth"}, 401)
    return patch(
        "src.api.routes.debug.get_session_and_player",
        return_value=(None, None, None, error),
    )


# ---------------------------------------------------------------------------
# _adjutant() singleton
# ---------------------------------------------------------------------------


class TestAdjutantSingleton:
    def test_creates_instance_on_first_call(self):
        dummy_cls = MagicMock()
        with patch("src.npc._adjutant.TheAdjutant", dummy_cls):
            result = debug_module._adjutant()
        assert result is dummy_cls.return_value

    def test_returns_cached_instance_on_second_call(self):
        dummy_cls = MagicMock()
        with patch("src.npc._adjutant.TheAdjutant", dummy_cls):
            first = debug_module._adjutant()
            second = debug_module._adjutant()
        assert first is second
        # Constructor only invoked once — second call used the cache.
        assert dummy_cls.call_count == 1


# ---------------------------------------------------------------------------
# _run() shared error handling
# ---------------------------------------------------------------------------


class TestRunErrorHandling:
    def test_auth_error_short_circuits(self, client):
        with _mock_auth_failure():
            resp = client.get("/api/debug/player")
        assert resp.status_code == 401
        assert resp.get_json()["success"] is False

    def test_missing_required_key_returns_400(self, client):
        """A KeyError inside the operation lambda is caught as a 400."""
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=MagicMock()
        ):
            resp = client.post("/api/debug/player/hp", json={})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["success"] is False
        assert "error" in body

    def test_value_error_returns_400(self, client):
        adj = MagicMock()
        adj.set_hp.side_effect = ValueError("bad value")
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post(
                "/api/debug/player/hp", json={"hp": 10, "maxhp": 20}
            )
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# Player stat operations — success paths
# ---------------------------------------------------------------------------


class TestPlayerOperations:
    def test_player_state(self, client):
        adj = MagicMock()
        adj.player_state.return_value = {"hp": 100, "level": 1}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.get("/api/debug/player")
        assert resp.status_code == 200
        assert resp.get_json() == {"hp": 100, "level": 1}
        adj.player_state.assert_called_once()

    def test_set_hp(self, client):
        adj = MagicMock()
        adj.set_hp.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post(
                "/api/debug/player/hp", json={"hp": 50, "maxhp": 100}
            )
        assert resp.status_code == 200
        adj.set_hp.assert_called_once()
        args = adj.set_hp.call_args[0]
        assert args[1] == 50 and args[2] == 100

    def test_set_level(self, client):
        adj = MagicMock()
        adj.set_level.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post(
                "/api/debug/player/level", json={"level": 5, "exp": 200}
            )
        assert resp.status_code == 200
        adj.set_level.assert_called_once()

    def test_set_attributes(self, client):
        adj = MagicMock()
        adj.set_attributes.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post(
                "/api/debug/player/attributes",
                json={"attributes": {"strength": 10}},
            )
        assert resp.status_code == 200
        adj.set_attributes.assert_called_once()
        args = adj.set_attributes.call_args[0]
        assert args[1] == {"strength": 10}

    def test_set_attributes_defaults_to_empty_dict(self, client):
        adj = MagicMock()
        adj.set_attributes.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post("/api/debug/player/attributes", json={})
        assert resp.status_code == 200
        args = adj.set_attributes.call_args[0]
        assert args[1] == {}

    def test_set_heat(self, client):
        adj = MagicMock()
        adj.set_heat.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post("/api/debug/player/heat", json={"heat": 3})
        assert resp.status_code == 200
        adj.set_heat.assert_called_once()

    def test_restore(self, client):
        adj = MagicMock()
        adj.restore.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post("/api/debug/player/restore", json={})
        assert resp.status_code == 200
        adj.restore.assert_called_once()

    def test_learn_skills(self, client):
        adj = MagicMock()
        adj.learn_all_skills.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post("/api/debug/player/learn-skills", json={})
        assert resp.status_code == 200
        adj.learn_all_skills.assert_called_once()

    def test_list_skills(self, client):
        adj = MagicMock()
        adj.list_skills.return_value = ["Slash", "Parry"]
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.get("/api/debug/player/skills")
        assert resp.status_code == 200
        assert resp.get_json() == {"skills": ["Slash", "Parry"]}


# ---------------------------------------------------------------------------
# Arena combatant management — success paths
# ---------------------------------------------------------------------------


class TestArenaOperations:
    def test_arena_rosters(self, client):
        adj = MagicMock()
        adj.arena_rosters.return_value = {"fodder_pit": []}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.get("/api/debug/arena")
        assert resp.status_code == 200
        assert resp.get_json() == {"rosters": {"fodder_pit": []}}

    def test_arena_add(self, client):
        adj = MagicMock()
        adj.add_combatant.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post(
                "/api/debug/arena/add",
                json={"arena": "fodder_pit", "cls_name": "Slime"},
            )
        assert resp.status_code == 200
        args = adj.add_combatant.call_args[0]
        assert args[1] == "fodder_pit" and args[2] == "Slime"

    def test_arena_remove(self, client):
        adj = MagicMock()
        adj.remove_combatant.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post(
                "/api/debug/arena/remove",
                json={"arena": "fodder_pit", "index": 0},
            )
        assert resp.status_code == 200
        args = adj.remove_combatant.call_args[0]
        assert args[1] == "fodder_pit" and args[2] == 0

    def test_arena_clear(self, client):
        adj = MagicMock()
        adj.clear_room.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post(
                "/api/debug/arena/clear", json={"arena": "fodder_pit"}
            )
        assert resp.status_code == 200
        args = adj.clear_room.call_args[0]
        assert args[1] == "fodder_pit"

    def test_arena_stats(self, client):
        adj = MagicMock()
        adj.set_combatant_stats.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post(
                "/api/debug/arena/stats",
                json={
                    "arena": "fodder_pit",
                    "index": 0,
                    "stats": {"hp": 10},
                },
            )
        assert resp.status_code == 200
        args = adj.set_combatant_stats.call_args[0]
        assert (
            args[1] == "fodder_pit"
            and args[2] == 0
            and args[3] == {"hp": 10}
        )

    def test_arena_stats_defaults_stats_to_empty_dict(self, client):
        adj = MagicMock()
        adj.set_combatant_stats.return_value = {"success": True}
        with _mock_auth_success(), patch(
            "src.api.routes.debug._adjutant", return_value=adj
        ):
            resp = client.post(
                "/api/debug/arena/stats",
                json={"arena": "fodder_pit", "index": 0},
            )
        assert resp.status_code == 200
        args = adj.set_combatant_stats.call_args[0]
        assert args[3] == {}
