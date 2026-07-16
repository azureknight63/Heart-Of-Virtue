"""
Flask routes for NPC chat interactions (LLM-driven conversation system).

Provides REST API endpoints for:
- Opening conversations with human NPCs
- Responding to NPC dialogue with tone selection
- Ending conversations and flushing state
- Retrieving conversation history
"""

from flask import Blueprint, request, jsonify, current_app
from src.api.middleware.auth import get_session_and_player

npc_chat_bp = Blueprint("npc_chat", __name__)

# Upper bound on any single free-text / identifier field accepted from the
# client. Both streams here are untrusted (player free-text and NPC keys), so
# a pathological multi-megabyte payload is truncated to this length rather than
# forwarded verbatim into the LLM prompt or NPC lookup. Chosen generously so
# no legitimate dialogue line is ever clipped.
_MAX_FIELD_LEN = 4000


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
