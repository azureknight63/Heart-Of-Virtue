"""
Coverage tests for src/api/routes/auth.py (35% -> target ~80%)

Uncovered: 14-44, 48-78, 115, 159-199, 235, 252-276, 329-353, 378-410, 437-485

Strategy: minimal Flask app with mocked session_manager and auth_service,
async routes need AsyncMock for auth_service calls.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from flask import Flask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(session_id="sid_a1", db_user_id="db_1"):
    s = MagicMock()
    s.session_id = session_id
    s.db_user_id = db_user_id
    s.player_id = "player_1"
    s.data = {"timezone": "America/New_York"}
    return s


def _make_session_manager(session=None):
    sm = MagicMock()
    sm.get_session.return_value = session
    sm.get_player.return_value = MagicMock()
    sm.create_session.return_value = ("sid_a1", "player_1")
    sm.expire_session.return_value = True
    sm.save_session.return_value = None
    return sm


AUTH = {"Authorization": "Bearer sid_a1"}
NO_AUTH = {}
BAD_AUTH = {"Authorization": "NotBearer sid_a1"}


def _make_app(session=None, sm=None):
    from src.api.routes.auth import auth_bp

    if session is None:
        session = _make_session()
    if sm is None:
        sm = _make_session_manager(session)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(auth_bp)
    app.session_manager = sm
    app.game_service = MagicMock()
    app._test_session = session
    app._test_sm = sm
    return app


# ===========================================================================
# POST /auth/register
# ===========================================================================


class TestRegister:
    @pytest.fixture
    def app(self):
        return _make_app()

    def test_register_success(self, app):
        mock_user = {
            "id": "user_001",
            "username": "Jean",
            "timezone": "America/New_York",
        }
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/register",
                    json={
                        "username": "Jean",
                        "password": "secret",
                        "email": "j@test.com",
                    },
                )
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["success"] is True
        assert "session_id" in data["data"]

    def test_register_missing_username(self, app):
        with app.test_client() as c:
            rv = c.post(
                "/auth/register",
                json={"password": "secret", "email": "j@test.com"},
            )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False

    def test_register_missing_password(self, app):
        with app.test_client() as c:
            rv = c.post(
                "/auth/register",
                json={"username": "Jean", "email": "j@test.com"},
            )
        assert rv.status_code == 400

    def test_register_missing_email(self, app):
        with app.test_client() as c:
            rv = c.post(
                "/auth/register",
                json={"username": "Jean", "password": "secret"},
            )
        assert rv.status_code == 400

    def test_register_no_body(self, app):
        # No JSON body: route checks `not data`, gets None, returns 400 or 500
        with app.test_client() as c:
            rv = c.post("/auth/register")
        assert rv.status_code in (400, 500)

    def test_register_username_taken(self, app):
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            side_effect=Exception("UNIQUE constraint failed: users.username"),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/register",
                    json={
                        "username": "existing",
                        "password": "pw",
                        "email": "e@test.com",
                    },
                )
        assert rv.status_code == 409
        data = rv.get_json()
        assert data["error"] == "conflict_error"

    def test_register_validation_error_from_service(self, app):
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            side_effect=ValueError("Username too short"),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/register",
                    json={"username": "ab", "password": "pw", "email": "x@test.com"},
                )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["error"] == "validation_error"

    def test_register_service_unavailable_env_error(self, app):
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            side_effect=ValueError("TURSO_URL not set"),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/register",
                    json={"username": "Jean", "password": "pw", "email": "j@test.com"},
                )
        assert rv.status_code == 503
        data = rv.get_json()
        assert data["error"] == "service_unavailable"

    def test_register_unexpected_exception(self, app):
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            side_effect=Exception("Something totally unexpected"),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/register",
                    json={"username": "Jean", "password": "pw", "email": "j@test.com"},
                )
        assert rv.status_code == 500
        data = rv.get_json()
        assert data["error"] == "server_error"


# ===========================================================================
# POST /auth/login
# ===========================================================================


class TestLogin:
    @pytest.fixture
    def app(self):
        return _make_app()

    def test_login_success(self, app):
        mock_user = {"id": "user_001", "username": "Jean", "timezone": "UTC"}
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/login",
                    json={"username": "Jean", "password": "secret"},
                )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert "session_id" in data["data"]

    def test_login_missing_username(self, app):
        with app.test_client() as c:
            rv = c.post("/auth/login", json={"password": "secret"})
        assert rv.status_code == 400

    def test_login_missing_password(self, app):
        with app.test_client() as c:
            rv = c.post("/auth/login", json={"username": "Jean"})
        assert rv.status_code == 400

    def test_login_no_body(self, app):
        # No JSON body: route checks `not data`, returns 400 or catches exception as 500
        with app.test_client() as c:
            rv = c.post("/auth/login")
        assert rv.status_code in (400, 500)

    def test_login_invalid_credentials(self, app):
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/login",
                    json={"username": "Jean", "password": "wrong"},
                )
        assert rv.status_code == 401
        data = rv.get_json()
        assert data["error"] == "auth_error"

    def test_login_service_unavailable(self, app):
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            side_effect=Exception("DATABASE_URL not set in os.environ"),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/login",
                    json={"username": "Jean", "password": "pw"},
                )
        assert rv.status_code == 503
        data = rv.get_json()
        assert data["error"] == "service_unavailable"

    def test_login_server_error(self, app):
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            side_effect=Exception("db connection failed"),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/login",
                    json={"username": "Jean", "password": "pw"},
                )
        assert rv.status_code == 500


class TestLoginRateLimitBoundedGrowth:
    """GitHub issue #284: the login throttle's in-memory store must not grow
    unboundedly under a spray attack across many distinct username:ip keys."""

    @pytest.fixture(autouse=True)
    def _isolate_limiter(self):
        from src.api.routes.auth import _login_limiter

        _login_limiter.clear_all()
        yield
        _login_limiter.clear_all()

    @pytest.fixture
    def app(self):
        return _make_app()

    def test_many_distinct_failed_logins_stay_bounded(self):
        from src.api.routes.auth import _login_limiter, _record_failed_login

        # Simulate a spray attack: many distinct username:ip keys (the same
        # shape `_login_rate_limit_key` produces) each failing login a few
        # times, well under any single key's own rate limit.
        for i in range(_login_limiter.max_keys + 500):
            key = f"attacker{i}:203.0.113.{i % 255}"
            _record_failed_login(key)
            assert _login_limiter.size() <= _login_limiter.max_keys

        assert _login_limiter.size() <= _login_limiter.max_keys

    def test_successful_login_clears_failed_attempt_key(self, app):
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/login",
                    json={"username": "ClearMeUser", "password": "wrong"},
                )
        assert rv.status_code == 401

        from src.api.routes.auth import _login_limiter, _login_rate_limit_key

        with app.test_request_context():
            key = _login_rate_limit_key("ClearMeUser")
        assert _login_limiter.size() >= 1

        mock_user = {"id": "user_002", "username": "ClearMeUser", "timezone": "UTC"}
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/login",
                    json={"username": "ClearMeUser", "password": "right"},
                )
        assert rv.status_code == 200
        assert _login_limiter.is_limited(key) is False


# ===========================================================================
# POST /auth/logout  (requires @require_auth)
# ===========================================================================


class TestLogout:
    @pytest.fixture
    def app(self):
        session = _make_session()
        sm = _make_session_manager(session)
        return _make_app(session=session, sm=sm)

    def test_logout_success(self, app):
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_logout_session_not_found(self, app):
        app._test_sm.expire_session.return_value = False
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=AUTH)
        assert rv.status_code == 404

    def test_logout_no_auth(self, app):
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_logout_bad_auth(self, app):
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=BAD_AUTH)
        assert rv.status_code == 401

    def test_logout_invalid_session_in_require_auth(self, app):
        app._test_sm.get_session.return_value = None
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=AUTH)
        assert rv.status_code == 401

    def test_logout_session_manager_not_initialized(self, app):
        # Issue #408: require_auth now routes through the shared resolve_session
        # helper; a falsy session_manager must still yield the 500 "not
        # initialized" response at every call site.
        app.session_manager = None
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=AUTH)
        assert rv.status_code == 500
        data = rv.get_json()
        assert data["error"] == "Session manager not initialized"


# ===========================================================================
# GET /auth/validate
# ===========================================================================


class TestValidateSession:
    @pytest.fixture
    def app(self):
        session = _make_session()
        sm = _make_session_manager(session)
        return _make_app(session=session, sm=sm)

    def test_valid_session(self, app):
        with app.test_client() as c:
            rv = c.get("/auth/validate", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["valid"] is True
        assert data["player_id"] == "player_1"

    def test_invalid_session(self, app):
        app._test_sm.get_session.return_value = None
        with app.test_client() as c:
            rv = c.get("/auth/validate", headers=AUTH)
        assert rv.status_code == 401
        data = rv.get_json()
        assert data["valid"] is False

    def test_no_bearer_token(self, app):
        with app.test_client() as c:
            rv = c.get("/auth/validate", headers=NO_AUTH)
        assert rv.status_code == 401
        data = rv.get_json()
        assert data["valid"] is False

    def test_bad_auth_format(self, app):
        with app.test_client() as c:
            rv = c.get("/auth/validate", headers=BAD_AUTH)
        assert rv.status_code == 401

    def test_exception_returns_500(self, app):
        app._test_sm.get_session.side_effect = RuntimeError("db crashed")
        with app.test_client() as c:
            rv = c.get("/auth/validate", headers=AUTH)
        assert rv.status_code == 500
        data = rv.get_json()
        assert data["valid"] is False


# ===========================================================================
# GET+PUT /auth/settings  (async, requires @require_auth)
# ===========================================================================


class TestSettings:
    @pytest.fixture
    def app(self):
        session = _make_session()
        sm = _make_session_manager(session)
        return _make_app(session=session, sm=sm)

    def test_get_settings_success(self, app):
        with app.test_client() as c:
            rv = c.get("/auth/settings", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert "timezone" in data["data"]

    def test_get_settings_no_db_user_id(self, app):
        app._test_session.db_user_id = None
        with app.test_client() as c:
            rv = c.get("/auth/settings", headers=AUTH)
        assert rv.status_code == 401

    def test_get_settings_no_auth(self, app):
        with app.test_client() as c:
            rv = c.get("/auth/settings", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_put_settings_success(self, app):
        with patch(
            "src.api.routes.auth.auth_service.update_user_timezone",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with app.test_client() as c:
                rv = c.put(
                    "/auth/settings",
                    json={"timezone": "Europe/London"},
                    headers=AUTH,
                )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert data["data"]["timezone"] == "Europe/London"

    def test_put_settings_missing_timezone(self, app):
        with app.test_client() as c:
            rv = c.put("/auth/settings", json={}, headers=AUTH)
        assert rv.status_code == 400

    def test_put_settings_invalid_timezone_rejected(self, app):
        """Regression test for issue #262: an unvalidated timezone string
        must be rejected with 400 rather than persisted."""
        with app.test_client() as c:
            rv = c.put(
                "/auth/settings",
                json={"timezone": "Not/A_Real_Zone"},
                headers=AUTH,
            )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False

    def test_put_settings_valid_timezone_accepted(self, app):
        with patch(
            "src.api.routes.auth.auth_service.update_user_timezone",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with app.test_client() as c:
                rv = c.put(
                    "/auth/settings",
                    json={"timezone": "America/New_York"},
                    headers=AUTH,
                )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert data["data"]["timezone"] == "America/New_York"

    def test_put_settings_update_fails(self, app):
        with patch(
            "src.api.routes.auth.auth_service.update_user_timezone",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with app.test_client() as c:
                rv = c.put(
                    "/auth/settings",
                    json={"timezone": "UTC"},
                    headers=AUTH,
                )
        assert rv.status_code == 500

    def test_put_settings_no_auth(self, app):
        with app.test_client() as c:
            rv = c.put(
                "/auth/settings",
                json={"timezone": "UTC"},
                headers=NO_AUTH,
            )
        assert rv.status_code == 401
