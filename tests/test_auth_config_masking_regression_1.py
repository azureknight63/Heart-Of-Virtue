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
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────────

_INFRA_KEYWORDS = ("_URL", "_KEY", "_TOKEN", "not set", "os.environ")


def _assert_no_infra_leak(response, raised: str = "") -> None:
    """Assert no infrastructure detail appears *anywhere* in the response.

    Scans the raw serialized body rather than the ``message``/``error`` keys.
    The original helper read only those two keys, so a leak that landed in a
    ``details``/``debug`` field, in a nested ``data`` object, or in a key added
    later would have passed silently -- and "the handler grew a new field" is
    exactly how this class of regression comes back.

    ``raised`` is the exact text of the exception the route was made to hit;
    asserting its absence verbatim catches a leak whose wording happens not to
    contain one of the coarse keyword markers.
    """
    body = response.data.decode("utf-8", "replace")
    for kw in _INFRA_KEYWORDS:
        assert kw not in body, (
            f"Infrastructure detail {kw!r} leaked in auth response: {body!r}"
        )
    if raised:
        assert raised not in body, (
            f"Raw exception text {raised!r} echoed to the client: {body!r}"
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
    # The real class, not a look-alike. auth.py's `except` clause resolves the
    # name through this stub module, so a locally-defined stand-in would make
    # every test below agree with itself while telling you nothing about the
    # exception AuthService actually raises.
    from src.api.services.auth_service import RegistrationValidationError

    _stubs[
        "src.api.services.auth_service"
    ].RegistrationValidationError = RegistrationValidationError
    _stubs["src.api.middleware.auth"].require_session = lambda f: f
    # auth.py also imports resolve_session (issue #408); the stub must provide
    # it or exec_module raises at fixture setup, skipping teardown and leaking
    # these stub modules into sys.modules for every later test.
    _stubs["src.api.middleware.auth"].resolve_session = MagicMock()

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

    # One representative message per marker in auth.py's _CONFIG_LEAK_MARKERS.
    # Parametrizing over the whole marker set (rather than hand-picking two of
    # the five) means adding a marker to the production tuple without a
    # matching mask is caught here.
    LEAKY_MESSAGES = [
        "TURSO_DATABASE_URL is not configured",          # _URL
        "SECRET_KEY missing from the environment",       # _KEY
        "TURSO_AUTH_TOKEN rejected by the backend",      # _TOKEN
        "database credentials not set",                  # not set
        "os.environ['DATABASE_KEY'] not configured",     # os.environ
    ]

    def test_every_production_marker_has_a_probe(self, auth_setup):
        """Guards the parametrization above against drift.

        If someone adds a sixth marker to ``_CONFIG_LEAK_MARKERS`` the
        LEAKY_MESSAGES list stops covering the module and this fails, instead
        of the new marker quietly going untested.
        """
        auth_mod, _, _ = auth_setup
        markers = set(auth_mod._CONFIG_LEAK_MARKERS)
        assert markers == set(_INFRA_KEYWORDS)
        for marker in markers:
            assert any(marker in msg for msg in self.LEAKY_MESSAGES), (
                f"no probe message exercises marker {marker!r}"
            )
            assert auth_mod._is_config_leak(f"boom {marker} boom") is True
        # ...and an ordinary message must NOT be classified as a leak, or
        # every validation error would be masked into a useless 503.
        assert auth_mod._is_config_leak("Username must be at least 3 characters") is False

    @pytest.mark.parametrize("raised", LEAKY_MESSAGES)
    def test_register_masks_config_errors_as_503(self, auth_setup, auth_client, raised):
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.create_user = AsyncMock(side_effect=ValueError(raised))
        response = auth_client.post(
            "/api/auth/register",
            json={"username": "testuser", "password": "testpass", "email": "t@t.com"},
        )
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data == {
            "success": False,
            "error": "service_unavailable",
            "message": "Registration is temporarily unavailable. Please try again later.",
        }
        _assert_no_infra_leak(response, raised)

    @pytest.mark.parametrize("raised", LEAKY_MESSAGES)
    def test_login_masks_config_errors_as_503(self, auth_setup, auth_client, raised):
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.authenticate_user = AsyncMock(side_effect=Exception(raised))
        response = auth_client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data == {
            "success": False,
            "error": "service_unavailable",
            "message": "Login is temporarily unavailable. Please try again later.",
        }
        _assert_no_infra_leak(response, raised)

    def test_login_regular_server_error_still_500(self, auth_setup, auth_client):
        """Non-infra server errors must still return 500 (not silently swallowed).

        The 503 mask must not become a catch-all: a genuine bug has to keep
        surfacing as a 500 so it shows up in monitoring as an error rather
        than as planned maintenance. And the generic 500 body must not echo
        the exception text either -- previously only ``success is False`` was
        asserted here, which a body of ``{"success": false, "message":
        "Something unexpected happened"}`` would also have satisfied.
        """
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
        assert data == {
            "success": False,
            "error": "server_error",
            "message": "Internal server error",
        }
        assert "Something unexpected happened" not in response.data.decode()

    def test_register_validation_error_still_400(self, auth_setup, auth_client):
        """A declared validation failure is passed through verbatim at 400.

        The deliberate counterweight to the masking above: real validation
        feedback is the message the user needs, so assert it actually reaches
        them rather than merely that the status is 400.

        Raised as ``RegistrationValidationError`` because that -- not the
        wording -- is now what marks a message safe to echo.
        """
        from src.api.services.auth_service import RegistrationValidationError

        auth_mod, auth_svc, _ = auth_setup
        auth_svc.create_user = AsyncMock(
            side_effect=RegistrationValidationError(
                "Username must be at least 3 characters"
            )
        )
        response = auth_client.post(
            "/api/auth/register",
            json={"username": "ab", "password": "testpass", "email": "t@t.com"},
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data == {
            "success": False,
            "error": "validation_error",
            "message": "Username must be at least 3 characters",
        }
        _assert_no_infra_leak(response)

    #: An infrastructure failure whose text contains NONE of
    #: ``_CONFIG_LEAK_MARKERS``. This is the case the marker list could not see
    #: and the case a test built from that same marker list could not think to
    #: ask about -- which is why it is written out here as its own probe rather
    #: than added to LEAKY_MESSAGES.
    UNMARKED_INFRA_MESSAGE = (
        "could not connect to postgres://svc:hunter2@db.internal:5432/hov"
    )

    def test_an_infra_message_with_no_marker_is_masked_too(
        self, auth_setup, auth_client
    ):
        """The regression. Measured before the fix: 400, with the message --
        and the password inside it -- returned verbatim to an anonymous POST.

        A plain ``ValueError`` now means "not a declared validation failure",
        so it is masked whatever it says. The five markers decide nothing here
        any more.
        """
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.create_user = AsyncMock(
            side_effect=ValueError(self.UNMARKED_INFRA_MESSAGE)
        )
        response = auth_client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "password": "testpassword1234",
                "email": "t@t.com",
            },
        )
        assert response.status_code == 503
        assert json.loads(response.data) == {
            "success": False,
            "error": "service_unavailable",
            "message": (
                "Registration is temporarily unavailable. Please try again later."
            ),
        }
        _assert_no_infra_leak(response, self.UNMARKED_INFRA_MESSAGE)

    def test_the_probe_message_really_is_invisible_to_the_markers(
        self, auth_setup
    ):
        """Non-vacuity for the test above.

        If the probe happened to contain a marker it would be masked by the
        old mechanism too, and would prove nothing about the new one.
        """
        auth_mod, _, _ = auth_setup
        assert auth_mod._is_config_leak(self.UNMARKED_INFRA_MESSAGE) is False
        present = [
            m for m in auth_mod._CONFIG_LEAK_MARKERS
            if m in self.UNMARKED_INFRA_MESSAGE
        ]
        assert present == [], present

    def test_every_validation_raise_in_create_user_is_the_declared_type(self):
        """Floor on the increment.

        The route now echoes exactly one exception type, so a sixth input
        bound added to ``create_user`` as a plain ``ValueError`` would not
        reach the user as advice -- it would be masked into an unhelpful 503.
        Derived from the source so the sixth one is caught on arrival.
        """
        import ast

        source = (ROOT / "src" / "api" / "services" / "auth_service.py").read_text(
            encoding="utf-8"
        )
        create_user = next(
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "create_user"
        )
        # Only the validation prologue -- the bounds checks that run before any
        # database work. Failures after that point are infrastructure.
        raises = [
            node
            for node in ast.walk(create_user)
            if isinstance(node, ast.Raise)
            and isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Name)
        ]
        assert raises, "no raises found in create_user; the scan has drifted"
        wrong = sorted(
            {
                node.exc.func.id
                for node in raises
                if node.exc.func.id == "ValueError"
            }
        )
        assert wrong == [], (
            "create_user raises plain %s for what looks like input validation. "
            "routes/auth.py echoes RegistrationValidationError and masks "
            "everything else, so this message would reach the user as a 503 "
            "with no explanation." % ", ".join(wrong)
        )

    def test_register_non_value_error_does_not_echo_the_exception(
        self, auth_setup, auth_client
    ):
        """register()'s inner ``except Exception`` re-raises anything that is
        not a UNIQUE-constraint violation, so an infra failure raised as a
        plain Exception (rather than ValueError) reaches the *outer* handler.

        That handler has no ``_is_config_leak`` check, so this is a 500 rather
        than a 503 -- an asymmetry with login(), which does check in its outer
        handler. It is safe only because the outer body is a fixed string.
        Pinned so that if the outer handler ever starts including ``str(e)``
        (as the original ISSUE-001 code did), the leak fails here.
        """
        auth_mod, auth_svc, _ = auth_setup
        raised = "TURSO_DATABASE_URL is not set"
        auth_svc.create_user = AsyncMock(side_effect=RuntimeError(raised))
        response = auth_client.post(
            "/api/auth/register",
            json={"username": "testuser", "password": "testpass", "email": "t@t.com"},
        )
        assert response.status_code == 500
        assert json.loads(response.data) == {
            "success": False,
            "error": "server_error",
            "message": "Internal server error",
        }
        _assert_no_infra_leak(response, raised)

    def test_username_conflict_is_409_and_says_so(self, auth_setup, auth_client):
        """The one exception register() translates rather than re-raises."""
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.create_user = AsyncMock(
            side_effect=Exception(
                "UNIQUE constraint failed: users.username (db=turso://internal)"
            )
        )
        response = auth_client.post(
            "/api/auth/register",
            json={"username": "testuser", "password": "testpass", "email": "t@t.com"},
        )
        assert response.status_code == 409
        assert json.loads(response.data) == {
            "success": False,
            "error": "conflict_error",
            "message": "Username already exists",
        }
        # The driver's message carries the table/DSN; none of it may survive.
        assert "UNIQUE constraint" not in response.data.decode()
        assert "turso://" not in response.data.decode()

    def test_bad_credentials_are_401_not_masked(self, auth_setup, auth_client):
        """A returned ``None`` (no such user / wrong password) is an ordinary
        401 with a non-enumerating message.

        Included because an over-broad ``status_code in (401, 503, ...)``
        assertion elsewhere in this suite passed on the *unconfigured
        database* 503 and never once proved that bad credentials are rejected.
        """
        auth_mod, auth_svc, _ = auth_setup
        auth_svc.authenticate_user = AsyncMock(return_value=None)
        response = auth_client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "wrong"},
        )
        assert response.status_code == 401
        assert json.loads(response.data) == {
            "success": False,
            "error": "auth_error",
            "message": "Invalid username or password",
        }
        # The credentials themselves must not be reflected back.
        assert "wrong" not in response.data.decode()
        auth_svc.authenticate_user.assert_awaited_once_with("testuser", "wrong")
