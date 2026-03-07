"""Quest chain routes for Phase 3 Stage 3."""

from flask import Blueprint, request, jsonify, current_app
from typing import Any, Optional, Tuple

quest_chains_bp = Blueprint("quest_chains", __name__, url_prefix="/api/quest-chains")


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


@quest_chains_bp.route("/progress", methods=["GET"])
def get_all_chains_progress():
    """Get player's progress in all quest chains.

    Requires: Bearer token in Authorization header
    Returns: Progress data for all chains
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    result = current_app.game_service.get_all_chains_progress(player)

    return jsonify({"success": True, "data": result["all_chains"]}), 200


@quest_chains_bp.route("/<chain_id>/progress", methods=["GET"])
def get_chain_progress(chain_id: str):
    """Get player's progress in a specific chain.

    Args:
        chain_id: Chain identifier

    Requires: Bearer token in Authorization header
    Returns: Progress data for the chain
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    if not chain_id or not isinstance(chain_id, str):
        return (
            jsonify({"success": False, "error": "Invalid chain ID"}),
            400,
        )

    result = current_app.game_service.get_chain_progress(player, chain_id)

    return jsonify({"success": True, "data": result["progress"]}), 200


@quest_chains_bp.route("/<chain_id>/advance", methods=["POST"])
def advance_chain_stage(chain_id: str):
    """Advance player to next stage in a chain.

    Args:
        chain_id: Chain identifier

    Request body:
        {
            "current_stage": <int>,
            "next_stage": <int>
        }

    Requires: Bearer token in Authorization header
    Returns: Updated chain progression
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    if not chain_id or not isinstance(chain_id, str):
        return (
            jsonify({"success": False, "error": "Invalid chain ID"}),
            400,
        )

    data = request.get_json() or {}

    # Validate current_stage
    if "current_stage" not in data:
        return (
            jsonify({"success": False, "error": "Missing 'current_stage'"}),
            400,
        )

    current_stage = data.get("current_stage")
    if not isinstance(current_stage, int) or current_stage < 0:
        return (
            jsonify({"success": False, "error": "'current_stage' must be non-negative integer"}),
            400,
        )

    # Validate next_stage
    if "next_stage" not in data:
        return (
            jsonify({"success": False, "error": "Missing 'next_stage'"}),
            400,
        )

    next_stage = data.get("next_stage")
    if not isinstance(next_stage, int) or next_stage < 0:
        return (
            jsonify({"success": False, "error": "'next_stage' must be non-negative integer"}),
            400,
        )

    # Advance chain
    result = current_app.game_service.advance_chain_stage(
        player, chain_id, current_stage, next_stage
    )

    # Save session
    session_manager.save_session(session.session_id)

    return (
        jsonify({"success": True, "data": result["advancement"]}),
        200,
    )


@quest_chains_bp.route("/<chain_id>/complete", methods=["POST"])
def complete_chain(chain_id: str):
    """Mark a chain as completed.

    Args:
        chain_id: Chain identifier

    Requires: Bearer token in Authorization header
    Returns: Completion result
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    if not chain_id or not isinstance(chain_id, str):
        return (
            jsonify({"success": False, "error": "Invalid chain ID"}),
            400,
        )

    result = current_app.game_service.complete_chain(player, chain_id)

    # Save session
    session_manager.save_session(session.session_id)

    return (
        jsonify({"success": True, "data": result["completion"]}),
        200,
    )


@quest_chains_bp.route("/<chain_id>/prerequisites", methods=["POST"])
def check_prerequisites(chain_id: str):
    """Check if chain prerequisites are met.

    Args:
        chain_id: Chain identifier

    Request body:
        {
            "prerequisites": [<chain_id>, ...]
        }

    Requires: Bearer token in Authorization header
    Returns: Prerequisite validation result
    """
    session_manager, session, player, error, status_code = get_session_and_player(
        request
    )
    if error:
        return error, status_code

    if not chain_id or not isinstance(chain_id, str):
        return (
            jsonify({"success": False, "error": "Invalid chain ID"}),
            400,
        )

    data = request.get_json() or {}

    # Validate prerequisites
    if "prerequisites" not in data:
        prerequisites = []
    else:
        prerequisites = data.get("prerequisites", [])
        if not isinstance(prerequisites, list):
            return (
                jsonify({"success": False, "error": "'prerequisites' must be a list"}),
                400,
            )

    result = current_app.game_service.check_chain_prerequisites(
        player, chain_id, prerequisites
    )

    return jsonify({"success": True, "data": result}), 200
