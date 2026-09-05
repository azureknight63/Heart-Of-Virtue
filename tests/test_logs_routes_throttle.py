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
