"""Tests for debug manager (Phase 2.6)."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.debug_manager import DebugManager, DebugValidator  # type: ignore
from src.config_manager import GameConfig  # type: ignore
from src.player import Player  # type: ignore


def test_debug_manager_debug_mode_disabled_default():
    """Test debug mode is disabled by default."""
    player = Player()
    debug_mgr = DebugManager(player)
    
    assert debug_mgr.is_debug_mode_enabled() is False


def test_debug_manager_debug_mode_enabled_from_config():
    """Test debug mode enabled from GameConfig."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    assert debug_mgr.is_debug_mode_enabled() is True


def test_debug_manager_should_debug_positions_default():
    """Test position debug disabled by default."""
    player = Player()
    debug_mgr = DebugManager(player)
    
    assert debug_mgr.should_debug_positions() is False


def test_debug_manager_should_debug_positions_enabled():
    """Test position debug from config."""
    player = Player()
    config = GameConfig()
    config.debug_positions = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    assert debug_mgr.should_debug_positions() is True


def test_debug_manager_should_debug_movement_enabled():
    """Test movement debug from config."""
    player = Player()
    config = GameConfig()
    config.debug_movement = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    assert debug_mgr.should_debug_movement() is True


def test_debug_manager_should_debug_damage_calc_enabled():
    """Test damage calc debug from config."""
    player = Player()
    config = GameConfig()
    config.debug_damage_calc = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    assert debug_mgr.should_debug_damage_calc() is True


def test_debug_manager_should_debug_accuracy_enabled():
    """Test accuracy debug from config."""
    player = Player()
    config = GameConfig()
    config.debug_accuracy = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    assert debug_mgr.should_debug_accuracy() is True


def test_debug_manager_should_debug_ai_decisions_enabled():
    """Test AI decision debug from config."""
    player = Player()
    config = GameConfig()
    config.debug_ai_decisions = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    assert debug_mgr.should_debug_ai_decisions() is True


def test_debug_manager_should_debug_npc_positions_enabled():
    """Test NPC position debug from config."""
    player = Player()
    config = GameConfig()
    config.debug_npc_positions = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    assert debug_mgr.should_debug_npc_positions() is True


def test_debug_manager_log_command():
    """Test logging a command."""
    player = Player()
    debug_mgr = DebugManager(player)
    
    debug_mgr.log_command('test_cmd', ['arg1'], 'result1')
    
    history = debug_mgr.get_command_history(10)
    assert len(history) == 1
    assert history[0]['command'] == 'test_cmd'
    assert history[0]['args'] == ['arg1']
    assert history[0]['result'] == 'result1'


def test_debug_manager_command_history_max_size():
    """Test command history respects max size."""
    player = Player()
    debug_mgr = DebugManager(player)
    debug_mgr.max_history = 5
    
    # Log more than max
    for i in range(10):
        debug_mgr.log_command(f'cmd{i}')
    
    history = debug_mgr.get_command_history(100)
    assert len(history) == 5


def test_debug_manager_get_command_history():
    """Test retrieving command history."""
    player = Player()
    debug_mgr = DebugManager(player)
    
    for i in range(5):
        debug_mgr.log_command(f'cmd{i}')
    
    history = debug_mgr.get_command_history(3)
    assert len(history) == 3


def test_debug_manager_cmd_instant_win_disabled():
    """Test instant_win command when debug disabled."""
    player = Player()
    config = GameConfig()
    config.debug_mode = False
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_instant_win()
    assert "disabled" in result.lower()


def test_debug_manager_cmd_instant_win_enabled():
    """Test instant_win command when debug enabled."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_instant_win()
    assert "victory" in result.lower()


def test_debug_manager_cmd_spawn_enemy():
    """Test spawn_enemy command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_spawn_enemy("Slime", 3)
    assert "Spawned" in result
    assert "Slime" in result


def test_debug_manager_cmd_damage_output_disabled():
    """Test damage_output when debug disabled."""
    player = Player()
    config = GameConfig()
    config.debug_mode = False
    config.debug_damage_calc = False
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_damage_output("Attacker", "Target")
    assert "disabled" in result.lower()


def test_debug_manager_cmd_damage_output_enabled():
    """Test damage_output when debug enabled."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    config.debug_damage_calc = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_damage_output("Attacker", "Target")
    assert "Damage Calculation" in result
    assert "Attacker" in result


def test_debug_manager_cmd_accuracy_info():
    """Test accuracy_info command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    config.debug_accuracy = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_accuracy_info("Archer", "Enemy")
    assert "Accuracy" in result
    assert "Archer" in result


def test_debug_manager_cmd_npc_decision_trace():
    """Test npc_decision_trace command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    config.debug_ai_decisions = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_npc_decision_trace("Goblin")
    assert "Decision Trace" in result
    assert "Goblin" in result


def test_debug_manager_cmd_performance_monitor():
    """Test performance_monitor command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_performance_monitor()
    assert "Performance" in result


def test_debug_manager_cmd_toggle_feature():
    """Test toggle_feature command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_toggle_feature("debug_positions")
    assert "Toggled" in result
    assert "debug_positions" in result


def test_debug_manager_cmd_toggle_feature_invalid():
    """Test toggle_feature with invalid feature."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_toggle_feature("invalid_feature")
    assert "Unknown" in result


def test_debug_manager_cmd_spawn_item():
    """Test spawn_item command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_spawn_item("Potion", 5)
    assert "Spawned" in result
    assert "Potion" in result


def test_debug_manager_cmd_list_stats():
    """Test list_stats command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_list_stats()
    assert "Stats for Player" in result


def test_debug_manager_cmd_list_stats_for_npc():
    """Test list_stats command for specific NPC."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.cmd_list_stats("Goblin")
    assert "Stats for Goblin" in result


def test_debug_manager_execute_command_debug_disabled():
    """Test executing command when debug disabled."""
    player = Player()
    config = GameConfig()
    config.debug_mode = False
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.execute_command("list_stats")
    assert "disabled" in result.lower()


def test_debug_manager_execute_command_unknown():
    """Test executing unknown command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.execute_command("unknown_cmd")
    assert "Unknown" in result


def test_debug_manager_execute_command_valid():
    """Test executing valid command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    result = debug_mgr.execute_command("list_stats")
    assert "Stats" in result


def test_debug_manager_get_available_commands():
    """Test getting available commands."""
    player = Player()
    debug_mgr = DebugManager(player)
    
    commands = debug_mgr.get_available_commands()
    assert len(commands) >= 9
    assert "instant_win" in commands
    assert "spawn_enemy" in commands
    assert "damage_output" in commands
    assert "accuracy_info" in commands
    assert "npc_decision_trace" in commands
    assert "performance_monitor" in commands
    assert "toggle_feature" in commands
    assert "spawn_item" in commands
    assert "list_stats" in commands


def test_debug_manager_get_debug_info_string():
    """Test debug info string generation."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    config.debug_positions = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    
    info = debug_mgr.get_debug_info_string()
    assert "Debug Manager Status" in info
    assert "Overall Debug Mode: True" in info
    assert "Debug Positions: True" in info


def test_debug_validator_initialization():
    """Test DebugValidator initialization."""
    player = Player()
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    assert validator.debug_manager is debug_mgr


def test_debug_validator_is_valid_command_debug_disabled():
    """Test command validation when debug disabled."""
    player = Player()
    config = GameConfig()
    config.debug_mode = False
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    is_valid, reason = validator.is_valid_command("list_stats")
    assert is_valid is False
    assert "disabled" in reason.lower()


def test_debug_validator_is_valid_command_unknown():
    """Test command validation for unknown command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    is_valid, reason = validator.is_valid_command("unknown_cmd")
    assert is_valid is False
    assert "Unknown" in reason


def test_debug_validator_is_valid_command_known():
    """Test command validation for known command."""
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    player.game_config = config
    
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    is_valid, reason = validator.is_valid_command("list_stats")
    assert is_valid is True


def test_debug_validator_is_valid_spawn_count_positive():
    """Test spawn count validation for positive count."""
    player = Player()
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    is_valid, reason = validator.is_valid_spawn_count(5)
    assert is_valid is True


def test_debug_validator_is_valid_spawn_count_zero():
    """Test spawn count validation for zero."""
    player = Player()
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    is_valid, reason = validator.is_valid_spawn_count(0)
    assert is_valid is False


def test_debug_validator_is_valid_spawn_count_negative():
    """Test spawn count validation for negative."""
    player = Player()
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    is_valid, reason = validator.is_valid_spawn_count(-1)
    assert is_valid is False


def test_debug_validator_is_valid_spawn_count_too_high():
    """Test spawn count validation for too high."""
    player = Player()
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    is_valid, reason = validator.is_valid_spawn_count(1000)
    assert is_valid is False


def test_debug_validator_is_valid_feature_name_valid():
    """Test feature name validation for valid feature."""
    player = Player()
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    is_valid, reason = validator.is_valid_feature_name("debug_positions")
    assert is_valid is True


def test_debug_validator_is_valid_feature_name_invalid():
    """Test feature name validation for invalid feature."""
    player = Player()
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    is_valid, reason = validator.is_valid_feature_name("invalid_feature")
    assert is_valid is False


def test_debug_validator_validate_all_commands():
    """Test all commands are valid."""
    player = Player()
    debug_mgr = DebugManager(player)
    validator = DebugValidator(debug_mgr)
    
    all_valid, issues = validator.validate_all_commands()
    assert all_valid is True
    assert len(issues) == 0
