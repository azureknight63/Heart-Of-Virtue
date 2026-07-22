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

from typing import Dict, Optional

# Effect descriptors for consumable items, keyed by class name.
# Each list entry has a `type` discriminator used by the frontend chip renderer.
# New consumables only need a new entry here — no frontend layout changes required.
# SYNC RISK: ranges are pre-computed from each item's power and variance in items.py.
# If items.py changes power or variance for a consumable, update its range here too.
_CONSUMABLE_EFFECTS = {
    "Restorative": [
        {"type": "heal", "stat": "hp", "power": 60, "range": [48, 72]},
    ],
    "Draught": [
        {"type": "heal", "stat": "fatigue", "power": 100, "range": [80, 120]},
    ],
    "Antidote": [
        {"type": "heal", "stat": "hp", "power": 15, "range": [12, 18]},
        {"type": "status_remove", "status_name": "Poisoned", "status_type": "poison"},
    ],
    "IronRation": [
        {"type": "heal", "stat": "hp", "power": 30, "range": [27, 33]},
    ],
    "Bitterroot": [
        {"type": "heal", "stat": "hp", "power": 60, "range": [51, 69]},
    ],
    "DriedCrystalSap": [
        {"type": "heal", "stat": "hp", "power": 20, "range": [20, 20]},
    ],
}

# Scalar stat-bonus attributes an item/enchantment may add, mapped to their
# player-stat label. Mirrors functions.py:refresh_stat_bonuses' bonuses_map —
# keep these in sync since that function is the authoritative source.
_BONUS_ATTRS = {
    "add_str": "strength",
    "add_fin": "finesse",
    "add_maxhp": "maxhp",
    "add_maxfatigue": "maxfatigue",
    "add_speed": "speed",
    "add_endurance": "endurance",
    "add_charisma": "charisma",
    "add_intelligence": "intelligence",
    "add_faith": "faith",
    "add_weight_tolerance": "weight_tolerance",
}

# Accessory subtypes that don't auto-replace on equip (see inventory.py
# equip_item) — a player can have multiple equipped at once, so there's no
# single "slot counterpart" to compare against.
_MULTI_EQUIP_ACCESSORY_SUBTYPES = ["Ring", "Bracelet", "Earring"]


def _collect_item_bonuses(item) -> Dict:
    """Collect non-zero scalar stat bonuses an item grants, keyed by stat label."""
    return {
        label: getattr(item, attr)
        for attr, label in _BONUS_ATTRS.items()
        if getattr(item, attr, 0)
    }


def _get_equip_slot_status(player, item):
    """
    Determine whether `item` has a single comparable equip-slot counterpart.

    Returns (comparable, counterpart):
        comparable: False for multi-equip accessory subtypes (Ring/Bracelet/
            Earring), which have no single slot counterpart to compare against.
        counterpart: the currently-equipped item occupying that slot, or None
            if the slot is empty.
    """
    maintype = getattr(item, "maintype", None)
    if not maintype:
        return False, None
    subtype = getattr(item, "subtype", None)
    if maintype == "Accessory" and subtype in _MULTI_EQUIP_ACCESSORY_SUBTYPES:
        return False, None

    inventory_list = getattr(player, "inventory_list", None) or getattr(
        player, "inventory", []
    )
    for other_item in inventory_list:
        if other_item is item or not getattr(other_item, "isequipped", False):
            continue
        if getattr(other_item, "maintype", None) != maintype:
            continue
        if maintype == "Accessory" and getattr(other_item, "subtype", None) != subtype:
            continue
        return True, other_item
    return True, None


def _diff_bonuses(current_item, candidate_item) -> Dict[str, float]:
    """Compute the per-stat delta of scalar bonuses between two items."""
    diffs = {}
    for attr, label in _BONUS_ATTRS.items():
        delta = getattr(candidate_item, attr, 0) - getattr(current_item, attr, 0)
        if delta:
            diffs[label] = delta
    return diffs


def _diff_resistance_dicts(current_item, candidate_item, attr_name: str) -> Dict[str, float]:
    """Compute the per-key delta of a resistance-style dict attribute between two items."""
    current = getattr(current_item, attr_name, None) or {}
    candidate = getattr(candidate_item, attr_name, None) or {}
    diffs = {}
    for key in set(current) | set(candidate):
        delta = candidate.get(key, 0) - current.get(key, 0)
        if delta:
            diffs[key] = delta
    return diffs


class InventoryItemSerializer:
    """Serialize a single item in player inventory."""

    @staticmethod
    def serialize(item, index: int, player=None) -> Dict:
        """
        Serialize an item for inventory listing.

        Args:
            item: The item object to serialize
            index: The position in inventory
            player: The owning Player, used to compute an equipped-item
                comparison block. Omit to skip the comparison.

        Returns:
            Dictionary with item data suitable for JSON
        """
        # Determine item category
        item_type = item.__class__.__name__
        maintype = getattr(item, "maintype", "")

        # Build base item data
        interactions = getattr(item, "interactions", [])
        item_data = {
            "id": str(id(item)),  # Unique identifier for this item object
            "index": index,
            "name": getattr(item, "name", "Unknown Item"),
            "type": item_type,
            "maintype": maintype,
            "subtype": getattr(item, "subtype", ""),
            "quantity": getattr(item, "count", getattr(item, "quantity", 1)),
            "rarity": getattr(item, "rarity", "common"),
            "weight": getattr(item, "weight", 0.0),
            "value": getattr(item, "value", 0),
            # Use interactions list as the canonical truth for what actions are available.
            # Fallback to hasattr checks for items that have methods but no interactions list.
            "can_equip": "equip" in interactions or "unequip" in interactions,
            "can_use": "use" in interactions or "drink" in interactions,
            "can_read": "read" in interactions,
            "can_drop": "drop" in interactions,
            "is_equipped": getattr(item, "isequipped", False),
            "is_merchandise": getattr(item, "merchandise", False),
            "description": getattr(item, "description", ""),
        }

        # Add weapon-specific stats
        if item_type == "Weapon" or maintype == "Weapon":
            item_data["damage"] = round(getattr(item, "damage", 0))
            item_data["str_mod"] = getattr(item, "str_mod", 0)
            item_data["fin_mod"] = getattr(item, "fin_mod", 0)
            from src.items import get_base_damage_type  # local import: see game_service.py precedent

            item_data["damage_type"] = get_base_damage_type(item)

        # Add armor-specific stats (Armor, Boots, Helm, Gloves, Accessory)
        if item_type in [
            "Armor",
            "Boots",
            "Helm",
            "Gloves",
            "Accessory",
        ] or maintype in ["Armor", "Boots", "Helm", "Gloves", "Accessory"]:
            item_data["protection"] = round(getattr(item, "protection", 0))
            item_data["str_mod"] = getattr(item, "str_mod", 0)
            if hasattr(item, "fin_mod"):
                item_data["fin_mod"] = getattr(item, "fin_mod", 0)

        # Add composable effects array for usable (consumable) items
        if item_data["can_use"]:
            item_data["effects"] = _CONSUMABLE_EFFECTS.get(item_type, [])

        # Add stat bonuses and resistances granted by this item (enchantments)
        if item_data["can_equip"]:
            bonuses = _collect_item_bonuses(item)
            if bonuses:
                item_data["bonuses"] = bonuses
            resistances = getattr(item, "add_resistance", None)
            if resistances:
                item_data["resistances"] = dict(resistances)
            status_resistances = getattr(item, "add_status_resistance", None)
            if status_resistances:
                item_data["status_resistances"] = dict(status_resistances)

        # Add a comparison against the currently-equipped counterpart, if any
        if player is not None and item_data["can_equip"] and not item_data["is_equipped"]:
            comparable, counterpart = _get_equip_slot_status(player, item)
            if comparable:
                item_data["comparison"] = ItemComparisonSerializer.serialize(
                    counterpart, item
                )

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
        inventory_list = getattr(player, "inventory_list", None) or getattr(
            player, "inventory", []
        )
        for idx, item in enumerate(inventory_list):
            items.append(InventoryItemSerializer.serialize(item, idx, player))
            total_weight += getattr(item, "weight", 0.0)

        return {
            "total_weight": round(total_weight, 2),
            "weight_limit": getattr(player, "carrying_capacity", 100.0),
            "weight_percentage": round(
                (total_weight / getattr(player, "carrying_capacity", 100.0)) * 100,
                1,
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
            "armor": round(getattr(item, "armor", 0)),
            "damage": round(getattr(item, "damage", 0)),
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
        equipment_dict = getattr(player, "equipped", None) or getattr(
            player, "equipment", {}
        )

        # Fallback: check individual attributes if dict is empty
        if not equipment_dict:
            slot_mapping = {
                "weapon": "eq_weapon",
                "shield": "shield",
                "head": "head",
                "body": "body",
                "legs": "legs",
                "feet": "feet",
                "hands": "hands",
                "accessory_1": "accessory_1",
                "accessory_2": "accessory_2",
            }
            equipment_dict = {}
            for slot, attr in slot_mapping.items():
                item = getattr(player, attr, None)
                if item:
                    # Only include if specifically marked as equipped, or if it's a weapon (always have a weapon)
                    # Use isequipped flag to distinguish real equipped items from defaults if needed
                    if getattr(item, "isequipped", False) or (
                        slot == "weapon" and item
                    ):
                        equipment_dict[slot] = item

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
        inventory_list = getattr(player, "inventory_list", None) or getattr(
            player, "inventory", []
        )
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
    def serialize(
        item, equipped: bool = False, inventory_index: Optional[int] = None
    ) -> Dict:
        """
        Serialize complete item details.

        Args:
            item: The item to serialize
            equipped: Whether the item is currently equipped
            inventory_index: Index in inventory if applicable

        Returns:
            Dictionary with full item information
        """
        from src.items import Special

        return {
            "name": getattr(item, "name", "Unknown Item"),
            "type": item.__class__.__name__,
            "description": getattr(item, "description", ""),
            "quantity": getattr(item, "count", getattr(item, "quantity", 1)),
            "rarity": getattr(item, "rarity", "common"),
            "weight": getattr(item, "weight", 0.0),
            "value": getattr(item, "value", 0),
            "equipped": equipped,
            "inventory_index": inventory_index,
            "can_equip": hasattr(item, "equip"),
            "can_use": hasattr(item, "use"),
            "can_drop": True,  # Most items can be dropped
            "stats": {
                "protection": round(getattr(item, "protection", 0)),
                "damage": round(getattr(item, "damage", 0)),
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
                "special": isinstance(item, Special),
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
        protection_diff = getattr(candidate_item, "protection", 0) - getattr(
            current_item, "protection", 0
        )
        weight_diff = getattr(candidate_item, "weight", 0) - getattr(
            current_item, "weight", 0
        )
        value_diff = getattr(candidate_item, "value", 0) - getattr(
            current_item, "value", 0
        )
        bonus_diffs = _diff_bonuses(current_item, candidate_item)
        resistance_diffs = _diff_resistance_dicts(
            current_item, candidate_item, "add_resistance"
        )
        status_resistance_diffs = _diff_resistance_dicts(
            current_item, candidate_item, "add_status_resistance"
        )

        # Determine recommendation. Weapons never carry protection and armor
        # never carries damage, so one side of each pair is always exactly 0
        # for a same-category comparison. The upgrade/downgrade checks below
        # are symmetric on purpose: each stat only needs to improve/worsen
        # while the other doesn't move in the opposite direction, so a
        # strictly-worse weapon (damage_diff < 0, protection_diff == 0) or a
        # strictly-worse armor piece (protection_diff < 0, damage_diff == 0)
        # is still correctly flagged instead of falling through to
        # "sidegrade".
        if damage_diff > 0 and protection_diff >= 0:
            recommendation = "upgrade"
        elif damage_diff >= 0 and protection_diff > 0:
            recommendation = "upgrade"
        elif damage_diff < 0 and protection_diff <= 0:
            recommendation = "downgrade"
        elif damage_diff <= 0 and protection_diff < 0:
            recommendation = "downgrade"
        else:
            recommendation = "sidegrade"

        reason_parts = []
        if damage_diff:
            reason_parts.append(f"Damage {'+' if damage_diff > 0 else ''}{damage_diff}")
        if protection_diff:
            reason_parts.append(
                f"Protection {'+' if protection_diff > 0 else ''}{protection_diff}"
            )
        reason_parts.append(f"Weight {'+' if weight_diff > 0 else ''}{weight_diff}")

        return {
            "comparison_type": "item_to_item",
            "current": current_data,
            "candidate": candidate_data,
            "differences": {
                "damage_diff": damage_diff,
                "protection_diff": protection_diff,
                "weight_diff": weight_diff,
                "value_diff": value_diff,
                "bonus_diffs": bonus_diffs,
                "resistance_diffs": resistance_diffs,
                "status_resistance_diffs": status_resistance_diffs,
            },
            "recommendation": recommendation,
            "reason": ", ".join(reason_parts),
        }
