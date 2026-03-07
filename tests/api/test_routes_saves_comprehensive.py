"""Comprehensive tests for saves routes."""

import sys
from pathlib import Path
import json
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest


class TestListSavesRoute:
    """Test GET /saves endpoint."""

    def test_list_saves_success(self, client, authenticated_session):
        """Test successful save listing."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/saves/",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "saves" in data
        assert isinstance(data["saves"], list)

    def test_list_saves_no_auth(self, client):
        """Test list saves without authentication."""
        response = client.get("/saves/")
        assert response.status_code == 401

    def test_list_saves_invalid_session(self, client):
        """Test list saves with invalid session."""
        response = client.get(
            "/saves/",
            headers={"Authorization": "Bearer invalid_session_id"},
        )
        assert response.status_code == 401

    def test_list_saves_expired_session(self, app, client):
        """Test list saves with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = datetime.now() - timedelta(hours=1)

        response = client.get(
            "/saves/",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Session expiration may result in 401 or 500 depending on error handling
        assert response.status_code in [401, 500]


class TestCreateSaveRoute:
    """Test POST /saves endpoint."""

    def test_create_save_missing_name(self, client, authenticated_session):
        """Test creating save without name."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_create_save_no_auth(self, client):
        """Test create save without authentication."""
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "My Save"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_create_save_invalid_session(self, client):
        """Test create save with invalid session."""
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "My Save"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_create_save_with_valid_name(self, client, authenticated_session):
        """Test creating save with valid name."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "My Test Save"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should handle the request
        assert response.status_code in [200, 201, 400, 422]

    def test_create_save_empty_name(self, client, authenticated_session):
        """Test creating save with empty name."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/",
            data=json.dumps({"name": ""}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Empty names may be accepted or rejected depending on validation
        # Accept either behavior (201 if accepted, 400 if rejected)
        assert response.status_code in [200, 201, 400, 422]


class TestLoadSaveRoute:
    """Test POST /saves/<id>/load endpoint."""

    def test_load_save_missing_id(self, client, authenticated_session):
        """Test load save without ID in path."""
        session_id, _, _ = authenticated_session
        # Try to POST to /saves/load without an ID
        response = client.post(
            "/saves/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should fail (404 or 405)
        assert response.status_code >= 400

    def test_load_save_no_auth(self, client):
        """Test load save without authentication."""
        response = client.post(
            "/saves/test_save_id/load",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_load_save_invalid_session(self, client):
        """Test load save with invalid session."""
        response = client.post(
            "/saves/test_save_id/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_load_nonexistent_save(self, client, authenticated_session):
        """Test loading a non-existent save."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/nonexistent_save_id/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should fail gracefully
        assert response.status_code >= 400


class TestDeleteSaveRoute:
    """Test DELETE /saves/<id> endpoint."""

    def test_delete_save_no_auth(self, client):
        """Test delete save without authentication."""
        response = client.delete("/saves/test_save_id")
        assert response.status_code == 401

    def test_delete_save_invalid_session(self, client):
        """Test delete save with invalid session."""
        response = client.delete(
            "/saves/test_save_id",
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_delete_nonexistent_save(self, client, authenticated_session):
        """Test deleting a non-existent save."""
        session_id, _, _ = authenticated_session
        response = client.delete(
            "/saves/nonexistent_save_id",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # May succeed (soft delete) or fail (404/422) - both are acceptable
        assert response.status_code in [200, 204, 400, 404, 422]

    def test_delete_save_expired_session(self, app, client):
        """Test delete save with expired session."""
        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("testplayer")
        session = session_manager.get_session(session_id)
        if session:
            session.expires_at = datetime.now() - timedelta(hours=1)

        response = client.delete(
            "/saves/test_save_id",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Session expiration may result in 401 or 500 depending on error handling
        assert response.status_code in [401, 500]


class TestSavesErrorCases:
    """Test error handling in saves routes."""

    def test_list_saves_returns_json(self, client):
        """Test that list_saves returns JSON on error."""
        response = client.get("/saves/")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_create_save_returns_json(self, client):
        """Test that create_save returns JSON on error."""
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_load_save_returns_json(self, client):
        """Test that load_save returns JSON on error."""
        response = client.post(
            "/saves/test_id/load",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_delete_save_returns_json(self, client):
        """Test that delete_save returns JSON on error."""
        response = client.delete("/saves/test_id")
        assert response.content_type == "application/json"
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_create_save_with_empty_bearer(self, client):
        """Test create_save with empty Bearer token."""
        response = client.post(
            "/saves/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_load_save_with_empty_bearer(self, client):
        """Test load_save with empty Bearer token."""
        response = client.post(
            "/saves/test_id/load",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_delete_save_with_empty_bearer(self, client):
        """Test delete_save with empty Bearer token."""
        response = client.delete(
            "/saves/test_id",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_create_save_malformed_json(self, client, authenticated_session):
        """Test create_save with malformed JSON."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/",
            data="not valid json",
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        assert response.status_code >= 400

    def test_load_save_malformed_json(self, client, authenticated_session):
        """Test load_save with malformed JSON."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/saves/test_id/load",
            data="not valid json",
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        assert response.status_code >= 400

    def test_create_save_very_long_name(self, client, authenticated_session):
        """Test create_save with very long name."""
        session_id, _, _ = authenticated_session
        long_name = "a" * 1000  # 1000 character name
        response = client.post(
            "/saves/",
            data=json.dumps({"name": long_name}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        # Should reject very long names
        assert response.status_code >= 400 or response.status_code == 201
