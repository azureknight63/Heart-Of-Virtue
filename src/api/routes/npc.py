"""
Flask routes for NPC interactions (dialogue, quests, state).

Provides REST API endpoints for:
- Getting NPC state and behavior
- Interacting with NPC dialogue systems
- Managing quest interactions
"""

from flask import Blueprint, request, jsonify, current_app
from src.api.services.validators import (
    validate_required_fields,
    validate_npc_id,
)

npc_bp = Blueprint("npc", __name__, url_prefix="/api/npc")


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


@npc_bp.route("/<npc_id>/state", methods=["GET"])
def get_npc_state(npc_id):
    """Get current state of an NPC.

    Args:
        npc_id: NPC identifier (from URL)

    Returns:
        JSON response with NPC state
    """
    # Validate input
    is_valid, error = validate_npc_id(npc_id)
    if not is_valid:
        return jsonify({"success": False, "error": error}), 400

    # Get session and player
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Get NPC state
    result = current_app.game_service.get_npc_state(player, npc_id)

    # Save session after read operation (defensive)
    session_manager.save_session(session.session_id)

    return jsonify({"success": result.get("success"), "data": result}), (
        200 if result.get("success") else 404
    )


@npc_bp.route("/<npc_id>/dialogue", methods=["GET"])
def get_npc_dialogue(npc_id):
    """Get dialogue options from an NPC.

    Args:
        npc_id: NPC identifier (from URL)

    Returns:
        JSON response with dialogue state
    """
    # Validate input
    is_valid, error = validate_npc_id(npc_id)
    if not is_valid:
        return jsonify({"success": False, "error": error}), 400

    # Get session and player
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Get dialogue
    result = current_app.game_service.get_npc_dialogue(player, npc_id)

    # Save session
    session_manager.save_session(session.session_id)

    return jsonify({"success": result.get("success"), "data": result}), (
        200 if result.get("success") else 404
    )


@npc_bp.route("/<npc_id>/dialogue", methods=["POST"])
def select_dialogue_option(npc_id):
    """Select a dialogue option from an NPC.

    Args:
        npc_id: NPC identifier (from URL)

    Request body:
        {
            "option_id": 0  // Index of selected dialogue option
        }

    Returns:
        JSON response with next dialogue state
    """
    # Validate input
    is_valid, error = validate_npc_id(npc_id)
    if not is_valid:
        return jsonify({"success": False, "error": error}), 400

    is_valid, error = validate_required_fields(request.get_json() or {}, ["option_id"])
    if not is_valid:
        return jsonify({"success": False, "error": error}), 400

    # Get session and player
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Validate option_id is an integer
    try:
        option_id = int(request.json["option_id"])
        if option_id < 0:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "option_id must be non-negative",
                    }
                ),
                400,
            )
    except (ValueError, TypeError):
        return (
            jsonify({"success": False, "error": "option_id must be an integer"}),
            400,
        )

    # Select dialogue option
    result = current_app.game_service.select_dialogue_option(player, npc_id, option_id)

    # Save session
    session_manager.save_session(session.session_id)

    return jsonify({"success": result.get("success"), "data": result}), (
        200 if result.get("success") else 404
    )


@npc_bp.route("/<npc_id>/profile", methods=["GET"])
def get_npc_profile(npc_id):
    """Get NPC behavior profile.

    Args:
        npc_id: NPC identifier (from URL)

    Returns:
        JSON response with NPC behavior profile
    """
    # Validate input
    is_valid, error = validate_npc_id(npc_id)
    if not is_valid:
        return jsonify({"success": False, "error": error}), 400

    # Get session and player
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Get profile
    result = current_app.game_service.get_npc_behavior_profile(player, npc_id)

    # Save session
    session_manager.save_session(session.session_id)

    return jsonify({"success": result.get("success"), "data": result}), (
        200 if result.get("success") else 404
    )
