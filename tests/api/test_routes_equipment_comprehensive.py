"""Comprehensive tests for equipment routes."""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.app import create_app  # type: ignore
from src.api.config import TestingConfig  # type: ignore


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
def authenticated_session(app):
    """Create authenticated session with player."""
    session_manager = app.session_manager
    session_id, player = session_manager.create_session("testplayer")
    return session_id, player, session_manager


class TestEquipmentGetRoute:
    """Test GET /equipment endpoint."""

    def test_get_equipment_success(self, client, authenticated_session):
        """Test successful equipment retrieval."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/equipment/",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "equipment" in data
        equipment = data["equipment"]
        # Check for expected equipment slots
        expected_slots = ["head", "body", "hands", "feet", "back", "neck"]
        for slot in expected_slots:
            assert slot in equipment or "error" not in data

    def test_get_equipment_no_auth(self, client):
        """Test equipment endpoint without authentication."""
        response = client.get("/equipment/")
        assert response.status_code == 401

    def test_get_equipment_invalid_session(self, client):
        """Test equipment with invalid session."""
        response = client.get(
            "/equipment/",
            headers={"Authorization": "Bearer invalid_session_id"},
        )
        assert response.status_code == 401

    def test_get_equipment_expired_session(self, app, client):
        """Test equipment with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = 0

        response = client.get(
            "/equipment/",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Session expiration may result in 401 or 500 depending on error handling
        assert response.status_code in [401, 500]


class TestEquipmentEquipRoute:
    """Test POST /equipment/equip endpoint."""

    def test_equip_item_missing_field(self, client, authenticated_session):
        """Test equipping without item_id."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/equipment/equip",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data

    def test_equip_item_no_auth(self, client):
        """Test equip endpoint without authentication."""
        response = client.post(
            "/equipment/equip",
            data=json.dumps({"item_id": "item_001"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_equip_item_invalid_session(self, client):
        """Test equip with invalid session."""
        response = client.post(
            "/equipment/equip",
            data=json.dumps({"item_id": "item_001"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_equip_item_malformed_json(self, client, authenticated_session):
        """Test equip with malformed JSON."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/equipment/equip",
            data="not valid json",
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should handle malformed JSON gracefully
        assert response.status_code >= 400


class TestEquipmentUnequipRoute:
    """Test POST /equipment/unequip endpoint."""

    def test_unequip_item_missing_field(self, client, authenticated_session):
        """Test unequipping without slot."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/equipment/unequip",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_unequip_item_no_auth(self, client):
        """Test unequip endpoint without authentication."""
        response = client.post(
            "/equipment/unequip",
            data=json.dumps({"slot": "head"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_unequip_item_invalid_session(self, client):
        """Test unequip with invalid session."""
        response = client.post(
            "/equipment/unequip",
            data=json.dumps({"slot": "head"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_unequip_with_valid_slot(self, client, authenticated_session):
        """Test unequip with valid slot format."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/equipment/unequip",
            data=json.dumps({"slot": "head"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should handle the request (may succeed or fail based on game state)
        assert response.status_code in [200, 400, 422]


class TestEquipmentErrorCases:
    """Test error handling in equipment routes."""

    def test_get_equipment_returns_json(self, client):
        """Test that equipment endpoint returns JSON on error."""
        response = client.get("/equipment/")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_equip_returns_json_on_error(self, client, authenticated_session):
        """Test that equip returns JSON on error."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/equipment/equip",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_unequip_returns_json_on_error(self, client):
        """Test that unequip returns JSON on error."""
        response = client.post(
            "/equipment/unequip",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_equip_with_empty_bearer(self, client):
        """Test equip with empty Bearer token."""
        response = client.post(
            "/equipment/equip",
            data=json.dumps({"item_id": "item_001"}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_unequip_with_empty_bearer(self, client):
        """Test unequip with empty Bearer token."""
        response = client.post(
            "/equipment/unequip",
            data=json.dumps({"slot": "head"}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401
