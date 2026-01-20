"""Authentication routes."""

from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from src.api.services import SessionManager

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/register", methods=["POST"])
def register():
    """Create a new player account and session.

    Request body:
        {
            "username": "str",
            "password": "str"
        }

    Returns:
        {
            "success": bool,
            "data": {
                "session_id": "str",
                "username": "str",
                "message": "str"
            }
        }
    """
    try:
        data = request.get_json()

        if not data or "username" not in data or "password" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "Missing username or password",
                    }
                ),
                400,
            )

        username = data["username"].strip()
        password = data["password"]

        if not username or len(username) < 2:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "Username must be at least 2 characters",
                    }
                ),
                400,
            )

        if not password or len(password) < 8:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "Password must be at least 8 characters",
                    }
                ),
                400,
            )

        # Hash password (prepared for database storage in the future)
        # Note: Current session manager doesn't persist users yet
        hashed_password = generate_password_hash(password)

        # Get session manager from app context
        from flask import current_app

        session_manager = current_app.session_manager

        if not session_manager:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "server_error",
                        "message": "Session manager not initialized",
                    }
                ),
                500,
            )

        # Create session (in a real app, would store password hash, check for duplicates, etc)
        session_id, player_id = session_manager.create_session(username)
        session = session_manager.get_session(session_id)

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "session_id": session_id,
                        "message": "Account created successfully. Welcome!",
                    }
                }
            ),
            201,
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "server_error",
                    "message": str(e),
                }
            ),
            500,
        )


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """Create a new player session (or login existing player).

    Request body:
        {
            "username": "str",
            "password": "str"
        }

    Returns:
        {
            "success": bool,
            "data": {
                "session_id": "str",
                "username": "str",
                "message": "str"
            }
        }
    """
    try:
        data = request.get_json()

        if not data or "username" not in data or "password" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "Missing username or password",
                    }
                ),
                400,
            )

        username = data["username"].strip()
        password = data["password"]

        if not username or len(username) < 2:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "Username must be at least 2 characters",
                    }
                ),
                400,
            )

        if not password:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "Password is required",
                    }
                ),
                400,
            )

        # Get session manager from app context
        from flask import current_app

        session_manager = current_app.session_manager

        if not session_manager:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "server_error",
                        "message": "Session manager not initialized",
                    }
                ),
                500,
            )

        # Create session (in a real app, would validate password hash)
        session_id, player_id = session_manager.create_session(username)
        session = session_manager.get_session(session_id)

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "session_id": session_id,
                        "message": "Welcome back!",
                    }
                }
            ),
            200,
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "server_error",
                    "message": str(e),
                }
            ),
            500,
        )


@auth_bp.route("/auth/logout", methods=["POST"])
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


@auth_bp.route("/auth/validate", methods=["GET"])
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
