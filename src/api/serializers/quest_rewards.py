"""
Quest rewards serializers for Phase 3: Advanced Features.

Handles serialization of quest rewards (items, gold, XP, reputation)
and reward distribution to players.
"""

from typing import Dict, Any, List, Optional, Tuple
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from player import Player


class QuestRewardSerializer:
    """Serializes quest reward data."""

    @staticmethod
    def serialize_quest_rewards(quest: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize quest rewards.

        Args:
            quest: Quest data dictionary

        Returns:
            Serialized quest rewards
        """
        rewards = quest.get("rewards", {})

        return {
            "quest_id": quest.get("id", "unknown"),
            "quest_title": quest.get("title", "Unknown Quest"),
            "rewards": {
                "gold": rewards.get("gold", 0),
                "experience": rewards.get("experience", 0),
                "items": QuestRewardSerializer._serialize_reward_items(
                    rewards.get("items", [])
                ),
                "reputation": rewards.get("reputation", {}),
            },
            "conditions": {
                "difficulty": rewards.get("difficulty", "normal"),
                "time_limit": rewards.get("time_limit", None),
                "no_deaths": rewards.get("no_deaths", False),
                "bonus_objectives_completed": rewards.get("bonus_complete", False),
            },
        }

    @staticmethod
    def serialize_reward_summary(quest: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize brief reward summary.

        Args:
            quest: Quest data

        Returns:
            Brief reward summary
        """
        rewards = quest.get("rewards", {})

        return {
            "gold": rewards.get("gold", 0),
            "experience": rewards.get("experience", 0),
            "item_count": len(rewards.get("items", [])),
            "has_reputation": len(rewards.get("reputation", {})) > 0,
        }

    @staticmethod
    def _serialize_reward_items(
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Serialize reward items.

        Args:
            items: List of reward items

        Returns:
            Serialized reward items
        """
        return [
            {
                "item_id": item.get("id", "unknown"),
                "item_name": item.get("name", "Unknown Item"),
                "quantity": item.get("quantity", 1),
                "rarity": item.get("rarity", "common"),
                "type": item.get("type", "miscellaneous"),
            }
            for item in items
        ]


class RewardDistributionSerializer:
    """Serializes reward distribution and player updates."""

    @staticmethod
    def serialize_distributed_rewards(
        player: "Player",
        quest_id: str,
        rewards: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Serialize distributed rewards to player.

        Args:
            player: Player object
            quest_id: Quest that was completed
            rewards: Rewards distributed

        Returns:
            Distribution summary with player updates
        """
        return {
            "success": True,
            "quest_id": quest_id,
            "rewards_received": {
                "gold": rewards.get("gold", 0),
                "experience": rewards.get("experience", 0),
                "items_received": rewards.get("items_received", []),
                "reputation_gained": rewards.get("reputation", {}),
            },
            "player_state_after": {
                "gold": getattr(player, "gold", 0),
                "experience": getattr(player, "experience", 0),
                "level": getattr(player, "level", 1),
                "inventory_count": len(getattr(player, "inventory", [])),
                "inventory_weight": getattr(player, "inventory_weight", 0),
            },
        }

    @staticmethod
    def serialize_xp_gain(
        player: "Player",
        xp_gained: int,
        level_up: bool = False,
        old_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Serialize XP gain.

        Args:
            player: Player object
            xp_gained: Amount of XP gained
            level_up: Whether level increased
            old_level: Previous level (optional, defaults to current - 1)

        Returns:
            XP gain details
        """
        current_level = getattr(player, "level", 1)
        if old_level is None:
            old_level = current_level - 1 if level_up else current_level

        return {
            "xp_gained": xp_gained,
            "total_experience": getattr(player, "experience", 0),
            "old_level": old_level,
            "new_level": current_level,
            "current_level": current_level,
            "level_up": level_up,
            "experience_to_next_level": RewardDistributionSerializer._xp_to_next_level(
                player
            ),
        }

    @staticmethod
    def serialize_gold_gain(
        player: "Player",
        gold_gained: int,
    ) -> Dict[str, Any]:
        """Serialize gold gain.

        Args:
            player: Player object
            gold_gained: Amount of gold gained

        Returns:
            Gold gain details
        """
        return {
            "gold_gained": gold_gained,
            "total_gold": getattr(player, "gold", 0),
        }

    @staticmethod
    def serialize_item_reward(
        item_id: str,
        item_name: str,
        quantity: int = 1,
    ) -> Dict[str, Any]:
        """Serialize item reward.

        Args:
            item_id: ID of item
            item_name: Name of item
            quantity: Quantity received

        Returns:
            Item reward details
        """
        return {
            "item_id": item_id,
            "item_name": item_name,
            "quantity": quantity,
            "added_to_inventory": True,
        }

    @staticmethod
    def serialize_reputation_gain(
        npc_id: str,
        npc_name: str,
        reputation_change: int,
    ) -> Dict[str, Any]:
        """Serialize reputation gain.

        Args:
            npc_id: NPC identifier
            npc_name: NPC name
            reputation_change: Change in reputation

        Returns:
            Reputation gain details
        """
        return {
            "npc_id": npc_id,
            "npc_name": npc_name,
            "reputation_change": reputation_change,
            "positive": reputation_change > 0,
        }

    @staticmethod
    def _xp_to_next_level(player: "Player") -> int:
        """Calculate XP needed to next level.

        Args:
            player: Player object

        Returns:
            XP needed for next level (or 0 if max level)
        """
        # Simple formula: level * 100 XP per level
        current_level = getattr(player, "level", 1)
        current_xp = getattr(player, "experience", 0)
        xp_for_level = current_level * 100
        return max(0, xp_for_level - current_xp)


class RewardConditionValidator:
    """Validates reward conditions and applies modifiers."""

    @staticmethod
    def check_reward_conditions(
        player: "Player",
        quest: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Check quest completion conditions and return base + bonus rewards.

        Args:
            player: Player object
            quest: Quest data

        Returns:
            Tuple of (rewards_dict, bonus_messages)
        """
        rewards = quest.get("rewards", {}).copy()
        bonuses = []

        # Check difficulty modifier
        difficulty = quest.get("difficulty", "normal")
        difficulty_multiplier = {
            "easy": 0.5,
            "normal": 1.0,
            "hard": 1.5,
            "nightmare": 2.0,
        }.get(difficulty, 1.0)

        # Apply difficulty multiplier to XP
        rewards["experience"] = int(
            rewards.get("experience", 0) * difficulty_multiplier
        )

        # Check no-death bonus
        if rewards.get("no_deaths", False):
            player_deaths = getattr(player, "death_count", 0)
            if player_deaths == 0:
                xp_bonus = int(rewards.get("experience", 0) * 0.2)
                rewards["experience"] += xp_bonus
                bonuses.append(f"No Death Bonus: +{xp_bonus} XP")

        # Check time limit bonus
        if rewards.get("time_limit"):
            # Assume time_limit is quest completion time in seconds
            # Would need to compare with actual completion time
            # For now, just mark as available
            bonuses.append("Speed Bonus Available: Complete faster for extra rewards")

        # Check bonus objectives
        if rewards.get("bonus_complete", False):
            gold_bonus = int(rewards.get("gold", 0) * 0.25)
            rewards["gold"] += gold_bonus
            bonuses.append(f"Bonus Objectives: +{gold_bonus} Gold")

        return rewards, bonuses

    @staticmethod
    def validate_reward_distribution(
        player: "Player",
        rewards: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Validate that player can receive all rewards.

        Args:
            player: Player object
            rewards: Rewards to distribute

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check inventory space for items
        items = rewards.get("items", [])
        total_items = sum(item.get("quantity", 1) for item in items)

        inventory = getattr(player, "inventory", [])
        max_inventory = getattr(player, "max_inventory", 20)

        if len(inventory) + total_items > max_inventory:
            return (
                False,
                f"Inventory full: need {total_items} slots, have {max_inventory - len(inventory)}",
            )

        # Check reputation recipients exist
        reputation = rewards.get("reputation", {})
        for npc_id in reputation.keys():
            if not npc_id or len(npc_id) == 0:
                return False, f"Invalid NPC ID for reputation: {npc_id}"

        return True, None


class LevelingProgressSerializer:
    """Serializes leveling and progression data."""

    @staticmethod
    def serialize_level_up(
        player: "Player",
        old_level: int,
        new_level: int,
        xp_gained: int,
    ) -> Dict[str, Any]:
        """Serialize level up event.

        Args:
            player: Player object
            old_level: Previous level
            new_level: New level
            xp_gained: XP that triggered level up

        Returns:
            Level up details
        """
        return {
            "level_up": True,
            "old_level": old_level,
            "new_level": new_level,
            "xp_gained": xp_gained,
            "stat_increases": LevelingProgressSerializer._get_stat_increases(
                new_level, old_level
            ),
            "new_skills_unlocked": LevelingProgressSerializer._get_new_skills(
                new_level
            ),
        }

    @staticmethod
    def _get_stat_increases(new_level: int, old_level: int) -> Dict[str, int]:
        """Get stat increases for level up.

        Args:
            new_level: New level
            old_level: Old level

        Returns:
            Dictionary of stat increases
        """
        # Simplified progression: +5 HP, +2 attack per level
        levels_gained = new_level - old_level
        return {
            "hp": 5 * levels_gained,
            "attack": 2 * levels_gained,
            "defense": 1 * levels_gained,
        }

    @staticmethod
    def _get_new_skills(level: int) -> List[str]:
        """Get new skills unlocked at level.

        Args:
            level: New level

        Returns:
            List of new skill names
        """
        skills_by_level = {
            5: ["Power Attack"],
            10: ["Defensive Stance"],
            15: ["Execute"],
            20: ["Heroic Last Stand"],
        }
        return skills_by_level.get(level, [])

    @staticmethod
    def serialize_progression(
        player: "Player",
        quests_completed: int,
    ) -> Dict[str, Any]:
        """Serialize player progression.

        Args:
            player: Player object
            quests_completed: Total quests completed

        Returns:
            Progression data
        """
        return {
            "level": getattr(player, "level", 1),
            "experience": getattr(player, "experience", 0),
            "quests_completed": quests_completed,
            "gold": getattr(player, "gold", 0),
            "playtime_hours": getattr(player, "playtime_hours", 0),
            "achievements_unlocked": len(getattr(player, "achievements", [])),
        }
