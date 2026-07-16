"""Combat system routes."""

import logging
from flask import Blueprint, request, jsonify

from src.api.middleware.auth import get_session_and_player
from src.api.services.validators import ensure_dict

logger = logging.getLogger(__name__)

combat_bp = Blueprint("combat", __name__)


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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        data = ensure_dict(request.get_json(silent=True))
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

        result = game_service.start_combat(
            player, enemy_id, session_id=session.session_id
        )

        if "error" in result:
            # Game-logic errors (already in combat, etc.) — return 200 with success=false
            # to match execute_move semantics. 4xx is reserved for structural/auth errors.
            return jsonify({"success": False, "error": result["error"]}), 200

        session_manager.save_session(session.session_id)

        return jsonify({"success": True, **result}), 201

    except Exception:
        logger.exception("Unhandled error in start_combat")
        return (
            jsonify({"success": False, "error": "An internal error occurred"}),
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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        data = ensure_dict(request.get_json(silent=True))
        if not data or "move_type" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing move_type",
                    }
                ),
                400,
            )

        move_type = data["move_type"]
        move_id = data.get("move_id", data.get("move_name", ""))
        target_id = data.get("target_id")
        direction = data.get("direction")

        from flask import current_app

        game_service = current_app.game_service

        result = game_service.execute_move(
            player,
            move_type,
            move_id,
            target_id,
            direction,
            session_id=session.session_id,
            session_data=session.data,
        )

        if "error" in result:
            # Game-logic errors (move not available, wrong state, etc.) are not bad
            # requests — return 200 with success=false so callers can distinguish
            # structural errors (4xx) from in-game conditions (200 success=false).
            # Do NOT save session on error paths — avoid persisting partial mutations.
            return jsonify({"success": False, "error": result["error"]}), 200

        session_manager.save_session(session.session_id)
        return jsonify({"success": True, **result}), 200

    except Exception:
        logger.exception("Unhandled error in execute_move")
        return (
            jsonify({"success": False, "error": "An internal error occurred"}),
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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        from flask import current_app

        game_service = current_app.game_service

        status = game_service.get_combat_status(
            player, session_id=session.session_id, session_data=session.data
        )

        return jsonify({"success": True, **status}), 200

    except Exception:
        logger.exception("Unhandled error in get_combat_status")
        return (
            jsonify({"success": False, "error": "An internal error occurred"}),
            500,
        )


@combat_bp.route("/suggestions/pause", methods=["POST"])
def toggle_suggestions_pause():
    """Pause or resume Tactical Advisor suggestion generation for this session."""
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        from flask import current_app

        data = ensure_dict(request.get_json(silent=True))
        paused = bool(data.get("paused", False))
        current_app.game_service.set_suggestions_paused(player, paused)
        return jsonify({"success": True, "paused": paused}), 200

    except Exception:
        logger.exception("Unhandled error in toggle_suggestions_pause")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@combat_bp.route("/collect-loot", methods=["POST"])
def collect_loot():
    """Move selected post-combat drops from the tile into the player's inventory.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "item_names": ["Iron Sword", "Health Potion", ...]
        }

    Returns:
        {
            "success": bool,
            "collected": [...],
            "skipped": [...]
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        data = ensure_dict(request.get_json(silent=True))
        item_names = data.get("item_names", [])
        if not isinstance(item_names, list):
            return (
                jsonify({"success": False, "error": "item_names must be a list"}),
                400,
            )

        from flask import current_app

        game_service = current_app.game_service
        result = game_service.collect_combat_loot(player, item_names)
        return jsonify(result), 200

    except Exception:
        logger.exception("Unhandled error in collect_loot")
        return (
            jsonify({"success": False, "error": "An internal error occurred"}),
            500,
        )
