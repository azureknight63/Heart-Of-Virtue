"""Reputation management routes for Phase 3 Stage 2."""

from flask import Blueprint, request, jsonify, current_app
from typing import Any, Optional, Tuple

reputation_bp = Blueprint("reputation", __name__, url_prefix="/api/reputation")


def get_session_and_player(
    req: Any,
) -> Tuple[Any, Any, Any, Optional[Any], Optional[int]]:
    """Extract and validate session from request header.

    Args:
        req: Flask request object

    Returns:
        Tuple of (session_manager, session, player, error_response, error_code)
    """
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return (
            None,
            None,
            None,
            jsonify(
                {
                    "success": False,
                    "error": "Missing or invalid authentication header",
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
            jsonify({"success": False, "error": "Player not found for session"}),
            404,
        )

    return session_manager, session, player, None, None


@reputation_bp.route("/player", methods=["GET"])
def get_player_reputation():
    """Get player's complete reputation state with all NPCs.

    Requires: Bearer token in Authorization header
    Returns: All reputation data
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    result = current_app.game_service.get_player_reputation(player)
    return jsonify({"success": True, "data": result["reputation"]}), 200


@reputation_bp.route("/npc/<npc_id>", methods=["GET"])
def get_npc_relationship(npc_id: str):
    """Get relationship with a specific NPC.

    Args:
        npc_id: NPC identifier

    Requires: Bearer token in Authorization header
    Returns: Relationship data including reputation, attitude, and flags
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    if not npc_id or not isinstance(npc_id, str):
        return (
            jsonify({"success": False, "error": "Invalid NPC ID"}),
            400,
        )

    result = current_app.game_service.get_npc_relationship(player, npc_id)

    return (
        jsonify({"success": True, "data": result}),
        200,
    )


@reputation_bp.route("/npc/<npc_id>", methods=["PUT"])
def update_npc_relationship(npc_id: str):
    """Update reputation with an NPC.

    Args:
        npc_id: NPC identifier

    Request body:
        {
            "amount": <int>,  # -100 to +100 reputation change
            "reason": <string>  # optional reason (quest_complete, dialogue_choice, etc.)
        }

    Requires: Bearer token in Authorization header
    Returns: Reputation change details
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    if not npc_id or not isinstance(npc_id, str):
        return (
            jsonify({"success": False, "error": "Invalid NPC ID"}),
            400,
        )

    data = request.get_json() or {}

    # Validate amount
    if "amount" not in data:
        return (
            jsonify({"success": False, "error": "Missing 'amount' in request"}),
            400,
        )

    amount = data.get("amount")
    if not isinstance(amount, (int, float)):
        return (
            jsonify({"success": False, "error": "'amount' must be a number"}),
            400,
        )

    amount = int(amount)
    if amount < -100 or amount > 100:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "'amount' must be between -100 and 100",
                }
            ),
            400,
        )

    reason = data.get("reason", "unknown")
    if not isinstance(reason, str):
        return (
            jsonify({"success": False, "error": "'reason' must be a string"}),
            400,
        )

    # Update reputation
    result = current_app.game_service.update_reputation(player, npc_id, amount, reason)

    # Save session
    session_manager.save_session(session.session_id)

    return (
        jsonify({"success": True, "data": result["reputation_change"]}),
        200,
    )


@reputation_bp.route("/npc/<npc_id>/flag/<flag_name>", methods=["POST"])
def set_relationship_flag(npc_id: str, flag_name: str):
    """Set a relationship flag for an NPC.

    Args:
        npc_id: NPC identifier
        flag_name: Flag name (romance, betrayed, alliance, etc.)

    Request body:
        {
            "value": <bool>  # true to set, false to unset
        }

    Requires: Bearer token in Authorization header
    Returns: Flag update result
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    if not npc_id or not isinstance(npc_id, str):
        return (
            jsonify({"success": False, "error": "Invalid NPC ID"}),
            400,
        )

    if not flag_name or not isinstance(flag_name, str):
        return (
            jsonify({"success": False, "error": "Invalid flag name"}),
            400,
        )

    data = request.get_json() or {}

    # Validate value
    if "value" not in data:
        return (
            jsonify({"success": False, "error": "Missing 'value' in request"}),
            400,
        )

    value = data.get("value")
    if not isinstance(value, bool):
        return (
            jsonify({"success": False, "error": "'value' must be a boolean"}),
            400,
        )

    # Set flag
    result = current_app.game_service.set_relationship_flag(
        player, npc_id, flag_name, value
    )

    # Save session
    session_manager.save_session(session.session_id)

    return (
        jsonify({"success": True, "data": result["flag_update"]}),
        200,
    )


@reputation_bp.route("/dialogue/<npc_id>/<dialogue_node>", methods=["GET"])
def check_dialogue_available(npc_id: str, dialogue_node: str):
    """Check if a dialogue node is available based on reputation.

    Args:
        npc_id: NPC identifier
        dialogue_node: Dialogue node identifier

    Requires: Bearer token in Authorization header
    Returns: Availability status and lock reason if applicable
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    if not npc_id or not isinstance(npc_id, str):
        return (
            jsonify({"success": False, "error": "Invalid NPC ID"}),
            400,
        )

    if not dialogue_node or not isinstance(dialogue_node, str):
        return (
            jsonify({"success": False, "error": "Invalid dialogue node"}),
            400,
        )

    result = current_app.game_service.check_dialogue_available(
        player, npc_id, dialogue_node
    )

    return jsonify({"success": True, "data": result}), 200


@reputation_bp.route("/quest/<npc_id>/<quest_type>", methods=["GET"])
def check_quest_available(npc_id: str, quest_type: str):
    """Check if a quest is available based on reputation.

    Args:
        npc_id: NPC identifier
        quest_type: Quest type identifier

    Requires: Bearer token in Authorization header
    Returns: Availability status and lock reason if applicable
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    if not npc_id or not isinstance(npc_id, str):
        return (
            jsonify({"success": False, "error": "Invalid NPC ID"}),
            400,
        )

    if not quest_type or not isinstance(quest_type, str):
        return (
            jsonify({"success": False, "error": "Invalid quest type"}),
            400,
        )

    result = current_app.game_service.check_quest_available(player, npc_id, quest_type)

    return jsonify({"success": True, "data": result}), 200
