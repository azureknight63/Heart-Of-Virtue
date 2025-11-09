"""
Unit tests for GameService NPC methods.

Tests all NPC-related methods in GameService for correct functionality
and proper serialization integration.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

try:
    from src.api.services.game_service import GameService
    from src.api.serializers.npc_ai import (
        NPCAIStateSerializer,
        DialogueStateSerializer,
        QuestStateSerializer,
        NPCBehaviorProfileSerializer,
    )
    GAME_SERVICE_AVAILABLE = True
except ImportError:
    GAME_SERVICE_AVAILABLE = False


@pytest.mark.skipif(
    not GAME_SERVICE_AVAILABLE, reason="GameService or serializers not available"
)
class TestGameServiceNPC:
    """Tests for GameService NPC methods."""

    @pytest.fixture
    def mock_universe(self):
        """Create a mock universe."""
        class MockTile:
            npcs_here = []

            def __init__(self):
                self.npcs_here = []

        class MockUniverse:
            def __init__(self):
                self.tiles = {}

            def get_tile(self, x, y):
                key = (x, y)
                if key not in self.tiles:
                    self.tiles[key] = MockTile()
                return self.tiles[key]

            def set_tile_npcs(self, x, y, npcs):
                self.get_tile(x, y).npcs_here = npcs

        return MockUniverse()

    @pytest.fixture
    def game_service(self, mock_universe):
        """Create a GameService instance with mock universe."""
        return GameService(mock_universe)

    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        class MockPlayer:
            x = 5
            y = 10
            active_quests = []
            available_quests = []
            completed_quests = []

        return MockPlayer()

    @pytest.fixture
    def mock_npc(self):
        """Create a mock NPC."""
        class MockNPC:
            name = "TestNPC"
            current_behavior = "idle"
            behavior_stack = []
            x = 5
            y = 10
            hp = 100
            maxhp = 100
            in_combat = False
            mood = "neutral"
            aggression = 0.5
            trust = 0.75
            last_interaction_time = None
            memory = []
            conversation_history = []

            # Behavior profile attributes
            personality_archetype = "warrior"
            personality_traits = ["brave"]
            intelligence = 0.7
            courage = 0.8
            friendliness = 0.6
            idle_behavior = "patrol"
            combat_behavior = "aggressive"
            social_behavior = "neutral"
            response_type = "aggressive"
            combat_preference = "melee"
            defense_priority = 0.5
            flee_at_health_percent = 0.2
            likes = []
            dislikes = []
            fears = []
            desires = []
            friends = []
            enemies = []
            neutral_npcs = []
            reputation = {}
            combat_skill = 0.9
            magic_skill = 0.3
            stealth_skill = 0.4
            persuasion_skill = 0.6
            tracking_skill = 0.7

        return MockNPC()

    def test_get_npc_state_success(self, game_service, mock_universe, mock_player, mock_npc):
        """Test getting NPC state when NPC exists."""
        game_service.universe.set_tile_npcs(mock_player.x, mock_player.y, [mock_npc])

        result = game_service.get_npc_state(mock_player, "TestNPC")

        assert result["success"] is True
        assert "npc" in result
        assert result["npc"]["npc_id"] == "TestNPC"
        assert result["npc"]["emotion_state"] == "neutral"

    def test_get_npc_state_not_found(self, game_service, mock_player):
        """Test getting NPC state when NPC doesn't exist."""
        result = game_service.get_npc_state(mock_player, "NonexistentNPC")

        assert result["success"] is False
        assert "error" in result

    def test_get_npc_dialogue_success(self, game_service, mock_universe, mock_player, mock_npc):
        """Test getting dialogue from NPC."""
        game_service.universe.set_tile_npcs(mock_player.x, mock_player.y, [mock_npc])

        result = game_service.get_npc_dialogue(mock_player, "TestNPC")

        assert result["success"] is True
        assert "dialogue" in result
        assert result["dialogue"]["npc_id"] == "TestNPC"
        assert "options" in result["dialogue"]

    def test_get_npc_dialogue_not_found(self, game_service, mock_player):
        """Test getting dialogue from nonexistent NPC."""
        result = game_service.get_npc_dialogue(mock_player, "NonexistentNPC")

        assert result["success"] is False
        assert "error" in result

    def test_select_dialogue_option_success(
        self, game_service, mock_universe, mock_player, mock_npc
    ):
        """Test selecting a dialogue option."""
        game_service.universe.set_tile_npcs(mock_player.x, mock_player.y, [mock_npc])

        result = game_service.select_dialogue_option(mock_player, "TestNPC", 0)

        assert result["success"] is True
        assert "dialogue" in result
        assert mock_npc.last_interaction_time is not None

    def test_select_dialogue_option_not_found(self, game_service, mock_player):
        """Test selecting dialogue option from nonexistent NPC."""
        result = game_service.select_dialogue_option(mock_player, "NonexistentNPC", 0)

        assert result["success"] is False

    def test_get_npc_behavior_profile_success(
        self, game_service, mock_universe, mock_player, mock_npc
    ):
        """Test getting NPC behavior profile."""
        game_service.universe.set_tile_npcs(mock_player.x, mock_player.y, [mock_npc])

        result = game_service.get_npc_behavior_profile(mock_player, "TestNPC")

        assert result["success"] is True
        assert "profile" in result
        assert result["profile"]["npc_id"] == "TestNPC"
        assert result["profile"]["personality"]["archetype"] == "warrior"
        assert result["profile"]["skills"]["combat"] == 0.9

    def test_get_npc_behavior_profile_not_found(self, game_service, mock_player):
        """Test getting profile from nonexistent NPC."""
        result = game_service.get_npc_behavior_profile(mock_player, "NonexistentNPC")

        assert result["success"] is False

    def test_get_active_quests_empty(self, game_service, mock_player):
        """Test getting active quests when none exist."""
        result = game_service.get_active_quests(mock_player)

        assert result["success"] is True
        assert result["count"] == 0
        assert result["quests"] == []

    def test_get_active_quests_with_quests(self, game_service, mock_player):
        """Test getting active quests."""
        quest1 = {
            "id": "quest_001",
            "title": "Quest 1",
            "status": "active",
            "progress": 50,
            "objectives": []
        }
        quest2 = {
            "id": "quest_002",
            "title": "Quest 2",
            "status": "active",
            "progress": 75,
            "objectives": []
        }
        mock_player.active_quests = [quest1, quest2]

        result = game_service.get_active_quests(mock_player)

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["quests"]) == 2

    def test_start_quest_success(self, game_service, mock_player):
        """Test starting a quest."""
        quest = {
            "id": "quest_001",
            "title": "Find the Amulet",
            "status": "available",
            "objectives": []
        }
        mock_player.available_quests = [quest]

        result = game_service.start_quest(mock_player, "quest_001")

        assert result["success"] is True
        assert "quest" in result
        assert len(mock_player.active_quests) == 1
        assert len(mock_player.available_quests) == 0

    def test_start_quest_not_found(self, game_service, mock_player):
        """Test starting a quest that doesn't exist."""
        result = game_service.start_quest(mock_player, "nonexistent")

        assert result["success"] is False
        assert "error" in result

    def test_update_quest_progress_success(self, game_service, mock_player):
        """Test updating quest progress."""
        quest = {
            "id": "quest_001",
            "title": "Test Quest",
            "progress": 0,
            "objectives": [
                {"id": "obj_1", "text": "Step 1", "completed": False},
                {"id": "obj_2", "text": "Step 2", "completed": False}
            ]
        }
        mock_player.active_quests = [quest]

        result = game_service.update_quest_progress(
            mock_player, "quest_001", "obj_1"
        )

        assert result["success"] is True
        assert quest["objectives"][0]["completed"] is True
        assert quest["progress"] == 50  # 1 of 2 objectives

    def test_update_quest_progress_all_objectives(self, game_service, mock_player):
        """Test updating quest progress when all objectives complete."""
        quest = {
            "id": "quest_001",
            "title": "Test Quest",
            "progress": 50,
            "objectives": [
                {"id": "obj_1", "text": "Step 1", "completed": True},
                {"id": "obj_2", "text": "Step 2", "completed": False}
            ]
        }
        mock_player.active_quests = [quest]

        result = game_service.update_quest_progress(
            mock_player, "quest_001", "obj_2"
        )

        assert result["success"] is True
        assert quest["progress"] == 100  # 2 of 2 objectives

    def test_update_quest_progress_not_found(self, game_service, mock_player):
        """Test updating progress on nonexistent quest."""
        result = game_service.update_quest_progress(
            mock_player, "nonexistent", "obj_1"
        )

        assert result["success"] is False

    def test_get_quest_status_active(self, game_service, mock_player):
        """Test getting status of active quest."""
        quest = {
            "id": "quest_001",
            "title": "Active Quest",
            "progress": 50,
            "objectives": []
        }
        mock_player.active_quests = [quest]

        result = game_service.get_quest_status(mock_player, "quest_001")

        assert result["success"] is True
        assert result["status"] == "active"

    def test_get_quest_status_completed(self, game_service, mock_player):
        """Test getting status of completed quest."""
        quest = {
            "id": "quest_001",
            "title": "Completed Quest",
            "progress": 100,
            "objectives": []
        }
        mock_player.completed_quests = [quest]

        result = game_service.get_quest_status(mock_player, "quest_001")

        assert result["success"] is True
        assert result["status"] == "completed"

    def test_get_quest_status_not_found(self, game_service, mock_player):
        """Test getting status of nonexistent quest."""
        result = game_service.get_quest_status(mock_player, "nonexistent")

        assert result["success"] is False
        assert "error" in result
