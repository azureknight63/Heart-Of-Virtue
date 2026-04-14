"""
Flask routes for NPC chat interactions (LLM-driven conversation system).

Provides REST API endpoints for:
- Opening conversations with human NPCs
- Responding to NPC dialogue with tone selection
- Ending conversations and flushing state
- Retrieving conversation history
"""

from flask import Blueprint, request, jsonify, current_app

npc_chat_bp = Blueprint("npc_chat", __name__)


def get_session_and_player():
    """Extract and validate session from Authorization header.

    Returns:
        Tuple of (session_manager, session, player, error_response, status_code)
        or (None, None, None, error_response, status_code) on error
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return (
            None,
            None,
            None,
            jsonify(
                {
                    "success": False,
                    "error": "Missing or invalid Authorization header",
                }
            ),
            401,
        )

    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)

    if not session:
        return (
            None,
            None,
            None,
            jsonify({"success": False, "error": "Invalid or expired session"}),
            401,
        )

    player = session_manager.get_player(session_id)
    if not player:
        return (
            None,
            None,
            None,
            jsonify({"success": False, "error": "Player not found"}),
            404,
        )

    return session_manager, session, player, None, None


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
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Get request body
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    npc_id = data.get("npc_id", "").strip()
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
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Get request body
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    npc_key = data.get("npc_key", "").strip()
    jean_text = data.get("jean_text", "").strip()
    jean_tone = data.get("jean_tone", "direct").strip()

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
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Get request body
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    npc_key = data.get("npc_key", "").strip()
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
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    npc_key = npc_key.strip()
    if not npc_key:
        return jsonify({"success": False, "error": "npc_key is required"}), 400

    # Call game service
    result = current_app.game_service.npc_chat_history(player, npc_key)

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code
