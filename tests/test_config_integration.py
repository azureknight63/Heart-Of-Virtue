"""Integration tests for ConfigManager with Player and Universe."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.config_manager import ConfigManager, GameConfig  # type: ignore
from src.player import Player  # type: ignore
from src.universe import Universe  # type: ignore


def test_config_manager_loads_config_dev_ini_if_exists():
    """Test that ConfigManager loads config_dev.ini if it exists in project root."""
    config_dev_path = ROOT / "config_dev.ini"
    
    if config_dev_path.exists():
        mgr = ConfigManager(str(config_dev_path))
        config = mgr.load()
        
        # Verify config loaded some settings (not all defaults)
        assert isinstance(config, GameConfig)
        # At minimum, check that basic structure is intact
        assert hasattr(config, 'testmode')
        assert hasattr(config, 'coordinate_grid_size')


def test_config_phase4_testing_loads_correctly():
    """Test that config_phase4_testing.ini loads with all sections parsed."""
    config_file = ROOT / "config_phase4_testing.ini"
    
    if not config_file.exists():
        # Skip if file doesn't exist
        return
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify all major sections were parsed
    # [game] section
    assert hasattr(config, 'testmode')
    assert hasattr(config, 'debug_mode')
    assert hasattr(config, 'coordinate_grid_size')
    
    # [development] section
    assert hasattr(config, 'enable_hot_reload')
    assert hasattr(config, 'show_all_items')
    assert hasattr(config, 'god_mode')
    assert hasattr(config, 'skip_combat')
    
    # [combat_testing] section
    assert hasattr(config, 'enable_scenario_rotation')
    assert hasattr(config, 'current_scenario')
    assert hasattr(config, 'npc_flanking_threshold')
    
    # [testing_locations] section
    assert hasattr(config, 'standard_player_x')
    assert hasattr(config, 'standard_player_y')
    assert hasattr(config, 'boss_arena_x')
    assert hasattr(config, 'boss_arena_y')


def test_player_receives_config_attributes():
    """Test that Player instance has config-related attributes."""
    player = Player()
    
    # Verify new attributes exist
    assert hasattr(player, 'testing_mode')
    assert hasattr(player, 'use_colour')
    assert hasattr(player, 'enable_animations')
    assert hasattr(player, 'animation_speed')
    assert hasattr(player, 'game_config')
    
    # Verify default values
    assert player.testing_mode is False
    assert player.use_colour is True
    assert player.enable_animations is True
    assert player.animation_speed == 1.0
    assert player.game_config is None


def test_universe_receives_config_attributes():
    """Test that Universe instance has config-related attributes."""
    player = Player()
    universe = Universe(player)
    
    # Verify new attributes exist
    assert hasattr(universe, 'testing_mode')
    assert hasattr(universe, 'game_config')
    
    # Verify default values
    assert universe.testing_mode is False
    assert universe.game_config is None


def test_player_config_can_be_set_from_gameconfig(tmp_path):
    """Test that Player config attributes can be set from GameConfig."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[game]
testmode = true
use_colour = false
enable_animations = false
animation_speed = 0.5
""")
    
    # Load config
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Create player and apply config
    player = Player()
    player.testing_mode = config.testmode
    player.use_colour = config.use_colour
    player.enable_animations = config.enable_animations
    player.animation_speed = config.animation_speed
    player.game_config = config
    
    # Verify settings applied
    assert player.testing_mode is True
    assert player.use_colour is False
    assert player.enable_animations is False
    assert player.animation_speed == 0.5
    assert player.game_config is not None
    assert player.game_config.testmode is True


def test_universe_config_can_be_set_from_gameconfig(tmp_path):
    """Test that Universe config attributes can be set from GameConfig."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[game]
testmode = true

[combat_testing]
enable_scenario_rotation = true
current_scenario = pincer
""")
    
    # Load config
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Create universe and apply config
    player = Player()
    universe = Universe(player)
    universe.testing_mode = config.testmode
    universe.game_config = config
    
    # Verify settings applied
    assert universe.testing_mode is True
    assert universe.game_config is not None
    assert universe.game_config.enable_scenario_rotation is True
    assert universe.game_config.current_scenario == "pincer"


def test_config_coordinate_grid_size_as_tuple(tmp_path):
    """Test that coordinate_grid_size parses and propagates as tuple."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[game]
coordinate_grid_size = 100, 150
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify tuple parsing
    assert config.coordinate_grid_size == (100, 150)
    assert isinstance(config.coordinate_grid_size, tuple)
    
    # Apply to universe and verify
    player = Player()
    universe = Universe(player)
    universe.game_config = config
    
    # Can access through universe
    assert universe.game_config.coordinate_grid_size == (100, 150)


def test_testing_locations_all_accessible(tmp_path):
    """Test that all testing location coordinates are accessible."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[testing_locations]
standard_player_x = 15
standard_player_y = 5
standard_enemy_x = 15
standard_enemy_y = 45
pincer_player_x = 20
pincer_player_y = 30
pincer_enemy1_x = 5
pincer_enemy1_y = 30
pincer_enemy2_x = 35
pincer_enemy2_y = 30
melee_center_x = 30
melee_center_y = 30
melee_spread_radius = 8
boss_arena_x = 20
boss_arena_y = 20
boss_start_distance = 35
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify all location coordinates loaded
    assert config.standard_player_x == 15
    assert config.standard_player_y == 5
    assert config.standard_enemy_x == 15
    assert config.standard_enemy_y == 45
    assert config.pincer_player_x == 20
    assert config.pincer_player_y == 30
    assert config.pincer_enemy1_x == 5
    assert config.pincer_enemy1_y == 30
    assert config.pincer_enemy2_x == 35
    assert config.pincer_enemy2_y == 30
    assert config.melee_center_x == 30
    assert config.melee_center_y == 30
    assert config.melee_spread_radius == 8
    assert config.boss_arena_x == 20
    assert config.boss_arena_y == 20
    assert config.boss_start_distance == 35


def test_all_debug_flags_accessible(tmp_path):
    """Test that all debug flags are accessible through config."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[game]
debug_mode = true
debug_positions = true
debug_movement = true
debug_damage_calc = true
debug_accuracy = true
debug_ai_decisions = true
debug_npc_positions = true
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify all debug flags loaded
    assert config.debug_mode is True
    assert config.debug_positions is True
    assert config.debug_movement is True
    assert config.debug_damage_calc is True
    assert config.debug_accuracy is True
    assert config.debug_ai_decisions is True
    assert config.debug_npc_positions is True


def test_validation_flags_accessible(tmp_path):
    """Test that validation flags in combat_testing section are accessible."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[combat_testing]
validate_grid_bounds = false
validate_distance_calc = false
validate_angle_calc = false
validate_modifier_calc = false
validate_npc_formations = false
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify all validation flags loaded and can be toggled
    assert config.validate_grid_bounds is False
    assert config.validate_distance_calc is False
    assert config.validate_angle_calc is False
    assert config.validate_modifier_calc is False
    assert config.validate_npc_formations is False


def test_development_settings_all_accessible(tmp_path):
    """Test that all development settings are accessible."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[development]
enable_hot_reload = true
show_all_items = true
god_mode = true
skip_combat = true
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify all development settings
    assert config.enable_hot_reload is True
    assert config.show_all_items is True
    assert config.god_mode is True
    assert config.skip_combat is True
    
    # Ensure they can be applied to player
    player = Player()
    player.game_config = config
    assert player.game_config.god_mode is True


def test_display_settings_all_accessible(tmp_path):
    """Test that all display settings are accessible."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[game]
show_combat_distance = false
show_unit_positions = false
show_facing_directions = false
show_damage_modifiers = false
show_accuracy_modifiers = false
show_coordinate_display = false
show_full_grid = true
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify all display settings
    assert config.show_combat_distance is False
    assert config.show_unit_positions is False
    assert config.show_facing_directions is False
    assert config.show_damage_modifiers is False
    assert config.show_accuracy_modifiers is False
    assert config.show_coordinate_display is False
    assert config.show_full_grid is True


def test_npc_ai_settings_accessible(tmp_path):
    """Test that NPC AI settings are accessible."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[game]
npc_flanking_enabled = false
npc_tactical_retreat = false
ai_difficulty = 7

[combat_testing]
npc_flanking_threshold = 60.0
npc_retreat_health_threshold = 0.5
npc_flanking_distance_range = 15.0 to 50.0
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify NPC AI settings
    assert config.npc_flanking_enabled is False
    assert config.npc_tactical_retreat is False
    assert config.ai_difficulty == 7
    assert config.npc_flanking_threshold == 60.0
    assert config.npc_retreat_health_threshold == 0.5
    assert config.npc_flanking_distance_range == "15.0 to 50.0"


def test_scenario_settings_accessible(tmp_path):
    """Test that scenario settings are accessible."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[game]
test_scenario = pincer
max_enemies_standard = 5
max_enemies_pincer = 8
max_enemies_melee = 10
max_enemies_boss = 2

[combat_testing]
enable_scenario_rotation = true
current_scenario = melee
starting_difficulty = 5
difficulty_scaling = 0.75
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify scenario settings
    assert config.test_scenario == "pincer"
    assert config.max_enemies_standard == 5
    assert config.max_enemies_pincer == 8
    assert config.max_enemies_melee == 10
    assert config.max_enemies_boss == 2
    assert config.enable_scenario_rotation is True
    assert config.current_scenario == "melee"
    assert config.starting_difficulty == 5
    assert config.difficulty_scaling == 0.75


def test_logging_settings_accessible(tmp_path):
    """Test that logging settings are accessible."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[game]
log_combat_moves = false
log_distance_calculations = false
log_angle_calculations = false
log_npc_decisions = false
log_file = custom_log.txt
log_performance = true
monitor_bps = true
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify logging settings
    assert config.log_combat_moves is False
    assert config.log_distance_calculations is False
    assert config.log_angle_calculations is False
    assert config.log_npc_decisions is False
    assert config.log_file == "custom_log.txt"
    assert config.log_performance is True
    assert config.monitor_bps is True
