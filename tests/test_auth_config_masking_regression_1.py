"""
Regression: ISSUE-001 — login and register endpoints expose internal config errors

The outer exception handlers in login() and register() were returning str(e) raw,
leaking infrastructure details like 'TURSO_DATABASE_URL is not set' to users.

Found by /qa on 2026-03-18
Report: .gstack/qa-reports/qa-report-localhost-3000-2026-03-18.md
"""

import sys
import json
import types
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────────

_INFRA_KEYWORDS = ("_URL", "_KEY", "_TOKEN", "not set", "os.environ")


def _assert_no_infra_leak(data: dict) -> None:
    """Assert that no infrastructure keywords appear in the response body."""
    message = data.get("message", "")
    error = data.get("error", "")
    combined = f"{message} {error}"
    for kw in _INFRA_KEYWORDS:
        assert kw not in combined, (
            f"Infrastructure detail {kw!r} leaked in auth response: {combined!r}"
        )


def _load_auth_module():
    """Load src/api/routes/auth.py directly, bypassing the routes package __init__
    (which imports every other route and drags in the game engine / tkinter)."""
    import importlib as _il

    # test_event_delay_features.py replaces sys.modules['flask'] with MagicMock
    # at module level during pytest collection.  auth.py does `from flask import Blueprint`
    # at module level, so we must restore the real flask *before* exec_module runs.
    _flask_mod = sys.modules.get("flask")
    if _flask_mod is None or isinstance(_flask_mod, MagicMock):
        sys.modules.pop("flask", None)
        sys.modules["flask"] = _il.import_module("flask")

    auth_svc = MagicMock()
    auth_svc.create_user = AsyncMock(return_value={"id": "test-id"})
    auth_svc.authenticate_user = AsyncMock(return_value=None)

    # Pre-populate sys.modules with stubs so auth.py's imports succeed
    _stubs = {
        "src.api.services": types.ModuleType("src.api.services"),
        "src.api.services.session_manager": types.ModuleType("src.api.services.session_manager"),
        "src.api.services.auth_service": types.ModuleType("src.api.services.auth_service"),
        "src.api.middleware": types.ModuleType("src.api.middleware"),
        "src.api.middleware.auth": types.ModuleType("src.api.middleware.auth"),
    }
    sm_mock = MagicMock()
    _stubs["src.api.services"].SessionManager = MagicMock(return_value=sm_mock)
    _stubs["src.api.services"].GameService = MagicMock()
    _stubs["src.api.services.session_manager"].SessionManager = MagicMock(return_value=sm_mock)
    _stubs["src.api.services.auth_service"].auth_service = auth_svc
    _stubs["src.api.middleware.auth"].require_session = lambda f: f

    # Always inject stubs, saving originals so teardown can restore them.
    # (The real src.api.* modules may already be in sys.modules from other test
    # files imported during pytest collection — we must overwrite them here.)
    saved = {}
    for name, mod in _stubs.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod
    injected = saved  # keys to restore on teardown

    # Load auth.py as a standalone module (not via the package __init__)
    auth_path = ROOT / "src" / "api" / "routes" / "auth.py"
    spec = importlib.util.spec_from_file_location("_auth_isolated", auth_path)
    auth_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth_mod)

    return auth_mod, auth_svc, sm_mock, injected


@pytest.fixture(scope="module")
def auth_setup():
    """Load the auth module and return (auth_bp, auth_svc, sm_mock)."""
    auth_mod, auth_svc, sm_mock, injected = _load_auth_module()
    yield auth_mod, auth_svc, sm_mock
    # Restore pre-test sys.modules state (originals or absent)
    for name, original in injected.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


@pytest.fixture(scope="module")
def auth_client(auth_setup):
    """Create a minimal Flask test client with just the auth blueprint."""
    import sys
    import importlib

    # test_event_delay_features.py replaces sys.modules['flask'] with MagicMock at
    # module level during pytest collection.  Reload the real flask if it was mocked
    # so this fixture always builds a real Flask app regardless of test ordering.
    from unittest.mock import MagicMock as _MM
    _flask = sys.modules.get("flask")
    if _flask is None or isinstance(_flask, _MM):
        sys.modules.pop("flask", None)
        _flask = importlib.import_module("flask")
        sys.modules["flask"] = _flask
    Flask = _flask.Flask

    auth_mod, auth_svc, sm_mock = auth_setup

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.session_manager = sm_mock
    app.register_blueprint(auth_mod.auth_bp, url_prefix="/api")

    with app.test_client() as client:
        yield client


# ─── Tests ──────────────────────────────────────────────────────────────────────

class TestAuthConfigMasking:
    """Ensure config/infra error details are never leaked in auth responses."""

    def test_register_masks_turso_url_error(self, auth_setup, auth_client):
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.create_user = AsyncMock(side_effect=ValueError("TURSO_DATABASE_URL is not set"))
        response = auth_client.post(
            "/api/auth/register",
            json={"username": "testuser", "password": "testpass", "email": "t@t.com"},
        )
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["success"] is False
        _assert_no_infra_leak(data)

    def test_register_masks_turso_token_error(self, auth_setup, auth_client):
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.create_user = AsyncMock(side_effect=ValueError("TURSO_AUTH_TOKEN is not set"))
        response = auth_client.post(
            "/api/auth/register",
            json={"username": "testuser", "password": "testpass", "email": "t@t.com"},
        )
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["success"] is False
        _assert_no_infra_leak(data)

    def test_login_masks_turso_url_error(self, auth_setup, auth_client):
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.authenticate_user = AsyncMock(side_effect=Exception("TURSO_DATABASE_URL is not set"))
        response = auth_client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["success"] is False
        _assert_no_infra_leak(data)

    def test_login_masks_env_var_error(self, auth_setup, auth_client):
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.authenticate_user = AsyncMock(
            side_effect=Exception("os.environ['DATABASE_KEY'] not configured")
        )
        response = auth_client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["success"] is False
        _assert_no_infra_leak(data)

    def test_login_regular_server_error_still_500(self, auth_setup, auth_client):
        """Non-infra server errors must still return 500 (not silently swallowed)."""
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.authenticate_user = AsyncMock(
            side_effect=Exception("Something unexpected happened")
        )
        response = auth_client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["success"] is False

    def test_register_validation_error_still_400(self, auth_setup, auth_client):
        """Non-infra ValueError from register should still return 400."""
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.create_user = AsyncMock(
            side_effect=ValueError("Username must be at least 3 characters")
        )
        response = auth_client.post(
            "/api/auth/register",
            json={"username": "ab", "password": "testpass", "email": "t@t.com"},
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        _assert_no_infra_leak(data)
