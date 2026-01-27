import pytest
import uuid
import json
import asyncio
from src.api.services.auth_service import auth_service
from src.api.db import db

@pytest.mark.asyncio
class TestCloudIntegration:
    """Integration tests for Cloud Authentication and Save System."""

    def setup_method(self, method):
        """Initialize test variables."""
        self.test_user_prefix = "test_cloud_user_"
        self.test_username = f"{self.test_user_prefix}{uuid.uuid4().hex[:8]}"
        self.test_password = "SecurePassword123!@#" # > 16 chars
        self.test_email = "test@example.com"

    async def teardown_method(self, method):
        """Clean up test data."""
        try:
            sql_get_user = "SELECT id FROM users WHERE username = ?"
            res = await db.execute(sql_get_user, [self.test_username])
            if res.rows:
                user_id = res.rows[0][0]
                await db.execute("DELETE FROM saves WHERE user_id = ?", [user_id])
                await db.execute("DELETE FROM users WHERE id = ?", [user_id])
        except Exception as e:
            print(f"Teardown error: {e}")

    async def test_user_lifecycle_and_saves(self, client, app):
        """Test registration, login, and cloud save persistence."""
        
        # 1. Test Registration
        reg_payload = {
            "username": self.test_username,
            "password": self.test_password,
            "email": self.test_email
        }
        # Correct URL with /api prefix
        response = client.post("/api/auth/register", json=reg_payload)
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        session_id = data["data"]["session_id"]
        assert session_id is not None

        # 2. Verify User ID in session
        session = app.session_manager.get_session(session_id)
        assert session is not None
        assert hasattr(session, "db_user_id")
        user_id = session.db_user_id

        # 3. Test Manual Save
        save_name = "Cloud Test Save"
        headers = {"Authorization": f"Bearer {session_id}"}
        save_resp = client.post("/api/saves", json={"name": save_name}, headers=headers)
        assert save_resp.status_code == 201
        save_data = save_resp.get_json()
        save_id = save_data["save_id"]

        # 4. Test List Saves
        list_resp = client.get("/api/saves", headers=headers)
        assert list_resp.status_code == 200
        saves_data = list_resp.get_json()
        assert len(saves_data["saves"]) >= 1
        # Find our manual save
        manual_saves = [s for s in saves_data["saves"] if s["name"] == save_name]
        assert len(manual_saves) == 1
        assert manual_saves[0]["is_autosave"] is False

        # 5. Test Autosave
        auto_resp1 = client.post("/api/saves", json={"is_autosave": True}, headers=headers)
        assert auto_resp1.status_code == 201
        
        # Perform second autosave (should UPSERT)
        auto_resp2 = client.post("/api/saves", json={"is_autosave": True}, headers=headers)
        assert auto_resp2.status_code == 201
        
        # List again
        list_resp2 = client.get("/api/saves", headers=headers)
        saves_data2 = list_resp2.get_json()
        autosave_recs = [s for s in saves_data2["saves"] if s["is_autosave"]]
        assert len(autosave_recs) == 1

        # 6. Test Login (Persistence check)
        login_payload = {
            "username": self.test_username,
            "password": self.test_password
        }
        login_resp = client.post("/api/auth/login", json=login_payload)
        assert login_resp.status_code == 200
        new_session_id = login_resp.get_json()["data"]["session_id"]
        
        # Verify new session access
        new_headers = {"Authorization": f"Bearer {new_session_id}"}
        list_resp3 = client.get("/api/saves", headers=new_headers)
        assert list_resp3.status_code == 200
        assert len(list_resp3.get_json()["saves"]) >= 2

        # 7. Test Load Game
        load_resp = client.post(f"/api/saves/{save_id}/load", headers=new_headers)
        assert load_resp.status_code == 200
        assert load_resp.get_json()["success"] is True

    async def test_auth_validations(self, client):
        """Test username/password security constraints."""
        
        # Short Username
        short_user = {
            "username": "abc", # < 4
            "password": "Password123!@#456",
            "email": "test@test.com"
        }
        resp1 = client.post("/api/auth/register", json=short_user)
        assert resp1.status_code == 400
        assert "at least 4 characters" in resp1.get_json()["message"]

        # Short Password
        short_pass = {
            "username": f"valid_{uuid.uuid4().hex[:4]}",
            "password": "short", # < 16
            "email": "test@test.com"
        }
        resp2 = client.post("/api/auth/register", json=short_pass)
        assert resp2.status_code == 400
        assert "at least 16 characters" in resp2.get_json()["message"]
