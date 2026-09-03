"""WebSocket event handlers for the Heart of Virtue API."""

import logging

from flask import request, current_app
from flask_socketio import emit, join_room, leave_room

from src.api.session_cookie import session_id_from_cookie

logger = logging.getLogger(__name__)


def register_socket_handlers(socketio):
    """Register all socket event handlers."""

    @socketio.on("connect")
    def handle_connect():
        logger.debug("[SOCKET] Client connected: %s", request.sid)

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.debug("[SOCKET] Client disconnected: %s", request.sid)

    def _session_id(data):
        """The session this socket event belongs to.

        The client used to put the session id in the event payload, because it
        held one in ``localStorage``. Since issue #493 it does not: the
        credential is an ``HttpOnly`` cookie the page cannot read. Flask-SocketIO
        runs handlers inside a request context built from the handshake, so the
        cookie the browser sent with it is available here and the server
        resolves the session itself.

        The payload form remains a fallback for the non-browser callers that
        hold an explicit session id (the QA harnesses, and any Socket.IO client
        outside a cookie jar) — the same fallback, and the same reasoning, as
        ``middleware.auth.session_token``.

        Precedence matches that helper's, cookie first, and for the same reason:
        a client-supplied session id has never been authenticated, only
        believed, so a page that carries a real cookie must not be able to name
        somebody else's room instead. Reversing these two would let script on
        the page join another session's combat stream.
        """
        return session_id_from_cookie() or (data or {}).get("session_id")

    @socketio.on("join_combat")
    def on_join(data):
        """Join a combat room based on session ID."""
        session_id = _session_id(data)
        if not session_id:
            return emit("error", {"message": "Missing or invalid session credentials"})

        session_manager = current_app.session_manager
        session = session_manager.get_session(session_id)

        if not session:
            return emit("error", {"message": "Invalid session"})

        room = f"combat_{session_id}"
        join_room(room)
        # The room name embeds the session id, which is the credential itself.
        # Neither the log nor the ack may carry it: the whole point of the
        # HttpOnly cookie is that page script cannot obtain this value, and
        # echoing it back in the ack would hand it straight over.
        logger.debug("[SOCKET] Client %s joined its combat room", request.sid)
        emit("joined_combat", {"joined": True})

    @socketio.on("leave_combat")
    def on_leave(data):
        """Leave a combat room."""
        session_id = _session_id(data)
        if session_id:
            room = f"combat_{session_id}"
            leave_room(room)
            # See on_join: the room name is the credential, so it is neither
            # logged nor returned to the client.
            logger.debug("[SOCKET] Client %s left its combat room", request.sid)
            emit("left_combat", {"left": True})

    @socketio.on("ping_combat")
    def on_ping(data):
        """Simple ping-pong for testing."""
        emit("pong_combat", {"message": "ready"})
