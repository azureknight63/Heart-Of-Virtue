"""Coverage for src/api/sockets.py — WebSocket event handlers registered on
a Flask-SocketIO instance. register_socket_handlers() registers handlers via
`@socketio.on(...)` decorators, so tests capture the decorated functions from
a mock socketio object and invoke them directly with patched flask `request`/
`current_app` and patched `emit`/`join_room`/`leave_room` (the exact names
src/api/sockets.py imports them under).
"""

from unittest.mock import MagicMock, patch

from src.api.sockets import register_socket_handlers, authenticated_only


def _register_and_capture_handlers():
    """Register handlers on a mock socketio and return {event_name: fn}."""
    handlers = {}

    def fake_on(event_name):
        def decorator(fn):
            handlers[event_name] = fn
            return fn

        return decorator

    socketio = MagicMock()
    socketio.on = fake_on
    register_socket_handlers(socketio)
    return handlers


def test_authenticated_only_wraps_and_calls_through():
    calls = []

    @authenticated_only
    def inner(*args, **kwargs):
        calls.append((args, kwargs))
        return "result"

    assert inner(1, 2, foo="bar") == "result"
    assert calls == [((1, 2), {"foo": "bar"})]


def test_handle_connect_and_disconnect_print_client_sid(capsys):
    handlers = _register_and_capture_handlers()
    fake_request = MagicMock()
    fake_request.sid = "sid-123"

    with patch("src.api.sockets.request", fake_request):
        handlers["connect"]()
        handlers["disconnect"]()

    out = capsys.readouterr().out
    assert "Client connected: sid-123" in out
    assert "Client disconnected: sid-123" in out


def test_on_join_missing_session_id_emits_error():
    handlers = _register_and_capture_handlers()
    with patch("src.api.sockets.emit") as mock_emit:
        handlers["join_combat"]({})
    mock_emit.assert_called_once_with("error", {"message": "Missing session_id"})


def test_on_join_invalid_session_emits_error():
    handlers = _register_and_capture_handlers()
    fake_app = MagicMock()
    fake_app.session_manager.get_session.return_value = None

    with patch("src.api.sockets.current_app", fake_app), \
         patch("src.api.sockets.emit") as mock_emit:
        handlers["join_combat"]({"session_id": "abc"})

    mock_emit.assert_called_once_with("error", {"message": "Invalid session"})


def test_on_join_valid_session_joins_room_and_emits(capsys):
    handlers = _register_and_capture_handlers()
    fake_app = MagicMock()
    fake_app.session_manager.get_session.return_value = MagicMock()
    fake_request = MagicMock()
    fake_request.sid = "sid-xyz"

    with patch("src.api.sockets.current_app", fake_app), \
         patch("src.api.sockets.request", fake_request), \
         patch("src.api.sockets.join_room") as mock_join_room, \
         patch("src.api.sockets.emit") as mock_emit:
        handlers["join_combat"]({"session_id": "abc"})

    mock_join_room.assert_called_once_with("combat_abc")
    mock_emit.assert_called_once_with("joined_combat", {"room": "combat_abc"})
    assert "joined room combat_abc" in capsys.readouterr().out


def test_on_leave_with_session_id_leaves_room_and_emits(capsys):
    handlers = _register_and_capture_handlers()
    fake_request = MagicMock()
    fake_request.sid = "sid-xyz"

    with patch("src.api.sockets.request", fake_request), \
         patch("src.api.sockets.leave_room") as mock_leave_room, \
         patch("src.api.sockets.emit") as mock_emit:
        handlers["leave_combat"]({"session_id": "abc"})

    mock_leave_room.assert_called_once_with("combat_abc")
    mock_emit.assert_called_once_with("left_combat", {"room": "combat_abc"})
    assert "left room combat_abc" in capsys.readouterr().out


def test_on_leave_without_session_id_is_a_noop():
    handlers = _register_and_capture_handlers()
    with patch("src.api.sockets.leave_room") as mock_leave_room, \
         patch("src.api.sockets.emit") as mock_emit:
        result = handlers["leave_combat"]({})

    mock_leave_room.assert_not_called()
    mock_emit.assert_not_called()
    assert result is None


def test_on_ping_emits_pong():
    handlers = _register_and_capture_handlers()
    with patch("src.api.sockets.emit") as mock_emit:
        handlers["ping_combat"]({})
    mock_emit.assert_called_once_with("pong_combat", {"message": "ready"})
