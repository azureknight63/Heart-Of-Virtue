"""WebSocket event handlers for the Heart of Virtue API."""

import logging

from flask import request, current_app
from flask_socketio import emit, join_room, leave_room

logger = logging.getLogger(__name__)


def register_socket_handlers(socketio):
    """Register all socket event handlers."""

    @socketio.on("connect")
    def handle_connect():
        logger.debug("[SOCKET] Client connected: %s", request.sid)

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.debug("[SOCKET] Client disconnected: %s", request.sid)

    @socketio.on("join_combat")
    def on_join(data):
        """Join a combat room based on session ID."""
        session_id = (data or {}).get("session_id")
        if not session_id:
            return emit("error", {"message": "Missing session_id"})

        session_manager = current_app.session_manager
        session = session_manager.get_session(session_id)

        if not session:
            return emit("error", {"message": "Invalid session"})

        room = f"combat_{session_id}"
        join_room(room)
        logger.debug("[SOCKET] Client %s joined room %s", request.sid, room)
        emit("joined_combat", {"room": room})

    @socketio.on("leave_combat")
    def on_leave(data):
        """Leave a combat room."""
        session_id = (data or {}).get("session_id")
        if session_id:
            room = f"combat_{session_id}"
            leave_room(room)
            logger.debug("[SOCKET] Client %s left room %s", request.sid, room)
            emit("left_combat", {"room": room})

    @socketio.on("ping_combat")
    def on_ping(data):
        """Simple ping-pong for testing."""
        emit("pong_combat", {"message": "ready"})
