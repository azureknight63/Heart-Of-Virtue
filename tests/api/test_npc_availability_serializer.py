"""
Tests for NPC Availability Serializers (Stage 4)

Tests all serializer classes for proper location tracking, availability checking,
and timeline progression.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.serializers.npc_availability import (
    NPCLocationSerializer,
    NPCAvailabilitySerializer,
    LocationNPCSerializer,
    NPCTimelineSerializer,
    NPCEventTriggerSerializer,
    NPCStatusSerializer,
    AvailabilityReason,
)


class TestNPCLocationSerializer:
    """Test location serialization and NPC position tracking."""

    def test_serialize_location(self):
        """Test serializing a location to JSON format."""
        location_data = {
            "location_id": "loc_forge",
            "map_name": "village",
            "coords": [10, 20],
            "description": "Blacksmith's Forge",
        }
        result = NPCLocationSerializer.serialize(location_data)
        
        assert result["location_id"] == "loc_forge"
        assert result["map_name"] == "village"
        assert result["coords"] == [10, 20]
        assert result["description"] == "Blacksmith's Forge"

    def test_deserialize_location(self):
        """Test deserializing a location from JSON format."""
        location_dict = {
            "location_id": "loc_forge",
            "map_name": "village",
            "coords": [10, 20],
            "description": "Blacksmith's Forge",
        }
        result = NPCLocationSerializer.deserialize(location_dict)
        
        assert result["location_id"] == "loc_forge"
        assert result["coords"] == (10, 20)  # Should be tuple
        assert isinstance(result["coords"], tuple)

    def test_get_location_story_gate_met(self):
        """Test getting NPC location when story gate is met."""
        npc_data = {
            "npc_id": "kael",
            "locations": [
                {
                    "location_id": "loc_forge",
                    "map_name": "village",
                    "coords": [10, 20],
                    "available_after_ticks": 0,
                    "available_after_story": "ch01_forge_unlocked",
                    "description": "Forge",
                }
            ],
        }
        player_story = {"ch01_forge_unlocked": "1"}
        
        location = NPCLocationSerializer.get_location(npc_data, game_tick=100, player_story=player_story)
        
        assert location is not None
        assert location["location_id"] == "loc_forge"

    def test_get_location_story_gate_not_met(self):
        """Test getting NPC location when story gate is not met."""
        npc_data = {
            "npc_id": "kael",
            "locations": [
                {
                    "location_id": "loc_forge",
                    "available_after_story": "ch01_forge_unlocked",
                }
            ],
        }
        player_story = {}  # Gate not met
        
        location = NPCLocationSerializer.get_location(npc_data, game_tick=100, player_story=player_story)
        
        assert location is None

    def test_get_location_tick_requirement_not_met(self):
        """Test getting NPC location when tick requirement not met."""
        npc_data = {
            "npc_id": "kael",
            "locations": [
                {
                    "location_id": "loc_forge",
                    "available_after_ticks": 500,
                    "available_after_story": "ch01_forge_unlocked",
                }
            ],
        }
        player_story = {"ch01_forge_unlocked": "1"}
        
        # Only at tick 100, but need 500
        location = NPCLocationSerializer.get_location(npc_data, game_tick=100, player_story=player_story)
        
        assert location is None

    def test_get_location_tick_requirement_met(self):
        """Test getting NPC location when tick requirement is met."""
        npc_data = {
            "npc_id": "kael",
            "locations": [
                {
                    "location_id": "loc_forge",
                    "map_name": "village",
                    "coords": [10, 20],
                    "available_after_ticks": 500,
                    "available_after_story": "ch01_forge_unlocked",
                    "description": "Forge",
                }
            ],
        }
        player_story = {"ch01_forge_unlocked": "1"}
        
        # At tick 600, should be available
        location = NPCLocationSerializer.get_location(npc_data, game_tick=600, player_story=player_story)
        
        assert location is not None
        assert location["location_id"] == "loc_forge"

    def test_is_at_location_true(self):
        """Test checking if NPC is at a specific location."""
        npc_data = {
            "npc_id": "kael",
            "locations": [
                {
                    "location_id": "loc_forge",
                    "available_after_ticks": 0,
                    "available_after_story": "ch01_forge_unlocked",
                }
            ],
        }
        player_story = {"ch01_forge_unlocked": "1"}
        
        is_here = NPCLocationSerializer.is_at_location(
            "kael", "loc_forge", npc_data, game_tick=100, player_story=player_story
        )
        
        assert is_here is True

    def test_is_at_location_false(self):
        """Test checking if NPC is at wrong location."""
        npc_data = {
            "npc_id": "kael",
            "locations": [
                {
                    "location_id": "loc_forge",
                    "available_after_story": "ch01_forge_unlocked",
                }
            ],
        }
        player_story = {"ch01_forge_unlocked": "1"}
        
        is_here = NPCLocationSerializer.is_at_location(
            "kael", "loc_tavern", npc_data, game_tick=100, player_story=player_story
        )
        
        assert is_here is False


class TestNPCAvailabilitySerializer:
    """Test availability checking based on story gates and tick requirements."""

    def test_check_story_gates_met(self):
        """Test checking story gates when all are met."""
        npc_data = {
            "availability_conditions": {
                "story_gates": ["ch01_forge_unlocked", "ch02_apprentice"],
            }
        }
        player_story = {"ch01_forge_unlocked": "1", "ch02_apprentice": "1"}
        
        is_met, missing = NPCAvailabilitySerializer.check_story_gates(npc_data, player_story)
        
        assert is_met is True
        assert missing is None

    def test_check_story_gates_not_met(self):
        """Test checking story gates when one is missing."""
        npc_data = {
            "availability_conditions": {
                "story_gates": ["ch01_forge_unlocked", "ch02_apprentice"],
            }
        }
        player_story = {"ch01_forge_unlocked": "1"}  # Missing ch02_apprentice
        
        is_met, missing = NPCAvailabilitySerializer.check_story_gates(npc_data, player_story)
        
        assert is_met is False
        assert missing == "ch02_apprentice"

    def test_check_tick_requirements_met(self):
        """Test checking tick requirements when met."""
        npc_data = {
            "availability_conditions": {
                "min_ticks_after_gate": 200,
            }
        }
        # Gate completed at tick 100, now at tick 350
        is_met, ticks_until = NPCAvailabilitySerializer.check_tick_requirements(
            npc_data, game_tick=350, gate_completion_tick=100
        )
        
        assert is_met is True
        assert ticks_until is None

    def test_check_tick_requirements_not_met(self):
        """Test checking tick requirements when not met."""
        npc_data = {
            "availability_conditions": {
                "min_ticks_after_gate": 200,
            }
        }
        # Gate completed at tick 100, now at tick 150
        is_met, ticks_until = NPCAvailabilitySerializer.check_tick_requirements(
            npc_data, game_tick=150, gate_completion_tick=100
        )
        
        assert is_met is False
        assert ticks_until == 150  # (100 + 200) - 150 = 150

    def test_is_available_all_conditions_met(self):
        """Test availability when all conditions are met."""
        npc_data = {
            "availability_conditions": {
                "story_gates": ["ch01_forge_unlocked"],
                "min_ticks_after_gate": 0,
            },
            "locations": [
                {
                    "location_id": "loc_forge",
                    "available_after_story": "ch01_forge_unlocked",
                }
            ],
        }
        player_story = {"ch01_forge_unlocked": "1"}
        
        is_available, reason = NPCAvailabilitySerializer.is_available(
            npc_data, game_tick=100, player_story=player_story
        )
        
        assert is_available is True
        assert reason == AvailabilityReason.AVAILABLE

    def test_is_available_story_gate_not_met(self):
        """Test availability when story gate is not met."""
        npc_data = {
            "availability_conditions": {
                "story_gates": ["ch01_forge_unlocked"],
            },
        }
        player_story = {}  # Gate not met
        
        is_available, reason = NPCAvailabilitySerializer.is_available(
            npc_data, game_tick=100, player_story=player_story
        )
        
        assert is_available is False
        assert reason == AvailabilityReason.STORY_GATE_NOT_MET

    def test_is_available_not_in_world(self):
        """Test availability when NPC has no valid location."""
        npc_data = {
            "availability_conditions": {
                "story_gates": [],
                "min_ticks_after_gate": 0,
            },
            "locations": [],  # No locations available
        }
        player_story = {}
        
        is_available, reason = NPCAvailabilitySerializer.is_available(
            npc_data, game_tick=100, player_story=player_story
        )
        
        assert is_available is False
        assert reason == AvailabilityReason.NOT_IN_WORLD

    def test_serialize_availability(self):
        """Test serializing full availability status."""
        npc_data = {
            "npc_id": "kael",
            "availability_conditions": {
                "story_gates": ["ch01_forge_unlocked"],
                "min_ticks_after_gate": 0,
            },
            "locations": [
                {
                    "location_id": "loc_forge",
                    "map_name": "village",
                    "coords": [10, 20],
                    "available_after_story": "ch01_forge_unlocked",
                    "description": "Forge",
                }
            ],
        }
        player_story = {"ch01_forge_unlocked": "1"}
        
        result = NPCAvailabilitySerializer.serialize(npc_data, game_tick=100, player_story=player_story)
        
        assert result["available"] is True
        assert result["story_gates_met"] is True
        assert result["in_world"] is True
        assert result["current_location"]["location_id"] == "loc_forge"


class TestLocationNPCSerializer:
    """Test getting NPCs at a specific location."""

    def test_get_npcs_at_location_empty(self):
        """Test getting NPCs at a location with no NPCs."""
        all_npcs = []
        
        npcs = LocationNPCSerializer.get_npcs_at_location(
            "loc_forge", all_npcs, game_tick=100, player_story={}
        )
        
        assert npcs == []

    def test_get_npcs_at_location_single_npc(self):
        """Test getting NPCs at a location with one NPC."""
        all_npcs = [
            {
                "npc_id": "kael",
                "name": "Kael",
                "description": "The blacksmith",
                "availability_conditions": {
                    "story_gates": [],
                    "min_ticks_after_gate": 0,
                },
                "locations": [
                    {
                        "location_id": "loc_forge",
                        "available_after_story": "",
                    }
                ],
            }
        ]
        
        npcs = LocationNPCSerializer.get_npcs_at_location(
            "loc_forge", all_npcs, game_tick=100, player_story={}
        )
        
        assert len(npcs) == 1
        assert npcs[0]["npc_id"] == "kael"
        assert npcs[0]["available"] is True


class TestNPCTimelineSerializer:
    """Test NPC location progression timeline."""

    def test_get_timeline_entry(self):
        """Test creating a timeline entry for a location."""
        location = {
            "location_id": "loc_forge",
            "description": "Blacksmith's Forge",
            "available_after_story": "ch01_forge_unlocked",
            "available_after_ticks": 0,
            "priority": 1,
        }
        
        entry = NPCTimelineSerializer.get_timeline_entry(location)
        
        assert entry["location_id"] == "loc_forge"
        assert "ch01_forge_unlocked" in entry["trigger"]
        assert entry["priority"] == 1

    def test_serialize_timeline(self):
        """Test serializing full NPC timeline."""
        npc_data = {
            "npc_id": "kael",
            "name": "Kael",
            "locations": [
                {
                    "location_id": "loc_forge",
                    "description": "Forge",
                    "available_after_story": "ch01_forge_unlocked",
                    "available_after_ticks": 0,
                    "priority": 1,
                },
                {
                    "location_id": "loc_tavern",
                    "description": "Tavern",
                    "available_after_story": "ch02_meeting",
                    "available_after_ticks": 500,
                    "priority": 2,
                },
            ],
        }
        
        result = NPCTimelineSerializer.serialize(npc_data)
        
        assert result["npc_id"] == "kael"
        assert result["name"] == "Kael"
        assert len(result["timeline"]) == 2
        assert result["timeline"][0]["location_id"] == "loc_forge"


class TestNPCEventTriggerSerializer:
    """Test NPC event triggers and state changes."""

    def test_check_trigger_conditions_met(self):
        """Test checking trigger conditions when all are met."""
        trigger_data = {
            "required_story_gate": "ch01_complete",
            "required_min_ticks": 100,
        }
        
        result = NPCEventTriggerSerializer.check_trigger_conditions(
            trigger_data, game_tick=200, player_story={"ch01_complete": "1"}
        )
        
        assert result is True

    def test_check_trigger_conditions_story_gate_not_met(self):
        """Test checking trigger when story gate not met."""
        trigger_data = {
            "required_story_gate": "ch01_complete",
        }
        
        result = NPCEventTriggerSerializer.check_trigger_conditions(
            trigger_data, game_tick=100, player_story={}
        )
        
        assert result is False

    def test_check_trigger_conditions_ticks_not_met(self):
        """Test checking trigger when ticks not met."""
        trigger_data = {
            "required_min_ticks": 500,
        }
        
        result = NPCEventTriggerSerializer.check_trigger_conditions(
            trigger_data, game_tick=100, player_story={}
        )
        
        assert result is False

    def test_get_active_triggers(self):
        """Test getting active triggers for an NPC."""
        npc_data = {
            "npc_id": "kael",
            "triggers": [
                {
                    "trigger_id": "trigger_1",
                    "required_story_gate": "ch01_complete",
                    "required_min_ticks": 0,
                },
                {
                    "trigger_id": "trigger_2",
                    "required_story_gate": "ch02_complete",
                    "required_min_ticks": 0,
                },
            ],
        }
        
        # Only first trigger is active
        active = NPCEventTriggerSerializer.get_active_triggers(
            npc_data, game_tick=100, player_story={"ch01_complete": "1"}
        )
        
        assert len(active) == 1
        assert active[0]["trigger_id"] == "trigger_1"


class TestNPCStatusSerializer:
    """Test complete NPC status serialization."""

    def test_serialize_npc_status(self):
        """Test serializing complete NPC status."""
        npc_data = {
            "npc_id": "kael",
            "name": "Kael the Blacksmith",
            "description": "An expert blacksmith",
            "availability_conditions": {
                "story_gates": ["ch01_forge_unlocked"],
                "min_ticks_after_gate": 0,
            },
            "locations": [
                {
                    "location_id": "loc_forge",
                    "map_name": "village",
                    "coords": [10, 20],
                    "available_after_story": "ch01_forge_unlocked",
                    "description": "Forge",
                }
            ],
        }
        
        result = NPCStatusSerializer.serialize(
            npc_data, game_tick=100, player_story={"ch01_forge_unlocked": "1"}
        )
        
        assert result["npc_id"] == "kael"
        assert result["name"] == "Kael the Blacksmith"
        assert result["available"] is True
        assert result["current_location"]["location_id"] == "loc_forge"

    def test_serialize_npc_status_unavailable(self):
        """Test serializing NPC status when unavailable."""
        npc_data = {
            "npc_id": "kael",
            "name": "Kael",
            "description": "An NPC",
            "availability_conditions": {
                "story_gates": ["ch01_forge_unlocked"],
                "min_ticks_after_gate": 0,
            },
            "locations": [],
        }
        
        result = NPCStatusSerializer.serialize(
            npc_data, game_tick=100, player_story={}  # Gate not met
        )
        
        assert result["available"] is False
        assert "story_gate" in result["availability_reason"]
