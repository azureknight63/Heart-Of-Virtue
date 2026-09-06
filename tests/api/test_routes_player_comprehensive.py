"""Comprehensive tests for player routes."""

import sys
from pathlib import Path
import json
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent


class TestPlayerStatusRoute:
    """Test the /api/status endpoint."""

    def test_get_status_success(self, client, authenticated_session):
        """Test successful status retrieval with auth."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/api/status",
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
        response = client.get("/api/status")
        assert response.status_code == 401

    def test_get_status_invalid_bearer_format(self, client):
        """Test status with invalid Bearer format."""
        response = client.get(
            "/api/status",
            headers={"Authorization": "Basic invalid"},
        )
        assert response.status_code == 401

    def test_get_status_invalid_session_id(self, client):
        """Test status with non-existent session ID."""
        response = client.get(
            "/api/status",
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
            "/api/status",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Deterministically 401: resolve_session answers "Session not found or
        # already expired" (src/api/middleware/auth.py:84) for an unknown or
        # expired session id. The only 500 on that path is a missing session
        # manager -- a server fault, not an auth outcome -- so accepting 500
        # here would let a real regression that leaked one through pass.
        assert response.status_code == 401


class TestPlayerStatsRoute:
    """Test the /api/stats endpoint."""

    def test_get_stats_success(self, client, authenticated_session):
        """Test successful stats retrieval with auth."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/api/stats",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "stats" in data
        stats = data["stats"]
        # The engine's attribute set (GameService.get_player_stats); the
        # generic dexterity/vitality/wisdom trio this test used to name has
        # never existed on Player.
        expected_stats = [
            "strength",
            "finesse",
            "speed",
            "endurance",
            "charisma",
            "intelligence",
            "faith",
        ]
        for stat in expected_stats:
            assert stat in stats
            assert stat + "_base" in stats

    def test_get_stats_no_auth(self, client):
        """Test stats without authentication."""
        response = client.get("/api/stats")
        assert response.status_code == 401

    def test_get_stats_invalid_session(self, client):
        """Test stats with invalid session."""
        response = client.get(
            "/api/stats",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_get_stats_missing_bearer_prefix(self, client, authenticated_session):
        """Test stats with malformed authorization header."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/api/stats",
            headers={"Authorization": session_id},  # Missing "Bearer " prefix
        )
        assert response.status_code == 401


class TestPlayerRouteErrorCases:
    """Test error handling in player routes."""

    def test_status_returns_json_on_error(self, client, app):
        """Test that status route returns valid JSON even on error."""
        response = client.get("/api/status")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_stats_returns_json_on_error(self, client):
        """Test that stats route returns valid JSON on error."""
        response = client.get("/api/stats")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_status_with_empty_bearer(self, client):
        """Test status with empty Bearer token."""
        response = client.get(
            "/api/status",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_stats_with_empty_bearer(self, client):
        """Test stats with empty Bearer token."""
        response = client.get(
            "/api/stats",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401
