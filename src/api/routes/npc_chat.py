"""
Flask routes for NPC chat interactions (LLM-driven conversation system).

Provides REST API endpoints for:
- Opening conversations with human NPCs
- Responding to NPC dialogue with tone selection
- Ending conversations and flushing state
- Retrieving conversation history
"""

import logging
import os

from flask import Blueprint, request, jsonify, current_app
from src.api.middleware.auth import get_session_and_player
from src.api.rate_limiter import RateLimiter

# Module-level: the rate limit is read at import, before an app context (and
# therefore current_app.logger) exists.
logger = logging.getLogger(__name__)

npc_chat_bp = Blueprint("npc_chat", __name__)

# Upper bound on any single free-text / identifier field accepted from the
# client. Both streams here are untrusted (player free-text and NPC keys), so
# a pathological multi-megabyte payload is truncated to this length rather than
# forwarded verbatim into the LLM prompt or NPC lookup. Chosen generously so
# no legitimate dialogue line is ever clipped.
_MAX_FIELD_LEN = 4000

# Rate limit for the LLM-backed endpoints (open/respond). Each call can drive
# up to ~3 provider calls through the fallback chain (see ai/llm_client.py),
# so an unthrottled client can burn the operator's shared free-tier LLM quota
# fast. 20/minute per session is well above anything a human clicking through
# dialogue options can produce, but trivially exceeded by a script.
# Configurable via NPC_CHAT_RATE_LIMIT_PER_MINUTE; 0 disables the limiter
# entirely. Per-worker (not shared across Gunicorn workers) — see GitHub issue
# #284 and `src.api.rate_limiter` for the bounded-store rationale, shared with
# auth.py's login throttle and feedback.py's submission throttle.
_RATE_LIMIT_DEFAULT_PER_MINUTE = 20


def _rate_limit_from_env():
    """Read the limit, surviving a malformed value.

    This runs at blueprint import, so a bare ``int()`` turned a typo in an env
    file (``NPC_CHAT_RATE_LIMIT_PER_MINUTE=twenty``) into a ValueError during
    import and took the whole API down at boot. Falling back to the default
    keeps the limiter *on*, which is the safe direction to fail: a garbled
    value must never be read as "unlimited".
    """
    raw = os.environ.get("NPC_CHAT_RATE_LIMIT_PER_MINUTE", "")
    if not raw.strip():
        return _RATE_LIMIT_DEFAULT_PER_MINUTE
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "NPC_CHAT_RATE_LIMIT_PER_MINUTE=%r is not an integer; "
            "falling back to %d/minute.",
            raw,
            _RATE_LIMIT_DEFAULT_PER_MINUTE,
        )
        return _RATE_LIMIT_DEFAULT_PER_MINUTE


_RATE_LIMIT_PER_MINUTE = _rate_limit_from_env()
_RATE_WINDOW_SECONDS = 60
_chat_limiter = (
    RateLimiter(limit=_RATE_LIMIT_PER_MINUTE, window_seconds=_RATE_WINDOW_SECONDS)
    if _RATE_LIMIT_PER_MINUTE > 0
    else None
)


def _chat_rate_limit_key(session):
    """Key the chat rate limiter on the session id.

    Falls back to the request's remote address if a session with no
    ``session_id`` somehow reaches here (defensive — ``get_session_and_player``
    always resolves a real session before this is called).
    """
    session_id = getattr(session, "session_id", None)
    if session_id:
        return str(session_id)
    try:
        return request.remote_addr or "unknown"
    except RuntimeError:  # working outside of request context
        return "unknown"


def _check_chat_rate_limit(session):
    """Return a ``(response, 429)`` tuple if `session` is over the LLM chat
    rate limit, else ``None``. A no-op when the limiter is disabled
    (``NPC_CHAT_RATE_LIMIT_PER_MINUTE=0``).
    """
    if _chat_limiter is None:
        return None
    key = _chat_rate_limit_key(session)
    if _chat_limiter.check_and_record(key):
        return (
            jsonify({"success": False, "error": "Slow down — too many messages."}),
            429,
        )
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
    result = current_app.game_service.npc_chat_open(player, npc_id)

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
    result = current_app.game_service.npc_chat_respond(
        player, npc_key, jean_text, jean_tone
    )

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
    result = current_app.game_service.npc_chat_end(player, npc_key)

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
    result = current_app.game_service.npc_chat_history(player, npc_key)

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code
