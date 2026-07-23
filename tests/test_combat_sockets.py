"""Phase 0 smoke tests for the combat SocketIO layer (issue #436).

Establishes the SocketIOTestClient harness the streaming work builds on and
pins the existing ``join_combat`` room contract before it is extended. See
docs/development/combat-streaming-plan.md.
"""

from unittest.mock import MagicMock

import pytest

from src.api.app import create_app
from src.api.config import TestingConfig


@pytest.fixture
def socket_app():
    """Return the (app, socketio) pair built by the factory for testing."""
    app, socketio = create_app(TestingConfig)
    return app, socketio


def _connected_client(app, socketio):
    """Attach a fake session_manager and return a connected socket test client.

    ``"good-session"`` resolves to a truthy session; anything else is unknown.
    This avoids building a real universe just to exercise the room handlers.
    """
    app.session_manager = MagicMock()
    app.session_manager.get_session.side_effect = (
        lambda sid: object() if sid == "good-session" else None
    )
    client = socketio.test_client(app)
    assert client.is_connected()
    return client


def _event_names(received):
    return [msg["name"] for msg in received]


def test_streaming_flag_defaults_off(socket_app):
    app, _ = socket_app
    assert app.config["COMBAT_SOCKET_STREAMING"] is False


def test_join_combat_valid_session_joins_room(socket_app):
    app, socketio = socket_app
    client = _connected_client(app, socketio)

    client.emit("join_combat", {"session_id": "good-session"})
    received = client.get_received()

    assert "joined_combat" in _event_names(received)
    joined = next(m for m in received if m["name"] == "joined_combat")
    assert joined["args"][0]["room"] == "combat_good-session"


def test_join_combat_invalid_session_emits_error(socket_app):
    app, socketio = socket_app
    client = _connected_client(app, socketio)

    client.emit("join_combat", {"session_id": "unknown"})
    received = client.get_received()

    assert "error" in _event_names(received)
    assert "joined_combat" not in _event_names(received)


def test_join_combat_missing_session_id_emits_error(socket_app):
    app, socketio = socket_app
    client = _connected_client(app, socketio)

    client.emit("join_combat", {})
    received = client.get_received()

    assert "error" in _event_names(received)


def test_leave_combat_emits_left(socket_app):
    app, socketio = socket_app
    client = _connected_client(app, socketio)
    client.emit("join_combat", {"session_id": "good-session"})
    client.get_received()  # drain the joined_combat event

    client.emit("leave_combat", {"session_id": "good-session"})
    received = client.get_received()

    assert "left_combat" in _event_names(received)
