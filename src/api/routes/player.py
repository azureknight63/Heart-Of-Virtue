"""Player status and stats routes."""

from flask import Blueprint, request, jsonify

player_bp = Blueprint("player", __name__)


def get_session_and_player(request):
    """Extract session and player from request."""
    from flask import current_app

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, None, (jsonify({"error": "Missing authorization"}), 401)

    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)

    if not session:
        return None, None, None, (jsonify({"error": "Invalid or expired session"}), 401)

    player = session_manager.get_player(session_id)
    if not player:
        return None, None, None, (jsonify({"error": "Player not found"}), 404)

    return session_manager, session, player, None


@player_bp.route("/status", methods=["GET"])
def get_status():
    """Get player status (name, level, HP, etc.).

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "status": {
                "name": str,
                "level": int,
                "exp": int,
                "hp": int,
                "max_hp": int,
                "state": str
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

        status = game_service.get_player_status(player)

        return jsonify({"success": True, "status": status}), 200

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


@player_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get player stats (strength, dexterity, etc.).

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "stats": {
                "strength": int,
                "dexterity": int,
                "vitality": int,
                "intelligence": int,
                "wisdom": int,
                "speed": int
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

        stats = game_service.get_player_stats(player)

        return jsonify({"success": True, "stats": stats}), 200

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
