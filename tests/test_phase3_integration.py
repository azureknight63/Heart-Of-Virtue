"""Integration tests for Phase 3 - Config systems working together in combat.

Tests verify:
- Display config controls what's shown
- Logger respects all flags and logs correctly
- Debug manager initializes and commands work
- Coordinate config provides distance/angle calculations
- NPC AI config integrates with select_move
- Scenario config initializes with universe
- All systems work together without breaking existing combat
"""

import sys
from pathlib import Path

# Setup path for imports
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.player import Player  # type: ignore
from src.universe import Universe  # type: ignore
from src.npc import NPC  # type: ignore
from src.moves import Advance  # type: ignore
from src.config_manager import GameConfig, ConfigManager  # type: ignore
from src.display_config import CombatDisplayConfig  # type: ignore
from src.game_logger import GameLogger  # type: ignore
from src.debug_manager import DebugManager  # type: ignore
from src.coordinate_config import CoordinateSystemConfig  # type: ignore
from src.npc_ai_config import NPCAIConfig  # type: ignore
from src.scenario_config import ScenarioConfig  # type: ignore


class TestCombatIntegration:
    """Test config systems in combat context."""
    
    @pytest.fixture
    def player(self):
        """Create a player with game_config for testing."""
        p = Player()
        # Set up config
        config = GameConfig(
            debug_mode=True,
            debug_ai_decisions=True,
            log_combat_moves=True,
            show_combat_distance=True,
            show_unit_positions=True
        )
        p.game_config = config
        p.universe = Universe(p)
        p.universe.build(p)
        return p
    
    def test_display_config_initializes(self, player):
        """Test CombatDisplayConfig initializes with player."""
        display_config = CombatDisplayConfig(player)
        assert display_config.player == player
        assert display_config.should_show_distance() == True
        assert display_config.should_show_positions() == True
    
    def test_game_logger_initializes(self, player):
        """Test GameLogger initializes with player."""
        game_logger = GameLogger(player)
        assert game_logger.player == player
        log_path = game_logger._get_log_file_path()
        assert log_path is not None
    
    def test_debug_manager_initializes(self, player):
        """Test DebugManager initializes with player."""
        debug_manager = DebugManager(player)
        assert debug_manager.player == player
        assert debug_manager.is_debug_mode_enabled() == True
        assert debug_manager.should_debug_ai_decisions() == True
    
    def test_coordinate_config_initializes(self, player):
        """Test CoordinateSystemConfig initializes with player."""
        coordinate_config = CoordinateSystemConfig(player)
        assert coordinate_config.player == player
        assert coordinate_config.get_grid_size() == (50, 50)
    
    def test_npc_ai_config_initializes(self, player):
        """Test NPCAIConfig initializes with player."""
        npc_ai_config = NPCAIConfig(player)
        assert npc_ai_config.player == player
        # Verify flanking is accessible
        assert npc_ai_config.is_flanking_enabled() in [True, False]
    
    def test_scenario_config_initializes(self, player):
        """Test ScenarioConfig initializes with player."""
        scenario_config = ScenarioConfig(player)
        assert scenario_config.player == player
        assert scenario_config.get_current_scenario() in ['standard', 'pincer', 'melee', 'boss']
    
    def test_universe_initializes_configs(self, player):
        """Test Universe initializes config systems."""
        player.game_config = GameConfig()
        universe = Universe(player)
        universe.build(player)
        
        # Configs should be initialized
        assert universe.scenario_config is not None
        assert universe.coordinate_config is not None
        # Verify by checking the presence of key methods
        assert hasattr(universe.scenario_config, 'get_current_scenario')
        assert hasattr(universe.coordinate_config, 'get_grid_size')
    
    def test_npc_player_ref_set_in_combat(self, player):
        """Test that NPC player_ref is accessible for config."""
        enemy = NPC("Test Enemy", "A test enemy", 10, 50, 100)
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        
        # Simulate combat initialization
        for npc in player.combat_list + player.combat_list_allies:
            npc.player_ref = player
        
        assert enemy.player_ref == player
        assert player.player_ref == player
    
    def test_all_configs_accessible_from_combat(self, player):
        """Test all config systems accessible during simulated combat."""
        # Simulate combat setup
        player.combat_display_config = CombatDisplayConfig(player)
        player.combat_game_logger = GameLogger(player)
        player.combat_debug_manager = DebugManager(player)
        player.combat_coordinate_config = CoordinateSystemConfig(player)
        
        # Verify all accessible
        assert hasattr(player, 'combat_display_config')
        assert hasattr(player, 'combat_game_logger')
        assert hasattr(player, 'combat_debug_manager')
        assert hasattr(player, 'combat_coordinate_config')
        
        assert isinstance(player.combat_display_config, CombatDisplayConfig)
        assert isinstance(player.combat_game_logger, GameLogger)
        assert isinstance(player.combat_debug_manager, DebugManager)
        assert isinstance(player.combat_coordinate_config, CoordinateSystemConfig)


class TestDisplayConfigIntegration:
    """Test display config respects flags."""
    
    def test_display_config_respects_show_distance_flag(self):
        """Test display config respects show_combat_distance flag."""
        p = Player()
        p.game_config = GameConfig(show_combat_distance=True)
        
        display_config = CombatDisplayConfig(p)
        assert display_config.should_show_distance() == True
        
        # Test with flag off
        p.game_config.show_combat_distance = False
        assert display_config.should_show_distance() == False
    
    def test_display_config_respects_show_positions_flag(self):
        """Test display config respects show_unit_positions flag."""
        p = Player()
        p.game_config = GameConfig(show_unit_positions=True)
        
        display_config = CombatDisplayConfig(p)
        assert display_config.should_show_positions() == True
        
        p.game_config.show_unit_positions = False
        assert display_config.should_show_positions() == False


class TestLoggingIntegration:
    """Test logging respects config flags."""
    
    def test_logger_respects_log_combat_moves_flag(self):
        """Test logger respects log_combat_moves flag."""
        p = Player()
        p.game_config = GameConfig(log_combat_moves=True)
        
        game_logger = GameLogger(p)
        # Logger should respect the flag
        assert game_logger.player.game_config.log_combat_moves == True
    
    def test_logger_respects_multiple_flags(self):
        """Test logger respects all logging flags."""
        p = Player()
        p.game_config = GameConfig(
            log_combat_moves=True,
            log_distance_calculations=False,
            log_angle_calculations=True,
            log_npc_decisions=False
        )
        
        game_logger = GameLogger(p)
        config = game_logger.player.game_config
        
        assert config.log_combat_moves == True
        assert config.log_distance_calculations == False
        assert config.log_angle_calculations == True
        assert config.log_npc_decisions == False


class TestDebugManagerIntegration:
    """Test debug manager works in combat context."""
    
    def test_debug_manager_respects_debug_flags(self):
        """Test debug manager respects all debug flags."""
        p = Player()
        p.game_config = GameConfig(
            debug_mode=True,
            debug_positions=True,
            debug_ai_decisions=True,
            debug_damage_calc=False
        )
        
        debug_manager = DebugManager(p)
        assert debug_manager.is_debug_mode_enabled() == True
        assert debug_manager.should_debug_positions() == True
        assert debug_manager.should_debug_ai_decisions() == True
        assert debug_manager.should_debug_damage_calc() == False
    
    def test_debug_commands_registered(self):
        """Test debug commands are accessible."""
        p = Player()
        p.game_config = GameConfig(debug_mode=True)
        
        debug_manager = DebugManager(p)
        # Verify debug manager has command logging methods
        assert hasattr(debug_manager, 'log_command')
        assert hasattr(debug_manager, 'get_command_history')
        assert hasattr(debug_manager, 'execute_command')


class TestCoordinateIntegration:
    """Test coordinate config calculations."""
    
    def test_coordinate_config_distance_calculation(self):
        """Test coordinate config calculates distance correctly."""
        p = Player()
        p.game_config = GameConfig(coordinate_grid_size=(50, 50))
        
        coord_config = CoordinateSystemConfig(p)
        distance = coord_config.get_distance_between_points(0, 0, 3, 4)
        
        # 3-4-5 triangle
        assert abs(distance - 5.0) < 0.01
    
    def test_coordinate_config_bounds_validation(self):
        """Test coordinate config validates bounds."""
        p = Player()
        p.game_config = GameConfig(coordinate_grid_size=(50, 50))

        coord_config = CoordinateSystemConfig(p)
        assert coord_config.is_coordinate_valid(25, 25) == True
        assert coord_config.is_coordinate_valid(0, 0) == True
        assert coord_config.is_coordinate_valid(49, 49) == True
        assert coord_config.is_coordinate_valid(50, 50) == True  # Grid includes boundary
        assert coord_config.is_coordinate_valid(51, 51) == False
        assert coord_config.is_coordinate_valid(-1, 0) == False
class TestScenarioIntegration:
    """Test scenario config integration."""
    
    def test_scenario_config_difficulty_scaling(self):
        """Test scenario config provides difficulty scaling."""
        p = Player()
        p.game_config = GameConfig(difficulty_scaling=0.5)
        
        scenario_config = ScenarioConfig(p)
        scaling = scenario_config.get_difficulty_scaling_factor()
        assert scaling == 0.5
    
    def test_scenario_config_current_scenario(self):
        """Test scenario config returns current scenario."""
        p = Player()
        p.game_config = GameConfig(current_scenario='melee')
        
        scenario_config = ScenarioConfig(p)
        current = scenario_config.get_current_scenario()
        assert current == 'melee'


class TestNPCAIIntegration:
    """Test NPC AI config integration."""
    
    def test_npc_ai_flanking_enabled(self):
        """Test NPC AI flanking configuration."""
        p = Player()
        p.game_config = GameConfig(npc_flanking_enabled=True)
        
        npc_ai_config = NPCAIConfig(p)
        assert npc_ai_config.is_flanking_enabled() == True
    
    def test_npc_ai_flanking_threshold(self):
        """Test NPC AI flanking threshold configuration."""
        p = Player()
        p.game_config = GameConfig(npc_flanking_threshold=45.0)
        
        npc_ai_config = NPCAIConfig(p)
        threshold = npc_ai_config.get_flanking_threshold()
        assert threshold == 45.0


class TestFullIntegration:
    """Test all systems together."""
    
    def test_all_systems_initialized_together(self):
        """Test all config systems initialize together."""
        p = Player()
        config = GameConfig(
            debug_mode=True,
            show_combat_distance=True,
            log_combat_moves=True
        )
        p.game_config = config
        
        # Initialize all systems
        display = CombatDisplayConfig(p)
        logger = GameLogger(p)
        debug = DebugManager(p)
        coords = CoordinateSystemConfig(p)
        npc_ai = NPCAIConfig(p)
        scenarios = ScenarioConfig(p)
        
        # Verify all initialized
        assert display.should_show_distance() == True
        assert debug.is_debug_mode_enabled() == True
        assert logger.player == p
        assert coords.get_grid_size() == (50, 50)
        assert npc_ai.is_flanking_enabled() == True
        assert scenarios.get_current_scenario() in ['standard', 'pincer', 'melee', 'boss_arena']
    
    def test_no_breaking_changes_to_existing_combat(self):
        """Test that config integration doesn't break existing combat."""
        p = Player()
        # Create enemy without game_config
        enemy = NPC("Enemy", "An enemy", 10, 50, 100)
        
        # Should not crash even without config
        assert enemy.player_ref is None
        assert enemy.name == "Enemy"
        assert enemy.hp == 100
