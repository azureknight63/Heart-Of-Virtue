"""Shared session/auth resolution for API routes."""

from typing import Any, Optional, Tuple

from flask import Response, current_app, jsonify, request

#: The error half of the ``(value, error)`` contract these helpers return: the
#: exact ``(response, status)`` pair Flask accepts from a view, so a caller
#: forwards it with a bare ``return error``. Named because it appears in every
#: signature below and, unannotated, the contract that every call site in
#: ``src/api/routes/`` depends on existed only in prose.
RouteError = Tuple[Response, int]


def _bearer_token() -> Optional[str]:
    """Return the Bearer token from the request's Authorization header.

    Returns the raw token string, or None if the header is missing or not a
    well-formed ``Bearer <token>`` value.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header[7:]


def resolve_session() -> Tuple[Optional[Any], Optional[Any], Optional[RouteError]]:
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


def get_session_and_player() -> Tuple[
    Optional[Any], Optional[Any], Optional[Any], Optional[RouteError]
]:
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


def require_game_service() -> Tuple[Optional[Any], Optional[RouteError]]:
    """Resolve ``current_app.game_service`` for the current request.

    Companion to :func:`get_session_and_player`, and returns the same
    ``(value, error)`` shape so a route reads the two the same way::

        game_service, gs_error = require_game_service()
        if gs_error:
            return gs_error

    ``gs_error``, not ``error``: the overwhelming majority of routes call this
    in a scope that already holds an ``error`` from
    :func:`get_session_and_player`, and binding both to the same name discards
    the first one's 401/404 in favour of this one's 500. Every call site in
    ``src/api/routes/`` spells it this way.

    ``create_app`` always assigns ``app.game_service``, but
    :func:`~src.api.app._init_universe` falls back to a universe-less service
    when startup fails, and several tests substitute a falsy one — so routes
    check. That check was copy-pasted, verbatim and including the error
    string, into fifteen handlers across ``world.py`` and ``player.py``; a
    fix or a rewording had fifteen places to reach, which is fourteen chances
    to miss one.

    Returns:
        Tuple of (game_service, None) on success, or (None, (response, 500)).
    """
    game_service = getattr(current_app, "game_service", None)
    if not game_service:
        return (
            None,
            (jsonify({"success": False, "error": "Game service not initialized"}), 500),
        )
    return game_service, None
