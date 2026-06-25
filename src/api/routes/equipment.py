"""Equipment management routes."""

from flask import Blueprint, request, jsonify
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


@equipment_bp.route("/equipment/equip", methods=["POST"])
def equip_item():
    """Equip an item.

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
            "stat_changes": {...}
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error[0], error[1]

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

        result = game_service.equip_item(player, item_id)

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


@equipment_bp.route("/equipment/unequip", methods=["POST"])
def unequip_item():
    """Unequip an item from a slot.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "slot": "head|body|hands|feet|back|neck"
        }

    Returns:
        {
            "success": bool,
            "slot": str,
            "stat_changes": {...}
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error[0], error[1]

        data = request.get_json()
        if not data or "slot" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing slot",
                    }
                ),
                400,
            )

        slot = data["slot"]

        from flask import current_app

        game_service = current_app.game_service

        result = game_service.unequip_item(player, slot)

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
