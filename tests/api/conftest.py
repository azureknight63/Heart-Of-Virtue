"""Pytest configuration for API tests."""

import sys
from pathlib import Path

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
    """Create Flask app for testing (session-scoped for performance)."""
    app, socketio = create_app(TestingConfig)
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


@pytest.fixture
def api_client():
    """Create a Flask test client (when routes are implemented)."""
    # TODO: Implement when app factory is complete
    pass


# Patch terminal output functions for tests to avoid encoding issues on Windows
@pytest.fixture(autouse=True)
def patch_terminal_output(monkeypatch):
    """Patch terminal output functions to prevent UnicodeEncodeError on Windows.

    Story events call cprint(), print_slow(), input_with_timeout() etc. which can fail
    with UnicodeEncodeError when trying to print Unicode characters to a Windows console.
    This fixture replaces those functions with no-ops for testing purposes.
    """
    import io

    # Create a dummy StringIO to capture output (or discard it)
    dummy_output = io.StringIO()

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

    # Patch functions in the game engine modules
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)

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
# Module-level mocking for slow I/O operations
# ─────────────────────────────────────────────────────────────────────────────
# These module-level patches apply to all tests in tests/api/ to reduce overhead.
# This is safe because tests explicitly mock required behaviors, and these are
# fallback safeguards for operations that should not occur during testing.

from unittest.mock import patch, MagicMock

# Mock time.sleep() globally for tests (should never be called; guards against
# inadvertent delays from untested code paths)
_sleep_patch = patch('time.sleep', return_value=None)
_sleep_patch.start()

# Mock any slow crypto/hashing operations if they occur unexpectedly
# (legitimate password hashing should be in tested methods, not untested code)
_hashlib_patch = patch('hashlib.pbkdf2_hmac', return_value=b'mocked_hash')
_hashlib_patch.start()
