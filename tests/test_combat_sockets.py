"""Phase 0 smoke tests for the combat SocketIO layer (issue #436).

Establishes the SocketIOTestClient harness the streaming work builds on and
pins the existing ``join_combat`` room contract before it is extended. See
docs/development/combat-streaming-plan.md.
"""

from unittest.mock import MagicMock

import json

import pytest

from src.api.app import create_app
from src.api.config import TestingConfig
from src.api.schemas.combat_beat import (
    ERROR_SESSION_INVALID,
    ERROR_SESSION_MISSING,
)
from src.api.session_cookie import cookie_name


@pytest.fixture
def socket_app(monkeypatch):
    """Return the (app, socketio) pair built by the factory for testing."""
    # The developer .env may enable the rollout flag for manual QA.  This
    # fixture tests the configuration default, so make the input deterministic.
    monkeypatch.delenv("COMBAT_SOCKET_STREAMING", raising=False)
    app, socketio = create_app(TestingConfig)
    app.config["COMBAT_SOCKET_STREAMING"] = False
    return app, socketio


def _fake_session_manager(app):
    """Attach a session store where only ``"good-session"`` resolves.

    Both connect helpers below need it, and they must agree on which id is
    live: the cookie tests assert that a *known* id joins and an unknown one is
    rejected, so a second copy of this that drifted would quietly turn one of
    those into a test of nothing.
    """
    app.session_manager = MagicMock()
    app.session_manager.get_session.side_effect = (
        lambda sid: object() if sid == "good-session" else None
    )


def _connected_client(app, socketio):
    """Attach a fake session_manager and return a connected socket test client.

    ``"good-session"`` resolves to a truthy session; anything else is unknown.
    This avoids building a real universe just to exercise the room handlers.
    """
    _fake_session_manager(app)
    client = socketio.test_client(app)
    assert client.is_connected()
    return client


def _cookie_client(app, socketio, cookie=None):
    """Connect a socket the way a real browser does — credential in the jar.

    The other helper hands the session id to the handler in the event payload.
    That fallback exists for non-browser callers (the QA harnesses), but NO
    browser has used it since issue #493 moved the credential into an HttpOnly
    cookie the page cannot read: the mechanism that actually authenticates
    players is the cookie the *handshake* carries. Passing a Flask test client
    makes ``SocketIOTestClient`` inject that client's cookie jar into the
    handshake environ, which is the same path ``session_id_from_cookie`` reads
    in production.
    """
    _fake_session_manager(app)
    flask_client = app.test_client()
    if cookie is not None:
        flask_client.set_cookie(cookie_name(app), cookie)
    client = socketio.test_client(app, flask_test_client=flask_client)
    assert client.is_connected()
    return client


def _event_names(received):
    return [msg["name"] for msg in received]


def _error_code(received):
    """The ``code`` on the single emitted ``error`` payload."""
    errors = [msg for msg in received if msg["name"] == "error"]
    assert len(errors) == 1, f"expected exactly one error, got {received}"
    return errors[0]["args"][0].get("code")


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
    # The room name embeds the session id, which IS the credential. The ack
    # must confirm the join without handing that value back to page script.
    assert joined["args"][0] == {"joined": True}
    assert "good-session" not in json.dumps(joined)


def test_join_combat_invalid_session_emits_error(socket_app):
    app, socketio = socket_app
    client = _connected_client(app, socketio)

    client.emit("join_combat", {"session_id": "unknown"})
    received = client.get_received()

    assert "error" in _event_names(received)
    assert "joined_combat" not in _event_names(received)
    assert _error_code(received) == ERROR_SESSION_INVALID


def test_join_combat_missing_session_id_emits_error(socket_app):
    app, socketio = socket_app
    client = _connected_client(app, socketio)

    client.emit("join_combat", {})
    received = client.get_received()

    assert "error" in _event_names(received)
    assert _error_code(received) == ERROR_SESSION_MISSING


# -- Cookie authentication (the mechanism real browsers use) ---------------
#
# Every test above authenticates through the payload fallback, so before these
# were written the cookie path -- the only path a browser takes -- had no
# socket coverage at all.

def test_join_combat_authenticates_from_the_handshake_cookie(socket_app):
    app, socketio = socket_app
    client = _cookie_client(app, socketio, cookie="good-session")

    # Deliberately empty, exactly as useCombatSocket emits it: the page holds
    # no readable session id to put here.
    client.emit("join_combat", {})
    received = client.get_received()

    assert "joined_combat" in _event_names(received)
    app.session_manager.get_session.assert_called_once_with("good-session")


def test_cookie_beats_a_payload_session_id(socket_app):
    """A client-supplied session id must never override an authenticated one.

    Reversing this precedence would let script on the page name somebody
    else's combat room.
    """
    app, socketio = socket_app
    client = _cookie_client(app, socketio, cookie="good-session")

    client.emit("join_combat", {"session_id": "somebody-elses-session"})
    received = client.get_received()

    assert "joined_combat" in _event_names(received)
    app.session_manager.get_session.assert_called_once_with("good-session")


def test_handshake_without_a_cookie_reports_a_missing_credential(socket_app):
    """No cookie is NOT a dead session, and the code has to say so.

    This is the condition the client used to answer by logging the player out
    of a live fight: it is produced by a path-scoping regression, a proxy that
    drops the header on /socket.io/, or a cross-origin dev setup -- none of
    which say anything about whether the session is alive. HTTP keeps working
    throughout.
    """
    app, socketio = socket_app
    client = _cookie_client(app, socketio, cookie=None)

    client.emit("join_combat", {})
    received = client.get_received()

    assert "joined_combat" not in _event_names(received)
    assert _error_code(received) == ERROR_SESSION_MISSING
    # Never mistakable for the sign-out condition.
    assert _error_code(received) != ERROR_SESSION_INVALID
    # The session store was never consulted -- there was nothing to look up.
    app.session_manager.get_session.assert_not_called()


def test_cookie_naming_an_unknown_session_reports_invalid(socket_app):
    """A credential arrived and names nothing live -- the player IS signed out.

    This is the only condition that may reach redirectToLogin on the client.
    """
    app, socketio = socket_app
    client = _cookie_client(app, socketio, cookie="expired-session")

    client.emit("join_combat", {})
    received = client.get_received()

    assert "joined_combat" not in _event_names(received)
    assert _error_code(received) == ERROR_SESSION_INVALID
    app.session_manager.get_session.assert_called_once_with("expired-session")


def test_error_payloads_keep_a_human_readable_message(socket_app):
    """The code is the contract; the message is still there for humans.

    Both payloads, not just the reworded one: a future edit that drops the
    message from either leaves logs and QA with a bare code.
    """
    app, socketio = socket_app
    client = _cookie_client(app, socketio, cookie=None)
    client.emit("join_combat", {})
    missing = [m for m in client.get_received() if m["name"] == "error"][0]

    invalid_client = _cookie_client(app, socketio, cookie="expired-session")
    invalid_client.emit("join_combat", {})
    invalid = [m for m in invalid_client.get_received() if m["name"] == "error"][0]

    assert missing["args"][0]["message"]
    assert invalid["args"][0]["message"]
    # ...and no longer says "invalid session" for a condition that is nothing
    # of the sort. The old wording, "Missing or invalid session credentials",
    # contained that substring and is exactly how the two conditions got
    # conflated.
    assert "invalid session" not in missing["args"][0]["message"].lower()


def test_leave_combat_emits_left(socket_app):
    app, socketio = socket_app
    client = _connected_client(app, socketio)
    client.emit("join_combat", {"session_id": "good-session"})
    client.get_received()  # drain the joined_combat event

    client.emit("leave_combat", {"session_id": "good-session"})
    received = client.get_received()

    assert "left_combat" in _event_names(received)


def test_a_payload_session_id_is_refused_outside_a_testing_app(socket_app):
    """The payload fallback is a TESTING affordance, not an auth path.

    Without this gate a caller holding NO cookie could name any session in the
    event payload, be joined to ``combat_<that session>`` and receive every
    ``combat:started``/``combat:beat``/``combat:ended`` payload for a fight
    that is not theirs -- full battle state, player stats and combat log. The
    id has never been authenticated, only believed.

    The rejection uses the MISSING code, not INVALID: from the server's point
    of view no credential arrived at all, and the client must not answer this
    one by signing the player out.
    """
    app, socketio = socket_app
    app.config["TESTING"] = False
    client = _cookie_client(app, socketio, cookie=None)

    client.emit("join_combat", {"session_id": "good-session"})
    received = client.get_received()

    assert "joined_combat" not in _event_names(received)
    assert _error_code(received) == ERROR_SESSION_MISSING
    # The store was never consulted: the payload id never became a candidate.
    app.session_manager.get_session.assert_not_called()


def test_a_non_dict_payload_is_rejected_cleanly(socket_app):
    """``emit("join_combat", "some string")`` is a legal Socket.IO call.

    ``(data or {}).get(...)`` did not coerce a non-dict, so a str payload
    raised AttributeError inside the handler. It must come back as the
    ordinary missing-credential error instead.
    """
    app, socketio = socket_app
    app.config["TESTING"] = False
    client = _cookie_client(app, socketio, cookie=None)

    for payload in ("some string", ["session_id"], 7):
        client.emit("join_combat", payload)
        received = client.get_received()
        assert "joined_combat" not in _event_names(received)
        assert _error_code(received) == ERROR_SESSION_MISSING


def test_a_non_dict_payload_is_rejected_cleanly_in_a_testing_app(socket_app):
    """Same for the branch that DOES read the payload.

    That is where the ``.get`` actually runs, so the coercion has to hold
    there or the AttributeError simply moves behind the gate.
    """
    app, socketio = socket_app
    assert app.config["TESTING"] is True
    client = _cookie_client(app, socketio, cookie=None)

    client.emit("join_combat", "good-session")
    received = client.get_received()

    assert "joined_combat" not in _event_names(received)
    assert _error_code(received) == ERROR_SESSION_MISSING


def test_leave_combat_ignores_a_payload_session_id_outside_a_testing_app(socket_app):
    """The same gate on the other room handler.

    ``leave_room`` is less dangerous than ``join_room``, but both handlers
    must resolve a session the same way or the next reader has to prove which
    one is safe.
    """
    app, socketio = socket_app
    app.config["TESTING"] = False
    client = _cookie_client(app, socketio, cookie=None)

    client.emit("leave_combat", {"session_id": "good-session"})

    assert "left_combat" not in _event_names(client.get_received())
