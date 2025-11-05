"""Integration tests for error handlers."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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

        @app.route("/test_500")
        def test_500():
            from flask import abort

            abort(500)

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

    def test_error_contains_message_field(self, client):
        """Test that all error responses contain a message field."""
        response = client.get("/test_400")
        data = response.get_json()
        assert "message" in data
        assert isinstance(data["message"], str)

    def test_404_nonexistent_route(self, client):
        """Test 404 for non-existent route."""
        response = client.get("/nonexistent/route")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False
