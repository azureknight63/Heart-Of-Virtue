"""Integration tests for API routes."""

import sys
from pathlib import Path
import json

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.app import create_app  # type: ignore
from src.api.config import TestingConfig  # type: ignore
from src.api.services import SessionManager  # type: ignore


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app, socketio = create_app(TestingConfig)
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def session_id(app):
    """Create a test session."""
    session_manager = app.session_manager
    sid, _ = session_manager.create_session("testuser")
    return sid


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test /health endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert "sessions" in data

    def test_api_info(self, client):
        """Test /api/info endpoint."""
        response = client.get("/api/info")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["name"] == "Heart of Virtue API"
        assert data["version"] == "1.0.0"


class TestAuthRoutes:
    """Test authentication endpoints."""

    def test_login_success(self, client):
        """Test successful login."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "testuser"}),
            content_type="application/json",
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["success"] is True
        assert "session_id" in data
        assert "player_id" in data
        assert "expires_at" in data

    def test_login_missing_username(self, client):
        """Test login without username."""
        response = client.post(
            "/auth/login",
            data=json.dumps({}),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_login_short_username(self, client):
        """Test login with too-short username."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "a"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_logout_success(self, client, session_id):
        """Test successful logout."""
        response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_logout_missing_auth(self, client):
        """Test logout without authorization."""
        response = client.post("/auth/logout")

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["success"] is False

    def test_validate_session_valid(self, client, session_id):
        """Test validating a valid session."""
        response = client.get(
            "/auth/validate",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["valid"] is True
        assert data["username"] == "testuser"
        assert "player_id" in data

    def test_validate_session_invalid(self, client):
        """Test validating an invalid session."""
        response = client.get(
            "/auth/validate",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["valid"] is False


class TestWorldRoutes:
    """Test world navigation endpoints."""

    def test_get_current_room_without_auth(self, client):
        """Test getting room without authentication."""
        response = client.get("/world/")

        assert response.status_code == 401

    def test_get_current_room_with_invalid_session(self, client):
        """Test getting room with invalid session."""
        response = client.get(
            "/world/",
            headers={"Authorization": "Bearer invalid_session"},
        )

        assert response.status_code == 401

    def test_move_player_without_auth(self, client):
        """Test moving without authentication."""
        response = client.post(
            "/world/move",
            data=json.dumps({"direction": "north"}),
            content_type="application/json",
        )

        assert response.status_code == 401

    def test_move_player_missing_direction(self, client, session_id):
        """Test moving without direction."""
        response = client.post(
            "/world/move",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400

    def test_get_tile_missing_coordinates(self, client, session_id):
        """Test getting tile without coordinates."""
        response = client.get(
            "/world/tile",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400


class TestPlayerRoutes:
    """Test player status endpoints."""

    def test_get_status_without_auth(self, client):
        """Test getting status without authentication."""
        response = client.get("/player/status")

        assert response.status_code == 401

    def test_get_stats_without_auth(self, client):
        """Test getting stats without authentication."""
        response = client.get("/player/stats")

        assert response.status_code == 401


class TestInventoryRoutes:
    """Test inventory endpoints."""

    def test_get_inventory_without_auth(self, client):
        """Test getting inventory without authentication."""
        response = client.get("/inventory/")

        assert response.status_code == 401

    def test_take_item_without_auth(self, client):
        """Test taking item without authentication."""
        response = client.post(
            "/inventory/take",
            data=json.dumps({"item_id": "item_123"}),
            content_type="application/json",
        )

        assert response.status_code == 401


class TestEquipmentRoutes:
    """Test equipment endpoints."""

    def test_get_equipment_without_auth(self, client):
        """Test getting equipment without authentication."""
        response = client.get("/equipment/")

        assert response.status_code == 401


class TestCombatRoutes:
    """Test combat endpoints."""

    def test_start_combat_without_auth(self, client):
        """Test starting combat without authentication."""
        response = client.post(
            "/combat/start",
            data=json.dumps({"enemy_id": "enemy_001"}),
            content_type="application/json",
        )

        assert response.status_code == 401


class TestSavesRoutes:
    """Test save/load endpoints."""

    def test_list_saves_without_auth(self, client):
        """Test listing saves without authentication."""
        response = client.get("/saves/")

        assert response.status_code == 401

    def test_create_save_without_auth(self, client):
        """Test creating save without authentication."""
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "My Save"}),
            content_type="application/json",
        )

        assert response.status_code == 401
