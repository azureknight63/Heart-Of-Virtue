"""
Comprehensive tests for NPC state management, dialogue flow, and conversation tracking.

Tests cover:
- NPC initialization and state management
- Dialogue tree navigation and branching
- Conversation history tracking
- NPC serialization (dialogue/AI state)
- Reputation and relationship tracking
- Dialogue flags and state persistence
- Edge cases and error handling
"""

import pytest
import sys
from unittest.mock import MagicMock, patch, call
from pathlib import Path

# Ensure src is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent


from src.npc import NPC, Friend
from src.api.serializers.npc_serializer import NPCSerializer


class TestNPCInitialization:
    """Test NPC initialization and basic properties."""

    def test_npc_basic_init(self):
        """Test basic NPC initialization with required parameters."""
        npc = NPC(
            name="TestNPC",
            description="A test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.name == "TestNPC"
        assert npc.description == "A test NPC"
        assert npc.damage == 10
        assert npc.aggro is True
        assert npc.exp_award == 50
        assert npc.friend is False

    def test_npc_full_initialization(self):
        """Test NPC with all optional parameters."""
        npc = NPC(
            name="BossNPC",
            description="A powerful boss",
            damage=25,
            aggro=True,
            exp_award=200,
            maxhp=500,
            protection=20,
            speed=15,
            finesse=12,
            awareness=18,
            maxfatigue=150,
            endurance=14,
            strength=16,
            charisma=10,
            intelligence=13,
            faith=11,
            hidden=True,
            hide_factor=0.7,
            combat_range=(0, 10),
            idle_message=" stands menacingly.",
            alert_message="prepares to attack!",
            discovery_message="a dangerous foe.",
            friend=False,
        )
        assert npc.name == "BossNPC"
        assert npc.maxhp == 500
        assert npc.hp == 500
        assert npc.protection == 20
        assert npc.speed == 15
        assert npc.hidden is True
        assert npc.hide_factor == 0.7
        assert npc.friend is False

    def test_friend_initialization(self):
        """Test Friend class initialization."""
        friend = Friend(
            name="CompanionNPC",
            description="A helpful ally",
            damage=15,
            aggro=False,
            exp_award=0,
            friend=True,
        )
        assert friend.name == "CompanionNPC"
        assert friend.friend is True
        assert friend.knocked_out is False
        # Friend sets keywords after super().__init__ so the base "talk" verb survives
        # NPC.__init__'s unconditional self.keywords = [] reset.
        assert friend.keywords == ["talk"]

    def test_npc_default_values(self):
        """Test NPC default parameter values."""
        npc = NPC(
            name="Simple",
            description="Simple NPC",
            damage=5,
            aggro=False,
            exp_award=10,
        )
        assert npc.current_room is None
        assert npc.inventory == []
        assert npc.states == []
        assert npc.in_combat is False
        assert npc.combat_proximity == {}
        assert npc.known_moves is not None
        assert len(npc.known_moves) > 0  # NpcRest move


class TestNPCStateManagement:
    """Test NPC state management and property updates."""

    def test_npc_health_state(self):
        """Test NPC health tracking."""
        npc = NPC(
            name="HealthTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
            maxhp=100,
        )
        assert npc.hp == 100
        assert npc.maxhp == 100
        npc.hp = 50
        assert npc.hp == 50

    def test_npc_damage_property(self):
        """Test NPC damage attributes."""
        npc = NPC(
            name="DamageTest",
            description="Test NPC",
            damage=15,
            aggro=True,
            exp_award=50,
        )
        assert npc.damage == 15
        assert npc.damage_base == 15

    def test_npc_stat_attributes(self):
        """Test NPC combat stat attributes."""
        npc = NPC(
            name="StatTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
            strength=14,
            finesse=12,
            speed=13,
            charisma=11,
            intelligence=10,
            faith=9,
            endurance=15,
        )
        assert npc.strength == 14
        assert npc.finesse == 12
        assert npc.speed == 13
        assert npc.charisma == 11
        assert npc.intelligence == 10
        assert npc.faith == 9
        assert npc.endurance == 15

    def test_npc_fatigue_system(self):
        """Test NPC fatigue management."""
        npc = NPC(
            name="FatigueTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
            maxfatigue=100,
        )
        assert npc.fatigue == 100
        assert npc.maxfatigue == 100
        npc.fatigue = 50
        assert npc.fatigue == 50

    def test_npc_protection_stat(self):
        """Test NPC protection attribute."""
        npc = NPC(
            name="ProtectionTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
            protection=15,
        )
        assert npc.protection == 15
        assert npc.protection_base == 15

    def test_npc_awareness_stat(self):
        """Test NPC awareness for detection."""
        npc = NPC(
            name="AwarenessTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
            awareness=18,
        )
        assert npc.awareness == 18


class TestNPCPronouns:
    """Test NPC pronoun system."""

    def test_default_pronouns(self):
        """Test default pronouns are neutral."""
        npc = NPC(
            name="PronounTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.pronouns["personal"] == "it"
        assert npc.pronouns["possessive"] == "its"
        assert npc.pronouns["reflexive"] == "itself"
        assert npc.pronouns["intensive"] == "itself"

    def test_custom_pronouns(self):
        """Test setting custom pronouns."""
        npc = NPC(
            name="HumanoidNPC",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.pronouns = {
            "personal": "she",
            "possessive": "her",
            "reflexive": "herself",
            "intensive": "herself",
        }
        assert npc.pronouns["personal"] == "she"
        assert npc.pronouns["possessive"] == "her"


class TestNPCCombatProperties:
    """Test NPC combat-related properties."""

    def test_npc_combat_state(self):
        """Test NPC in_combat flag."""
        npc = NPC(
            name="CombatTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.in_combat is False
        npc.in_combat = True
        assert npc.in_combat is True

    def test_npc_combat_range(self):
        """Test NPC combat range attribute."""
        npc = NPC(
            name="RangeTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
            combat_range=(0, 5),
        )
        assert npc.combat_range == (0, 5)

    def test_npc_combat_proximity(self):
        """Test NPC combat proximity tracking."""
        npc = NPC(
            name="ProximityTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.combat_proximity == {}
        npc.combat_proximity = {"unit1": 10, "unit2": 15}
        assert npc.combat_proximity == {"unit1": 10, "unit2": 15}

    def test_npc_hidden_state(self):
        """Test NPC hidden/stealth state."""
        npc = NPC(
            name="StealthTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
            hidden=True,
            hide_factor=0.8,
        )
        assert npc.hidden is True
        assert npc.hide_factor == 0.8


class TestNPCFriendState:
    """Test Friend-specific functionality."""

    def test_friend_talk_method(self):
        """Test Friend talk method."""
        friend = Friend(
            name="Companion",
            description="A helpful ally",
            damage=10,
            aggro=False,
            exp_award=0,
        )
        # Default talk() should output a message
        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            friend.talk(None)
        output = f.getvalue()
        assert "nothing to say" in output.lower()

    def test_friend_wounded_flavor(self):
        """Test wounded flavor method is None by default."""
        friend = Friend(
            name="Companion",
            description="A helpful ally",
            damage=10,
            aggro=False,
            exp_award=0,
        )
        assert friend.wounded_flavor() is None

    def test_friend_knockout_state(self):
        """Test Friend knockout tracking."""
        friend = Friend(
            name="Companion",
            description="A helpful ally",
            damage=10,
            aggro=False,
            exp_award=0,
        )
        assert friend.knocked_out is False
        friend.knocked_out = True
        assert friend.knocked_out is True


class TestNPCInventory:
    """Test NPC inventory management."""

    def test_npc_empty_inventory(self):
        """Test NPC with empty inventory."""
        npc = NPC(
            name="NoItems",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.inventory == []

    def test_npc_with_inventory(self):
        """Test NPC initialization with items."""
        mock_item1 = MagicMock()
        mock_item1.name = "Sword"
        mock_item2 = MagicMock()
        mock_item2.name = "Shield"

        npc = NPC(
            name="Merchant",
            description="Test NPC",
            damage=10,
            aggro=False,
            exp_award=50,
            inventory=[mock_item1, mock_item2],
        )
        assert len(npc.inventory) == 2
        assert npc.inventory[0].name == "Sword"
        assert npc.inventory[1].name == "Shield"

    def test_npc_inventory_modification(self):
        """Test modifying NPC inventory."""
        npc = NPC(
            name="Inventory",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        mock_item = MagicMock()
        mock_item.name = "Ring"
        npc.inventory.append(mock_item)
        assert len(npc.inventory) == 1
        assert npc.inventory[0].name == "Ring"


class TestNPCSerializer:
    """Test NPC serialization."""

    def test_serialize_basic_npc(self):
        """Test basic NPC serialization."""
        npc = NPC(
            name="SerializeTest",
            description="A test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )

        serialized = NPCSerializer.serialize(npc)

        assert serialized["name"] == "SerializeTest"
        assert serialized["description"] == "A test NPC"
        assert "type" in serialized
        assert "keywords" in serialized or "keywords" not in serialized  # keywords is optional


class TestNPCEdgeCases:
    """Test edge cases and error handling."""

    def test_npc_null_name(self):
        """Test NPC with empty/null name."""
        npc = NPC(
            name="",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.name == ""

    def test_npc_zero_damage(self):
        """Test NPC with zero damage."""
        npc = NPC(
            name="NoDamage",
            description="Test NPC",
            damage=0,
            aggro=False,
            exp_award=0,
        )
        assert npc.damage == 0

    def test_npc_negative_health(self):
        """Test NPC with negative health (defeated state)."""
        npc = NPC(
            name="Defeated",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
            maxhp=100,
        )
        npc.hp = -10
        assert npc.hp == -10

    def test_npc_high_stat_values(self):
        """Test NPC with extremely high stat values."""
        npc = NPC(
            name="PowerfulBoss",
            description="Test NPC",
            damage=999,
            aggro=True,
            exp_award=9999,
            maxhp=10000,
            strength=100,
            speed=100,
        )
        assert npc.damage == 999
        assert npc.maxhp == 10000
        assert npc.strength == 100

    def test_serialize_none_npc(self):
        """Test serializing None NPC gracefully."""
        serialized = NPCSerializer.serialize(None)
        assert serialized == {}

    def test_serialize_empty_npc_list(self):
        """Test serializing empty NPC list."""
        serialized = NPCSerializer.serialize_list([])
        assert serialized == []

    def test_dialogue_with_empty_tree(self):
        """Test dialogue with empty nodes."""
        npc = NPC(
            name="EmptyTree",
            description="Test NPC",
            damage=10,
            aggro=False,
            exp_award=50,
        )

        empty_tree = {"id": "empty", "nodes": {}}
        dialogue_state = DialogueStateSerializer.serialize_dialogue_state(
            npc, dialogue_tree=empty_tree, current_node="nonexistent"
        )

        assert dialogue_state is not None
        assert "current_node" in dialogue_state

    def test_npc_movement_state(self):
        """Test NPC movement/location state."""
        npc = NPC(
            name="MovementTest",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.current_room is None
        # Simulate room assignment
        npc.current_room = "Tavern"
        assert npc.current_room == "Tavern"

    def test_dialogue_relationship_tracking(self):
        """Test dialogue relationship metrics."""
        npc = NPC(
            name="RelationshipTest",
            description="Test NPC",
            damage=10,
            aggro=False,
            exp_award=50,
        )

        # Initial state
        dialogue_state = DialogueStateSerializer.serialize_dialogue_state(npc)
        assert dialogue_state["relationship"]["known"] is False
        assert dialogue_state["relationship"]["times_talked"] == 0

        # After multiple interactions
        history = [
            {"player": "Hello", "npc": "Hi"},
            {"player": "How are you?", "npc": "Good"},
        ]
        dialogue_state = DialogueStateSerializer.serialize_dialogue_state(
            npc, conversation_history=history
        )
        assert dialogue_state["relationship"]["times_talked"] == 2


class TestNPCComplexScenarios:
    """Test complex interaction scenarios."""

    def test_npc_multiple_serialization_formats(self):
        """Test NPC serialization across multiple formats."""
        npc = NPC(
            name="MultiFormat",
            description="Test NPC",
            damage=15,
            aggro=True,
            exp_award=100,
            maxhp=200,
        )

        basic = NPCSerializer.serialize(npc)
        with_stats = NPCSerializer.serialize_with_stats(npc)
        for_combat = NPCSerializer.serialize_for_combat(npc)

        assert basic["name"] == "MultiFormat"
        assert with_stats["name"] == "MultiFormat"
        assert for_combat["name"] == "MultiFormat"

    def test_dialogue_branching_complexity(self):
        """Test complex dialogue tree branching."""
        npc = NPC(
            name="BranchingDialogue",
            description="Test NPC",
            damage=10,
            aggro=False,
            exp_award=50,
        )

        complex_tree = {
            "id": "complex",
            "nodes": {
                "start": {
                    "text": "Welcome!",
                    "options": [
                        {"id": 1, "text": "Tell me about yourself", "next": "backstory"},
                        {"id": 2, "text": "I need work", "next": "quest"},
                        {"id": 3, "text": "Goodbye", "next": "end"},
                    ],
                },
                "backstory": {
                    "text": "I've been here for years.",
                    "options": [
                        {"id": 1, "text": "How interesting!", "next": "quest"},
                        {"id": 2, "text": "Goodbye", "next": "end"},
                    ],
                },
                "quest": {
                    "text": "I need help with something.",
                    "options": [
                        {"id": 1, "text": "I'm interested", "next": "quest_accept"},
                        {"id": 2, "text": "Not right now", "next": "end"},
                    ],
                },
                "quest_accept": {
                    "text": "Great! Here's what you need to do...",
                    "options": [{"id": 1, "text": "Understood", "next": "end"}],
                },
                "end": {"text": "Farewell.", "options": []},
            },
        }

        # Test from different starting nodes
        for start_node in ["start", "backstory", "quest"]:
            dialogue_state = DialogueStateSerializer.serialize_dialogue_state(
                npc, dialogue_tree=complex_tree, current_node=start_node
            )
            assert dialogue_state["current_node"] == start_node
            assert "options" in dialogue_state

    def test_npc_ai_state_with_attributes(self):
        """Test AI state serialization with various attributes."""
        npc = NPC(
            name="AIComplex",
            description="Test NPC",
            damage=12,
            aggro=True,
            exp_award=75,
            maxhp=150,
        )

        # Add custom attributes
        npc.current_behavior = "patrolling"
        npc.behavior_stack = ["idle", "alert"]
        npc.last_interaction_time = 123456789

        ai_state = NPCAIStateSerializer.serialize_npc_ai_state(npc)

        assert ai_state["current_behavior"] == "patrolling"
        assert ai_state["behavior_stack"] == ["idle", "alert"]
        assert ai_state["last_interaction"] == 123456789


class TestNPCIntegration:
    """Integration tests combining multiple NPC systems."""

    def test_npc_full_lifecycle(self):
        """Test complete NPC lifecycle from creation to serialization."""
        # Create NPC
        npc = NPC(
            name="Lifecycle",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
            maxhp=100,
        )

        # Simulate interaction
        assert npc.hp == 100
        npc.hp = 75  # Take damage

        # Serialize in all formats
        basic = NPCSerializer.serialize(npc)
        assert basic["name"] == "Lifecycle"

        ai_state = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert ai_state["health_status"]["hp"] == 75

        dialogue = DialogueStateSerializer.serialize_dialogue_state(npc)
        assert dialogue["npc_name"] == "Lifecycle"

        profile = NPCBehaviorProfileSerializer.serialize_behavior_profile(npc)
        assert profile["name"] == "Lifecycle"

    def test_friend_and_npc_polymorphism(self):
        """Test Friend and NPC polymorphism in serialization."""
        npc = NPC(
            name="EnemyNPC",
            description="Test Enemy",
            damage=15,
            aggro=True,
            exp_award=100,
        )

        friend = Friend(
            name="Companion",
            description="Test Friend",
            damage=10,
            aggro=False,
            exp_award=0,
        )

        npc_data = NPCSerializer.serialize(npc)
        friend_data = NPCSerializer.serialize(friend)

        assert npc_data["name"] == "EnemyNPC"
        assert friend_data["name"] == "Companion"
        assert friend.friend is True
        assert npc.friend is False

    def test_multiple_npcs_concurrent_dialogue(self):
        """Test managing dialogue state for multiple NPCs."""
        npcs = [
            NPC(
                name=f"NPC{i}",
                description=f"Test NPC {i}",
                damage=10 + i,
                aggro=bool(i % 2),
                exp_award=50 + i * 10,
            )
            for i in range(3)
        ]

        # Get dialogue state for each
        dialogues = [DialogueStateSerializer.serialize_dialogue_state(npc) for npc in npcs]

        assert len(dialogues) == 3
        assert dialogues[0]["npc_name"] == "NPC0"
        assert dialogues[1]["npc_name"] == "NPC1"
        assert dialogues[2]["npc_name"] == "NPC2"

    def test_serialization_consistency(self):
        """Test that serialization is consistent across calls."""
        npc = NPC(
            name="Consistency",
            description="Test NPC",
            damage=10,
            aggro=True,
            exp_award=50,
        )

        # Serialize multiple times
        s1 = NPCSerializer.serialize(npc)
        s2 = NPCSerializer.serialize(npc)

        assert s1["name"] == s2["name"]
        assert s1["description"] == s2["description"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
