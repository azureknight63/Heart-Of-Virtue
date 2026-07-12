"""
Tests for advanced API serializers:
- api/serializers/reputation.py (NPCRelationshipSerializer)
"""

from src.api.serializers.reputation import NPCRelationshipSerializer

# ===========================================================================
# NPCRelationshipSerializer
# ===========================================================================


class TestNPCRelationshipSerializer:
    def test_serialize_friendly(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", 75)
        assert result["attitude"] == "friendly"
        assert result["locked_dialogue"] is False

    def test_serialize_favorable(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", 30)
        assert result["attitude"] == "favorable"

    def test_serialize_neutral(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", 0)
        assert result["attitude"] == "neutral"
        assert result["locked_dialogue"] is False

    def test_serialize_wary(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", -10)
        assert result["attitude"] == "wary"
        assert result["locked_dialogue"] is True

    def test_serialize_hostile(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", -40)
        assert result["attitude"] == "hostile"

    def test_serialize_enemy(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", -75)
        assert result["attitude"] == "enemy"

    def test_calculate_trust_levels(self):
        assert NPCRelationshipSerializer._calculate_trust_level(80) == "Complete Trust"
        assert NPCRelationshipSerializer._calculate_trust_level(60) == "High Trust"
        assert NPCRelationshipSerializer._calculate_trust_level(30) == "Good Trust"
        assert NPCRelationshipSerializer._calculate_trust_level(10) == "Neutral"
        assert NPCRelationshipSerializer._calculate_trust_level(-10) == "Suspicious"
        assert NPCRelationshipSerializer._calculate_trust_level(-40) == "Distrusting"
        assert NPCRelationshipSerializer._calculate_trust_level(-80) == "Hostile"

    def test_get_npc_name_returns_input_unchanged(self):
        """_get_npc_name is a passthrough: reputation is keyed by NPC display name already."""
        assert NPCRelationshipSerializer._get_npc_name("Gorran") == "Gorran"
