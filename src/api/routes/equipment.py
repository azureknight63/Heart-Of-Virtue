"""Equipment management routes."""

from flask import Blueprint, request, jsonify

equipment_bp = Blueprint("equipment", __name__)


def get_session_and_player(request):
    """Extract session and player from request."""
    from flask import current_app

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return (
            None,
            None,
            None,
            (jsonify({"error": "Missing authorization"}), 401),
        )

    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)

    if not session:
        return (
            None,
            None,
            None,
            (jsonify({"error": "Invalid or expired session"}), 401),
        )

    player = session_manager.get_player(session_id)
    if not player:
        return None, None, None, (jsonify({"error": "Player not found"}), 404)

    return session_manager, session, player, None


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
        session_manager, session, player, error = get_session_and_player(request)
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
