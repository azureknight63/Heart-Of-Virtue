"""Pytest configuration for API tests."""

import os
import sys
from pathlib import Path

# Keep API tests deterministic even when the developer's .env selects a manual
# gameplay configuration. Individual tests that exercise config loading use
# monkeypatch/patch.dict explicitly.
_TEST_CONFIG_FILE = os.environ.pop("CONFIG_FILE", None)
# A missing CONFIG_FILE makes SessionManager fall back to the developer-only
# config_dev.ini when it exists. Use a nonexistent sentinel instead so tests
# exercise engine defaults without depending on an untracked local file.
os.environ["CONFIG_FILE"] = "__hermes_api_tests_no_config__.ini"

# Project root on sys.path. src/ is deliberately NOT added and no bare-name
# module shims are installed: every local import uses the canonical `src.`
# path, so a bare-import regression fails loudly here too.
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from src.api.app import create_app
from src.api.config import TestingConfig
FLASK_AVAILABLE = True


@pytest.fixture(scope="session")
def app():
    """Create a config-isolated Flask app for API tests.

    The developer's .env may select a gameplay config for manual QA. API tests
    must not inherit that config because it changes starting equipment, maps,
    and combat ranges for every session created by this fixture.
    """
    sentinel = object()
    streaming_flag = os.environ.pop("COMBAT_SOCKET_STREAMING", sentinel)
    try:
        app, socketio = create_app(TestingConfig)
    finally:
        if streaming_flag is not sentinel:
            os.environ["COMBAT_SOCKET_STREAMING"] = streaming_flag
    return app


@pytest.fixture
def client(app):
    """Create Flask test client (function-scoped)."""
    return app.test_client()


@pytest.fixture
def authenticated_session(app):
    """Create authenticated session with player (function-scoped)."""
    session_manager = app.session_manager
    session_id, username = session_manager.create_session("testplayer")
    player = session_manager.get_player(session_id)
    return session_id, player, session_manager


# Patch terminal output functions for tests to avoid encoding issues on Windows
@pytest.fixture(autouse=True)
def patch_terminal_output(monkeypatch):
    """Silence the engine's terminal writers so a Windows console cannot choke.

    Story events call cprint(), print_slow(), input_with_timeout() etc. Those
    emit the engine's box-drawing characters, which a cp1252 console cannot
    encode -- and input_with_timeout blocks on a terminal nobody is watching.
    Replacing those four is the whole of what this needs to do.

    ``builtins.print`` is deliberately NOT patched, and must not be. It looks
    like a cheaper way to get the same silence, and it is a trap:

    * ``logging.Formatter.formatException`` renders a traceback through
      ``traceback.print_exception``, which writes with ``print``. Null ``print``
      and every formatted traceback in the process becomes the empty string --
      so an assertion that a credential is absent from a traceback holds
      vacuously, in the one direction where a false green is a security claim.
      See ``tests/test_error_handler_logging.py``, which had to be moved out of
      this directory to escape exactly that.
    * It is the wrong tool for asserting on engine output anyway. Engine text
      goes through the narration sink (``src/narration.py``), which carries
      ``color`` and ``type`` alongside the text; ``print`` sees the text only.
      ``tests/conftest.py`` says this at length and supplies the ``narrated``
      and ``narration_pairs`` helpers. Those apply here too -- this conftest is
      a child of that one.
    """

    def mock_cprint(*args, **kwargs):
        """Mock cprint that discards output."""
        pass

    def mock_print_slow(text, *args, **kwargs):
        """Mock print_slow that discards output."""
        pass

    def mock_input_with_timeout(*args, **kwargs):
        """Mock input_with_timeout that returns a default value."""
        return kwargs.get('default', 'continue')

    def mock_input_prompt(*args, **kwargs):
        """Mock input_prompt that returns a default value."""
        return 'continue'

    try:
        import src.interface as interface
        monkeypatch.setattr(interface, 'cprint', mock_cprint, raising=False)
        monkeypatch.setattr(interface, 'print_slow', mock_print_slow, raising=False)
        monkeypatch.setattr(interface, 'input_with_timeout', mock_input_with_timeout, raising=False)
        monkeypatch.setattr(interface, 'input_prompt', mock_input_prompt, raising=False)
    except (ImportError, AttributeError):
        pass

    try:
        from neotermcolor import cprint
        monkeypatch.setattr('neotermcolor.cprint', mock_cprint, raising=False)
    except (ImportError, AttributeError):
        pass


# ─────────────────────────────────────────────────────────────────────────────
# What used to be here, and why it is gone
# ─────────────────────────────────────────────────────────────────────────────
# Two ``unittest.mock.patch(...).start()`` calls sat at module scope with no
# matching ``.stop()`` and no fixture to bound them. A conftest is imported, not
# run, so both took effect at collection time and stayed in force for the rest
# of the process -- including any test outside this directory collected in the
# same session.
#
#   patch('time.sleep')       Redundant. ``tests/conftest.py`` is this file's
#       parent conftest and its ``_no_real_sleep`` autouse fixture already
#       no-ops ``time.sleep`` for every test here, scoped per test and with a
#       ``@pytest.mark.real_sleep`` opt-out for the tests that need real timing.
#       The module-level version offered no opt-out and could not be undone.
#
#   patch('hashlib.pbkdf2_hmac')  Guarded nothing. Nothing under ``src/`` calls
#       it: ``AuthService`` hashes with argon2 (``self.ph.hash`` /
#       ``self.ph.verify``, see ``src/api/services/auth_service.py``). All it
#       could do was make an unrelated caller's digest silently constant.
