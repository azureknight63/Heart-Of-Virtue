"""NPC/Enemy serialization for API responses."""

from typing import Dict, Any, List
from src.api.serializers.item_serializer import ItemSerializer


class NPCSerializer:
    """Serialize NPC objects to JSON-safe dictionaries."""

    @staticmethod
    def serialize(npc: Any) -> Dict[str, Any]:
        """Serialize a single NPC with basic combat stats.

        Args:
            npc: NPC object to serialize

        Returns:
            Dictionary with NPC data
        """
        if not npc:
            return {}

        npc_data = {
            "id": str(id(npc)),
            "name": getattr(npc, "name", "Unknown"),
            "type": type(npc).__name__,
            "description": getattr(npc, "description", ""),
            "level": getattr(npc, "level", 1),
        }

        # Combat stats
        if hasattr(npc, "current_hp"):
            npc_data["health"] = npc.current_hp
        if hasattr(npc, "maxhp"):
            npc_data["max_health"] = npc.maxhp
        elif hasattr(npc, "max_hp"):
            npc_data["max_health"] = npc.max_hp

        # Hostility
        if hasattr(npc, "is_hostile"):
            npc_data["is_hostile"] = npc.is_hostile

        # Conversation/dialogue
        if hasattr(npc, "idle_message"):
            npc_data["idle_message"] = npc.idle_message
        if hasattr(npc, "alert_message"):
            npc_data["alert_message"] = npc.alert_message

        # Keywords for interaction
        keywords = []
        if hasattr(npc, "keywords") and npc.keywords:
            keywords = list(npc.keywords)

        # Add attack keyword for hostile/aggressive NPCs
        is_hostile = getattr(npc, "is_hostile", False)
        is_aggressive = getattr(npc, "aggro", False)
        if (is_hostile or is_aggressive) and "attack" not in keywords:
            keywords.append("attack")

        if keywords:
            npc_data["keywords"] = keywords

        # LLM chat capability flags (set by HumanNPCLLMMixin)
        import os
        chat_enabled_env = os.getenv("NPC_CHAT_LLM_ENABLED", "0") in ("1", "true", "True")
        has_mixin = hasattr(npc, "_init_chat_attrs")
        npc_data["llm_chat_enabled"] = has_mixin and chat_enabled_env
        loquacity_max = getattr(npc, "loquacity_max", 0)
        loquacity_current = getattr(npc, "loquacity_current", 0)
        loquacity_threshold = getattr(npc, "loquacity_threshold", 0)
        npc_data["loquacity_available"] = (
            has_mixin and loquacity_current >= loquacity_threshold and loquacity_max > 0
        ) if loquacity_max > 0 else has_mixin

        return npc_data

    @staticmethod
    def serialize_list(npcs: List[Any]) -> List[Dict[str, Any]]:
        """Serialize multiple NPCs.

        Args:
            npcs: List of NPC objects

        Returns:
            List of serialized NPC dictionaries
        """
        if not npcs:
            return []

        return [NPCSerializer.serialize(npc) for npc in npcs]

    @staticmethod
    def serialize_with_stats(npc: Any) -> Dict[str, Any]:
        """Serialize NPC with detailed combat statistics.

        Args:
            npc: NPC object to serialize

        Returns:
            Dictionary with detailed NPC and stat data
        """
        npc_data = NPCSerializer.serialize(npc)

        # Add all combat stats if available
        stat_names = [
            "strength",
            "dexterity",
            "vitality",
            "intelligence",
            "wisdom",
            "speed",
        ]
        stats = {}
        for stat in stat_names:
            if hasattr(npc, stat):
                stats[stat] = getattr(npc, stat)

        if stats:
            npc_data["stats"] = stats

        # Add resistances
        if hasattr(npc, "add_resistance"):
            resistances = npc.add_resistance
            if resistances:
                npc_data["resistances"] = resistances

        # Add status effect resistances
        if hasattr(npc, "add_status_resistance"):
            status_res = npc.add_status_resistance
            if status_res:
                npc_data["status_resistances"] = status_res

        # Add equipment
        if hasattr(npc, "equipped"):
            npc_data["equipped"] = npc.equipped

        return npc_data

    @staticmethod
    def serialize_merchant(npc: Any) -> Dict[str, Any]:
        """Serialize NPC as merchant with shop inventory.

        Args:
            npc: NPC object (merchant) to serialize

        Returns:
            Dictionary with merchant data including shop items
        """
        npc_data = NPCSerializer.serialize(npc)

        # Add merchant/shop flag
        npc_data["is_merchant"] = True

        # Serialize inventory as shop stock
        if hasattr(npc, "inventory") and npc.inventory:
            npc_data["shop_items"] = ItemSerializer.serialize_list(npc.inventory)
        else:
            npc_data["shop_items"] = []

        # Add shop keywords/interactions
        if hasattr(npc, "keywords"):
            npc_data["shop_keywords"] = npc.keywords

        return npc_data

    @staticmethod
    def serialize_with_inventory(npc: Any) -> Dict[str, Any]:
        """Serialize NPC with full inventory details.

        Args:
            npc: NPC object to serialize

        Returns:
            Dictionary with NPC and inventory data
        """
        npc_data = NPCSerializer.serialize_with_stats(npc)

        # Add inventory
        if hasattr(npc, "inventory"):
            npc_data["inventory"] = ItemSerializer.serialize_list(npc.inventory)
            npc_data["inventory_count"] = len(npc.inventory)
        else:
            npc_data["inventory"] = []
            npc_data["inventory_count"] = 0

        return npc_data

    @staticmethod
    def serialize_for_combat(npc: Any) -> Dict[str, Any]:
        """Serialize NPC for combat display.

        Args:
            npc: NPC object to serialize

        Returns:
            Dictionary with combat-relevant NPC data
        """
        npc_data = NPCSerializer.serialize_with_stats(npc)

        # Add combat-specific info
        if hasattr(npc, "combat_list"):
            npc_data["in_combat"] = len(npc.combat_list) > 0

        if hasattr(npc, "status_effects"):
            npc_data["status_effects"] = getattr(npc, "status_effects", [])

        return npc_data
