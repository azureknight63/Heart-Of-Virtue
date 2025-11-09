"""Pytest configuration for API tests."""

import sys
from pathlib import Path

# Ensure src is on path for API tests
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# CRITICAL: Set up module shims for game engine BEFORE importing anything else
# This prevents "No module named 'functions'" when universe.py does 'import functions'
import src.functions as functions  # noqa: F401
sys.modules['functions'] = functions

# Set up other core module shims (only after functions is available)
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
    'scenario_config',
    'coordinate_config',
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
        _mod = __import__(f'src.{_name}', fromlist=['*'])
        sys.modules[_name] = _mod
    except Exception as e:
        # Silently skip modules that fail to import
        pass

# Optional shims (for modules that may not exist)
for _mod in ("combat", "events", "shop_conditions"):
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
except (ImportError, ModuleNotFoundError) as e:
    FLASK_AVAILABLE = False
    print(f"WARNING: Failed to import Flask API: {e}")
    import traceback
    traceback.print_exc()


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
    session_id, username = session_manager.create_session("testplayer")
    player = session_manager.get_player(session_id)
    return session_id, player, session_manager


@pytest.fixture
def api_client():
    """Create a Flask test client (when routes are implemented)."""
    # TODO: Implement when app factory is complete
    pass
