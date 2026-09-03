"""The HttpOnly session cookie that replaced the localStorage token (issue #493).

What these pin is the security contract itself, not just plumbing: the cookie
must be ``HttpOnly`` (or the change accomplished nothing), it must be cleared
with the same attributes it was set with (or logout does not log anybody out),
and the Bearer fallback the QA harnesses depend on must keep working while never
overriding a real cookie.
"""

from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask, jsonify, make_response

from src.api.config import DevelopmentConfig, ProductionConfig, TestingConfig
from src.api.session_cookie import (
    DEFAULT_COOKIE_NAME,
    clear_session_cookie,
    cookie_name,
    session_id_from_cookie,
    set_session_cookie,
)


def _cookie_header(response):
    """The raw Set-Cookie line for the session cookie, or None."""
    for value in response.headers.getlist("Set-Cookie"):
        if value.startswith(f"{DEFAULT_COOKIE_NAME}="):
            return value
    return None


def _attributes(header):
    """Set-Cookie attributes as a dict, so assertions don't depend on order.

    Werkzeug emits `Path=/` last with no trailing separator, so substring
    matching on "Path=/;" passes for a set cookie and fails for a cleared one —
    a difference in formatting, not in behaviour.
    """
    parts = header.split("; ")[1:]
    attrs = {}
    for part in parts:
        name, _, value = part.partition("=")
        attrs[name] = value
    return attrs


def _cookie_app(config_class=TestingConfig, **overrides):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.update(overrides)

    @app.route("/set")
    def set_route():
        return set_session_cookie(make_response(jsonify(ok=True)), "sid-42")

    @app.route("/clear")
    def clear_route():
        return clear_session_cookie(make_response(jsonify(ok=True)))

    @app.route("/read")
    def read_route():
        return jsonify(session_id=session_id_from_cookie())

    return app


# ---------------------------------------------------------------------------
# Cookie attributes
# ---------------------------------------------------------------------------


class TestCookieAttributes:
    def test_the_cookie_is_httponly(self):
        """The entire point of #493: script must not be able to read it."""
        header = _cookie_header(_cookie_app().test_client().get("/set"))
        assert "HttpOnly" in header

    def test_httponly_cannot_be_switched_off_by_config(self):
        """Not a knob. A config key here would be a footgun with no upside."""
        app = _cookie_app(SESSION_COOKIE_HTTPONLY=False, AUTH_COOKIE_HTTPONLY=False)
        assert "HttpOnly" in _cookie_header(app.test_client().get("/set"))

    def test_the_cookie_carries_the_session_id(self):
        header = _cookie_header(_cookie_app().test_client().get("/set"))
        assert header.startswith(f"{DEFAULT_COOKIE_NAME}=sid-42")

    def test_samesite_lax_blocks_cross_site_replay(self):
        assert "SameSite=Lax" in _cookie_header(_cookie_app().test_client().get("/set"))

    def test_production_marks_the_cookie_secure(self):
        header = _cookie_header(_cookie_app(ProductionConfig).test_client().get("/set"))
        assert "Secure" in header

    def test_local_development_does_not_require_https(self):
        """Dev is plain HTTP; a Secure cookie there would never be sent back."""
        header = _cookie_header(_cookie_app(DevelopmentConfig).test_client().get("/set"))
        assert "Secure" not in header

    def test_the_cookie_expires_with_the_session_it_names(self):
        """24h, matching Session.expires_at — a cookie outliving it is dead weight."""
        header = _cookie_header(_cookie_app().test_client().get("/set"))
        assert "Max-Age=86400" in header

    def test_no_lifetime_configured_yields_a_session_cookie(self):
        app = _cookie_app(PERMANENT_SESSION_LIFETIME=None)
        assert "Max-Age" not in _cookie_header(app.test_client().get("/set"))

    def test_lifetime_is_read_from_config_not_hardcoded(self):
        app = _cookie_app(PERMANENT_SESSION_LIFETIME=timedelta(minutes=30))
        assert "Max-Age=1800" in _cookie_header(app.test_client().get("/set"))

    def test_an_integer_lifetime_is_accepted_as_seconds(self):
        """Flask allows PERMANENT_SESSION_LIFETIME as a plain number of seconds.

        Assuming a timedelta would raise on every single response for an app
        written that way — a total outage caused by a config style choice.
        """
        app = _cookie_app(PERMANENT_SESSION_LIFETIME=600)
        assert "Max-Age=600" in _cookie_header(app.test_client().get("/set"))

    def test_path_is_the_app_root_so_the_socketio_handshake_gets_it(self):
        """Socket.IO is served from `/socket.io`, outside the SPA's base path.

        A cookie scoped to `/games/HeartOfVirtue/` would simply not be sent on
        that handshake, and the combat beat stream would connect as nobody —
        silently, since the socket still opens.
        """
        assert _attributes(_cookie_header(_cookie_app().test_client().get("/set")))["Path"] == "/"

    def test_the_name_is_not_flasks_own_session_cookie_key(self):
        """Claiming SESSION_COOKIE_NAME would rename Flask's signed session."""
        app = _cookie_app(SESSION_COOKIE_NAME="something_else")
        assert cookie_name(app) == DEFAULT_COOKIE_NAME

    def test_the_name_is_configurable(self):
        app = _cookie_app(AUTH_COOKIE_NAME="custom_name")
        with app.test_request_context("/"):
            assert cookie_name() == "custom_name"


class TestClearing:
    def test_clearing_repeats_the_path_so_the_browser_matches_the_cookie(self):
        """A bare delete_cookie(name) would not match a path-scoped cookie.

        The failure mode is the worst kind: logout returns 200 and the player
        stays authenticated.
        """
        attrs = _attributes(_cookie_header(_cookie_app().test_client().get("/clear")))
        assert attrs["Path"] == "/"
        assert "Expires" in attrs

    def test_clearing_keeps_the_security_attributes(self):
        header = _cookie_header(_cookie_app(ProductionConfig).test_client().get("/clear"))
        assert "HttpOnly" in header
        assert "Secure" in header
        assert "SameSite=Lax" in header

    def test_a_cleared_cookie_carries_no_value(self):
        header = _cookie_header(_cookie_app().test_client().get("/clear"))
        assert header.startswith(f"{DEFAULT_COOKIE_NAME}=;")


class TestReading:
    def test_reads_the_cookie_the_client_sent(self):
        client = _cookie_app().test_client()
        client.set_cookie(DEFAULT_COOKIE_NAME, "sid-7")
        assert client.get("/read").get_json()["session_id"] == "sid-7"

    def test_absent_cookie_reads_as_none(self):
        assert _cookie_app().test_client().get("/read").get_json()["session_id"] is None

    def test_empty_cookie_reads_as_none_not_empty_string(self):
        """An empty value must not be mistaken for a session id downstream."""
        client = _cookie_app().test_client()
        client.set_cookie(DEFAULT_COOKIE_NAME, "")
        assert client.get("/read").get_json()["session_id"] is None

    def test_outside_a_request_context_it_returns_none_rather_than_raising(self):
        """Socket.IO handlers are also invoked directly, with no context pushed."""
        assert session_id_from_cookie() is None


# ---------------------------------------------------------------------------
# Middleware resolution
# ---------------------------------------------------------------------------


@pytest.fixture
def resolver_app(make_route_app, make_stub_session, make_stub_session_manager):
    """An app whose one route reports which session the middleware resolved."""
    from flask import Blueprint
    from src.api.middleware.auth import resolve_session

    bp = Blueprint("probe", __name__)

    @bp.route("/whoami")
    def whoami():
        _, session, error = resolve_session()
        if error:
            return error
        return jsonify(session_id=session.session_id)

    session = make_stub_session(session_id="sid_cookie")
    sm = make_stub_session_manager(session, MagicMock())
    # Report back whatever id was looked up, so the test can tell *which*
    # credential the middleware chose rather than only that one worked.
    sm.get_session.side_effect = lambda sid: (
        make_stub_session(session_id=sid) if sid else None
    )
    return make_route_app(bp, session=session, session_manager=sm)


class TestMiddlewareResolution:
    def test_the_cookie_authenticates_the_request(self, resolver_app):
        client = resolver_app.test_client()
        client.set_cookie(DEFAULT_COOKIE_NAME, "sid_cookie")
        assert client.get("/whoami").get_json()["session_id"] == "sid_cookie"

    def test_the_bearer_header_still_works_for_non_browser_callers(self, resolver_app):
        """The QA harnesses hold a session id and no cookie jar."""
        response = resolver_app.test_client().get(
            "/whoami", headers={"Authorization": "Bearer sid_header"}
        )
        assert response.get_json()["session_id"] == "sid_header"

    def test_the_cookie_wins_over_a_stale_header(self, resolver_app):
        """A leftover Authorization header must not override a fresh cookie."""
        client = resolver_app.test_client()
        client.set_cookie(DEFAULT_COOKIE_NAME, "sid_cookie")
        response = client.get(
            "/whoami", headers={"Authorization": "Bearer sid_stale"}
        )
        assert response.get_json()["session_id"] == "sid_cookie"

    def test_no_credential_at_all_is_a_401(self, resolver_app):
        assert resolver_app.test_client().get("/whoami").status_code == 401


# ---------------------------------------------------------------------------
# The auth routes
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_client(make_route_app, make_stub_session, make_stub_session_manager):
    from src.api.routes.auth import auth_bp

    session = make_stub_session(session_id="sid_new")
    sm = make_stub_session_manager(session, MagicMock())
    sm.create_session.return_value = ("sid_new", "player_1")
    return make_route_app(auth_bp, session=session, session_manager=sm).test_client()


USER = {"id": "db_1", "timezone": "America/New_York"}


class TestAuthRoutesIssueTheCookie:
    def test_login_sets_the_session_cookie(self, auth_client):
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new=AsyncMock(return_value=USER),
        ):
            response = auth_client.post(
                "/auth/login", json={"username": "jean", "password": "pw"}
            )
        assert response.status_code == 200
        header = _cookie_header(response)
        assert header.startswith(f"{DEFAULT_COOKIE_NAME}=sid_new")
        assert "HttpOnly" in header

    def test_login_still_returns_the_id_in_the_body(self, auth_client):
        """Non-browser callers have no cookie jar; the SPA ignores this field."""
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new=AsyncMock(return_value=USER),
        ):
            response = auth_client.post(
                "/auth/login", json={"username": "jean", "password": "pw"}
            )
        assert response.get_json()["data"]["session_id"] == "sid_new"

    @pytest.fixture(autouse=True)
    def _isolate_limiter(self):
        """The login limiters are process-global and keyed on 127.0.0.1.

        Under ``-n auto --dist loadfile`` several files share a worker, so an
        un-reset increment here leaks into whatever runs next in that process.
        """
        from src.api.routes.auth import _login_limiter, _ip_limiter

        _login_limiter.clear_all()
        _ip_limiter.clear_all()
        yield
        _login_limiter.clear_all()
        _ip_limiter.clear_all()

    def test_a_failed_login_sets_no_cookie(self, auth_client):
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new=AsyncMock(return_value=None),
        ):
            response = auth_client.post(
                "/auth/login", json={"username": "jean", "password": "nope"}
            )
        assert response.status_code == 401
        assert _cookie_header(response) is None

    def test_register_sets_the_session_cookie(self, auth_client):
        with patch(
            "src.api.routes.auth.auth_service.create_user",
            new=AsyncMock(return_value=USER),
        ):
            response = auth_client.post(
                "/auth/register",
                json={"username": "jean", "password": "pw", "email": "j@e.com"},
            )
        assert response.status_code == 201
        assert "HttpOnly" in _cookie_header(response)

    def test_logout_expires_the_cookie(self, auth_client):
        auth_client.set_cookie(DEFAULT_COOKIE_NAME, "sid_new")
        response = auth_client.post("/auth/logout")
        assert response.status_code == 200
        header = _cookie_header(response)
        assert header.startswith(f"{DEFAULT_COOKIE_NAME}=;")
        assert _attributes(header)["Path"] == "/"
        # Clearing the cookie is only half of a logout. Without this, a
        # regression that expired a client-supplied id — or nothing at all —
        # would still pass, leaving the server session alive for 24h.
        auth_client.application.session_manager.expire_session.assert_called_once_with(
            "sid_new"
        )

    def test_logout_authenticates_from_the_cookie_alone(self, auth_client):
        """No Authorization header anywhere — the browser cannot send one."""
        auth_client.set_cookie(DEFAULT_COOKIE_NAME, "sid_new")
        assert auth_client.post("/auth/logout").status_code == 200

    def test_logout_clears_the_cookie_even_when_the_session_is_already_gone(
        self, make_route_app, make_stub_session, make_stub_session_manager
    ):
        """Otherwise the browser keeps replaying a credential that names nothing."""
        from src.api.routes.auth import auth_bp

        session = make_stub_session(session_id="sid_new")
        sm = make_stub_session_manager(session, MagicMock())
        sm.expire_session.return_value = False
        client = make_route_app(auth_bp, session=session, session_manager=sm).test_client()
        client.set_cookie(DEFAULT_COOKIE_NAME, "sid_new")

        response = client.post("/auth/logout")
        assert response.status_code == 200
        assert _cookie_header(response).startswith(f"{DEFAULT_COOKIE_NAME}=;")

    def test_validate_accepts_the_cookie(self, auth_client):
        auth_client.set_cookie(DEFAULT_COOKIE_NAME, "sid_new")
        assert auth_client.get("/auth/validate").get_json()["valid"] is True


# ---------------------------------------------------------------------------
# Socket.IO
# ---------------------------------------------------------------------------


class TestSocketHandshake:
    def _handlers(self):
        """Capture the handlers register_socket_handlers() installs."""
        from src.api.sockets import register_socket_handlers

        registered = {}

        class FakeSocketIO:
            def on(self, event):
                def decorator(fn):
                    registered[event] = fn
                    return fn

                return decorator

        register_socket_handlers(FakeSocketIO())
        return registered

    @contextmanager
    def _handshake(self, app, cookie=None):
        """A request context shaped like a Socket.IO handshake.

        Flask-SocketIO grafts the socket id onto the request object; a plain
        Flask test context has no ``sid``, and the handlers log it. Setting it
        here keeps the test exercising the real handler body instead of
        patching ``request`` wholesale — which would also patch away the
        cookies these tests are about.
        """
        headers = {"Cookie": f"{DEFAULT_COOKIE_NAME}={cookie}"} if cookie else {}
        with app.test_request_context("/socket.io/", headers=headers) as ctx:
            ctx.request.sid = "socket-1"
            yield

    def test_join_combat_resolves_the_room_from_the_handshake_cookie(
        self, make_route_app, make_stub_session, make_stub_session_manager
    ):
        """The client can no longer name its own session, so the server does."""
        session = make_stub_session(session_id="sid_sock")
        sm = make_stub_session_manager(session, MagicMock())
        app = make_route_app(_empty_blueprint(), session=session, session_manager=sm)
        handlers = self._handlers()

        with self._handshake(app, cookie="sid_sock"):
            with patch("src.api.sockets.join_room") as join_room, patch(
                "src.api.sockets.emit"
            ) as emit:
                handlers["join_combat"]({})

        join_room.assert_called_once_with("combat_sid_sock")
        emit.assert_called_once_with("joined_combat", {"joined": True})

    def test_a_payload_session_id_is_used_when_there_is_no_cookie(
        self, make_route_app, make_stub_session, make_stub_session_manager
    ):
        """The non-browser fallback: a Socket.IO client outside a cookie jar."""
        session = make_stub_session(session_id="sid_payload")
        sm = make_stub_session_manager(session, MagicMock())
        app = make_route_app(_empty_blueprint(), session=session, session_manager=sm)
        handlers = self._handlers()

        with self._handshake(app):
            with patch("src.api.sockets.join_room") as join_room, patch(
                "src.api.sockets.emit"
            ):
                handlers["join_combat"]({"session_id": "sid_payload"})

        join_room.assert_called_once_with("combat_sid_payload")

    def test_no_cookie_and_no_payload_is_rejected(
        self, make_route_app, make_stub_session, make_stub_session_manager
    ):
        session = make_stub_session(session_id="sid_sock")
        sm = make_stub_session_manager(session, MagicMock())
        app = make_route_app(_empty_blueprint(), session=session, session_manager=sm)
        handlers = self._handlers()

        with self._handshake(app):
            with patch("src.api.sockets.emit") as emit, patch(
                "src.api.sockets.join_room"
            ) as join_room:
                handlers["join_combat"]({})

        emit.assert_called_once_with("error", {"message": "Missing or invalid session credentials"})
        join_room.assert_not_called()

    def test_the_cookie_beats_a_payload_that_names_another_session(
        self, make_route_app, make_stub_session, make_stub_session_manager
    ):
        """Script on the page must not be able to join somebody else's room.

        A payload session id has never been authenticated, only believed. If the
        payload won, injected script could name another session and read its
        combat beat stream — so the cookie, which the page cannot forge, wins.
        """
        session = make_stub_session(session_id="sid_cookie")
        sm = make_stub_session_manager(session, MagicMock())
        app = make_route_app(_empty_blueprint(), session=session, session_manager=sm)
        handlers = self._handlers()

        with self._handshake(app, cookie="sid_cookie"):
            with patch("src.api.sockets.join_room") as join_room, patch(
                "src.api.sockets.emit"
            ):
                handlers["join_combat"]({"session_id": "sid_someone_else"})

        join_room.assert_called_once_with("combat_sid_cookie")

    def test_leave_combat_also_resolves_from_the_cookie(
        self, make_route_app, make_stub_session, make_stub_session_manager
    ):
        session = make_stub_session(session_id="sid_sock")
        sm = make_stub_session_manager(session, MagicMock())
        app = make_route_app(_empty_blueprint(), session=session, session_manager=sm)
        handlers = self._handlers()

        with self._handshake(app, cookie="sid_sock"):
            with patch("src.api.sockets.leave_room") as leave_room, patch(
                "src.api.sockets.emit"
            ):
                handlers["leave_combat"]({})

        leave_room.assert_called_once_with("combat_sid_sock")


def _empty_blueprint():
    from flask import Blueprint

    return Blueprint("empty", __name__)
