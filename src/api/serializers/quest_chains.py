"""
Quest chain system serializers for Phase 3 Stage 3.

Handles serialization of quest chains, dependencies, progression tracking,
and multi-stage storyline management.
"""

from typing import Dict, Any, List, Optional, Tuple
from typing import TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from player import Player


class ChainStatus(Enum):
    """Quest chain status enumeration."""

    LOCKED = "locked"  # Prerequisites not met
    AVAILABLE = "available"  # Can be started
    IN_PROGRESS = "in_progress"  # At least one quest started
    COMPLETED = "completed"  # All quests finished


class QuestChainSerializer:
    """Serializes individual quest chain data."""

    @staticmethod
    def serialize_chain(
        chain_id: str,
        chain_name: str,
        description: str,
        stages: List[Dict[str, Any]],
        status: str = ChainStatus.AVAILABLE.value,
        current_stage: int = 0,
        completion_percentage: int = 0,
    ) -> Dict[str, Any]:
        """Serialize a quest chain.

        Args:
            chain_id: Unique chain identifier
            chain_name: Display name
            description: Chain description/story
            stages: List of quest stages in the chain
            status: Current chain status
            current_stage: Current stage index (0-based)
            completion_percentage: Completion %

        Returns:
            Serialized chain data
        """
        return {
            "chain_id": chain_id,
            "chain_name": chain_name,
            "description": description,
            "status": status,
            "total_stages": len(stages),
            "current_stage": current_stage,
            "completion_percentage": completion_percentage,
            "stages": stages,
            "can_continue": status
            in [
                ChainStatus.AVAILABLE.value,
                ChainStatus.IN_PROGRESS.value,
            ],
            "is_completed": status == ChainStatus.COMPLETED.value,
        }

    @staticmethod
    def serialize_stage(
        stage_index: int,
        stage_name: str,
        quest_id: str,
        description: str,
        status: str,
        rewards: Optional[Dict[str, Any]] = None,
        prerequisites: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Serialize a single stage in a quest chain.

        Args:
            stage_index: 0-based stage number
            stage_name: Stage name
            quest_id: Quest ID for this stage
            description: Stage description
            status: Stage status (locked, available, completed)
            rewards: Optional reward data
            prerequisites: Optional list of prerequisite quest IDs

        Returns:
            Serialized stage data
        """
        return {
            "stage_index": stage_index,
            "stage_name": stage_name,
            "quest_id": quest_id,
            "description": description,
            "status": status,
            "rewards": rewards or {},
            "prerequisites": prerequisites or [],
            "is_locked": status == "locked",
            "is_completed": status == "completed",
        }


class ChainDependencySerializer:
    """Manages and serializes quest chain dependencies."""

    @staticmethod
    def validate_chain_dependencies(
        chain_id: str,
        prerequisites: List[str],
        completed_chains: Dict[str, str],
    ) -> Tuple[bool, Optional[str]]:
        """Validate if a chain's prerequisites are met.

        Args:
            chain_id: Chain to check
            prerequisites: List of required completed chains
            completed_chains: Dict of chain_id -> status

        Returns:
            Tuple of (is_valid, error_message)
        """
        for prereq_chain in prerequisites:
            if (
                completed_chains.get(prereq_chain)
                != ChainStatus.COMPLETED.value
            ):
                return False, f"Chain '{prereq_chain}' must be completed first"

        return True, None

    @staticmethod
    def validate_stage_dependencies(
        stage_index: int,
        stage_prerequisites: List[str],
        completed_quests: List[str],
    ) -> Tuple[bool, Optional[str]]:
        """Validate if a stage's prerequisites are met.

        Args:
            stage_index: Stage number
            stage_prerequisites: List of required quest IDs
            completed_quests: List of completed quest IDs

        Returns:
            Tuple of (is_valid, error_message)
        """
        for prereq_quest in stage_prerequisites:
            if prereq_quest not in completed_quests:
                return (
                    False,
                    f"Stage {stage_index} requires quest '{prereq_quest}'",
                )

        return True, None

    @staticmethod
    def serialize_dependency_graph(
        chains: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Serialize a dependency graph for all chains.

        Args:
            chains: Dict of chain_id -> chain_data

        Returns:
            Dependency graph structure
        """
        graph = {}

        for chain_id, chain_data in chains.items():
            graph[chain_id] = {
                "prerequisites": chain_data.get("prerequisites", []),
                "unlocks": [
                    cid
                    for cid, cd in chains.items()
                    if chain_id in cd.get("prerequisites", [])
                ],
                "can_start": len(chain_data.get("prerequisites", [])) == 0,
            }

        return graph


class ChainProgressionSerializer:
    """Tracks and serializes quest chain progression."""

    @staticmethod
    def get_chain_progress(
        player: "Player",
        chain_id: str,
    ) -> Dict[str, Any]:
        """Get current progress in a quest chain.

        Args:
            player: Player object
            chain_id: Chain ID

        Returns:
            Progress data
        """
        if not hasattr(player, "chain_progress"):
            player.chain_progress = {}

        progress_data = player.chain_progress.get(chain_id, {})
        current_stage = progress_data.get("current_stage", 0)
        completed_stages = progress_data.get("completed_stages", [])

        return {
            "chain_id": chain_id,
            "current_stage": current_stage,
            "completed_stages": completed_stages,
            "total_completed": len(completed_stages),
            "is_active": chain_id in getattr(player, "active_chains", []),
        }

    @staticmethod
    def advance_to_next_stage(
        player: "Player",
        chain_id: str,
        current_stage: int,
        next_stage: int,
    ) -> Dict[str, Any]:
        """Advance player to next stage in a chain.

        Args:
            player: Player object
            chain_id: Chain ID
            current_stage: Current stage index
            next_stage: Next stage index

        Returns:
            Updated progress
        """
        if not hasattr(player, "chain_progress"):
            player.chain_progress = {}

        if chain_id not in player.chain_progress:
            player.chain_progress[chain_id] = {
                "current_stage": 0,
                "completed_stages": [],
            }

        # Mark current stage as completed
        progress = player.chain_progress[chain_id]
        if current_stage not in progress["completed_stages"]:
            progress["completed_stages"].append(current_stage)

        # Advance to next stage
        progress["current_stage"] = next_stage

        return {
            "success": True,
            "chain_id": chain_id,
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "completed_count": len(progress["completed_stages"]),
        }

    @staticmethod
    def complete_chain(
        player: "Player",
        chain_id: str,
    ) -> Dict[str, Any]:
        """Mark a chain as completed.

        Args:
            player: Player object
            chain_id: Chain ID

        Returns:
            Completion data
        """
        if not hasattr(player, "completed_chains"):
            player.completed_chains = {}

        if not hasattr(player, "chain_progress"):
            player.chain_progress = {}

        # Mark chain as completed
        player.completed_chains[chain_id] = {
            "completed_at": "timestamp_here",
            "playtime_seconds": 0,  # Could track actual playtime
        }

        return {
            "success": True,
            "chain_id": chain_id,
            "status": ChainStatus.COMPLETED.value,
        }

    @staticmethod
    def serialize_all_chains_progress(
        player: "Player",
    ) -> Dict[str, Any]:
        """Serialize player's progress in all chains.

        Args:
            player: Player object

        Returns:
            All chain progress data
        """
        if not hasattr(player, "chain_progress"):
            player.chain_progress = {}

        if not hasattr(player, "completed_chains"):
            player.completed_chains = {}

        all_progress = {}
        total_chains = 0
        completed_chains = 0

        for chain_id, progress in player.chain_progress.items():
            all_progress[chain_id] = {
                "status": (
                    ChainStatus.COMPLETED.value
                    if chain_id in player.completed_chains
                    else ChainStatus.IN_PROGRESS.value
                ),
                "current_stage": progress.get("current_stage", 0),
                "completed_stages": len(progress.get("completed_stages", [])),
            }
            total_chains += 1

        for chain_id in player.completed_chains:
            if chain_id not in all_progress:
                all_progress[chain_id] = {
                    "status": ChainStatus.COMPLETED.value,
                }
            completed_chains += 1

        return {
            "total_chains": total_chains,
            "completed_chains": completed_chains,
            "completion_percentage": (
                (completed_chains / total_chains * 100)
                if total_chains > 0
                else 0
            ),
            "chains": all_progress,
        }


class ChainRewardSerializer:
    """Serializes rewards for completing chain stages and full chains."""

    @staticmethod
    def serialize_stage_rewards(
        stage_rewards: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Serialize rewards for a single stage.

        Args:
            stage_rewards: Reward data dict

        Returns:
            Serialized reward data
        """
        return {
            "gold": stage_rewards.get("gold", 0),
            "experience": stage_rewards.get("experience", 0),
            "items": stage_rewards.get("items", []),
            "reputation": stage_rewards.get("reputation", {}),
            "skill_points": stage_rewards.get("skill_points", 0),
            "unlocks": stage_rewards.get(
                "unlocks", []
            ),  # Dialogue, quests, etc.
        }

    @staticmethod
    def serialize_chain_completion_rewards(
        chain_id: str,
        completion_bonus: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Serialize completion bonus for finishing entire chain.

        Args:
            chain_id: Completed chain ID
            completion_bonus: Bonus data

        Returns:
            Serialized completion reward
        """
        return {
            "chain_id": chain_id,
            "bonus_type": completion_bonus.get("bonus_type", "standard"),
            "title_unlocked": completion_bonus.get("title", None),
            "achievement_unlocked": completion_bonus.get("achievement", None),
            "gold_bonus": completion_bonus.get("gold_bonus", 0),
            "experience_bonus": completion_bonus.get("experience_bonus", 0),
            "special_item": completion_bonus.get("special_item", None),
            "story_milestone": completion_bonus.get("story_milestone", None),
        }

    @staticmethod
    def calculate_completion_bonus(
        chain_length: int,
        difficulty: str,
        bonus_objectives_completed: int,
        total_bonus_objectives: int,
    ) -> Dict[str, Any]:
        """Calculate completion bonus based on chain metrics.

        Args:
            chain_length: Number of stages
            difficulty: Chain difficulty (normal, hard, nightmare)
            bonus_objectives_completed: Bonus objectives done
            total_bonus_objectives: Total bonus objectives

        Returns:
            Calculated bonus
        """
        # Base multiplier by difficulty
        difficulty_multipliers = {
            "normal": 1.0,
            "hard": 1.5,
            "nightmare": 2.0,
        }
        multiplier = difficulty_multipliers.get(difficulty, 1.0)

        # Bonus for completing objectives
        objective_bonus = (
            (bonus_objectives_completed / total_bonus_objectives) * 0.5
            if total_bonus_objectives > 0
            else 0
        )

        total_multiplier = (1.0 + objective_bonus) * multiplier

        return {
            "gold_multiplier": total_multiplier,
            "experience_multiplier": total_multiplier,
            "objective_bonus_percentage": objective_bonus * 100,
        }


class ChainBranchSerializer:
    """Handles branching quest chains (multiple paths)."""

    @staticmethod
    def serialize_branch_point(
        chain_id: str,
        branch_stage: int,
        branches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Serialize a branching point in a quest chain.

        Args:
            chain_id: Chain ID
            branch_stage: Stage where branch occurs
            branches: List of available branches

        Returns:
            Branch point data
        """
        return {
            "chain_id": chain_id,
            "branch_stage": branch_stage,
            "total_branches": len(branches),
            "branches": [
                {
                    "branch_id": b.get("id", f"branch_{i}"),
                    "name": b.get("name", f"Branch {i}"),
                    "description": b.get("description", ""),
                    "next_stages": b.get("next_stages", []),
                    "reputation_effects": b.get("reputation_effects", {}),
                    "alignment": b.get("alignment", "neutral"),
                }
                for i, b in enumerate(branches)
            ],
        }

    @staticmethod
    def get_available_branches(
        player: "Player",
        chain_id: str,
        branch_point: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get branches available to player at a branch point.

        Args:
            player: Player object
            chain_id: Chain ID
            branch_point: Branch point data

        Returns:
            Available branches filtered by player state
        """
        available = []

        for branch in branch_point.get("branches", []):
            # Check reputation gates
            reputation_gates = branch.get("reputation_gates", {})
            gates_passed = True

            for npc_id, min_rep in reputation_gates.items():
                player_rep = player.reputation.get(npc_id, 0)
                if player_rep < min_rep:
                    gates_passed = False
                    break

            if gates_passed:
                available.append(branch)

        return available
