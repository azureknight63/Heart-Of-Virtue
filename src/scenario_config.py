"""Scenario Configuration for Phase 2.5.

Manages combat scenario selection, rotation, and difficulty progression based on config.
Provides framework for dynamic scenario management and difficulty scaling.
"""

from typing import List, Tuple, Optional
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
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.enable_scenario_rotation
        return False
    
    def get_current_scenario(self) -> str:
        """Get the current scenario to use.
        
        Returns:
            Scenario name (standard, pincer, melee, boss_arena)
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.current_scenario
        return "standard"
    
    def get_test_scenario(self) -> str:
        """Get the test scenario override if configured.
        
        Returns:
            Test scenario name or empty string if not set
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            scenario = self.player.game_config.test_scenario
            if scenario and scenario != "standard":  # If overridden
                return scenario
        return ""
    
    def get_starting_difficulty(self) -> int:
        """Get starting difficulty level.
        
        Returns:
            Starting difficulty (typically 1-5 or 1-10 scale)
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.starting_difficulty
        return 3
    
    def get_difficulty_scaling_factor(self) -> float:
        """Get difficulty scaling multiplier.
        
        Returns:
            Scaling factor (default 0.5, multiply by per-combat increment)
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.difficulty_scaling
        return 0.5
    
    def get_max_rounds_before_auto_victory(self) -> int:
        """Get max rounds before auto-victory trigger.
        
        Returns:
            Maximum round count (default 50)
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
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
        self.current_rotation_index = (self.current_rotation_index + 1) % len(self.scenario_order)
        new_scenario = self.scenario_order[self.current_rotation_index]
        
        # Update config if writable
        if hasattr(self.player, 'game_config') and self.player.game_config:
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


class DifficultyProgressionManager:
    """Manages difficulty progression and scaling."""
    
    def __init__(self, scenario_config: ScenarioConfig):
        """Initialize with scenario config.
        
        Args:
            scenario_config: ScenarioConfig instance
        """
        self.scenario_config = scenario_config
    
    def get_difficulty_multiplier(self) -> float:
        """Get current difficulty as a multiplier (e.g., 1.0 = normal, 1.5 = hard).
        
        Returns:
            Difficulty multiplier
        """
        current_diff = self.scenario_config.calculate_current_difficulty()
        starting_diff = self.scenario_config.get_starting_difficulty()
        
        if starting_diff <= 0:
            return 1.0
        
        return max(0.5, current_diff / starting_diff)
    
    def apply_difficulty_to_npc_stats(self, npc, stat_name: str, base_value: float) -> float:
        """Apply difficulty scaling to an NPC stat.
        
        Args:
            npc: The NPC to scale
            stat_name: Name of stat being scaled
            base_value: Base value of stat
            
        Returns:
            Scaled value
        """
        multiplier = self.get_difficulty_multiplier()
        
        # Certain stats scale differently
        if stat_name in ['damage', 'maxhp', 'protection']:
            return base_value * multiplier
        elif stat_name in ['speed', 'finesse', 'awareness']:
            # Offensive stats get smaller boost
            return base_value * (1.0 + (multiplier - 1.0) * 0.5)
        else:
            return base_value
    
    def get_enemy_count_by_difficulty(self, difficulty: Optional[float] = None) -> int:
        """Get recommended enemy count for difficulty.
        
        Args:
            difficulty: Difficulty multiplier (uses current if None)
            
        Returns:
            Recommended enemy count (1-8)
        """
        if difficulty is None:
            difficulty = self.get_difficulty_multiplier()
        
        # Scale enemy count: 1.0x = 2 enemies, 1.5x = 3, 2.0x = 4, etc.
        base_count = 2
        count = int(base_count + (difficulty - 1.0) * 2)
        return max(1, min(8, count))
    
    def get_loot_multiplier(self, difficulty: Optional[float] = None) -> float:
        """Get loot drop rate multiplier based on difficulty.
        
        Args:
            difficulty: Difficulty multiplier (uses current if None)
            
        Returns:
            Loot multiplier (default 1.0)
        """
        if difficulty is None:
            difficulty = self.get_difficulty_multiplier()
        
        # Higher difficulty = more loot
        return max(0.5, difficulty)
    
    def get_experience_multiplier(self, difficulty: Optional[float] = None) -> float:
        """Get experience gain multiplier based on difficulty.
        
        Args:
            difficulty: Difficulty multiplier (uses current if None)
            
        Returns:
            Experience multiplier
        """
        if difficulty is None:
            difficulty = self.get_difficulty_multiplier()
        
        # Higher difficulty = more XP
        return difficulty
    
    def increment_difficulty_after_combat(self) -> float:
        """Increment difficulty after successful combat.
        
        Returns:
            New difficulty value
        """
        self.scenario_config.increment_combat_count()
        return self.scenario_config.calculate_current_difficulty()


class ScenarioValidator:
    """Validates scenario configuration and transitions."""
    
    def __init__(self, scenario_config: ScenarioConfig):
        """Initialize with scenario config.
        
        Args:
            scenario_config: ScenarioConfig instance
        """
        self.scenario_config = scenario_config
    
    def is_valid_scenario_transition(self, from_scenario: str, to_scenario: str) -> Tuple[bool, str]:
        """Validate transition between scenarios.
        
        Args:
            from_scenario: Current scenario
            to_scenario: Target scenario
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        if not self.scenario_config.is_scenario_valid(from_scenario):
            return (False, f"Invalid source scenario: {from_scenario}")
        
        if not self.scenario_config.is_scenario_valid(to_scenario):
            return (False, f"Invalid target scenario: {to_scenario}")
        
        return (True, f"Valid transition from {from_scenario} to {to_scenario}")
    
    def is_valid_difficulty_level(self, difficulty: float) -> Tuple[bool, str]:
        """Validate difficulty level.
        
        Args:
            difficulty: Difficulty to validate
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        if difficulty < 0:
            return (False, f"Difficulty cannot be negative: {difficulty}")
        
        if difficulty > 100:
            return (False, f"Difficulty unreasonably high: {difficulty}")
        
        return (True, f"Difficulty level valid: {difficulty}")
    
    def is_valid_round_count(self, round_count: int) -> Tuple[bool, str]:
        """Validate round count.
        
        Args:
            round_count: Round count to validate
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        if round_count < 0:
            return (False, f"Round count cannot be negative: {round_count}")
        
        max_rounds = self.scenario_config.get_max_rounds_before_auto_victory()
        
        if round_count > max_rounds:
            return (False, f"Round count exceeds max: {round_count} > {max_rounds}")
        
        return (True, f"Round count valid: {round_count}")
    
    def validate_all_settings(self) -> Tuple[bool, list]:
        """Validate all scenario configuration settings.
        
        Returns:
            Tuple of (all_valid, list_of_issues)
        """
        issues = []
        
        # Check current scenario
        current = self.scenario_config.get_current_scenario()
        if not self.scenario_config.is_scenario_valid(current):
            issues.append(f"Invalid current scenario: {current}")
        
        # Check test scenario
        test = self.scenario_config.get_test_scenario()
        if test and not self.scenario_config.is_scenario_valid(test):
            issues.append(f"Invalid test scenario: {test}")
        
        # Check difficulty
        starting_diff = self.scenario_config.get_starting_difficulty()
        if starting_diff < 0:
            issues.append(f"Starting difficulty cannot be negative: {starting_diff}")
        
        # Check scaling
        scaling = self.scenario_config.get_difficulty_scaling_factor()
        if scaling < 0:
            issues.append(f"Difficulty scaling cannot be negative: {scaling}")
        
        # Check max rounds
        max_rounds = self.scenario_config.get_max_rounds_before_auto_victory()
        if max_rounds < 1:
            issues.append(f"Max rounds must be at least 1: {max_rounds}")
        
        return (len(issues) == 0, issues)
