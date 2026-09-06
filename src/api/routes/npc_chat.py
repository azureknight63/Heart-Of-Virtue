"""
Flask routes for NPC chat interactions (LLM-driven conversation system).

Provides REST API endpoints for:
- Opening conversations with human NPCs
- Responding to NPC dialogue with tone selection
- Ending conversations and flushing state
- Retrieving conversation history
"""

from flask import Blueprint, request, jsonify
from src.api.middleware.auth import get_session_and_player, require_game_service
from src.api.rate_limiter import (
    RateLimiter,
    client_ip,
    limiter_from_env,
    rate_limited_response,
)

npc_chat_bp = Blueprint("npc_chat", __name__)

# Upper bound on any single free-text / identifier field accepted from the
# client. Both streams here are untrusted (player free-text and NPC keys), so
# a pathological multi-megabyte payload is truncated to this length rather than
# forwarded verbatim into the LLM prompt or NPC lookup. Chosen generously so
# no legitimate dialogue line is ever clipped.
_MAX_FIELD_LEN = 4000

# Rate limit for the LLM-backed endpoints (open/respond). One call composes
# several provider stages — up to two QC attempts, a state-guard revision, and
# (on a legacy adapter) a separate Jean-options call — and each stage walks the
# whole provider fallback chain, so the worst case is closer to a dozen provider
# calls than to a handful. `_CHAT_DEADLINE_SECONDS` in src/npc/_chat_llm.py
# bounds how many provider *stages* one call may open (a stage starts only
# while a full round timeout still fits, so the real ceiling is that budget
# plus one chain walk); this bounds how many calls a client may start. Both
# matter: the operator's free-tier LLM quota is account-wide and a script can
# drain it in seconds.
#
# 10/minute per player is well above anything a human clicking through dialogue
# options can produce (each round trip takes seconds), and trivially exceeded
# by a script. Configurable via NPC_CHAT_RATE_LIMIT_PER_MINUTE; 0 disables this
# tier. Per-worker (not shared across Gunicorn workers) — see GitHub issue #284
# and `src.api.rate_limiter` for the bounded-store rationale, the
# `None`-tolerant `RateLimiter.check` and the shared 429 body, all of which
# auth.py's login throttles and feedback.py's submission throttle use too.
_RATE_LIMIT_DEFAULT_PER_MINUTE = 10

# Second, independent throttle keyed on IP alone, mirroring auth.py's two-tier
# pattern. The identity-keyed limiter above is only as strong as the identity:
# an attacker who can log in repeatedly gets a fresh budget per account. This
# one caps a single source regardless. Set well above what several players
# behind one NAT would produce, so it is defense-in-depth against spray rather
# than a per-player gate. Same per-worker caveat as above.
_IP_RATE_LIMIT_DEFAULT_PER_MINUTE = 40

_RATE_WINDOW_SECONDS = 60

# Both tiers are built at blueprint *import* time by the shared factory, which
# carries the boot-outage rationale for never letting a garbled env value read
# as "unlimited". Each tier is disabled independently by setting its own var to
# 0; a disabled tier simply never trips.
_chat_limiter = limiter_from_env(
    "NPC_CHAT_RATE_LIMIT_PER_MINUTE",
    _RATE_LIMIT_DEFAULT_PER_MINUTE,
    _RATE_WINDOW_SECONDS,
)
_chat_ip_limiter = limiter_from_env(
    "NPC_CHAT_IP_RATE_LIMIT_PER_MINUTE",
    _IP_RATE_LIMIT_DEFAULT_PER_MINUTE,
    _RATE_WINDOW_SECONDS,
)


def _chat_rate_limit_key(session) -> str:
    """Key the chat rate limiter on a *stable*, unambiguous identity.

    This used to key on ``session.session_id``, which is a fresh uuid4 minted
    on every login (``session_manager.create_session``), while the login
    throttle records only *failed* attempts. So the budget could be reset at
    will: log in, spend the quota, log in again, indefinitely. The database
    user id survives re-login; username is the fallback for a session that
    predates it, and the session id (then the client IP) only for a session
    with no identity at all.

    Each source is prefixed because the four of them are otherwise one flat key
    space: a user free to choose a ``username`` equal to another principal's
    ``db_user_id`` (or to a session uuid, or to an IP literal) shares that
    principal's bucket, which is a denial of service against them and a
    doubled budget for whoever collides deliberately. The prefix makes the
    namespaces disjoint, which is what "stable identity" was supposed to mean.
    """
    for prefix, value in (
        ("uid", getattr(session, "db_user_id", None)),
        ("user", getattr(session, "username", None)),
        ("sid", getattr(session, "session_id", None)),
    ):
        if value:
            return "{}:{}".format(prefix, value)
    return "ip:{}".format(client_ip())


def _check_chat_rate_limit(session):
    """Return a ``(response, 429)`` tuple if this call is over the LLM chat
    rate limit, else ``None``.

    Either tier trips it, and a disabled tier simply never limits --
    ``RateLimiter.check`` owns that rule, so neither tier repeats it here.
    Set both ``NPC_CHAT_RATE_LIMIT_PER_MINUTE`` and
    ``NPC_CHAT_IP_RATE_LIMIT_PER_MINUTE`` to 0 to turn npc-chat throttling
    off entirely.

    The identity tier goes through ``check_and_record``, which is one locked
    operation. Checking both tiers and only then recording either left a window
    in which N concurrent requests all read "not limited" before any of them
    wrote, so a burst could spend N times the budget — on the endpoint whose
    whole purpose is protecting an account-wide LLM quota from exactly that.
    The IP tier still records separately: two limiters cannot be updated
    atomically *together*, so the choice is which one gets the atomic path, and
    it is the one keyed on the identity an attacker cannot rotate for free.
    Its bucket is therefore charged even when the identity tier already
    rejected — a caller being throttled has still cost this worker a request.
    """
    limited = RateLimiter.check(_chat_limiter, _chat_rate_limit_key(session))
    # Not `or`-short-circuited: `RateLimiter.check` records, and a
    # short-circuit would leave the IP tier uncounted whenever the identity
    # tier tripped -- see the paragraph above on charging both buckets.
    limited = RateLimiter.check(_chat_ip_limiter, client_ip()) or limited
    if limited:
        return rate_limited_response("Slow down — too many messages.")
    return None


def _string_field(data, key, default=""):
    """Safely extract a stripped string field from an untrusted JSON body.

    ``request.get_json()`` can yield any JSON type for a given key, so calling
    ``.strip()`` on the raw value 500s when the client sends a number, list,
    object, or bool. This coerces defensively:

    - a missing key yields ``default``;
    - a non-string value is treated as *missing* (returns ``default``) rather
      than crashing — an invalid type is not a valid identifier or message;
    - an oversized string is truncated to :data:`_MAX_FIELD_LEN`.

    The result is whitespace-stripped so downstream "required" checks still
    reject empty/whitespace input with a 400.
    """
    # A JSON body can parse to a non-object (string/number/list); guard so
    # ``.get`` is only called on a dict, otherwise treat the field as missing.
    value = data.get(key, default) if isinstance(data, dict) else default
    if not isinstance(value, str):
        value = default
    return value[:_MAX_FIELD_LEN].strip()


@npc_chat_bp.route("/open", methods=["POST"])
def npc_chat_open():
    """Start an LLM conversation with a human NPC.

    Request body:
        {
            "npc_id": "NPC identifier or name"
        }

    Returns:
        JSON response with conversation state
    """
    # Get session and player
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    limited = _check_chat_rate_limit(session)
    if limited:
        return limited

    # Get request body
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    npc_id = _string_field(data, "npc_id")
    if not npc_id:
        return jsonify({"success": False, "error": "npc_id is required"}), 400

    # Call game service
    game_service, gs_error = require_game_service()
    if gs_error:
        return gs_error

    result = game_service.npc_chat_open(player, npc_id)

    # Save session
    session_manager.save_session(session.session_id)

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@npc_chat_bp.route("/respond", methods=["POST"])
def npc_chat_respond():
    """Process Jean's dialogue choice and get NPC response.

    Request body:
        {
            "npc_key": "NPC identifier for active chat",
            "jean_text": "Jean's dialogue text",
            "jean_tone": "direct" | "guarded" | "open" (optional, default "direct")
        }

    Returns:
        JSON response with NPC reply and options
    """
    # Get session and player
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    limited = _check_chat_rate_limit(session)
    if limited:
        return limited

    # Get request body
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    npc_key = _string_field(data, "npc_key")
    jean_text = _string_field(data, "jean_text")
    jean_tone = _string_field(data, "jean_tone", "direct") or "direct"

    if not npc_key:
        return jsonify({"success": False, "error": "npc_key is required"}), 400
    if not jean_text:
        return jsonify({"success": False, "error": "jean_text is required"}), 400

    # Call game service
    game_service, gs_error = require_game_service()
    if gs_error:
        return gs_error

    result = game_service.npc_chat_respond(player, npc_key, jean_text, jean_tone)

    # Save session
    session_manager.save_session(session.session_id)

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@npc_chat_bp.route("/end", methods=["POST"])
def npc_chat_end():
    """End an NPC conversation and flush state.

    Request body:
        {
            "npc_key": "NPC identifier for active chat"
        }

    Returns:
        JSON response with conversation summary
    """
    # Get session and player
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    # Get request body
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    npc_key = _string_field(data, "npc_key")
    if not npc_key:
        return jsonify({"success": False, "error": "npc_key is required"}), 400

    # Call game service
    game_service, gs_error = require_game_service()
    if gs_error:
        return gs_error

    result = game_service.npc_chat_end(player, npc_key)

    # Save session
    session_manager.save_session(session.session_id)

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@npc_chat_bp.route("/history/<npc_key>", methods=["GET"])
def npc_chat_history(npc_key):
    """Get stored conversation history for an NPC.

    URL parameters:
        npc_key: NPC identifier to retrieve history for

    Returns:
        JSON response with conversation exchanges and metadata
    """
    # Get session and player
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    # npc_key arrives as a URL path segment (always a str); still bound its
    # length so a pathological identifier can't be forwarded verbatim.
    npc_key = (npc_key or "")[:_MAX_FIELD_LEN].strip()
    if not npc_key:
        return jsonify({"success": False, "error": "npc_key is required"}), 400

    # Call game service
    game_service, gs_error = require_game_service()
    if gs_error:
        return gs_error

    result = game_service.npc_chat_history(player, npc_key)

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code
