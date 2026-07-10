"""Scenario Configuration for Phase 2.5.

Manages combat scenario selection, rotation, and difficulty progression based on config.
Provides framework for dynamic scenario management and difficulty scaling.
"""

from typing import List
from enum import Enum


class ScenarioType(Enum):
    """Enumeration of available combat scenarios."""

    STANDARD = "standard"
    PINCER = "pincer"
    MELEE = "melee"
    BOSS_ARENA = "boss_arena"


class ScenarioConfig:
    """Manages scenario configuration from GameConfig."""

    # Valid scenario names
    VALID_SCENARIOS = ["standard", "pincer", "melee", "boss_arena"]

    def __init__(self, player):
        """Initialize with player reference for accessing config.

        Args:
            player: Player object with game_config
        """
        self.player = player
        self.scenario_order = ["standard", "pincer", "melee", "boss_arena"]
        self.current_rotation_index = 0
        self.combat_count = 0
        self.current_difficulty = 3  # Default starting difficulty

    def is_scenario_rotation_enabled(self) -> bool:
        """Check if scenario rotation is enabled.

        Returns:
            True if rotation is enabled, False otherwise
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.enable_scenario_rotation
        return False

    def get_current_scenario(self) -> str:
        """Get the current scenario to use.

        Returns:
            Scenario name (standard, pincer, melee, boss_arena)
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.current_scenario
        return "standard"

    def get_test_scenario(self) -> str:
        """Get the test scenario override if configured.

        Returns:
            Test scenario name or empty string if not set
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            scenario = self.player.game_config.test_scenario
            if scenario and scenario != "standard":  # If overridden
                return scenario
        return ""

    def get_starting_difficulty(self) -> int:
        """Get starting difficulty level.

        Returns:
            Starting difficulty (typically 1-5 or 1-10 scale)
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.starting_difficulty
        return 3

    def get_difficulty_scaling_factor(self) -> float:
        """Get difficulty scaling multiplier.

        Returns:
            Scaling factor (default 0.5, multiply by per-combat increment)
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.difficulty_scaling
        return 0.5

    def get_max_rounds_before_auto_victory(self) -> int:
        """Get max rounds before auto-victory trigger.

        Returns:
            Maximum round count (default 50)
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.max_rounds_before_auto_victory
        return 50

    def get_next_scenario(self) -> str:
        """Get the next scenario in rotation.

        Returns:
            Next scenario name
        """
        if not self.is_scenario_rotation_enabled():
            return self.get_current_scenario()

        # Advance to next scenario in rotation
        next_index = (self.current_rotation_index + 1) % len(self.scenario_order)
        return self.scenario_order[next_index]

    def advance_scenario(self) -> str:
        """Advance to next scenario in rotation and return new scenario.

        Returns:
            New scenario name
        """
        if not self.is_scenario_rotation_enabled():
            return self.get_current_scenario()

        # Increment rotation index
        self.current_rotation_index = (self.current_rotation_index + 1) % len(
            self.scenario_order
        )
        new_scenario = self.scenario_order[self.current_rotation_index]

        # Update config if writable
        if hasattr(self.player, "game_config") and self.player.game_config:
            self.player.game_config.current_scenario = new_scenario

        return new_scenario

    def calculate_current_difficulty(self) -> float:
        """Calculate current difficulty based on combat count and scaling.

        Formula: starting_difficulty + (combat_count * difficulty_scaling)

        Returns:
            Current difficulty as float
        """
        starting = self.get_starting_difficulty()
        scaling = self.get_difficulty_scaling_factor()

        current = starting + (self.combat_count * scaling)
        return current

    def increment_combat_count(self) -> int:
        """Increment combat counter for difficulty progression.

        Returns:
            New combat count
        """
        self.combat_count += 1
        return self.combat_count

    def reset_combat_count(self) -> None:
        """Reset combat counter (for testing or scenario reset)."""
        self.combat_count = 0

    def get_combat_count(self) -> int:
        """Get current combat count.

        Returns:
            Number of combats completed in this rotation
        """
        return self.combat_count

    def is_scenario_valid(self, scenario_name: str) -> bool:
        """Check if scenario name is valid.

        Args:
            scenario_name: Scenario to validate

        Returns:
            True if valid scenario, False otherwise
        """
        return scenario_name.lower() in self.VALID_SCENARIOS

    def should_auto_victory_trigger(self, current_round: int) -> bool:
        """Check if auto-victory should trigger based on round count.

        Args:
            current_round: Current round number in combat

        Returns:
            True if max rounds exceeded, False otherwise
        """
        max_rounds = self.get_max_rounds_before_auto_victory()
        return current_round >= max_rounds

    def get_scenario_info_string(self) -> str:
        """Get human-readable summary of scenario configuration.

        Returns:
            Formatted string with all scenario settings
        """
        rotation_enabled = self.is_scenario_rotation_enabled()
        current_scenario = self.get_current_scenario()
        starting_diff = self.get_starting_difficulty()
        scaling = self.get_difficulty_scaling_factor()
        current_diff = self.calculate_current_difficulty()
        combat_count = self.get_combat_count()
        max_rounds = self.get_max_rounds_before_auto_victory()

        info = (
            f"Scenario Configuration:\n"
            f"  Current Scenario: {current_scenario}\n"
            f"  Rotation Enabled: {rotation_enabled}\n"
            f"  Rotation Index: {self.current_rotation_index}\n"
            f"  Combat Count: {combat_count}\n"
            f"  Starting Difficulty: {starting_diff}\n"
            f"  Current Difficulty: {current_diff:.2f}\n"
            f"  Difficulty Scaling: {scaling}\n"
            f"  Max Rounds Before Auto-Victory: {max_rounds}"
        )
        return info

    def get_all_scenarios(self) -> List[str]:
        """Get list of all available scenarios.

        Returns:
            List of scenario names
        """
        return self.VALID_SCENARIOS.copy()

    def get_scenario_rotation_order(self) -> List[str]:
        """Get the rotation order of scenarios.

        Returns:
            List of scenarios in rotation order
        """
        return self.scenario_order.copy()
