"""
Coverage tests for smaller route files:
- src/api/routes/npc_chat.py          (14% -> ~90%)
"""

import pytest
from unittest.mock import MagicMock
from flask import Flask

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_player():
    p = MagicMock()
    p.name = "Jean Claire"
    p.hp = 100
    p.maxhp = 100
    return p


def _make_gs():
    gs = MagicMock()
    # npc_chat
    gs.npc_chat_open.return_value = {"success": True, "conversation": {}}
    gs.npc_chat_respond.return_value = {"success": True, "npc_reply": "Hello!"}
    gs.npc_chat_end.return_value = {"success": True, "summary": "Conversation ended"}
    gs.npc_chat_history.return_value = {"success": True, "exchanges": []}
    return gs


@pytest.fixture
def app_for(make_stub_session, make_stub_session_manager):
    """Build a one-blueprint Flask app on the shared session/manager stubs.

    The session comes from ``make_stub_session`` (a *real* ``Session``, so a
    typo'd attribute raises instead of being invented) and the manager from
    ``make_stub_session_manager`` (``spec``-constrained, so a route calling a
    method ``SessionManager`` does not have fails the test). Only the blueprint
    registration stays local, because these routes are mounted under a URL
    prefix and the shared ``make_route_app`` registers at the app root.
    """

    def _app_for(bp, url_prefix=None, session=None, player=None):
        if session is None:
            session = make_stub_session(session_id="sid_m1", db_user_id="db_1")
        if player is None:
            player = _make_player()
        sm = make_stub_session_manager(session, player)
        gs = _make_gs()

        app = Flask(__name__)
        app.config["TESTING"] = True
        if url_prefix is not None:
            app.register_blueprint(bp, url_prefix=url_prefix)
        else:
            app.register_blueprint(bp)
        app.session_manager = sm
        app.game_service = gs
        app._test_session = session
        app._test_player = player
        app._test_sm = sm
        app._test_gs = gs
        return app

    return _app_for


AUTH = {"Authorization": "Bearer sid_m1"}
NO_AUTH = {}


# ===========================================================================
# npc_chat.py
# ===========================================================================


class TestNpcChat:
    @pytest.fixture
    def app(self, app_for):
        from src.api.routes.npc_chat import npc_chat_bp

        return app_for(npc_chat_bp, url_prefix="/npc-chat")

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    # POST /npc-chat/open
    def test_chat_open_success(self, client):
        rv = client.post(
            "/npc-chat/open",
            json={"npc_id": "amelia"},
            headers=AUTH,
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_chat_open_no_npc_id(self, client):
        rv = client.post("/npc-chat/open", json={}, headers=AUTH)
        assert rv.status_code == 400
        data = rv.get_json()
        assert "npc_id" in data["error"]

    def test_chat_open_empty_npc_id(self, client):
        rv = client.post("/npc-chat/open", json={"npc_id": "  "}, headers=AUTH)
        assert rv.status_code == 400

    def test_chat_open_no_auth(self, client):
        rv = client.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=NO_AUTH)
        assert rv.status_code == 401

    def test_chat_open_invalid_session(self, app):
        app._test_sm.get_session.return_value = None
        with app.test_client() as c:
            rv = c.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
        assert rv.status_code == 401

    def test_chat_open_player_not_found(self, app):
        app._test_sm.get_player.return_value = None
        with app.test_client() as c:
            rv = c.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
        assert rv.status_code == 404

    def test_chat_open_service_failure(self, app):
        app._test_gs.npc_chat_open.return_value = {
            "success": False,
            "error": "NPC not found",
        }
        with app.test_client() as c:
            rv = c.post("/npc-chat/open", json={"npc_id": "ghost"}, headers=AUTH)
        assert rv.status_code == 400

    # POST /npc-chat/respond
    def test_chat_respond_success(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={
                "npc_key": "amelia",
                "jean_text": "Hello there!",
                "jean_tone": "open",
            },
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_chat_respond_missing_npc_key(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={"jean_text": "Hi"},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert "npc_key" in data["error"]

    def test_chat_respond_missing_jean_text(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={"npc_key": "amelia"},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert "jean_text" in data["error"]

    def test_chat_respond_no_auth(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={"npc_key": "amelia", "jean_text": "Hi"},
            headers=NO_AUTH,
        )
        assert rv.status_code == 401

    def test_chat_respond_default_tone(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={"npc_key": "guard", "jean_text": "Stand aside."},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_chat_respond_service_failure(self, app):
        app._test_gs.npc_chat_respond.return_value = {
            "success": False,
            "error": "Chat not open",
        }
        with app.test_client() as c:
            rv = c.post(
                "/npc-chat/respond",
                json={"npc_key": "amelia", "jean_text": "Hi"},
                headers=AUTH,
            )
        assert rv.status_code == 400

    # POST /npc-chat/end
    def test_chat_end_success(self, client):
        rv = client.post(
            "/npc-chat/end",
            json={"npc_key": "amelia"},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_chat_end_missing_npc_key(self, client):
        rv = client.post("/npc-chat/end", json={}, headers=AUTH)
        assert rv.status_code == 400

    def test_chat_end_no_auth(self, client):
        rv = client.post("/npc-chat/end", json={"npc_key": "amelia"}, headers=NO_AUTH)
        assert rv.status_code == 401

    def test_chat_end_service_failure(self, app):
        app._test_gs.npc_chat_end.return_value = {
            "success": False,
            "error": "No active chat",
        }
        with app.test_client() as c:
            rv = c.post("/npc-chat/end", json={"npc_key": "ghost"}, headers=AUTH)
        assert rv.status_code == 400

    # GET /npc-chat/history/<npc_key>
    def test_chat_history_success(self, client):
        rv = client.get("/npc-chat/history/amelia", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_chat_history_no_auth(self, client):
        rv = client.get("/npc-chat/history/amelia", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_chat_history_service_failure(self, app):
        app._test_gs.npc_chat_history.return_value = {
            "success": False,
            "error": "No history",
        }
        with app.test_client() as c:
            rv = c.get("/npc-chat/history/ghost", headers=AUTH)
        assert rv.status_code == 400
