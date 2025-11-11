"""
Dialogue Context REST API Routes

Provides HTTP endpoints for:
- Starting dialogues with NPCs
- Retrieving dialogue nodes
- Processing player choices
- Viewing conversation history
- Listing available dialogues

All endpoints require Bearer token authentication.

Routes:
- POST /api/dialogue/start
- GET /api/dialogue/node/<node_id>
- POST /api/dialogue/select
- GET /api/npc/<npc_id>/dialogue/history
- GET /api/npc/<npc_id>/dialogue/available
"""

from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import logging

# Blueprint definition
dialogue_context_bp = Blueprint("dialogue_context", __name__, url_prefix="/api")

logger = logging.getLogger(__name__)


def get_session_and_player(request_obj):
    """Extract and validate session from Bearer token.
    
    Returns:
        (session_manager, session, player, error_tuple) where error_tuple is None on success
        or (error_response, status_code) on failure
    """
    auth_header = request_obj.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, None, (
            jsonify({"success": False, "error": "Missing authentication"}),
            401
        )
    
    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)
    
    if not session:
        return None, None, None, (
            jsonify({"success": False, "error": "Invalid session"}),
            401
        )
    
    player = session_manager.get_player(session_id)
    if not player:
        return None, None, None, (
            jsonify({"success": False, "error": "Player not found"}),
            404
        )
    
    return session_manager, session, player, None


# ========================
# Dialogue Context Endpoints
# ========================

@dialogue_context_bp.route("/dialogue/start", methods=["POST"])
def start_dialogue():
    """Start a new dialogue with an NPC.
    
    Request Body:
        {
            "npc_id": "merchant_kael",
            "dialogue_id": "greeting_001"
        }
    
    Response:
        {
            "success": true,
            "data": {
                "conversation_id": "uuid",
                "current_node": { node data },
                "available_choices": [ choices ],
                "conversation_history": { history },
                "is_complete": false
            }
        }
    
    Status Codes:
        200: Dialogue started successfully
        400: Missing required fields
        401: Invalid/missing authentication
        404: NPC or dialogue not found
        500: Server error
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            response, status_code = error
            return response, status_code
        
        # Validate request body
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Request must be JSON"
            }), 400
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = {"npc_id", "dialogue_id"}
        missing = required_fields - set(data.keys())
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400
        
        npc_id = data.get("npc_id", "").strip()
        dialogue_id = data.get("dialogue_id", "").strip()
        
        if not npc_id or not dialogue_id:
            return jsonify({
                "success": False,
                "error": "npc_id and dialogue_id cannot be empty"
            }), 400
        
        # Call GameService
        game_service = current_app.game_service
        result = game_service.start_dialogue(player, npc_id, dialogue_id)
        
        # Save session after modifications
        session_manager.save_session(session.session_id)
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error starting dialogue: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@dialogue_context_bp.route("/dialogue/node/<node_id>", methods=["GET"])
def get_dialogue_node(node_id):
    """Get a specific dialogue node.
    
    Args:
        node_id: ID of the dialogue node to retrieve
    
    Response:
        {
            "success": true,
            "data": {
                "node": { node data },
                "available_choices": [ filtered choices ]
            }
        }
    
    Status Codes:
        200: Node retrieved successfully
        401: Invalid/missing authentication
        404: Node not found
        500: Server error
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            response, status_code = error
            return response, status_code
        
        # Validate node_id
        node_id = node_id.strip()
        if not node_id:
            return jsonify({
                "success": False,
                "error": "node_id cannot be empty"
            }), 400
        
        # Call GameService
        game_service = current_app.game_service
        result = game_service.get_dialogue_node(player, node_id)
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error retrieving dialogue node: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@dialogue_context_bp.route("/dialogue/select", methods=["POST"])
def select_dialogue_choice():
    """Process a dialogue choice selection.
    
    Request Body:
        {
            "conversation_id": "uuid",
            "choice_id": "choice_001"
        }
    
    Response:
        {
            "success": true,
            "data": {
                "conversation_id": "uuid",
                "current_node": { next node data },
                "available_choices": [ next choices ],
                "conversation_history": { updated history },
                "is_complete": false
            }
        }
    
    Status Codes:
        200: Choice processed successfully
        400: Missing required fields or invalid choice
        401: Invalid/missing authentication
        404: Conversation not found
        500: Server error
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            response, status_code = error
            return response, status_code
        
        # Validate request body
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Request must be JSON"
            }), 400
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = {"conversation_id", "choice_id"}
        missing = required_fields - set(data.keys())
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400
        
        conversation_id = data.get("conversation_id", "").strip()
        choice_id = data.get("choice_id", "").strip()
        
        if not conversation_id or not choice_id:
            return jsonify({
                "success": False,
                "error": "conversation_id and choice_id cannot be empty"
            }), 400
        
        # Call GameService
        game_service = current_app.game_service
        result = game_service.select_dialogue_choice(
            player,
            conversation_id,
            choice_id
        )
        
        # Save session after modifications
        session_manager.save_session(session.session_id)
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error selecting dialogue choice: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@dialogue_context_bp.route("/npc/<npc_id>/dialogue/history", methods=["GET"])
def get_conversation_history(npc_id):
    """Get conversation history with an NPC.
    
    Args:
        npc_id: ID of the NPC
    
    Query Parameters:
        limit: Maximum conversations to return (default: 50)
        offset: Number of conversations to skip (default: 0)
    
    Response:
        {
            "success": true,
            "data": {
                "npc_id": "merchant_kael",
                "total_conversations": 3,
                "conversations": [
                    { conversation history },
                    ...
                ]
            }
        }
    
    Status Codes:
        200: History retrieved successfully
        401: Invalid/missing authentication
        404: NPC not found
        500: Server error
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            response, status_code = error
            return response, status_code
        
        # Validate npc_id
        npc_id = npc_id.strip()
        if not npc_id:
            return jsonify({
                "success": False,
                "error": "npc_id cannot be empty"
            }), 400
        
        # Get pagination parameters (optional)
        try:
            limit = int(request.args.get("limit", 50))
            offset = int(request.args.get("offset", 0))
            
            if limit < 1 or offset < 0:
                return jsonify({
                    "success": False,
                    "error": "limit must be > 0, offset must be >= 0"
                }), 400
        except ValueError:
            return jsonify({
                "success": False,
                "error": "limit and offset must be integers"
            }), 400
        
        # Call GameService
        game_service = current_app.game_service
        result = game_service.get_conversation_history(player, npc_id)
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@dialogue_context_bp.route("/npc/<npc_id>/dialogue/available", methods=["GET"])
def get_available_dialogues(npc_id):
    """Get available dialogues with an NPC.
    
    Lists all dialogue options available to the player with this NPC,
    filtered by story gates and player conditions.
    
    Args:
        npc_id: ID of the NPC
    
    Response:
        {
            "success": true,
            "data": {
                "npc_id": "merchant_kael",
                "total_available": 2,
                "dialogues": [
                    {
                        "dialogue_id": "greeting_001",
                        "title": "Greetings",
                        "description": "..."
                    },
                    ...
                ]
            }
        }
    
    Status Codes:
        200: Available dialogues retrieved successfully
        401: Invalid/missing authentication
        404: NPC not found
        500: Server error
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            response, status_code = error
            return response, status_code
        
        # Validate npc_id
        npc_id = npc_id.strip()
        if not npc_id:
            return jsonify({
                "success": False,
                "error": "npc_id cannot be empty"
            }), 400
        
        # Call GameService
        game_service = current_app.game_service
        result = game_service.get_available_dialogues(player, npc_id)
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error retrieving available dialogues: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500
