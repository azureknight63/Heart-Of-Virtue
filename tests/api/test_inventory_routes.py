"""
Integration tests for inventory and equipment management routes.

Tests the inventory/equipment endpoints:
- GET /api/inventory - Get full inventory
- GET /api/inventory/examine - Examine single item
- POST /api/inventory/drop - Drop item on ground
- GET /api/equipment - Get equipment status
- POST /api/inventory/equip - Equip an item
- POST /api/inventory/unequip - Unequip an item
- GET /api/inventory/compare - Compare items
- GET /api/inventory/stats - Get player stats

Every URL literal in this file is contract-checked by
``tests/api/test_route_prefix_contract.py``, including the ones in the
``endpoints = [...]`` lists the two require-auth tests loop over: those are
not verb calls, so the guard's second pass reads them as plain literals. A
routeless URL there would 404 for every credential and the "must be 401"
assertions would have been passing against nothing.
- GET /api/inventory/currency - Get currency info
"""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent


import pytest

try:
    from src.api.app import create_app
    from src.api.config import TestingConfig
    from src.api.utils.inventory import get_inventory_list
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestInventoryRoutes:
    """Test inventory route endpoints."""

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        # Create session and get session_id
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    # ========== GET /inventory/ ==========

    def test_get_inventory_success(self, app_and_client):
        """Test getting inventory returns correct structure."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/api/inventory", headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "inventory" in data

    def test_get_inventory_missing_auth(self, app_and_client):
        """Test getting inventory without auth returns 401."""
        response = app_and_client["client"].get("/api/inventory")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    def test_get_inventory_invalid_session(self, app_and_client):
        """Test getting inventory with invalid session returns 401."""
        headers = {"Authorization": "Bearer invalid-session-id"}
        response = app_and_client["client"].get(
            "/api/inventory", headers=headers
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    # ========== GET /inventory/examine ==========

    def test_examine_item_missing_index(self, app_and_client):
        """Test examining item without index parameter returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/api/inventory/examine", headers=headers
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Missing index parameter" in data["error"]

    def test_examine_item_invalid_index(self, app_and_client):
        """Test examining item with invalid index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/api/inventory/examine?index=99", headers=headers
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    # ========== POST /inventory/drop ==========

    def test_drop_item_missing_body(self, app_and_client):
        """Test dropping item without request body returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/api/inventory/drop",
            data=json.dumps({}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    def test_drop_item_invalid_index(self, app_and_client):
        """Test dropping item with invalid index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/api/inventory/drop",
            data=json.dumps({"index": 99}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400

    # ========== GET /inventory/equipment ==========

    def test_get_equipment_success(self, app_and_client):
        """Test getting equipment returns correct structure."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/api/equipment", headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "equipment" in data

    def test_get_equipment_missing_auth(self, app_and_client):
        """Test getting equipment without auth returns 401."""
        response = app_and_client["client"].get("/api/equipment")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    # ========== POST /inventory/equip ==========

    def test_equip_item_missing_body(self, app_and_client):
        """Test equipping item without request body returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/api/inventory/equip",
            data=json.dumps({}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    def test_equip_item_invalid_index(self, app_and_client):
        """Test equipping item with invalid index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/api/inventory/equip",
            data=json.dumps({"index": 99}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400

    # ========== POST /inventory/unequip ==========

    def test_unequip_item_missing_body(self, app_and_client):
        """Test unequipping item without request body returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/api/inventory/unequip",
            data=json.dumps({}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Missing item_id or item_index" in data["error"]

    def test_unequip_item_invalid_index(self, app_and_client):
        """Test unequipping item with an out-of-range index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/api/inventory/unequip",
            data=json.dumps({"item_index": 99}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Item not found in inventory" in data["error"]

    def test_unequip_item_not_equipped(self, app_and_client):
        """Test unequipping an item that is not currently equipped returns 400.

        The API is item-based, not slot-based: the "empty slot" case is
        expressed as unequipping an item whose ``isequipped`` is False.
        """
        headers = self.get_auth_header(app_and_client["session_id"])
        player = app_and_client["session_manager"].get_player(
            app_and_client["session_id"]
        )
        equipped_index = next(
            i
            for i, item in enumerate(get_inventory_list(player))
            if getattr(item, "isequipped", False)
        )

        # First unequip succeeds ...
        first = app_and_client["client"].post(
            "/api/inventory/unequip",
            data=json.dumps({"item_index": equipped_index}),
            headers=headers,
            content_type="application/json"
        )
        assert first.status_code == 200
        assert first.get_json()["success"] is True

        # ... the second one has nothing to unequip.
        response = app_and_client["client"].post(
            "/api/inventory/unequip",
            data=json.dumps({"item_index": equipped_index}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "is not equipped" in data["error"]

    # ========== GET /inventory/compare ==========

    def test_compare_items_missing_candidate(self, app_and_client):
        """Test comparing items without candidate_index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/api/inventory/compare", headers=headers
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Missing candidate_index parameter" in data["error"]

    def test_compare_items_invalid_candidate(self, app_and_client):
        """Test comparing items with invalid candidate index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/api/inventory/compare?candidate_index=99", headers=headers
        )

        assert response.status_code == 400

    # ========== GET /inventory/stats ==========

    def test_get_stats_success(self, app_and_client):
        """Test getting stats returns correct structure."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/api/inventory/stats", headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "stats" in data
        assert "hp" in data["stats"]
        assert "max_hp" in data["stats"]

    def test_get_stats_missing_auth(self, app_and_client):
        """Test getting stats without auth returns 401."""
        response = app_and_client["client"].get("/api/inventory/stats")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    # ========== GET /inventory/currency ==========

    def test_get_currency_success(self, app_and_client):
        """Test getting currency returns correct structure."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/api/inventory/currency", headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "currency" in data
        assert "gold" in data["currency"]

    def test_get_currency_missing_auth(self, app_and_client):
        """Test getting currency without auth returns 401."""
        response = app_and_client["client"].get("/api/inventory/currency")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    # ========== Error handling ==========

    def test_all_get_endpoints_require_auth(self, app_and_client):
        """Test all GET endpoints require authentication."""
        endpoints = [
            "/api/inventory",
            "/api/equipment",
            "/api/inventory/stats",
            "/api/inventory/currency",
        ]

        for path in endpoints:
            response = app_and_client["client"].get(path)
            assert response.status_code == 401, f"Failed for GET {path}"
            data = response.get_json()
            assert data["success"] is False

    def test_all_post_endpoints_require_auth(self, app_and_client):
        """Test all POST endpoints require authentication."""
        endpoints = [
            "/api/inventory/drop",
            "/api/inventory/equip",
            "/api/inventory/unequip",
        ]

        for path in endpoints:
            response = app_and_client["client"].post(path)
            assert response.status_code == 401, f"Failed for POST {path}"
            data = response.get_json()
            assert data["success"] is False
