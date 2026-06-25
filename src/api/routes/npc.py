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
from src.api.middleware.auth import get_session_and_player

npc_bp = Blueprint("npc", __name__, url_prefix="/api/npc")


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
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

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
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

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
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

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
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    # Get profile
    result = current_app.game_service.get_npc_behavior_profile(player, npc_id)

    # Save session
    session_manager.save_session(session.session_id)

    return jsonify({"success": result.get("success"), "data": result}), (
        200 if result.get("success") else 404
    )


@npc_bp.route("/quests/active", methods=["GET"])
def get_active_quests():
    """Get list of active quests.

    Returns:
        JSON response with active quests
    """
    # Get session and player
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    # Get active quests
    result = current_app.game_service.get_active_quests(player)

    # Save session
    session_manager.save_session(session.session_id)

    return jsonify({"success": result.get("success"), "data": result}), 200


@npc_bp.route("/quests/<quest_id>/accept", methods=["POST"])
def accept_quest(quest_id):
    """Accept (start) a quest.

    Args:
        quest_id: Quest identifier (from URL)

    Returns:
        JSON response with quest details
    """
    # Validate quest_id
    if not quest_id or len(quest_id) == 0:
        return jsonify({"success": False, "error": "Invalid quest_id"}), 400

    # Get session and player
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    # Start quest
    result = current_app.game_service.start_quest(player, quest_id)

    # Save session (quest state changed)
    session_manager.save_session(session.session_id)

    status_code = 200 if result.get("success") else 404
    return (
        jsonify({"success": result.get("success"), "data": result}),
        status_code,
    )


@npc_bp.route("/quests/<quest_id>/progress", methods=["POST"])
def update_quest_progress(quest_id):
    """Update progress on a quest objective.

    Args:
        quest_id: Quest identifier (from URL)

    Request body:
        {
            "objective_id": "obj_1"  // Objective to complete
        }

    Returns:
        JSON response with updated quest progress
    """
    # Validate input
    if not quest_id or len(quest_id) == 0:
        return jsonify({"success": False, "error": "Invalid quest_id"}), 400

    is_valid, error = validate_required_fields(
        request.get_json() or {}, ["objective_id"]
    )
    if not is_valid:
        return jsonify({"success": False, "error": error}), 400

    # Get session and player
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    objective_id = request.json["objective_id"]

    # Update quest progress
    result = current_app.game_service.update_quest_progress(
        player, quest_id, objective_id
    )

    # Save session (quest progress changed)
    session_manager.save_session(session.session_id)

    status_code = 200 if result.get("success") else 404
    return (
        jsonify({"success": result.get("success"), "data": result}),
        status_code,
    )


@npc_bp.route("/quests/<quest_id>/status", methods=["GET"])
def get_quest_status(quest_id):
    """Get status of a specific quest.

    Args:
        quest_id: Quest identifier (from URL)

    Returns:
        JSON response with quest status
    """
    # Validate input
    if not quest_id or len(quest_id) == 0:
        return jsonify({"success": False, "error": "Invalid quest_id"}), 400

    # Get session and player
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    # Get quest status
    result = current_app.game_service.get_quest_status(player, quest_id)

    # Save session
    session_manager.save_session(session.session_id)

    status_code = 200 if result.get("success") else 404
    return (
        jsonify({"success": result.get("success"), "data": result}),
        status_code,
    )
