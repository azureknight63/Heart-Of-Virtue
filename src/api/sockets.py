"""WebSocket event handlers for the Heart of Virtue API."""

import logging

from flask import request, current_app
from flask_socketio import emit, join_room, leave_room

from src.api.schemas.combat_beat import (
    ERROR_EVENT,
    ERROR_SESSION_INVALID,
    ERROR_SESSION_MISSING,
)
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

    def _payload_session_id_allowed():
        """Whether a caller may name its own session in the event payload.

        Only in a ``TESTING`` app. A payload session id has never been
        authenticated, only believed: outside a test app a caller carrying NO
        cookie could name any session, be joined to ``combat_<that session>``
        and receive every ``combat:started``/``combat:beat``/``combat:ended``
        payload for a fight that is not theirs — full battle state, player
        stats and combat log. Same precedent, and the same reason, as
        ``/api/test/session`` and ``debug_bp``, which are likewise registered
        only when ``app.config["TESTING"]``.

        No real client needs it: since issue #493 the browser sends ``{}`` and
        authenticates off the handshake cookie, and nothing in ``tools/``
        (bug-hunt harness, Inquisitor) speaks Socket.IO at all — they hold a
        session id for the HTTP ``Authorization`` header only.

        Returns False outside an app context: an absent context is not a
        licence to trust the payload.
        """
        try:
            return bool(current_app.config.get("TESTING"))
        except RuntimeError:  # working outside of application context
            return False

    def _session_id(data):
        """The session this socket event belongs to.

        The client used to put the session id in the event payload, because it
        held one in ``localStorage``. Since issue #493 it does not: the
        credential is an ``HttpOnly`` cookie the page cannot read. Flask-SocketIO
        runs handlers inside a request context built from the handshake, so the
        cookie the browser sent with it is available here and the server
        resolves the session itself. That is the only way a real client
        authenticates a socket.

        The payload form survives as a test-only affordance, gated by
        :func:`_payload_session_id_allowed` — see there for why it must never
        be reachable in production.

        Cookie first, and for the same reason as
        ``middleware.auth.session_token``: a page that carries a real cookie
        must not be able to name somebody else's room instead. Reversing these
        two would let script on the page join another session's combat stream.
        """
        from_cookie = session_id_from_cookie()
        if from_cookie:
            return from_cookie
        if not _payload_session_id_allowed():
            return None
        # Coerce rather than trust: ``emit("join_combat", "some string")`` is a
        # legal Socket.IO call, and ``.get`` on a str raises inside the handler.
        payload = data if isinstance(data, dict) else {}
        return payload.get("session_id")

    @socketio.on("join_combat")
    def on_join(data):
        """Join a combat room based on session ID."""
        session_id = _session_id(data)
        if not session_id:
            # Nothing to authenticate: the handshake carried no cookie and the
            # caller named no session. Distinct from a dead session, and the
            # ``code`` is what says so — see ERROR_SESSION_MISSING for why the
            # client must not treat this as a sign-out.
            return emit(ERROR_EVENT, {
                "code": ERROR_SESSION_MISSING,
                "message": "No session credential on the socket handshake",
            })

        session_manager = current_app.session_manager
        session = session_manager.get_session(session_id)

        if not session:
            return emit(ERROR_EVENT, {
                "code": ERROR_SESSION_INVALID,
                "message": "Invalid session",
            })

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
