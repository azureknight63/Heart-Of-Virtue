"""The Socket.IO transport pin is a CSP constraint, not a dev-server nicety.

``createCombatSocket`` pins ``transports: ['polling']``. The comment there used
to justify the pin only as a workaround for a spurious Werkzeug dev-server 500
on WebSocket close — a reason a reader could reasonably decide no longer
applies, delete the pin, and see everything keep working locally.

It would not keep working in production. ``src/resources/csp-policy.json`` is
the single source of truth for the app's Content-Security-Policy, and it grants
``connect-src 'self'`` in ``base`` while listing ``ws:``/``wss:`` only under
``dev_additions``. A WebSocket upgrade is checked against ``connect-src``, and
``'self'`` does not cover the ``ws(s)`` scheme, so under the enforcing
production policy the browser blocks the upgrade — a socket allowed to upgrade
works in dev and silently dies in production, taking the combat beat stream
with it.

This test ties the two files together so the constraint cannot be discovered
the hard way: while the production policy permits no WebSocket scheme, the
client must pin a non-WebSocket transport.
"""

import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_POLICY = _ROOT / "src" / "resources" / "csp-policy.json"
_SOCKET_CLIENT = _ROOT / "frontend" / "src" / "api" / "socketClient.js"

#: Source values that would let a browser open a WebSocket.
_WS_SCHEMES = ("ws:", "wss:")


def _policy():
    return json.loads(_POLICY.read_text(encoding="utf-8"))


def _client_transports():
    """The transports array passed to ``io()``, in order."""
    source = _SOCKET_CLIENT.read_text(encoding="utf-8")
    # Comments in this file legitimately mention transports, so match the
    # object property rather than any occurrence of the word.
    match = re.search(r"^\s*transports:\s*\[([^\]]*)\]", source, re.MULTILINE)
    assert match, "no `transports:` option found in socketClient.js"
    return tuple(re.findall(r"'([^']+)'", match.group(1)))


def test_production_csp_permits_no_websocket_scheme():
    """The premise. If this ever changes, revisit the pin below."""
    base_connect = _policy()["base"]["connect-src"]
    assert not [s for s in base_connect if s in _WS_SCHEMES], (
        "base connect-src now allows a WebSocket scheme; the transport pin's "
        "rationale in socketClient.js needs revisiting"
    )
    # ws:/wss: live in dev_additions, which is why an upgrade works locally and
    # would not in production.
    assert [s for s in _policy()["dev_additions"]["connect-src"] if s in _WS_SCHEMES]


def test_socket_client_pins_a_transport_the_production_csp_allows():
    base_connect = _policy()["base"]["connect-src"]
    if [s for s in base_connect if s in _WS_SCHEMES]:
        return  # policy permits WebSockets; the pin is no longer load-bearing
    transports = _client_transports()
    assert transports == ("polling",), (
        "socketClient.js must pin transports: ['polling'] while the production "
        f"CSP allows no ws:/wss: in connect-src (found {transports!r}). "
        "Allowing a WebSocket upgrade would work in dev and be blocked by CSP "
        "in production, silently killing the combat stream."
    )


def test_transport_pin_comment_cites_the_csp():
    """The next reader must find the real reason at the line itself.

    Without this the file can drift back to justifying the pin purely as a
    Werkzeug workaround, which is what made it look deletable.
    """
    source = _SOCKET_CLIENT.read_text(encoding="utf-8")
    pin = source.index("transports:")
    preamble = source[:pin]
    assert "csp-policy.json" in preamble, (
        "the transports pin must be documented as a CSP constraint, citing "
        "src/resources/csp-policy.json"
    )
