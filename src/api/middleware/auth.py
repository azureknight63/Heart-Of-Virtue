"""Shared session/auth resolution for API routes."""

from flask import current_app, jsonify, request


def get_session_and_player():
    """Resolve the session manager, session, and player for the current request.

    Reads the Bearer token from the request's Authorization header.

    Returns:
        Tuple of (session_manager, session, player, error) on success, where
        error is None. On failure, session_manager/session/player are None and
        error is a (response, status_code) tuple the caller should return
        immediately (e.g. ``if error: return error``).
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return (
            None,
            None,
            None,
            (jsonify({"success": False, "error": "Missing or invalid Authorization header"}), 401),
        )

    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)
    if not session:
        return (
            None,
            None,
            None,
            (jsonify({"success": False, "error": "Invalid or expired session"}), 401),
        )

    player = session_manager.get_player(session_id)
    if not player:
        return (
            None,
            None,
            None,
            (jsonify({"success": False, "error": "Player not found"}), 404),
        )

    return session_manager, session, player, None
