"""Tests for the reputation serializer.

Covers NPCRelationshipSerializer — the chat-relationship-badge and
shop-price-modifier serializer. The route-gating serializers it used to share
this module with (PlayerReputationSerializer, RelationshipFlagSerializer,
ReputationThresholdValidator) backed the dead `/api/reputation/*` routes and
were removed along with them (see issue #252).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.serializers.reputation import NPCRelationshipSerializer


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

    def test_get_npc_name_returns_input_unchanged(self):
        """_get_npc_name is a passthrough: reputation is keyed by NPC display name already."""
        name = NPCRelationshipSerializer._get_npc_name("Gorran")
        assert name == "Gorran"

    def test_get_price_modifier_friendly(self):
        """Max positive reputation yields the full +15% favorable swing."""
        modifier = NPCRelationshipSerializer.get_price_modifier(100)
        assert modifier == pytest.approx(0.15)

    def test_get_price_modifier_hostile(self):
        """Max negative reputation yields the full -15% unfavorable swing."""
        modifier = NPCRelationshipSerializer.get_price_modifier(-100)
        assert modifier == pytest.approx(-0.15)

    def test_get_price_modifier_neutral(self):
        """Zero reputation has no effect on price."""
        assert NPCRelationshipSerializer.get_price_modifier(0) == 0.0
