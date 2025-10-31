"""Tests for scenario configuration (Phase 2.5)."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.scenario_config import ScenarioConfig, DifficultyProgressionManager, ScenarioValidator  # type: ignore
from src.config_manager import GameConfig  # type: ignore
from src.player import Player  # type: ignore


def test_scenario_config_rotation_disabled_default():
    """Test scenario rotation is disabled by default."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.is_scenario_rotation_enabled() is False


def test_scenario_config_rotation_enabled_from_config():
    """Test scenario rotation enabled from GameConfig."""
    player = Player()
    config = GameConfig()
    config.enable_scenario_rotation = True
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.is_scenario_rotation_enabled() is True


def test_scenario_config_current_scenario_default():
    """Test default current scenario."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_current_scenario() == "standard"


def test_scenario_config_current_scenario_from_config():
    """Test current scenario from GameConfig."""
    player = Player()
    config = GameConfig()
    config.current_scenario = "boss_arena"
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_current_scenario() == "boss_arena"


def test_scenario_config_test_scenario_default():
    """Test default test scenario returns empty."""
    player = Player()
    config = GameConfig()
    config.test_scenario = "standard"
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_test_scenario() == ""


def test_scenario_config_test_scenario_override():
    """Test test scenario override."""
    player = Player()
    config = GameConfig()
    config.test_scenario = "melee"
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_test_scenario() == "melee"


def test_scenario_config_starting_difficulty_default():
    """Test default starting difficulty."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_starting_difficulty() == 3


def test_scenario_config_starting_difficulty_from_config():
    """Test starting difficulty from GameConfig."""
    player = Player()
    config = GameConfig()
    config.starting_difficulty = 5
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_starting_difficulty() == 5


def test_scenario_config_difficulty_scaling_default():
    """Test default difficulty scaling."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_difficulty_scaling_factor() == 0.5


def test_scenario_config_difficulty_scaling_from_config():
    """Test difficulty scaling from GameConfig."""
    player = Player()
    config = GameConfig()
    config.difficulty_scaling = 0.75
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_difficulty_scaling_factor() == 0.75


def test_scenario_config_max_rounds_default():
    """Test default max rounds."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_max_rounds_before_auto_victory() == 50


def test_scenario_config_max_rounds_from_config():
    """Test max rounds from GameConfig."""
    player = Player()
    config = GameConfig()
    config.max_rounds_before_auto_victory = 100
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_max_rounds_before_auto_victory() == 100


def test_scenario_config_get_next_scenario():
    """Test getting next scenario in rotation."""
    player = Player()
    config = GameConfig()
    config.enable_scenario_rotation = True
    config.current_scenario = "standard"
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    next_scenario = scenario_config.get_next_scenario()
    assert next_scenario == "pincer"


def test_scenario_config_advance_scenario_rotation_disabled():
    """Test advancing scenario when rotation is disabled."""
    player = Player()
    config = GameConfig()
    config.enable_scenario_rotation = False
    config.current_scenario = "standard"
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    # Should return current scenario, not advance
    new_scenario = scenario_config.advance_scenario()
    assert new_scenario == "standard"


def test_scenario_config_advance_scenario_rotation_enabled():
    """Test advancing scenario when rotation is enabled."""
    player = Player()
    config = GameConfig()
    config.enable_scenario_rotation = True
    config.current_scenario = "standard"
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    new_scenario = scenario_config.advance_scenario()
    assert new_scenario == "pincer"
    
    # Advance through all remaining scenarios: melee, boss_arena, standard
    scenario_config.advance_scenario()  # melee
    scenario_config.advance_scenario()  # boss_arena
    final_scenario = scenario_config.advance_scenario()  # wraps back to standard
    assert final_scenario == "standard"


def test_scenario_config_calculate_current_difficulty_at_start():
    """Test difficulty calculation at start."""
    player = Player()
    config = GameConfig()
    config.starting_difficulty = 3
    config.difficulty_scaling = 0.5
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    difficulty = scenario_config.calculate_current_difficulty()
    assert difficulty == 3.0


def test_scenario_config_calculate_current_difficulty_after_combats():
    """Test difficulty calculation after multiple combats."""
    player = Player()
    config = GameConfig()
    config.starting_difficulty = 3
    config.difficulty_scaling = 0.5
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    # Simulate 4 combats
    for i in range(4):
        scenario_config.increment_combat_count()
    
    # Difficulty should be 3 + (4 * 0.5) = 5.0
    difficulty = scenario_config.calculate_current_difficulty()
    assert difficulty == 5.0


def test_scenario_config_increment_combat_count():
    """Test incrementing combat counter."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.get_combat_count() == 0
    
    count = scenario_config.increment_combat_count()
    assert count == 1
    assert scenario_config.get_combat_count() == 1


def test_scenario_config_reset_combat_count():
    """Test resetting combat counter."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    
    scenario_config.increment_combat_count()
    scenario_config.increment_combat_count()
    assert scenario_config.get_combat_count() == 2
    
    scenario_config.reset_combat_count()
    assert scenario_config.get_combat_count() == 0


def test_scenario_config_is_scenario_valid():
    """Test scenario validity check."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.is_scenario_valid("standard") is True
    assert scenario_config.is_scenario_valid("pincer") is True
    assert scenario_config.is_scenario_valid("melee") is True
    assert scenario_config.is_scenario_valid("boss_arena") is True
    assert scenario_config.is_scenario_valid("invalid") is False


def test_scenario_config_should_auto_victory_trigger_below_max():
    """Test auto-victory doesn't trigger below max rounds."""
    player = Player()
    config = GameConfig()
    config.max_rounds_before_auto_victory = 50
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.should_auto_victory_trigger(49) is False


def test_scenario_config_should_auto_victory_trigger_at_max():
    """Test auto-victory triggers at max rounds."""
    player = Player()
    config = GameConfig()
    config.max_rounds_before_auto_victory = 50
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    assert scenario_config.should_auto_victory_trigger(50) is True


def test_scenario_config_get_scenario_info_string():
    """Test scenario info string generation."""
    player = Player()
    config = GameConfig()
    config.enable_scenario_rotation = True
    config.current_scenario = "pincer"
    config.starting_difficulty = 3
    config.difficulty_scaling = 0.5
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    
    info = scenario_config.get_scenario_info_string()
    assert "Scenario Configuration" in info
    assert "pincer" in info
    assert "Rotation Enabled: True" in info


def test_scenario_config_get_all_scenarios():
    """Test getting all available scenarios."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    
    scenarios = scenario_config.get_all_scenarios()
    assert len(scenarios) == 4
    assert "standard" in scenarios
    assert "pincer" in scenarios
    assert "melee" in scenarios
    assert "boss_arena" in scenarios


def test_difficulty_progression_manager_get_difficulty_multiplier_at_baseline():
    """Test difficulty multiplier at baseline."""
    player = Player()
    config = GameConfig()
    config.starting_difficulty = 3
    config.difficulty_scaling = 0.5
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    progression = DifficultyProgressionManager(scenario_config)
    
    multiplier = progression.get_difficulty_multiplier()
    assert abs(multiplier - 1.0) < 0.001


def test_difficulty_progression_manager_get_difficulty_multiplier_increased():
    """Test difficulty multiplier after combat."""
    player = Player()
    config = GameConfig()
    config.starting_difficulty = 3
    config.difficulty_scaling = 0.5
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    scenario_config.increment_combat_count()
    
    progression = DifficultyProgressionManager(scenario_config)
    multiplier = progression.get_difficulty_multiplier()
    # 3 + 0.5 = 3.5, so 3.5/3 = 1.166...
    assert multiplier > 1.0


def test_difficulty_progression_manager_apply_difficulty_to_npc_stats_damage():
    """Test applying difficulty to damage stat."""
    player = Player()
    config = GameConfig()
    config.starting_difficulty = 3
    config.difficulty_scaling = 1.0
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    scenario_config.increment_combat_count()  # Difficulty becomes 4
    
    progression = DifficultyProgressionManager(scenario_config)
    
    scaled_damage = progression.apply_difficulty_to_npc_stats(None, 'damage', 10.0)
    # Multiplier should be 4/3 = 1.333...
    expected = 10.0 * (4.0 / 3.0)
    assert abs(scaled_damage - expected) < 0.01


def test_difficulty_progression_manager_get_enemy_count_by_difficulty():
    """Test enemy count scales with difficulty."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    progression = DifficultyProgressionManager(scenario_config)
    
    # At baseline (1.0x)
    count = progression.get_enemy_count_by_difficulty(1.0)
    assert count == 2
    
    # At 1.5x difficulty
    count = progression.get_enemy_count_by_difficulty(1.5)
    assert count == 3
    
    # At 2.0x difficulty
    count = progression.get_enemy_count_by_difficulty(2.0)
    assert count == 4


def test_difficulty_progression_manager_get_loot_multiplier():
    """Test loot multiplier scales with difficulty."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    progression = DifficultyProgressionManager(scenario_config)
    
    # At baseline
    multiplier = progression.get_loot_multiplier(1.0)
    assert abs(multiplier - 1.0) < 0.001
    
    # At higher difficulty
    multiplier = progression.get_loot_multiplier(2.0)
    assert multiplier == 2.0


def test_difficulty_progression_manager_get_experience_multiplier():
    """Test experience multiplier scales with difficulty."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    progression = DifficultyProgressionManager(scenario_config)
    
    # At baseline
    multiplier = progression.get_experience_multiplier(1.0)
    assert abs(multiplier - 1.0) < 0.001
    
    # At higher difficulty
    multiplier = progression.get_experience_multiplier(1.5)
    assert abs(multiplier - 1.5) < 0.001


def test_difficulty_progression_manager_increment_difficulty_after_combat():
    """Test incrementing difficulty after combat."""
    player = Player()
    config = GameConfig()
    config.starting_difficulty = 3
    config.difficulty_scaling = 0.5
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    progression = DifficultyProgressionManager(scenario_config)
    
    # Initial
    assert scenario_config.get_combat_count() == 0
    
    # After increment
    new_diff = progression.increment_difficulty_after_combat()
    assert scenario_config.get_combat_count() == 1
    assert new_diff == 3.5  # 3 + (1 * 0.5)


def test_scenario_validator_is_valid_scenario_transition():
    """Test scenario transition validation."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    validator = ScenarioValidator(scenario_config)
    
    # Valid transition
    is_valid, reason = validator.is_valid_scenario_transition("standard", "pincer")
    assert is_valid is True
    
    # Invalid source
    is_valid, reason = validator.is_valid_scenario_transition("invalid", "pincer")
    assert is_valid is False


def test_scenario_validator_is_valid_difficulty_level():
    """Test difficulty level validation."""
    player = Player()
    scenario_config = ScenarioConfig(player)
    validator = ScenarioValidator(scenario_config)
    
    # Valid difficulty
    is_valid, reason = validator.is_valid_difficulty_level(5.0)
    assert is_valid is True
    
    # Negative difficulty
    is_valid, reason = validator.is_valid_difficulty_level(-1.0)
    assert is_valid is False
    
    # Too high difficulty
    is_valid, reason = validator.is_valid_difficulty_level(150.0)
    assert is_valid is False


def test_scenario_validator_is_valid_round_count():
    """Test round count validation."""
    player = Player()
    config = GameConfig()
    config.max_rounds_before_auto_victory = 50
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    validator = ScenarioValidator(scenario_config)
    
    # Valid round count
    is_valid, reason = validator.is_valid_round_count(25)
    assert is_valid is True
    
    # At max
    is_valid, reason = validator.is_valid_round_count(50)
    assert is_valid is True
    
    # Negative
    is_valid, reason = validator.is_valid_round_count(-1)
    assert is_valid is False
    
    # Over max
    is_valid, reason = validator.is_valid_round_count(100)
    assert is_valid is False


def test_scenario_validator_validate_all_settings_valid():
    """Test all settings validation with valid config."""
    player = Player()
    config = GameConfig()
    config.current_scenario = "standard"
    config.test_scenario = "melee"
    config.starting_difficulty = 3
    config.difficulty_scaling = 0.5
    config.max_rounds_before_auto_victory = 50
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    validator = ScenarioValidator(scenario_config)
    
    all_valid, issues = validator.validate_all_settings()
    assert all_valid is True
    assert len(issues) == 0


def test_scenario_validator_validate_all_settings_invalid_scenario():
    """Test all settings validation with invalid scenario."""
    player = Player()
    config = GameConfig()
    config.current_scenario = "invalid_scenario"
    config.starting_difficulty = 3
    config.difficulty_scaling = 0.5
    config.max_rounds_before_auto_victory = 50
    player.game_config = config
    
    scenario_config = ScenarioConfig(player)
    validator = ScenarioValidator(scenario_config)
    
    all_valid, issues = validator.validate_all_settings()
    assert all_valid is False
    assert any("scenario" in issue.lower() for issue in issues)
