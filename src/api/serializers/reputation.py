"""
Reputation system serializers.

Serializes the player's per-NPC reputation (`player.reputation`, keyed by
NPC display name) into the attitude/trust badge consumed by the npc-chat
relationship display and the shop price modifiers.
"""

from typing import Dict, Any


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

        `player.reputation` is keyed by the NPC's actual display name
        (`self.name` on the NPC instance, per `HumanNPCLLMMixin`), not a
        separate slug, so the id passed in already is the name.

        Args:
            npc_id: NPC identifier (== NPC display name)

        Returns:
            NPC display name
        """
        return npc_id

    # Max swing applied to a merchant's buy/sell modifier at +/-100 reputation.
    REPUTATION_PRICE_SWING = 0.15

    @staticmethod
    def get_price_modifier(reputation: int) -> float:
        """Reputation-scaled multiplier applied to a merchant's price modifiers.

        Friendly merchants (positive reputation) charge less to buy and pay
        more to sell; hostile merchants do the opposite. Scales linearly to a
        +/-15% swing at the +/-100 reputation extremes.

        Args:
            reputation: Reputation score (-100 to +100)

        Returns:
            Discount fraction in [-0.15, 0.15] — positive means favorable to
            the player. Apply as `buy_modifier * (1 - modifier)` and
            `sell_modifier * (1 + modifier)`.
        """
        return (reputation / 100.0) * NPCRelationshipSerializer.REPUTATION_PRICE_SWING
