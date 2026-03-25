"""WebSocket event handlers for the Heart of Virtue API."""

import functools
from flask import request, current_app
from flask_socketio import emit, join_room, leave_room, disconnect


def authenticated_only(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        # In a real app, we'd verify the token here
        # For now, we'll check if the session exists in the session manager
        return f(*args, **kwargs)

    return wrapped


def register_socket_handlers(socketio):
    """Register all socket event handlers."""

    @socketio.on("connect")
    def handle_connect():
        print(f"[SOCKET] Client connected: {request.sid}")

    @socketio.on("disconnect")
    def handle_disconnect():
        print(f"[SOCKET] Client disconnected: {request.sid}")

    @socketio.on("join_combat")
    def on_join(data):
        """Join a combat room based on session ID."""
        session_id = data.get("session_id")
        if not session_id:
            return emit("error", {"message": "Missing session_id"})

        session_manager = current_app.session_manager
        session = session_manager.get_session(session_id)

        if not session:
            return emit("error", {"message": "Invalid session"})

        room = f"combat_{session_id}"
        join_room(room)
        print(f"[SOCKET] Client {request.sid} joined room {room}")
        emit("joined_combat", {"room": room})

    @socketio.on("leave_combat")
    def on_leave(data):
        """Leave a combat room."""
        session_id = data.get("session_id")
        if session_id:
            room = f"combat_{session_id}"
            leave_room(room)
            print(f"[SOCKET] Client {request.sid} left room {room}")
            emit("left_combat", {"room": room})

    @socketio.on("ping_combat")
    def on_ping(data):
        """Simple ping-pong for testing."""
        emit("pong_combat", {"message": "ready"})
