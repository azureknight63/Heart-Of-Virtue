"""
Coverage tests for smaller route files:
- src/api/routes/npc_chat.py          (14% -> ~90%)
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock
from flask import Flask

from tests.llm_doubles import child_env

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
    """POST /npc-chat/open and /respond share one per-identity rate limit
    guarding the LLM-backed calls (each can drive a dozen provider calls
    through the fallback chain against the operator's account-wide free-tier
    quota). /end and /history never touch the LLM and are exempt.

    Two limiters are in play. ``_chat_limiter`` buckets on the *database user
    id* -- deliberately NOT on ``session_id``, which is a fresh uuid4 per login
    and so let a client reset its own budget by logging in again (S2). A second
    ``_chat_ip_limiter`` caps a single source regardless of identity, mirroring
    auth.py's two-tier pattern.

    Both are module-level singletons shared by every test in the process. The
    IP tier in particular cannot be isolated by varying anything the test
    controls -- every request from a Flask test client arrives from 127.0.0.1 --
    so ``_reset_chat_limiters`` clears both around each test.
    """

    @pytest.fixture(autouse=True)
    def _reset_chat_limiters(self):
        """Both tiers are process-wide singletons; drop every key around each
        test so neither this class nor its neighbours inherit a partly-spent
        bucket (the IP tier is shared by ALL of them at 127.0.0.1).

        This is the ONLY cleanup the class needs. Individual tests used to wrap
        themselves in ``try/finally: limiter.clear(session_id)``, which cleared
        nothing: the limiter records ``uid:<db_user_id>`` (see
        ``_chat_rate_limit_key``), so those calls named keys that had never
        existed -- and they could not have covered the IP tier in any case.
        """
        from src.api.routes import npc_chat as m

        for lim in (m._chat_limiter, m._chat_ip_limiter):
            if lim is not None:
                lim.clear_all()
        yield
        for lim in (m._chat_limiter, m._chat_ip_limiter):
            if lim is not None:
                lim.clear_all()

    @pytest.fixture
    def limiter(self):
        from src.api.routes.npc_chat import _chat_limiter

        assert _chat_limiter is not None, (
            "NPC_CHAT_RATE_LIMIT_PER_MINUTE must be at its nonzero default "
            "for this test -- check the test environment."
        )
        return _chat_limiter

    @pytest.fixture
    def ip_limiter(self):
        from src.api.routes.npc_chat import _chat_ip_limiter

        assert _chat_ip_limiter is not None
        return _chat_ip_limiter

    @pytest.fixture
    def client_for(self, app_for, make_stub_session):
        """``client_for(db_user_id)`` -- a one-blueprint app keyed to that
        database user, via the shared ``app_for``/``make_stub_session``
        fixtures.

        The identity limiter buckets on ``session.db_user_id`` (see
        ``_chat_rate_limit_key``), not on the bearer token and no longer on
        ``session_id``, so that is the field a test must vary to get its own
        bucket. Every request still authenticates with the shared ``AUTH``
        header.
        """
        from src.api.routes.npc_chat import npc_chat_bp

        def _client_for(db_user_id):
            app = app_for(
                npc_chat_bp,
                url_prefix="/npc-chat",
                session=make_stub_session(
                    session_id=f"sess_{db_user_id}", db_user_id=db_user_id
                ),
            )
            return app.test_client()

        return _client_for

    def test_the_bucket_survives_a_new_session_id(self, limiter, client_for, app_for,
                                                  make_stub_session):
        """S2 regression: keying on ``session_id`` let a client mint a fresh
        budget just by logging in again, because ``create_session`` issues a new
        uuid4 every time and the login throttle records only *failures*."""
        from src.api.routes.npc_chat import npc_chat_bp

        first = client_for("db_relogin")
        for _ in range(limiter.limit):
            assert first.post(
                "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
            ).status_code == 200

        # Same user, brand new session id -- as a re-login would produce.
        relogged = app_for(
            npc_chat_bp,
            url_prefix="/npc-chat",
            session=make_stub_session(
                session_id="a-completely-new-uuid", db_user_id="db_relogin"
            ),
        ).test_client()
        rv = relogged.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
        assert rv.status_code == 429

    def test_the_ip_tier_trips_independently_of_identity(
        self, limiter, ip_limiter, client_for
    ):
        """Defense in depth: distinct users behind one source still hit the
        IP cap, so an attacker cycling accounts cannot spray past the
        identity-keyed tier."""
        sent = 0
        user = 0
        while sent < ip_limiter.limit:
            client = client_for(f"db_spray_{user}")
            user += 1
            # Each synthetic user stays inside its own identity budget.
            for _ in range(min(limiter.limit, ip_limiter.limit - sent)):
                assert client.post(
                    "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
                ).status_code == 200
                sent += 1
        rv = client_for("db_spray_fresh").post(
            "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
        )
        assert rv.status_code == 429

    def test_under_limit_requests_all_succeed(self, limiter, client_for):
        client = client_for("rl_under_limit")
        for i in range(limiter.limit - 1):
            rv = client.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
            assert rv.status_code == 200, f"request {i} unexpectedly limited"

    def test_over_limit_request_gets_429(self, limiter, client_for):
        client = client_for("rl_over_limit")
        # Exhaust the budget alternating endpoints -- /open and /respond draw
        # from the same per-user bucket.
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

        rv = client.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
        assert rv.status_code == 429
        # The canonical 429 body, built by `rate_limited_response`: a stable
        # token in `error` for a client to branch on, the endpoint's own
        # prose in `message` for a human. This route used to put the prose
        # in `error` and ship no `message` at all, which is the half of the
        # shape auth.py disagreed with.
        assert rv.get_json() == {
            "success": False,
            "error": "rate_limited",
            "message": "Slow down — too many messages.",
        }

    def test_rate_limit_is_per_user(self, limiter, client_for):
        client_a = client_for("rl_bucket_a")
        client_b = client_for("rl_bucket_b")
        for _ in range(limiter.limit):
            rv = client_a.post(
                "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
            )
            assert rv.status_code == 200

        # User A is now exhausted...
        rv = client_a.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
        assert rv.status_code == 429

        # ...but user B has never made a request, so it has its own untouched
        # bucket.
        rv = client_b.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
        assert rv.status_code == 200

    def test_end_and_history_are_not_rate_limited(self, limiter, client_for):
        client = client_for("rl_end_history_exempt")
        # Comfortably above the /open+/respond ceiling -- must never trip since
        # these two routes never call `_check_chat_rate_limit`.
        for _ in range(limiter.limit + 5):
            rv = client.post("/npc-chat/end", json={"npc_key": "amelia"}, headers=AUTH)
            assert rv.status_code == 200
        rv = client.get("/npc-chat/history/amelia", headers=AUTH)
        assert rv.status_code == 200

    def test_the_identity_sources_do_not_share_one_key_space(self):
        """The four sources used to be concatenated into one flat key space, so
        a user free to choose a ``username`` equal to another principal's
        ``db_user_id`` (or to a session uuid, or to an IP literal) shared that
        principal's bucket -- a denial of service against them, and a doubled
        budget for whoever collided deliberately."""
        from src.api.routes.npc_chat import _chat_rate_limit_key

        by_id = SimpleNamespace(db_user_id="alice", username=None, session_id=None)
        by_name = SimpleNamespace(db_user_id=None, username="alice", session_id=None)
        by_session = SimpleNamespace(db_user_id=None, username=None, session_id="alice")

        keys = [
            _chat_rate_limit_key(by_id),
            _chat_rate_limit_key(by_name),
            _chat_rate_limit_key(by_session),
        ]
        assert keys == ["uid:alice", "user:alice", "sid:alice"]
        assert len(set(keys)) == 3

    def test_a_colliding_username_does_not_spend_another_users_budget(
        self, limiter, client_for, app_for, make_stub_session
    ):
        from src.api.routes.npc_chat import npc_chat_bp

        victim = client_for("db_collide")
        for _ in range(limiter.limit):
            assert victim.post(
                "/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH
            ).status_code == 200

        # A different principal whose *username* is the victim's db_user_id.
        impostor = app_for(
            npc_chat_bp,
            url_prefix="/npc-chat",
            session=make_stub_session(
                session_id="sess_impostor",
                username="db_collide",
                db_user_id=None,
            ),
        ).test_client()
        rv = impostor.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
        assert rv.status_code == 200

    def test_the_identity_tier_checks_and_records_in_one_operation(
        self, monkeypatch
    ):
        """Checking both tiers and only then recording either left a window in
        which N concurrent requests all read "not limited" before any of them
        wrote -- N times the budget, on the endpoint whose whole purpose is
        protecting an account-wide LLM quota from exactly that."""
        from src.api.routes import npc_chat as m

        seen = []

        class _Spy:
            limit = 10

            def is_limited(self, key):
                seen.append(("is_limited", key))
                return False

            def record(self, key):
                seen.append(("record", key))

            def check_and_record(self, key):
                seen.append(("check_and_record", key))
                return False

            def clear_all(self):  # the class's autouse reset fixture calls this
                seen.clear()

        monkeypatch.setattr(m, "_chat_limiter", _Spy())
        monkeypatch.setattr(m, "_chat_ip_limiter", None)

        session = SimpleNamespace(
            db_user_id="db_atomic", username=None, session_id=None
        )
        assert m._check_chat_rate_limit(session) is None
        assert seen == [("check_and_record", "uid:db_atomic")]

    def test_rate_limit_disabled_via_env_var(self):
        """NPC_CHAT_RATE_LIMIT_PER_MINUTE=0 disables the limiter at import
        time (``_chat_limiter`` is built once, at module import).

        Runs in a subprocess: `src.api.routes.npc_chat` is a shared
        singleton every other test in this process depends on, so mutating
        its live state here (or reloading it) would leak into them.
        """
        import subprocess
        import sys
        from pathlib import Path

        env = child_env(NPC_CHAT_RATE_LIMIT_PER_MINUTE="0")
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
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "CHAT_LIMITER_DISABLED_OK" in result.stdout

    def test_malformed_rate_limit_does_not_break_blueprint_import(self):
        """A typo'd NPC_CHAT_RATE_LIMIT_PER_MINUTE must not stop the server.

        The value was read with a bare ``int()`` at module scope, so
        ``NPC_CHAT_RATE_LIMIT_PER_MINUTE=twenty`` raised ValueError while the
        blueprint was being imported and took the whole API down at boot --
        a hard outage from a one-character mistake in an env file. Falling
        back to the default keeps the limiter on, which is the safe direction.

        Subprocess for the same reason as the test above: the module is a
        process-wide singleton.
        """
        import subprocess
        import sys
        from pathlib import Path

        env = child_env(NPC_CHAT_RATE_LIMIT_PER_MINUTE="twenty")
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import src.api.routes.npc_chat as m; "
                "assert m._chat_limiter is not None, 'limiter silently disabled'; "
                "assert m._chat_limiter.limit "
                "== m._RATE_LIMIT_DEFAULT_PER_MINUTE, m._chat_limiter.limit; "
                "print('CHAT_LIMITER_DEFAULTED_OK')",
            ],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "CHAT_LIMITER_DEFAULTED_OK" in result.stdout
