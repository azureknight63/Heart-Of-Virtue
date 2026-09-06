"""Comprehensive tests for equipment routes."""

import sys
from pathlib import Path
import json
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent


class TestEquipmentGetRoute:
    """Test the GET /api/equipment endpoint."""

    def test_get_equipment_success(self, client, authenticated_session):
        """Test successful equipment retrieval."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/api/equipment",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "equipment" in data
        equipment = data["equipment"]
        # EquipmentSerializer emits a fixed envelope; `equipped` only carries
        # slots that actually hold an item (see _collect_equipped_items), so
        # assert the envelope and that every emitted slot is a known one.
        assert set(equipment) == {
            "equipped",
            "unequipped_equippable_count",
            "total_stat_bonuses",
            "equipment_value",
        }
        known_slots = {"weapon", "body", "head", "hands", "feet"}
        for slot in equipment["equipped"]:
            assert slot in known_slots or slot.startswith("accessory_")
        assert isinstance(equipment["unequipped_equippable_count"], int)
        assert isinstance(equipment["total_stat_bonuses"], dict)

    def test_get_equipment_no_auth(self, client):
        """Test equipment endpoint without authentication."""
        response = client.get("/api/equipment")
        assert response.status_code == 401

    def test_get_equipment_invalid_session(self, client):
        """Test equipment with invalid session."""
        response = client.get(
            "/api/equipment",
            headers={"Authorization": "Bearer invalid_session_id"},
        )
        assert response.status_code == 401

    def test_get_equipment_expired_session(self, app, client):
        """Test equipment with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = datetime.now() - timedelta(hours=1)

        response = client.get(
            "/api/equipment",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Deterministically 401: resolve_session answers "Session not found or
        # already expired" (src/api/middleware/auth.py:84) for an unknown or
        # expired session id. The only 500 on that path is a missing session
        # manager -- a server fault, not an auth outcome -- so accepting 500
        # here would let a real regression that leaked one through pass.
        assert response.status_code == 401


class TestEquipmentErrorCases:
    """Test error handling in equipment routes."""

    def test_get_equipment_returns_json(self, client):
        """Test that equipment endpoint returns JSON on error."""
        response = client.get("/api/equipment")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)
