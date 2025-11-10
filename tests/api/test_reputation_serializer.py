"""Tests for reputation serializers (Phase 3 Stage 2)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.serializers.reputation import (
    NPCRelationshipSerializer,
    PlayerReputationSerializer,
    RelationshipFlagSerializer,
    ReputationThresholdValidator,
)


class TestNPCRelationshipSerializer:
    """Tests for NPCRelationshipSerializer."""

    def test_serialize_relationship_friendly(self):
        """Test serializing a friendly relationship."""
        result = NPCRelationshipSerializer.serialize_relationship(
            "merchant", "Merchant", 60
        )

        assert result["npc_id"] == "merchant"
        assert result["npc_name"] == "Merchant"
        assert result["reputation"] == 60
        assert result["attitude"] == "friendly"
        assert result["emoji"] == "😊"
        assert result["trust_level"] == "High Trust"
        assert result["locked_dialogue"] is False

    def test_serialize_relationship_neutral(self):
        """Test serializing a neutral relationship."""
        result = NPCRelationshipSerializer.serialize_relationship(
            "npc_1", "NPC One", 0
        )

        assert result["attitude"] == "neutral"
        assert result["emoji"] == "😐"
        assert result["trust_level"] == "Neutral"

    def test_serialize_relationship_hostile(self):
        """Test serializing a hostile relationship."""
        result = NPCRelationshipSerializer.serialize_relationship(
            "enemy", "Enemy NPC", -50
        )

        assert result["attitude"] == "hostile"
        assert result["emoji"] == "😠"
        assert result["trust_level"] == "Distrusting"
        assert result["locked_dialogue"] is True

    def test_serialize_relationship_very_hostile(self):
        """Test serializing a very hostile relationship."""
        result = NPCRelationshipSerializer.serialize_relationship(
            "enemy", "Enemy NPC", -80
        )

        assert result["attitude"] == "enemy"
        assert result["emoji"] == "😡"
        assert result["trust_level"] == "Hostile"

    def test_calculate_trust_level_complete_trust(self):
        """Test trust level calculation for complete trust."""
        level = NPCRelationshipSerializer._calculate_trust_level(75)
        assert level == "Complete Trust"

    def test_calculate_trust_level_high_trust(self):
        """Test trust level calculation for high trust."""
        level = NPCRelationshipSerializer._calculate_trust_level(60)
        assert level == "High Trust"

    def test_calculate_trust_level_suspicious(self):
        """Test trust level calculation for suspicious."""
        level = NPCRelationshipSerializer._calculate_trust_level(-25)
        assert level == "Suspicious"

    def test_get_npc_name_known_npc(self):
        """Test getting NPC name for known NPC."""
        name = NPCRelationshipSerializer._get_npc_name("cave_guide")
        assert name == "Cave Guide"

    def test_get_npc_name_unknown_npc(self):
        """Test getting NPC name for unknown NPC."""
        name = NPCRelationshipSerializer._get_npc_name("custom_npc_123")
        assert name == "Custom Npc 123"


class TestPlayerReputationSerializer:
    """Tests for PlayerReputationSerializer."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player with reputation data."""
        from src.player import Player

        player = Player()
        player.reputation = {
            "merchant": 60,
            "cave_guide": 30,
            "blacksmith": -40,
            "dragon_slayer": 80,
        }
        return player

    def test_serialize_all_reputation(self, mock_player):
        """Test serializing all reputation data."""
        result = PlayerReputationSerializer.serialize_all_reputation(mock_player)

        assert result["total_npcs"] == 4
        assert result["highest_reputation"] == 80
        assert result["lowest_reputation"] == -40
        assert result["friendly_npcs"] == 2  # merchant (60), dragon_slayer (80)
        assert result["hostile_npcs"] == 0  # blacksmith (-40) is "wary", not hostile

        # Check individual relationships are serialized
        assert "merchant" in result["relationships"]
        assert result["relationships"]["merchant"]["reputation"] == 60
        assert result["relationships"]["merchant"]["attitude"] == "friendly"

    def test_serialize_reputation_change(self):
        """Test serializing a reputation change event."""
        result = PlayerReputationSerializer.serialize_reputation_change(
            "merchant", "Merchant", 30, 60, "quest_complete"
        )

        assert result["npc_id"] == "merchant"
        assert result["old_reputation"] == 30
        assert result["new_reputation"] == 60
        assert result["change"] == 30
        assert result["direction"] == "positive"
        assert result["reason"] == "quest_complete"
        assert result["attitude_changed"] is True
        assert result["old_attitude"] == "favorable"
        assert result["new_attitude"] == "friendly"

    def test_serialize_reputation_change_negative(self):
        """Test serializing a negative reputation change."""
        result = PlayerReputationSerializer.serialize_reputation_change(
            "npc", "NPC", 50, 30, "dialogue_choice"
        )

        assert result["change"] == -20
        assert result["direction"] == "negative"
        assert result["attitude_changed"] is True

    def test_serialize_reputation_change_no_attitude_change(self):
        """Test reputation change with no attitude change."""
        result = PlayerReputationSerializer.serialize_reputation_change(
            "npc", "NPC", 50, 55, "quest_bonus"
        )

        assert result["change"] == 5
        assert result["direction"] == "positive"
        assert result["attitude_changed"] is False

    def test_get_npc_name_mapping(self):
        """Test NPC name mapping."""
        assert PlayerReputationSerializer._get_npc_name("healer") == "Healer"
        assert PlayerReputationSerializer._get_npc_name("blacksmith") == "Blacksmith"


class TestRelationshipFlagSerializer:
    """Tests for RelationshipFlagSerializer."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        from src.player import Player

        player = Player()
        return player

    def test_set_flag_success(self, mock_player):
        """Test setting a flag successfully."""
        result = RelationshipFlagSerializer.set_flag(
            mock_player, "merchant", "romance", True
        )

        assert result["success"] is True
        assert result["npc_id"] == "merchant"
        assert result["flag"] == "romance"
        assert result["new_value"] is True
        assert result["changed"] is True

        # Verify flag was set
        assert mock_player.relationship_flags["merchant"]["romance"] is True

    def test_set_flag_invalid_flag(self, mock_player):
        """Test setting an invalid flag."""
        result = RelationshipFlagSerializer.set_flag(
            mock_player, "merchant", "invalid_flag", True
        )

        assert result["success"] is False
        assert "Invalid flag" in result["error"]

    def test_set_flag_multiple_flags(self, mock_player):
        """Test setting multiple flags for same NPC."""
        RelationshipFlagSerializer.set_flag(
            mock_player, "merchant", "romance", True
        )
        RelationshipFlagSerializer.set_flag(
            mock_player, "merchant", "alliance", True
        )

        flags = mock_player.relationship_flags["merchant"]
        assert flags["romance"] is True
        assert flags["alliance"] is True

    def test_set_flag_toggle(self, mock_player):
        """Test toggling a flag off."""
        RelationshipFlagSerializer.set_flag(
            mock_player, "merchant", "romance", True
        )
        result = RelationshipFlagSerializer.set_flag(
            mock_player, "merchant", "romance", False
        )

        assert result["old_value"] is True
        assert result["new_value"] is False
        assert result["changed"] is True

    def test_get_flags(self, mock_player):
        """Test getting flags for an NPC."""
        RelationshipFlagSerializer.set_flag(
            mock_player, "merchant", "romance", True
        )
        RelationshipFlagSerializer.set_flag(
            mock_player, "merchant", "alliance", True
        )

        result = RelationshipFlagSerializer.get_flags(mock_player, "merchant")

        assert result["npc_id"] == "merchant"
        assert result["active_count"] == 2
        assert result["flag_count"] == 2
        assert "romance" in result["active_flags"]
        assert "alliance" in result["active_flags"]

    def test_get_flags_no_flags(self, mock_player):
        """Test getting flags when none are set."""
        result = RelationshipFlagSerializer.get_flags(mock_player, "unknown_npc")

        assert result["npc_id"] == "unknown_npc"
        assert result["active_count"] == 0
        assert result["flag_count"] == 0

    def test_serialize_flags_summary(self, mock_player):
        """Test serializing flags summary."""
        RelationshipFlagSerializer.set_flag(
            mock_player, "merchant", "romance", True
        )
        RelationshipFlagSerializer.set_flag(
            mock_player, "blacksmith", "alliance", True
        )
        RelationshipFlagSerializer.set_flag(
            mock_player, "blacksmith", "enemy", True
        )

        result = RelationshipFlagSerializer.serialize_flags_summary(mock_player)

        assert result["total_npcs_with_flags"] == 2
        assert result["total_active_flags"] == 3
        assert result["romance_count"] == 1
        assert result["allied_npcs"] == 1
        assert result["enemy_npcs"] == 1


class TestReputationThresholdValidator:
    """Tests for ReputationThresholdValidator."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        from src.player import Player

        player = Player()
        player.reputation = {"merchant": 60, "blacksmith": -40}
        return player

    def test_check_dialogue_available_friendly(self, mock_player):
        """Test dialogue available for friendly NPC."""
        available, reason = ReputationThresholdValidator.check_dialogue_available(
            mock_player, "merchant", "special_dialogue"
        )

        assert available is True
        assert reason is None

    def test_check_dialogue_available_locked(self, mock_player):
        """Test dialogue locked for low reputation."""
        available, reason = ReputationThresholdValidator.check_dialogue_available(
            mock_player, "blacksmith", "special_dialogue"
        )

        assert available is False
        assert "doesn't want to talk" in reason

    def test_check_quest_available_normal_quest(self, mock_player):
        """Test normal quest available at neutral."""
        available, reason = ReputationThresholdValidator.check_quest_available(
            mock_player, "merchant", "normal_quest"
        )

        assert available is True
        assert reason is None

    def test_check_quest_available_secret_quest_locked(self, mock_player):
        """Test secret quest locked at low reputation."""
        available, reason = ReputationThresholdValidator.check_quest_available(
            mock_player, "blacksmith", "secret_quest"
        )

        assert available is False
        assert "doesn't trust you" in reason

    def test_serialize_dialogue_locks(self, mock_player):
        """Test serializing dialogue locks."""
        dialogues = ["greeting_friendly", "quest_offer", "special_dialogue"]
        result = ReputationThresholdValidator.serialize_dialogue_locks(
            mock_player, "merchant", dialogues
        )

        assert result["npc_id"] == "merchant"
        assert result["current_reputation"] == 60
        assert result["total_dialogues"] == 3
        assert result["unlocked_dialogues"] == 3

        # All should be available for merchant
        for node, status in result["dialogue_status"].items():
            assert status["available"] is True

    def test_serialize_dialogue_locks_hostile(self, mock_player):
        """Test serializing dialogue locks for hostile NPC."""
        dialogues = [
            "greeting_friendly",
            "quest_offer",
            "special_dialogue",
            "betrayal_available",
        ]
        result = ReputationThresholdValidator.serialize_dialogue_locks(
            mock_player, "blacksmith", dialogues
        )

        assert result["current_reputation"] == -40
        assert result["locked_dialogues"] > 0

    def test_serialize_quest_locks(self, mock_player):
        """Test serializing quest locks."""
        quests = [
            ("q1", "normal_quest"),
            ("q2", "important_quest"),
            ("q3", "secret_quest"),
        ]
        result = ReputationThresholdValidator.serialize_quest_locks(
            mock_player, "merchant", quests
        )

        assert result["npc_id"] == "merchant"
        assert result["total_quests"] == 3
        assert result["unlocked_quests"] >= 2  # normal and important at least

    def test_serialize_quest_locks_hostile(self, mock_player):
        """Test serializing quest locks for hostile NPC."""
        quests = [("q1", "secret_quest")]
        result = ReputationThresholdValidator.serialize_quest_locks(
            mock_player, "blacksmith", quests
        )

        assert result["current_reputation"] == -40
        assert result["unlocked_quests"] == 0
        assert result["locked_quests"] == 1
