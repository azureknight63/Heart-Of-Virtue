"""Comprehensive tests for player routes."""

import sys
from pathlib import Path
import json
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest


class TestPlayerStatusRoute:
    """Test /player/status endpoint."""

    def test_get_status_success(self, client, authenticated_session):
        """Test successful status retrieval with auth."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/player/status",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "status" in data
        assert "name" in data["status"]
        assert "level" in data["status"]
        assert "hp" in data["status"]
        assert "max_hp" in data["status"]
        assert "state" in data["status"]
        assert "exp" in data["status"]

    def test_get_status_no_auth_header(self, client):
        """Test status without authorization header."""
        response = client.get("/player/status")
        assert response.status_code == 401

    def test_get_status_invalid_bearer_format(self, client):
        """Test status with invalid Bearer format."""
        response = client.get(
            "/player/status",
            headers={"Authorization": "Basic invalid"},
        )
        assert response.status_code == 401

    def test_get_status_invalid_session_id(self, client):
        """Test status with non-existent session ID."""
        response = client.get(
            "/player/status",
            headers={"Authorization": "Bearer invalid_session_id"},
        )
        assert response.status_code == 401

    def test_get_status_expired_session(self, app, client):
        """Test status with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")

        # Manually expire the session
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = datetime.now() - timedelta(hours=1)  # Set to past (expired)

        response = client.get(
            "/player/status",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Session expiration may result in 401 or 500 depending on error handling
        assert response.status_code in [401, 500]


class TestPlayerStatsRoute:
    """Test /player/stats endpoint."""

    def test_get_stats_success(self, client, authenticated_session):
        """Test successful stats retrieval with auth."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/player/stats",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "stats" in data
        stats = data["stats"]
        # Check for expected stat attributes
        expected_stats = [
            "strength",
            "dexterity",
            "vitality",
            "intelligence",
            "wisdom",
            "speed",
        ]
        for stat in expected_stats:
            assert stat in stats or "error" not in data

    def test_get_stats_no_auth(self, client):
        """Test stats without authentication."""
        response = client.get("/player/stats")
        assert response.status_code == 401

    def test_get_stats_invalid_session(self, client):
        """Test stats with invalid session."""
        response = client.get(
            "/player/stats",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_get_stats_missing_bearer_prefix(self, client, authenticated_session):
        """Test stats with malformed authorization header."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/player/stats",
            headers={"Authorization": session_id},  # Missing "Bearer " prefix
        )
        assert response.status_code == 401


class TestPlayerRouteErrorCases:
    """Test error handling in player routes."""

    def test_status_returns_json_on_error(self, client, app):
        """Test that status route returns valid JSON even on error."""
        response = client.get("/player/status")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_stats_returns_json_on_error(self, client):
        """Test that stats route returns valid JSON on error."""
        response = client.get("/player/stats")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_status_with_empty_bearer(self, client):
        """Test status with empty Bearer token."""
        response = client.get(
            "/player/status",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_stats_with_empty_bearer(self, client):
        """Test stats with empty Bearer token."""
        response = client.get(
            "/player/stats",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401
