"""
Coverage tests for src/api/routes/auth.py (35% -> target ~80%)

Uncovered: 14-44, 48-78, 115, 159-199, 235, 252-276, 329-353, 378-410, 437-485

Strategy: minimal Flask app with mocked session_manager and auth_service,
async routes need AsyncMock for auth_service calls.
"""

import logging

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from flask import Flask
from werkzeug.wrappers import Request

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


AUTH = {"Authorization": "Bearer sid_a1"}
NO_AUTH = {}
BAD_AUTH = {"Authorization": "NotBearer sid_a1"}


@pytest.fixture
def auth_app(make_route_app, make_stub_session, make_stub_session_manager):
    """A one-blueprint app for ``auth_bp`` on the shared route harness.

    The session is a *real* ``Session`` (``make_stub_session``) rather than a
    MagicMock, so ``session.data``/``expires_at``/``to_dict()`` behave as
    production's do and an attribute the routes read but ``Session`` never
    defines raises instead of being invented. The manager is
    ``spec``-constrained against ``SessionManager``.

    Exposes ``app.stub_session`` and ``app.stub_session_manager``.
    """

    def _auth_app(session=None, sm=None):
        from src.api.routes.auth import auth_bp

        if session is None:
            session = make_stub_session(
                session_id="sid_a1",
                player_id="player_1",
                db_user_id="db_1",
                timezone="America/New_York",
            )
        if sm is None:
            sm = make_stub_session_manager(session, MagicMock())
        return make_route_app(auth_bp, session=session, session_manager=sm)

    return _auth_app


# ===========================================================================
# POST /auth/register
# ===========================================================================


class TestRegister:
    @pytest.fixture
    def app(self, auth_app):
        return auth_app()

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
        """``RegistrationValidationError``, because the route echoes a message
        on the strength of its TYPE now, not on its wording surviving a
        five-substring deny-list. A plain ValueError is infrastructure until
        declared otherwise -- see test_register_infra_value_error_is_masked."""
        from src.api.services.auth_service import RegistrationValidationError

        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            side_effect=RegistrationValidationError("Username too short"),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/register",
                    json={"username": "ab", "password": "pw", "email": "x@test.com"},
                )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["error"] == "validation_error"

    def test_register_infra_value_error_is_masked(self, app):
        """The other half of the same contract, in the suite that covers this
        route generally: an undeclared ValueError is never echoed."""
        leak = "could not connect to postgres://svc:hunter2@db.internal:5432/hov"
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            side_effect=ValueError(leak),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/register",
                    json={
                        "username": "abcd",
                        "password": "pw",
                        "email": "x@test.com",
                    },
                )
        assert rv.status_code == 503
        assert leak not in rv.data.decode()

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
    def app(self, auth_app):
        return auth_app()

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
        from src.api.routes.auth import _login_limiter, _ip_limiter

        _login_limiter.clear_all()
        _ip_limiter.clear_all()
        yield
        _login_limiter.clear_all()
        _ip_limiter.clear_all()

    @pytest.fixture
    def app(self, auth_app):
        return auth_app()

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


class TestLoginPerIpThrottle:
    """Second, IP-only throttle: catches credential-stuffing / username-spray
    from a single IP, which the username+IP limiter never trips (each new
    username gets a fresh budget)."""

    @pytest.fixture(autouse=True)
    def _isolate_limiter(self):
        from src.api.routes.auth import _login_limiter, _ip_limiter

        _login_limiter.clear_all()
        _ip_limiter.clear_all()
        yield
        _login_limiter.clear_all()
        _ip_limiter.clear_all()

    @pytest.fixture
    def app(self, auth_app):
        return auth_app()

    # Pin the source IP so the throttle key is deterministic regardless of the
    # test client's default REMOTE_ADDR.
    _ATTACKER = {"REMOTE_ADDR": "203.0.113.50"}

    def test_username_spray_from_one_ip_is_throttled(self, app):
        """Distinct usernames from one IP never trip the username+IP limiter,
        but the IP-only limiter locks the source out after its threshold."""
        from src.api.routes.auth import _IP_RATE_LIMIT

        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with app.test_client() as c:
                # Each attempt uses a brand-new username, so no username+IP key
                # ever reaches its own (10) limit — only the IP counter climbs.
                for i in range(_IP_RATE_LIMIT):
                    rv = c.post(
                        "/auth/login",
                        json={"username": f"spray{i}", "password": "wrong"},
                        environ_base=self._ATTACKER,
                    )
                    assert rv.status_code == 401, f"attempt {i} should be a 401"

                # The next distinct-username attempt is now IP-throttled.
                rv = c.post(
                    "/auth/login",
                    json={"username": "spray_final", "password": "wrong"},
                    environ_base=self._ATTACKER,
                )
        assert rv.status_code == 429
        body = rv.get_json()
        assert body["error"] == "rate_limited"
        # `message`, not `error`, carries the prose. LoginPage.jsx renders
        # `data.message` for any non-401 / non-5xx auth failure, so a body
        # without it degrades silently to the generic "Authentication
        # failed" copy and the player is never told they are throttled.
        assert body["message"] == (
            "Too many failed login attempts. Please try again later."
        )

    def test_successful_login_does_not_clear_ip_counter(self, app):
        """A valid login clears only the per-account key; the IP evidence of an
        ongoing spray must survive so the attack stays throttled."""
        from src.api.routes.auth import _ip_limiter, _IP_RATE_LIMIT

        ip_key = self._ATTACKER["REMOTE_ADDR"]

        # Fill the IP counter to its limit via failed logins.
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with app.test_client() as c:
                for i in range(_IP_RATE_LIMIT):
                    c.post(
                        "/auth/login",
                        json={"username": f"spray{i}", "password": "wrong"},
                        environ_base=self._ATTACKER,
                    )

        assert _ip_limiter.is_limited(ip_key) is True

        # A genuine success on a fresh username still 429s: the IP is locked and
        # the success path must not reset the IP counter.
        mock_user = {"id": "u1", "username": "legit", "timezone": "UTC"}
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/auth/login",
                    json={"username": "legit", "password": "right"},
                    environ_base=self._ATTACKER,
                )
        assert rv.status_code == 429
        assert _ip_limiter.is_limited(ip_key) is True

    def test_login_key_collapses_ipv6_to_the_same_64_prefix_as_the_ip_tier(self):
        """The username+IP key must key on the same collapsed client identity
        the IP-only tier uses. Keying this half on the raw ``remote_addr``
        would hand an IPv6 attacker a fresh per-username budget for every
        address in their /64.

        ``client_ip`` itself is tested in ``tests/test_rate_limiter.py``, where
        it now lives -- it was previously copy-pasted into both this blueprint
        and ``npc_chat.py``.
        """
        from src.api.routes.auth import _login_rate_limit_key

        app = Flask(__name__)
        keys = set()
        for suffix in ("::dead:beef", "::1"):
            with app.test_request_context(
                "/auth/login",
                environ_base={"REMOTE_ADDR": f"2001:db8:abcd:1234{suffix}"},
            ):
                keys.add(_login_rate_limit_key("SprayTarget"))
        assert keys == {"spraytarget:2001:db8:abcd:1234::"}


# ===========================================================================
# POST /auth/logout  (requires @require_auth)
# ===========================================================================


class TestLogout:
    @pytest.fixture
    def app(self, auth_app):
        return auth_app()

    def test_logout_success(self, app):
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_logout_session_not_found(self, app):
        """A session that is already gone still logs you out.

        Since #493 the credential is an HttpOnly cookie the page cannot clear,
        so refusing here left the browser pinned to a dead session forever.
        """
        app.stub_session_manager.expire_session.return_value = False
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=AUTH)
        assert rv.status_code == 200

    def test_logout_no_auth(self, app):
        """No credential at all: nothing to expire, but still a clean logout."""
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=NO_AUTH)
        assert rv.status_code == 200
        app.stub_session_manager.expire_session.assert_not_called()

    def test_logout_bad_auth(self, app):
        """An unparseable credential must not strand the caller either."""
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=BAD_AUTH)
        assert rv.status_code == 200

    def test_logout_expired_session_still_clears(self, app):
        """The expired-cookie case: the one that used to be an inescapable 401."""
        app.stub_session_manager.get_session.return_value = None
        with app.test_client() as c:
            rv = c.post("/auth/logout", headers=AUTH)
        assert rv.status_code == 200

    def test_logout_session_manager_not_initialized(self, app):
        # Issue #408: a falsy session_manager must still yield the 500 "not
        # initialized" response. Logout tolerates a dead *credential* but not a
        # dead *server* — it cannot expire anything, so it must not claim to.
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
    def app(self, auth_app):
        return auth_app()

    def test_valid_session(self, app):
        with app.test_client() as c:
            rv = c.get("/auth/validate", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["valid"] is True
        assert data["player_id"] == "player_1"

    def test_invalid_session(self, app):
        app.stub_session_manager.get_session.return_value = None
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
        app.stub_session_manager.get_session.side_effect = RuntimeError("db crashed")
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
    def app(self, auth_app):
        return auth_app()

    def test_get_settings_success(self, app):
        with app.test_client() as c:
            rv = c.get("/auth/settings", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert "timezone" in data["data"]

    def test_get_settings_no_db_user_id(self, app):
        app.stub_session.db_user_id = None
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


# ===========================================================================
# POST /auth/register -- the throttle
# ===========================================================================


class TestRegisterThrottle:
    """``/auth/register`` had no throttle at all, which mattered twice over:
    account creation is unbounded work against the DB (a bcrypt hash per
    attempt), and a fresh account is a fresh session -- which is how
    ``feedback.py``'s per-session cap on *real GitHub issue creation* used to
    be walked past.
    """

    @pytest.fixture
    def app(self, auth_app):
        return auth_app()

    @pytest.fixture(autouse=True)
    def _clear_limiter(self):
        from src.api.routes import auth as auth_module

        auth_module._register_limiter.clear_all()
        yield
        auth_module._register_limiter.clear_all()

    @staticmethod
    def _register(client, ip, username="Jean"):
        return client.post(
            "/auth/register",
            json={
                "username": username,
                "password": "secret",
                "email": "j@test.com",
            },
            environ_base={"REMOTE_ADDR": ip},
        )

    def test_the_limiter_exists_and_is_tunable(self):
        from src.api.rate_limiter import RateLimiter
        from src.api.routes import auth as auth_module

        assert isinstance(auth_module._register_limiter, RateLimiter)
        assert auth_module._register_limiter.limit == auth_module._REGISTER_RATE_LIMIT

    def test_the_budget_runs_out(self, app):
        from src.api.routes import auth as auth_module

        mock_user = {"id": "u", "username": "Jean", "timezone": "America/New_York"}
        limit = auth_module._register_limiter.limit
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            with app.test_client() as c:
                for i in range(limit):
                    assert self._register(c, "198.51.100.20").status_code == 201, i
                rv = self._register(c, "198.51.100.20")
        assert rv.status_code == 429
        body = rv.get_json()
        assert body["error"] == "rate_limited"
        assert body["message"] == (
            "Too many registration attempts. Please try again later."
        )

    def test_it_is_keyed_per_source(self, app):
        from src.api.routes import auth as auth_module

        mock_user = {"id": "u", "username": "Jean", "timezone": "America/New_York"}
        limit = auth_module._register_limiter.limit
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            with app.test_client() as c:
                for _ in range(limit + 1):
                    self._register(c, "198.51.100.21")
                # A different client is not collateral damage.
                rv = self._register(c, "198.51.100.22")
        assert rv.status_code == 201

    def test_a_malformed_payload_spends_the_budget_too(self, app):
        """The throttle now runs *before* the body is parsed, so it counts.

        This used to assert the opposite -- that a request rejected at shape
        validation cost nobody anything -- on the argument that a malformed
        payload is free. It is not free: `/auth/register` takes no credentials,
        so parsing up to MAX_CONTENT_LENGTH of attacker-chosen JSON was the one
        piece of work on this route that no throttle gated. And the budget the
        old ordering protected was never protectable: an attacker exhausting a
        shared NAT's register budget sends well-formed payloads, which are
        cheaper to produce and were always counted.
        """
        from src.api.routes import auth as auth_module

        limit = auth_module._register_limiter.limit
        with app.test_client() as c:
            for i in range(limit):
                rv = c.post(
                    "/auth/register",
                    json={"username": "Jean"},
                    environ_base={"REMOTE_ADDR": "198.51.100.23"},
                )
                assert rv.status_code == 400, i
            rv = c.post(
                "/auth/register",
                json={"username": "Jean"},
                environ_base={"REMOTE_ADDR": "198.51.100.23"},
            )
        assert rv.status_code == 429
        assert auth_module._register_limiter.is_limited("198.51.100.23") is True

    def test_the_throttle_answers_before_the_body_is_parsed(self, app):
        """The property the ordering exists for, asserted at the parse itself.

        A 429 that still parsed the body would satisfy the test above while
        leaving the work ungated, so this watches ``request.get_json`` rather
        than the status code alone. The over-budget request must not reach it.
        """
        from src.api.routes import auth as auth_module

        parses = []
        real_get_json = Request.get_json

        def _counting_get_json(self, *args, **kwargs):
            parses.append(self.path)
            return real_get_json(self, *args, **kwargs)

        limit = auth_module._register_limiter.limit
        with app.test_client() as c:
            for _ in range(limit):
                self._register(c, "198.51.100.24")
            with patch.object(Request, "get_json", _counting_get_json):
                rv = self._register(c, "198.51.100.24")
        assert rv.status_code == 429
        assert parses == []


class TestAHostileBodyWritesNoTraceback:
    """`/auth/register` is unauthenticated, so anything it logs per request is
    logged at whatever rate an attacker chooses. With LOG_FILE set (5 MiB x 3
    rotation, `src/api/app.py`) a flood of tracebacks evicts the audit trail.

    The route's `except Exception: logger.exception(...)` is nonetheless the
    right thing there, because no *client-controlled* input reaches it. That
    is the claim under test, and it is not obvious -- it rests on
    `get_json(silent=True)` returning None rather than raising for every
    malformed shape, and on the body cap being enforced before the view. Both
    are somebody else's code, so this asserts the outcome instead of trusting
    them: a traceback here means a new input path found its way to the
    catch-all, and the fix is a 4xx at that path, not a quieter log call.
    """

    @pytest.fixture
    def app(self, auth_app):
        return auth_app()

    @pytest.fixture(autouse=True)
    def _clear_limiter(self):
        from src.api.routes import auth as auth_module

        auth_module._register_limiter.clear_all()
        yield
        auth_module._register_limiter.clear_all()

    #: Every shape a client can put in a body that this route does not want.
    HOSTILE_BODIES = {
        "not json at all": (b"<<< not json >>>", "application/json"),
        "truncated json": (b'{"username": "a", ', "application/json"),
        "wrong content type": (b"username=a&password=b", "text/plain"),
        "json null": (b"null", "application/json"),
        "json scalar": (b"12345", "application/json"),
        "json list": (b'["username", "password"]', "application/json"),
        "nulls for strings": (
            b'{"username": null, "password": null, "email": null}',
            "application/json",
        ),
        "nested objects for strings": (
            b'{"username": {}, "password": [], "email": 7}',
            "application/json",
        ),
        "empty body": (b"", "application/json"),
    }

    @pytest.mark.parametrize("label", sorted(HOSTILE_BODIES))
    def test_no_traceback_is_logged(self, app, caplog, label):
        body, content_type = self.HOSTILE_BODIES[label]
        with caplog.at_level(logging.DEBUG):
            with app.test_client() as c:
                rv = c.post("/auth/register", data=body, content_type=content_type)
        assert rv.status_code == 400, rv.get_json()
        with_tracebacks = [r for r in caplog.records if r.exc_info]
        assert with_tracebacks == [], [r.getMessage() for r in with_tracebacks]

    def test_a_real_server_fault_still_logs_one(self, app, caplog):
        """The control. Every assertion above holds for a route that logs
        nothing at all -- a worse bug than the one they guard against -- so the
        traceback the catch-all exists for has to still arrive."""
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new_callable=AsyncMock,
            side_effect=RuntimeError("the database fell over"),
        ):
            with caplog.at_level(logging.DEBUG):
                with app.test_client() as c:
                    rv = c.post(
                        "/auth/register",
                        json={
                            "username": "Jean",
                            "password": "secret",
                            "email": "j@test.com",
                        },
                    )
        assert rv.status_code == 500
        assert [r for r in caplog.records if r.exc_info]


class TestASuccessfulLoginAlsoCostsSomething:
    """The two original login tiers are FAILURE counters, and that left a hole.

    ``_record_failed_login`` runs only under ``if not user``, so a caller
    holding one valid credential never touches either budget and can replay
    that login without limit -- each request costing a full Argon2id verify at
    the configured memory cost, on a synchronous worker. Credential guessing is
    bounded by wrong answers; this attack never gives one.

    The property asserted here is the one that was missing, and it is stated
    against the limiter's own configured ceiling rather than a number written
    here: a source that keeps logging in SUCCESSFULLY eventually gets a 429.
    """

    @pytest.fixture(autouse=True)
    def _isolate_limiters(self):
        from src.api.routes.auth import (
            _ip_limiter,
            _login_attempt_limiter,
            _login_limiter,
        )

        for limiter in (_login_limiter, _ip_limiter, _login_attempt_limiter):
            limiter.clear_all()
        yield
        for limiter in (_login_limiter, _ip_limiter, _login_attempt_limiter):
            limiter.clear_all()

    @pytest.fixture
    def app(self, auth_app):
        return auth_app()

    def _login_ok(self, client):
        return client.post(
            "/auth/login", json={"username": "Jean", "password": "secret"}
        )

    def test_the_ceiling_is_a_real_one(self):
        """Non-vacuity in both directions: a limit of 0 would make the loop
        below trivially true, and an enormous one would make it untestable."""
        from src.api.routes.auth import _login_attempt_limiter

        assert 1 < _login_attempt_limiter.limit <= 10_000

    def test_repeated_successful_logins_are_eventually_throttled(self, app):
        from src.api.routes.auth import _login_attempt_limiter

        ceiling = _login_attempt_limiter.limit
        mock_user = {"id": "user_001", "username": "Jean", "timezone": "UTC"}
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            with app.test_client() as c:
                statuses = [self._login_ok(c).status_code for _ in range(ceiling + 2)]

        assert 200 in statuses, "no login succeeded; the probe is vacuous"
        assert 429 in statuses, (
            "%d consecutive SUCCESSFUL logins from one source were all "
            "accepted. Every one of them paid for an Argon2 verify, and "
            "neither failure-counting tier can ever see them."
            % (ceiling + 2)
        )
        # And the throttle arrives at the ceiling, not somewhere arbitrary.
        assert statuses.index(429) >= ceiling - 1, statuses.index(429)

    def test_the_failure_tiers_are_untouched(self, app):
        """The control. Adding a third tier must not have moved the behaviour
        the first two own: a wrong password still trips the failed-attempt
        counter with its own message."""
        from src.api.routes.auth import _login_limiter

        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with app.test_client() as c:
                seen = set()
                for _ in range(_login_limiter.limit + 2):
                    rv = c.post(
                        "/auth/login",
                        json={"username": "Jean", "password": "wrong"},
                    )
                    seen.add(rv.status_code)
                    if rv.status_code == 429:
                        assert "failed login" in rv.get_json()["message"].lower()
                        break
        assert 401 in seen
        assert 429 in seen

    def test_one_ordinary_login_is_not_throttled(self, app):
        """The other control: a cost ceiling that refused the first login
        would satisfy the assertions above and lock everybody out."""
        mock_user = {"id": "user_001", "username": "Jean", "timezone": "UTC"}
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            with app.test_client() as c:
                assert self._login_ok(c).status_code == 200
