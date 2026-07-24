"""NPC/Enemy serialization for API responses."""

from typing import Dict, Any, List


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
        if hasattr(npc, "hp"):
            npc_data["health"] = npc.hp
        if hasattr(npc, "maxhp"):
            npc_data["max_health"] = npc.maxhp
        elif hasattr(npc, "max_hp"):
            npc_data["max_health"] = npc.max_hp

        # Hostility — the real model has no `is_hostile` flag; derive it from
        # `aggro` (will attack on sight) and `friend` (never hostile to Jean).
        if hasattr(npc, "aggro"):
            npc_data["is_hostile"] = bool(getattr(npc, "aggro", False)) and not getattr(
                npc, "friend", False
            )

        # Conversation/dialogue
        if hasattr(npc, "idle_message"):
            npc_data["idle_message"] = npc.idle_message
        if hasattr(npc, "alert_message"):
            npc_data["alert_message"] = npc.alert_message

        # Keywords for interaction
        keywords = []
        if hasattr(npc, "keywords") and npc.keywords:
            keywords = list(npc.keywords)

        # Add attack keyword for hostile/aggressive NPCs, unless they are friendly
        is_hostile = getattr(npc, "is_hostile", False)
        is_aggressive = getattr(npc, "aggro", False)
        is_friend = getattr(npc, "friend", False)
        if (is_hostile or is_aggressive) and not is_friend and "attack" not in keywords:
            keywords.append("attack")

        if keywords:
            npc_data["keywords"] = keywords

        # LLM chat capability flags (set by ConversationalNPCMixin)
        import os

        chat_enabled_env = os.getenv("NPC_CHAT_LLM_ENABLED", "0") in (
            "1",
            "true",
            "True",
        )
        has_mixin = hasattr(npc, "_init_chat_attrs")
        npc_data["llm_chat_enabled"] = has_mixin and chat_enabled_env
        loquacity_max = getattr(npc, "loquacity_max", 0)
        loquacity_current = getattr(npc, "loquacity_current", 0)
        loquacity_threshold = getattr(npc, "loquacity_threshold", 0)
        npc_data["loquacity_available"] = (
            (
                has_mixin
                and loquacity_current >= loquacity_threshold
                and loquacity_max > 0
            )
            if loquacity_max > 0
            else has_mixin
        )

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
