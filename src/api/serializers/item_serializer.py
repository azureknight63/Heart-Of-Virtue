"""Item serialization for API responses."""

from typing import Dict, Any, List


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
            "aliases": getattr(item, "aliases", []),
            "action_aliases": getattr(item, "action_aliases", []),
            "value": getattr(item, "value", 0),
            "weight": getattr(item, "weight", 0.0),
            "count": 1,
        }

        # Add quantity for stackable items. Real Item objects (src/items.py)
        # always use `count`; `quantity` is never set, so that branch was
        # dead code.
        if hasattr(item, "count"):
            item_data["count"] = item.count

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

        # Add announce text for room display
        if hasattr(item, "announce"):
            item_data["announce"] = item.announce

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

        # Add 'equip' for equippable items (Equipment subclasses: Armor, Weapon, Accessory)
        # Guard on equip_states being non-empty — consumables never have equip_states
        equip_states = getattr(item, "equip_states", None)
        if hasattr(item, "isequipped") and equip_states and "equip" not in keywords:
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
