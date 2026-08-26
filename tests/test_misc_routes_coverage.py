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


class TestNpcChatRateLimit:
    """POST /npc-chat/open and /respond share one per-session rate limit
    guarding the LLM-backed calls (each can drive up to ~3 provider calls
    through the fallback chain against the operator's shared free-tier
    quota). /end and /history never touch the LLM and are exempt.

    The limiter (``npc_chat._chat_limiter``) is a module-level singleton
    shared by every test in the process, so each test below uses its own
    uniquely-named session id to avoid cross-test bucket collisions, and
    clears that key when done.
    """

    @pytest.fixture
    def limiter(self):
        from src.api.routes.npc_chat import _chat_limiter

        assert _chat_limiter is not None, (
            "NPC_CHAT_RATE_LIMIT_PER_MINUTE must be at its nonzero default "
            "for this test -- check the test environment."
        )
        return _chat_limiter

    @pytest.fixture
    def client_for(self, app_for, make_stub_session):
        """``client_for(session_id)`` -- a one-blueprint app keyed to that
        session id, via the shared ``app_for``/``make_stub_session`` fixtures
        (the rate limiter buckets on ``session.session_id``, not the bearer
        token, so every request still authenticates with the shared ``AUTH``
        header regardless of which session id this builds)."""
        from src.api.routes.npc_chat import npc_chat_bp

        def _client_for(session_id):
            app = app_for(
                npc_chat_bp,
                url_prefix="/npc-chat",
                session=make_stub_session(session_id=session_id),
            )
            return app.test_client()

        return _client_for

    def test_under_limit_requests_all_succeed(self, limiter, client_for):
        session_id = "rl_under_limit"
        limiter.clear(session_id)
        client = client_for(session_id)
        try:
            for i in range(limiter.limit - 1):
                rv = client.post(
                    "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
                )
                assert rv.status_code == 200, f"request {i} unexpectedly limited"
        finally:
            limiter.clear(session_id)

    def test_over_limit_request_gets_429(self, limiter, client_for):
        session_id = "rl_over_limit"
        limiter.clear(session_id)
        client = client_for(session_id)
        try:
            # Exhaust the budget alternating endpoints -- /open and /respond
            # draw from the same per-session bucket.
            for i in range(limiter.limit):
                if i % 2 == 0:
                    endpoint, payload = "/npc-chat/open", {"npc_id": "amelia"}
                else:
                    endpoint, payload = (
                        "/npc-chat/respond",
                        {"npc_key": "amelia", "jean_text": "hi"},
                    )
                rv = client.post(endpoint, json=payload, headers=AUTH)
                assert rv.status_code == 200, f"request {i} unexpectedly limited"

            rv = client.post(
                "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
            )
            assert rv.status_code == 429
            assert rv.get_json() == {
                "success": False,
                "error": "Slow down — too many messages.",
            }
        finally:
            limiter.clear(session_id)

    def test_rate_limit_is_per_session(self, limiter, client_for):
        session_a = "rl_bucket_a"
        session_b = "rl_bucket_b"
        limiter.clear(session_a)
        limiter.clear(session_b)
        client_a = client_for(session_a)
        client_b = client_for(session_b)
        try:
            for _ in range(limiter.limit):
                rv = client_a.post(
                    "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
                )
                assert rv.status_code == 200

            # Session A is now exhausted...
            rv = client_a.post(
                "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
            )
            assert rv.status_code == 429

            # ...but session B has never made a request, so it has its own
            # untouched bucket.
            rv = client_b.post(
                "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
            )
            assert rv.status_code == 200
        finally:
            limiter.clear(session_a)
            limiter.clear(session_b)

    def test_end_and_history_are_not_rate_limited(self, limiter, client_for):
        session_id = "rl_end_history_exempt"
        limiter.clear(session_id)
        client = client_for(session_id)
        try:
            # Comfortably above the /open+/respond ceiling -- must never trip
            # since these two routes never call `_check_chat_rate_limit`.
            for _ in range(limiter.limit + 5):
                rv = client.post(
                    "/npc-chat/end", json={"npc_key": "amelia"}, headers=AUTH
                )
                assert rv.status_code == 200
            rv = client.get("/npc-chat/history/amelia", headers=AUTH)
            assert rv.status_code == 200
        finally:
            limiter.clear(session_id)

    def test_rate_limit_disabled_via_env_var(self):
        """NPC_CHAT_RATE_LIMIT_PER_MINUTE=0 disables the limiter at import
        time (``_chat_limiter`` is built once, at module import).

        Runs in a subprocess: `src.api.routes.npc_chat` is a shared
        singleton every other test in this process depends on, so mutating
        its live state here (or reloading it) would leak into them.
        """
        import os
        import subprocess
        import sys
        from pathlib import Path

        env = os.environ.copy()
        env["NPC_CHAT_RATE_LIMIT_PER_MINUTE"] = "0"
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import src.api.routes.npc_chat as m; "
                "assert m._chat_limiter is None, m._chat_limiter; "
                "print('CHAT_LIMITER_DISABLED_OK')",
            ],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "CHAT_LIMITER_DISABLED_OK" in result.stdout
