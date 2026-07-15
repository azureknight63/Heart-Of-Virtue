"""Configuration management for Heart of Virtue.

Loads and parses game configuration from INI files.
Provides structured access to all game settings.
"""

import math
import configparser
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple


def _safe_get(section, key, fallback):
    """``section.get`` that never raises -- degrades to ``fallback``."""
    try:
        return section.get(key, fallback=fallback)
    except (configparser.Error, ValueError, TypeError):
        return fallback


def _safe_getboolean(section, key, fallback):
    """``section.getboolean`` that never raises -- degrades to ``fallback``."""
    try:
        return section.getboolean(key, fallback=fallback)
    except (configparser.Error, ValueError, TypeError):
        return fallback


def _safe_getint(section, key, fallback):
    """``section.getint`` that never raises -- degrades to ``fallback``."""
    try:
        return section.getint(key, fallback=fallback)
    except (configparser.Error, ValueError, TypeError):
        return fallback


def _safe_getfloat(section, key, fallback):
    """``section.getfloat`` that never raises and never yields inf/nan.

    Malformed, overflowing, or non-finite (``inf``/``nan``) values all
    degrade to ``fallback`` -- a config-driven float feeding a game
    calculation should never poison downstream math with a non-finite value.
    """
    try:
        value = section.getfloat(key, fallback=fallback)
    except (configparser.Error, ValueError, TypeError, OverflowError):
        return fallback
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return fallback
    return value


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
    starting_exp: int = 0

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
    learn_all_skills: bool = False

    # === [game] section: Story pre-seeding ===
    # Comma-separated list of "flag" or "flag=value" entries to inject into universe.story
    # e.g. starting_story_flags = king_slime_defeated, votha_krr_response_given
    # Entries without an explicit value default to "1".
    starting_story_flags: List[str] = field(default_factory=list)

    # === [game] section: Starting party ===
    # Comma-separated list of NPC class names (from the npc package) to spawn
    # at the player's starting tile and add to combat_list_allies immediately.
    # e.g. starting_party_members = Gorran
    starting_party_members: List[str] = field(default_factory=list)

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
    log_file: str = "combat.log"

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

    def __init__(self, config_file: str = "config_dev.ini"):
        """Initialize ConfigManager with config file path.

        Args:
            config_file: Path to INI configuration file
        """
        self.config_file = config_file
        # Allow inline comments with semicolon and hash. Interpolation is
        # disabled -- config values are opaque strings, not templates, and a
        # stray "%" (very plausible in free-text fields) must not raise.
        # strict=False lets duplicate keys/sections merge (last value wins)
        # instead of treating the whole file as unparseable.
        self.parser = configparser.ConfigParser(
            inline_comment_prefixes=(";", "#"), interpolation=None, strict=False
        )
        self.config = GameConfig()

    def load(self) -> GameConfig:
        """Load configuration from INI file.

        Never raises: any unreadable or malformed INI file (bad encoding,
        missing section headers, syntax errors, etc.) degrades to the
        default ``GameConfig()`` rather than propagating an exception.

        Returns:
            GameConfig object with all parsed settings
        """
        config_path = Path(self.config_file)

        if not config_path.exists():
            # Return defaults if file doesn't exist
            return self.config

        try:
            self.parser.read(self.config_file, encoding="utf-8")
        except (configparser.Error, UnicodeDecodeError, OSError, ValueError):
            # Malformed/unreadable INI (bad encoding, duplicate headers,
            # missing section headers, etc.): the parser may hold a partial,
            # inconsistent state, so start clean and fall back to defaults
            # rather than parse a half-populated config.
            self.parser = configparser.ConfigParser(
                inline_comment_prefixes=(";", "#"), interpolation=None, strict=False
            )
            return self.config

        try:
            self._parse_game_section()
            self._parse_development_section()
            self._parse_combat_testing_section()
            self._parse_testing_locations_section()
        except Exception:
            # Belt-and-suspenders: every individual field read is already
            # guarded (see _safe_get*), so this should be unreachable. Never
            # let a config bug crash the caller -- fall back to whatever
            # fields were already populated (defaults for the rest).
            pass

        return self.config

    def _parse_game_section(self) -> None:
        """Parse [game] section settings."""
        if not self.parser.has_section("game"):
            return

        section = self.parser["game"]

        # Base settings
        self.config.testmode = _safe_getboolean(section, "testmode", False)
        self.config.skipdialog = _safe_getboolean(section, "skipdialog", False)
        self.config.skipintro = _safe_getboolean(section, "skipintro", False)
        self.config.startmap = _safe_get(section, "startmap", "default")

        # Parse startposition as tuple
        try:
            pos_str = _safe_get(section, "startposition", "0, 0")
            # Remove parentheses if present
            pos_str = pos_str.strip("() ")
            x, y = map(int, pos_str.split(","))
            self.config.startposition = (x, y)
        except (ValueError, AttributeError):
            self.config.startposition = (0, 0)

        # Graphics
        self.config.use_colour = _safe_getboolean(section, "use_colour", True)
        self.config.enable_animations = _safe_getboolean(
            section, "enable_animations", True
        )
        self.config.animation_speed = _safe_getfloat(section, "animation_speed", 1.0)
        self.config.starting_exp = _safe_getint(section, "starting_exp", 0)

        # Story flag pre-seeding: parse comma-separated "flag" or "flag=value" tokens
        raw_flags = _safe_get(section, "starting_story_flags", "")
        parsed_flags: List[str] = []
        if raw_flags.strip():
            for token in raw_flags.split(","):
                token = token.strip()
                if token:
                    parsed_flags.append(token)
        self.config.starting_story_flags = parsed_flags

        # Starting party members: parse comma-separated NPC class names
        raw_party = _safe_get(section, "starting_party_members", "")
        parsed_party: List[str] = []
        if raw_party.strip():
            for token in raw_party.split(","):
                token = token.strip()
                if token:
                    parsed_party.append(token)
        self.config.starting_party_members = parsed_party

        # Debug settings
        self.config.debug_mode = _safe_getboolean(section, "debug_mode", False)
        self.config.debug_positions = _safe_getboolean(
            section, "debug_positions", False
        )
        self.config.debug_movement = _safe_getboolean(section, "debug_movement", False)
        self.config.debug_damage_calc = _safe_getboolean(
            section, "debug_damage_calc", False
        )
        self.config.debug_accuracy = _safe_getboolean(section, "debug_accuracy", False)
        self.config.debug_ai_decisions = _safe_getboolean(
            section, "debug_ai_decisions", False
        )
        self.config.debug_npc_positions = _safe_getboolean(
            section, "debug_npc_positions", False
        )

        # Coordinate system (format: "50, 50" in INI)
        try:
            grid_str = _safe_get(section, "coordinate_grid_size", "50, 50")
            w, h = map(int, grid_str.split(","))
            if w <= 0 or h <= 0:
                # A non-positive grid dimension is nonsensical (would break
                # any bounds/modulo math downstream) -- fall back to default.
                raise ValueError("non-positive grid dimension")
            self.config.coordinate_grid_size = (w, h)
        except (ValueError, AttributeError):
            self.config.coordinate_grid_size = (50, 50)

        # Combat settings
        self.config.enable_new_combat_moves = _safe_getboolean(
            section, "enable_new_combat_moves", True
        )
        self.config.enable_flanking_mechanics = _safe_getboolean(
            section, "enable_flanking_mechanics", True
        )
        self.config.enable_tactical_positioning = _safe_getboolean(
            section, "enable_tactical_positioning", True
        )

        # NPC AI
        self.config.npc_flanking_enabled = _safe_getboolean(
            section, "npc_flanking_enabled", True
        )
        self.config.npc_tactical_retreat = _safe_getboolean(
            section, "npc_tactical_retreat", True
        )
        self.config.ai_difficulty = _safe_getint(section, "ai_difficulty", 3)

        # Save/Load
        self.config.autosave_enabled = _safe_getboolean(
            section, "autosave_enabled", False
        )
        self.config.allow_quicksave = _safe_getboolean(section, "allow_quicksave", True)
        self.config.auto_load_latest = _safe_getboolean(
            section, "auto_load_latest", False
        )
        self.config.learn_all_skills = _safe_getboolean(
            section, "learn_all_skills", False
        )

        # Display
        self.config.show_combat_distance = _safe_getboolean(
            section, "show_combat_distance", True
        )
        self.config.show_unit_positions = _safe_getboolean(
            section, "show_unit_positions", True
        )
        self.config.show_facing_directions = _safe_getboolean(
            section, "show_facing_directions", True
        )
        self.config.show_damage_modifiers = _safe_getboolean(
            section, "show_damage_modifiers", True
        )
        self.config.show_accuracy_modifiers = _safe_getboolean(
            section, "show_accuracy_modifiers", True
        )

        # Logging
        self.config.log_combat_moves = _safe_getboolean(
            section, "log_combat_moves", True
        )
        self.config.log_distance_calculations = _safe_getboolean(
            section, "log_distance_calculations", True
        )
        self.config.log_angle_calculations = _safe_getboolean(
            section, "log_angle_calculations", True
        )
        self.config.log_npc_decisions = _safe_getboolean(
            section, "log_npc_decisions", True
        )
        self.config.log_file = _safe_get(section, "log_file", "combat.log")

        # Scenarios
        self.config.test_scenario = _safe_get(section, "test_scenario", "standard")
        self.config.max_enemies_standard = _safe_getint(
            section, "max_enemies_standard", 3
        )
        self.config.max_enemies_pincer = _safe_getint(section, "max_enemies_pincer", 4)
        self.config.max_enemies_melee = _safe_getint(section, "max_enemies_melee", 6)
        self.config.max_enemies_boss = _safe_getint(section, "max_enemies_boss", 1)

        # Performance monitoring
        self.config.monitor_bps = _safe_getboolean(section, "monitor_bps", False)
        self.config.log_performance = _safe_getboolean(
            section, "log_performance", False
        )
        self.config.show_full_grid = _safe_getboolean(section, "show_full_grid", False)
        self.config.grid_display_interval = _safe_getint(
            section, "grid_display_interval", 1
        )
        self.config.show_coordinate_display = _safe_getboolean(
            section, "show_coordinate_display", True
        )

    def _parse_development_section(self) -> None:
        """Parse [development] section settings."""
        if not self.parser.has_section("development"):
            return

        section = self.parser["development"]
        self.config.enable_hot_reload = _safe_getboolean(
            section, "enable_hot_reload", False
        )
        self.config.show_all_items = _safe_getboolean(section, "show_all_items", False)
        self.config.god_mode = _safe_getboolean(section, "god_mode", False)
        self.config.skip_combat = _safe_getboolean(section, "skip_combat", False)

    def _parse_combat_testing_section(self) -> None:
        """Parse [combat_testing] section settings."""
        if not self.parser.has_section("combat_testing"):
            return

        section = self.parser["combat_testing"]
        self.config.enable_scenario_rotation = _safe_getboolean(
            section, "enable_scenario_rotation", False
        )
        self.config.current_scenario = _safe_get(
            section, "current_scenario", "standard"
        )
        self.config.starting_difficulty = _safe_getint(
            section, "starting_difficulty", 3
        )
        self.config.difficulty_scaling = _safe_getfloat(
            section, "difficulty_scaling", 0.5
        )
        self.config.max_rounds_before_auto_victory = _safe_getint(
            section, "max_rounds_before_auto_victory", 50
        )
        self.config.npc_decision_delay = _safe_getfloat(
            section, "npc_decision_delay", 0.5
        )
        self.config.npc_flanking_threshold = _safe_getfloat(
            section, "npc_flanking_threshold", 45.0
        )
        self.config.npc_retreat_health_threshold = _safe_getfloat(
            section, "npc_retreat_health_threshold", 0.3
        )
        self.config.npc_flanking_distance_range = _safe_get(
            section, "npc_flanking_distance_range", "20.0 to 40.0"
        )
        self.config.validate_grid_bounds = _safe_getboolean(
            section, "validate_grid_bounds", True
        )
        self.config.validate_distance_calc = _safe_getboolean(
            section, "validate_distance_calc", True
        )
        self.config.validate_angle_calc = _safe_getboolean(
            section, "validate_angle_calc", True
        )
        self.config.validate_modifier_calc = _safe_getboolean(
            section, "validate_modifier_calc", True
        )
        self.config.validate_npc_formations = _safe_getboolean(
            section, "validate_npc_formations", True
        )

    def _parse_testing_locations_section(self) -> None:
        """Parse [testing_locations] section settings."""
        if not self.parser.has_section("testing_locations"):
            return

        section = self.parser["testing_locations"]

        # Standard formation
        self.config.standard_player_x = _safe_getint(section, "standard_player_x", 25)
        self.config.standard_player_y = _safe_getint(section, "standard_player_y", 10)
        self.config.standard_enemy_x = _safe_getint(section, "standard_enemy_x", 25)
        self.config.standard_enemy_y = _safe_getint(section, "standard_enemy_y", 40)

        # Pincer formation
        self.config.pincer_player_x = _safe_getint(section, "pincer_player_x", 25)
        self.config.pincer_player_y = _safe_getint(section, "pincer_player_y", 25)
        self.config.pincer_enemy1_x = _safe_getint(section, "pincer_enemy1_x", 10)
        self.config.pincer_enemy1_y = _safe_getint(section, "pincer_enemy1_y", 25)
        self.config.pincer_enemy2_x = _safe_getint(section, "pincer_enemy2_x", 40)
        self.config.pincer_enemy2_y = _safe_getint(section, "pincer_enemy2_y", 25)

        # Melee
        self.config.melee_center_x = _safe_getint(section, "melee_center_x", 25)
        self.config.melee_center_y = _safe_getint(section, "melee_center_y", 25)
        self.config.melee_spread_radius = _safe_getint(
            section, "melee_spread_radius", 5
        )

        # Boss arena
        self.config.boss_arena_x = _safe_getint(section, "boss_arena_x", 25)
        self.config.boss_arena_y = _safe_getint(section, "boss_arena_y", 25)
        self.config.boss_start_distance = _safe_getint(
            section, "boss_start_distance", 30
        )
