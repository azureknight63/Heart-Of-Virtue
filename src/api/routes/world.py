"""World navigation routes."""

from flask import Blueprint, request, jsonify

world_bp = Blueprint("world", __name__)


def get_session_and_player(request):
    """Extract session and player from request.

    Returns:
        Tuple of (session_manager, session, player, None) on success
        or (None, None, None, (jsonify_response, status_code)) on error
    """
    from flask import current_app

    # Extract session ID from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, None, (jsonify({"error": "Missing authorization"}), 401)

    session_id = auth_header[7:]
    session_manager = current_app.session_manager

    # Get session and player
    session = session_manager.get_session(session_id)
    if not session:
        return None, None, None, (jsonify({"error": "Invalid or expired session"}), 401)

    player = session_manager.get_player(session_id)
    if not player:
        return None, None, None, (jsonify({"error": "Player not found"}), 404)

    return session_manager, session, player, None


@world_bp.route("/world", methods=["GET"])
@world_bp.route("/world/", methods=["GET"])  # Add trailing slash variant
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
            return error[0], error[1]

        game_service = None
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

        room = game_service.get_current_room(player, session.data)
        
        # Debug: Check if room has error
        if "error" in room:
            return jsonify({"success": False, "error": room["error"]}), 404

        return jsonify({"success": True, "room": room}), 200

    except Exception as e:
        import traceback
        print(f"[ERROR] World route exception: {e}", flush=True)
        traceback.print_exc()
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )


@world_bp.route("/world/move", methods=["POST"])
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
            return error[0], error[1]

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

        result = game_service.move_player(player, direction, session.data)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        # Save session after movement (includes pending events)
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


@world_bp.route("/world/events/input", methods=["POST"])
def submit_event_input():
    """Submit user input for a pending event.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "event_id": str (UUID),
            "user_input": str
        }

    Returns:
        {
            "success": bool,
            "output_text": str (optional),
            "error": str (optional)
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error[0], error[1]

        data = request.get_json()
        if not data or "event_id" not in data or "user_input" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing event_id or user_input",
                    }
                ),
                400,
            )

        event_id = data["event_id"]
        user_input = data["user_input"]

        # Sanitize user input
        from src.api.utils.input_sanitizer import sanitize_event_input
        sanitized_input, validation_error = sanitize_event_input(user_input, session.data, event_id)
        
        if validation_error:
            return jsonify({"success": False, "error": validation_error}), 400

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

        # Process the event with user input
        result = game_service.process_event_input(player, event_id, sanitized_input, session.data)

        # Save session after processing event
        session_manager.save_session(session.session_id)

        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        import traceback
        print(f"[ERROR] Event input route exception: {e}", flush=True)
        traceback.print_exc()
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )


@world_bp.route("/world/tile", methods=["GET"])
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
            return error[0], error[1]

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

        tile = game_service.get_tile(player, x, y)
        if "error" in tile:
            return jsonify({"success": False, "error": tile["error"]}), 404

        return jsonify({"success": True, "tile": tile}), 200
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Internal server error",
                    "message": str(e),
                }
            ),
            500,
        )


@world_bp.route("/world/explored", methods=["GET"])
def get_explored_tiles():
    """Get all tiles explored by the player.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "explored_tiles": {
                "x,y": {
                    "items": [...],
                    "npcs": [...],
                    "objects": [...],
                    "exits": {...}
                },
                ...
            }
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error[0], error[1]

        from flask import current_app
        game_service = current_app.game_service

        if not game_service:
            return jsonify({"success": False, "error": "Game service not initialized"}), 500

        explored_tiles = game_service.get_explored_tiles(player)

        return jsonify({"success": True, "explored_tiles": explored_tiles}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@world_bp.route("/world/tiles/batch", methods=["POST"])
def get_tiles_batch():
    """Get multiple tiles at once (batch request).
    
    Headers:
        Authorization: Bearer <session_id>
    
    Request body:
        {
            "coordinates": [
                {"x": int, "y": int},
                {"x": int, "y": int},
                ...
            ]
        }
    
    Returns:
        {
            "success": bool,
            "tiles": [
                {
                    "x": int,
                    "y": int,
                    "name": str,
                    "description": str,
                    "items": [...],
                    "npcs": [...]
                },
                ...
            ]
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error[0], error[1]

        data = request.get_json()
        if not data or "coordinates" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing coordinates array",
                    }
                ),
                400,
            )

        coordinates = data["coordinates"]
        if not isinstance(coordinates, list):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Coordinates must be an array",
                    }
                ),
                400,
            )

        # Limit batch size to prevent abuse
        if len(coordinates) > 20:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Maximum 20 tiles per batch request",
                    }
                ),
                400,
            )

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

        tiles = []
        for coord in coordinates:
            if not isinstance(coord, dict) or "x" not in coord or "y" not in coord:
                continue
            
            try:
                x = int(coord["x"])
                y = int(coord["y"])
                tile = game_service.get_tile(player, x, y)
                
                # Only include valid tiles (skip errors)
                if "error" not in tile:
                    tiles.append(tile)
            except (ValueError, TypeError):
                # Skip invalid coordinates
                continue

        return jsonify({"success": True, "tiles": tiles}), 200
    
    except Exception as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Internal server error",
                        "message": str(e),
                    }
                ),
                500,
            )


@world_bp.route("/world/commands", methods=["GET"])
def get_available_commands():
    """Get available commands/actions for player in current room.

    Authorization: Required (Bearer token)

    Returns:
        {
            "success": bool,
            "commands": [
                {
                    "name": str (action name),
                    "hotkey": list (keyboard shortcuts)
                }
            ],
            "count": int (number of available commands)
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
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

        commands_data = game_service.get_available_commands(player)

        return jsonify({"success": True, **commands_data}), 200
    
    except Exception as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Internal server error",
                        "message": str(e),
                    }
                ),
                500,
            )


@world_bp.route("/world/interact", methods=["POST"])
def interact_with_target():
    """Interact with an object or NPC.

    Headers:
        Authorization: Bearer <session_id>

    Request body:
        {
            "target_id": "...",
            "action": "...",
            "quantity": int (optional)
        }

    Returns:
        {
            "success": bool,
            "message": str,
            "target_name": str,
            "action": str
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
        if error:
            return error[0], error[1]

        data = request.get_json()
        if not data or "target_id" not in data or "action" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing target_id or action",
                    }
                ),
                400,
            )

        target_id = data["target_id"]
        action = data["action"]
        quantity = data.get("quantity")

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

        result = game_service.interact_with_target(
            player, target_id, action, quantity=quantity, session_data=session.data
        )

        if not result["success"]:
            return jsonify(result), 200

        # Save session to ensure world state changes (like block_exit) are persisted
        session_manager.save_session(session.session_id)

        return jsonify(result), 200

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


@world_bp.route("/world/events", methods=["POST"])
def trigger_room_events():
    """Trigger events in the current room.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "events": [...]
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
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

        # Get current tile
        tile = player.universe.get_tile(player.location_x, player.location_y)
        if not tile:
            return jsonify({"success": False, "error": "Current tile not found"}), 404

        # Trigger events on the tile
        events_triggered = game_service.trigger_tile_events(player, tile, session.data)

        # Store tile modifications after events have processed
        game_service.store_tile_modification(
            session.data,
            tile.x,
            tile.y,
            'block_exit',
            tile.block_exit.copy() if hasattr(tile, 'block_exit') else []
        )
        session_manager.save_session(session.session_id)

        return jsonify({"success": True, "events": events_triggered}), 200

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


@world_bp.route("/world/search", methods=["POST"])
def search_room():
    """Search the current room for hidden items/NPCs.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "messages": [str],
            "found": [...],
            "room": {...}
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player(request)
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

        result = game_service.search(player)

        # Save session to ensure items/NPCs found during search are persisted
        session_manager.save_session(session.session_id)

        return jsonify(result), 200

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

