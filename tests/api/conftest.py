"""Pytest configuration for API tests."""

import sys
from pathlib import Path

# Ensure src is on path for API tests
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Set up module shims for game engine (same as tests/conftest.py)
import src.functions as _functions  # noqa: F401
sys.modules.setdefault('functions', _functions)

# Set up core module shims in order
_core_order = [
    'animations',
    'genericng',
    'enchant_tables',
    'states',
    'items',
    'objects',
    'loot_tables',
    'actions',
    'tiles',
    'universe',
    'positions',
    'moves',
    'npc',
    'skilltree',
    'switch',
    'player'
]
for _name in _core_order:
    if _name in sys.modules:
        continue
    try:
        sys.modules[_name] = __import__(f'src.{_name}', fromlist=['*'])
    except Exception:
        pass

# Optional shims
for _mod in ("combat", "skilltree", "events", "shop_conditions"):
    if _mod not in sys.modules:
        try:
            sys.modules[_mod] = __import__(f"src.{_mod}", fromlist=['*'])
        except Exception:
            pass

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
