"""Save and load game routes."""

import logging

from flask import Blueprint, request, jsonify
from src.api.services.auth_service import SaveLimitReached
from src.api.middleware.auth import get_session_and_player, require_game_service
from src.api.services.validators import validate_string_field

saves_bp = Blueprint("saves", __name__)

logger = logging.getLogger(__name__)

# Issue #523: POST /saves used to gate on `"name" in data` alone, so "", None
# and a 1000-character name were all stored verbatim -- the load list then
# rendered a blank row, a row literally labelled "None", or one that blew out
# the layout. Not a security issue (the SQL is parameterised); a data-quality
# and UI one.
#
# The frontend never asks the player to type a save name -- ActionsPanel
# generates `Save_<iso-timestamp>` (24 chars) and useAutosave sends the literal
# "Autosave" (8 chars) -- so there is no input field to mirror this cap into.
# Should a naming dialog ever be added, mirror MAX_SAVE_NAME_LENGTH there as a
# `maxLength` and reference this constant by name in a comment (CLAUDE.md flags
# mirrored-literal drift as a recurring failure mode in this codebase).
MAX_SAVE_NAME_LENGTH = 100

# Used when the caller supplies no "name" at all. Server-generated, so both
# bypass the rules by construction: validate_save_name returns one before any
# check runs, which is what keeps validation from ever rejecting an autosave.
#
# The two are distinct because the name is what the load list renders: an
# autosave POSTed as just {"is_autosave": true} is stored with the flag set, so
# labelling it "Manual Save" put a row in front of the player describing itself
# as the opposite of what it is. useAutosave sends the "Autosave" literal
# explicitly today, so this default is the fallback for a caller that does not.
DEFAULT_SAVE_NAME = "Manual Save"
DEFAULT_AUTOSAVE_NAME = "Autosave"


def validate_save_name(data):
    """Resolve and validate the save name from a POST /saves body.

    Returns ``(name, error)``. Exactly one is non-None: on success ``name`` is
    the stripped, validated save name; on failure ``error`` is a player-facing
    message explaining what is wrong.

    Rules (deliberately conservative -- reject rather than repair, so a mistake
    is reported instead of silently rewritten):
      * absent            -> the server default for this save's kind
                             (DEFAULT_AUTOSAVE_NAME when the body sets
                             is_autosave, else DEFAULT_SAVE_NAME), no
                             validation
      * not a string      -> error (no coercion; ``None`` must not become "None")
      * blank             -> error (no auto-naming, which would hide the mistake)
      * > MAX_SAVE_NAME_LENGTH after stripping -> error (no truncation, which
        would silently discard the player's intent)

    The type and blank rules are delegated to the shared route validator so that
    every endpoint agrees on what a usable string field is -- in particular its
    blank rule counts a value made only of invisible codepoints (NUL, U+200B) as
    empty, which plain ``.strip()`` does not.
    """
    if "name" not in data:
        if data.get("is_autosave"):
            return DEFAULT_AUTOSAVE_NAME, None
        return DEFAULT_SAVE_NAME, None

    raw = data["name"]
    is_valid, error = validate_string_field(raw, "Save name")
    if not is_valid:
        return None, error

    # Measured after stripping, so padding alone cannot push a legitimate name
    # over the cap. validate_string_field's own max_length deliberately measures
    # the raw value instead, so the check stays here rather than being delegated.
    name = raw.strip()
    if len(name) > MAX_SAVE_NAME_LENGTH:
        return (
            None,
            f"Save name cannot exceed {MAX_SAVE_NAME_LENGTH} characters "
            f"(got {len(name)}).",
        )

    return name, None


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

        save_name, name_error = validate_save_name(data)
        if name_error:
            return jsonify({"success": False, "error": name_error}), 400

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
