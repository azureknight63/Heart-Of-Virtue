"""World navigation routes."""

import logging
import threading

from flask import Blueprint, current_app, jsonify, request

from src.api.middleware.auth import get_session_and_player, require_game_service
from src.api.services.validators import (
    validate_direction,
    validate_string_field,
    ensure_dict,
)

world_bp = Blueprint("world", __name__)
_log = logging.getLogger(__name__)

# One-shot latch for the process-wide background services kicked off by the
# first real world load. See _ensure_background_services_started.
#
# This is process-wide startup state living in a route module, which is not
# where it belongs: ``src/api/app.py`` owns startup wiring, and the latch would
# be better as app-scoped state set up there (the trigger would stay here,
# since GET /world is the event, but the "has this process started them yet"
# bit would not). Moving it is a cross-module change and this module cannot
# make it alone; ``_reset_background_services`` below is the interim so at
# least tests do not have to reach in and assign the global by hand.
_background_services_lock = threading.Lock()
_background_services_started = False


def _reset_background_services() -> None:
    """Re-arm the latch. Test-only.

    The latch outlives any one test, so a test that trips it turns every later
    one into a silent no-op — which is an ordering dependency, not a test. The
    reset is exposed as a function rather than left to an assignment on
    ``world._background_services_started`` at the call site, so the
    invariant has one owner and the global stays private to this module.
    """
    global _background_services_started
    with _background_services_lock:
        _background_services_started = False


def _ensure_background_services_started(app):
    """Start the process-wide LLM background services, once.

    ``GET /api/world`` is simply the earliest point at which the process is
    known to be serving a real session, which is why the startup wiring hangs
    off it — but it is also the hottest route in the game, so everything here
    is behind a single module-level latch.

    The latch earns its keep on the *imports*, not on the callees. Both
    services are individually idempotent — ``start_digest_scheduler()`` latches
    every terminal branch, including the unconfigured ones, and ``prewarm()``
    claims its attempt under a lock — so re-entering them is cheap. Reaching
    them is not: ``from ai.llm_client import ...`` pulls in a 3000-line module
    that imports ``requests`` and calls ``load_project_env()``, and an
    unlatched route would pay that import lookup plus two function calls on the
    request thread for the rest of the process's life.

    Each service gets its own ``try``, so a failure in one cannot take the
    other with it. They are unrelated, and one shared block meant an exception
    raised before ``start_digest_scheduler()`` disabled the digest for the
    process lifetime behind a single warning about "background services".

    Gated on TESTING (deliberately *without* latching, so a test app can never
    poison a later real one in the same process): ``prewarm()`` performs real
    network discovery/validation, so without this every suite or bug-hunt
    world load would spend free-tier requests and mutate class-level LLM state
    on a daemon thread, after the per-test reset fixtures have already run.
    The digest scheduler is gated for the same reason feedback.py's GitHub
    issue filing is — once a webhook is configured it posts real analytics to
    Discord.
    """
    global _background_services_started

    if _background_services_started or app.config.get("TESTING"):
        return

    with _background_services_lock:
        if _background_services_started:
            return
        # Latch before the work, not after: a failure here must not re-run on
        # every subsequent request.
        _background_services_started = True

        # WARNING, not DEBUG, in both handlers below: WARNING is Python's root
        # default, which this app deliberately leaves in place
        # (``app.py::_configure_logging`` sets no level at all unless
        # ``LOG_LEVEL`` is), so a debug-level record is invisible in exactly
        # the runs where these services silently failed to start.

        try:
            from ai.llm_client import NpcChatLLMAdapter

            # Eagerly prewarm the NPC chat LLM adapter so OpenRouter
            # discovery/validation doesn't run on the first chat request and
            # add latency there. It runs on a daemon thread because the
            # constructor does real network discovery and model validation —
            # seconds of blocking I/O — and gunicorn runs a single worker, so
            # inline it would stall this response and every concurrent request
            # behind it. It does not hold a lock for that duration: prewarm()
            # claims the attempt under _instances_lock and then builds outside
            # it, so concurrent get_instance()/is_prewarmed() callers are not
            # starved.
            if not NpcChatLLMAdapter.is_prewarmed():
                _log.info("Triggering NPC chat LLM prewarm after map load...")
                threading.Thread(
                    target=NpcChatLLMAdapter.prewarm,
                    name="npc-chat-prewarm",
                    daemon=True,
                ).start()
        except Exception:
            _log.warning("NPC chat LLM prewarm failed to start", exc_info=True)

        try:
            from ai.provider_digest import start_digest_scheduler

            # Returns whether a scheduler thread actually started; discarding
            # it left "webhook configured but nothing scheduled" invisible.
            if start_digest_scheduler():
                _log.info("Provider digest scheduler started")
            else:
                # The failure case gets the level that is actually visible:
                # logging "started=False" at INFO reported the outage into a
                # sink nobody was listening to.
                _log.warning(
                    "Provider digest scheduler did not start "
                    "(no webhook configured, or already running)"
                )
        except Exception:
            _log.warning("Provider digest scheduler failed to start", exc_info=True)


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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        room = game_service.get_current_room(player, session.data)

        if "error" in room:
            return jsonify({"success": False, "error": room["error"]}), 404

        _ensure_background_services_started(current_app)

        return jsonify({"success": True, "room": room}), 200

    except Exception:
        _log.exception("World route exception in get_current_room")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        data = ensure_dict(request.get_json(silent=True))
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

        is_valid, dir_error = validate_string_field(data["direction"], "direction")
        if not is_valid:
            return jsonify({"success": False, "error": dir_error}), 400

        direction = data["direction"].lower()

        is_valid, direction_error = validate_direction(direction)
        if not is_valid:
            return jsonify({"success": False, "error": direction_error}), 400

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        result = game_service.move_player(
            player, direction, session.data, session_id=session.session_id
        )

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        # Save session after movement (includes pending events)
        session_manager.save_session(session.session_id)

        return jsonify({"success": True, **result}), 200

    except Exception:
        _log.exception("World route exception in move_player")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        data = ensure_dict(request.get_json(silent=True))
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

        # event_id is used as a dict key (unhashable types like a list would
        # raise TypeError) and user_input is later .strip()'d — validate both
        # are strings here so bad input surfaces as a 400, not a 500.
        is_valid, event_id_error = validate_string_field(event_id, "event_id")
        if not is_valid:
            return jsonify({"success": False, "error": event_id_error}), 400

        is_valid, user_input_error = validate_string_field(
            user_input, "user_input", allow_empty=True
        )
        if not is_valid:
            return jsonify({"success": False, "error": user_input_error}), 400

        # Sanitize user input
        from src.api.utils.input_sanitizer import sanitize_event_input

        sanitized_input, validation_error = sanitize_event_input(
            user_input, session.data, event_id
        )

        if validation_error:
            return jsonify({"success": False, "error": validation_error}), 400

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        # Process the event with user input
        result = game_service.process_event_input(
            player, event_id, sanitized_input, session.data, session_id=session.session_id
        )

        # Save session after processing event
        session_manager.save_session(session.session_id)

        if not result.get("success"):
            return jsonify(result), 400

        # Detect player death caused by event processing
        if game_service.is_player_dead(player):
            result["is_game_over"] = True
            result["is_death_scene"] = True

        return jsonify(result), 200

    except Exception:
        _log.exception("World route exception in submit_event_input")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
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
        session_manager, session, player, error = get_session_and_player()
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

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        tile = game_service.get_tile(player, x, y)
        if "error" in tile:
            return jsonify({"success": False, "error": tile["error"]}), 404

        return jsonify({"success": True, "tile": tile}), 200
    except Exception:
        _log.exception("World route exception in get_tile")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Internal server error",
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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        explored_tiles = game_service.get_explored_tiles(player)

        return (
            jsonify({"success": True, "explored_tiles": explored_tiles}),
            200,
        )

    except Exception:
        _log.exception("World route exception in get_explored_tiles")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        data = ensure_dict(request.get_json(silent=True))
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

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

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

    except Exception:
        _log.exception("World route exception in get_tiles_batch")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Internal server error",
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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        commands_data = game_service.get_available_commands(player)

        return jsonify({"success": True, **commands_data}), 200

    except Exception:
        _log.exception("World route exception in get_available_commands")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Internal server error",
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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        data = ensure_dict(request.get_json(silent=True))
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

        # GameService.interact_with_target calls action.lower() before its own
        # try/except, so a non-string action (e.g. null, 123) would raise
        # AttributeError and surface as a 500. Validate here instead.
        is_valid, action_error = validate_string_field(action, "action")
        if not is_valid:
            return jsonify({"success": False, "error": action_error}), 400

        quantity = data.get("quantity")

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        result = game_service.interact_with_target(
            player,
            target_id,
            action,
            quantity=quantity,
            session_data=session.data,
            session_id=session.session_id,
        )

        if not result["success"]:
            return jsonify(result), 200

        # Save session to ensure world state changes (like block_exit) are persisted
        session_manager.save_session(session.session_id)

        return jsonify(result), 200

    except Exception:
        _log.exception("World route exception in interact_with_target")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        # Get current tile
        tile = game_service.get_current_tile_object(player)
        if not tile:
            return (
                jsonify({"success": False, "error": "Current tile not found"}),
                404,
            )

        # Trigger events on the tile
        events_triggered = game_service.trigger_tile_events(player, tile, session.data)

        # Store tile modifications after events have processed. Delegate to the
        # service so persistence logic lives in one place (see #401).
        game_service.persist_tile_state(session.data, tile)
        session_manager.save_session(session.session_id)

        return jsonify({"success": True, "events": events_triggered}), 200

    except Exception:
        _log.exception("World route exception in trigger_room_events")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@world_bp.route("/world/events/pending", methods=["GET"])
def get_pending_events():
    """Get any pending/interactive events stored in the session.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "events": [...]
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        pending_events = []
        if "pending_events" in session.data:
            for event_id, data in session.data["pending_events"].items():
                event_data = data.get("event_data", {}).copy()
                event_data["event_id"] = event_id
                pending_events.append(event_data)

        return jsonify({"success": True, "events": pending_events}), 200

    except Exception:
        _log.exception("World route exception in get_pending_events")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


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
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        result = game_service.search(player)

        # Save session to ensure items/NPCs found during search are persisted
        session_manager.save_session(session.session_id)

        return jsonify(result), 200

    except Exception:
        _log.exception("World route exception in search_room")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )
