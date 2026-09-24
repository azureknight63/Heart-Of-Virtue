"""The Socket.IO transport pin, held to the deployment that was VERIFIED.

``createCombatSocket`` pins ``transports: ['polling']``. Three rationales for
that pin have now been wrong, so this file records what is checked, what is
merely asserted, and which claim was retired when.

Wrong reason #1 --- CSP. CSP Level 3 relaxed ``connect-src 'self'`` to match the
``ws:``/``wss:`` variants of the page's own origin, and both engines implement
it (Blink's ``CSPSourceMatchesAsSelf`` in ``csp_source.cc``; Gecko's
``permitsScheme`` special case in ``nsCSPUtils.cpp``). ``'self'`` would permit a
same-origin upgrade.

Wrong reason #2 --- "the deployment cannot serve an upgrade at all". It can, and
it advertises that it can. engineio's threading driver sets
``'websocket': SimpleWebSocketWSGI`` (``async_drivers/threading.py``) and
``BaseServer._upgrades()`` returns ``['websocket']`` whenever that entry is
non-None, consulting nothing about the WSGI server.

Wrong reason #3, retired 2026-09-19 --- "a parked upgrade is SIGKILLed". That
reasoning ran: engineio parks the WSGI request thread for the life of the
connection, the Procfile runs a single SYNC worker, so the arbiter kills it at
the 30s default and every in-memory session dies. The premise was read off the
Procfile and never verified. The real unit (mirrored at
``deploy/heart-of-virtue.service``, read from the server) runs
``--worker-class eventlet -w 1 --timeout 120``: requests are concurrent
greenlets, a parked connection holds a greenlet rather than the worker, and on
a non-sync worker ``--timeout`` is a liveness heartbeat, not a per-request
deadline.

So the pin is no longer load-bearing for the reason it carried. It STANDS
(#653, maintainer decision "pin now, migrate later") for three reasons that do
hold on the verified process model:

(a) the reverse proxy's ``Upgrade``/``Connection`` handling is unverified ---
    its config has never been read (``docs/development/deployment.md``);
(b) ``async_mode="threading"`` (``src/api/app.py``) serving WebSockets under
    an eventlet worker is an unsupported combination;
(c) the worker class is due to migrate off eventlet, which gunicorn 26
    removed --- ``requirements-api.txt`` holds gunicorn below 26 until then.

These tests hold the pin and its rationale to that. They also hold the repo to
the unit: the worker class production runs must be a declared dependency,
because it was installed on the server by hand and pinned nowhere for the
whole life of this file (and ``tests/test_npc_chat_turn_budget.py`` holds the
gunicorn range to a release that still ships that worker).
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SOCKET_CLIENT = _ROOT / "frontend" / "src" / "api" / "socketClient.js"
_APP = _ROOT / "src" / "api" / "app.py"
_REQUIREMENTS = _ROOT / "requirements-api.txt"
_UNIT = _ROOT / "deploy" / "heart-of-virtue.service"

#: Server packages that give Flask-SocketIO a real WebSocket transport.
_ASYNC_WORKERS = ("eventlet", "gevent")

#: The issue that owns re-deriving the pin. Named in the client comment too, so
#: a reader who finds the retired rationale has somewhere to go.
_REVISIT_ISSUE = "#653"


def _client_source():
    return _SOCKET_CLIENT.read_text(encoding="utf-8")


def _client_transports():
    """The transports array passed to ``io()``, in order."""
    match = re.search(r"^\s*transports:\s*\[([^\]]*)\]", _client_source(), re.MULTILINE)
    assert match, "no `transports:` option found in socketClient.js"
    return tuple(re.findall(r"'([^']+)'", match.group(1)))


def _declared_requirements():
    """Requirement names from requirements-api.txt, lowercased."""
    names = []
    for line in _REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        # maxsplit by keyword: passing it positionally to re.split is
        # deprecated in 3.13 and slated for removal.
        names.append(
            re.split(r"[<>=!\[;]", line, maxsplit=1)[0].strip().lower()
        )
    return names


def _unit_worker_class():
    """The worker class the production unit runs, or ``sync`` if unflagged."""
    unit = _UNIT.read_text(encoding="utf-8")
    assert "gunicorn" in unit, f"{_UNIT.name} no longer runs gunicorn"
    match = re.search(r"--worker-class[ =](\S+)", unit)
    return match.group(1) if match else "sync"


def test_the_worker_class_production_runs_is_a_declared_dependency():
    """The premise these tests rest on, and the one that was never checked.

    Production has run an eventlet worker all along while no requirements file
    named it -- so the repo asserted a sync deployment, the client pinned a
    transport for a sync deployment, and one venv rebuild would have stopped
    gunicorn booting at all.
    """
    worker_class = _unit_worker_class()
    declared = _declared_requirements()

    assert worker_class, "read no worker class off the unit"
    if worker_class in _ASYNC_WORKERS:
        assert worker_class in declared, (
            f"the production unit runs the {worker_class} worker, which "
            "requirements-api.txt does not install"
        )


def test_the_client_does_not_claim_a_process_model_the_unit_contradicts():
    """The retired rationale must not sit in the file as if it still held.

    Two rationales before it were 'confidently wrong' in the same place, which
    is why this is a guard rather than a comment asking nicely.
    """
    source = _client_source()
    worker_class = _unit_worker_class()

    assert "deploy/heart-of-virtue.service" in source, (
        "socketClient.js no longer cites the unit its reasoning depends on"
    )
    assert _REVISIT_ISSUE in source, (
        f"socketClient.js no longer points at {_REVISIT_ISSUE}, which owns "
        "re-deriving the pin"
    )
    # The worker class is read off the unit, not written here: a comment
    # rewritten back to the sync-worker story -- or left behind when the unit
    # changes again -- stops naming what production runs, and fails.
    assert worker_class in source, (
        f"the production unit runs the {worker_class} worker, and "
        "socketClient.js's rationale does not mention it. That rationale has "
        "been confidently wrong three times; it names the process model it "
        "depends on or it is wrong again."
    )


def test_the_transport_pin_stands_until_its_rationale_is_re_derived():
    """Behaviour is unchanged on purpose: the old reason died, not the decision.

    The pin now rests on (a) an unverified proxy, (b) ``async_mode="threading"``
    under an eventlet worker, and (c) the pending move off eventlet (#653).
    Until all three are settled, the client keeps polling and this says so.
    """
    assert _client_transports() == ("polling",), (
        "socketClient.js changed transports while #653's reasons still hold: "
        "the proxy's Upgrade handling is unverified, async_mode=threading "
        "under an eventlet worker is unsupported, and the worker is due to "
        "migrate. Settle those first, then change this test."
    )
    assert 'async_mode="threading"' in _APP.read_text(encoding="utf-8"), (
        "src/api/app.py no longer pins async_mode=threading; under an "
        "eventlet worker that is exactly the question #653 asks, so re-derive "
        "the pin rather than letting the two drift"
    )
