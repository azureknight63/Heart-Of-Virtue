"""Player status and stats routes."""

import logging

from flask import Blueprint, request, jsonify
from src.api.serializers.inventory import InventorySerializer
from src.api.middleware.auth import get_session_and_player
from src.api.services.validators import ensure_dict

player_bp = Blueprint("player", __name__)
_log = logging.getLogger(__name__)


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

        status = game_service.get_player_status(player)

        return jsonify({"success": True, "status": status}), 200

    except Exception:
        _log.exception("Unhandled error in get_status")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@player_bp.route("/full-state", methods=["GET"])
def get_full_state():
    """Get full player combined state (status, inventory, stats, skills).

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "status": {...},
            "inventory": {...},
            "stats": {...},
            "skills": {...}
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
                jsonify({"success": False, "error": "Game service not initialized"}),
                500,
            )

        # Collect all data in one pass
        status = game_service.get_player_status(player)
        inventory = InventorySerializer.serialize(player)
        from src.api.serializers.inventory import EquipmentSerializer

        equipment = EquipmentSerializer.serialize(player)
        stats = game_service.get_player_stats(player)
        skills = game_service.get_player_skills(player)

        return (
            jsonify(
                {
                    "success": True,
                    "status": status,
                    "inventory": inventory,
                    "equipment": equipment,
                    "stats": stats,
                    "skills": skills,
                }
            ),
            200,
        )

    except Exception:
        _log.exception("Unhandled error in get_full_state")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


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

        stats = game_service.get_player_stats(player)

        return jsonify({"success": True, "stats": stats}), 200

    except Exception:
        _log.exception("Unhandled error in get_stats")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@player_bp.route("/skills", methods=["GET"])
def get_skills():
    """Get player skills and experience.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "skills": {
                "known_moves": [...],
                "skill_exp": {...},
                "skill_tree": {...}
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

        skills = game_service.get_player_skills(player)

        return jsonify({"success": True, "skills": skills}), 200

    except Exception:
        _log.exception("Unhandled error in get_skills")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@player_bp.route("/skills/learn", methods=["POST"])
def learn_skill():
    """Learn a skill.

    Headers:
        Authorization: Bearer <session_id>

    Body:
        {
            "skill_name": str,
            "category": str
        }

    Returns:
        {
            "success": bool,
            "message": str,
            "remaining_exp": int,
            "skills": {...}
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

        data = request.get_json(silent=True)
        if not data or "skill_name" not in data or "category" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing skill_name or category",
                    }
                ),
                400,
            )

        result = game_service.learn_skill(player, data["skill_name"], data["category"])

        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception:
        _log.exception("Unhandled error in learn_skill")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@player_bp.route("/level-up/allocate", methods=["POST"])
def allocate_level_up_points():
    """Allocate pending attribute points (API mode).

    Headers:
        Authorization: Bearer <session_id>

    Body:
        {
            "attribute": "strength_base|finesse_base|speed_base|endurance_base|charisma_base|intelligence_base",
            "amount": int
        }

    Returns:
        {
            "success": bool,
            "remaining_points": int,
            "stats": {...}
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error[0], error[1]

        data = ensure_dict(request.get_json(silent=True))
        attribute = data.get("attribute")
        amount = data.get("amount")

        from flask import current_app

        result = current_app.game_service.allocate_level_up_points(
            player, attribute, amount
        )

        if not result.get("success"):
            return jsonify(result), 400

        session_manager.save_session(session.session_id)

        return jsonify(result), 200

    except Exception:
        _log.exception("Unhandled error in allocate_level_up_points")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )
