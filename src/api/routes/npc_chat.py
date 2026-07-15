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
from src.api.services.validators import validate_string_field, ensure_dict

npc_chat_bp = Blueprint("npc_chat", __name__)


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
        data = ensure_dict(request.get_json(silent=True))
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    is_valid, err = validate_string_field(data.get("npc_id", ""), "npc_id")
    if not is_valid:
        return jsonify({"success": False, "error": err}), 400
    npc_id = data["npc_id"].strip()

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
        data = ensure_dict(request.get_json(silent=True))
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    is_valid, err = validate_string_field(data.get("npc_key", ""), "npc_key")
    if not is_valid:
        return jsonify({"success": False, "error": err}), 400
    is_valid, err = validate_string_field(data.get("jean_text", ""), "jean_text")
    if not is_valid:
        return jsonify({"success": False, "error": err}), 400

    npc_key = data["npc_key"].strip()
    jean_text = data["jean_text"].strip()
    # jean_tone is optional; ignore a non-string value and fall back to default.
    raw_tone = data.get("jean_tone", "direct")
    jean_tone = raw_tone.strip() if isinstance(raw_tone, str) and raw_tone.strip() else "direct"

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
        data = ensure_dict(request.get_json(silent=True))
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    is_valid, err = validate_string_field(data.get("npc_key", ""), "npc_key")
    if not is_valid:
        return jsonify({"success": False, "error": err}), 400
    npc_key = data["npc_key"].strip()

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

    npc_key = npc_key.strip()
    if not npc_key:
        return jsonify({"success": False, "error": "npc_key is required"}), 400

    # Call game service
    result = current_app.game_service.npc_chat_history(player, npc_key)

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code
