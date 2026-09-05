"""Authentication routes."""

import logging

from flask import Blueprint, current_app, jsonify, request
from src.api.middleware.auth import resolve_session
from src.api.rate_limiter import (
    RateLimiter,
    client_ip,
    limiter_from_env,
    rate_limited_response,
)
from src.api.services.auth_service import auth_service
from functools import wraps
import asyncio

auth_bp = Blueprint("auth", __name__)

logger = logging.getLogger(__name__)

# Simple in-memory login throttle: 10 failed attempts per username+IP per 15
# minutes. Per-worker (not shared across Gunicorn workers) — see GitHub issue
# #284 and `src.api.rate_limiter` for the bounded-store rationale, the
# `None`-tolerant `RateLimiter.check` and the shared 429 body, all of which
# feedback.py's submission throttle and npc_chat.py's chat throttles use
# too. Only failed (invalid-credential) attempts count, so retries after a
# typo or a flaky DB call don't lock out a legitimate player.
# The threshold is tunable via LOGIN_RATE_LIMIT_PER_15_MIN, but this throttle
# cannot be switched off: `allow_disable=False` makes a configured 0 warn and
# fall back to the default, exactly like a garbled value (see
# `limiter_from_env`). Both login limiters below are therefore never None.
_LOGIN_RATE_LIMIT = 10
_LOGIN_RATE_WINDOW = 900  # 15 minutes
_login_limiter = limiter_from_env(
    "LOGIN_RATE_LIMIT_PER_15_MIN",
    _LOGIN_RATE_LIMIT,
    _LOGIN_RATE_WINDOW,
    allow_disable=False,
)

# Second, independent throttle keyed on IP alone. The username+IP limiter above
# resets its budget every time the username changes, so a single IP can spray
# thousands of distinct usernames (credential stuffing) without ever tripping
# it. This IP-only limiter catches that horizontal attack. The threshold is set
# far above what a legitimate human — even several sharing one NAT'd IP — would
# fail in the window, so it's defense-in-depth against spray, not a per-account
# gate. Same per-worker caveat as above (issue #284): the effective limit is
# _IP_RATE_LIMIT * worker_count, so treat it as raising the cost of spray, not
# an airtight cap. Tunable via LOGIN_IP_RATE_LIMIT_PER_15_MIN and, like the
# tier above, not disableable by configuration. See
# `src.api.rate_limiter.client_ip` for how a client is keyed.
_IP_RATE_LIMIT = 60
_IP_RATE_WINDOW = 900  # 15 minutes
_ip_limiter = limiter_from_env(
    "LOGIN_IP_RATE_LIMIT_PER_15_MIN",
    _IP_RATE_LIMIT,
    _IP_RATE_WINDOW,
    allow_disable=False,
)


# Third tier, on the *other* credential-path endpoint. `/auth/register` had no
# throttle at all, which mattered twice over: account creation is unbounded
# work against the DB (bcrypt per attempt), and a fresh account is a fresh
# session — which is how feedback.py's per-session cap on real GitHub issue
# creation used to be walked past. Keyed on the source alone, since there is no
# account to key on yet. The ceiling is deliberately far above any human
# (nobody signs up thirty times an hour) and far below an account farm; unlike
# the two login tiers this one *is* disableable, because its absence is spam
# and cost rather than an open door to credential guessing.
_REGISTER_RATE_LIMIT = 30
_REGISTER_RATE_WINDOW = 3600  # 1 hour
_register_limiter = limiter_from_env(
    "REGISTER_RATE_LIMIT_PER_HOUR",
    _REGISTER_RATE_LIMIT,
    _REGISTER_RATE_WINDOW,
)


def _is_register_rate_limited() -> bool:
    """True if this source has spent its account-creation budget.

    Counts the call unless already limited. ``RateLimiter.check`` carries
    the ``None`` case — the documented ``REGISTER_RATE_LIMIT_PER_HOUR=0``
    disable — so it is not re-derived here.
    """
    return RateLimiter.check(_register_limiter, client_ip())


def _login_rate_limit_key(username: str) -> str:
    """Bucket a login attempt by account *and* source.

    Uses the same ``client_ip()`` collapsing as the IP-only tier: keying this
    half on the raw ``remote_addr`` would let an IPv6 attacker mint a fresh
    username+IP budget per address in their /64, which is precisely what the
    collapsing exists to prevent.
    """
    return f"{(username or '').strip().lower()}:{client_ip()}"


# Neither limiter is ever None (`allow_disable=False` above), so the helpers
# below dereference them directly. A None guard here would be dead code that
# reads as though switching a login throttle off were a supported state.


def _is_login_rate_limited(key: str) -> bool:
    """True if either the username+IP or the IP-only throttle is tripped."""
    return _login_limiter.is_limited(key) or _ip_limiter.is_limited(client_ip())


def _record_failed_login(key: str) -> None:
    _login_limiter.record(key)
    _ip_limiter.record(client_ip())


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

        # Throttled after shape validation and before create_user: a malformed
        # payload costs nothing and should not spend anyone's budget, while a
        # well-formed one is about to hash a password and write a row.
        if _is_register_rate_limited():
            return rate_limited_response(
                "Too many registration attempts. Please try again later."
            )

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

        session_manager = current_app.session_manager

        # Create session and link it to the DB user record.
        session_id, player_id = _establish_session_for_user(
            session_manager, username, user
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "session_id": session_id,
                        "message": "Account created successfully. Welcome!",
                    },
                }
            ),
            201,
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
            return rate_limited_response(
                "Too many failed login attempts. Please try again later."
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

        session_manager = current_app.session_manager

        # Create session and link it to the DB user record.
        session_id, player_id = _establish_session_for_user(
            session_manager, username, user
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "session_id": session_id,
                        "message": "Welcome back!",
                    },
                }
            ),
            200,
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
@require_auth
def logout():
    """End a player session.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "message": "str"
        }
    """
    try:
        session_id = request.session_obj.session_id
        session_manager = request.session_manager

        # Expire session
        success = session_manager.expire_session(session_id)

        if success:
            return (
                jsonify({"success": True, "message": "Logged out successfully"}),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Session not found or already expired",
                    }
                ),
                404,
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
