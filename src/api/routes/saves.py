"""Save and load game routes."""

from flask import Blueprint, request, jsonify

saves_bp = Blueprint("saves", __name__)


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


@saves_bp.route("/saves", methods=["GET"])
async def list_saves():
    """List all saved games for player from Turso cloud storage."""
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error[0], error[1]

        if not hasattr(session, "db_user_id") or not session.db_user_id:
            return jsonify({"success": True, "saves": []}), 200

        from flask import current_app
        game_service = current_app.game_service

        saves = await game_service.list_saves(session.db_user_id)

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


@saves_bp.route("/saves", methods=["POST"])
async def create_save():
    """Create a new manual or auto save in Turso cloud."""
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error[0], error[1]

        if not hasattr(session, "db_user_id") or not session.db_user_id:
            return jsonify({"success": False, "error": "Cloud saves require a registered account."}), 403

        data = request.get_json()
        if not data or ("name" not in data and "is_autosave" not in data):
            return jsonify({"success": False, "error": "Missing save name or type"}), 400

        save_name = data.get("name", "Manual Save")
        is_autosave = data.get("is_autosave", False)

        from flask import current_app
        game_service = current_app.game_service

        try:
            save_id = await game_service.save_game(player, save_name, session.db_user_id, is_autosave=is_autosave)
        except ValueError as ve:
            # Handle the 20 manual save limit
            return jsonify({"success": False, "error": str(ve)}), 403

        from datetime import datetime

        return (
            jsonify(
                {
                    "success": True,
                    "save_id": save_id,
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Game saved: {save_name}" if not is_autosave else "Game autosaved",
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


@saves_bp.route("/saves/<save_id>/load", methods=["POST"])
async def load_save(save_id):
    """Load a saved game from Turso cloud."""
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error[0], error[1]

        if not hasattr(session, "db_user_id") or not session.db_user_id:
            return jsonify({"success": False, "error": "Cloud saves require a registered account."}), 403

        from flask import current_app
        game_service = current_app.game_service

        loaded_player = await game_service.load_game(save_id, session.db_user_id)

        if not loaded_player:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Save not found or access denied",
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


@saves_bp.route("/saves/<save_id>", methods=["DELETE"])
async def delete_save(save_id):
    """Delete a saved game from Turso cloud."""
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error[0], error[1]

        if not hasattr(session, "db_user_id") or not session.db_user_id:
            return jsonify({"success": False, "error": "Cloud saves require a registered account."}), 403

        from flask import current_app
        game_service = current_app.game_service

        success = await game_service.delete_save(save_id, session.db_user_id)

        if success:
            return jsonify({"success": True, "message": "Save deleted successfully"}), 200
        else:
            return jsonify({"success": False, "error": "Save not found or access denied"}), 404

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
@saves_bp.route("/game/new", methods=["POST"])
def new_game():
    """Start a new game for the current session.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error[0], error[1]

        success = session_manager.start_new_game(session.session_id)

        if success:
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "New game started successfully",
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to start new game",
                    }
                ),
                400,
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
