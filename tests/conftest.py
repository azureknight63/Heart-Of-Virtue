# Test-wide environment setup. All local imports use the canonical `src.` path
# (see tests/test_no_bare_local_imports.py), so no bare<->src module aliasing
# is needed here anymore — only the project root goes on sys.path.
import sys, os, pathlib
import time

# Disable LLM and reduce delays for tests
os.environ["MYNX_LLM_ENABLED"] = "0"
os.environ["MYNX_FALLBACK_DELAY"] = "0"
# Prevent CombatStrategist from making discovery requests
os.environ["MYNX_LLM_PROVIDER"] = "none"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Skip tkinter tests during web app implementation
def pytest_configure(config):
    """Configure pytest to skip tkinter-related tests."""
    config.addinivalue_line(
        "markers", "tkinter_test: mark test as tkinter-related (skipped for web app iteration)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers",
        "real_sleep: opt out of the autouse time.sleep no-op patch for tests "
        "that genuinely need real timing",
    )


import pytest


@pytest.fixture(autouse=True)
def _no_real_sleep(request, monkeypatch):
    """Globally no-op time.sleep for the duration of every test.

    Many engine code paths (story narration pacing in src/story/*.py in
    particular — ~145 time.sleep() calls across src/) use real sleeps for
    dramatic timing during actual play. Only one narrow code path
    (GameService._build_event_patches) patches time.sleep for tests that go
    through it; tests that construct/call Event or move classes directly
    bypass that harness and pay the real delay (previously several seconds
    per test in some story/event test files). This fixture closes that gap
    suite-wide instead of requiring every such test to remember to patch it.

    Tests that genuinely need real timing can opt out with
    @pytest.mark.real_sleep. A test's own `with patch("time.sleep")` (or
    similar) still works normally — it just wraps this no-op for the
    duration of its own `with` block, same as patching the real function.
    """
    if request.node.get_closest_marker("real_sleep"):
        yield
        return
    monkeypatch.setattr(time, "sleep", lambda *args, **kwargs: None)
    yield


def isinstance_by_class_name(obj, *class_names):
    """
    Check if obj's class name matches any of the given class_names.
    This is more reliable than isinstance() when modules are loaded via different paths.
    Example: isinstance_by_class_name(move, 'Attack', 'Slash')
    """
    obj_class_name = obj.__class__.__name__
    for name in class_names:
        if isinstance(name, str):
            if obj_class_name == name:
                return True
        else:
            # If name is a class, also check __name__
            if obj_class_name == getattr(name, '__name__', None):
                return True
    return False

# Monkey-patch isinstance for test convenience (optional, can be used via explicit function call)
# Actually, don't do this - it might break other code. Users should use the function explicitly.


def wire_real_allocate_level_up_points(gs):
    """
    Route a mocked GameService's allocate_level_up_points through the real
    implementation, so tests that mutate `player` attributes directly still
    exercise the actual allocation logic. The real method calls
    self.get_player_stats(player) internally, so point it at the mock's
    configurable get_player_stats instead of computing stats for real (which
    chokes on an unconfigured MagicMock player).
    """
    from src.api.services.game_service import GameService
    real_gs = GameService()
    real_gs.get_player_stats = gs.get_player_stats
    gs.allocate_level_up_points.side_effect = real_gs.allocate_level_up_points


# ─────────────────────────────────────────────────────────────────────────────
# NPC and Player Fixtures for Performance Optimization
# ─────────────────────────────────────────────────────────────────────────────
# These fixtures are available to all tests. Use them to reduce repeated setup
# overhead when creating NPCs and Players for testing.

@pytest.fixture
def player():
    """Create a fresh Player instance for testing."""
    from src.player import Player
    return Player()


@pytest.fixture
def slime_npc():
    """Create a Slime NPC for combat testing."""
    from src.npc._enemies import Slime
    return Slime()


@pytest.fixture
def mynx_npc():
    """Create a Mynx NPC for dialogue/interaction testing."""
    from src.npc._friends import Mynx
    return Mynx()


@pytest.fixture
def gorran_npc():
    """Create a Gorran NPC for ally testing."""
    from src.npc._friends import Gorran
    return Gorran()


# ─────────────────────────────────────────────────────────────────────────────
# Flask App Fixtures for API Testing
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def flask_app():
    """Create a Flask app instance for testing."""
    from src.api.app import create_app
    from src.api.config import TestingConfig
    app = create_app(TestingConfig)
    return app


@pytest.fixture
def flask_client(flask_app):
    """Create a Flask test client."""
    return flask_app.test_client()


@pytest.fixture
def app_with_session(flask_app):
    """Create a Flask app with test session support."""
    with flask_app.app_context():
        from src.api.services.session_manager import SessionManager
        # Initialize session manager if needed
        session_mgr = SessionManager()
        flask_app.session_manager = session_mgr
    return flask_app
