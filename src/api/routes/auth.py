"""Authentication routes."""

import logging

from flask import Blueprint, request, jsonify, make_response
from src.api.middleware.auth import resolve_session
from src.api.session_cookie import (
    clear_session_cookie,
    session_id_from_cookie,
    set_session_cookie,
)
from src.api.rate_limiter import RateLimiter
from src.api.services.auth_service import auth_service
from functools import wraps
import asyncio

auth_bp = Blueprint("auth", __name__)

logger = logging.getLogger(__name__)

# Simple in-memory login throttle: 10 failed attempts per username+IP per 15
# minutes. Per-worker (not shared across Gunicorn workers) — see GitHub issue
# #284 and `src.api.rate_limiter` for the bounded-store rationale, shared with
# feedback.py's submission throttle. Only failed (invalid-credential) attempts
# count, so retries after a typo or a flaky DB call don't lock out a
# legitimate player.
_LOGIN_RATE_LIMIT = 10
_LOGIN_RATE_WINDOW = 900  # 15 minutes
_login_limiter = RateLimiter(limit=_LOGIN_RATE_LIMIT, window_seconds=_LOGIN_RATE_WINDOW)

# Second, independent throttle keyed on IP alone. The username+IP limiter above
# resets its budget every time the username changes, so a single IP can spray
# thousands of distinct usernames (credential stuffing) without ever tripping
# it. This IP-only limiter catches that horizontal attack. The threshold is set
# far above what a legitimate human — even several sharing one NAT'd IP — would
# fail in the window, so it's defense-in-depth against spray, not a per-account
# gate. Same per-worker caveat as above (issue #284): the effective limit is
# _IP_RATE_LIMIT * worker_count, so treat it as raising the cost of spray, not
# an airtight cap. It keys on request.remote_addr, which is the direct client
# IP by default (no proxy/load balancer in this deployment) and automatically
# becomes the real client IP if the opt-in ProxyFix is ever configured (see
# _apply_proxy_fix / TRUSTED_PROXY_COUNT and tests/test_proxy_fix.py).
_IP_RATE_LIMIT = 60
_IP_RATE_WINDOW = 900  # 15 minutes
_ip_limiter = RateLimiter(limit=_IP_RATE_LIMIT, window_seconds=_IP_RATE_WINDOW)


def _client_ip() -> str:
    """The client's IP, collapsed to a /64 prefix for IPv6.

    Full IPv6 addresses (/128) are cheap for an attacker to rotate within their
    allocation, which would defeat an IP-keyed throttle; a typical end-site is a
    /64, so keying on that prefix throttles the whole allocation. IPv4 and
    unparseable values are used verbatim. Returns ``"unknown"`` when called
    outside a request context (e.g. direct helper calls in tests).
    """
    try:
        ip = request.remote_addr or "unknown"
    except RuntimeError:  # working outside of request context
        return "unknown"
    if ":" in ip:  # IPv6
        try:
            import ipaddress

            network = ipaddress.ip_network(f"{ip}/64", strict=False)
            return str(network.network_address)
        except ValueError:
            return ip
    return ip


def _login_rate_limit_key(username: str) -> str:
    return f"{(username or '').strip().lower()}:{request.remote_addr or 'unknown'}"


def _is_login_rate_limited(key: str) -> bool:
    """True if either the username+IP or the IP-only throttle is tripped."""
    return _login_limiter.is_limited(key) or _ip_limiter.is_limited(_client_ip())


def _record_failed_login(key: str) -> None:
    _login_limiter.record(key)
    _ip_limiter.record(_client_ip())


def _clear_login_attempts(key: str) -> None:
    # Clear only the per-account key on success. The IP counter is left to decay
    # naturally so a single valid login mid-spray doesn't wipe the accumulated
    # IP-level evidence of an ongoing attack.
    _login_limiter.clear(key)


# Substrings that mark an internal config/infrastructure error whose text must
# never reach the client (avoids leaking env-var names, connection URLs, etc).
_CONFIG_LEAK_MARKERS = ("_URL", "_KEY", "_TOKEN", "not set", "os.environ")


def _is_config_leak(msg: str) -> bool:
    """True if an error message would expose internal config/infra details."""
    return any(marker in msg for marker in _CONFIG_LEAK_MARKERS)


def _establish_session_for_user(session_manager, username, user):
    """Create a session for ``username`` and link it to the DB user record.

    Shared by register and login so the session-creation + linkage contract
    (db_user_id, timezone default) lives in exactly one place.
    """
    session_id, player_id = session_manager.create_session(username)
    session = session_manager.get_session(session_id)
    session.db_user_id = user["id"]
    session.data["timezone"] = user.get("timezone", "America/New_York")
    return session_id, player_id


def require_auth(f):
    """Require a valid session for the wrapped route.

    Resolves the session via the shared ``resolve_session`` helper (session
    only — no player is fetched) and stashes it on ``request.session_obj`` /
    ``request.session_manager`` for the handler. Works for both sync and async
    routes.
    """

    @wraps(f)
    async def async_decorated(*args, **kwargs):
        session_manager, session, error = resolve_session()
        if error:
            return error
        request.session_obj = session
        request.session_manager = session_manager
        return await f(*args, **kwargs)

    @wraps(f)
    def sync_decorated(*args, **kwargs):
        session_manager, session, error = resolve_session()
        if error:
            return error
        request.session_obj = session
        request.session_manager = session_manager
        return f(*args, **kwargs)

    if asyncio.iscoroutinefunction(f):
        return async_decorated
    return sync_decorated


def _is_browser_caller():
    """True when the request looks like it came from a page, not a harness.

    Login and register still return ``session_id`` in the body for the callers
    that have no cookie jar — the bug-hunt harness, API-only Inquisitor mode
    and the route tests. Browsers must not receive it: a script that lands an
    XSS at sign-in would otherwise capture a portable 24h credential, which is
    exactly the exposure the HttpOnly cookie exists to close. A page always
    sends ``Origin`` on a same-origin POST, or already carries our cookie;
    neither is true of the harnesses.
    """
    return bool(request.headers.get("Origin")) or session_id_from_cookie() is not None


def _session_id_for_body(session_id):
    """``session_id`` for non-browser callers, omitted for browsers."""
    return {} if _is_browser_caller() else {"session_id": session_id}


@auth_bp.route("/auth/register", methods=["POST"])
async def register():
    """Create a new player account and session.

    Request body:
        {
            "username": "str",
            "password": "str",
            "email": "str"
        }

    Returns:
        {
            "success": bool,
            "data": {
                "session_id": "str",
                "username": "str",
                "message": "str"
            }
        }
    """
    try:
        data = request.get_json(silent=True)

        if (
            not isinstance(data, dict)
            or "username" not in data
            or "password" not in data
            or "email" not in data
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "Missing username, password, or email",
                    }
                ),
                400,
            )

        if not all(
            isinstance(data[k], str) for k in ("username", "password", "email")
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "username, password, and email must be strings",
                    }
                ),
                400,
            )

        username = data["username"].strip()
        password = data["password"]
        email = data["email"].strip()

        # Registration logic using auth_service
        try:
            user = await auth_service.create_user(username, password, email)
        except ValueError as ve:
            msg = str(ve)
            # Don't expose internal config/infrastructure details to users
            if _is_config_leak(msg):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "service_unavailable",
                            "message": "Registration is temporarily unavailable. Please try again later.",
                        }
                    ),
                    503,
                )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": msg,
                    }
                ),
                400,
            )
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "conflict_error",
                            "message": "Username already exists",
                        }
                    ),
                    409,
                )
            raise e

        # Get session manager from app context
        from flask import current_app

        session_manager = current_app.session_manager

        # Create session and link it to the DB user record.
        session_id, player_id = _establish_session_for_user(
            session_manager, username, user
        )

        # The session id also travels in an HttpOnly cookie (issue #493) — that
        # is what the browser actually authenticates with from here on. It stays
        # in the body as well for the non-browser callers documented on
        # `middleware.auth.session_token`; the SPA no longer reads it.
        return set_session_cookie(
            make_response(
                jsonify(
                    {
                        "success": True,
                        "data": {
                            **_session_id_for_body(session_id),
                            "message": "Account created successfully. Welcome!",
                        },
                    }
                ),
                201,
            ),
            session_id,
        )

    except Exception:
        logger.exception("Unhandled error in register")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "server_error",
                    "message": "Internal server error",
                }
            ),
            500,
        )


@auth_bp.route("/auth/login", methods=["POST"])
async def login():
    """Create a new player session (or login existing player).

    Request body:
        {
            "username": "str",
            "password": "str"
        }

    Returns:
        {
            "success": bool,
            "data": {
                "session_id": "str",
                "username": "str",
                "message": "str"
            }
        }
    """
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict) or "username" not in data or "password" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "Missing username or password",
                    }
                ),
                400,
            )

        if not isinstance(data["username"], str) or not isinstance(
            data["password"], str
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "username and password must be strings",
                    }
                ),
                400,
            )

        username = data["username"].strip()
        password = data["password"]

        rate_key = _login_rate_limit_key(username)
        if _is_login_rate_limited(rate_key):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "rate_limited",
                        "message": "Too many failed login attempts. Please try again later.",
                    }
                ),
                429,
            )

        # Authenticate using auth_service
        user = await auth_service.authenticate_user(username, password)

        if not user:
            _record_failed_login(rate_key)
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "auth_error",
                        "message": "Invalid username or password",
                    }
                ),
                401,
            )

        _clear_login_attempts(rate_key)

        # Get session manager from app context
        from flask import current_app

        session_manager = current_app.session_manager

        # Create session and link it to the DB user record.
        session_id, player_id = _establish_session_for_user(
            session_manager, username, user
        )

        # See register() — the browser authenticates with the HttpOnly cookie.
        return set_session_cookie(
            make_response(
                jsonify(
                    {
                        "success": True,
                        "data": {
                            **_session_id_for_body(session_id),
                            "message": "Welcome back!",
                        },
                    }
                ),
                200,
            ),
            session_id,
        )

    except Exception as e:
        logger.exception("Unhandled error in login")
        msg = str(e)
        # Don't expose internal config/infrastructure details to users
        if _is_config_leak(msg):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "service_unavailable",
                        "message": "Login is temporarily unavailable. Please try again later.",
                    }
                ),
                503,
            )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "server_error",
                    "message": "Internal server error",
                }
            ),
            500,
        )


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    """End a player session.

    Authenticated by the HttpOnly session cookie (or, for non-browser callers,
    an ``Authorization: Bearer <session_id>`` header). Clears the cookie on the
    way out.

    Returns:
        {
            "success": bool,
            "message": "str"
        }
    """
    try:
        # Deliberately NOT @require_auth. That decorator 401s before the body
        # runs whenever the cookie names an expired or unknown session — so the
        # cookie was never cleared, and since #493 the page cannot clear it
        # itself. The browser was left pinned to a dead credential with no way
        # out. Logout must therefore always clear, whether or not the session
        # still resolves.
        #
        # The trade-off, accepted knowingly: an unauthenticated cross-site POST
        # can force a logout. That is a nuisance, not a disclosure — nothing is
        # read or written — and SameSite=Lax already withholds the cookie on
        # cross-site POST.
        session_manager, session, error = resolve_session()

        # A dead or missing credential is not a reason to refuse: that is the
        # case this route exists to clean up. A *server* fault is different —
        # we genuinely cannot expire the session, so say so rather than
        # reporting a logout that did not happen.
        if session is None and error is not None and error[1] >= 500:
            return error

        if session is not None:
            session_manager.expire_session(session.session_id)

        return clear_session_cookie(
            make_response(
                jsonify({"success": True, "message": "Logged out successfully"}),
                200,
            )
        )

    except Exception:
        logger.exception("Unhandled error in logout")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@auth_bp.route("/auth/validate", methods=["GET"])
def validate_session():
    """Validate a session ID.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        On success (200):
            {
                "valid": true,
                "player_id": "str"
            }
        On failure (401):
            {
                "valid": false,
                "username": null,
                "player_id": null
            }
    """
    try:
        session_manager, session, error = resolve_session()
        if error:
            # Re-shape the shared helper's {success, error} response into this
            # route's own {valid, username, player_id} contract, preserving the
            # helper's status code (401 for missing/invalid auth or session).
            _, status = error
            return (
                jsonify({"valid": False, "username": None, "player_id": None}),
                status,
            )

        return (
            jsonify(
                {
                    "valid": True,
                    "player_id": session.player_id,
                }
            ),
            200,
        )

    except Exception:
        logger.exception("Unhandled error in validate_session")
        return (
            jsonify(
                {
                    "valid": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@auth_bp.route("/auth/settings", methods=["GET", "PUT"])
@require_auth
async def settings():
    """Get or update user settings.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "data": {
                "timezone": "str"
            }
        }
    """
    try:
        session = request.session_obj
        if not getattr(session, "db_user_id", None):
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        user_id = session.db_user_id

        if request.method == "GET":
            # Just read from session cache
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {
                            "timezone": session.data.get("timezone", "America/New_York")
                        },
                    }
                ),
                200,
            )

        elif request.method == "PUT":
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or "timezone" not in data:
                return jsonify({"success": False, "error": "Missing timezone"}), 400

            timezone = data["timezone"]

            # Validate against the IANA tz database before persisting — the
            # stored value later drives save-list time formatting.
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

            if not isinstance(timezone, str):
                return jsonify({"success": False, "error": "Invalid timezone"}), 400
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, ValueError):
                return jsonify({"success": False, "error": "Invalid timezone"}), 400

            success = await auth_service.update_user_timezone(user_id, timezone)

            if success:
                session.data["timezone"] = timezone
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "Settings updated successfully",
                            "data": {"timezone": timezone},
                        }
                    ),
                    200,
                )
            else:
                return (
                    jsonify({"success": False, "error": "Failed to update settings"}),
                    500,
                )

    except Exception:
        logger.exception("Unhandled error in settings")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
