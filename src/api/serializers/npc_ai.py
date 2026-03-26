"""
NPC AI, Dialogue, and Quest serializers for game state.

This module handles serialization of:
- NPC behavior and AI state
- Dialogue trees and conversation state
- Quest progress and tracking
- NPC behavior profiles
"""

from typing import Any, Dict, List, Optional


class NPCAIStateSerializer:
    """Serializer for NPC AI and behavior state."""

    @staticmethod
    def serialize_npc_ai_state(npc: "NPC") -> Dict[str, Any]:
        """
        Serialize complete NPC AI state.

        Args:
            npc: NPC object with behavior state

        Returns:
            Dict with NPC AI state ready for API response
        """
        return {
            "npc_id": getattr(npc, "name", "unknown"),
            "name": getattr(npc, "name", "Unknown NPC"),
            "current_behavior": getattr(npc, "current_behavior", "idle"),
            "behavior_stack": getattr(npc, "behavior_stack", []),
            "emotion_state": NPCAIStateSerializer._get_emotion_state(npc),
            "aggression_level": NPCAIStateSerializer._get_aggression_level(npc),
            "trust_level": NPCAIStateSerializer._get_trust_level(npc),
            "last_interaction": getattr(npc, "last_interaction_time", None),
            "memory": NPCAIStateSerializer._serialize_npc_memory(npc),
            "position": {"x": getattr(npc, "x", 0), "y": getattr(npc, "y", 0)},
            "health_status": {
                "hp": getattr(npc, "hp", 0),
                "maxhp": getattr(npc, "maxhp", 100),
                "status": (
                    "healthy"
                    if getattr(npc, "hp", 0) > getattr(npc, "maxhp", 100) * 0.5
                    else "wounded"
                ),
            },
        }

    @staticmethod
    def serialize_npc_list(npcs: List["NPC"]) -> List[Dict[str, Any]]:
        """
        Serialize list of NPCs with AI state.

        Args:
            npcs: List of NPC objects

        Returns:
            List of serialized NPC states
        """
        return [NPCAIStateSerializer.serialize_npc_ai_state(npc) for npc in npcs]

    @staticmethod
    def _get_emotion_state(npc: "NPC") -> str:
        """
        Determine emotion state from NPC properties.

        Args:
            npc: NPC object

        Returns:
            Emotion state string (neutral, angry, happy, sad, fearful)
        """
        # Simple heuristic based on NPC state
        if getattr(npc, "in_combat", False):
            return "angry"
        elif getattr(npc, "hp", 0) < getattr(npc, "maxhp", 100) * 0.3:
            return "fearful"
        elif hasattr(npc, "mood") and npc.mood:
            return npc.mood
        else:
            return "neutral"

    @staticmethod
    def _get_aggression_level(npc: "NPC") -> float:
        """
        Calculate aggression level (0.0 to 1.0).

        Args:
            npc: NPC object

        Returns:
            Aggression level as float
        """
        if getattr(npc, "in_combat", False):
            return 1.0
        elif hasattr(npc, "aggression") and npc.aggression is not None:
            return float(npc.aggression)
        else:
            return 0.5

    @staticmethod
    def _get_trust_level(npc: "NPC") -> float:
        """
        Calculate trust level (0.0 to 1.0).

        Args:
            npc: NPC object

        Returns:
            Trust level as float
        """
        if hasattr(npc, "trust") and npc.trust is not None:
            return float(npc.trust)
        else:
            return 0.5

    @staticmethod
    def _serialize_npc_memory(npc: "NPC") -> List[Dict[str, Any]]:
        """
        Serialize NPC memory of interactions.

        Args:
            npc: NPC object

        Returns:
            List of memory entries
        """
        if not hasattr(npc, "memory") or not npc.memory:
            return []

        return [
            {
                "event": entry.get("event", "unknown"),
                "timestamp": entry.get("timestamp", None),
                "context": entry.get("context", ""),
                "importance": entry.get("importance", 0.5),
            }
            for entry in npc.memory[:10]  # Last 10 memories
        ]


class DialogueStateSerializer:
    """Serializer for dialogue trees and conversation state."""

    @staticmethod
    def serialize_dialogue_state(
        npc: "NPC",
        dialogue_tree: Optional[Dict[str, Any]] = None,
        current_node: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Serialize dialogue state for NPC interaction.

        Args:
            npc: NPC object
            dialogue_tree: Dialogue tree structure
            current_node: Current position in dialogue tree
            conversation_history: List of past exchanges

        Returns:
            Dict with dialogue state
        """
        if not dialogue_tree:
            dialogue_tree = DialogueStateSerializer._get_default_dialogue_tree(npc)

        if not current_node:
            current_node = "start"

        if not conversation_history:
            conversation_history = []

        current_options = DialogueStateSerializer._get_dialogue_options(
            dialogue_tree, current_node
        )

        return {
            "npc_id": getattr(npc, "name", "unknown"),
            "npc_name": getattr(npc, "name", "Unknown"),
            "dialogue_tree": dialogue_tree.get("id", "default"),
            "current_node": current_node,
            "current_text": DialogueStateSerializer._get_node_text(
                dialogue_tree, current_node
            ),
            "options": current_options,
            "conversation_history": conversation_history[-5:],  # Last 5 exchanges
            "dialogue_flags": getattr(npc, "dialogue_flags", {}),
            "relationship": {
                "known": getattr(npc, "player_knows_npc", False),
                "trust": DialogueStateSerializer._calculate_trust(npc),
                "times_talked": len(conversation_history),
            },
        }

    @staticmethod
    def serialize_dialogue_options(
        npc: "NPC",
        dialogue_tree: Optional[Dict[str, Any]] = None,
        current_node: str = "start",
    ) -> Dict[str, Any]:
        """
        Serialize available dialogue options.

        Args:
            npc: NPC object
            dialogue_tree: Dialogue tree structure
            current_node: Current dialogue node

        Returns:
            Dict with available options
        """
        if not dialogue_tree:
            dialogue_tree = DialogueStateSerializer._get_default_dialogue_tree(npc)

        options = DialogueStateSerializer._get_dialogue_options(
            dialogue_tree, current_node
        )

        return {
            "npc_id": getattr(npc, "name", "unknown"),
            "current_node": current_node,
            "options": options,
            "current_text": DialogueStateSerializer._get_node_text(
                dialogue_tree, current_node
            ),
        }

    @staticmethod
    def _get_default_dialogue_tree(npc: "NPC") -> Dict[str, Any]:
        """Get default dialogue tree for NPC."""
        return {
            "id": f"dialogue_{getattr(npc, 'name', 'unknown').lower()}",
            "nodes": {
                "start": {
                    "text": f"Hello, I'm {getattr(npc, 'name', 'Unknown')}.",
                    "options": [
                        {"id": 1, "text": "Who are you?", "next": "backstory"},
                        {"id": 2, "text": "Goodbye.", "next": "end"},
                    ],
                },
                "backstory": {
                    "text": "I'm just passing through.",
                    "options": [
                        {"id": 1, "text": "Anything I should know?", "next": "quest"},
                        {"id": 2, "text": "Goodbye.", "next": "end"},
                    ],
                },
                "quest": {
                    "text": "Help me if you can.",
                    "options": [
                        {"id": 1, "text": "What do you need?", "next": "quest_details"},
                        {"id": 2, "text": "I'll pass.", "next": "end"},
                    ],
                },
                "quest_details": {
                    "text": "I need your help with something.",
                    "options": [
                        {"id": 1, "text": "I'll help.", "next": "accept_quest"},
                        {"id": 2, "text": "Not interested.", "next": "end"},
                    ],
                },
                "accept_quest": {
                    "text": "Thank you! You won't regret this.",
                    "options": [{"id": 1, "text": "Goodbye.", "next": "end"}],
                },
                "end": {"text": "Farewell.", "options": []},
            },
        }

    @staticmethod
    def _get_dialogue_options(
        dialogue_tree: Dict[str, Any], current_node: str
    ) -> List[Dict[str, Any]]:
        """Get options for current dialogue node."""
        nodes = dialogue_tree.get("nodes", {})
        node = nodes.get(current_node, {})
        return node.get("options", [])

    @staticmethod
    def _get_node_text(dialogue_tree: Dict[str, Any], current_node: str) -> str:
        """Get text for current dialogue node."""
        nodes = dialogue_tree.get("nodes", {})
        node = nodes.get(current_node, {})
        return node.get("text", "...")

    @staticmethod
    def _calculate_trust(npc: "NPC") -> float:
        """Calculate trust level for dialogue relationship."""
        if hasattr(npc, "trust"):
            return float(npc.trust)
        return 0.5


class QuestStateSerializer:
    """Serializer for quest progress and tracking."""

    @staticmethod
    def serialize_quest(quest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize quest state.

        Args:
            quest: Quest data dictionary

        Returns:
            Serialized quest state
        """
        return {
            "quest_id": quest.get("id", "unknown"),
            "title": quest.get("title", "Unknown Quest"),
            "description": quest.get("description", ""),
            "status": quest.get(
                "status", "active"
            ),  # active, completed, failed, abandoned
            "progress": quest.get("progress", 0),
            "objectives": QuestStateSerializer._serialize_objectives(
                quest.get("objectives", [])
            ),
            "rewards": quest.get("rewards", {}),
            "started_at": quest.get("started_at", None),
            "completed_at": quest.get("completed_at", None),
            "deadline": quest.get("deadline", None),
            "giver": quest.get("giver", "Unknown"),
            "tags": quest.get("tags", []),
            "can_abandon": quest.get("can_abandon", True),
        }

    @staticmethod
    def serialize_active_quests(player: "Player") -> List[Dict[str, Any]]:
        """
        Serialize list of active quests.

        Args:
            player: Player object

        Returns:
            List of active quest states
        """
        quests = getattr(player, "active_quests", [])
        return [QuestStateSerializer.serialize_quest(quest) for quest in quests]

    @staticmethod
    def serialize_completed_quests(player: "Player") -> List[Dict[str, Any]]:
        """
        Serialize list of completed quests.

        Args:
            player: Player object

        Returns:
            List of completed quest states
        """
        quests = getattr(player, "completed_quests", [])
        return [QuestStateSerializer.serialize_quest(quest) for quest in quests]

    @staticmethod
    def serialize_quest_progress(quest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize quest progress details.

        Args:
            quest: Quest data

        Returns:
            Quest progress data
        """
        objectives = quest.get("objectives", [])
        completed_objectives = sum(
            1 for obj in objectives if obj.get("completed", False)
        )

        return {
            "quest_id": quest.get("id", "unknown"),
            "title": quest.get("title", "Unknown"),
            "progress": quest.get("progress", 0),
            "objectives_completed": completed_objectives,
            "objectives_total": len(objectives),
            "status": quest.get("status", "active"),
            "current_step": quest.get("current_step", ""),
            "next_step": quest.get("next_step", ""),
            "time_elapsed": QuestStateSerializer._calculate_time_elapsed(quest),
        }

    @staticmethod
    def _serialize_objectives(objectives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Serialize quest objectives."""
        return [
            {
                "id": obj.get("id", f"obj_{i}"),
                "text": obj.get("text", "Unknown"),
                "completed": obj.get("completed", False),
                "progress": obj.get("progress", 0),
                "type": obj.get(
                    "type", "task"
                ),  # task, explore, collect, defeat, speak
            }
            for i, obj in enumerate(objectives)
        ]

    @staticmethod
    def _calculate_time_elapsed(quest: Dict[str, Any]) -> Optional[float]:
        """Calculate time elapsed since quest started (in seconds)."""
        started = quest.get("started_at")
        if not started:
            return None
        # In a real implementation, calculate from timestamps
        return 0.0


class NPCBehaviorProfileSerializer:
    """Serializer for NPC behavior profiles and AI configuration."""

    @staticmethod
    def serialize_behavior_profile(npc: "NPC") -> Dict[str, Any]:
        """
        Serialize NPC behavior profile.

        Args:
            npc: NPC object

        Returns:
            Behavior profile data
        """
        return {
            "npc_id": getattr(npc, "name", "unknown"),
            "name": getattr(npc, "name", "Unknown"),
            "personality": NPCBehaviorProfileSerializer._get_personality(npc),
            "behaviors": NPCBehaviorProfileSerializer._get_behaviors(npc),
            "combat_style": NPCBehaviorProfileSerializer._get_combat_style(npc),
            "preferences": NPCBehaviorProfileSerializer._get_preferences(npc),
            "relationships": NPCBehaviorProfileSerializer._get_relationships(npc),
            "skills": NPCBehaviorProfileSerializer._get_skills(npc),
        }

    @staticmethod
    def _get_personality(npc: "NPC") -> Dict[str, Any]:
        """Get NPC personality traits."""
        return {
            "archetype": getattr(npc, "personality_archetype", "neutral"),
            "traits": getattr(npc, "personality_traits", []),
            "intelligence": getattr(npc, "intelligence", 0.5),
            "courage": getattr(npc, "courage", 0.5),
            "friendliness": getattr(npc, "friendliness", 0.5),
        }

    @staticmethod
    def _get_behaviors(npc: "NPC") -> Dict[str, Any]:
        """Get NPC behavior configuration."""
        return {
            "idle_behavior": getattr(npc, "idle_behavior", "wander"),
            "combat_behavior": getattr(npc, "combat_behavior", "aggressive"),
            "social_behavior": getattr(npc, "social_behavior", "neutral"),
            "response_type": getattr(npc, "response_type", "defensive"),
        }

    @staticmethod
    def _get_combat_style(npc: "NPC") -> Dict[str, Any]:
        """Get NPC combat style."""
        return {
            "preference": getattr(npc, "combat_preference", "melee"),
            "aggression": getattr(npc, "aggression", 0.5),
            "defense": getattr(npc, "defense_priority", 0.5),
            "flee_threshold": getattr(npc, "flee_at_health_percent", 0.1),
        }

    @staticmethod
    def _get_preferences(npc: "NPC") -> Dict[str, Any]:
        """Get NPC preferences."""
        return {
            "likes": getattr(npc, "likes", []),
            "dislikes": getattr(npc, "dislikes", []),
            "fears": getattr(npc, "fears", []),
            "desires": getattr(npc, "desires", []),
        }

    @staticmethod
    def _get_relationships(npc: "NPC") -> Dict[str, Any]:
        """Get NPC relationships."""
        return {
            "friends": getattr(npc, "friends", []),
            "enemies": getattr(npc, "enemies", []),
            "neutral": getattr(npc, "neutral_npcs", []),
            "reputation": getattr(npc, "reputation", {}),
        }

    @staticmethod
    def _get_skills(npc: "NPC") -> Dict[str, float]:
        """Get NPC skills."""
        return {
            "combat": getattr(npc, "combat_skill", 0.5),
            "magic": getattr(npc, "magic_skill", 0.5),
            "stealth": getattr(npc, "stealth_skill", 0.5),
            "persuasion": getattr(npc, "persuasion_skill", 0.5),
            "tracking": getattr(npc, "tracking_skill", 0.5),
        }
