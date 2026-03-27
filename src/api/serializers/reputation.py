"""
Reputation system serializers for Phase 3 Stage 2.

Handles serialization of NPC relationships, reputation tracking, and
relationship-based dialogue/quest gating.
"""

from typing import Dict, Any, List, Optional, Tuple
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from player import Player


class NPCRelationshipSerializer:
    """Serializes individual NPC relationship data."""

    @staticmethod
    def serialize_relationship(
        npc_id: str,
        npc_name: str,
        reputation: int,
    ) -> Dict[str, Any]:
        """Serialize an NPC relationship.

        Args:
            npc_id: NPC identifier
            npc_name: NPC display name
            reputation: Reputation score (-100 to +100)

        Returns:
            Serialized relationship data
        """
        # Determine attitude based on reputation
        if reputation >= 50:
            attitude = "friendly"
            emoji = "😊"
        elif reputation >= 25:
            attitude = "favorable"
            emoji = "🙂"
        elif reputation >= 0:
            attitude = "neutral"
            emoji = "😐"
        elif reputation >= -25:
            attitude = "wary"
            emoji = "😕"
        elif reputation >= -50:
            attitude = "hostile"
            emoji = "😠"
        else:
            attitude = "enemy"
            emoji = "😡"

        return {
            "npc_id": npc_id,
            "npc_name": npc_name,
            "reputation": reputation,
            "attitude": attitude,
            "emoji": emoji,
            "trust_level": NPCRelationshipSerializer._calculate_trust_level(reputation),
            "locked_dialogue": reputation < 0,  # Dialogue locked at negative reputation
        }

    @staticmethod
    def _calculate_trust_level(reputation: int) -> str:
        """Calculate trust level from reputation.

        Args:
            reputation: Reputation score

        Returns:
            Trust level string
        """
        if reputation >= 75:
            return "Complete Trust"
        elif reputation >= 50:
            return "High Trust"
        elif reputation >= 25:
            return "Good Trust"
        elif reputation >= 0:
            return "Neutral"
        elif reputation >= -25:
            return "Suspicious"
        elif reputation >= -50:
            return "Distrusting"
        else:
            return "Hostile"

    @staticmethod
    def _get_npc_name(npc_id: str) -> str:
        """Get NPC display name from ID.

        Args:
            npc_id: NPC identifier

        Returns:
            NPC display name
        """
        # Simple mapping - can be expanded
        npc_names = {
            "cave_guide": "Cave Guide",
            "bat_trainer": "Bat Trainer",
            "blacksmith": "Blacksmith",
            "merchant": "Merchant",
            "healer": "Healer",
            "dragon_slayer": "Dragon Slayer Guild",
            "hermit": "Old Hermit",
        }
        return npc_names.get(npc_id, npc_id.replace("_", " ").title())


class PlayerReputationSerializer:
    """Serializes player's reputation with all NPCs."""

    @staticmethod
    def serialize_all_reputation(player: "Player") -> Dict[str, Any]:
        """Serialize player's complete reputation state.

        Args:
            player: Player object

        Returns:
            All reputation data
        """
        reputation_data = getattr(player, "reputation", {})

        relationships = {}
        for npc_id, rep_value in reputation_data.items():
            # Get NPC name from NPC registry or use ID
            npc_name = PlayerReputationSerializer._get_npc_name(npc_id)
            relationships[npc_id] = NPCRelationshipSerializer.serialize_relationship(
                npc_id, npc_name, rep_value
            )

        return {
            "total_npcs": len(relationships),
            "relationships": relationships,
            "highest_reputation": max(reputation_data.values(), default=0),
            "lowest_reputation": min(reputation_data.values(), default=0),
            "friendly_npcs": sum(1 for r in reputation_data.values() if r >= 50),
            "hostile_npcs": sum(1 for r in reputation_data.values() if r <= -50),
        }

    @staticmethod
    def serialize_reputation_change(
        npc_id: str,
        npc_name: str,
        old_reputation: int,
        new_reputation: int,
        reason: str,
    ) -> Dict[str, Any]:
        """Serialize a reputation change event.

        Args:
            npc_id: NPC identifier
            npc_name: NPC name
            old_reputation: Previous reputation
            new_reputation: New reputation
            reason: Reason for change (e.g., "quest_complete", "dialogue_choice")

        Returns:
            Reputation change data
        """
        change = new_reputation - old_reputation
        direction = (
            "positive" if change > 0 else "negative" if change < 0 else "neutral"
        )

        return {
            "npc_id": npc_id,
            "npc_name": npc_name,
            "old_reputation": old_reputation,
            "new_reputation": new_reputation,
            "change": change,
            "direction": direction,
            "reason": reason,
            "old_attitude": NPCRelationshipSerializer.serialize_relationship(
                npc_id, npc_name, old_reputation
            )["attitude"],
            "new_attitude": NPCRelationshipSerializer.serialize_relationship(
                npc_id, npc_name, new_reputation
            )["attitude"],
            "attitude_changed": (
                NPCRelationshipSerializer.serialize_relationship(
                    npc_id, npc_name, old_reputation
                )["attitude"]
                != NPCRelationshipSerializer.serialize_relationship(
                    npc_id, npc_name, new_reputation
                )["attitude"]
            ),
        }

    @staticmethod
    def _get_npc_name(npc_id: str) -> str:
        """Get NPC display name from ID.

        Args:
            npc_id: NPC identifier

        Returns:
            NPC display name
        """
        # Simple mapping - can be expanded
        npc_names = {
            "cave_guide": "Cave Guide",
            "bat_trainer": "Bat Trainer",
            "blacksmith": "Blacksmith",
            "merchant": "Merchant",
            "healer": "Healer",
            "dragon_slayer": "Dragon Slayer Guild",
            "hermit": "Old Hermit",
        }
        return npc_names.get(npc_id, npc_id.replace("_", " ").title())


class RelationshipFlagSerializer:
    """Serializes relationship flags (romance, betrayal, alliance, etc.)."""

    # Valid flag types
    VALID_FLAGS = {
        "romance": bool,
        "betrayed": bool,
        "alliance": bool,
        "enemy": bool,
        "quest_chain_started": bool,
        "quest_chain_completed": bool,
        "special_dialogue_unlocked": bool,
        "merchant_discount": bool,
    }

    @staticmethod
    def set_flag(
        player: "Player",
        npc_id: str,
        flag_name: str,
        value: bool,
    ) -> Dict[str, Any]:
        """Set a relationship flag for an NPC.

        Args:
            player: Player object
            npc_id: NPC identifier
            flag_name: Flag name (must be in VALID_FLAGS)
            value: Flag value (True/False)

        Returns:
            Updated flag data
        """
        if flag_name not in RelationshipFlagSerializer.VALID_FLAGS:
            return {
                "success": False,
                "error": f"Invalid flag '{flag_name}'. Valid flags: {list(RelationshipFlagSerializer.VALID_FLAGS.keys())}",
            }

        if not hasattr(player, "relationship_flags"):
            player.relationship_flags = {}

        if npc_id not in player.relationship_flags:
            player.relationship_flags[npc_id] = {}

        old_value = player.relationship_flags[npc_id].get(flag_name, False)
        player.relationship_flags[npc_id][flag_name] = value

        return {
            "success": True,
            "npc_id": npc_id,
            "flag": flag_name,
            "old_value": old_value,
            "new_value": value,
            "changed": old_value != value,
        }

    @staticmethod
    def get_flags(player: "Player", npc_id: str) -> Dict[str, Any]:
        """Get all flags for an NPC.

        Args:
            player: Player object
            npc_id: NPC identifier

        Returns:
            All flags for the NPC
        """
        if not hasattr(player, "relationship_flags"):
            player.relationship_flags = {}

        npc_flags = player.relationship_flags.get(npc_id, {})

        return {
            "npc_id": npc_id,
            "flags": npc_flags,
            "active_flags": [f for f, v in npc_flags.items() if v],
            "flag_count": len(npc_flags),
            "active_count": sum(1 for v in npc_flags.values() if v),
        }

    @staticmethod
    def serialize_flags_summary(player: "Player") -> Dict[str, Any]:
        """Serialize all relationship flags across all NPCs.

        Args:
            player: Player object

        Returns:
            Summary of all flags
        """
        if not hasattr(player, "relationship_flags"):
            player.relationship_flags = {}

        all_flags = {}
        total_active = 0

        for npc_id, flags in player.relationship_flags.items():
            active = [f for f, v in flags.items() if v]
            if active:
                all_flags[npc_id] = active
                total_active += len(active)

        return {
            "total_npcs_with_flags": len(all_flags),
            "total_active_flags": total_active,
            "flags_by_npc": all_flags,
            "romance_count": sum(
                1
                for npc_flags in player.relationship_flags.values()
                if npc_flags.get("romance", False)
            ),
            "allied_npcs": sum(
                1
                for npc_flags in player.relationship_flags.values()
                if npc_flags.get("alliance", False)
            ),
            "enemy_npcs": sum(
                1
                for npc_flags in player.relationship_flags.values()
                if npc_flags.get("enemy", False)
            ),
        }


class ReputationThresholdValidator:
    """Validates dialogue and quest access based on reputation."""

    # Dialogue node requirements
    DIALOGUE_THRESHOLDS = {
        "greeting_friendly": 25,  # Only greet if at least somewhat friendly
        "quest_offer": 0,  # Can offer quests to neutral
        "special_dialogue": 50,  # Special dialogue only for friendly NPCs
        "secret_revealed": 75,  # Secrets only for trusted NPCs
        "betrayal_available": -50,  # Can betray if hostile
    }

    # Quest availability requirements
    QUEST_THRESHOLDS = {
        "normal_quest": 0,  # Available at neutral
        "important_quest": 25,  # Need favorable reputation
        "secret_quest": 75,  # Only for high trust
        "difficult_quest": 50,  # Need good reputation
    }

    @staticmethod
    def check_dialogue_available(
        player: "Player",
        npc_id: str,
        dialogue_node: str,
    ) -> Tuple[bool, Optional[str]]:
        """Check if a dialogue node is available based on reputation.

        Args:
            player: Player object
            npc_id: NPC identifier
            dialogue_node: Dialogue node identifier

        Returns:
            Tuple of (is_available, locked_reason)
        """
        reputation = getattr(player, "reputation", {}).get(npc_id, 0)

        # Get required reputation for this dialogue
        required = ReputationThresholdValidator.DIALOGUE_THRESHOLDS.get(
            dialogue_node, 0
        )

        if reputation >= required:
            return True, None
        else:
            npc_name = NPCRelationshipSerializer._get_npc_name(npc_id)
            reason = f"{npc_name} doesn't want to talk about that. (Need {required} reputation, you have {reputation})"
            return False, reason

    @staticmethod
    def check_quest_available(
        player: "Player",
        npc_id: str,
        quest_type: str,
    ) -> Tuple[bool, Optional[str]]:
        """Check if a quest is available based on reputation.

        Args:
            player: Player object
            npc_id: NPC identifier
            quest_type: Type of quest (normal_quest, secret_quest, etc.)

        Returns:
            Tuple of (is_available, locked_reason)
        """
        reputation = getattr(player, "reputation", {}).get(npc_id, 0)

        # Get required reputation for this quest type
        required = ReputationThresholdValidator.QUEST_THRESHOLDS.get(quest_type, 0)

        if reputation >= required:
            return True, None
        else:
            npc_name = NPCRelationshipSerializer._get_npc_name(npc_id)
            reason = f"{npc_name} doesn't trust you with this quest. (Need {required} reputation, you have {reputation})"
            return False, reason

    @staticmethod
    def serialize_dialogue_locks(
        player: "Player",
        npc_id: str,
        available_dialogues: List[str],
    ) -> Dict[str, Any]:
        """Serialize which dialogues are locked/unlocked.

        Args:
            player: Player object
            npc_id: NPC identifier
            available_dialogues: List of possible dialogue nodes

        Returns:
            Lock status for each dialogue
        """
        reputation = getattr(player, "reputation", {}).get(npc_id, 0)

        dialogue_status = {}
        unlocked_count = 0

        for dialogue_node in available_dialogues:
            available, reason = ReputationThresholdValidator.check_dialogue_available(
                player, npc_id, dialogue_node
            )
            dialogue_status[dialogue_node] = {
                "available": available,
                "locked_reason": reason,
            }
            if available:
                unlocked_count += 1

        return {
            "npc_id": npc_id,
            "current_reputation": reputation,
            "total_dialogues": len(available_dialogues),
            "unlocked_dialogues": unlocked_count,
            "locked_dialogues": len(available_dialogues) - unlocked_count,
            "dialogue_status": dialogue_status,
        }

    @staticmethod
    def serialize_quest_locks(
        player: "Player",
        npc_id: str,
        available_quests: List[Tuple[str, str]],  # (quest_id, quest_type)
    ) -> Dict[str, Any]:
        """Serialize which quests are locked/unlocked.

        Args:
            player: Player object
            npc_id: NPC identifier
            available_quests: List of (quest_id, quest_type) tuples

        Returns:
            Lock status for each quest
        """
        reputation = getattr(player, "reputation", {}).get(npc_id, 0)

        quest_status = {}
        unlocked_count = 0

        for quest_id, quest_type in available_quests:
            available, reason = ReputationThresholdValidator.check_quest_available(
                player, npc_id, quest_type
            )
            quest_status[quest_id] = {
                "available": available,
                "required_reputation": ReputationThresholdValidator.QUEST_THRESHOLDS.get(
                    quest_type, 0
                ),
                "current_reputation": reputation,
                "locked_reason": reason,
            }
            if available:
                unlocked_count += 1

        return {
            "npc_id": npc_id,
            "current_reputation": reputation,
            "total_quests": len(available_quests),
            "unlocked_quests": unlocked_count,
            "locked_quests": len(available_quests) - unlocked_count,
            "quest_status": quest_status,
        }
