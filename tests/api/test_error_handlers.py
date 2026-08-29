"""Integration tests for error handlers.

Only 404/405 (raised by Flask's own routing) and 500/generic-exception
handlers are registered — see `src/api/handlers/error_handler.py`. Every
other status code (400/401/403/422/429/503) is produced by routes/middleware
building their own JSON response inline (issue #437), so there is no global
handler to test for those; asserting on them here would test dead code.

NOTHING IN THIS FILE RUNS. `pytest.ini`'s `norecursedirs` excludes
`tests/api`, so this module is collected only when the directory is named
explicitly. Do not add a guard here expecting it to hold: the security
assertion that used to live here (a 500's `description` must not reach the
client) has been moved to `tests/test_error_handler_logging.py`, along with
the message-field check, because that file is inside the walked suite. Every
remaining test below is duplicated by `TestErrorHandler` in
`tests/test_api_routes_and_serializers.py`, which does run.
"""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent


import pytest

try:
    from flask import Flask
    from src.api.handlers.error_handler import register_error_handlers

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestErrorHandlers:
    """Test suite for error handlers."""

    @pytest.fixture
    def app(self):
        """Create test Flask app with error handlers."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        register_error_handlers(app)

        @app.route("/test_404")
        def test_404():
            from flask import abort

            abort(404)

        @app.route("/test_500")
        def test_500():
            from flask import abort

            abort(500)

        @app.route("/test_exception")
        def test_exception():
            raise Exception("Test exception")

        return app

    @pytest.fixture
    def client(self, app):
        """Create Flask test client."""
        return app.test_client()

    def test_404_error_response(self, client):
        """Test 404 Not Found error response format."""
        response = client.get("/test_404")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False
        assert "Not found" in data["error"]

    def test_500_error_response(self, client):
        """Test 500 Internal Server Error response format."""
        response = client.get("/test_500")
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "Internal server error" in data["error"]

    # The issue #262 leak regression and the message-field check that used to
    # sit here now live in tests/test_error_handler_logging.py, inside the
    # walked suite. See this module's docstring.

    def test_generic_exception_handler(self, client):
        """Test generic exception handler for unhandled exceptions."""
        response = client.get("/test_exception")
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "Internal server error" in data["error"]
