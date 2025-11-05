"""Save and load game routes."""

from flask import Blueprint, request, jsonify

saves_bp = Blueprint("saves", __name__, url_prefix="/saves")


def get_session_and_player(request):
    """Extract session and player from request."""
    from flask import current_app

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, jsonify({"error": "Missing authorization"}), 401

    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)

    if not session:
        return None, None, jsonify({"error": "Invalid or expired session"}), 401

    player = session_manager.get_player(session_id)
    if not player:
        return None, None, jsonify({"error": "Player not found"}), 404

    return session_manager, session, player, None


@saves_bp.route("/", methods=["GET"])
def list_saves():
    """List all saved games for player.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "saves": [
                {
                    "id": str,
                    "name": str,
                    "timestamp": ISO 8601,
                    "location": str,
                    "level": int
                }
            ]
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        from flask import current_app

        game_service = current_app.game_service

        saves = game_service.list_saves()

        return jsonify({"success": True, "saves": saves}), 200

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


@saves_bp.route("/", methods=["POST"])
def create_save():
    """Create a new save.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "name": str
        }

    Returns:
        {
            "success": bool,
            "save_id": str,
            "timestamp": ISO 8601,
            "message": str
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        data = request.get_json()
        if not data or "name" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing save name",
                    }
                ),
                400,
            )

        save_name = data["name"]

        from flask import current_app

        game_service = current_app.game_service

        save_id = game_service.save_game(player, save_name)

        from datetime import datetime

        return (
            jsonify(
                {
                    "success": True,
                    "save_id": save_id,
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Game saved: {save_name}",
                }
            ),
            201,
        )

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


@saves_bp.route("/<save_id>/load", methods=["POST"])
def load_save(save_id):
    """Load a saved game.

    Headers:
        Authorization: Bearer <session_id>

    Path parameters:
        save_id: str (save identifier)

    Returns:
        {
            "success": bool,
            "message": str,
            "player": {...}
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        from flask import current_app

        game_service = current_app.game_service

        loaded_player = game_service.load_game(save_id)

        if not loaded_player:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Save not found",
                    }
                ),
                404,
            )

        # Update session with loaded player
        session_manager.set_player(session.session_id, loaded_player)
        session_manager.save_session(session.session_id)

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Game loaded successfully",
                }
            ),
            200,
        )

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


@saves_bp.route("/<save_id>", methods=["DELETE"])
def delete_save(save_id):
    """Delete a saved game.

    Headers:
        Authorization: Bearer <session_id>

    Path parameters:
        save_id: str (save identifier)

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        from flask import current_app

        game_service = current_app.game_service

        success = game_service.delete_save(save_id)

        if success:
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Save deleted successfully",
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Save not found",
                    }
                ),
                404,
            )

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
