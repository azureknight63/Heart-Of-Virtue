"""Equipment management routes."""

from flask import Blueprint, jsonify
from src.api.middleware.auth import get_session_and_player

equipment_bp = Blueprint("equipment", __name__)


@equipment_bp.route("/equipment", methods=["GET"])
def get_equipment():
    """Get player equipment status.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "equipment": {
                "head": item or null,
                "body": item or null,
                "hands": item or null,
                "feet": item or null,
                "back": item or null,
                "neck": item or null
            }
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error[0], error[1]

        from flask import current_app

        game_service = current_app.game_service

        if not game_service:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Game service not initialized",
                    }
                ),
                500,
            )

        equipment = game_service.get_equipment(player)

        return jsonify({"success": True, "equipment": equipment}), 200

    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )
