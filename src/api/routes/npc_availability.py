"""
NPC Availability Routes for Stage 4: Story-Gated NPC Location Tracking

Endpoints:
- GET /api/npcs/<npc_id>/status - Get NPC availability status
- GET /api/locations/<location_id>/npcs - Get NPCs at a location
- POST /api/npcs/<npc_id>/check-availability - Check if NPC is available
- POST /api/npcs/<npc_id>/location - Update NPC location
- GET /api/npcs/<npc_id>/timeline - Get NPC location progression
"""

from flask import Blueprint, request, current_app, jsonify
from src.api.middleware.auth import get_session_and_player

npc_availability_bp = Blueprint("npc_availability", __name__, url_prefix="/api")


@npc_availability_bp.route("/npcs/<npc_id>/status", methods=["GET"])
def get_npc_status(npc_id):
    """
    Get current status and availability of an NPC.

    Returns NPC name, availability status, current location, and availability reasons.
    """
    session_manager, session, player, error = get_session_and_player()
    if error:
        response, status_code = error
        return response, status_code

    try:
        result = current_app.game_service.get_npc_status(player, npc_id)
        return jsonify(result), 200
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to get NPC status: {str(e)}",
                }
            ),
            500,
        )


@npc_availability_bp.route("/locations/<location_id>/npcs", methods=["GET"])
def get_npcs_at_location(location_id):
    """
    Get all NPCs currently at a specific location.

    Returns list of NPCs and their availability status.
    """
    session_manager, session, player, error = get_session_and_player()
    if error:
        response, status_code = error
        return response, status_code

    try:
        result = current_app.game_service.get_npcs_at_location(player, location_id)
        return jsonify(result), 200
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to get NPCs at location: {str(e)}",
                }
            ),
            500,
        )


@npc_availability_bp.route("/npcs/<npc_id>/check-availability", methods=["POST"])
def check_npc_availability(npc_id):
    """
    Check if an NPC is available for interaction.

    Returns availability status, reason if unavailable, and location.
    """
    session_manager, session, player, error = get_session_and_player()
    if error:
        response, status_code = error
        return response, status_code

    try:
        data = request.get_json() or {}
        reason = data.get("reason")

        result = current_app.game_service.check_npc_availability(player, npc_id, reason)
        return jsonify(result), 200
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to check NPC availability: {str(e)}",
                }
            ),
            500,
        )


@npc_availability_bp.route("/npcs/<npc_id>/location", methods=["POST"])
def update_npc_location(npc_id):
    """
    Update an NPC's location (for story progression events).

    Request body:
    {
        "new_location_id": "location_id"
    }
    """
    session_manager, session, player, error = get_session_and_player()
    if error:
        response, status_code = error
        return response, status_code

    try:
        data = request.get_json() or {}
        new_location_id = data.get("new_location_id")

        if not new_location_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing required field: new_location_id",
                    }
                ),
                400,
            )

        result = current_app.game_service.update_npc_location(
            player, npc_id, new_location_id
        )
        session_manager.save_session(session.session_id)
        return jsonify(result), 200
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to update NPC location: {str(e)}",
                }
            ),
            500,
        )


@npc_availability_bp.route("/npcs/<npc_id>/timeline", methods=["GET"])
def get_npc_timeline(npc_id):
    """
    Get the location progression timeline for an NPC.

    Shows where NPCs appear and when, based on story progression.
    """
    session_manager, session, player, error = get_session_and_player()
    if error:
        response, status_code = error
        return response, status_code

    try:
        result = current_app.game_service.get_npc_timeline(player, npc_id)
        return jsonify(result), 200
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to get NPC timeline: {str(e)}",
                }
            ),
            500,
        )
