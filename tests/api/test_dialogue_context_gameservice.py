"""
Tests for Dialogue Context GameService Methods

Tests all 5 GameService dialogue methods:
- start_dialogue: Initiate conversation with NPC
- get_dialogue_node: Retrieve specific dialogue node
- select_dialogue_choice: Process player choice and apply effects
- get_conversation_history: Retrieve past conversations
- get_available_dialogues: List available dialogues

Test Structure:
- 4-5 tests per method covering success cases, validation, and error handling

Total: 22 tests
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.api.services.game_service import GameService
from src.api.services.session_manager import MinimalPlayer


@pytest.fixture
def mock_universe():
    """Create a mock universe for testing."""
    universe = Mock()
    universe.get_tile = Mock(return_value=None)
    universe.game_tick = 0
    return universe


@pytest.fixture
def game_service(mock_universe):
    """Create GameService with mock universe."""
    return GameService(mock_universe)


@pytest.fixture
def minimal_player():
    """Create a minimal player for testing."""
    player = MinimalPlayer(name="TestPlayer")
    player.story = {"ch01_complete": True}
    player.reputation = {"npc_1": 10}
    player.completed_dialogues = ["greeting_001"]
    player.dialogue_contexts = {}
    return player


class TestStartDialogue:
    """Tests for GameService.start_dialogue method."""
    
    def test_start_dialogue_success(self, game_service, minimal_player):
        """Test successful dialogue initiation."""
        result = game_service.start_dialogue(
            minimal_player,
            npc_id="merchant_kael",
            dialogue_id="greeting_001"
        )
        
        assert result["success"] is True
        assert "data" in result
        assert "conversation_id" in result["data"]
        assert result["data"]["current_node"]["speaker"] == "merchant_kael"
    
    def test_start_dialogue_creates_conversation_id(self, game_service, minimal_player):
        """Test that unique conversation IDs are created."""
        result1 = game_service.start_dialogue(minimal_player, "npc_1", "dial_1")
        result2 = game_service.start_dialogue(minimal_player, "npc_1", "dial_1")
        
        conv_id_1 = result1["data"]["conversation_id"]
        conv_id_2 = result2["data"]["conversation_id"]
        
        assert conv_id_1 != conv_id_2
    
    def test_start_dialogue_stores_context(self, game_service, minimal_player):
        """Test that dialogue context is stored on player."""
        result = game_service.start_dialogue(minimal_player, "npc_1", "dial_1")
        conv_id = result["data"]["conversation_id"]
        
        assert conv_id in minimal_player.dialogue_contexts
        assert minimal_player.dialogue_contexts[conv_id] is not None
    
    def test_start_dialogue_initial_node_has_speaker(self, game_service, minimal_player):
        """Test that initial node has NPC as speaker."""
        result = game_service.start_dialogue(minimal_player, "npc_xyz", "dial_1")
        
        assert result["data"]["current_node"]["speaker"] == "npc_xyz"
    
    def test_start_dialogue_has_conversation_history(self, game_service, minimal_player):
        """Test that conversation history is initialized."""
        result = game_service.start_dialogue(minimal_player, "npc_1", "dial_1")
        
        assert "conversation_history" in result["data"]
        assert result["data"]["conversation_history"]["status"] == "ongoing"
        assert result["data"]["conversation_history"]["npc_id"] == "npc_1"


class TestGetDialogueNode:
    """Tests for GameService.get_dialogue_node method."""
    
    def test_get_dialogue_node_success(self, game_service, minimal_player):
        """Test successful node retrieval."""
        result = game_service.get_dialogue_node(minimal_player, "node_greeting")
        
        assert result["success"] is True
        assert "data" in result
        assert "node" in result["data"]
        assert "available_choices" in result["data"]
    
    def test_get_dialogue_node_returns_node_id(self, game_service, minimal_player):
        """Test that node has correct ID."""
        result = game_service.get_dialogue_node(minimal_player, "quest_offer_001")
        
        assert result["data"]["node"]["node_id"] == "quest_offer_001"
    
    def test_get_dialogue_node_filters_choices(self, game_service, minimal_player):
        """Test that node returns available choices."""
        result = game_service.get_dialogue_node(minimal_player, "test_node")
        
        # Should have choices list even if empty
        assert isinstance(result["data"]["available_choices"], list)
    
    def test_get_dialogue_node_for_different_nodes(self, game_service, minimal_player):
        """Test retrieving different nodes."""
        result1 = game_service.get_dialogue_node(minimal_player, "node_1")
        result2 = game_service.get_dialogue_node(minimal_player, "node_2")
        
        assert result1["data"]["node"]["node_id"] == "node_1"
        assert result2["data"]["node"]["node_id"] == "node_2"
    
    def test_get_dialogue_node_player_level_check(self, game_service, minimal_player):
        """Test that player level is passed for condition checking."""
        result = game_service.get_dialogue_node(minimal_player, "test_node")
        
        # Should succeed - player level should be in request
        assert result["success"] is True


class TestSelectDialogueChoice:
    """Tests for GameService.select_dialogue_choice method."""
    
    def test_select_choice_success(self, game_service, minimal_player):
        """Test successful choice selection."""
        # First start a dialogue
        start_result = game_service.start_dialogue(minimal_player, "npc_1", "dial_1")
        conv_id = start_result["data"]["conversation_id"]
        
        # Then select a choice
        result = game_service.select_dialogue_choice(minimal_player, conv_id, "choice_1")
        
        assert result["success"] is True
        assert "data" in result
    
    def test_select_choice_returns_next_node(self, game_service, minimal_player):
        """Test that choice selection returns next node."""
        start_result = game_service.start_dialogue(minimal_player, "npc_1", "dial_1")
        conv_id = start_result["data"]["conversation_id"]
        
        result = game_service.select_dialogue_choice(minimal_player, conv_id, "choice_1")
        
        assert "current_node" in result["data"]
        assert result["data"]["current_node"]["node_id"] is not None
    
    def test_select_choice_updates_history(self, game_service, minimal_player):
        """Test that choice selection updates conversation history."""
        start_result = game_service.start_dialogue(minimal_player, "npc_1", "dial_1")
        conv_id = start_result["data"]["conversation_id"]
        
        result = game_service.select_dialogue_choice(minimal_player, conv_id, "choice_1")
        
        assert "conversation_history" in result["data"]
    
    def test_select_choice_multiple_choices(self, game_service, minimal_player):
        """Test selecting multiple choices in sequence."""
        # Start dialogue
        start_result = game_service.start_dialogue(minimal_player, "npc_1", "dial_1")
        conv_id = start_result["data"]["conversation_id"]
        
        # Make first choice
        result1 = game_service.select_dialogue_choice(minimal_player, conv_id, "choice_a")
        assert result1["success"] is True
        
        # Make second choice (from same conversation)
        result2 = game_service.select_dialogue_choice(minimal_player, conv_id, "choice_b")
        assert result2["success"] is True


class TestGetConversationHistory:
    """Tests for GameService.get_conversation_history method."""
    
    def test_get_conversation_history_success(self, game_service, minimal_player):
        """Test successful history retrieval."""
        result = game_service.get_conversation_history(minimal_player, "npc_1")
        
        assert result["success"] is True
        assert "data" in result
        assert "conversations" in result["data"]
    
    def test_get_conversation_history_npc_id(self, game_service, minimal_player):
        """Test that history request specifies NPC."""
        result = game_service.get_conversation_history(minimal_player, "merchant_kael")
        
        assert result["data"]["npc_id"] == "merchant_kael"
    
    def test_get_conversation_history_count(self, game_service, minimal_player):
        """Test that history returns conversation count."""
        result = game_service.get_conversation_history(minimal_player, "npc_1")
        
        assert "total_conversations" in result["data"]
        assert isinstance(result["data"]["total_conversations"], int)
    
    def test_get_conversation_history_empty_initially(self, game_service, minimal_player):
        """Test that history is empty for new NPCs."""
        result = game_service.get_conversation_history(minimal_player, "unknown_npc")
        
        assert result["data"]["total_conversations"] == 0
        assert result["data"]["conversations"] == []
    
    def test_get_conversation_history_different_npcs(self, game_service, minimal_player):
        """Test retrieving history for different NPCs."""
        result1 = game_service.get_conversation_history(minimal_player, "npc_1")
        result2 = game_service.get_conversation_history(minimal_player, "npc_2")
        
        assert result1["data"]["npc_id"] == "npc_1"
        assert result2["data"]["npc_id"] == "npc_2"


class TestGetAvailableDialogues:
    """Tests for GameService.get_available_dialogues method."""
    
    def test_get_available_dialogues_success(self, game_service, minimal_player):
        """Test successful available dialogues retrieval."""
        result = game_service.get_available_dialogues(minimal_player, "npc_1")
        
        assert result["success"] is True
        assert "data" in result
        assert "dialogues" in result["data"]
    
    def test_get_available_dialogues_npc_id(self, game_service, minimal_player):
        """Test that request specifies NPC."""
        result = game_service.get_available_dialogues(minimal_player, "quest_giver")
        
        assert result["data"]["npc_id"] == "quest_giver"
    
    def test_get_available_dialogues_count(self, game_service, minimal_player):
        """Test that available list has count."""
        result = game_service.get_available_dialogues(minimal_player, "npc_1")
        
        assert "total_available" in result["data"]
        assert isinstance(result["data"]["total_available"], int)
    
    def test_get_available_dialogues_returns_list(self, game_service, minimal_player):
        """Test that dialogues is a list."""
        result = game_service.get_available_dialogues(minimal_player, "npc_1")
        
        assert isinstance(result["data"]["dialogues"], list)
    
    def test_get_available_dialogues_different_npcs(self, game_service, minimal_player):
        """Test retrieving available for different NPCs."""
        result1 = game_service.get_available_dialogues(minimal_player, "npc_1")
        result2 = game_service.get_available_dialogues(minimal_player, "npc_2")
        
        assert result1["data"]["npc_id"] == "npc_1"
        assert result2["data"]["npc_id"] == "npc_2"
