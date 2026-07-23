"""Tests for reverse-proxy client-IP handling (GitHub issue #409).

The login rate limiter keys on ``request.remote_addr``. Behind a reverse proxy
that is the proxy's address for every request, collapsing the per-IP dimension.
``_apply_proxy_fix`` installs Werkzeug's ProxyFix when ``TRUSTED_PROXY_COUNT``
is configured, so ``remote_addr`` reflects the real client again — but it is
**off by default** so an untrusted client can't spoof ``X-Forwarded-For``.
"""

import pytest
from flask import Flask, request

from src.api.app import _apply_proxy_fix


def _echo_app():
    app = Flask(__name__)

    @app.route("/whoami")
    def whoami():
        return request.remote_addr or "unknown"

    return app


# Direct peer the proxy connects from; the header claims a different client.
DIRECT_PEER = {"REMOTE_ADDR": "10.0.0.5"}
SPOOFED = {"X-Forwarded-For": "203.0.113.9"}


class TestApplyProxyFix:
    def test_disabled_by_default_ignores_forwarded_for(self, monkeypatch):
        monkeypatch.delenv("TRUSTED_PROXY_COUNT", raising=False)
        app = _echo_app()

        installed = _apply_proxy_fix(app)

        assert installed is False
        with app.test_client() as c:
            rv = c.get("/whoami", environ_base=DIRECT_PEER, headers=SPOOFED)
        # remote_addr must stay the direct peer — the forwarded header is ignored.
        assert rv.get_data(as_text=True) == "10.0.0.5"

    def test_zero_count_is_treated_as_disabled(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "0")
        app = _echo_app()
        assert _apply_proxy_fix(app) is False

    def test_invalid_count_is_treated_as_disabled(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "not-a-number")
        app = _echo_app()
        assert _apply_proxy_fix(app) is False
        with app.test_client() as c:
            rv = c.get("/whoami", environ_base=DIRECT_PEER, headers=SPOOFED)
        assert rv.get_data(as_text=True) == "10.0.0.5"

    def test_configured_trusts_forwarded_for(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
        app = _echo_app()

        installed = _apply_proxy_fix(app)

        assert installed is True
        with app.test_client() as c:
            rv = c.get("/whoami", environ_base=DIRECT_PEER, headers=SPOOFED)
        # With one trusted hop, remote_addr becomes the forwarded client IP.
        assert rv.get_data(as_text=True) == "203.0.113.9"

    def test_config_value_takes_precedence_over_env(self, monkeypatch):
        # Explicit Flask config wins even if the env var is unset.
        monkeypatch.delenv("TRUSTED_PROXY_COUNT", raising=False)
        app = _echo_app()
        app.config["TRUSTED_PROXY_COUNT"] = 1
        assert _apply_proxy_fix(app) is True
        with app.test_client() as c:
            rv = c.get("/whoami", environ_base=DIRECT_PEER, headers=SPOOFED)
        assert rv.get_data(as_text=True) == "203.0.113.9"


class TestLoginRateLimitKeyHonorsRemoteAddr:
    """The rate-limit key ties to request.remote_addr, so ProxyFix (once
    configured) automatically re-buckets logins by the real client."""

    def test_key_uses_remote_addr(self):
        from src.api.routes.auth import _login_rate_limit_key

        app = Flask(__name__)
        with app.test_request_context(
            "/auth/login", environ_base={"REMOTE_ADDR": "198.51.100.7"}
        ):
            key = _login_rate_limit_key("Jean")
        assert key == "jean:198.51.100.7"


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
