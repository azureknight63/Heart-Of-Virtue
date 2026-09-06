"""``POST /api/logs/browser`` is throttled, and its cleanup is not per-request.

This is the only route in the API with neither authentication nor a session:
the frontend logger posts to it directly, including via ``sendBeacon`` on
unload, so it cannot be gated. It had no rate-limit tier at all while six
others existed across auth/feedback/npc_chat, and every accepted request also
ran ``cleanup_manager.cleanup()`` — a full listing and stat of the log
directory, whose 100 MB size cap evicts the *oldest* files first. So a flood
bought a directory scan per request and could push genuine logs out of
retention.

Both halves are asserted here: the tier exists and holds, and the sweep runs on
an interval floor rather than per request. The controls matter as much as the
guards — a throttle that refused everything, or a floor that never swept, would
satisfy the negative assertions and break the endpoint.
"""

import ast
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask

from src.api.routes import logs as logs_module
from src.api.routes.logs import logs_bp

_PATH = "/api/logs/browser"
_PAYLOAD = {
    "session_id": "throttle-probe",
    "logs": [{"timestamp": "T", "level": "LOG", "message": "m", "url": "u"}],
}


@pytest.fixture
def client(tmp_path):
    """A one-blueprint app writing into ``tmp_path``.

    The limiter and the cleanup timestamp are module-level and process-wide —
    shared with every other test that touches this route — so both are reset
    around each test rather than inherited.
    """
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(logs_bp, url_prefix="/api/logs")
    limiter = logs_module._browser_log_limiter
    if limiter is not None:
        limiter.clear_all()
    with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
        with app.test_client() as c:
            yield c
    if limiter is not None:
        limiter.clear_all()


@pytest.fixture(autouse=True)
def _reset_cleanup_clock(monkeypatch):
    monkeypatch.setattr(logs_module, "_last_cleanup_at", 0.0)


class TestTheTierExists:
    def test_the_route_has_a_limiter_built_by_the_shared_factory(self):
        """``limiter_from_env`` is what carries the malformed-value guard (a
        garbled or negative ``BROWSER_LOG_RATE_LIMIT_PER_MINUTE`` must never be
        read as "unlimited"), so the tier has to come from it rather than from
        a hand-rolled ``RateLimiter``."""
        from src.api.rate_limiter import RateLimiter

        limiter = logs_module._browser_log_limiter
        assert limiter is None or isinstance(limiter, RateLimiter)
        assert limiter is not None, (
            "BROWSER_LOG_RATE_LIMIT_PER_MINUTE=0 in the environment running "
            "these tests -- logs.py disables the tier entirely at 0."
        )

    def test_the_variable_is_documented(self):
        """An undocumented knob is a knob nobody sets. The repo-wide check in
        tests/test_env_example_completeness.py covers ``src/`` generally; this
        one names the variable, so a rename here fails next to the code that
        renamed it."""
        import pathlib

        env_example = (
            pathlib.Path(__file__).resolve().parent.parent / ".env.example"
        )
        assert "BROWSER_LOG_RATE_LIMIT_PER_MINUTE=" in env_example.read_text(
            encoding="utf-8"
        )


class TestTheThrottleHolds:
    def test_a_flood_is_refused_with_the_shared_429(self, client, monkeypatch):
        limiter = logs_module._browser_log_limiter
        monkeypatch.setattr(limiter, "limit", 3)

        for _ in range(3):
            assert client.post(_PATH, json=_PAYLOAD).status_code == 200

        rv = client.post(_PATH, json=_PAYLOAD)
        assert rv.status_code == 429
        body = rv.get_json()
        # The one 429 shape in this API: a machine token *and* prose, because
        # the frontend renders `message || error` and would otherwise show a
        # player the word "rate_limited".
        assert body["error"] == "rate_limited"
        assert body["message"].strip()

    def test_a_refused_request_writes_nothing(self, client, monkeypatch, tmp_path):
        """The throttle is admission control, not a late check: a refused post
        must not have opened a file or run the retention sweep."""
        limiter = logs_module._browser_log_limiter
        monkeypatch.setattr(limiter, "limit", 1)
        assert client.post(_PATH, json=_PAYLOAD).status_code == 200

        before = sorted(p.name for p in tmp_path.glob("*.log"))
        swept = []
        monkeypatch.setattr(
            logs_module, "cleanup_manager", type("Stub", (), {
                "cleanup": staticmethod(lambda: swept.append(1)),
            })
        )
        assert client.post(_PATH, json=_PAYLOAD).status_code == 429
        assert sorted(p.name for p in tmp_path.glob("*.log")) == before
        assert swept == []

    def test_ordinary_traffic_is_not_refused(self, client):
        """The control. The default ceiling is 60/minute against a frontend
        that flushes on a 5s timer; a handful of posts must sail through."""
        for _ in range(5):
            assert client.post(_PATH, json=_PAYLOAD).status_code == 200


class TestTheSweepRunsOnAnIntervalFloor:
    def test_the_first_post_sweeps(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            logs_module.cleanup_manager, "cleanup", lambda: calls.append(1)
        )
        assert client.post(_PATH, json=_PAYLOAD).status_code == 200
        assert calls == [1]

    def test_the_next_posts_do_not(self, client, monkeypatch):
        """What the finding was about: an unauthenticated caller could drive a
        full-directory scan, and the size-based eviction with it, once per
        request."""
        calls = []
        monkeypatch.setattr(
            logs_module.cleanup_manager, "cleanup", lambda: calls.append(1)
        )
        for _ in range(5):
            assert client.post(_PATH, json=_PAYLOAD).status_code == 200
        assert calls == [1]

    def test_the_floor_lapses(self, client, monkeypatch):
        """The other control: a floor that never lapsed would stop enforcing
        retention altogether, which is worse than scanning too often."""
        calls = []
        monkeypatch.setattr(
            logs_module.cleanup_manager, "cleanup", lambda: calls.append(1)
        )
        assert client.post(_PATH, json=_PAYLOAD).status_code == 200

        base = logs_module.time.monotonic()
        monkeypatch.setattr(
            logs_module.time,
            "monotonic",
            lambda: base + logs_module.CLEANUP_MIN_INTERVAL_SECONDS + 1,
        )
        assert client.post(_PATH, json=_PAYLOAD).status_code == 200
        assert calls == [1, 1]

    def test_a_failing_sweep_does_not_fail_the_write(self, client, monkeypatch):
        monkeypatch.setattr(
            logs_module.cleanup_manager,
            "cleanup",
            lambda: (_ for _ in ()).throw(RuntimeError("cleanup fail")),
        )
        assert client.post(_PATH, json=_PAYLOAD).status_code == 200


def _print_and_warn_sites():
    """Where ``print`` is called in ``logs.py``, and where ``_warn`` is.

    Structural rather than behavioural because the property is structural: the
    claim ":func:`_maybe_cleanup` never raises" is about every line that can
    execute inside its handler, and a test that drives one handler says nothing
    about the next one somebody adds.
    """
    source = Path(logs_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    in_warn = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_warn":
            in_warn = {
                id(c)
                for c in ast.walk(node)
                if isinstance(c, ast.Call)
            }

    prints_outside_warn, warns_in_handlers = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                if isinstance(call.func, ast.Name) and call.func.id == "_warn":
                    warns_in_handlers.append(call.lineno)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "print":
            continue
        if id(node) not in in_warn:
            prints_outside_warn.append(node.lineno)
    return prints_outside_warn, warns_in_handlers


class TestAHandledFailureCannotBecomeAnUnhandledOne:
    """``_maybe_cleanup`` promised "never raises". It could.

    Seven error paths in this module report with ``print``, all of them inside
    an ``except`` block whose whole purpose is to swallow — and ``print`` is
    not exception-free. It raises ``UnicodeEncodeError`` on a cp1252 Windows
    console (this repo has hit that from the terminal engine's ``cprint``) and
    ``ValueError`` on a stdout a WSGI server has closed. Either turned a
    swallowed housekeeping failure into a 500 on the request that happened to
    trigger the sweep.

    The docstring's other claim was wrong in a quieter way: "returns True when
    a sweep ran" described a value the function has never returned. It returns
    True when a sweep was *attempted*, failures included, so that a
    persistently failing sweep is not retried on every request.
    """

    def test_a_failing_sweep_survives_a_failing_print(self, monkeypatch):
        """The regression, with both faults live at once: the sweep raises,
        and so does the diagnostic that reports it."""

        def _explode(*_args, **_kwargs):
            raise UnicodeEncodeError("cp1252", "─", 0, 1, "not encodable")

        monkeypatch.setattr(
            logs_module.cleanup_manager,
            "cleanup",
            lambda: (_ for _ in ()).throw(OSError("disk full")),
        )
        monkeypatch.setattr("builtins.print", _explode)
        assert logs_module._maybe_cleanup() is True

    def test_the_diagnostic_is_reached_at_all(self, monkeypatch):
        """Non-vacuity for the test above, which would pass just as well if
        ``_warn`` were never called."""
        seen = []
        monkeypatch.setattr(
            logs_module.cleanup_manager,
            "cleanup",
            lambda: (_ for _ in ()).throw(OSError("disk full")),
        )
        monkeypatch.setattr(logs_module, "_warn", seen.append)
        assert logs_module._maybe_cleanup() is True
        assert seen and "disk full" in seen[0], seen

    def test_a_successful_sweep_also_returns_true(self, monkeypatch):
        """The control on the corrected docstring: True means attempted, and
        both outcomes are attempts."""
        monkeypatch.setattr(logs_module.cleanup_manager, "cleanup", lambda: None)
        assert logs_module._maybe_cleanup() is True

    def test_print_is_called_in_exactly_one_place(self):
        """The floor on the increment.

        Fixing the seven sites is worth nothing if the eighth is written the
        old way, so what is banned is ``print`` anywhere in this module outside
        ``_warn`` — not the seven instances that happened to be found.
        """
        prints_outside_warn, _ = _print_and_warn_sites()
        assert prints_outside_warn == [], (
            "src/api/routes/logs.py calls print() at line(s) %s outside _warn. "
            "Every diagnostic in this module runs inside an except block, and "
            "print raises (UnicodeEncodeError on a cp1252 console, ValueError "
            "on a closed stdout) — which escapes the handler and fails the "
            "request. Use _warn."
            % ", ".join(str(n) for n in prints_outside_warn)
        )

    def test_the_module_still_reports_its_failures(self):
        """Non-vacuity for the floor above: it is satisfied trivially by a
        module that reports nothing at all."""
        _, warns_in_handlers = _print_and_warn_sites()
        assert len(warns_in_handlers) >= 6, warns_in_handlers


class TestOneRequestCannotWriteMuchMoreThanItSent:
    """The unauthenticated route had a ~500x write amplification.

    ``session_id`` was the one client-supplied field re-emitted on EVERY
    written line rather than once per request, and it was unbounded: ``str()``,
    ``os.path.basename`` and the charset ``re.sub`` are all length-preserving.
    A ~1 MiB session_id with ``MAX_LOGS_PER_REQUEST`` entries wrote ~500 MB,
    with no auth, at the route's own 60/min/IP ceiling, and with the retention
    sweep floored at ``CLEANUP_MIN_INTERVAL_SECONDS`` so growth between sweeps
    was unbounded. ``cleanup_by_size`` then evicts oldest-first, so the flood
    destroys genuine logs on its way through.

    The module's bounds comment claimed to cap "what a single request can
    write". The enumeration behind it was derived from the ENTRY schema, and
    ``session_id`` is a sibling of ``logs``, not a member of an entry -- so it
    was outside the population that comment described. And nothing in
    ``tests/`` referenced any of the four bound constants, so the block was
    coverage theatre in both directions.

    The property asserted here is the one that matters and is not a restatement
    of any constant: **the bytes written must not be a large multiple of the
    bytes sent.** A future field that is emitted per line rather than per
    request fails this without anyone adding it to a list.
    """

    def _written_bytes(self, tmp_path):
        return sum(p.stat().st_size for p in tmp_path.rglob("*") if p.is_file())

    def test_a_huge_repeated_field_does_not_multiply_on_disk(
        self, client, tmp_path
    ):
        big = "s" * 100_000
        body = {
            "session_id": big,
            "logs": [
                {"timestamp": "T", "level": "LOG", "message": "m", "url": "u"}
                for _ in range(logs_module.MAX_LOGS_PER_REQUEST)
            ],
        }
        sent = len(json.dumps(body).encode("utf-8"))
        response = client.post(_PATH, json=body)
        assert response.status_code == 200, response.data

        written = self._written_bytes(tmp_path)
        assert written <= sent * 2, (
            "the request sent %d bytes and the route wrote %d (%.1fx). A "
            "client-supplied field is being emitted once per LINE rather than "
            "once per request." % (sent, written, written / max(sent, 1))
        )

    def test_the_probe_would_have_caught_the_original(self, client, tmp_path):
        """Non-vacuity, stated as arithmetic rather than trusted.

        The old behaviour wrote roughly `len(session_id) * entries` bytes. With
        the numbers this test uses that is far above the bound asserted above,
        so the assertion is one the bug would genuinely have failed.
        """
        would_have_written = 100_000 * logs_module.MAX_LOGS_PER_REQUEST
        body_bytes = 100_000 + 60 * logs_module.MAX_LOGS_PER_REQUEST
        assert would_have_written > body_bytes * 2

    def test_an_ordinary_request_still_writes_its_line(self, client, tmp_path):
        """The control: bounding the field must not stop the route logging.

        A guard that made the endpoint write nothing would satisfy every
        assertion above.
        """
        response = client.post(
            _PATH,
            json={
                "session_id": "session_12345_abc",
                "logs": [
                    {
                        "timestamp": "T",
                        "level": "ERROR",
                        "message": "a real message",
                        "url": "u",
                    }
                ],
            },
        )
        assert response.status_code == 200
        written = [p for p in tmp_path.rglob("*") if p.is_file()]
        assert written, "nothing was logged at all"
        text = written[0].read_text(encoding="utf-8")
        assert "a real message" in text
        assert "session_12345_abc" in text

    def test_a_long_session_id_is_truncated_not_rejected(self, client, tmp_path):
        """It is a correlation id, not a credential -- an over-long one is a
        buggy client, not an attack, and the route should keep working."""
        response = client.post(
            _PATH,
            json={
                "session_id": "x" * 5000,
                "logs": [
                    {"timestamp": "T", "level": "LOG", "message": "kept", "url": "u"}
                ],
            },
        )
        assert response.status_code == 200
        written = [p for p in tmp_path.rglob("*") if p.is_file()]
        assert written
        text = written[0].read_text(encoding="utf-8")
        assert "kept" in text
        assert "x" * (logs_module.MAX_SHORT_FIELD_LENGTH + 1) not in text
