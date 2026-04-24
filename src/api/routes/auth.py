"""Authentication routes."""

from flask import Blueprint, request, jsonify
from src.api.services.auth_service import auth_service
from functools import wraps
import asyncio

auth_bp = Blueprint("auth", __name__)

def require_auth(f):
    @wraps(f)
    async def async_decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "Missing or invalid Authorization header"}), 401
        session_id = auth_header[7:]
        from flask import current_app
        session_manager = current_app.session_manager
        if not session_manager:
            return jsonify({"success": False, "error": "Session manager not initialized"}), 500
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({"success": False, "error": "Session not found or already expired"}), 401
        request.session_obj = session
        request.session_manager = session_manager
        return await f(*args, **kwargs)
        
    @wraps(f)
    def sync_decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "Missing or invalid Authorization header"}), 401
        session_id = auth_header[7:]
        from flask import current_app
        session_manager = current_app.session_manager
        if not session_manager:
            return jsonify({"success": False, "error": "Session manager not initialized"}), 500
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({"success": False, "error": "Session not found or already expired"}), 401
        request.session_obj = session
        request.session_manager = session_manager
        return f(*args, **kwargs)

    if asyncio.iscoroutinefunction(f):
        return async_decorated
    return sync_decorated


@auth_bp.route("/auth/register", methods=["POST"])
async def register():
    """Create a new player account and session.

    Request body:
        {
            "username": "str",
            "password": "str",
            "email": "str"
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

        if (
            not data
            or "username" not in data
            or "password" not in data
            or "email" not in data
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": "Missing username, password, or email",
                    }
                ),
                400,
            )

        username = data["username"].strip()
        password = data["password"]
        email = data["email"].strip()

        # Registration logic using auth_service
        try:
            user = await auth_service.create_user(username, password, email)
        except ValueError as ve:
            msg = str(ve)
            # Don't expose internal config/infrastructure details to users
            if any(
                kw in msg for kw in ("_URL", "_KEY", "_TOKEN", "not set", "os.environ")
            ):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "service_unavailable",
                            "message": "Registration is temporarily unavailable. Please try again later.",
                        }
                    ),
                    503,
                )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "validation_error",
                        "message": msg,
                    }
                ),
                400,
            )
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "conflict_error",
                            "message": "Username already exists",
                        }
                    ),
                    409,
                )
            raise e

        # Get session manager from app context
        from flask import current_app

        session_manager = current_app.session_manager

        # Create session with the DB user ID
        session_id, player_id = session_manager.create_session(username)
        # Link session to DB user ID
        session = session_manager.get_session(session_id)
        session.db_user_id = user["id"]
        session.data["timezone"] = user.get("timezone", "US/Eastern")

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "session_id": session_id,
                        "message": "Account created successfully. Welcome!",
                    },
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
async def login():
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

        # Authenticate using auth_service
        user = await auth_service.authenticate_user(username, password)

        if not user:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "auth_error",
                        "message": "Invalid username or password",
                    }
                ),
                401,
            )

        # Get session manager from app context
        from flask import current_app

        session_manager = current_app.session_manager

        # Create session
        session_id, player_id = session_manager.create_session(username)
        # Link session to DB user ID
        session = session_manager.get_session(session_id)
        session.db_user_id = user["id"]
        session.data["timezone"] = user.get("timezone", "US/Eastern")

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "session_id": session_id,
                        "message": "Welcome back!",
                    },
                }
            ),
            200,
        )

    except Exception as e:
        msg = str(e)
        # Don't expose internal config/infrastructure details to users
        if any(kw in msg for kw in ("_URL", "_KEY", "_TOKEN", "not set", "os.environ")):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "service_unavailable",
                        "message": "Login is temporarily unavailable. Please try again later.",
                    }
                ),
                503,
            )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "server_error",
                    "message": msg,
                }
            ),
            500,
        )


@auth_bp.route("/auth/logout", methods=["POST"])
@require_auth
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
        session_id = request.session_obj.session_id
        session_manager = request.session_manager

        # Expire session
        success = session_manager.expire_session(session_id)

        if success:
            return (
                jsonify({"success": True, "message": "Logged out successfully"}),
                200,
            )
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
            return (
                jsonify({"valid": False, "username": None, "player_id": None}),
                401,
            )

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

@auth_bp.route("/auth/settings", methods=["GET", "PUT"])
@require_auth
async def settings():
    """Get or update user settings.

    Headers:
        Authorization: Bearer <session_id>

    Returns:
        {
            "success": bool,
            "data": {
                "timezone": "str"
            }
        }
    """
    try:
        session = request.session_obj
        if not session.db_user_id:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
            
        user_id = session.db_user_id

        if request.method == "GET":
            # Just read from session cache
            return jsonify({
                "success": True,
                "data": {
                    "timezone": session.data.get("timezone", "US/Eastern")
                }
            }), 200

        elif request.method == "PUT":
            data = request.get_json()
            if not data or "timezone" not in data:
                return jsonify({"success": False, "error": "Missing timezone"}), 400
                
            timezone = data["timezone"]
            success = await auth_service.update_user_timezone(user_id, timezone)
            
            if success:
                session.data["timezone"] = timezone
                return jsonify({
                    "success": True,
                    "message": "Settings updated successfully",
                    "data": {
                        "timezone": timezone
                    }
                }), 200
            else:
                return jsonify({"success": False, "error": "Failed to update settings"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

