"""Inventory and item management routes."""

from flask import Blueprint, request, jsonify

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


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


@inventory_bp.route("/", methods=["GET"])
def get_inventory():
    """Get player inventory.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "inventory": {
                "items": [...],
                "count": int,
                "weight": float,
                "max_weight": float
            }
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

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

        inventory = game_service.get_inventory(player)

        return jsonify({"success": True, "inventory": inventory}), 200

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


@inventory_bp.route("/take", methods=["POST"])
def take_item():
    """Take an item from ground.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "item_id": str
        }

    Returns:
        {
            "success": bool,
            "item_id": str,
            "message": str
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        data = request.get_json()
        if not data or "item_id" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing item_id",
                    }
                ),
                400,
            )

        item_id = data["item_id"]

        from flask import current_app

        game_service = current_app.game_service

        result = game_service.take_item(player, item_id)

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


@inventory_bp.route("/drop", methods=["POST"])
def drop_item():
    """Drop an item from inventory.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "item_id": str
        }

    Returns:
        {
            "success": bool,
            "item_id": str,
            "message": str
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error

        data = request.get_json()
        if not data or "item_id" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing item_id",
                    }
                ),
                400,
            )

        item_id = data["item_id"]

        from flask import current_app

        game_service = current_app.game_service

        result = game_service.drop_item(player, item_id)

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
