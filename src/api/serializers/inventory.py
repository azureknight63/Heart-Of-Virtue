"""
Inventory and equipment serializers for the Flask API.

Converts game objects (items, inventory, equipment) to JSON-safe dictionaries
for API responses. Reuses patterns from world.py serializers.

Classes:
    InventoryItemSerializer: Single item in inventory
    InventorySerializer: Full player inventory
    EquipmentSlotSerializer: Single equipped item slot
    EquipmentSerializer: All equipped items with bonuses
    ItemComparisonSerializer: Compare two items for decision-making
"""

from typing import Dict, List, Optional


class InventoryItemSerializer:
    """Serialize a single item in player inventory."""

    @staticmethod
    def serialize(item, index: int) -> Dict:
        """
        Serialize an item for inventory listing.

        Args:
            item: The item object to serialize
            index: The position in inventory

        Returns:
            Dictionary with item data suitable for JSON
        """
        # Determine item category
        item_type = item.__class__.__name__
        maintype = getattr(item, "maintype", "")
        
        # Build base item data
        item_data = {
            "id": str(id(item)),  # Unique identifier for this item object
            "index": index,
            "name": getattr(item, "name", "Unknown Item"),
            "type": item_type,
            "maintype": maintype,
            "subtype": getattr(item, "subtype", ""),
            "quantity": getattr(item, "quantity", 1),
            "rarity": getattr(item, "rarity", "common"),
            "weight": getattr(item, "weight", 0.0),
            "value": getattr(item, "value", 0),
            "can_equip": hasattr(item, "equip"),
            "can_use": "use" in getattr(item, "interactions", []),
            "can_drop": "drop" in getattr(item, "interactions", []),
            "is_equipped": getattr(item, "isequipped", False),
            "is_merchandise": getattr(item, "merchandise", False),
            "description": getattr(item, "description", ""),
        }
        
        # Add weapon-specific stats
        if item_type == "Weapon" or maintype == "Weapon":
            item_data["damage"] = getattr(item, "damage", 0)
            item_data["str_mod"] = getattr(item, "str_mod", 0)
            item_data["fin_mod"] = getattr(item, "fin_mod", 0)
        
        # Add armor-specific stats (Armor, Boots, Helm, Gloves, Accessory)
        if item_type in ["Armor", "Boots", "Helm", "Gloves", "Accessory"] or \
           maintype in ["Armor", "Boots", "Helm", "Gloves", "Accessory"]:
            item_data["protection"] = getattr(item, "protection", 0)
        
        return item_data


class InventorySerializer:
    """Serialize player's complete inventory."""

    @staticmethod
    def serialize(player) -> Dict:
        """
        Serialize full player inventory.

        Args:
            player: The Player object

        Returns:
            Dictionary with inventory info and all items
        """
        items = []
        total_weight = 0.0

        # Handle both inventory_list (real Player) and inventory (MinimalPlayer)
        inventory_list = getattr(player, "inventory_list", None) or getattr(player, "inventory", [])
        for idx, item in enumerate(inventory_list):
            items.append(InventoryItemSerializer.serialize(item, idx))
            total_weight += getattr(item, "weight", 0.0)

        return {
            "total_weight": round(total_weight, 2),
            "weight_limit": getattr(player, "carrying_capacity", 100.0),
            "weight_percentage": round(
                (total_weight / getattr(player, "carrying_capacity", 100.0)) * 100, 1
            ),
            "item_count": len(items),
            "slots_used": len([i for i in items if i]),
            "slots_total": getattr(player, "inventory_slots", 20),
            "items": items,
        }


class EquipmentSlotSerializer:
    """Serialize a single equipment slot."""

    @staticmethod
    def serialize(slot_name: str, item) -> Dict:
        """
        Serialize a single equipment slot.

        Args:
            slot_name: Name of the slot (e.g., 'head', 'chest')
            item: The item equipped in this slot (or None)

        Returns:
            Dictionary with slot information
        """
        if not item:
            return {
                "slot": slot_name,
                "equipped": False,
                "item_name": None,
                "armor": 0,
                "damage": 0,
                "stat_bonuses": {},
                "resistance_bonuses": {},
            }

        return {
            "slot": slot_name,
            "equipped": True,
            "item_name": getattr(item, "name", "Unknown"),
            "item_type": item.__class__.__name__,
            "armor": getattr(item, "armor", 0),
            "damage": getattr(item, "damage", 0),
            "weight": getattr(item, "weight", 0.0),
            "value": getattr(item, "value", 0),
            "stat_bonuses": getattr(item, "stat_bonuses", {}),
            "resistance_bonuses": getattr(item, "resistance_bonuses", {}),
            "rarity": getattr(item, "rarity", "common"),
        }


class EquipmentSerializer:
    """Serialize player's complete equipment state."""

    @staticmethod
    def serialize(player) -> Dict:
        """
        Serialize full equipment with bonuses.

        Args:
            player: The Player object

        Returns:
            Dictionary with all equipment slots and calculated bonuses
        """
        equipped = {}
        total_bonuses = {
            "attack": 0,
            "defense": 0,
            "magic_attack": 0,
            "magic_defense": 0,
            "speed": 0,
            "accuracy": 0,
            "evasion": 0,
            "crit_chance": 0,
        }

        # Get equipped items from player (handle both equipped and equipment attributes)
        equipment_dict = getattr(player, "equipped", None) or getattr(player, "equipment", {})
        if equipment_dict:
            for slot_name, item in equipment_dict.items():
                equipped[slot_name] = EquipmentSlotSerializer.serialize(slot_name, item)

                # Accumulate bonuses
                if item and hasattr(item, "stat_bonuses"):
                    for stat, bonus in item.stat_bonuses.items():
                        if stat in total_bonuses:
                            total_bonuses[stat] += bonus

        # Count unequipped equippable items (handle both inventory_list and inventory)
        unequipped_equippable = 0
        inventory_list = getattr(player, "inventory_list", None) or getattr(player, "inventory", [])
        for item in inventory_list:
            if hasattr(item, "equip") and not getattr(item, "equipped_state", False):
                unequipped_equippable += 1

        # Calculate equipment value
        equipment_value = 0
        for item in equipment_dict.values() if equipment_dict else []:
            if item:
                equipment_value += getattr(item, "value", 0)

        return {
            "equipped": equipped,
            "unequipped_equippable_count": unequipped_equippable,
            "total_stat_bonuses": total_bonuses,
            "equipment_value": equipment_value,
        }


class ItemDetailSerializer:
    """Serialize full details of a single item."""

    @staticmethod
    def serialize(item, equipped: bool = False, inventory_index: Optional[int] = None) -> Dict:
        """
        Serialize complete item details.

        Args:
            item: The item to serialize
            equipped: Whether the item is currently equipped
            inventory_index: Index in inventory if applicable

        Returns:
            Dictionary with full item information
        """
        return {
            "name": getattr(item, "name", "Unknown Item"),
            "type": item.__class__.__name__,
            "description": getattr(item, "description", ""),
            "quantity": getattr(item, "quantity", 1),
            "rarity": getattr(item, "rarity", "common"),
            "weight": getattr(item, "weight", 0.0),
            "value": getattr(item, "value", 0),
            "equipped": equipped,
            "inventory_index": inventory_index,
            "can_equip": hasattr(item, "equip"),
            "can_use": hasattr(item, "use"),
            "can_drop": True,  # Most items can be dropped
            "stats": {
                "armor": getattr(item, "armor", 0),
                "damage": getattr(item, "damage", 0),
                "magic_attack": getattr(item, "magic_attack", 0),
                "magic_defense": getattr(item, "magic_defense", 0),
                "accuracy": getattr(item, "accuracy", 0),
                "evasion": getattr(item, "evasion", 0),
            },
            "bonuses": {
                "stat_bonuses": getattr(item, "stat_bonuses", {}),
                "resistance_bonuses": getattr(item, "resistance_bonuses", {}),
            },
            "flags": {
                "merchandise": getattr(item, "merchandise", False),
                "hidden": getattr(item, "hidden", False),
                "special": isinstance(item, type) and item.__class__.__name__ == "Special",
            },
        }


class ItemComparisonSerializer:
    """Compare two items (e.g., for equip decision)."""

    @staticmethod
    def serialize(current_item: Optional[object], candidate_item: object) -> Dict:
        """
        Compare two items side-by-side.

        Args:
            current_item: Currently equipped item (or None)
            candidate_item: Item being considered for equip

        Returns:
            Dictionary showing comparison and recommendation
        """
        if not current_item:
            return {
                "comparison_type": "empty_to_item",
                "current": None,
                "candidate": ItemDetailSerializer.serialize(candidate_item),
                "recommendation": "upgrade",
                "reason": "No item currently equipped",
            }

        current_data = ItemDetailSerializer.serialize(current_item, equipped=True)
        candidate_data = ItemDetailSerializer.serialize(candidate_item, equipped=False)

        # Calculate differences
        damage_diff = getattr(candidate_item, "damage", 0) - getattr(
            current_item, "damage", 0
        )
        armor_diff = getattr(candidate_item, "armor", 0) - getattr(current_item, "armor", 0)
        weight_diff = getattr(candidate_item, "weight", 0) - getattr(
            current_item, "weight", 0
        )
        value_diff = getattr(candidate_item, "value", 0) - getattr(current_item, "value", 0)

        # Determine recommendation
        if damage_diff > 0 and armor_diff >= 0:
            recommendation = "upgrade"
        elif damage_diff >= 0 and armor_diff > 0:
            recommendation = "upgrade"
        elif damage_diff < 0 and armor_diff < 0:
            recommendation = "downgrade"
        else:
            recommendation = "sidegrade"

        return {
            "comparison_type": "item_to_item",
            "current": current_data,
            "candidate": candidate_data,
            "differences": {
                "damage_diff": damage_diff,
                "armor_diff": armor_diff,
                "weight_diff": weight_diff,
                "value_diff": value_diff,
            },
            "recommendation": recommendation,
            "reason": f"Damage {'+' if damage_diff > 0 else ''}{damage_diff}, "
            f"Armor {'+' if armor_diff > 0 else ''}{armor_diff}, "
            f"Weight {'+' if weight_diff > 0 else ''}{weight_diff}",
        }
