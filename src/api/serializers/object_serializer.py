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

        is_dict = isinstance(obj, dict)

        def get_attr(attr_name: str, default: Any = None) -> Any:
            if is_dict:
                return obj.get(attr_name, default)
            return getattr(obj, attr_name, default)

        def has_attr(attr_name: str) -> bool:
            if is_dict:
                return attr_name in obj
            return hasattr(obj, attr_name)

        # Default object id
        obj_id = get_attr("id", id(obj))

        obj_data = {
            "id": str(obj_id),
            "name": get_attr("name", "Unknown"),
            "type": get_attr("type", "dict" if is_dict else type(obj).__name__),
            "description": get_attr("description", ""),
            "aliases": get_attr("aliases", []),
            "action_aliases": get_attr("action_aliases", []),
        }

        # Passability and state
        if has_attr("is_passable"):
            obj_data["is_passable"] = get_attr("is_passable")

        # Hidden/discovery info
        if has_attr("hidden"):
            obj_data["hidden"] = get_attr("hidden")
        if has_attr("hide_factor"):
            obj_data["hide_factor"] = get_attr("hide_factor")

        # Interaction keywords
        if has_attr("keywords"):
            obj_data["keywords"] = get_attr("keywords")

        # Specific object states
        if has_attr("locked"):
            obj_data["locked"] = get_attr("locked")

        # Handle state/opened flag consistently
        if has_attr("state"):
            obj_state = get_attr("state")
            obj_data["state"] = obj_state
            obj_data["opened"] = obj_state == "opened"
        elif has_attr("opened"):
            obj_data["opened"] = get_attr("opened")

        # Ensure keywords are consistent with dynamic state
        if "keywords" in obj_data and isinstance(obj_data["keywords"], list):
            has_locked = has_attr("locked")
            has_opened_attr = has_attr("opened") or has_attr("state")

            if has_locked or has_opened_attr:
                current_k = obj_data["keywords"]
                is_locked = obj_data.get("locked", False)
                is_opened = obj_data.get("opened", False)

                # Filter out state-dependent keywords to avoid duplicates or inconsistencies
                new_k = [k for k in current_k if k not in ("open", "unlock")]

                if is_locked:
                    # If locked, only show unlock
                    if "unlock" not in new_k:
                        new_k.append("unlock")
                elif not is_opened:
                    # If closed and unlocked, show open
                    if "open" not in new_k:
                        new_k.append("open")

                obj_data["keywords"] = new_k

        if has_attr("open_message"):
            obj_data["open_message"] = get_attr("open_message")
        if has_attr("idle_message"):
            obj_data["idle_message"] = get_attr("idle_message")

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
        from src.objects import Container

        if isinstance(obj, Container):
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

