"""Basic tests for ConfigManager class."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.config_manager import ConfigManager, GameConfig  # type: ignore


def test_config_manager_creates_default_config():
    """Test that ConfigManager creates defaults with non-existent file."""
    mgr = ConfigManager('nonexistent_config.ini')
    config = mgr.load()
    
    assert isinstance(config, GameConfig)
    assert config.testmode is False
    assert config.debug_mode is False
    assert config.coordinate_grid_size == (50, 50)


def test_config_manager_parses_game_section(tmp_path):
    """Test parsing of [game] section."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[game]
testmode = true
skipdialog = true
skipintro = true
startmap = test_map
startposition = 10, 20
use_colour = false
enable_animations = false
animation_speed = 0.5
debug_mode = true
debug_positions = true
coordinate_grid_size = 100, 100
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    assert config.testmode is True
    assert config.skipdialog is True
    assert config.skipintro is True
    assert config.startmap == "test_map"
    assert config.startposition == (10, 20)
    assert config.use_colour is False
    assert config.enable_animations is False
    assert config.animation_speed == 0.5
    assert config.debug_mode is True
    assert config.debug_positions is True
    assert config.coordinate_grid_size == (100, 100)


def test_config_manager_parses_development_section(tmp_path):
    """Test parsing of [development] section."""
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
    
    assert config.enable_hot_reload is True
    assert config.show_all_items is True
    assert config.god_mode is True
    assert config.skip_combat is True


def test_config_manager_parses_combat_testing_section(tmp_path):
    """Test parsing of [combat_testing] section."""
    config_file = tmp_path / "test.ini"
    config_file.write_text("""
[combat_testing]
enable_scenario_rotation = true
current_scenario = pincer
starting_difficulty = 5
difficulty_scaling = 0.75
max_rounds_before_auto_victory = 100
npc_decision_delay = 1.5
npc_flanking_threshold = 60.0
npc_retreat_health_threshold = 0.5
validate_grid_bounds = false
validate_distance_calc = false
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    assert config.enable_scenario_rotation is True
    assert config.current_scenario == "pincer"
    assert config.starting_difficulty == 5
    assert config.difficulty_scaling == 0.75
    assert config.max_rounds_before_auto_victory == 100
    assert config.npc_decision_delay == 1.5
    assert config.npc_flanking_threshold == 60.0
    assert config.npc_retreat_health_threshold == 0.5
    assert config.validate_grid_bounds is False
    assert config.validate_distance_calc is False


def test_config_manager_parses_testing_locations_section(tmp_path):
    """Test parsing of [testing_locations] section."""
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


def test_config_manager_full_config_file(tmp_path):
    """Test loading complete config_phase4_testing.ini style file."""
    config_file = tmp_path / "full_config.ini"
    config_file.write_text("""
[game]
testmode = false
skipdialog = false
skipintro = false
startmap = default_map
startposition = 25, 25
use_colour = true
enable_animations = true
animation_speed = 1.0
debug_mode = true
debug_positions = true
debug_movement = true
debug_damage_calc = true
debug_accuracy = true
debug_ai_decisions = true
debug_npc_positions = true
coordinate_grid_size = 50, 50
enable_new_combat_moves = true
enable_flanking_mechanics = true
enable_tactical_positioning = true
npc_flanking_enabled = true
npc_tactical_retreat = true
ai_difficulty = 3
autosave_enabled = false
allow_quicksave = true
auto_load_latest = false
show_combat_distance = true
show_unit_positions = true
show_facing_directions = true
show_damage_modifiers = true
show_accuracy_modifiers = true
log_combat_moves = true
log_distance_calculations = true
log_angle_calculations = true
log_npc_decisions = true
log_file = combat_testing_phase4.log
test_scenario = standard
max_enemies_standard = 3
max_enemies_pincer = 4
max_enemies_melee = 6
max_enemies_boss = 1
monitor_bps = false
log_performance = false
show_full_grid = false
grid_display_interval = 1
show_coordinate_display = true

[development]
enable_hot_reload = false
show_all_items = false
god_mode = false
skip_combat = false

[combat_testing]
enable_scenario_rotation = false
current_scenario = standard
starting_difficulty = 3
difficulty_scaling = 0.5
max_rounds_before_auto_victory = 50
npc_decision_delay = 0.5
npc_flanking_threshold = 45.0
npc_retreat_health_threshold = 0.3
npc_flanking_distance_range = 20.0 to 40.0
validate_grid_bounds = true
validate_distance_calc = true
validate_angle_calc = true
validate_modifier_calc = true
validate_npc_formations = true

[testing_locations]
standard_player_x = 25
standard_player_y = 10
standard_enemy_x = 25
standard_enemy_y = 40
pincer_player_x = 25
pincer_player_y = 25
pincer_enemy1_x = 10
pincer_enemy1_y = 25
pincer_enemy2_x = 40
pincer_enemy2_y = 25
melee_center_x = 25
melee_center_y = 25
melee_spread_radius = 5
boss_arena_x = 25
boss_arena_y = 25
boss_start_distance = 30
""")
    
    mgr = ConfigManager(str(config_file))
    config = mgr.load()
    
    # Verify all major settings loaded
    assert config.debug_mode is True
    assert config.coordinate_grid_size == (50, 50)
    assert config.enable_scenario_rotation is False
    assert config.standard_player_x == 25
    assert config.standard_player_y == 10
    assert config.show_all_items is False


def test_gameconfig_defaults():
    """Test GameConfig has sensible defaults."""
    config = GameConfig()
    
    assert config.testmode is False
    assert config.debug_mode is False
    assert config.use_colour is True
    assert config.enable_animations is True
    assert config.coordinate_grid_size == (50, 50)
    assert config.ai_difficulty == 3
    assert config.allow_quicksave is True
