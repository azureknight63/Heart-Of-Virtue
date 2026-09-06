"""Authentication routes."""

import logging

from flask import Blueprint, current_app, jsonify, make_response, request
from src.api.middleware.auth import resolve_session
from src.api.session_cookie import (
    clear_session_cookie,
    session_id_from_cookie,
    set_session_cookie,
)
from src.api.rate_limiter import (
    RateLimiter,
    client_ip,
    limiter_from_env,
    rate_limited_response,
)
from src.api.services.auth_service import (
    RegistrationValidationError,
    auth_service,
)
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


# Third login tier, and the one that counts EVERY attempt rather than every
# failure.
#
# Both tiers above are spent by `_record_failed_login`, which runs only under
# `if not user`. So a caller holding ONE valid credential never touches either
# budget, and can replay that login without limit -- each request costing a
# full Argon2id verify at the configured memory cost, on a synchronous worker.
# The two failure tiers are the right shape for credential guessing and the
# wrong shape for this: guessing is bounded by wrong answers, and this attack
# never gives one.
#
# Keyed on the source alone, because the account is not the thing being abused
# -- the hasher is. Set far above any human login rate (a shared NAT'd office
# does not log in 120 times in fifteen minutes) so it is a cost ceiling rather
# than a per-account gate, and NOT disableable, for the same reason as its two
# siblings: its absence is an unauthenticated way to spend the server's memory
# budget.
_LOGIN_ATTEMPT_RATE_LIMIT = 120
_LOGIN_ATTEMPT_RATE_WINDOW = 900  # 15 minutes
_login_attempt_limiter = limiter_from_env(
    "LOGIN_ATTEMPT_RATE_LIMIT_PER_15_MIN",
    _LOGIN_ATTEMPT_RATE_LIMIT,
    _LOGIN_ATTEMPT_RATE_WINDOW,
    allow_disable=False,
)


def _is_login_attempt_rate_limited() -> bool:
    """True if this source has spent its total login-attempt budget.

    ``RateLimiter.check`` counts the call unless already limited, which is what
    makes this tier count successes too -- the distinction from
    :func:`_is_login_rate_limited`, which only ever sees what
    ``_record_failed_login`` has spent.
    """
    return RateLimiter.check(_login_attempt_limiter, client_ip())


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


# Substrings that suggest an internal config/infrastructure fault. This is a
# HEURISTIC, and it is no longer what stands between an exception message and
# the client.
#
# It used to be: `register` echoed any ValueError whose text matched none of
# these five markers, so `could not connect to
# postgres://svc:<password>@db.internal:5432/hov` -- which matches none of them
# -- went back to an anonymous caller verbatim. A deny-list over free-form
# exception text cannot be complete, and a test built from the same five
# markers cannot notice that it is not. `register` now allow-lists
# `RegistrationValidationError` instead, and every other failure is masked.
#
# What remains is a status-code hint on the login path, where BOTH branches
# return a generic message and the only thing this chooses is 503 ("infra
# trouble, retry") versus 500 ("we broke"). A false negative there costs a
# status code, not a disclosure.
_CONFIG_LEAK_MARKERS = ("_URL", "_KEY", "_TOKEN", "not set", "os.environ")


def _is_config_leak(msg: str) -> bool:
    """True if ``msg`` contains one of :data:`_CONFIG_LEAK_MARKERS`.

    Named for the question it is asked, not for a property it can decide: a
    message with no marker in it may still be pure infrastructure. Only ever
    used to pick between two responses that are both generic.
    """
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
    # Spent before the body is parsed and outside the try below, the way
    # logs.py and feedback.py spend theirs. It used to sit after the shape
    # validation, on the argument that "a malformed payload costs nothing and
    # should not spend anyone's budget". The first half of that is not true —
    # this route is unauthenticated, so parsing up to MAX_CONTENT_LENGTH of
    # attacker-chosen JSON was the one piece of work no throttle gated — and
    # the second half bought nothing: an attacker who wants to exhaust a
    # shared NAT's register budget sends *well-formed* payloads, which are
    # cheaper for them and always counted. Outside the try so the 429 cannot
    # be relabelled a 500 by the catch-all at the bottom.
    if _is_register_rate_limited():
        return rate_limited_response(
            "Too many registration attempts. Please try again later."
        )

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
        except RegistrationValidationError as ve:
            # The ONLY exception whose text is echoed, and it is echoed because
            # of its type rather than because its wording passed a filter.
            # `AuthService` raises it for the five input bounds a caller can
            # act on; nothing else in the stack raises it.
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": str(ve),
                    }
                ),
                400,
            )
        except ValueError:
            # Everything else is infrastructure until proven otherwise. This
            # used to be the other way round -- echo unless the message
            # contained one of five markers -- and a ValueError reading
            # `could not connect to postgres://svc:<password>@db.internal:5432`
            # matched none of them and went back to an anonymous caller with
            # the credential in it. Logged, not returned: the operator needs
            # the text and the client does not.
            logger.exception("Registration failed with a non-validation error")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "service_unavailable",
                        "message": (
                            "Registration is temporarily unavailable. "
                            "Please try again later."
                        ),
                    }
                ),
                503,
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

        # The one throttle in this API that cannot be hoisted above the parse,
        # and it is not an oversight. This is a *failed-attempt* counter, not a
        # request counter: `_record_failed_login` runs only on a bad password,
        # and half the key is the username, which does not exist until the body
        # is parsed. Moved up, it would check a budget nothing has spent and
        # key it on nothing. It is inside the try for the same reason. What it
        # therefore does not gate — the parse of an unauthenticated body — is
        # gated instead by `MAX_CONTENT_LENGTH` and the `before_request` hook
        # in `src/api/app.py::_register_request_limits`, which bound the parse
        # for every route rather than for the throttled ones.
        rate_key = _login_rate_limit_key(username)
        if _is_login_rate_limited(rate_key):
            return rate_limited_response(
                "Too many failed login attempts. Please try again later."
            )

        # Spent on EVERY attempt, and checked before `authenticate_user` so the
        # Argon2 verify is what it bounds. The two tiers above are failure
        # counters and a valid credential never touches them.
        if _is_login_attempt_rate_limited():
            return rate_limited_response(
                "Too many login attempts. Please try again later."
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
