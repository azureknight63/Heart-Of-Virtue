# INI Configuration Features Implementation Plan

**Date:** October 31, 2025  
**Status:** Design Phase (Pre-Implementation)  
**Related:** HV-1 Coordinate Combat Positioning, Phase 4 Testing, config_phase4_testing.ini  

---

## Overview

This plan specifies how to implement the configuration features defined in `config_phase4_testing.ini`. Currently, the game only reads `testmode`, `skipdialog`, `startmap`, and `startposition`. This plan extends that to support **40+ new settings** organized into 7 sections.

---

## Implementation Strategy

### Phase 1: Config Loading Infrastructure
Extend `src/game.py` config reading to support all sections and settings.

### Phase 2: Feature Implementation by Category
Implement settings in grouped priority:
1. Display/Performance (visual settings)
2. Logging (debug output)
3. Combat/Positioning (coordinate system)
4. NPC AI (enemy behavior)
5. Testing Scenarios (combat rotation)

### Phase 3: Integration & Testing
Wire up features into existing game systems.

---

## Phase 1: Config Loading Infrastructure

### Current State
**File:** `src/game.py` lines 112-130

```python
try:
    config.read('config_dev.ini')
    testing_mode = config.getboolean('Startup', 'testmode')
    skip_dialog = config.getboolean('Startup', 'skipdialog')
    if skip_dialog:
        player.skip_dialog = True
    starting_map_name = config.get('Startup', 'startmap')
    startposition = ast.literal_eval(config.get('Startup', 'startposition'))
    starting_map = next((map_item for map_item in player.universe.maps if
                         map_item.get('name') == starting_map_name), player.universe.starting_map_default)
except FileNotFoundError:
    testing_mode = False
    starting_map = player.universe.starting_map_default
    startposition = player.universe.starting_position
```

### Required Changes

**Step 1: Create ConfigManager Class**

**File:** `src/config_manager.py` (new)

```python
"""Manage game configuration from INI files."""

import configparser
from pathlib import Path
from dataclasses import dataclass

@dataclass
class GameConfig:
    """Holds all parsed game configuration."""
    
    # [game] section
    testmode: bool = False
    skipdialog: bool = False
    skipintro: bool = False
    startmap: str = "default"
    startposition: tuple = (0, 0)
    use_colour: bool = True
    enable_animations: bool = True
    animation_speed: float = 1.0
    
    # Debug settings
    debug_mode: bool = False
    debug_positions: bool = False
    debug_movement: bool = False
    debug_damage_calc: bool = False
    debug_accuracy: bool = False
    debug_ai_decisions: bool = False
    debug_npc_positions: bool = False
    
    # Coordinate system
    use_coordinates: bool = True
    coordinate_grid_size: int = 50
    use_damage_modifiers: bool = True
    use_accuracy_modifiers: bool = True
    
    # Combat settings
    enable_new_combat_moves: bool = True
    enable_flanking_mechanics: bool = True
    enable_tactical_positioning: bool = True
    
    # NPC AI
    npc_use_coordinates: bool = True
    npc_flanking_enabled: bool = True
    npc_tactical_retreat: bool = True
    ai_difficulty: int = 3
    
    # Save/Load
    autosave_enabled: bool = False
    allow_quicksave: bool = True
    auto_load_latest: bool = False
    
    # Display
    show_combat_distance: bool = True
    show_unit_positions: bool = True
    show_facing_directions: bool = True
    show_damage_modifiers: bool = True
    show_accuracy_modifiers: bool = True
    
    # Logging
    log_combat_moves: bool = True
    log_distance_calculations: bool = True
    log_angle_calculations: bool = True
    log_npc_decisions: bool = True
    log_file: str = "combat_testing_phase4.log"
    
    # Scenarios
    test_scenario: str = "standard"
    max_enemies_standard: int = 3
    max_enemies_pincer: int = 4
    max_enemies_melee: int = 6
    max_enemies_boss: int = 1
    
    # Performance
    monitor_fps: bool = False
    monitor_memory: bool = False
    log_performance: bool = False
    
    # View
    follow_player: bool = True
    show_grid_overlay: bool = False
    show_coordinate_display: bool = True


class ConfigManager:
    """Load and manage game configuration."""
    
    def __init__(self, config_file='config_dev.ini'):
        self.config_file = config_file
        self.parser = configparser.ConfigParser()
        self.config = GameConfig()
    
    def load(self):
        """Load configuration from INI file."""
        if not Path(self.config_file).exists():
            return self.config
        
        self.parser.read(self.config_file)
        self._parse_game_section()
        self._parse_development_section()
        self._parse_combat_testing_section()
        self._parse_testing_locations_section()
        
        return self.config
    
    def _parse_game_section(self):
        """Parse [game] section."""
        if not self.parser.has_section('game'):
            return
        
        section = self.parser['game']
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
        
        # Coordinate system
        self.config.use_coordinates = section.getboolean('use_coordinates', fallback=True)
        self.config.coordinate_grid_size = section.getint('coordinate_grid_size', fallback=50)
        self.config.use_damage_modifiers = section.getboolean('use_damage_modifiers', fallback=True)
        self.config.use_accuracy_modifiers = section.getboolean('use_accuracy_modifiers', fallback=True)
        
        # Combat settings
        self.config.enable_new_combat_moves = section.getboolean('enable_new_combat_moves', fallback=True)
        self.config.enable_flanking_mechanics = section.getboolean('enable_flanking_mechanics', fallback=True)
        self.config.enable_tactical_positioning = section.getboolean('enable_tactical_positioning', fallback=True)
        
        # NPC AI
        self.config.npc_use_coordinates = section.getboolean('npc_use_coordinates', fallback=True)
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
        
        # Performance
        self.config.monitor_fps = section.getboolean('monitor_fps', fallback=False)
        self.config.monitor_memory = section.getboolean('monitor_memory', fallback=False)
        self.config.log_performance = section.getboolean('log_performance', fallback=False)
        
        # View
        self.config.follow_player = section.getboolean('follow_player', fallback=True)
        self.config.show_grid_overlay = section.getboolean('show_grid_overlay', fallback=False)
        self.config.show_coordinate_display = section.getboolean('show_coordinate_display', fallback=True)
    
    def _parse_development_section(self):
        """Parse [development] section (if implemented)."""
        pass  # Not needed for Phase 4, but reserved for future
    
    def _parse_combat_testing_section(self):
        """Parse [combat_testing] section (if implemented)."""
        pass  # Advanced features, can be added later
    
    def _parse_testing_locations_section(self):
        """Parse [testing_locations] section (if needed)."""
        pass  # Coordinates for different scenarios, can be added later
```

**Step 2: Update game.py to use ConfigManager**

**File:** `src/game.py` (modify)

```python
from config_manager import ConfigManager

def play():
    # ... existing code ...
    
    # Load configuration
    config_mgr = ConfigManager('config_dev.ini')
    config = config_mgr.load()
    
    # ... rest of menu ...
    
    if newgame:
        player = Player()
    else:
        loaded = functions.load_select()
        if loaded is None:
            continue
        player = loaded
    
    # Apply configuration to player and universe
    player.universe = Universe(player)
    player.universe.build(player)
    
    # Set configuration on player/universe
    player.testing_mode = config.testmode
    player.debug_mode = config.debug_mode
    player.skip_dialog = config.skipdialog
    player.use_colour = config.use_colour
    player.enable_animations = config.enable_animations
    
    player.universe.testing_mode = config.testmode
    player.universe.debug_mode = config.debug_mode
    player.universe.use_coordinates = config.use_coordinates
    player.universe.coordinate_grid_size = config.coordinate_grid_size
    player.universe.enable_flanking_mechanics = config.enable_flanking_mechanics
    player.universe.enable_tactical_positioning = config.enable_tactical_positioning
    player.universe.log_file = config.log_file
    
    # Set starting location
    starting_map = next((m for m in player.universe.maps if m.get('name') == config.startmap),
                        player.universe.starting_map_default)
    player.map = starting_map
    player.location_x, player.location_y = config.startposition
    
    # ... rest of game ...
```

---

## Phase 2: Feature Implementation by Category

### Category A: Display & Performance Settings

**Settings:**
- `use_colour` - Enable/disable colored text output
- `enable_animations` - Enable/disable animations
- `animation_speed` - Animation speed multiplier
- `show_combat_distance` - Display distance in combat
- `show_unit_positions` - Display unit coordinates
- `show_facing_directions` - Display unit facing
- `show_damage_modifiers` - Display damage bonuses
- `show_accuracy_modifiers` - Display accuracy bonuses
- `monitor_fps` - Monitor frame rate
- `monitor_memory` - Monitor memory usage
- `follow_player` - Follow player with camera
- `show_grid_overlay` - Show tactical grid
- `show_coordinate_display` - Show coordinate HUD

**Implementation:**

Create `src/display_config.py`:
```python
"""Display configuration management."""

@dataclass
class DisplayConfig:
    use_colour: bool
    enable_animations: bool
    animation_speed: float
    show_combat_distance: bool
    show_unit_positions: bool
    show_facing_directions: bool
    show_damage_modifiers: bool
    show_accuracy_modifiers: bool
    follow_player: bool
    show_grid_overlay: bool
    show_coordinate_display: bool

def apply_display_config(player, config: DisplayConfig):
    """Apply display settings to game."""
    player.use_colour = config.use_colour
    player.enable_animations = config.enable_animations
    player.animation_speed = config.animation_speed
    
    # These affect combat display
    player.show_combat_distance = config.show_combat_distance
    player.show_unit_positions = config.show_unit_positions
    player.show_facing_directions = config.show_facing_directions
    player.show_damage_modifiers = config.show_damage_modifiers
    player.show_accuracy_modifiers = config.show_accuracy_modifiers
    
    # Camera/view settings
    player.follow_player = config.follow_player
    player.show_grid_overlay = config.show_grid_overlay
    player.show_coordinate_display = config.show_coordinate_display
```

**Integration Points:**
- `src/interface.py` - Check `player.show_*` flags before displaying info
- `src/combat.py` - Display distance/modifiers if flags set
- `src/animations.py` - Check `animation_speed` for timing

---

### Category B: Logging Settings

**Settings:**
- `log_combat_moves` - Log player and NPC moves
- `log_distance_calculations` - Log distance math
- `log_angle_calculations` - Log angle math
- `log_npc_decisions` - Log NPC AI decisions
- `log_file` - Output file name
- `log_performance` - Log FPS/memory metrics

**Implementation:**

Create `src/game_logger.py`:
```python
"""Game logging system."""

import logging
from pathlib import Path
from datetime import datetime

class GameLogger:
    """Unified logging for debug output."""
    
    def __init__(self, log_file, log_config):
        self.log_file = log_file
        self.config = log_config
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """Set up Python logger."""
        logger = logging.getLogger('heart_of_virtue')
        logger.setLevel(logging.DEBUG)
        
        # File handler
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        return logger
    
    def log_move(self, unit_name, move_type, distance):
        """Log a move action."""
        if not self.config.log_combat_moves:
            return
        self.logger.info(f"{unit_name} used {move_type} (moved {distance} squares)")
    
    def log_distance(self, unit1, unit2, distance):
        """Log distance calculation."""
        if not self.config.log_distance_calculations:
            return
        self.logger.info(f"Distance {unit1} to {unit2}: {distance:.1f} ft")
    
    def log_angle(self, unit1, unit2, angle):
        """Log angle calculation."""
        if not self.config.log_angle_calculations:
            return
        self.logger.info(f"Angle {unit1} to {unit2}: {angle:.1f}°")
    
    def log_npc_decision(self, npc_name, decision, reasoning):
        """Log NPC AI decision."""
        if not self.config.log_npc_decisions:
            return
        self.logger.info(f"[AI] {npc_name}: {decision} ({reasoning})")
```

**Integration Points:**
- `src/combat.py` - Call logger after moves
- `src/npc.py` - Log AI decisions
- `src/positions.py` - Log calculations (optional)

---

### Category C: Coordinate System Settings

**Settings:**
- `use_coordinates` - Enable coordinate positioning
- `coordinate_grid_size` - Grid dimensions (default 50×50)
- `use_damage_modifiers` - Apply angle-based damage mods
- `use_accuracy_modifiers` - Apply angle-based accuracy mods

**Implementation:**

Modify `src/combat.py`:
```python
def combat(...):
    # Check if coordinate system enabled
    if not player.universe.use_coordinates:
        # Fall back to legacy distance-based combat
        return legacy_combat(...)
    
    # Use new coordinate system
    initialize_combat_positions(player, enemies, scenario, config.coordinate_grid_size)
    
    # Apply modifiers during combat
    if config.use_damage_modifiers:
        # Calculate angle-based damage bonus
        angle_diff = calculate_attack_angle(attacker, defender)
        damage_mod = get_damage_modifier(angle_diff)
        damage *= damage_mod
    
    if config.use_accuracy_modifiers:
        # Calculate angle-based accuracy bonus
        accuracy_mod = get_accuracy_modifier(angle_diff)
        accuracy *= accuracy_mod
```

---

### Category D: NPC AI Settings

**Settings:**
- `npc_use_coordinates` - Enable NPC coordinate positioning
- `npc_flanking_enabled` - Allow NPC flanking moves
- `npc_tactical_retreat` - Allow NPC retreats
- `ai_difficulty` - AI difficulty level (1-5)

**Implementation:**

Modify `src/npc.py`:
```python
def choose_action(self, combat_state):
    """NPC decision making."""
    
    # Check if coordinate system enabled
    if not combat_state.use_coordinates:
        return self.legacy_choose_action()
    
    # Calculate options
    options = []
    
    if combat_state.npc_flanking_enabled:
        flank_score = self.evaluate_flank_option()
        options.append(('flank', flank_score))
    
    if combat_state.npc_tactical_retreat:
        retreat_score = self.evaluate_retreat_option()
        options.append(('retreat', retreat_score))
    
    # Add standard moves
    advance_score = self.evaluate_advance_option()
    options.append(('advance', advance_score))
    
    # Select based on difficulty
    selected = self.select_by_difficulty(options, combat_state.ai_difficulty)
    return selected
```

---

### Category E: Combat Scenario Settings

**Settings:**
- `test_scenario` - Current scenario (standard/pincer/melee/boss)
- `max_enemies_*` - Enemy count per scenario
- `enable_scenario_rotation` - Auto-rotate scenarios
- `current_scenario` - Starting scenario

**Implementation:**

Modify `src/universe.py`:
```python
def initialize_combat_scenario(self, scenario_type, config):
    """Spawn enemies for scenario."""
    
    max_enemies = getattr(config, f'max_enemies_{scenario_type}', 3)
    
    COMBAT_SCENARIOS[scenario_type]['spawn'](
        self.maps[current_map],
        enemy_type='standard',
        count=max_enemies,
        player=self.player
    )
```

---

## Phase 3: Integration & Testing

### Step 1: Wire Configuration to Player/Universe

Ensure all config settings are accessible:
```python
player.debug_mode = config.debug_mode
player.logging = GameLogger(config.log_file, config)
player.universe.config = config
```

### Step 2: Update Combat Loop

```python
def combat(...):
    config = player.universe.config
    logger = player.logging
    
    while combat_active:
        if config.use_coordinates:
            # Coordinate-based combat
            ...
        else:
            # Legacy distance-based
            ...
```

### Step 3: Test Each Feature

Create tests in `tests/test_config_integration.py`:
```python
def test_config_load():
    """Test ConfigManager loads all settings."""
    mgr = ConfigManager('config_phase4_testing.ini')
    cfg = mgr.load()
    assert cfg.debug_mode == True
    assert cfg.ai_difficulty == 3
    assert cfg.coordinate_grid_size == 50

def test_display_config_applied():
    """Test display settings applied to player."""
    cfg = GameConfig(show_combat_distance=True, ...)
    apply_display_config(player, cfg)
    assert player.show_combat_distance == True

def test_logger_respects_config():
    """Test logger only logs when enabled."""
    cfg = LogConfig(log_combat_moves=False, ...)
    logger = GameLogger('test.log', cfg)
    logger.log_move(...)  # Should NOT write
```

---

## Implementation Priority & Effort Estimate

| Feature | Complexity | Effort | Priority |
|---------|-----------|--------|----------|
| ConfigManager (Phase 1) | High | 3-4 hrs | P0 (blocks all) |
| Display Settings | Low | 1-2 hrs | P1 (visual) |
| Logging System | Medium | 2-3 hrs | P1 (debug) |
| Coordinate System | High | 2-3 hrs | P0 (core) |
| NPC AI Settings | Medium | 2 hrs | P2 (optional) |
| Scenario Settings | Medium | 1-2 hrs | P2 (optional) |
| Integration Testing | Medium | 2-3 hrs | P1 (validation) |

**Total Estimated Effort:** 14-20 hours across 3-4 development sessions

---

## Success Criteria

✅ **Implementation Complete When:**

- ConfigManager loads all 40+ settings from INI
- Game applies config settings to player/universe/logger
- Display settings control what's shown in combat
- Logging system writes debug output to file
- Coordinate system can be toggled on/off via config
- NPC AI respects difficulty/feature flags
- Scenarios spawn correct enemy counts
- All 545 automated tests still passing
- New integration tests verify config features
- Phase 4 manual testing can control system via INI

---

## Files to Create/Modify

**New Files:**
- `src/config_manager.py` - Config loading
- `src/display_config.py` - Display settings management
- `src/game_logger.py` - Logging system
- `tests/test_config_integration.py` - Integration tests

**Modified Files:**
- `src/game.py` - Use ConfigManager, apply settings
- `src/combat.py` - Check config flags, apply modifiers
- `src/npc.py` - Check config flags for AI options
- `src/universe.py` - Apply scenario config
- `src/interface.py` - Check display flags before showing

---

## Future Enhancements

After Phase 4:
- [ ] Hot-reload config during game (enable_hot_reload)
- [ ] Configuration UI menu in-game
- [ ] Per-map configuration overrides
- [ ] Performance profiling dashboard
- [ ] Advanced NPC AI tuning parameters
- [ ] Save/restore config presets

---

**Document Status:** Ready for Implementation  
**Next Step:** Begin Phase 1 with ConfigManager

