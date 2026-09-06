""".env.example must not ship a value that satisfies a production guard.

``src/api/config.py`` refuses to start when ``FLASK_ENV=production`` and
``SECRET_KEY`` is empty; ``AuthService`` does the same for ``ENCRYPTION_KEY``.
Both guards test for *emptiness*, so any non-empty placeholder in the example
file — ``SECRET_KEY=changeme-generate-with-secrets-token-hex`` was the one
actually shipped — passes them. A deployment that copies the file then boots
happily on a signing key published in a public repository, with the guard
reporting success while doing nothing. ``ENCRYPTION_KEY`` was already blank;
the two have the same shape and only one of them was safe.

This is asserted by *behaviour*, not by string comparison: each value is read
out of ``.env.example`` and put through the real guard. A future placeholder
fails here whatever it is spelled, and the test cannot pass by agreeing with a
copy of the value it is checking.
"""

import pathlib
import re

import pytest

from src.api.config import Config

_ENV_EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / ".env.example"

#: Variables whose *only* protection in production is a "is it empty?" check.
#: Both are read as ``os.environ.get(...)`` and both raise when blank under
#: ``FLASK_ENV=production``.
_FAIL_CLOSED_ON_EMPTY = ("SECRET_KEY", "ENCRYPTION_KEY")


def _example_value(name, text=None):
    """The value ``.env.example`` assigns to ``name`` on a live (uncommented)
    line, or ``None`` if it does not assign one."""
    if text is None:
        text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    match = re.search(r"^[ \t]*%s[ \t]*=(.*)$" % re.escape(name), text, re.M)
    return None if match is None else match.group(1).strip()


class TestTheExampleFileShipsNoUsableSecret:
    @pytest.mark.parametrize("name", _FAIL_CLOSED_ON_EMPTY)
    def test_the_line_exists_and_is_blank(self, name):
        """Present, so an operator has a line to fill in; blank, so nothing
        can boot on it."""
        assert _example_value(name) == ""

    def test_the_shipped_secret_key_does_not_satisfy_the_production_guard(
        self, monkeypatch
    ):
        """The behavioural half. Whatever ``.env.example`` says, using it
        verbatim in production must refuse to start."""
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", _example_value("SECRET_KEY") or "")
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            Config.runtime_config()

    def test_the_shipped_encryption_key_does_not_satisfy_its_guard(
        self, monkeypatch
    ):
        from src.api.services.auth_service import AuthService

        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv(
            "ENCRYPTION_KEY", _example_value("ENCRYPTION_KEY") or ""
        )
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
            AuthService()

    def test_the_generation_command_survived_the_move(self):
        """The placeholder was carrying instructions as well as a value. They
        belong in the comment, and dropping them while blanking the value
        would trade one problem for a worse-documented one."""
        text = _ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "secrets.token_hex" in text
        assert "Fernet.generate_key" in text


class TestTheGuardsStillAcceptARealSecret:
    """The control: a guard that rejected everything would satisfy the
    assertions above and take the deployment down."""

    def test_a_real_secret_key_boots(self, monkeypatch):
        """Both production credentials are set, because production needs both.

        ``runtime_config`` now refuses a missing ENCRYPTION_KEY as well --
        ``AuthService``'s own check runs at import time and so cannot see a
        config class, which left ``create_app(ProductionConfig)`` minting an
        ephemeral Fernet key. Setting only SECRET_KEY here would now be a
        production boot this method's own premise says should fail.
        """
        from cryptography.fernet import Fernet

        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "0" * 64)
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        assert Config.runtime_config()["SECRET_KEY"] == "0" * 64

    def test_production_refuses_a_missing_encryption_key(self, monkeypatch):
        """The half that was left open when the SECRET_KEY guard learned to
        ask the config class. `create_app(ProductionConfig)` with FLASK_ENV
        unset skipped it entirely and silently generated a key, orphaning every
        already-encrypted email on the next restart."""
        monkeypatch.delenv("FLASK_ENV", raising=False)
        monkeypatch.setenv("SECRET_KEY", "0" * 64)
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        from src.api.config import ProductionConfig

        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
            ProductionConfig.runtime_config()

    def test_development_still_boots_without_either(self, monkeypatch):
        """The control on the control. A dev machine must not need production
        credentials configured, or nobody can run the game."""
        from src.api.config import DevelopmentConfig

        monkeypatch.delenv("FLASK_ENV", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        assert DevelopmentConfig.runtime_config()["SECRET_KEY"]

    def test_a_real_encryption_key_boots(self, monkeypatch):
        from cryptography.fernet import Fernet

        from src.api.services.auth_service import AuthService

        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        assert AuthService().fernet is not None
