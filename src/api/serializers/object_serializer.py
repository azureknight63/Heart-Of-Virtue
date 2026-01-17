"""World object serialization for API responses."""

from typing import Dict, Any, List
from src.api.serializers.item_serializer import ItemSerializer


class ObjectSerializer:
    """Serialize world objects to JSON-safe dictionaries."""

    @staticmethod
    def _serialize_base(obj: Any) -> Dict[str, Any]:
        """Internal method for basic object serialization to avoid recursion."""
        if not obj:
            return {}

        obj_data = {
            "id": str(id(obj)),
            "name": getattr(obj, "name", "Unknown"),
            "type": type(obj).__name__,
            "description": getattr(obj, "description", ""),
            "aliases": getattr(obj, "aliases", []),
            "action_aliases": getattr(obj, "action_aliases", []),
        }

        # Passability and state
        if hasattr(obj, "is_passable"):
            obj_data["is_passable"] = obj.is_passable
        
        # Hidden/discovery info
        if hasattr(obj, "hidden"):
            obj_data["hidden"] = obj.hidden
        if hasattr(obj, "hide_factor"):
            obj_data["hide_factor"] = obj.hide_factor

        # Interaction keywords
        if hasattr(obj, "keywords"):
            obj_data["keywords"] = obj.keywords

        # Specific object states
        if hasattr(obj, "locked"):
            obj_data["locked"] = obj.locked

        # Handle container state correctly
        if hasattr(obj, "state"):
            obj_data["state"] = obj.state
            obj_data["opened"] = (obj.state == "opened")
        elif hasattr(obj, "opened"):
            obj_data["opened"] = obj.opened
            
        if hasattr(obj, "open_message"):
            obj_data["open_message"] = obj.open_message
        if hasattr(obj, "idle_message"):
            obj_data["idle_message"] = obj.idle_message

        return obj_data

    @staticmethod
    def serialize(obj: Any) -> Dict[str, Any]:
        """Serialize a single world object.
        
        Args:
            obj: World object to serialize (Container, Chest, Door, Shrine, etc.)
            
        Returns:
            Dictionary with object data
        """
        if not obj:
            return {}

        # Check if it's a container and use container serialization if so
        try:
            from objects import Container
        except ImportError:
            from src.objects import Container
        
        if isinstance(obj, Container) or type(obj).__name__ == "Container":
            return ObjectSerializer.serialize_container(obj)

        return ObjectSerializer._serialize_base(obj)

    @staticmethod
    def serialize_list(objects: List[Any]) -> List[Dict[str, Any]]:
        """Serialize multiple world objects.
        
        Args:
            objects: List of world objects
            
        Returns:
            List of serialized object dictionaries
        """
        if not objects:
            return []
        
        return [ObjectSerializer.serialize(obj) for obj in objects]

    @staticmethod
    def serialize_container(obj: Any) -> Dict[str, Any]:
        """Serialize a container object with its contents.
        
        Args:
            obj: Container object (Chest, Container, etc.)
            
        Returns:
            Dictionary with container data and items
        """
        obj_data = ObjectSerializer._serialize_base(obj)

        # Container-specific info
        obj_data["is_container"] = True

        # Serialize contents
        if hasattr(obj, "inventory") and obj.inventory:
            obj_data["contents"] = ItemSerializer.serialize_list(obj.inventory)
            obj_data["item_count"] = len(obj.inventory)
        elif hasattr(obj, "contents") and obj.contents:
            obj_data["contents"] = ItemSerializer.serialize_list(obj.contents)
            obj_data["item_count"] = len(obj.contents)
        elif hasattr(obj, "items_here") and obj.items_here:
            obj_data["contents"] = ItemSerializer.serialize_list(obj.items_here)
            obj_data["item_count"] = len(obj.items_here)
        else:
            obj_data["contents"] = []
            obj_data["item_count"] = 0

        # Container capacity if applicable
        if hasattr(obj, "capacity"):
            obj_data["capacity"] = obj.capacity

        return obj_data

    @staticmethod
    def serialize_interactive(obj: Any) -> Dict[str, Any]:
        """Serialize interactive object with event/consequence data.
        
        Args:
            obj: Interactive object to serialize
            
        Returns:
            Dictionary with interaction data
        """
        obj_data = ObjectSerializer.serialize(obj)

        # Event information
        if hasattr(obj, "events") and obj.events:
            obj_data["events"] = len(obj.events)
            obj_data["has_events"] = True
        else:
            obj_data["has_events"] = False

        # Interaction consequences
        if hasattr(obj, "consequence_text"):
            obj_data["consequence"] = obj.consequence_text
        if hasattr(obj, "use_message"):
            obj_data["use_message"] = obj.use_message
        if hasattr(obj, "examine_message"):
            obj_data["examine_message"] = obj.examine_message

        # One-time or repeatable
        if hasattr(obj, "one_time_only"):
            obj_data["one_time_only"] = obj.one_time_only

        return obj_data

    @staticmethod
    def serialize_door(obj: Any) -> Dict[str, Any]:
        """Serialize door object with state and connection info.
        
        Args:
            obj: Door object to serialize
            
        Returns:
            Dictionary with door data
        """
        obj_data = ObjectSerializer.serialize(obj)

        obj_data["is_door"] = True

        # Door state
        if hasattr(obj, "opened"):
            obj_data["opened"] = obj.opened
        if hasattr(obj, "locked"):
            obj_data["locked"] = obj.locked

        # Door messages
        if hasattr(obj, "open_message"):
            obj_data["open_message"] = obj.open_message
        if hasattr(obj, "locked_message"):
            obj_data["locked_message"] = obj.locked_message

        # Connection target (if applicable)
        if hasattr(obj, "leads_to"):
            obj_data["leads_to"] = obj.leads_to

        return obj_data

    @staticmethod
    def serialize_shrine(obj: Any) -> Dict[str, Any]:
        """Serialize shrine object with blessing/interaction info.
        
        Args:
            obj: Shrine object to serialize
            
        Returns:
            Dictionary with shrine data
        """
        obj_data = ObjectSerializer.serialize(obj)

        obj_data["is_shrine"] = True

        # Shrine blessings/effects
        if hasattr(obj, "blessing_text"):
            obj_data["blessing"] = obj.blessing_text
        if hasattr(obj, "blessing_effect"):
            obj_data["blessing_effect"] = obj.blessing_effect

        # Shrine cooldown
        if hasattr(obj, "last_blessed_at"):
            obj_data["last_blessed_at"] = obj.last_blessed_at

        return obj_data
