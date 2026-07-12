"""Integration tests for error handlers."""

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

        @app.route("/test_400")
        def test_400():
            from flask import abort

            abort(400)

        @app.route("/test_401")
        def test_401():
            from flask import abort

            abort(401)

        @app.route("/test_403")
        def test_403():
            from flask import abort

            abort(403)

        @app.route("/test_404")
        def test_404():
            from flask import abort

            abort(404)

        @app.route("/test_422")
        def test_422():
            from flask import abort

            abort(422)

        @app.route("/test_429")
        def test_429():
            from flask import abort

            abort(429)

        @app.route("/test_500")
        def test_500():
            from flask import abort

            abort(500)

        @app.route("/test_500_detail")
        def test_500_detail():
            from werkzeug.exceptions import InternalServerError

            # Simulate an internal error whose description carries sensitive
            # detail (stack/path info) that must never reach the client.
            raise InternalServerError(
                description="secret-db-password=hunter2 at /etc/private/config.py"
            )

        @app.route("/test_503")
        def test_503():
            from flask import abort

            abort(503)

        @app.route("/test_exception")
        def test_exception():
            raise Exception("Test exception")

        return app

    @pytest.fixture
    def client(self, app):
        """Create Flask test client."""
        return app.test_client()

    def test_400_error_response(self, client):
        """Test 400 Bad Request error response format."""
        response = client.get("/test_400")
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data
        assert "Bad request" in data["error"]

    def test_401_error_response(self, client):
        """Test 401 Unauthorized error response format."""
        response = client.get("/test_401")
        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert "Unauthorized" in data["error"]

    def test_403_error_response(self, client):
        """Test 403 Forbidden error response format."""
        response = client.get("/test_403")
        assert response.status_code == 403
        data = response.get_json()
        assert data["success"] is False
        assert "Forbidden" in data["error"]

    def test_404_error_response(self, client):
        """Test 404 Not Found error response format."""
        response = client.get("/test_404")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False
        assert "Not found" in data["error"]

    def test_422_error_response(self, client):
        """Test 422 Unprocessable Entity error response format."""
        response = client.get("/test_422")
        assert response.status_code == 422
        data = response.get_json()
        assert data["success"] is False
        assert "Unprocessable" in data["error"]

    def test_500_error_response(self, client):
        """Test 500 Internal Server Error response format."""
        response = client.get("/test_500")
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "Internal server error" in data["error"]

    def test_500_error_does_not_leak_exception_detail(self, client):
        """Regression test for issue #262: the 500 handler must return a
        generic message and never echo str(error) / exception detail."""
        response = client.get("/test_500_detail")
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert data["message"] == "An unexpected error occurred"
        assert "secret-db-password" not in data["message"]
        assert "hunter2" not in data["message"]
        assert "/etc/private/config.py" not in data["message"]

    def test_error_contains_message_field(self, client):
        """Test that all error responses contain a message field."""
        response = client.get("/test_400")
        data = response.get_json()
        assert "message" in data
        assert isinstance(data["message"], str)

    def test_429_error_response(self, client):
        """Test 429 Too Many Requests error response format."""
        response = client.get("/test_429")
        assert response.status_code == 429
        data = response.get_json()
        assert data["success"] is False
        assert "Too many requests" in data["error"]

    def test_503_error_response(self, client):
        """Test 503 Service Unavailable error response format."""
        response = client.get("/test_503")
        assert response.status_code == 503
        data = response.get_json()
        assert data["success"] is False
        assert "Service unavailable" in data["error"]

    def test_generic_exception_handler(self, client):
        """Test generic exception handler for unhandled exceptions."""
        response = client.get("/test_exception")
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "Internal server error" in data["error"]
