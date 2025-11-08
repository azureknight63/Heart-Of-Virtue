"""Pytest configuration for API tests."""

import sys
from pathlib import Path

# Ensure src is on path for API tests
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

try:
    from src.api.app import create_app  # type: ignore
    from src.api.config import TestingConfig  # type: ignore
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@pytest.fixture(scope="session")
def app():
    """Create Flask app for testing (session-scoped for performance)."""
    if not FLASK_AVAILABLE:
        pytest.skip("Flask not installed")
    
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
    session_id, player = session_manager.create_session("testplayer")
    return session_id, player, session_manager


@pytest.fixture
def api_client():
    """Create a Flask test client (when routes are implemented)."""
    # TODO: Implement when app factory is complete
    pass
