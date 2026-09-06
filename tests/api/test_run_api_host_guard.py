"""``tools/run_api.py`` does not publish the dev server on one variable.

The sibling of ``tests/api/test_wsgi_production_guard.py``: that file asserts
the production entry point refuses a TESTING config, this one asserts the
*development* entry point refuses a non-loopback bind without a second, named
opt-in.

What ``HOST=0.0.0.0`` used to hand to the LAN, unconditionally: Werkzeug's
``/console`` (an interactive Python REPL, PIN-gated only) and a full source
traceback on every 500 — every config this entry point serves pins
``DEBUG = True`` — plus, under ``FLASK_ENV=testing``, which this repo's own
``.env`` sets, ``/api/test/session`` (a valid session for any username, no
credentials) and the whole ``/api/debug/*`` blueprint. That is the same pair
``wsgi.py`` refuses to boot rather than expose, and it was reachable here by
one variable that a ``.env`` copied between machines carries silently.
"""

import pytest

from tools.run_api import REMOTE_OPT_IN_VAR, resolve_host

_ROUTABLE = "0.0.0.0"


@pytest.fixture(autouse=True)
def _no_inherited_opt_in(monkeypatch):
    """The developer's own environment must not decide these tests."""
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv(REMOTE_OPT_IN_VAR, raising=False)


class TestTheDefaultIsLoopback:
    def test_unset_host_binds_loopback(self):
        assert resolve_host() == "127.0.0.1"

    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",
            "127.0.0.53",  # the whole 127/8 block, not just the one address
            "::1",
            "localhost",
            "LocalHost",  # a hostname is not case-sensitive
        ],
    )
    def test_a_loopback_host_needs_no_opt_in(self, host, monkeypatch):
        monkeypatch.setenv("HOST", host)
        assert resolve_host() == host


class TestANonLoopbackHostIsRefused:
    @pytest.mark.parametrize(
        "host",
        [
            "0.0.0.0",  # the one people actually type
            "::",
            "192.168.1.50",
            "hov.local",  # a name is not assumed to be loopback
        ],
    )
    def test_it_raises_rather_than_binding(self, host, monkeypatch):
        monkeypatch.setenv("HOST", host)
        with pytest.raises(SystemExit):
            resolve_host()

    def test_the_refusal_says_what_it_is_protecting(self, monkeypatch):
        """As specific as wsgi.py's refusal, and for the same reason: a
        message that only says "refused" reads as pedantry and gets deleted,
        or worked around with the opt-in without the reader ever learning
        what they just switched on."""
        monkeypatch.setenv("HOST", _ROUTABLE)
        with pytest.raises(SystemExit) as excinfo:
            resolve_host()
        message = str(excinfo.value)
        assert repr(_ROUTABLE) in message
        assert "/console" in message
        assert "/api/test/session" in message
        assert "/api/debug/" in message
        # ...and it has to name the way out, or the operator's only options
        # are to give up or to edit the guard.
        assert REMOTE_OPT_IN_VAR in message


class TestTheOptInWorks:
    """The control. A guard that refused every non-loopback host outright
    would satisfy every assertion above and make a LAN demo impossible."""

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_an_explicit_opt_in_permits_the_bind(self, value, monkeypatch):
        monkeypatch.setenv("HOST", _ROUTABLE)
        monkeypatch.setenv(REMOTE_OPT_IN_VAR, value)
        assert resolve_host() == _ROUTABLE

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_an_off_value_is_not_an_opt_in(self, value, monkeypatch):
        """Shares ``_env_flag`` with the rest of the config surface, so the
        spellings that mean "off" everywhere else — including an
        exported-but-blank variable — mean "off" here too."""
        monkeypatch.setenv("HOST", _ROUTABLE)
        monkeypatch.setenv(REMOTE_OPT_IN_VAR, value)
        with pytest.raises(SystemExit):
            resolve_host()


class TestTheVariableIsDocumented:
    def test_env_example_offers_the_opt_in(self):
        import pathlib

        env_example = (
            pathlib.Path(__file__).resolve().parents[2] / ".env.example"
        )
        text = env_example.read_text(encoding="utf-8")
        assert "%s=" % REMOTE_OPT_IN_VAR in text
