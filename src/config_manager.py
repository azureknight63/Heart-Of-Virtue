"""Configuration management for Heart of Virtue.

Loads and parses game configuration from INI files.
Provides structured access to all game settings.
"""

import configparser
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple


@dataclass
class GameConfig:
    """Holds all parsed game configuration with sensible defaults."""
    
    # === [game] section: Base settings ===
    testmode: bool = False
    skipdialog: bool = False
    skipintro: bool = False
    startmap: str = "default"
    startposition: Tuple[int, int] = (0, 0)
    use_colour: bool = True
    enable_animations: bool = True
    animation_speed: float = 1.0
    
    # === [game] section: Debug settings ===
    debug_mode: bool = False
    debug_positions: bool = False
    debug_movement: bool = False
    debug_damage_calc: bool = False
    debug_accuracy: bool = False
    debug_ai_decisions: bool = False
    debug_npc_positions: bool = False
    
    # === [game] section: Coordinate system ===
    coordinate_grid_size: Tuple[int, int] = (50, 50)
    
    # === [game] section: Combat settings ===
    enable_new_combat_moves: bool = True
    enable_flanking_mechanics: bool = True
    enable_tactical_positioning: bool = True
    
    # === [game] section: NPC AI ===
    npc_flanking_enabled: bool = True
    npc_tactical_retreat: bool = True
    ai_difficulty: int = 3
    
    # === [game] section: Save/Load ===
    autosave_enabled: bool = False
    allow_quicksave: bool = True
    auto_load_latest: bool = False
    
    # === [game] section: Display ===
    show_combat_distance: bool = True
    show_unit_positions: bool = True
    show_facing_directions: bool = True
    show_damage_modifiers: bool = True
    show_accuracy_modifiers: bool = True
    
    # === [game] section: Logging ===
    log_combat_moves: bool = True
    log_distance_calculations: bool = True
    log_angle_calculations: bool = True
    log_npc_decisions: bool = True
    log_file: str = "combat_testing_phase4.log"
    
    # === [game] section: Scenarios ===
    test_scenario: str = "standard"
    max_enemies_standard: int = 3
    max_enemies_pincer: int = 4
    max_enemies_melee: int = 6
    max_enemies_boss: int = 1
    
    # === [game] section: Performance monitoring ===
    monitor_bps: bool = False
    log_performance: bool = False
    show_full_grid: bool = False
    grid_display_interval: int = 1
    show_coordinate_display: bool = True
    
    # === [development] section ===
    enable_hot_reload: bool = False
    show_all_items: bool = False
    god_mode: bool = False
    skip_combat: bool = False
    
    # === [combat_testing] section ===
    enable_scenario_rotation: bool = False
    current_scenario: str = "standard"
    starting_difficulty: int = 3
    difficulty_scaling: float = 0.5
    max_rounds_before_auto_victory: int = 50
    npc_decision_delay: float = 0.5
    npc_flanking_threshold: float = 45.0
    npc_retreat_health_threshold: float = 0.3
    npc_flanking_distance_range: str = "20.0 to 40.0"
    validate_grid_bounds: bool = True
    validate_distance_calc: bool = True
    validate_angle_calc: bool = True
    validate_modifier_calc: bool = True
    validate_npc_formations: bool = True
    
    # === [testing_locations] section: Standard formation ===
    standard_player_x: int = 25
    standard_player_y: int = 10
    standard_enemy_x: int = 25
    standard_enemy_y: int = 40
    
    # === [testing_locations] section: Pincer formation ===
    pincer_player_x: int = 25
    pincer_player_y: int = 25
    pincer_enemy1_x: int = 10
    pincer_enemy1_y: int = 25
    pincer_enemy2_x: int = 40
    pincer_enemy2_y: int = 25
    
    # === [testing_locations] section: Melee ===
    melee_center_x: int = 25
    melee_center_y: int = 25
    melee_spread_radius: int = 5
    
    # === [testing_locations] section: Boss arena ===
    boss_arena_x: int = 25
    boss_arena_y: int = 25
    boss_start_distance: int = 30


class ConfigManager:
    """Load and manage game configuration from INI files."""
    
    def __init__(self, config_file: str = 'config_dev.ini'):
        """Initialize ConfigManager with config file path.
        
        Args:
            config_file: Path to INI configuration file
        """
        self.config_file = config_file
        self.parser = configparser.ConfigParser()
        self.config = GameConfig()
    
    def load(self) -> GameConfig:
        """Load configuration from INI file.
        
        Returns:
            GameConfig object with all parsed settings
        """
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            # Return defaults if file doesn't exist
            return self.config
        
        self.parser.read(self.config_file)
        self._parse_game_section()
        self._parse_development_section()
        self._parse_combat_testing_section()
        self._parse_testing_locations_section()
        
        return self.config
    
    def _parse_game_section(self) -> None:
        """Parse [game] section settings."""
        if not self.parser.has_section('game'):
            return
        
        section = self.parser['game']
        
        # Base settings
        self.config.testmode = section.getboolean('testmode', fallback=False)
        self.config.skipdialog = section.getboolean('skipdialog', fallback=False)
        self.config.skipintro = section.getboolean('skipintro', fallback=False)
        self.config.startmap = section.get('startmap', fallback='default')
        
        # Parse startposition as tuple
        try:
            pos_str = section.get('startposition', fallback='0, 0')
            x, y = map(int, pos_str.split(','))
            self.config.startposition = (x, y)
        except (ValueError, AttributeError):
            self.config.startposition = (0, 0)
        
        # Graphics
        self.config.use_colour = section.getboolean('use_colour', fallback=True)
        self.config.enable_animations = section.getboolean('enable_animations', fallback=True)
        self.config.animation_speed = section.getfloat('animation_speed', fallback=1.0)
        
        # Debug settings
        self.config.debug_mode = section.getboolean('debug_mode', fallback=False)
        self.config.debug_positions = section.getboolean('debug_positions', fallback=False)
        self.config.debug_movement = section.getboolean('debug_movement', fallback=False)
        self.config.debug_damage_calc = section.getboolean('debug_damage_calc', fallback=False)
        self.config.debug_accuracy = section.getboolean('debug_accuracy', fallback=False)
        self.config.debug_ai_decisions = section.getboolean('debug_ai_decisions', fallback=False)
        self.config.debug_npc_positions = section.getboolean('debug_npc_positions', fallback=False)
        
        # Coordinate system (format: "50, 50" in INI)
        try:
            grid_str = section.get('coordinate_grid_size', fallback='50, 50')
            w, h = map(int, grid_str.split(','))
            self.config.coordinate_grid_size = (w, h)
        except (ValueError, AttributeError):
            self.config.coordinate_grid_size = (50, 50)
        
        # Combat settings
        self.config.enable_new_combat_moves = section.getboolean('enable_new_combat_moves', fallback=True)
        self.config.enable_flanking_mechanics = section.getboolean('enable_flanking_mechanics', fallback=True)
        self.config.enable_tactical_positioning = section.getboolean('enable_tactical_positioning', fallback=True)
        
        # NPC AI
        self.config.npc_flanking_enabled = section.getboolean('npc_flanking_enabled', fallback=True)
        self.config.npc_tactical_retreat = section.getboolean('npc_tactical_retreat', fallback=True)
        self.config.ai_difficulty = section.getint('ai_difficulty', fallback=3)
        
        # Save/Load
        self.config.autosave_enabled = section.getboolean('autosave_enabled', fallback=False)
        self.config.allow_quicksave = section.getboolean('allow_quicksave', fallback=True)
        self.config.auto_load_latest = section.getboolean('auto_load_latest', fallback=False)
        
        # Display
        self.config.show_combat_distance = section.getboolean('show_combat_distance', fallback=True)
        self.config.show_unit_positions = section.getboolean('show_unit_positions', fallback=True)
        self.config.show_facing_directions = section.getboolean('show_facing_directions', fallback=True)
        self.config.show_damage_modifiers = section.getboolean('show_damage_modifiers', fallback=True)
        self.config.show_accuracy_modifiers = section.getboolean('show_accuracy_modifiers', fallback=True)
        
        # Logging
        self.config.log_combat_moves = section.getboolean('log_combat_moves', fallback=True)
        self.config.log_distance_calculations = section.getboolean('log_distance_calculations', fallback=True)
        self.config.log_angle_calculations = section.getboolean('log_angle_calculations', fallback=True)
        self.config.log_npc_decisions = section.getboolean('log_npc_decisions', fallback=True)
        self.config.log_file = section.get('log_file', fallback='combat_testing_phase4.log')
        
        # Scenarios
        self.config.test_scenario = section.get('test_scenario', fallback='standard')
        self.config.max_enemies_standard = section.getint('max_enemies_standard', fallback=3)
        self.config.max_enemies_pincer = section.getint('max_enemies_pincer', fallback=4)
        self.config.max_enemies_melee = section.getint('max_enemies_melee', fallback=6)
        self.config.max_enemies_boss = section.getint('max_enemies_boss', fallback=1)
        
        # Performance monitoring
        self.config.monitor_bps = section.getboolean('monitor_bps', fallback=False)
        self.config.log_performance = section.getboolean('log_performance', fallback=False)
        self.config.show_full_grid = section.getboolean('show_full_grid', fallback=False)
        self.config.grid_display_interval = section.getint('grid_display_interval', fallback=1)
        self.config.show_coordinate_display = section.getboolean('show_coordinate_display', fallback=True)
    
    def _parse_development_section(self) -> None:
        """Parse [development] section settings."""
        if not self.parser.has_section('development'):
            return
        
        section = self.parser['development']
        self.config.enable_hot_reload = section.getboolean('enable_hot_reload', fallback=False)
        self.config.show_all_items = section.getboolean('show_all_items', fallback=False)
        self.config.god_mode = section.getboolean('god_mode', fallback=False)
        self.config.skip_combat = section.getboolean('skip_combat', fallback=False)
    
    def _parse_combat_testing_section(self) -> None:
        """Parse [combat_testing] section settings."""
        if not self.parser.has_section('combat_testing'):
            return
        
        section = self.parser['combat_testing']
        self.config.enable_scenario_rotation = section.getboolean('enable_scenario_rotation', fallback=False)
        self.config.current_scenario = section.get('current_scenario', fallback='standard')
        self.config.starting_difficulty = section.getint('starting_difficulty', fallback=3)
        self.config.difficulty_scaling = section.getfloat('difficulty_scaling', fallback=0.5)
        self.config.max_rounds_before_auto_victory = section.getint('max_rounds_before_auto_victory', fallback=50)
        self.config.npc_decision_delay = section.getfloat('npc_decision_delay', fallback=0.5)
        self.config.npc_flanking_threshold = section.getfloat('npc_flanking_threshold', fallback=45.0)
        self.config.npc_retreat_health_threshold = section.getfloat('npc_retreat_health_threshold', fallback=0.3)
        self.config.npc_flanking_distance_range = section.get('npc_flanking_distance_range', fallback='20.0 to 40.0')
        self.config.validate_grid_bounds = section.getboolean('validate_grid_bounds', fallback=True)
        self.config.validate_distance_calc = section.getboolean('validate_distance_calc', fallback=True)
        self.config.validate_angle_calc = section.getboolean('validate_angle_calc', fallback=True)
        self.config.validate_modifier_calc = section.getboolean('validate_modifier_calc', fallback=True)
        self.config.validate_npc_formations = section.getboolean('validate_npc_formations', fallback=True)
    
    def _parse_testing_locations_section(self) -> None:
        """Parse [testing_locations] section settings."""
        if not self.parser.has_section('testing_locations'):
            return
        
        section = self.parser['testing_locations']
        
        # Standard formation
        self.config.standard_player_x = section.getint('standard_player_x', fallback=25)
        self.config.standard_player_y = section.getint('standard_player_y', fallback=10)
        self.config.standard_enemy_x = section.getint('standard_enemy_x', fallback=25)
        self.config.standard_enemy_y = section.getint('standard_enemy_y', fallback=40)
        
        # Pincer formation
        self.config.pincer_player_x = section.getint('pincer_player_x', fallback=25)
        self.config.pincer_player_y = section.getint('pincer_player_y', fallback=25)
        self.config.pincer_enemy1_x = section.getint('pincer_enemy1_x', fallback=10)
        self.config.pincer_enemy1_y = section.getint('pincer_enemy1_y', fallback=25)
        self.config.pincer_enemy2_x = section.getint('pincer_enemy2_x', fallback=40)
        self.config.pincer_enemy2_y = section.getint('pincer_enemy2_y', fallback=25)
        
        # Melee
        self.config.melee_center_x = section.getint('melee_center_x', fallback=25)
        self.config.melee_center_y = section.getint('melee_center_y', fallback=25)
        self.config.melee_spread_radius = section.getint('melee_spread_radius', fallback=5)
        
        # Boss arena
        self.config.boss_arena_x = section.getint('boss_arena_x', fallback=25)
        self.config.boss_arena_y = section.getint('boss_arena_y', fallback=25)
        self.config.boss_start_distance = section.getint('boss_start_distance', fallback=30)
