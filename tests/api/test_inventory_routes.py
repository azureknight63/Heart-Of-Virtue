"""
Integration tests for inventory and equipment management routes.

Tests all 10 inventory endpoints:
- GET /inventory/ - Get full inventory
- GET /inventory/examine - Examine single item
- POST /inventory/take - Take item from ground
- POST /inventory/drop - Drop item on ground
- GET /inventory/equipment - Get equipment status
- POST /inventory/equip - Equip an item
- POST /inventory/unequip - Unequip an item
- GET /inventory/compare - Compare items
- GET /inventory/stats - Get player stats
- GET /inventory/currency - Get currency info
"""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

try:
    from src.api.app import create_app
    from src.api.config import TestingConfig
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
            "/inventory/", headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "inventory" in data

    def test_get_inventory_missing_auth(self, app_and_client):
        """Test getting inventory without auth returns 401."""
        response = app_and_client["client"].get("/inventory/")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    def test_get_inventory_invalid_session(self, app_and_client):
        """Test getting inventory with invalid session returns 401."""
        headers = {"Authorization": "Bearer invalid-session-id"}
        response = app_and_client["client"].get(
            "/inventory/", headers=headers
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    # ========== GET /inventory/examine ==========

    def test_examine_item_missing_index(self, app_and_client):
        """Test examining item without index parameter returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/inventory/examine", headers=headers
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Missing index parameter" in data["error"]

    def test_examine_item_invalid_index(self, app_and_client):
        """Test examining item with invalid index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/inventory/examine?index=99", headers=headers
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    # ========== POST /inventory/take ==========

    def test_take_item_missing_body(self, app_and_client):
        """Test taking item without request body returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/inventory/take",
            data=json.dumps({}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    def test_take_item_invalid_index(self, app_and_client):
        """Test taking item with invalid index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/inventory/take",
            data=json.dumps({"index": 99}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400

    # ========== POST /inventory/drop ==========

    def test_drop_item_missing_body(self, app_and_client):
        """Test dropping item without request body returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/inventory/drop",
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
            "/inventory/drop",
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
            "/inventory/equipment", headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "equipment" in data

    def test_get_equipment_missing_auth(self, app_and_client):
        """Test getting equipment without auth returns 401."""
        response = app_and_client["client"].get("/inventory/equipment")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    # ========== POST /inventory/equip ==========

    def test_equip_item_missing_body(self, app_and_client):
        """Test equipping item without request body returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/inventory/equip",
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
            "/inventory/equip",
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
            "/inventory/unequip",
            data=json.dumps({}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    def test_unequip_item_invalid_slot(self, app_and_client):
        """Test unequipping item with invalid slot returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/inventory/unequip",
            data=json.dumps({"slot": "invalid_slot"}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400

    def test_unequip_item_empty_slot(self, app_and_client):
        """Test unequipping from empty slot returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].post(
            "/inventory/unequip",
            data=json.dumps({"slot": "head"}),
            headers=headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        # Accept either error message (depends on player object structure)
        assert ("No item equipped" in data["error"] or "Invalid slot" in data["error"])

    # ========== GET /inventory/compare ==========

    def test_compare_items_missing_candidate(self, app_and_client):
        """Test comparing items without candidate_index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/inventory/compare", headers=headers
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Missing candidate_index parameter" in data["error"]

    def test_compare_items_invalid_candidate(self, app_and_client):
        """Test comparing items with invalid candidate index returns 400."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/inventory/compare?candidate_index=99", headers=headers
        )

        assert response.status_code == 400

    # ========== GET /inventory/stats ==========

    def test_get_stats_success(self, app_and_client):
        """Test getting stats returns correct structure."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/inventory/stats", headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "stats" in data
        assert "health" in data["stats"]

    def test_get_stats_missing_auth(self, app_and_client):
        """Test getting stats without auth returns 401."""
        response = app_and_client["client"].get("/inventory/stats")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    # ========== GET /inventory/currency ==========

    def test_get_currency_success(self, app_and_client):
        """Test getting currency returns correct structure."""
        headers = self.get_auth_header(app_and_client["session_id"])
        response = app_and_client["client"].get(
            "/inventory/currency", headers=headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "currency" in data
        assert "gold" in data["currency"]

    def test_get_currency_missing_auth(self, app_and_client):
        """Test getting currency without auth returns 401."""
        response = app_and_client["client"].get("/inventory/currency")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    # ========== Error handling ==========

    def test_all_get_endpoints_require_auth(self, app_and_client):
        """Test all GET endpoints require authentication."""
        endpoints = [
            "/inventory/",
            "/inventory/equipment",
            "/inventory/stats",
            "/inventory/currency",
        ]

        for path in endpoints:
            response = app_and_client["client"].get(path)
            assert response.status_code == 401, f"Failed for GET {path}"
            data = response.get_json()
            assert data["success"] is False

    def test_all_post_endpoints_require_auth(self, app_and_client):
        """Test all POST endpoints require authentication."""
        endpoints = [
            "/inventory/take",
            "/inventory/drop",
            "/inventory/equip",
            "/inventory/unequip",
        ]

        for path in endpoints:
            response = app_and_client["client"].post(path)
            assert response.status_code == 401, f"Failed for POST {path}"
            data = response.get_json()
            assert data["success"] is False
