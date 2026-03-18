"""
Unit tests for NPC AI, Dialogue, and Quest serializers.

Tests all serializer classes for correct data transformation and handling
of edge cases.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

try:
    from src.api.serializers.npc_ai import (
        NPCAIStateSerializer,
        DialogueStateSerializer,
        QuestStateSerializer,
        NPCBehaviorProfileSerializer,
    )
    SERIALIZERS_AVAILABLE = True
except ImportError:
    SERIALIZERS_AVAILABLE = False


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="NPC AI serializers not available"
)
class TestNPCAIStateSerializer:
    """Tests for NPCAIStateSerializer."""

    def test_serialize_npc_ai_state_basic(self):
        """Test serializing basic NPC AI state."""
        class MockNPC:
            name = "TestNPC"
            current_behavior = "idle"
            behavior_stack = ["patrol"]
            x = 5
            y = 10
            hp = 100
            maxhp = 100
            in_combat = False
            mood = "neutral"
            aggression = 0.5
            trust = 0.75
            last_interaction_time = "2025-11-08T10:00:00Z"
            memory = []

        npc = MockNPC()
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)

        assert result["npc_id"] == "TestNPC"
        assert result["current_behavior"] == "idle"
        assert result["emotion_state"] == "neutral"
        assert result["aggression_level"] == 0.5
        assert result["trust_level"] == 0.75
        assert result["position"]["x"] == 5
        assert result["position"]["y"] == 10

    def test_serialize_npc_ai_state_in_combat(self):
        """Test serializing NPC in combat."""
        class MockNPC:
            name = "CombatNPC"
            current_behavior = "attack"
            behavior_stack = []
            x = 0
            y = 0
            hp = 50
            maxhp = 100
            in_combat = True
            mood = None
            aggression = None
            trust = None
            last_interaction_time = None
            memory = []

        npc = MockNPC()
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)

        assert result["emotion_state"] == "angry"
        assert result["aggression_level"] == 1.0
        assert result["health_status"]["status"] == "wounded"

    def test_serialize_npc_list(self):
        """Test serializing list of NPCs."""
        class MockNPC:
            def __init__(self, name):
                self.name = name
                self.current_behavior = "idle"
                self.behavior_stack = []
                self.x = 0
                self.y = 0
                self.hp = 100
                self.maxhp = 100
                self.in_combat = False
                self.mood = None
                self.aggression = 0.5
                self.trust = 0.5
                self.last_interaction_time = None
                self.memory = []

        npcs = [MockNPC(f"NPC{i}") for i in range(3)]
        result = NPCAIStateSerializer.serialize_npc_list(npcs)

        assert len(result) == 3
        assert result[0]["npc_id"] == "NPC0"
        assert result[1]["npc_id"] == "NPC1"
        assert result[2]["npc_id"] == "NPC2"

    def test_emotion_state_fearful(self):
        """Test fear emotion when HP is low."""
        class MockNPC:
            name = "FearfulNPC"
            current_behavior = "flee"
            behavior_stack = []
            x = 0
            y = 0
            hp = 15  # 15% of 100
            maxhp = 100
            in_combat = False
            mood = None
            aggression = 0.5
            trust = 0.5
            last_interaction_time = None
            memory = []

        npc = MockNPC()
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)

        assert result["emotion_state"] == "fearful"

    def test_aggression_level_from_attribute(self):
        """Test aggression level from NPC attribute."""
        class MockNPC:
            name = "AggressiveNPC"
            current_behavior = "attack"
            behavior_stack = []
            x = 0
            y = 0
            hp = 100
            maxhp = 100
            in_combat = False
            mood = None
            aggression = 0.9
            trust = 0.5
            last_interaction_time = None
            memory = []

        npc = MockNPC()
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)

        assert result["aggression_level"] == 0.9


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Dialogue serializer not available"
)
class TestDialogueStateSerializer:
    """Tests for DialogueStateSerializer."""

    def test_serialize_dialogue_state_basic(self):
        """Test serializing basic dialogue state."""
        class MockNPC:
            name = "NPC"
            player_knows_npc = True
            trust = 0.75
            dialogue_flags = {"has_quest": True}

        npc = MockNPC()
        result = DialogueStateSerializer.serialize_dialogue_state(
            npc,
            current_node="start"
        )

        assert result["npc_id"] == "NPC"
        assert result["current_node"] == "start"
        assert "current_text" in result
        assert "options" in result
        assert isinstance(result["options"], list)

    def test_serialize_dialogue_options(self):
        """Test serializing dialogue options."""
        class MockNPC:
            name = "NPC"
            player_knows_npc = True
            trust = 0.75
            dialogue_flags = {}

        npc = MockNPC()
        result = DialogueStateSerializer.serialize_dialogue_options(
            npc,
            current_node="start"
        )

        assert result["npc_id"] == "NPC"
        assert result["current_node"] == "start"
        assert "options" in result
        assert len(result["options"]) > 0

    def test_default_dialogue_tree(self):
        """Test default dialogue tree has required structure."""
        class MockNPC:
            name = "TestNPC"

        npc = MockNPC()
        tree = DialogueStateSerializer._get_default_dialogue_tree(npc)

        assert "id" in tree
        assert "nodes" in tree
        assert "start" in tree["nodes"]
        assert "end" in tree["nodes"]

    def test_get_node_text(self):
        """Test getting text from dialogue node."""
        dialogue_tree = {
            "nodes": {
                "test": {"text": "Test message", "options": []}
            }
        }

        text = DialogueStateSerializer._get_node_text(dialogue_tree, "test")
        assert text == "Test message"

    def test_conversation_history_limited(self):
        """Test conversation history is limited to last 5."""
        class MockNPC:
            name = "NPC"
            player_knows_npc = True
            trust = 0.5
            dialogue_flags = {}

        history = [
            {"speaker": "npc", "text": f"Line {i}"}
            for i in range(10)
        ]

        npc = MockNPC()
        result = DialogueStateSerializer.serialize_dialogue_state(
            npc,
            conversation_history=history
        )

        assert len(result["conversation_history"]) == 5


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Quest serializer not available"
)
class TestQuestStateSerializer:
    """Tests for QuestStateSerializer."""

    def test_serialize_quest_basic(self):
        """Test serializing basic quest."""
        quest = {
            "id": "quest_001",
            "title": "Find the Amulet",
            "description": "Find the missing amulet",
            "status": "active",
            "progress": 50,
            "objectives": [
                {"id": "obj_1", "text": "Search the cave", "completed": True},
                {"id": "obj_2", "text": "Find the thief", "completed": False}
            ],
            "rewards": {"experience": 100, "gold": 50},
            "giver": "Elder"
        }

        result = QuestStateSerializer.serialize_quest(quest)

        assert result["quest_id"] == "quest_001"
        assert result["title"] == "Find the Amulet"
        assert result["status"] == "active"
        assert result["progress"] == 50
        assert len(result["objectives"]) == 2

    def test_serialize_active_quests(self):
        """Test serializing active quests."""
        class MockPlayer:
            active_quests = [
                {"id": "quest_001", "title": "Quest 1", "status": "active", "progress": 50},
                {"id": "quest_002", "title": "Quest 2", "status": "active", "progress": 100}
            ]

        player = MockPlayer()
        result = QuestStateSerializer.serialize_active_quests(player)

        assert len(result) == 2
        assert result[0]["quest_id"] == "quest_001"
        assert result[1]["quest_id"] == "quest_002"

    def test_serialize_quest_progress(self):
        """Test serializing quest progress."""
        quest = {
            "id": "quest_001",
            "title": "Test Quest",
            "progress": 60,
            "status": "active",
            "objectives": [
                {"id": "obj_1", "text": "Step 1", "completed": True},
                {"id": "obj_2", "text": "Step 2", "completed": True},
                {"id": "obj_3", "text": "Step 3", "completed": False}
            ],
            "current_step": "Step 2",
            "next_step": "Step 3",
            "started_at": "2025-11-08T10:00:00Z"
        }

        result = QuestStateSerializer.serialize_quest_progress(quest)

        assert result["objectives_completed"] == 2
        assert result["objectives_total"] == 3
        assert result["status"] == "active"

    def test_serialize_objectives(self):
        """Test serializing quest objectives."""
        objectives = [
            {"id": "obj_1", "text": "Find item", "completed": True, "progress": 100},
            {"id": "obj_2", "text": "Deliver item", "completed": False, "progress": 0},
            {"text": "Final task", "completed": False}  # Missing ID
        ]

        result = QuestStateSerializer._serialize_objectives(objectives)

        assert len(result) == 3
        assert result[0]["completed"] is True
        assert result[1]["completed"] is False
        assert result[2]["id"] == "obj_2"  # Auto-generated ID


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Behavior profile serializer not available"
)
class TestNPCBehaviorProfileSerializer:
    """Tests for NPCBehaviorProfileSerializer."""

    def test_serialize_behavior_profile_basic(self):
        """Test serializing NPC behavior profile."""
        class MockNPC:
            name = "ProfileNPC"
            personality_archetype = "warrior"
            personality_traits = ["brave", "strong"]
            intelligence = 0.7
            courage = 0.9
            friendliness = 0.5
            idle_behavior = "patrol"
            combat_behavior = "aggressive"
            social_behavior = "neutral"
            response_type = "aggressive"
            combat_preference = "melee"
            aggression = 0.8
            defense_priority = 0.4
            flee_at_health_percent = 0.1
            likes = ["battle"]
            dislikes = ["peace"]
            fears = []
            desires = ["glory"]
            friends = []
            enemies = []
            neutral_npcs = []
            reputation = {}
            combat_skill = 0.9
            magic_skill = 0.3
            stealth_skill = 0.5
            persuasion_skill = 0.6
            tracking_skill = 0.7

        npc = MockNPC()
        result = NPCBehaviorProfileSerializer.serialize_behavior_profile(npc)

        assert result["npc_id"] == "ProfileNPC"
        assert result["personality"]["archetype"] == "warrior"
        assert result["behaviors"]["idle_behavior"] == "patrol"
        assert result["combat_style"]["preference"] == "melee"
        assert result["skills"]["combat"] == 0.9

    def test_personality_traits(self):
        """Test personality trait serialization."""
        class MockNPC:
            name = "NPC"
            personality_archetype = "mage"
            personality_traits = ["intelligent", "patient"]
            intelligence = 0.95
            courage = 0.3
            friendliness = 0.7
            idle_behavior = None
            combat_behavior = None
            social_behavior = None
            response_type = None
            combat_preference = None
            aggression = None
            defense_priority = None
            flee_at_health_percent = None
            likes = None
            dislikes = None
            fears = None
            desires = None
            friends = None
            enemies = None
            neutral_npcs = None
            reputation = None
            combat_skill = None
            magic_skill = None
            stealth_skill = None
            persuasion_skill = None
            tracking_skill = None

        npc = MockNPC()
        result = NPCBehaviorProfileSerializer.serialize_behavior_profile(npc)

        assert result["personality"]["intelligence"] == 0.95
        assert result["personality"]["traits"] == ["intelligent", "patient"]

    def test_combat_style_defaults(self):
        """Test combat style with defaults."""
        class MockNPC:
            name = "NPC"
            personality_archetype = None
            personality_traits = None
            intelligence = None
            courage = None
            friendliness = None
            idle_behavior = None
            combat_behavior = None
            social_behavior = None
            response_type = None
            combat_preference = "magic"
            aggression = 0.6
            defense_priority = 0.8
            flee_at_health_percent = 0.2
            likes = None
            dislikes = None
            fears = None
            desires = None
            friends = None
            enemies = None
            neutral_npcs = None
            reputation = None
            combat_skill = None
            magic_skill = None
            stealth_skill = None
            persuasion_skill = None
            tracking_skill = None

        npc = MockNPC()
        result = NPCBehaviorProfileSerializer.serialize_behavior_profile(npc)

        assert result["combat_style"]["preference"] == "magic"
        assert result["combat_style"]["flee_threshold"] == 0.2


# Integration test to ensure all serializers work together
@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Serializers not available"
)
def test_serializers_integrate():
    """Test that all serializers are properly exported and integrated."""
    from src.api.serializers import (
        NPCAIStateSerializer,
        DialogueStateSerializer,
        QuestStateSerializer,
        NPCBehaviorProfileSerializer,
    )

    # Verify all serializers are available
    assert NPCAIStateSerializer is not None
    assert DialogueStateSerializer is not None
    assert QuestStateSerializer is not None
    assert NPCBehaviorProfileSerializer is not None

    # Verify they have required methods
    assert hasattr(NPCAIStateSerializer, "serialize_npc_ai_state")
    assert hasattr(DialogueStateSerializer, "serialize_dialogue_state")
    assert hasattr(QuestStateSerializer, "serialize_quest")
    assert hasattr(NPCBehaviorProfileSerializer, "serialize_behavior_profile")
