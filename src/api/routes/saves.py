"""Save and load game routes."""

import logging

from flask import Blueprint, request, jsonify
from src.api.services.auth_service import SaveLimitReached
from src.api.middleware.auth import get_session_and_player, require_game_service

saves_bp = Blueprint("saves", __name__)

logger = logging.getLogger(__name__)

#: Longest save name accepted. The name is client-supplied, persisted to Turso,
#: echoed back in the 201 body, and listed in the save picker, so it is bounded
#: here rather than wherever it is next rendered. 96 is set against what a
#: person types ("Before the Grotto, 3rd try") with room to spare, and far
#: below MAX_CONTENT_LENGTH -- which was previously the *only* thing standing
#: between this field and a megabyte of attacker text in a durable row. Feedback
#: bounds its title the same way (MAX_TITLE_LENGTH, routes/feedback.py).
MAX_SAVE_NAME_LENGTH = 96

#: Used when a client sends no name at all, which is a documented shape: the
#: route accepts a body carrying only ``is_autosave``.
DEFAULT_SAVE_NAME = "Manual Save"


@saves_bp.route("/saves", methods=["GET"])
async def list_saves():
    """List all saved games for player from Turso cloud storage."""
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        if not hasattr(session, "db_user_id") or not session.db_user_id:
            return jsonify({"success": True, "saves": []}), 200

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error
        timezone = session.data.get("timezone", "America/New_York")

        saves = await game_service.list_saves(session.db_user_id, timezone=timezone)

        return jsonify({"success": True, "saves": saves}), 200

    except Exception:
        logger.exception("Unhandled error in list_saves")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@saves_bp.route("/saves", methods=["POST"])
async def create_save():
    """Create a new manual or auto save in Turso cloud."""
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        if not hasattr(session, "db_user_id") or not session.db_user_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Cloud saves require a registered account.",
                    }
                ),
                403,
            )

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or (
            "name" not in data and "is_autosave" not in data
        ):
            return (
                jsonify({"success": False, "error": "Missing save name or type"}),
                400,
            )

        # Rejected rather than coerced. ``str(data["name"])`` would happily
        # persist "{'$ne': None}" or "[1, 2, 3]" as somebody's save title,
        # which is a client bug worth reporting back rather than storing; this
        # matches how auth.py answers a non-string username. Over-length IS
        # truncated rather than refused, because a name is presentation and
        # losing the tail of one should not lose the save.
        save_name = data.get("name", DEFAULT_SAVE_NAME)
        if not isinstance(save_name, str):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Save name must be a string",
                    }
                ),
                400,
            )
        save_name = save_name.strip()[:MAX_SAVE_NAME_LENGTH] or DEFAULT_SAVE_NAME

        is_autosave = data.get("is_autosave", False)

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        try:
            save_id = await game_service.save_game(
                player, save_name, session.db_user_id, is_autosave=is_autosave
            )
        except SaveLimitReached as limit:
            # The ONLY exception whose text is echoed here, and it is echoed
            # because of its type. See routes/auth.py for the same rule and
            # the leak that produced it.
            return jsonify({"success": False, "error": str(limit)}), 403
        except ValueError:
            # Everything else is infrastructure until declared otherwise.
            # This used to be the same `except ValueError: str(ve)` that leaked
            # `could not connect to postgres://svc:<password>@...` out of the
            # registration route -- and `save_game` reaches `db.get_client()`,
            # which raises `ValueError("TURSO_DATABASE_URL is not set")`.
            # Logged for the operator, masked for the player.
            logger.exception("Save failed with a non-limit ValueError")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "service_unavailable",
                        "message": (
                            "Saving is temporarily unavailable. Please try "
                            "again later."
                        ),
                    }
                ),
                503,
            )

        # save_game returns None only for an autosave skipped because
        # GameConfig.autosave_enabled is False (issue #450) -- not an error,
        # just nothing to report.
        if save_id is None:
            return (
                jsonify(
                    {
                        "success": True,
                        "skipped": True,
                        "message": "Autosave disabled",
                    }
                ),
                200,
            )

        from datetime import datetime

        return (
            jsonify(
                {
                    "success": True,
                    "save_id": save_id,
                    "timestamp": datetime.now().isoformat(),
                    "message": (
                        f"Game saved: {save_name}"
                        if not is_autosave
                        else "Game autosaved"
                    ),
                }
            ),
            201,
        )

    except Exception:
        logger.exception("Unhandled error in create_save")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@saves_bp.route("/saves/<save_id>/load", methods=["POST"])
async def load_save(save_id):
    """Load a saved game from Turso cloud."""
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        if not hasattr(session, "db_user_id") or not session.db_user_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Cloud saves require a registered account.",
                    }
                ),
                403,
            )

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        loaded_player = await game_service.load_game(save_id, session.db_user_id)

        if not loaded_player:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Save not found or access denied",
                    }
                ),
                404,
            )

        # Update session with loaded player
        session_manager.set_player(session.session_id, loaded_player)
        session_manager.save_session(session.session_id)

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Game loaded successfully",
                }
            ),
            200,
        )

    except Exception:
        logger.exception("Unhandled error in load_save")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@saves_bp.route("/saves/<save_id>", methods=["DELETE"])
async def delete_save(save_id):
    """Delete a saved game from Turso cloud."""
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        if not hasattr(session, "db_user_id") or not session.db_user_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Cloud saves require a registered account.",
                    }
                ),
                403,
            )

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

        success = await game_service.delete_save(save_id, session.db_user_id)

        if success:
            return (
                jsonify({"success": True, "message": "Save deleted successfully"}),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Save not found or access denied",
                    }
                ),
                404,
            )

    except Exception:
        logger.exception("Unhandled error in delete_save")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )


@saves_bp.route("/game/new", methods=["POST"])
def new_game():
    """Start a new game for the current session.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        session_manager, session, player, error = get_session_and_player()
        if error:
            return error

        success = session_manager.start_new_game(session.session_id)

        if success:
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "New game started successfully",
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to start new game",
                    }
                ),
                400,
            )

    except Exception:
        logger.exception("Unhandled error in new_game")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                }
            ),
            500,
        )
