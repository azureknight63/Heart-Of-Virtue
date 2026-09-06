"""Comprehensive tests for combat routes."""

import sys
from pathlib import Path
import json
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent


class TestCombatStartRoute:
    """Test POST /combat/start endpoint."""

    def test_start_combat_missing_enemy_id(self, client, authenticated_session):
        """Test combat start without enemy_id."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/combat/start",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data or "Missing" in data.get("error", "")

    def test_start_combat_no_auth(self, client):
        """Test combat start without authentication."""
        response = client.post(
            "/api/combat/start",
            data=json.dumps({"enemy_id": "enemy_001"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_start_combat_invalid_session(self, client):
        """Test combat start with invalid session."""
        response = client.post(
            "/api/combat/start",
            data=json.dumps({"enemy_id": "enemy_001"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session_id"},
        )
        assert response.status_code == 401

    def test_start_combat_expired_session(self, app, client):
        """Test combat start with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = datetime.now() - timedelta(hours=1)

        response = client.post(
            "/api/combat/start",
            data=json.dumps({"enemy_id": "enemy_001"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Deterministically 401: resolve_session answers "Session not found or
        # already expired" (src/api/middleware/auth.py:84) for an unknown or
        # expired session id. The only 500 on that path is a missing session
        # manager -- a server fault, not an auth outcome -- so accepting 500
        # here would let a real regression that leaked one through pass.
        assert response.status_code == 401

    def test_start_combat_with_valid_enemy_id(self, client, authenticated_session):
        """Test combat start with valid enemy_id format."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/combat/start",
            data=json.dumps({"enemy_id": "enemy_001"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # A well-formed request naming an enemy that is not here is an in-game
        # condition, not a bad request: the route deliberately reserves 4xx for
        # structural/auth errors and answers game-logic refusals with
        # 200 + success=false. (`>= 200`, which this used to assert, is true of
        # every HTTP status there is.)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]


class TestCombatMoveRoute:
    """Test POST /combat/move endpoint."""

    def test_combat_move_missing_move_type(self, client, authenticated_session):
        """Test combat move without move_type."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/combat/move",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # A missing move_type IS a structural error, so this one is a real 400.
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"] == "Missing move_type"

    def test_combat_move_no_auth(self, client):
        """Test combat move without authentication."""
        response = client.post(
            "/api/combat/move",
            data=json.dumps({"move_type": "attack"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_combat_move_invalid_session(self, client):
        """Test combat move with invalid session."""
        response = client.post(
            "/api/combat/move",
            data=json.dumps({"move_type": "attack"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_combat_move_with_valid_move_type(self, client, authenticated_session):
        """Test combat move with valid move type."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/combat/move",
            data=json.dumps({"move_type": "attack"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Same contract as start_combat: no combat is active, which is an
        # in-game condition, so 200 + success=false rather than a 4xx.
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]

    def test_combat_move_with_multiple_params(self, client, authenticated_session):
        """Test combat move with multiple parameters."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/combat/move",
            data=json.dumps(
                {
                    "move_type": "attack",
                    "move_id": "move_001",
                    "target_id": "enemy_001",
                }
            ),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Same contract as start_combat: no combat is active, which is an
        # in-game condition, so 200 + success=false rather than a 4xx.
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]


class TestCombatStatusRoute:
    """Test GET /combat/status endpoint."""

    def test_get_combat_status_success(self, client, authenticated_session):
        """Test getting combat status with auth."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/api/combat/status",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        # Nothing is fighting yet, so the flag the client polls must say so.
        assert data["combat_active"] is False

    def test_get_combat_status_no_auth(self, client):
        """Test combat status without authentication."""
        response = client.get("/api/combat/status")
        assert response.status_code == 401

    def test_get_combat_status_invalid_session(self, client):
        """Test combat status with invalid session."""
        response = client.get(
            "/api/combat/status",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_get_combat_status_expired_session(self, app, client):
        """Test combat status with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = datetime.now() - timedelta(hours=1)

        response = client.get(
            "/api/combat/status",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Deterministically 401: resolve_session answers "Session not found or
        # already expired" (src/api/middleware/auth.py:84) for an unknown or
        # expired session id. The only 500 on that path is a missing session
        # manager -- a server fault, not an auth outcome -- so accepting 500
        # here would let a real regression that leaked one through pass.
        assert response.status_code == 401


class TestCombatErrorCases:
    """Test error handling in combat routes."""

    def test_start_combat_returns_json(self, client):
        """Test that start_combat returns JSON on error."""
        response = client.post(
            "/api/combat/start",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_combat_move_returns_json(self, client):
        """Test that combat_move returns JSON on error."""
        response = client.post(
            "/api/combat/move",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_combat_status_returns_json(self, client):
        """Test that combat_status returns JSON on error."""
        response = client.get("/api/combat/status")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_start_combat_with_empty_bearer(self, client):
        """Test start_combat with empty Bearer token."""
        response = client.post(
            "/api/combat/start",
            data=json.dumps({"enemy_id": "enemy_001"}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_combat_move_with_empty_bearer(self, client):
        """Test combat_move with empty Bearer token."""
        response = client.post(
            "/api/combat/move",
            data=json.dumps({"move_type": "attack"}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_combat_status_with_empty_bearer(self, client):
        """Test combat_status with empty Bearer token."""
        response = client.get(
            "/api/combat/status",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_start_combat_malformed_json(self, client, authenticated_session):
        """Malformed JSON is a 400 from the missing-field check, never a 500.

        Both routes read the body with ``get_json(silent=True)``, so an
        unparseable body is indistinguishable from an empty one and lands on
        the required-field check. ``>= 400`` was satisfied by the 500 these
        tests exist to catch.
        """
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/combat/start",
            data="not valid json",
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"] == "Missing enemy_id"

    def test_combat_move_malformed_json(self, client, authenticated_session):
        """Malformed JSON on the move route is likewise a 400."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/api/combat/move",
            data="not valid json",
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"] == "Missing move_type"
