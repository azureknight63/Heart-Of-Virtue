"""Tests for SessionManager."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.services.session_manager import SessionManager, Session  # type: ignore


class TestSession:
    """Test Session class."""

    def test_session_creation(self):
        """Test creating a new session."""
        session = Session("sess_123", "player_456", "testuser", datetime.now())

        assert session.session_id == "sess_123"
        assert session.player_id == "player_456"
        assert session.username == "testuser"
        assert not session.is_expired()

    def test_session_expiration(self):
        """Test session expiration."""
        past_time = datetime.now() - timedelta(days=2)
        session = Session("sess_123", "player_456", "testuser", past_time)

        assert session.is_expired()

    def test_session_update_access_time(self):
        """Test updating session access time."""
        now = datetime.now()
        session = Session("sess_123", "player_456", "testuser", now)
        original_expires = session.expires_at

        # Wait a tiny bit and update
        import time

        time.sleep(0.01)
        session.update_access_time()

        assert session.last_accessed > now
        assert session.expires_at > original_expires

    def test_session_to_dict(self):
        """Test converting session to dictionary."""
        session = Session("sess_123", "player_456", "testuser", datetime.now())
        session_dict = session.to_dict()

        assert session_dict["session_id"] == "sess_123"
        assert session_dict["player_id"] == "player_456"
        assert session_dict["username"] == "testuser"
        assert "created_at" in session_dict
        assert "expires_at" in session_dict


class TestSessionManager:
    """Test SessionManager class."""

    def test_create_session(self):
        """Test creating a new session."""
        manager = SessionManager()

        session_id, player_id = manager.create_session("testuser")

        assert session_id is not None
        assert player_id is not None
        assert session_id != player_id

    def test_get_session_valid(self):
        """Test retrieving a valid session."""
        manager = SessionManager()
        session_id, _ = manager.create_session("testuser")

        session = manager.get_session(session_id)

        assert session is not None
        assert session.session_id == session_id
        assert session.username == "testuser"

    def test_get_session_invalid(self):
        """Test retrieving an invalid session."""
        manager = SessionManager()

        session = manager.get_session("invalid_id")

        assert session is None

    def test_get_session_expired(self):
        """Test that expired sessions return None."""
        manager = SessionManager()
        session_id, _ = manager.create_session("testuser")

        # Manually expire the session
        session = manager.sessions[session_id]
        session.expires_at = datetime.now() - timedelta(hours=1)

        result = manager.get_session(session_id)

        assert result is None
        assert session_id not in manager.sessions

    def test_get_player(self):
        """Test retrieving a player from a session."""
        manager = SessionManager()
        session_id, player_id = manager.create_session("testuser")

        # Set a dummy player
        manager.players[player_id] = "dummy_player_object"

        player = manager.get_player(session_id)

        assert player == "dummy_player_object"

    def test_get_player_invalid_session(self):
        """Test getting player from invalid session."""
        manager = SessionManager()

        player = manager.get_player("invalid_id")

        assert player is None

    def test_set_player(self):
        """Test setting a player for a session."""
        manager = SessionManager()
        session_id, player_id = manager.create_session("testuser")

        result = manager.set_player(session_id, "test_player")

        assert result is True
        assert manager.players[player_id] == "test_player"

    def test_set_player_invalid_session(self):
        """Test setting player for invalid session."""
        manager = SessionManager()

        result = manager.set_player("invalid_id", "test_player")

        assert result is False

    def test_expire_session(self):
        """Test expiring a session."""
        manager = SessionManager()
        session_id, player_id = manager.create_session("testuser")

        result = manager.expire_session(session_id)

        assert result is True
        assert session_id not in manager.sessions
        assert player_id not in manager.players

    def test_expire_invalid_session(self):
        """Test expiring an invalid session."""
        manager = SessionManager()

        result = manager.expire_session("invalid_id")

        assert result is False

    def test_cleanup_expired(self):
        """Test cleaning up expired sessions."""
        manager = SessionManager()

        # Create multiple sessions
        ids = []
        for i in range(3):
            session_id, _ = manager.create_session(f"user{i}")
            ids.append(session_id)

        # Expire first two
        for session_id in ids[:2]:
            manager.sessions[session_id].expires_at = datetime.now() - timedelta(
                hours=1
            )

        count = manager.cleanup_expired()

        assert count == 2
        assert ids[0] not in manager.sessions
        assert ids[1] not in manager.sessions
        assert ids[2] in manager.sessions

    def test_get_active_session_count(self):
        """Test counting active sessions."""
        manager = SessionManager()

        for i in range(3):
            manager.create_session(f"user{i}")

        count = manager.get_active_session_count()

        assert count == 3

    def test_get_all_sessions(self):
        """Test retrieving all sessions."""
        manager = SessionManager()

        for i in range(3):
            manager.create_session(f"user{i}")

        sessions = manager.get_all_sessions()

        assert len(sessions) == 3
        assert all("session_id" in s for s in sessions)
        assert all("username" in s for s in sessions)
