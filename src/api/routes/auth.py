"""Authentication routes."""

from flask import Blueprint, request, jsonify
from src.api.services import SessionManager

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    """Create a new player session.

    Request body:
        {
            "username": "str"
        }

    Returns:
        {
            "success": bool,
            "session_id": "str",
            "player_id": "str",
            "expires_at": "ISO 8601 timestamp"
        }
    """
    try:
        data = request.get_json()

        if not data or "username" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing username",
                    }
                ),
                400,
            )

        username = data["username"].strip()

        if not username or len(username) < 2:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Username must be at least 2 characters",
                    }
                ),
                400,
            )

        # Get session manager from app context
        session_manager = None
        if hasattr(request, "app"):
            session_manager = request.app.session_manager
        else:
            from flask import current_app

            session_manager = current_app.session_manager

        if not session_manager:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Session manager not initialized",
                    }
                ),
                500,
            )

        # Create session
        session_id, player_id = session_manager.create_session(username)
        session = session_manager.get_session(session_id)

        return (
            jsonify(
                {
                    "success": True,
                    "session_id": session_id,
                    "player_id": player_id,
                    "expires_at": session.expires_at.isoformat(),
                    "message": f"Welcome, {username}!",
                }
            ),
            201,
        )

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


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """End a player session.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "message": "str"
        }
    """
    try:
        # Extract session ID from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Missing or invalid Authorization header",
                    }
                ),
                401,
            )

        session_id = auth_header[7:]  # Remove "Bearer " prefix

        from flask import current_app

        session_manager = current_app.session_manager

        if not session_manager:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Session manager not initialized",
                    }
                ),
                500,
            )

        # Expire session
        success = session_manager.expire_session(session_id)

        if success:
            return jsonify({"success": True, "message": "Logged out successfully"}), 200
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Session not found or already expired",
                    }
                ),
                404,
            )

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


@auth_bp.route("/validate", methods=["GET"])
def validate_session():
    """Validate a session ID.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "valid": bool,
            "username": "str or null",
            "player_id": "str or null"
        }
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"valid": False, "username": None, "player_id": None}), 401

        session_id = auth_header[7:]

        from flask import current_app

        session_manager = current_app.session_manager
        session = session_manager.get_session(session_id)

        if session:
            return (
                jsonify(
                    {
                        "valid": True,
                        "username": session.username,
                        "player_id": session.player_id,
                    }
                ),
                200,
            )
        else:
            return (
                jsonify({"valid": False, "username": None, "player_id": None}),
                401,
            )

    except Exception as e:
        return (
            jsonify(
                {
                    "valid": False,
                    "error": str(e),
                }
            ),
            500,
        )
