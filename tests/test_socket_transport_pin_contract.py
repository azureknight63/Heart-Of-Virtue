"""The Socket.IO transport pin is a DEPLOYMENT constraint, not a dev nicety.

``createCombatSocket`` pins ``transports: ['polling']``. Two earlier rationales
for that pin were confidently wrong, so this file records what is actually
checked and what is merely asserted.

Wrong reason #1 --- CSP. CSP Level 3 relaxed ``connect-src 'self'`` to match the
``ws:``/``wss:`` variants of the page's own origin, and both engines implement
it (Blink's ``CSPSourceMatchesAsSelf`` in ``csp_source.cc``; Gecko's
``permitsScheme`` special case in ``nsCSPUtils.cpp``). ``'self'`` would permit a
same-origin upgrade. The contrary intuition comes from Chromium's
*network-service* CSP implementation, which still has pre-CSP3 behaviour and is
not the code path a document's ``connect-src`` check takes.

Wrong reason #2 --- "the deployment cannot serve an upgrade at all". It can, and
it advertises that it can. engineio's threading driver sets
``'websocket': SimpleWebSocketWSGI`` (``async_drivers/threading.py``) and
``BaseServer._upgrades()`` returns ``['websocket']`` whenever that entry is
non-None, consulting nothing about the WSGI server; simple_websocket even has a
dedicated ``mode == 'gunicorn'`` hijack path that engineio's
``_websocket_wsgi.py`` drives with ``raise StopIteration()``. The handshake
advertises a websocket upgrade in production today.

The actual reason is what happens *after* a successful upgrade: engineio parks
the WSGI request thread in ``while True: websocket_wait()`` (``socket.py``) for
the life of the connection. The Procfile runs ``gunicorn -w 1``; a sync worker
serves one connection at a time and notifies the arbiter only at the top of its
accept loop, so a parked worker is SIGKILLed at the default 30s timeout --- and
``SessionManager`` holds sessions in memory, so every connected player is
force-logged-out. ``socketClient.js`` carries the full derivation.

What this file can and cannot check: ``gunicorn`` appears in no requirements
file in this repo, and CLAUDE.md says production hosting is configured outside
it, so the process model above is asserted from the Procfile rather than
verified. These tests therefore assert only the two facts that do live in this
repo --- no async worker is declared, and ``async_mode="threading"`` is still
pinned --- and tie the client's transport pin to them.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SOCKET_CLIENT = _ROOT / "frontend" / "src" / "api" / "socketClient.js"
_APP = _ROOT / "src" / "api" / "app.py"
_REQUIREMENTS = _ROOT / "requirements-api.txt"

#: Server packages that would give Flask-SocketIO a real WebSocket transport.
_ASYNC_WORKERS = ("eventlet", "gevent")


def _client_transports():
    """The transports array passed to ``io()``, in order."""
    source = _SOCKET_CLIENT.read_text(encoding="utf-8")
    # Comments in this file legitimately mention transports, so match the
    # object property rather than any occurrence of the word.
    match = re.search(r"^\s*transports:\s*\[([^\]]*)\]", source, re.MULTILINE)
    assert match, "no `transports:` option found in socketClient.js"
    return tuple(re.findall(r"'([^']+)'", match.group(1)))


def _declared_requirements():
    """Requirement names from requirements-api.txt, lowercased."""
    names = []
    for line in _REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        names.append(re.split(r"[<>=!\[;]", line, 1)[0].strip().lower())
    return names


def test_the_deployment_carries_no_async_websocket_worker():
    """The premise. If this ever changes, revisit the pin below."""
    declared = _declared_requirements()
    assert not [n for n in declared if n in _ASYNC_WORKERS], (
        "requirements-api.txt now declares an async worker; Flask-SocketIO "
        "could serve a real WebSocket and the transport pin in "
        "socketClient.js needs revisiting"
    )
    assert 'async_mode="threading"' in _APP.read_text(encoding="utf-8"), (
        "src/api/app.py no longer pins async_mode=threading; the transport "
        "pin's rationale in socketClient.js needs revisiting"
    )


def test_socket_client_pins_a_transport_the_deployment_can_serve():
    declared = _declared_requirements()
    if [n for n in declared if n in _ASYNC_WORKERS]:
        return  # an async worker is present; the pin is no longer load-bearing
    transports = _client_transports()
    assert transports == ("polling",), (
        "socketClient.js must pin transports: ['polling'] while the API runs "
        f"async_mode=threading with no async worker (found {transports!r}). "
        "The upgrade itself would succeed --- engineio advertises websocket "
        "under the threading driver. The problem is that a completed upgrade "
        "parks the WSGI request thread for the life of the connection, which "
        "a single sync worker cannot survive. See socketClient.js."
    )
