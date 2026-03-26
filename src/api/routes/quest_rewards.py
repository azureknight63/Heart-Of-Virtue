"""
Flask routes for quest rewards (Phase 3: Advanced Features).

Provides REST API endpoints for:
- Getting quest rewards
- Completing quests and receiving rewards
- Tracking progression
"""

from flask import Blueprint, request, jsonify, current_app, abort
from src.api.services.validators import (
    validate_required_fields,
)

quest_rewards_bp = Blueprint(
    "quest_rewards", __name__, url_prefix="/api/quests"
)


def get_session_and_player():
    """Extract and validate session from Authorization header.

    Returns:
        Tuple of (session_manager, session, player, error_response, status_code)
        or (None, None, None, error_response, status_code) on error
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return (
            None,
            None,
            None,
            jsonify(
                {
                    "success": False,
                    "error": "Missing or invalid Authorization header",
                }
            ),
            401,
        )

    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)

    if not session:
        return (
            None,
            None,
            None,
            jsonify({"success": False, "error": "Invalid or expired session"}),
            401,
        )

    player = session_manager.get_player(session_id)
    if not player:
        return (
            None,
            None,
            None,
            jsonify({"success": False, "error": "Player not found"}),
            404,
        )

    return session_manager, session, player, None, None


@quest_rewards_bp.route("/<quest_id>/rewards", methods=["GET"])
def get_quest_rewards(quest_id: str):
    """Get rewards for a specific quest.

    Args:
        quest_id: Quest identifier from URL

    Returns:
        JSON with quest reward details
    """
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Get rewards using GameService
    result = current_app.game_service.get_quest_rewards(player, quest_id)

    if not result.get("success"):
        return jsonify(result), 404

    return jsonify(result), 200


@quest_rewards_bp.route("/<quest_id>/complete", methods=["POST"])
def complete_quest(quest_id: str):
    """Complete a quest and distribute rewards.

    Args:
        quest_id: Quest identifier from URL

    Request body:
    {
        "difficulty": "normal|easy|hard|nightmare" (optional, defaults to "normal"),
        "no_deaths": boolean (optional, defaults to True),
        "bonus_objectives_completed": boolean (optional, defaults to False)
    }

    Returns:
        JSON with quest completion details and rewards
    """
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Parse request body
    data = request.get_json() or {}

    # Validate request fields
    difficulty = data.get("difficulty", "normal")
    if difficulty not in ["easy", "normal", "hard", "nightmare"]:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Invalid difficulty. Must be: easy, normal, hard, or nightmare",
                }
            ),
            400,
        )

    no_deaths = data.get("no_deaths", True)
    bonus_objectives_completed = data.get("bonus_objectives_completed", False)

    # Complete quest using GameService
    result = current_app.game_service.complete_quest(
        player,
        quest_id,
        difficulty=difficulty,
        no_deaths=no_deaths,
        bonus_objectives_completed=bonus_objectives_completed,
    )

    if not result.get("success"):
        return jsonify(result), 400

    # Save session after modifications
    session_manager.save_session(session.session_id)

    return jsonify(result), 200


@quest_rewards_bp.route("/award-gold", methods=["POST"])
def award_gold():
    """Award gold to player (for testing/admin).

    Request body:
    {
        "amount": int (required)
    }

    Returns:
        JSON with gold update info
    """
    if not current_app.debug:
        abort(404)
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Validate request
    is_valid, error_msg = validate_required_fields(
        request.get_json() or {}, ["amount"]
    )
    if not is_valid:
        return jsonify({"success": False, "error": error_msg}), 400

    amount = request.json["amount"]
    if not isinstance(amount, int) or amount <= 0:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Amount must be a positive integer",
                }
            ),
            400,
        )

    # Award gold
    result = current_app.game_service.award_gold(player, amount)

    # Save session
    session_manager.save_session(session.session_id)

    return jsonify(result), 200


@quest_rewards_bp.route("/award-experience", methods=["POST"])
def award_experience():
    """Award experience to player (for testing/admin).

    Request body:
    {
        "amount": int (required)
    }

    Returns:
        JSON with experience update info
    """
    if not current_app.debug:
        abort(404)
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Validate request
    is_valid, error_msg = validate_required_fields(
        request.get_json() or {}, ["amount"]
    )
    if not is_valid:
        return jsonify({"success": False, "error": error_msg}), 400

    amount = request.json["amount"]
    if not isinstance(amount, int) or amount <= 0:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Amount must be a positive integer",
                }
            ),
            400,
        )

    # Award experience
    result = current_app.game_service.award_experience(player, amount)

    # Save session
    session_manager.save_session(session.session_id)

    return jsonify(result), 200


@quest_rewards_bp.route("/award-item", methods=["POST"])
def award_item():
    """Award item to player inventory (for testing/admin).

    Request body:
    {
        "item_id": str (required),
        "item_name": str (required),
        "quantity": int (optional, defaults to 1)
    }

    Returns:
        JSON with item award info
    """
    if not current_app.debug:
        abort(404)
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Validate request
    is_valid, error_msg = validate_required_fields(
        request.get_json() or {}, ["item_id", "item_name"]
    )
    if not is_valid:
        return jsonify({"success": False, "error": error_msg}), 400

    item_id = request.json["item_id"]
    item_name = request.json["item_name"]
    quantity = request.json.get("quantity", 1)

    if not isinstance(quantity, int) or quantity <= 0:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Quantity must be a positive integer",
                }
            ),
            400,
        )

    # Award item
    result = current_app.game_service.award_item(
        player, item_id, item_name, quantity
    )

    if not result.get("success"):
        return jsonify(result), 400

    # Save session
    session_manager.save_session(session.session_id)

    return jsonify(result), 200


@quest_rewards_bp.route("/award-reputation", methods=["POST"])
def award_reputation():
    """Award reputation with an NPC.

    Request body:
    {
        "npc_id": str (required),
        "npc_name": str (required),
        "amount": int (required, can be negative for loss)
    }

    Returns:
        JSON with reputation update info
    """
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    # Validate request
    is_valid, error_msg = validate_required_fields(
        request.get_json() or {}, ["npc_id", "npc_name", "amount"]
    )
    if not is_valid:
        return jsonify({"success": False, "error": error_msg}), 400

    npc_id = request.json["npc_id"]
    npc_name = request.json["npc_name"]
    amount = request.json["amount"]

    if not isinstance(amount, int):
        return (
            jsonify({"success": False, "error": "Amount must be an integer"}),
            400,
        )

    # Award reputation
    result = current_app.game_service.award_reputation(
        player, npc_id, npc_name, amount
    )

    # Save session
    session_manager.save_session(session.session_id)

    return jsonify(result), 200


@quest_rewards_bp.route("/progression", methods=["GET"])
def get_progression():
    """Get player progression stats.

    Returns:
        JSON with progression data
    """
    session_manager, session, player, error, status = get_session_and_player()
    if error:
        return error, status

    result = current_app.game_service.get_player_progression(player)

    return jsonify(result), 200
