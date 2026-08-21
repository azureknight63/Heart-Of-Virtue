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

    @pytest.mark.parametrize("raw", ["0", "-1", ""])
    def test_non_positive_count_is_treated_as_disabled(self, monkeypatch, raw):
        monkeypatch.setenv("TRUSTED_PROXY_COUNT", raw)
        app = _echo_app()

        assert _apply_proxy_fix(app) is False

        # The return value is a report; the security property is that the WSGI
        # stack was left unwrapped and the forwarded header stays ignored.
        # NB: identity on `app.wsgi_app` cannot be used here -- Flask defines it
        # as a method, so every attribute access yields a fresh bound-method
        # object and `app.wsgi_app is app.wsgi_app` is already False.
        from werkzeug.middleware.proxy_fix import ProxyFix

        assert not isinstance(app.wsgi_app, ProxyFix)
        with app.test_client() as c:
            rv = c.get("/whoami", environ_base=DIRECT_PEER, headers=SPOOFED)
        assert rv.get_data(as_text=True) == "10.0.0.5"

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

    def test_one_trusted_hop_reads_only_the_last_forwarded_entry(self, monkeypatch):
        """The count is a *trust depth*, not "believe the whole chain".

        With one trusted hop and a client-supplied chain, only the entry the
        trusted proxy appended may be believed. Trusting the leftmost entry
        would hand the login rate-limit key straight back to the attacker,
        who controls it -- which is the entire point of issue #409.
        """
        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
        app = _echo_app()
        assert _apply_proxy_fix(app) is True

        with app.test_client() as c:
            rv = c.get(
                "/whoami",
                environ_base=DIRECT_PEER,
                # "198.51.100.1" is attacker-supplied; "203.0.113.9" is what
                # the one trusted proxy actually observed.
                headers={"X-Forwarded-For": "198.51.100.1, 203.0.113.9"},
            )
        assert rv.get_data(as_text=True) == "203.0.113.9"

    def test_two_trusted_hops_step_one_further_left(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "2")
        app = _echo_app()
        assert _apply_proxy_fix(app) is True

        with app.test_client() as c:
            rv = c.get(
                "/whoami",
                environ_base=DIRECT_PEER,
                headers={"X-Forwarded-For": "198.51.100.1, 203.0.113.9, 10.0.0.6"},
            )
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

    def test_config_zero_overrides_a_permissive_env_var(self, monkeypatch):
        """Config wins in *both* directions -- an operator who sets 0 in code
        must not be silently overridden by a stray environment variable."""
        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "3")
        app = _echo_app()
        app.config["TRUSTED_PROXY_COUNT"] = 0
        assert _apply_proxy_fix(app) is False
        with app.test_client() as c:
            rv = c.get("/whoami", environ_base=DIRECT_PEER, headers=SPOOFED)
        assert rv.get_data(as_text=True) == "10.0.0.5"

    def test_create_app_applies_the_setting(self, monkeypatch):
        """The wiring, not just the helper: create_app must call it.

        Without this, _apply_proxy_fix could be perfect and never invoked.
        """
        from unittest.mock import MagicMock, patch

        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")

        class _Cfg:
            TESTING = True
            DEBUG = False
            SECRET_KEY = "x"
            CORS_ORIGINS = []
            SQLALCHEMY_TRACK_MODIFICATIONS = False

        _Cfg.__name__ = "_ProxyProbeConfig"  # not dev/test => skip universe

        with (
            patch("src.api.app.universe_module"),
            patch("src.api.app.SessionManager", return_value=MagicMock()),
            patch("src.api.app.GameService", return_value=MagicMock()),
        ):
            from src.api.app import create_app

            app, _ = create_app(_Cfg)

        from werkzeug.middleware.proxy_fix import ProxyFix

        # ProxyFix is NOT the outermost layer: create_app installs it, then
        # Flask-SocketIO wraps the stack again, so app.wsgi_app is a
        # _SocketIOMiddleware whose inner app is the ProxyFix. Asserting on the
        # top of the stack alone would fail even though the wiring is correct.
        layers = []
        node = app.wsgi_app
        for _ in range(6):
            layers.append(node)
            nxt = getattr(node, "wsgi_app", None) or getattr(node, "app", None)
            if nxt is None or nxt is node:
                break
            node = nxt

        assert any(isinstance(layer, ProxyFix) for layer in layers), [
            type(layer).__name__ for layer in layers
        ]


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
        # Username is case-folded so "Jean"/"JEAN" share one bucket -- an
        # attacker cannot get a fresh quota by changing capitalization.
        assert key == "jean:198.51.100.7"

    def test_key_folds_username_case_and_separates_by_ip(self):
        from src.api.routes.auth import _login_rate_limit_key

        app = Flask(__name__)
        with app.test_request_context(
            "/auth/login", environ_base={"REMOTE_ADDR": "198.51.100.7"}
        ):
            assert _login_rate_limit_key("JEAN") == _login_rate_limit_key("jean")
        with app.test_request_context(
            "/auth/login", environ_base={"REMOTE_ADDR": "203.0.113.4"}
        ):
            other = _login_rate_limit_key("Jean")
        assert other == "jean:203.0.113.4"


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
