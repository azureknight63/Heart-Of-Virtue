"""
NPC Availability Serializers for Stage 4: Story-Gated NPC Location Tracking

Provides serialization and availability checking for NPCs based on:
- Story gates (required story switches)
- Tick thresholds (minimum game ticks required)
- Location tracking (where NPCs are available)
- Linear progression (NPCs move through locations as story progresses)
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum


class AvailabilityReason(Enum):
    """Reasons why an NPC is or isn't available."""

    STORY_GATE_NOT_MET = "story_gate_not_met"
    TICK_REQUIREMENT_NOT_MET = "tick_requirement_not_met"
    NOT_IN_WORLD = "not_in_world"
    AVAILABLE = "available"


class NPCLocationSerializer:
    """
    Serializes NPC location data.
    Handles: where NPCs are and what location they're currently at.

    Attributes:
        location_id (str): Unique identifier for the location
        map_name (str): Map/world this location exists in
        coords (Tuple[int, int]): (x, y) coordinates on the map
        description (str): Human-readable location description
    """

    @staticmethod
    def serialize(location_data: Dict) -> Dict:
        """Serialize a location to JSON-safe format."""
        return {
            "location_id": location_data.get("location_id"),
            "map_name": location_data.get("map_name"),
            "coords": location_data.get("coords", [0, 0]),
            "description": location_data.get("description", "Unknown location"),
        }

    @staticmethod
    def deserialize(location_dict: Dict) -> Dict:
        """Deserialize location from JSON format."""
        return {
            "location_id": location_dict.get("location_id"),
            "map_name": location_dict.get("map_name"),
            "coords": tuple(location_dict.get("coords", [0, 0])),
            "description": location_dict.get("description", "Unknown location"),
        }

    @staticmethod
    def get_location(
        npc_data: Dict, game_tick: int, player_story: Dict
    ) -> Optional[Dict]:
        """
        Get the current active location for an NPC based on availability conditions.

        Returns the first location where ALL conditions are met:
        - Story gate is satisfied
        - Tick threshold is satisfied

        Args:
            npc_data: NPC definition with locations list
            game_tick: Current game tick
            player_story: Player's story switches dict

        Returns:
            Dict with location details, or None if no location available
        """
        locations = npc_data.get("locations", [])

        for location in locations:
            # Check story gate requirement
            story_gate = location.get("available_after_story")
            if story_gate and not player_story.get(story_gate, "0") == "1":
                continue

            # Check tick requirement (relative to gate completion if gate exists)
            min_ticks = location.get("available_after_ticks", 0)
            if game_tick < min_ticks:
                continue

            # All conditions met for this location
            return NPCLocationSerializer.deserialize(location)

        return None

    @staticmethod
    def is_at_location(
        npc_id: str,
        location_id: str,
        npc_data: Dict,
        game_tick: int,
        player_story: Dict,
    ) -> bool:
        """Check if an NPC is at a specific location right now."""
        current_location = NPCLocationSerializer.get_location(
            npc_data, game_tick, player_story
        )

        if current_location is None:
            return False

        return current_location["location_id"] == location_id


class NPCAvailabilitySerializer:
    """
    Serializes NPC availability checking.
    Handles: can the player interact with this NPC right now?

    Checks story gates and tick requirements to determine availability.
    """

    @staticmethod
    def check_story_gates(
        npc_data: Dict, player_story: Dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if all story gate requirements are met.

        Returns:
            (is_met, missing_gate_name)
        """
        required_gates = npc_data.get("availability_conditions", {}).get(
            "story_gates", []
        )

        for gate in required_gates:
            if not player_story.get(gate, "0") == "1":
                return False, gate

        return True, None

    @staticmethod
    def check_tick_requirements(
        npc_data: Dict, game_tick: int, gate_completion_tick: int = 0
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if tick requirements are met.

        Args:
            npc_data: NPC definition
            game_tick: Current game tick
            gate_completion_tick: Game tick when story gate was completed (optional)

        Returns:
            (is_met, ticks_until_available)
        """
        min_ticks_after_gate = npc_data.get("availability_conditions", {}).get(
            "min_ticks_after_gate", 0
        )
        required_total_ticks = gate_completion_tick + min_ticks_after_gate

        if game_tick < required_total_ticks:
            return False, required_total_ticks - game_tick

        return True, None

    @staticmethod
    def is_available(
        npc_data: Dict,
        game_tick: int,
        player_story: Dict,
        gate_completion_tick: int = 0,
    ) -> Tuple[bool, AvailabilityReason]:
        """
        Check if NPC is available to interact with.

        Returns:
            (is_available, reason)
        """
        # Check story gates
        gates_met, missing_gate = NPCAvailabilitySerializer.check_story_gates(
            npc_data, player_story
        )
        if not gates_met:
            return False, AvailabilityReason.STORY_GATE_NOT_MET

        # Check tick requirements
        ticks_met, _ = NPCAvailabilitySerializer.check_tick_requirements(
            npc_data, game_tick, gate_completion_tick
        )
        if not ticks_met:
            return False, AvailabilityReason.TICK_REQUIREMENT_NOT_MET

        # Check if NPC has a location available
        locations = npc_data.get("locations", [])
        if not locations:
            return False, AvailabilityReason.NOT_IN_WORLD

        # Verify at least one location meets conditions
        current_location = NPCLocationSerializer.get_location(
            npc_data, game_tick, player_story
        )
        if current_location is None:
            return False, AvailabilityReason.NOT_IN_WORLD

        return True, AvailabilityReason.AVAILABLE

    @staticmethod
    def serialize(
        npc_data: Dict,
        game_tick: int,
        player_story: Dict,
        gate_completion_tick: int = 0,
    ) -> Dict:
        """
        Serialize full availability status.

        Returns dict with all availability information.
        """
        is_available, reason = NPCAvailabilitySerializer.is_available(
            npc_data, game_tick, player_story, gate_completion_tick
        )

        current_location = NPCLocationSerializer.get_location(
            npc_data, game_tick, player_story
        )
        gates_met, missing_gate = NPCAvailabilitySerializer.check_story_gates(
            npc_data, player_story
        )
        ticks_met, ticks_until = NPCAvailabilitySerializer.check_tick_requirements(
            npc_data, game_tick, gate_completion_tick
        )

        location_data = None
        if current_location:
            location_data = NPCLocationSerializer.serialize(current_location)

        return {
            "available": is_available,
            "reason": reason.value,
            "story_gates_met": gates_met,
            "missing_gate": missing_gate,
            "tick_requirements_met": ticks_met,
            "ticks_until_available": ticks_until,
            "in_world": current_location is not None,
            "current_location": location_data,
        }


class LocationNPCSerializer:
    """
    Serializes NPC data for a specific location.
    Handles: which NPCs are at a given location right now?
    """

    @staticmethod
    def get_npcs_at_location(
        location_id: str,
        all_npcs: List[Dict],
        game_tick: int,
        player_story: Dict,
    ) -> List[Dict]:
        """
        Get all NPCs currently at a specific location.

        Args:
            location_id: Location to check
            all_npcs: List of all NPC definitions
            game_tick: Current game tick
            player_story: Player's story switches

        Returns:
            List of NPCs currently at that location
        """
        npcs_here = []

        for npc_data in all_npcs:
            if NPCLocationSerializer.is_at_location(
                npc_data.get("npc_id"),
                location_id,
                npc_data,
                game_tick,
                player_story,
            ):
                npc_info = {
                    "npc_id": npc_data.get("npc_id"),
                    "name": npc_data.get("name"),
                    "description": npc_data.get("description", "An NPC"),
                    "available": True,
                }
                npcs_here.append(npc_info)

        return npcs_here

    @staticmethod
    def serialize(
        location_id: str,
        location_name: str,
        all_npcs: List[Dict],
        game_tick: int,
        player_story: Dict,
    ) -> Dict:
        """
        Serialize all NPC data for a location.
        """
        npcs = LocationNPCSerializer.get_npcs_at_location(
            location_id, all_npcs, game_tick, player_story
        )

        return {
            "location_id": location_id,
            "location_name": location_name,
            "npcs": npcs,
            "npc_count": len(npcs),
        }


class NPCTimelineSerializer:
    """
    Serializes NPC location progression over story timeline.
    Handles: where does this NPC go as the story progresses?
    """

    @staticmethod
    def get_timeline_entry(location: Dict) -> Dict:
        """
        Create a timeline entry for a location.

        Shows when and why this location becomes available.
        """
        story_gate = location.get("available_after_story", "game_start")
        tick_requirement = location.get("available_after_ticks", 0)

        # Create human-readable trigger description
        if story_gate == "game_start":
            trigger_desc = f"Game start"
        else:
            trigger_desc = f"Story gate: {story_gate}"

        if tick_requirement > 0:
            trigger_desc += f" + {tick_requirement} ticks"

        return {
            "location_id": location.get("location_id"),
            "location_name": location.get("description", "Unknown location"),
            "trigger": trigger_desc,
            "story_gate": story_gate,
            "tick_requirement": tick_requirement,
            "priority": location.get("priority", 999),
        }

    @staticmethod
    def serialize(npc_data: Dict) -> Dict:
        """
        Serialize NPC's full timeline.

        Shows progression through all locations as story advances.
        """
        locations = npc_data.get("locations", [])
        timeline_entries = [
            NPCTimelineSerializer.get_timeline_entry(loc)
            for loc in sorted(locations, key=lambda x: x.get("priority", 999))
        ]

        return {
            "npc_id": npc_data.get("npc_id"),
            "name": npc_data.get("name"),
            "timeline": timeline_entries,
        }


class NPCEventTriggerSerializer:
    """
    Serializes NPC state change triggers.
    Handles: what causes NPCs to move or become available?
    """

    @staticmethod
    def check_trigger_conditions(
        trigger_data: Dict, game_tick: int, player_story: Dict
    ) -> bool:
        """
        Check if a trigger's conditions are met.

        Supports: story_gate and min_ticks conditions.
        """
        required_story_gate = trigger_data.get("required_story_gate")
        if required_story_gate:
            if not player_story.get(required_story_gate, "0") == "1":
                return False

        required_ticks = trigger_data.get("required_min_ticks", 0)
        if game_tick < required_ticks:
            return False

        return True

    @staticmethod
    def get_active_triggers(
        npc_data: Dict, game_tick: int, player_story: Dict
    ) -> List[Dict]:
        """
        Get all currently active triggers for an NPC.

        Active = all conditions are met.
        """
        triggers = npc_data.get("triggers", [])
        active = []

        for trigger in triggers:
            if NPCEventTriggerSerializer.check_trigger_conditions(
                trigger, game_tick, player_story
            ):
                active.append(trigger)

        return active

    @staticmethod
    def serialize(npc_data: Dict, game_tick: int, player_story: Dict) -> Dict:
        """
        Serialize trigger status for an NPC.
        """
        active_triggers = NPCEventTriggerSerializer.get_active_triggers(
            npc_data, game_tick, player_story
        )

        return {
            "npc_id": npc_data.get("npc_id"),
            "active_triggers": len(active_triggers),
            "triggers": active_triggers,
        }


class NPCStatusSerializer:
    """
    Main serializer: combines all NPC availability info into one response.
    """

    @staticmethod
    def serialize(
        npc_data: Dict,
        game_tick: int,
        player_story: Dict,
        gate_completion_ticks: Optional[Dict] = None,
    ) -> Dict:
        """
        Serialize complete NPC status.

        Args:
            npc_data: NPC definition
            game_tick: Current game tick
            player_story: Player's story switches
            gate_completion_ticks: Map of story_gate -> completion_tick (optional)
        """
        if gate_completion_ticks is None:
            gate_completion_ticks = {}

        npc_id = npc_data.get("npc_id")

        # Get gate completion tick for this NPC's primary gate
        gates = npc_data.get("availability_conditions", {}).get("story_gates", [])
        primary_gate = gates[0] if gates else None
        gate_completion_tick = gate_completion_ticks.get(primary_gate, 0)

        # Serialize availability
        availability = NPCAvailabilitySerializer.serialize(
            npc_data, game_tick, player_story, gate_completion_tick
        )

        # Get current location
        current_location = NPCLocationSerializer.get_location(
            npc_data, game_tick, player_story
        )

        return {
            "npc_id": npc_id,
            "name": npc_data.get("name"),
            "description": npc_data.get("description", "An NPC"),
            "available": availability["available"],
            "availability_reason": availability["reason"],
            "current_location": current_location,
            "story_gates_met": availability["story_gates_met"],
            "tick_requirements_met": availability["tick_requirements_met"],
            "in_world": availability["in_world"],
        }
