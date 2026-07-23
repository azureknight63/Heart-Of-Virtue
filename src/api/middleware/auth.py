"""Shared session/auth resolution for API routes."""

from flask import current_app, jsonify, request


def _bearer_token():
    """Return the Bearer token from the request's Authorization header.

    Returns the raw token string, or None if the header is missing or not a
    well-formed ``Bearer <token>`` value.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header[7:]


def resolve_session():
    """Resolve the session manager and session for the current request.

    Session-only counterpart to :func:`get_session_and_player`: does NOT
    require (or fetch) a player, so it suits session-scoped routes such as
    logout and validate. Reads the Bearer token from the Authorization header.

    Returns:
        Tuple of (session_manager, session, error) on success, where error is
        None. On failure, session_manager/session are None and error is a
        (response, status_code) tuple the caller should return immediately
        (e.g. ``if error: return error``).
    """
    token = _bearer_token()
    if token is None:
        return (
            None,
            None,
            (jsonify({"success": False, "error": "Missing or invalid Authorization header"}), 401),
        )

    session_manager = current_app.session_manager
    if not session_manager:
        return (
            None,
            None,
            (jsonify({"success": False, "error": "Session manager not initialized"}), 500),
        )

    session = session_manager.get_session(token)
    if not session:
        return (
            None,
            None,
            (jsonify({"success": False, "error": "Session not found or already expired"}), 401),
        )

    return session_manager, session, None


def get_session_and_player():
    """Resolve the session manager, session, and player for the current request.

    Reads the Bearer token from the request's Authorization header.

    Returns:
        Tuple of (session_manager, session, player, error) on success, where
        error is None. On failure, session_manager/session/player are None and
        error is a (response, status_code) tuple the caller should return
        immediately (e.g. ``if error: return error``).
    """
    session_id = _bearer_token()
    if session_id is None:
        return (
            None,
            None,
            None,
            (jsonify({"success": False, "error": "Missing or invalid Authorization header"}), 401),
        )

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
