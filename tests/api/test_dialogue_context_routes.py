"""
Tests for Dialogue Context API Routes

Tests all 5 endpoints with:
- Authentication (Bearer token validation)
- Request validation
- Response format
- Error handling
- Integration with GameService

Test Structure:
- POST /api/dialogue/start: 6 tests
- GET /api/dialogue/node/<node_id>: 5 tests
- POST /api/dialogue/select: 6 tests
- GET /api/npc/<npc_id>/dialogue/history: 5 tests
- GET /api/npc/<npc_id>/dialogue/available: 6 tests

Total: 28 tests
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
try:
    from flask import Flask
    from src.api.app import create_app
    from src.api.services.session_manager import SessionManager
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestStartDialogueEndpoint:
    """Tests for POST /api/dialogue/start endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        app, socketio = create_app()
        app.config["TESTING"] = True
        return app.test_client()
    
    @pytest.fixture
    def session_with_player(self, client):
        """Create session for testing."""
        app = client.application
        session_manager = app.session_manager
        session_id, player_id = session_manager.create_session("testuser")
        player = session_manager.get_player(session_id)
        return session_id, player, session_manager
    
    def test_start_dialogue_success(self, client, session_with_player):
        """Test successful dialogue start."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.post(
            "/api/dialogue/start",
            json={"npc_id": "merchant_kael", "dialogue_id": "greeting_001"},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        assert "conversation_id" in data["data"]
    
    def test_start_dialogue_missing_auth(self, client):
        """Test start dialogue without authentication."""
        response = client.post(
            "/api/dialogue/start",
            json={"npc_id": "npc_1", "dialogue_id": "dial_1"}
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
    
    def test_start_dialogue_missing_fields(self, client, session_with_player):
        """Test start dialogue with missing required fields."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.post(
            "/api/dialogue/start",
            json={"npc_id": "merchant_kael"},  # Missing dialogue_id
            headers=headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
    
    def test_start_dialogue_empty_fields(self, client, session_with_player):
        """Test start dialogue with empty field values."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.post(
            "/api/dialogue/start",
            json={"npc_id": "", "dialogue_id": "dial_1"},
            headers=headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
    
    def test_start_dialogue_not_json(self, client, session_with_player):
        """Test start dialogue with non-JSON content."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.post(
            "/api/dialogue/start",
            data="not json",
            headers=headers
        )
        
        assert response.status_code == 400


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestGetDialogueNodeEndpoint:
    """Tests for GET /api/dialogue/node/<node_id> endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        app, socketio = create_app()
        app.config["TESTING"] = True
        return app.test_client()
    
    @pytest.fixture
    def session_with_player(self, client):
        """Create session for testing."""
        app = client.application
        session_manager = app.session_manager
        session_id, player_id = session_manager.create_session("testuser")
        player = session_manager.get_player(session_id)
        return session_id, player, session_manager
    
    def test_get_dialogue_node_success(self, client, session_with_player):
        """Test successful node retrieval."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/dialogue/node/greeting_001",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
    
    def test_get_dialogue_node_missing_auth(self, client):
        """Test get node without authentication."""
        response = client.get("/api/dialogue/node/node_1")
        
        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
    
    def test_get_dialogue_node_empty_id(self, client, session_with_player):
        """Test get node with empty node_id."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/dialogue/node/ ",  # Empty/whitespace node_id
            headers=headers
        )
        
        assert response.status_code == 400
    
    def test_get_dialogue_node_returns_choices(self, client, session_with_player):
        """Test that node retrieval includes available choices."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/dialogue/node/test_node",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert "available_choices" in data["data"]
    
    def test_get_dialogue_node_different_nodes(self, client, session_with_player):
        """Test retrieving different nodes."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response1 = client.get("/api/dialogue/node/node_a", headers=headers)
        response2 = client.get("/api/dialogue/node/node_b", headers=headers)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        data1 = response1.get_json()
        data2 = response2.get_json()
        assert data1["data"]["node"]["node_id"] == "node_a"
        assert data2["data"]["node"]["node_id"] == "node_b"


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestSelectDialogueChoiceEndpoint:
    """Tests for POST /api/dialogue/select endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        app, socketio = create_app()
        app.config["TESTING"] = True
        return app.test_client()
    
    @pytest.fixture
    def session_with_player(self, client):
        """Create session for testing."""
        app = client.application
        session_manager = app.session_manager
        session_id, player_id = session_manager.create_session("testuser")
        player = session_manager.get_player(session_id)
        return session_id, player, session_manager
    
    def test_select_choice_success(self, client, session_with_player):
        """Test successful choice selection."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.post(
            "/api/dialogue/select",
            json={
                "conversation_id": "conv_001",
                "choice_id": "choice_1"
            },
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
    
    def test_select_choice_missing_auth(self, client):
        """Test select choice without authentication."""
        response = client.post(
            "/api/dialogue/select",
            json={"conversation_id": "conv_1", "choice_id": "c_1"}
        )
        
        assert response.status_code == 401
    
    def test_select_choice_missing_fields(self, client, session_with_player):
        """Test select choice with missing fields."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.post(
            "/api/dialogue/select",
            json={"conversation_id": "conv_1"},  # Missing choice_id
            headers=headers
        )
        
        assert response.status_code == 400
    
    def test_select_choice_empty_fields(self, client, session_with_player):
        """Test select choice with empty field values."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.post(
            "/api/dialogue/select",
            json={"conversation_id": "", "choice_id": "c_1"},
            headers=headers
        )
        
        assert response.status_code == 400
    
    def test_select_choice_not_json(self, client, session_with_player):
        """Test select choice with non-JSON request."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.post(
            "/api/dialogue/select",
            data="not json",
            headers=headers
        )
        
        assert response.status_code == 400


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestConversationHistoryEndpoint:
    """Tests for GET /api/npc/<npc_id>/dialogue/history endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        app, socketio = create_app()
        app.config["TESTING"] = True
        return app.test_client()
    
    @pytest.fixture
    def session_with_player(self, client):
        """Create session for testing."""
        app = client.application
        session_manager = app.session_manager
        session_id, player_id = session_manager.create_session("testuser")
        player = session_manager.get_player(session_id)
        return session_id, player, session_manager
    
    def test_get_history_success(self, client, session_with_player):
        """Test successful history retrieval."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/npc/merchant_kael/dialogue/history",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "npc_id" in data["data"]
    
    def test_get_history_missing_auth(self, client):
        """Test history without authentication."""
        response = client.get("/api/npc/npc_1/dialogue/history")
        
        assert response.status_code == 401
    
    def test_get_history_with_pagination(self, client, session_with_player):
        """Test history with pagination parameters."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/npc/npc_1/dialogue/history?limit=10&offset=0",
            headers=headers
        )
        
        assert response.status_code == 200
    
    def test_get_history_invalid_pagination(self, client, session_with_player):
        """Test history with invalid pagination."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/npc/npc_1/dialogue/history?limit=not_a_number",
            headers=headers
        )
        
        assert response.status_code == 400
    
    def test_get_history_empty_npc_id(self, client, session_with_player):
        """Test history with empty NPC ID."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/npc/ /dialogue/history",  # Empty NPC ID
            headers=headers
        )
        
        assert response.status_code == 400


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestAvailableDialoguesEndpoint:
    """Tests for GET /api/npc/<npc_id>/dialogue/available endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        app, socketio = create_app()
        app.config["TESTING"] = True
        return app.test_client()
    
    @pytest.fixture
    def session_with_player(self, client):
        """Create session for testing."""
        app = client.application
        session_manager = app.session_manager
        session_id, player_id = session_manager.create_session("testuser")
        player = session_manager.get_player(session_id)
        return session_id, player, session_manager
    
    def test_get_available_success(self, client, session_with_player):
        """Test successful available dialogues retrieval."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/npc/merchant_kael/dialogue/available",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "npc_id" in data["data"]
    
    def test_get_available_missing_auth(self, client):
        """Test available dialogues without authentication."""
        response = client.get("/api/npc/npc_1/dialogue/available")
        
        assert response.status_code == 401
    
    def test_get_available_returns_list(self, client, session_with_player):
        """Test that available returns dialogue list."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/npc/npc_1/dialogue/available",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data["data"]["dialogues"], list)
    
    def test_get_available_different_npcs(self, client, session_with_player):
        """Test retrieving available for different NPCs."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response1 = client.get("/api/npc/npc_a/dialogue/available", headers=headers)
        response2 = client.get("/api/npc/npc_b/dialogue/available", headers=headers)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        data1 = response1.get_json()
        data2 = response2.get_json()
        assert data1["data"]["npc_id"] == "npc_a"
        assert data2["data"]["npc_id"] == "npc_b"
    
    def test_get_available_empty_npc_id(self, client, session_with_player):
        """Test available with empty NPC ID."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        response = client.get(
            "/api/npc/ /dialogue/available",  # Empty NPC ID
            headers=headers
        )
        
        assert response.status_code == 400
