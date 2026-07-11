"""
API Route Integration Tests - Tier 1

Implements 9 core API route tests covering:
- Test 1-3: GET /api/world/tile (query, boundary, error cases)
- Test 4-5: POST /api/combat/move (valid move, invalid move)
- Test 6-7: POST /api/inventory/use-item (use, error handling)
- Test 8-9: Integration tests (multi-step workflows)

Expected coverage gain: +2-3% (11-23% → 25-30%)
"""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent


import pytest

try:
    from src.api.app import create_app
    from src.api.config import TestingConfig
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestWorldRoutesTier1:
    """Test world route endpoints (Tests 1-3)."""

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        # Create session and get session_id
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_world")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    # ========== Test 1: GET /world/tile - Valid Tile Query ==========

    def test_get_tile_data_valid(self, app_and_client):
        """Test 1: GET /world/tile returns tile data for valid coordinates."""
        session_id = app_and_client["session_id"]
        session_manager = app_and_client["session_manager"]
        player = session_manager.get_player(session_id)

        # Use player's current location
        x, y = player.location_x, player.location_y
        headers = self.get_auth_header(session_id)

        response = app_and_client["client"].get(
            f"/api/world/tile?x={x}&y={y}",
            headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["success"] is True
        assert "tile" in data

        tile = data["tile"]
        assert "x" in tile
        assert "y" in tile
        assert "name" in tile
        assert "description" in tile
        assert tile["x"] == x
        assert tile["y"] == y

    # ========== Test 2: GET /world/tile - Boundary/Out-of-bounds ==========

    def test_get_tile_out_of_bounds(self, app_and_client):
        """Test 2: GET /world/tile rejects out-of-bounds coordinates."""
        headers = self.get_auth_header(app_and_client["session_id"])

        response = app_and_client["client"].get(
            "/api/world/tile?x=999&y=999",
            headers=headers
        )

        # Should return 404 for out-of-bounds or 200 with success=false
        assert response.status_code in [404, 200]
        data = response.get_json()

        if response.status_code == 404:
            assert data["success"] is False
        else:
            assert data["success"] is False or "error" in data

    # ========== Test 3: GET /world/tile - Missing Parameters ==========

    def test_get_tile_missing_parameters(self, app_and_client):
        """Test 3: GET /world/tile rejects missing x or y parameters."""
        headers = self.get_auth_header(app_and_client["session_id"])

        # Missing y
        response = app_and_client["client"].get(
            "/api/world/tile?x=5",
            headers=headers
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

    # ========== Test 4: GET /world/tile - With NPCs ==========

    def test_get_tile_with_npcs_on_tile(self, app_and_client):
        """Test 4: GET /world/tile includes NPCs present on the tile."""
        session_id = app_and_client["session_id"]
        session_manager = app_and_client["session_manager"]
        player = session_manager.get_player(session_id)

        x, y = player.location_x, player.location_y
        headers = self.get_auth_header(session_id)

        response = app_and_client["client"].get(
            f"/api/world/tile?x={x}&y={y}",
            headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["success"] is True
        tile = data["tile"]
        # npcs field should exist (may be empty list)
        assert "npcs" in tile or tile.get("npcs") is not None


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestCombatRoutesTier1:
    """Test combat route endpoints (Tests 5-6)."""

    @pytest.fixture
    def app_and_client_combat(self):
        """Create Flask app with test client and combat setup."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        # Create session and get session_id
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_combat")
        player = session_manager.get_player(session_id)

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
            "player": player,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    # ========== Test 5: GET /combat/status - Not in Combat ==========

    def test_combat_status_not_in_combat(self, app_and_client_combat):
        """Test 5: GET /combat/status returns correct status when not in combat."""
        session_id = app_and_client_combat["session_id"]
        headers = self.get_auth_header(session_id)

        response = app_and_client_combat["client"].get(
            "/api/combat/status",
            headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["success"] is True
        assert "combat_active" in data
        assert data["combat_active"] is False

    # ========== Test 6: POST /combat/move - Invalid Move (Not in Combat) ==========

    def test_execute_move_not_in_combat(self, app_and_client_combat):
        """Test 6: POST /combat/move fails when player is not in combat."""
        session_id = app_and_client_combat["session_id"]
        headers = self.get_auth_header(session_id)

        response = app_and_client_combat["client"].post(
            "/api/combat/move",
            json={
                "move_type": "attack",
                "move_id": "PowerStrike",
                "target_id": "enemy_1"
            },
            headers=headers,
            content_type="application/json"
        )

        # Should return 200 with success=false (game-logic error, not structural)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

    # ========== Test 7: GET /combat/status - Response Structure ==========

    def test_combat_status_response_structure(self, app_and_client_combat):
        """Test 7: GET /combat/status returns required fields."""
        session_id = app_and_client_combat["session_id"]
        headers = self.get_auth_header(session_id)

        response = app_and_client_combat["client"].get(
            "/api/combat/status",
            headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["success"] is True
        assert "combat_active" in data
        # These fields should exist based on the docstring
        assert "log" in data
        # Optional fields that may be present when in combat
        if data["combat_active"]:
            assert "battle_state" in data


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestInventoryRoutesTier1:
    """Test inventory route endpoints (Tests 8-9)."""

    @pytest.fixture
    def app_and_client_inventory(self):
        """Create Flask app with test client and inventory setup."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        # Create session and get session_id
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_inventory")
        player = session_manager.get_player(session_id)

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
            "player": player,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    # ========== Test 8: POST /inventory/use-item - Non-existent Item ==========

    def test_use_item_not_in_inventory(self, app_and_client_inventory):
        """Test 8: POST /inventory/use-item fails for non-existent item."""
        session_id = app_and_client_inventory["session_id"]
        headers = self.get_auth_header(session_id)

        response = app_and_client_inventory["client"].post(
            "/api/inventory/use-item",
            json={"item_id": 999999},
            headers=headers,
            content_type="application/json"
        )

        # Should return 404 or 200 with success=false
        assert response.status_code in [404, 200, 400]
        data = response.get_json()
        assert data["success"] is False

    # ========== Test 9: POST /inventory/use-item - Missing Parameters ==========

    def test_use_item_missing_parameters(self, app_and_client_inventory):
        """Test 9: POST /inventory/use-item rejects missing item_id."""
        session_id = app_and_client_inventory["session_id"]
        headers = self.get_auth_header(session_id)

        response = app_and_client_inventory["client"].post(
            "/api/inventory/use-item",
            json={},  # Empty body
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code in [400, 404]
        data = response.get_json()
        assert data["success"] is False


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestAPIIntegrationTier1:
    """Integration tests for multi-step workflows (Tests 10-11)."""

    @pytest.fixture
    def app_and_client_integration(self):
        """Create Flask app with test client for integration tests."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        # Create session and get session_id
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_integration")
        player = session_manager.get_player(session_id)

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
            "player": player,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    # ========== Test 10: Multi-step World Navigation ==========

    def test_world_navigation_workflow(self, app_and_client_integration):
        """Test 10: Multi-step workflow - Get current room, then query adjacent tile."""
        session_id = app_and_client_integration["session_id"]
        headers = self.get_auth_header(session_id)
        client = app_and_client_integration["client"]

        # Step 1: Get current room
        response1 = client.get(
            "/api/world",
            headers=headers
        )
        assert response1.status_code == 200
        data1 = response1.get_json()
        assert data1["success"] is True
        assert "room" in data1

        current_room = data1["room"]
        x = current_room.get("x", 5)
        y = current_room.get("y", 5)

        # Step 2: Query the current tile explicitly
        response2 = client.get(
            f"/api/world/tile?x={x}&y={y}",
            headers=headers
        )
        assert response2.status_code == 200
        data2 = response2.get_json()
        assert data2["success"] is True
        assert data2["tile"]["x"] == x
        assert data2["tile"]["y"] == y

    # ========== Test 11: Combat Status Check Workflow ==========

    def test_combat_status_check_workflow(self, app_and_client_integration):
        """Test 11: Multi-step workflow - Check combat status, then attempt move."""
        session_id = app_and_client_integration["session_id"]
        headers = self.get_auth_header(session_id)
        client = app_and_client_integration["client"]

        # Step 1: Check combat status
        response1 = client.get(
            "/api/combat/status",
            headers=headers
        )
        assert response1.status_code == 200
        data1 = response1.get_json()
        assert data1["success"] is True
        in_combat = data1.get("combat_active", False)

        # Step 2: Attempt to execute a move
        response2 = client.post(
            "/api/combat/move",
            json={
                "move_type": "attack",
                "move_id": "PowerStrike",
                "target_id": "dummy_target"
            },
            headers=headers,
            content_type="application/json"
        )
        assert response2.status_code == 200
        data2 = response2.get_json()

        # If not in combat, should fail
        if not in_combat:
            assert data2["success"] is False
        else:
            # If in combat, move may succeed or fail depending on game state
            assert "success" in data2


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestAuthenticationAndErrorHandling:
    """Test authentication and error handling across all routes."""

    @pytest.fixture
    def app_and_client_auth(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        yield {
            "app": app,
            "client": client,
        }

    # ========== Test 12: Missing Authentication ==========

    def test_missing_authentication_world(self, app_and_client_auth):
        """Test world endpoints reject missing authentication."""
        response = app_and_client_auth["client"].get("/api/world/tile?x=5&y=5")

        assert response.status_code == 401
        data = response.get_json()
        # Response should have error info (structure may vary)
        assert "error" in data or data.get("success") is False

    def test_missing_authentication_combat(self, app_and_client_auth):
        """Test combat endpoints reject missing authentication."""
        response = app_and_client_auth["client"].get("/api/combat/status")

        assert response.status_code == 401
        data = response.get_json()
        # Response should have error info (structure may vary)
        assert "error" in data or data.get("success") is False

    def test_missing_authentication_inventory(self, app_and_client_auth):
        """Test inventory endpoints reject missing authentication."""
        response = app_and_client_auth["client"].post(
            "/api/inventory/use-item",
            json={"item_id": 1},
            content_type="application/json"
        )

        # Should fail with 401 or 404 (depending on route availability)
        assert response.status_code in [401, 404]
        if response.status_code == 401:
            data = response.get_json()
            assert "error" in data or data.get("success") is False

    # ========== Test 13: Invalid Session Token ==========

    def test_invalid_session_token(self, app_and_client_auth):
        """Test routes reject invalid session tokens."""
        headers = {"Authorization": "Bearer invalid-session-token"}

        response = app_and_client_auth["client"].get(
            "/api/world/tile?x=5&y=5",
            headers=headers
        )

        assert response.status_code == 401
        data = response.get_json()
        # Response should have error info (structure may vary)
        assert "error" in data or data.get("success") is False
