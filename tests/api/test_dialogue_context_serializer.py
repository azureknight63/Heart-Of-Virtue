"""
Tests for Dialogue Context Serializers

Tests all 6 serializer classes with:
- Serialization/deserialization roundtrips
- Edge cases (empty lists, None values, invalid data)
- Condition checking logic
- Choice filtering
- Effect validation

Test Structure:
- DialogueEffectSerializerTests: 4-5 tests
- DialogueConditionSerializerTests: 5-6 tests
- DialogueChoiceSerializerTests: 4-5 tests
- DialogueNodeSerializerTests: 4-5 tests
- ConversationHistorySerializerTests: 3-4 tests
- DialogueContextSerializerTests: 3-4 tests

Total: 26 tests
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.serializers.dialogue_context import (
    DialogueEffect,
    DialogueEffectSerializer,
    DialogueCondition,
    DialogueConditionSerializer,
    DialogueChoice,
    DialogueChoiceSerializer,
    DialogueNode,
    DialogueNodeSerializer,
    ConversationHistory,
    ConversationHistorySerializer,
    DialogueContext,
    DialogueContextSerializer,
)


class TestDialogueEffectSerializer:
    """Tests for DialogueEffectSerializer."""

    def test_serialize_story_gate_effect(self):
        """Test serialization of story gate effect."""
        effect = DialogueEffect(
            effect_type="story_gate",
            target="ch01_door_opened",
            value=True,
            description="Opens the stone door"
        )

        serialized = DialogueEffectSerializer.serialize(effect)

        assert serialized["effect_type"] == "story_gate"
        assert serialized["target"] == "ch01_door_opened"
        assert serialized["value"] is True
        assert serialized["description"] == "Opens the stone door"

    def test_serialize_reputation_effect(self):
        """Test serialization of reputation effect."""
        effect = DialogueEffect(
            effect_type="reputation",
            target="merchant_kael",
            value=15,
            description="Kael likes you more"
        )

        serialized = DialogueEffectSerializer.serialize(effect)

        assert serialized["effect_type"] == "reputation"
        assert serialized["target"] == "merchant_kael"
        assert serialized["value"] == 15

    def test_deserialize_effect(self):
        """Test deserialization of effect dict."""
        data = {
            "effect_type": "item_reward",
            "target": "potion_basic",
            "value": 5,
            "description": "Received 5 potions"
        }

        effect = DialogueEffectSerializer.deserialize(data)

        assert effect.effect_type == "item_reward"
        assert effect.target == "potion_basic"
        assert effect.value == 5

    def test_deserialize_missing_field_raises_key_error(self):
        """Test deserialization with missing required field."""
        data = {"effect_type": "reputation", "target": "npc_1"}
        # Missing "value"

        with pytest.raises(KeyError):
            DialogueEffectSerializer.deserialize(data)

    def test_deserialize_invalid_effect_type_raises_value_error(self):
        """Test deserialization with invalid effect type."""
        data = {
            "effect_type": "invalid_type",
            "target": "npc_1",
            "value": 10
        }

        with pytest.raises(ValueError):
            DialogueEffectSerializer.deserialize(data)


class TestDialogueConditionSerializer:
    """Tests for DialogueConditionSerializer."""

    def test_serialize_condition_with_all_fields(self):
        """Test serialization of condition with all fields."""
        condition = DialogueCondition(
            required_story_gates=["ch01_complete"],
            forbidden_story_gates=["ch02_started"],
            min_reputation=10,
            max_reputation=50,
            required_completed_dialogues=["greeting_001"],
            min_player_level=5
        )

        serialized = DialogueConditionSerializer.serialize(condition)

        assert serialized["required_story_gates"] == ["ch01_complete"]
        assert serialized["forbidden_story_gates"] == ["ch02_started"]
        assert serialized["min_reputation"] == 10
        assert serialized["max_reputation"] == 50
        assert serialized["required_completed_dialogues"] == ["greeting_001"]
        assert serialized["min_player_level"] == 5

    def test_deserialize_condition(self):
        """Test deserialization of condition dict."""
        data = {
            "required_story_gates": ["gate1"],
            "forbidden_story_gates": [],
            "min_reputation": 5,
            "max_reputation": None,
            "required_completed_dialogues": [],
            "min_player_level": None
        }

        condition = DialogueConditionSerializer.deserialize(data)

        assert condition.required_story_gates == ["gate1"]
        assert condition.min_reputation == 5

    def test_check_conditions_all_met(self):
        """Test condition checking when all conditions met."""
        condition = DialogueCondition(
            required_story_gates=["ch01_complete"],
            min_reputation=10
        )
        player_story = {"ch01_complete": True}
        player_reputation = {"merchant_1": 15}

        is_available, reason = DialogueConditionSerializer.check_conditions(
            condition,
            player_story=player_story,
            player_reputation=player_reputation,
            player_level=10,
            player_completed_dialogues=[]
        )

        assert is_available is True
        assert reason is None

    def test_check_conditions_missing_story_gate(self):
        """Test condition checking when story gate missing."""
        condition = DialogueCondition(required_story_gates=["ch01_complete"])
        player_story = {"ch01_complete": False}

        is_available, reason = DialogueConditionSerializer.check_conditions(
            condition,
            player_story=player_story,
            player_reputation={},
            player_level=1,
            player_completed_dialogues=[]
        )

        assert is_available is False
        assert "Required story gate not set" in reason

    def test_check_conditions_forbidden_gate_set(self):
        """Test condition checking when forbidden gate is set."""
        condition = DialogueCondition(forbidden_story_gates=["ch02_started"])
        player_story = {"ch02_started": True}

        is_available, reason = DialogueConditionSerializer.check_conditions(
            condition,
            player_story=player_story,
            player_reputation={},
            player_level=1,
            player_completed_dialogues=[]
        )

        assert is_available is False
        assert "Forbidden story gate is set" in reason

    def test_check_conditions_level_too_low(self):
        """Test condition checking when player level too low."""
        condition = DialogueCondition(min_player_level=10)

        is_available, reason = DialogueConditionSerializer.check_conditions(
            condition,
            player_story={},
            player_reputation={},
            player_level=5,
            player_completed_dialogues=[]
        )

        assert is_available is False
        assert "Player level too low" in reason


class TestDialogueChoiceSerializer:
    """Tests for DialogueChoiceSerializer."""

    def test_serialize_choice_simple(self):
        """Test serialization of simple choice."""
        choice = DialogueChoice(
            choice_id="choice_001",
            text="I'll help you",
            target_node_id="node_002"
        )

        serialized = DialogueChoiceSerializer.serialize(choice)

        assert serialized["choice_id"] == "choice_001"
        assert serialized["text"] == "I'll help you"
        assert serialized["target_node_id"] == "node_002"

    def test_serialize_choice_with_effects(self):
        """Test serialization of choice with effects."""
        effect = DialogueEffect(
            effect_type="reputation",
            target="npc_1",
            value=10
        )
        choice = DialogueChoice(
            choice_id="choice_001",
            text="I'll help you",
            target_node_id="node_002",
            effects=[effect]
        )

        serialized = DialogueChoiceSerializer.serialize(choice)

        assert len(serialized["effects"]) == 1
        assert serialized["effects"][0]["effect_type"] == "reputation"

    def test_deserialize_choice(self):
        """Test deserialization of choice dict."""
        data = {
            "choice_id": "choice_001",
            "text": "Accept quest",
            "target_node_id": "quest_node",
            "condition": None,
            "effects": []
        }

        choice = DialogueChoiceSerializer.deserialize(data)

        assert choice.choice_id == "choice_001"
        assert choice.text == "Accept quest"
        assert choice.target_node_id == "quest_node"

    def test_deserialize_choice_missing_field_raises_key_error(self):
        """Test deserialization with missing required field."""
        data = {"choice_id": "choice_1", "text": "Choose this"}
        # Missing target_node_id

        with pytest.raises(KeyError):
            DialogueChoiceSerializer.deserialize(data)

    def test_filter_available_choices_unconditioned(self):
        """Test filtering choices when no conditions."""
        choices = [
            DialogueChoice("c1", "Choice 1", "node_1"),
            DialogueChoice("c2", "Choice 2", "node_2"),
        ]

        available = DialogueChoiceSerializer.filter_available_choices(
            choices,
            player_story={},
            player_reputation={},
            player_level=1,
            player_completed_dialogues=[]
        )

        assert len(available) == 2

    def test_filter_available_choices_with_condition(self):
        """Test filtering choices with conditions."""
        condition = DialogueCondition(required_story_gates=["gate1"])
        choice_available = DialogueChoice(
            "c1", "Available", "node_1",
            condition=condition
        )
        choice_unavailable = DialogueChoice(
            "c2", "Unavailable", "node_2",
            condition=DialogueCondition(required_story_gates=["gate2"])
        )

        available = DialogueChoiceSerializer.filter_available_choices(
            [choice_available, choice_unavailable],
            player_story={"gate1": True, "gate2": False},
            player_reputation={},
            player_level=1,
            player_completed_dialogues=[]
        )

        assert len(available) == 1
        assert available[0].choice_id == "c1"


class TestDialogueNodeSerializer:
    """Tests for DialogueNodeSerializer."""

    def test_serialize_node_simple(self):
        """Test serialization of simple node."""
        node = DialogueNode(
            node_id="greeting",
            text="Hello there!",
            speaker="merchant_kael",
            npc_tone="friendly"
        )

        serialized = DialogueNodeSerializer.serialize(node)

        assert serialized["node_id"] == "greeting"
        assert serialized["text"] == "Hello there!"
        assert serialized["speaker"] == "merchant_kael"
        assert serialized["npc_tone"] == "friendly"

    def test_serialize_node_with_choices(self):
        """Test serialization of node with choices."""
        choice = DialogueChoice("c1", "Accept", "next_node")
        node = DialogueNode(
            node_id="quest_offer",
            text="Will you help?",
            speaker="quest_giver",
            choices=[choice]
        )

        serialized = DialogueNodeSerializer.serialize(node)

        assert len(serialized["choices"]) == 1
        assert serialized["choices"][0]["choice_id"] == "c1"

    def test_deserialize_node(self):
        """Test deserialization of node dict."""
        data = {
            "node_id": "greeting",
            "text": "Hello!",
            "speaker": "npc_1",
            "npc_tone": "neutral",
            "choices": [],
            "condition": None
        }

        node = DialogueNodeSerializer.deserialize(data)

        assert node.node_id == "greeting"
        assert node.text == "Hello!"
        assert node.speaker == "npc_1"

    def test_deserialize_node_missing_field_raises_key_error(self):
        """Test deserialization with missing required field."""
        data = {"node_id": "node_1", "text": "Hello"}
        # Missing speaker

        with pytest.raises(KeyError):
            DialogueNodeSerializer.deserialize(data)

    def test_get_available_choices_simple(self):
        """Test getting available choices from node."""
        choice1 = DialogueChoice("c1", "Yes", "node_yes")
        choice2 = DialogueChoice("c2", "No", "node_no")
        node = DialogueNode(
            "question", "Do you agree?", "npc_1",
            choices=[choice1, choice2]
        )

        available = DialogueNodeSerializer.get_available_choices(
            node,
            player_story={},
            player_reputation={},
            player_level=1,
            player_completed_dialogues=[]
        )

        assert len(available) == 2


class TestConversationHistorySerializer:
    """Tests for ConversationHistorySerializer."""

    def test_serialize_conversation(self):
        """Test serialization of conversation history."""
        history = ConversationHistory(
            conversation_id="conv_001",
            npc_id="merchant_kael",
            player_id="player_1",
            dialogue_id="greeting_001",
            started_at="2025-11-10T10:00:00Z",
            nodes_visited=["greeting", "quest_offer"],
            choices_made=["yes_option"],
            status="completed"
        )

        serialized = ConversationHistorySerializer.serialize(history)

        assert serialized["conversation_id"] == "conv_001"
        assert serialized["npc_id"] == "merchant_kael"
        assert serialized["nodes_visited"] == ["greeting", "quest_offer"]
        assert serialized["status"] == "completed"

    def test_deserialize_conversation(self):
        """Test deserialization of conversation dict."""
        data = {
            "conversation_id": "conv_001",
            "npc_id": "npc_1",
            "player_id": "player_1",
            "dialogue_id": "dial_001",
            "started_at": "2025-11-10T10:00:00Z",
            "nodes_visited": [],
            "choices_made": [],
            "effects_applied": [],
            "status": "ongoing"
        }

        history = ConversationHistorySerializer.deserialize(data)

        assert history.conversation_id == "conv_001"
        assert history.status == "ongoing"

    def test_add_node_visit(self):
        """Test adding node visit to history."""
        history = ConversationHistory(
            "conv_1", "npc_1", "player_1", "dial_1",
            "2025-11-10T10:00:00Z"
        )

        ConversationHistorySerializer.add_node_visit(history, "node_1")
        ConversationHistorySerializer.add_node_visit(history, "node_1")  # Duplicate

        assert len(history.nodes_visited) == 1
        assert history.nodes_visited[0] == "node_1"

    def test_add_choice_to_history(self):
        """Test adding choice to history."""
        history = ConversationHistory(
            "conv_1", "npc_1", "player_1", "dial_1",
            "2025-11-10T10:00:00Z"
        )

        ConversationHistorySerializer.add_choice(history, "choice_1")
        ConversationHistorySerializer.add_choice(history, "choice_2")

        assert len(history.choices_made) == 2
        assert history.choices_made[0] == "choice_1"


class TestDialogueContextSerializer:
    """Tests for DialogueContextSerializer."""

    def test_serialize_dialogue_context(self):
        """Test serialization of dialogue context."""
        node = DialogueNode("greeting", "Hello!", "npc_1")
        choice = DialogueChoice("c1", "Accept", "node_2")
        history = ConversationHistory(
            "conv_1", "npc_1", "player_1", "dial_1",
            "2025-11-10T10:00:00Z"
        )
        context = DialogueContext(
            conversation_id="conv_1",
            current_node=node,
            available_choices=[choice],
            conversation_history=history,
            is_complete=False
        )

        serialized = DialogueContextSerializer.serialize(context)

        assert serialized["conversation_id"] == "conv_1"
        assert serialized["current_node"]["node_id"] == "greeting"
        assert len(serialized["available_choices"]) == 1
        assert serialized["is_complete"] is False

    def test_deserialize_dialogue_context(self):
        """Test deserialization of dialogue context dict."""
        data = {
            "conversation_id": "conv_1",
            "current_node": {
                "node_id": "greeting",
                "text": "Hello!",
                "speaker": "npc_1",
                "npc_tone": "friendly",
                "choices": [],
                "condition": None
            },
            "available_choices": [],
            "conversation_history": {
                "conversation_id": "conv_1",
                "npc_id": "npc_1",
                "player_id": "player_1",
                "dialogue_id": "dial_1",
                "started_at": "2025-11-10T10:00:00Z",
                "nodes_visited": [],
                "choices_made": [],
                "effects_applied": [],
                "status": "ongoing"
            },
            "is_complete": False
        }

        context = DialogueContextSerializer.deserialize(data)

        assert context.conversation_id == "conv_1"
        assert context.current_node.node_id == "greeting"
        assert context.is_complete is False
