"""Integration tests for API routes."""

import sys
from pathlib import Path
import json
from unittest.mock import AsyncMock, patch

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent


import pytest


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
        """Test successful login.

        Login requires real credentials (there is no guest mode), so the
        database-backed authentication is stubbed and everything downstream of
        it -- session creation, response envelope, cookie -- runs for real.
        """
        mock_user = {"id": "user_001", "username": "testuser", "timezone": "UTC"}
        with patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            response = client.post(
                "/api/auth/login",
                data=json.dumps({"username": "testuser", "password": "secret"}),
                content_type="application/json",
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "session_id" in data["data"]
        # The session id also travels in an HttpOnly cookie (issue #493).
        assert "hov_session" in response.headers.get("Set-Cookie", "")

    def test_login_missing_username(self, client):
        """Test login without username."""
        response = client.post(
            "/api/auth/login",
            data=json.dumps({"password": "secret"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_login_missing_password(self, client):
        """Test login without password."""
        response = client.post(
            "/api/auth/login",
            data=json.dumps({"username": "testuser"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_register_short_username(self, client):
        """Test registration with a too-short username.

        Username-length validation lives in ``auth_service.create_user``, i.e.
        on registration. Login has never validated it -- a login posting only a
        short username 400s for the missing password, so asserting it there
        proved nothing.
        """
        response = client.post(
            "/api/auth/register",
            data=json.dumps(
                {
                    "username": "a",
                    "password": "a-sufficiently-long-password",
                    "email": "a@example.com",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"] == "validation_error"
        assert "at least 4 characters" in data["message"]

    def test_logout_success(self, client, session_id):
        """Test successful logout."""
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_logout_missing_auth(self, client):
        """Logout without credentials still succeeds and clears the cookie.

        Deliberate since issue #493: logout is NOT behind @require_auth, so a
        browser pinned to an expired/unknown session can still clear it. See
        the comment in ``routes/auth.logout``.
        """
        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "hov_session" in response.headers.get("Set-Cookie", "")

    def test_validate_session_valid(self, client, session_id):
        """Test validating a valid session."""
        response = client.get(
            "/api/auth/validate",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["valid"] is True
        # `username` is not part of the success contract (see the route's own
        # docstring) -- only the failure body carries a null one.
        assert data["player_id"] is not None

    def test_validate_session_invalid(self, client):
        """Test validating an invalid session."""
        response = client.get(
            "/api/auth/validate",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["valid"] is False


class TestWorldRoutes:
    """Test world navigation endpoints."""

    def test_get_current_room_without_auth(self, client):
        """Test getting room without authentication."""
        response = client.get("/api/world/")

        assert response.status_code == 401

    def test_get_current_room_with_invalid_session(self, client):
        """Test getting room with invalid session."""
        response = client.get(
            "/api/world/",
            headers={"Authorization": "Bearer invalid_session"},
        )

        assert response.status_code == 401

    def test_move_player_without_auth(self, client):
        """Test moving without authentication."""
        response = client.post(
            "/api/world/move",
            data=json.dumps({"direction": "north"}),
            content_type="application/json",
        )

        assert response.status_code == 401

    def test_move_player_missing_direction(self, client, session_id):
        """Test moving without direction."""
        response = client.post(
            "/api/world/move",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400

    def test_get_tile_missing_coordinates(self, client, session_id):
        """Test getting tile without coordinates."""
        response = client.get(
            "/api/world/tile",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400

    def test_get_current_room_success(self, client, session_id):
        """Test getting current room successfully."""
        response = client.get(
            "/api/world/",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "room" in data
        room = data["room"]
        assert "x" in room
        assert "y" in room
        assert "name" in room
        assert "description" in room
        assert "exits" in room or isinstance(room.get("exits"), dict)
        # Verify room contents are returned
        assert "items" in room
        assert "npcs" in room
        assert "objects" in room
        assert isinstance(room["items"], list)
        assert isinstance(room["npcs"], list)
        assert isinstance(room["objects"], list)
        # Verify items have announce field
        for item in room["items"]:
            assert "name" in item
            # ItemSerializer emits `count`, never `quantity` -- real engine
            # items only carry `count`.
            assert "count" in item
            assert "announce" in item
        # Verify NPCs have idle_message field
        for npc in room["npcs"]:
            assert "name" in npc
            assert "level" in npc
            assert "idle_message" in npc
        # Verify objects have idle_message field
        for obj in room["objects"]:
            assert "name" in obj
            assert "idle_message" in obj

    def test_move_player_north_success(self, client, session_id):
        """Test moving player east successfully (valid from (1,1))."""
        response = client.post(
            "/api/world/move",
            data=json.dumps({"direction": "east"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "new_position" in data
        assert "room" in data
        assert "events_triggered" in data

    def test_move_player_invalid_direction(self, client, session_id):
        """Test moving in an invalid direction."""
        response = client.post(
            "/api/world/move",
            data=json.dumps({"direction": "north"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data

    def test_move_player_case_insensitive(self, client, session_id):
        """Test that direction is case-insensitive."""
        response = client.post(
            "/api/world/move",
            data=json.dumps({"direction": "EAST"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_get_tile_success(self, client, session_id):
        """Test getting tile data successfully."""
        response = client.get(
            "/api/world/tile?x=1&y=1",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "tile" in data
        tile = data["tile"]
        assert tile["x"] == 1
        assert tile["y"] == 1
        assert "name" in tile
        assert "description" in tile
        assert "items" in tile
        assert "npcs" in tile
        assert isinstance(tile["items"], list)
        assert isinstance(tile["npcs"], list)

    def test_get_tile_invalid_coordinates(self, client, session_id):
        """Test getting tile with non-integer coordinates."""
        response = client.get(
            "/api/world/tile?x=abc&y=def",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_get_tile_out_of_bounds(self, client, session_id):
        """Test getting tile outside map bounds."""
        response = client.get(
            "/api/world/tile?x=9999&y=9999",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data


class TestPlayerRoutes:
    """Test player status endpoints."""

    def test_get_status_without_auth(self, client):
        """Test getting status without authentication."""
        response = client.get("/api/status")

        assert response.status_code == 401

    def test_get_stats_without_auth(self, client):
        """Test getting stats without authentication."""
        response = client.get("/api/stats")

        assert response.status_code == 401


class TestInventoryRoutes:
    """Test inventory endpoints."""

    def test_get_inventory_without_auth(self, client):
        """Test getting inventory without authentication."""
        response = client.get("/api/inventory")

        assert response.status_code == 401

    def test_take_item_without_auth(self, client):
        """Test taking item without authentication.

        There is no /api/inventory/take route (nor /pickup) -- item pickup goes
        through /api/world/interact (Item.take() / interact_with_target), so
        that is the route the auth check belongs on.
        """
        response = client.post(
            "/api/world/interact",
            data=json.dumps({"target": "item_123", "action": "take"}),
            content_type="application/json",
        )

        assert response.status_code == 401


class TestEquipmentRoutes:
    """Test equipment endpoints."""

    def test_get_equipment_without_auth(self, client):
        """Test getting equipment without authentication."""
        response = client.get("/api/equipment")

        assert response.status_code == 401


class TestCombatRoutes:
    """Test combat endpoints."""

    def test_start_combat_without_auth(self, client):
        """Test starting combat without authentication."""
        response = client.post(
            "/api/combat/start",
            data=json.dumps({"enemy_id": "enemy_001"}),
            content_type="application/json",
        )

        assert response.status_code == 401


class TestSavesRoutes:
    """Test save/load endpoints."""

    def test_list_saves_without_auth(self, client):
        """Test listing saves without authentication."""
        response = client.get("/api/saves")

        assert response.status_code == 401

    def test_create_save_without_auth(self, client):
        """Test creating save without authentication."""
        response = client.post(
            "/api/saves",
            data=json.dumps({"name": "My Save"}),
            content_type="application/json",
        )

        assert response.status_code == 401
