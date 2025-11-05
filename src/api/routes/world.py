"""World navigation routes."""

from flask import Blueprint, request, jsonify

world_bp = Blueprint("world", __name__, url_prefix="/world")


def get_session_and_player(request):
    """Extract session and player from request.

    Returns:
        Tuple of (session_manager, session, player) or error response
    """
    from flask import current_app

    # Extract session ID from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, jsonify({"error": "Missing authorization"}), 401

    session_id = auth_header[7:]
    session_manager = current_app.session_manager

    # Get session and player
    session = session_manager.get_session(session_id)
    if not session:
        return None, None, jsonify({"error": "Invalid or expired session"}), 401

    player = session_manager.get_player(session_id)
    if not player:
        return None, None, jsonify({"error": "Player not found"}), 404

    return session_manager, session, player, None


@world_bp.route("/", methods=["GET"])
def get_current_room():
    """Get current room data.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "room": {
                "x": int,
                "y": int,
                "name": str,
                "description": str,
                "exits": [str],
                "items": [...],
                "npcs": [...]
            }
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        game_service = None
        from flask import current_app

        game_service = current_app.game_service

        if not game_service or not game_service.universe:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Game service not initialized",
                    }
                ),
                500,
            )

        room = game_service.get_current_room(player)

        return jsonify({"success": True, "room": room}), 200

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


@world_bp.route("/move", methods=["POST"])
def move_player():
    """Move player in a direction.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "direction": "north|south|east|west"
        }

    Returns:
        {
            "success": bool,
            "new_position": {"x": int, "y": int},
            "room": {...},
            "events_triggered": [...]
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        data = request.get_json()
        if not data or "direction" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing direction",
                    }
                ),
                400,
            )

        direction = data["direction"].lower()

        from flask import current_app

        game_service = current_app.game_service

        if not game_service or not game_service.universe:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Game service not initialized",
                    }
                ),
                500,
            )

        result = game_service.move_player(player, direction)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        # Save session after movement
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


@world_bp.route("/tile", methods=["GET"])
def get_tile():
    """Get tile data at specific coordinates.

    Headers:
        Authorization: Bearer <session_id>

    Query parameters:
        x: int (tile x coordinate)
        y: int (tile y coordinate)

    Returns:
        {
            "success": bool,
            "tile": {
                "x": int,
                "y": int,
                "name": str,
                "description": str,
                "items": [...],
                "npcs": [...]
            }
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        # Get query parameters
        x_str = request.args.get("x")
        y_str = request.args.get("y")

        if not x_str or not y_str:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing x or y coordinate",
                    }
                ),
                400,
            )

        try:
            x = int(x_str)
            y = int(y_str)
        except ValueError:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Coordinates must be integers",
                    }
                ),
                400,
            )

        from flask import current_app

        game_service = current_app.game_service

        if not game_service or not game_service.universe:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Game service not initialized",
                    }
                ),
                500,
            )

        tile = game_service.get_tile(x, y)

        if "error" in tile:
            return jsonify({"success": False, "error": tile["error"]}), 404

        return jsonify({"success": True, "tile": tile}), 200

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
