"""Combat system routes."""

from flask import Blueprint, request, jsonify

combat_bp = Blueprint("combat", __name__, url_prefix="/combat")


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


@combat_bp.route("/start", methods=["POST"])
def start_combat():
    """Initiate combat with an enemy.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "enemy_id": str
        }

    Returns:
        {
            "success": bool,
            "combat_id": str,
            "combatants": [...],
            "turn_order": [...],
            "current_turn": int
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        data = request.get_json()
        if not data or "enemy_id" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing enemy_id",
                    }
                ),
                400,
            )

        enemy_id = data["enemy_id"]

        from flask import current_app

        game_service = current_app.game_service

        result = game_service.start_combat(player, enemy_id)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        session_manager.save_session(session.session_id)

        return jsonify({"success": True, **result}), 201

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


@combat_bp.route("/move", methods=["POST"])
def execute_move():
    """Execute a combat move.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "move_type": "attack|defend|cast|item",
            "move_id": str,
            "target_id": str (optional)
        }

    Returns:
        {
            "success": bool,
            "result": str,
            "damage": int (optional),
            "effects": [...] (optional)
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        data = request.get_json()
        if not data or "move_type" not in data or "move_id" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing move_type or move_id",
                    }
                ),
                400,
            )

        move_type = data["move_type"]
        move_id = data["move_id"]
        target_id = data.get("target_id")

        from flask import current_app

        game_service = current_app.game_service

        result = game_service.execute_move(player, move_type, move_id, target_id)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        session_manager.save_session(session.session_id)

        return jsonify({"success": True, **result}), 200

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


@combat_bp.route("/status", methods=["GET"])
def get_combat_status():
    """Get current combat status.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "combat_active": bool,
            "combatants": [...],
            "current_turn": int,
            "log": [...]
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        from flask import current_app

        game_service = current_app.game_service

        status = game_service.get_combat_status(player)

        return jsonify({"success": True, **status}), 200

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
