"""Item serialization for API responses."""

from typing import Dict, Any, List, Optional


class ItemSerializer:
    """Serialize Item objects to JSON-safe dictionaries."""

    @staticmethod
    def serialize(item: Any) -> Dict[str, Any]:
        """Serialize a single item.
        
        Args:
            item: Item object to serialize
            
        Returns:
            Dictionary with item data
        """
        if not item:
            return {}

        # Basic item properties
        item_data = {
            "id": str(id(item)),
            "name": getattr(item, "name", "Unknown"),
            "type": type(item).__name__,
            "description": getattr(item, "description", ""),
            "value": getattr(item, "value", 0),
            "weight": getattr(item, "weight", 0.0),
        }

        # Add quantity for stackable items
        if hasattr(item, "quantity"):
            item_data["quantity"] = item.quantity
        
        # Add subtype for categorization
        if hasattr(item, "subtype"):
            item_data["subtype"] = item.subtype

        # Add equipment info if applicable
        if hasattr(item, "equip_states") and item.equip_states:
            item_data["equip_states"] = item.equip_states

        # Add status effects if present
        if hasattr(item, "add_status_resistance"):
            resistances = item.add_status_resistance
            if resistances:
                item_data["status_resistances"] = resistances

        # Add damage resistance modifiers
        if hasattr(item, "add_resistance"):
            resistances = item.add_resistance
            if resistances:
                item_data["resistances"] = resistances

        # Add power/damage rating if applicable
        if hasattr(item, "power"):
            item_data["power"] = item.power

        # Add hidden/discovery info
        if hasattr(item, "hidden"):
            item_data["hidden"] = item.hidden
        if hasattr(item, "hide_factor"):
            item_data["hide_factor"] = item.hide_factor

        # Add merchandise flag
        if hasattr(item, "merchandise"):
            item_data["merchandise"] = item.merchandise

        # Add keywords for interaction
        # For items in the world, we want 'take' and potentially 'equip' for equippable items
        keywords = []
        if hasattr(item, "keywords"):
            keywords = list(item.keywords)
        elif hasattr(item, "interactions"):
            keywords = list(item.interactions)
        
        # Filter out inventory-only interactions (drop, unequip)
        # Keep 'equip' if the item is equippable
        inventory_only_actions = ["drop", "unequip"]
        keywords = [k for k in keywords if k not in inventory_only_actions]
        
        # Ensure 'take' is available for items
        if "take" not in keywords:
            keywords.append("take")
        
        # Add 'equip' for equippable items if not already present
        if hasattr(item, "isequipped") and "equip" not in keywords:
            keywords.append("equip")
            
        item_data["keywords"] = keywords

        return item_data

    @staticmethod
    def serialize_list(items: List[Any]) -> List[Dict[str, Any]]:
        """Serialize multiple items.
        
        Args:
            items: List of Item objects
            
        Returns:
            List of serialized item dictionaries
        """
        if not items:
            return []
        
        return [ItemSerializer.serialize(item) for item in items]

    @staticmethod
    def serialize_with_effects(item: Any) -> Dict[str, Any]:
        """Serialize item with full effect details.
        
        Args:
            item: Item object to serialize
            
        Returns:
            Dictionary with detailed item and effect data
        """
        item_data = ItemSerializer.serialize(item)
        
        # Add effect descriptions if available
        if hasattr(item, "skills") and item.skills:
            item_data["skills"] = item.skills
        
        if hasattr(item, "effects") and item.effects:
            item_data["effects"] = item.effects
        
        # Add discovery/announcement text
        if hasattr(item, "discovery_message"):
            item_data["discovery_message"] = item.discovery_message
        
        if hasattr(item, "announce"):
            item_data["announce"] = item.announce
        
        return item_data

    @staticmethod
    def serialize_inventory(items: List[Any], include_effects: bool = False) -> Dict[str, Any]:
        """Serialize player inventory.
        
        Args:
            items: List of items in inventory
            include_effects: Whether to include full effect details
            
        Returns:
            Dictionary with inventory data
        """
        serializer = ItemSerializer.serialize_with_effects if include_effects else ItemSerializer.serialize
        
        return {
            "items": [serializer(item) for item in items],
            "count": len(items),
            "total_weight": sum(getattr(item, "weight", 0.0) for item in items),
        }

    @staticmethod
    def serialize_container(items: List[Any]) -> Dict[str, Any]:
        """Serialize items in a container (chest, shop, etc).
        
        Args:
            items: List of items in container
            
        Returns:
            Dictionary with container items
        """
        return {
            "items": ItemSerializer.serialize_list(items),
            "count": len(items),
        }
