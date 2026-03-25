"""Serializers for world navigation data."""

from typing import Any, Dict, List


from src.api.serializers.item_serializer import ItemSerializer
from src.api.serializers.npc_serializer import NPCSerializer
from src.api.serializers.object_serializer import ObjectSerializer


class EventSerializer:
    """Serializes event objects for API responses."""

    @staticmethod
    def serialize(event: Any) -> Dict[str, Any]:
        """Serialize a single event.

        Args:
            event: The event object to serialize

        Returns:
            Dictionary with event data
        """
        if not event:
            return {}

        result = {
            "id": str(id(event)),
            "type": type(event).__name__,
            "description": getattr(event, "description", ""),
        }

        # Add repeat status if available
        if hasattr(event, "repeat"):
            result["repeat"] = event.repeat

        # Add triggers if available
        if hasattr(event, "triggers"):
            result["triggers"] = event.triggers

        return result

    @staticmethod
    def serialize_many(events: List[Any]) -> List[Dict[str, Any]]:
        """Serialize multiple events.

        Args:
            events: List of event objects

        Returns:
            List of serialized event dictionaries
        """
        return [EventSerializer.serialize(event) for event in events]


class TileSerializer:
    """Serializes tile objects for API responses."""

    @staticmethod
    def serialize(tile: Any) -> Dict[str, Any]:
        """Serialize a tile with all its contents.

        Args:
            tile: The tile object to serialize

        Returns:
            Dictionary with tile data including items, NPCs, objects, and exits
        """
        if not tile:
            return {}

        # Basic tile info
        result = {
            "x": getattr(tile, "x", 0),
            "y": getattr(tile, "y", 0),
            "name": getattr(tile, "name", "Unknown"),
            "description": getattr(tile, "description", ""),
            "is_passable": getattr(tile, "is_passable", True),
        }

        # Serialize items
        items = getattr(tile, "items_here", [])
        result["items"] = ItemSerializer.serialize_list(items)

        # Serialize NPCs
        npcs = getattr(tile, "npcs_here", [])
        result["npcs"] = NPCSerializer.serialize_list(npcs)

        # Serialize objects
        objects = getattr(tile, "objects_here", [])
        result["objects"] = ObjectSerializer.serialize_list(objects)

        # Serialize events
        events = getattr(tile, "events_here", [])
        result["events"] = EventSerializer.serialize_list(events)

        # Serialize exits/connections
        exits = {}
        if hasattr(tile, "exits"):
            for direction, (ex, ey) in tile.exits.items():
                exits[direction] = {"x": ex, "y": ey}
        result["exits"] = exits

        return result

    @staticmethod
    def serialize_many(tiles: List[Any]) -> List[Dict[str, Any]]:
        """Serialize multiple tiles.

        Args:
            tiles: List of tile objects

        Returns:
            List of serialized tile dictionaries
        """
        return [TileSerializer.serialize(tile) for tile in tiles]


class WorldSerializer:
    """Serializes complete world state for API responses."""

    @staticmethod
    def serialize_current_room(player: Any, tile: Any) -> Dict[str, Any]:
        """Serialize current room information for a player.

        Args:
            player: The player object
            tile: The current tile

        Returns:
            Dictionary with room data and player position
        """
        if not tile:
            return {
                "error": "Tile not found",
                "x": getattr(player, "location_x", 0),
                "y": getattr(player, "location_y", 0),
            }

        return {
            "x": getattr(player, "location_x", 0),
            "y": getattr(player, "location_y", 0),
            "tile": TileSerializer.serialize(tile),
        }

    @staticmethod
    def serialize_movement_result(
        player: Any,
        old_position: tuple,
        new_tile: Any,
        events_triggered: List[Dict],
    ) -> Dict[str, Any]:
        """Serialize the result of a movement action.

        Args:
            player: The player object
            old_position: Tuple of (old_x, old_y)
            new_tile: The destination tile
            events_triggered: List of triggered event data

        Returns:
            Dictionary with movement result including new room and events
        """
        return {
            "old_position": {"x": old_position[0], "y": old_position[1]},
            "new_position": {
                "x": getattr(player, "location_x", 0),
                "y": getattr(player, "location_y", 0),
            },
            "room": TileSerializer.serialize(new_tile),
            "events_triggered": events_triggered,
        }

    @staticmethod
    def serialize_exploration_context(
        player: Any, current_tile: Any, nearby_tiles: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Serialize exploration context with current tile and nearby areas.

        Args:
            player: The player object
            current_tile: The current tile
            nearby_tiles: Dictionary of nearby tiles keyed by direction

        Returns:
            Dictionary with exploration context
        """
        return {
            "player_position": {
                "x": getattr(player, "location_x", 0),
                "y": getattr(player, "location_y", 0),
            },
            "current_room": TileSerializer.serialize(current_tile),
            "adjacent_rooms": {
                direction: TileSerializer.serialize(tile)
                for direction, tile in nearby_tiles.items()
                if tile is not None
            },
        }
