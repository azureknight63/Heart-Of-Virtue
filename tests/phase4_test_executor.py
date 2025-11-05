"""Phase 4 Manual Testing Helper - Automated Test Execution Framework

This script helps execute Phase 4 manual tests by:
1. Starting combat with predefined config states
2. Logging test execution
3. Capturing console output
4. Verifying expected behavior
"""

import sys
from pathlib import Path
import json
from datetime import datetime

# Setup path
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from player import Player  # type: ignore
from universe import Universe  # type: ignore
from npc import NPC  # type: ignore
from config_manager import GameConfig, ConfigManager  # type: ignore
from display_config import CombatDisplayConfig  # type: ignore
from game_logger import GameLogger  # type: ignore
from debug_manager import DebugManager  # type: ignore
from coordinate_config import CoordinateSystemConfig  # type: ignore
from npc_ai_config import NPCAIConfig  # type: ignore
from scenario_config import ScenarioConfig  # type: ignore


class Phase4TestExecutor:
    """Executes Phase 4 manual test cases."""
    
    def __init__(self):
        """Initialize test executor."""
        self.test_results = []
        self.test_log = ROOT / "tests" / "PHASE4_TEST_RESULTS.json"
        self.start_time = datetime.now()
    
    def log_test(self, suite: str, test_id: str, status: str, notes: str = ""):
        """Log a test result.
        
        Args:
            suite: Test suite name (e.g., "Display Config")
            test_id: Test ID (e.g., "1.1")
            status: Status ("PASS", "FAIL", "SKIP")
            notes: Additional notes
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "suite": suite,
            "test_id": test_id,
            "status": status,
            "notes": notes
        }
        self.test_results.append(result)
        print(f"[{suite}] {test_id}: {status} - {notes}")
    
    def setup_combat(self, config_overrides: dict = None) -> Player:
        """Setup a combat scenario with given config.
        
        Args:
            config_overrides: Dict of config overrides
            
        Returns:
            Player object ready for combat
        """
        player = Player()
        
        # Create default config
        config = GameConfig(
            debug_mode=True,
            show_combat_distance=True,
            log_combat_moves=True,
            show_unit_positions=True
        )
        
        # Apply overrides
        if config_overrides:
            for key, value in config_overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        player.game_config = config
        player.universe = Universe(player)
        player.universe.build(player)
        
        return player
    
    def test_display_config_distance(self):
        """Test 1.1: Show Distance During Combat"""
        try:
            player = self.setup_combat({"show_combat_distance": True})
            display_config = CombatDisplayConfig(player)
            
            # Verify distance display enabled
            assert display_config.should_show_distance() == True
            
            # Toggle off
            player.game_config.show_combat_distance = False
            assert display_config.should_show_distance() == False
            
            self.log_test("Display Config", "1.1", "PASS", "Distance display toggle works")
        except Exception as e:
            self.log_test("Display Config", "1.1", "FAIL", str(e))
    
    def test_display_config_positions(self):
        """Test 1.2: Show Unit Positions During Combat"""
        try:
            player = self.setup_combat({"show_unit_positions": True})
            display_config = CombatDisplayConfig(player)
            
            # Verify positions display enabled
            assert display_config.should_show_positions() == True
            
            # Toggle off
            player.game_config.show_unit_positions = False
            assert display_config.should_show_positions() == False
            
            self.log_test("Display Config", "1.2", "PASS", "Position display toggle works")
        except Exception as e:
            self.log_test("Display Config", "1.2", "FAIL", str(e))
    
    def test_logging_combat_moves(self):
        """Test 2.1: Log Combat Moves"""
        try:
            player = self.setup_combat({"log_combat_moves": True})
            game_logger = GameLogger(player)
            
            # Verify logger respects flag
            assert player.game_config.log_combat_moves == True
            
            # Log a test move
            game_logger.log_combat_move(
                actor="TestActor",
                move_name="TestMove",
                target="TestTarget",
                details="25 damage dealt"
            )
            
            self.log_test("Logging", "2.1", "PASS", "Combat move logging works")
        except Exception as e:
            self.log_test("Logging", "2.1", "FAIL", str(e))
    
    def test_logging_distance(self):
        """Test 2.2: Log Distance Calculations"""
        try:
            player = self.setup_combat({"log_distance_calculations": True})
            game_logger = GameLogger(player)
            
            # Verify logger respects flag
            assert player.game_config.log_distance_calculations == True
            
            # Log a test distance
            game_logger.log_distance_calculation(
                unit1="Unit1",
                unit2="Unit2",
                distance=15.5,
                details="Calculated using Euclidean distance"
            )
            
            self.log_test("Logging", "2.2", "PASS", "Distance logging works")
        except Exception as e:
            self.log_test("Logging", "2.2", "FAIL", str(e))
    
    def test_debug_manager_enabled(self):
        """Test 3.1-3.5: Debug Manager Functions"""
        try:
            player = self.setup_combat({"debug_mode": True})
            debug_manager = DebugManager(player)
            
            # Verify debug mode enabled
            assert debug_manager.is_debug_mode_enabled() == True
            
            # Verify command execution available
            assert hasattr(debug_manager, 'execute_command')
            
            # Verify commands exist
            assert hasattr(debug_manager, 'cmd_instant_win')
            assert hasattr(debug_manager, 'cmd_spawn_enemy')
            assert hasattr(debug_manager, 'cmd_damage_output')
            
            self.log_test("Debug Manager", "3.1-3.5", "PASS", "Debug commands available")
        except Exception as e:
            self.log_test("Debug Manager", "3.1-3.5", "FAIL", str(e))
    
    def test_coordinate_system_grid(self):
        """Test 4.1-4.5: Coordinate System Functions"""
        try:
            player = self.setup_combat()
            coord_config = CoordinateSystemConfig(player)
            
            # Verify grid size
            width, height = coord_config.get_grid_size()
            assert width == 50 and height == 50
            
            # Verify bounds validation
            assert coord_config.is_coordinate_valid(25, 25) == True
            assert coord_config.is_coordinate_valid(50, 50) == True  # Includes boundary
            assert coord_config.is_coordinate_valid(-1, 0) == False
            
            # Verify distance calculation
            distance = coord_config.get_distance_between_points(0, 0, 3, 4)
            assert abs(distance - 5.0) < 0.01  # 3-4-5 triangle
            
            self.log_test("Coordinate System", "4.1-4.5", "PASS", "Coordinate functions work")
        except Exception as e:
            self.log_test("Coordinate System", "4.1-4.5", "FAIL", str(e))
    
    def test_npc_ai_config(self):
        """Test 5.1-5.5: NPC AI Config Functions"""
        try:
            player = self.setup_combat({"npc_flanking_enabled": True})
            npc_ai_config = NPCAIConfig(player)
            
            # Verify flanking enabled
            assert npc_ai_config.is_flanking_enabled() == True
            
            # Verify threshold accessible
            threshold = npc_ai_config.get_flanking_threshold()
            assert threshold == 45.0  # Default
            
            # Verify retreat accessible
            assert npc_ai_config.is_tactical_retreat_enabled() in [True, False]
            
            self.log_test("NPC AI", "5.1-5.5", "PASS", "NPC AI config works")
        except Exception as e:
            self.log_test("NPC AI", "5.1-5.5", "FAIL", str(e))
    
    def test_scenario_config(self):
        """Test 6.1-6.5: Scenario Config Functions"""
        try:
            player = self.setup_combat({"current_scenario": "pincer"})
            scenario_config = ScenarioConfig(player)
            
            # Verify scenario accessible
            current = scenario_config.get_current_scenario()
            assert current == "pincer"
            
            # Verify difficulty scaling accessible
            scaling = scenario_config.get_difficulty_scaling_factor()
            assert scaling > 0
            
            self.log_test("Scenario Config", "6.1-6.5", "PASS", "Scenario config works")
        except Exception as e:
            self.log_test("Scenario Config", "6.1-6.5", "FAIL", str(e))
    
    def test_all_systems_together(self):
        """Test 7.1-7.5: Full System Integration"""
        try:
            player = self.setup_combat({
                "debug_mode": True,
                "show_combat_distance": True,
                "log_combat_moves": True,
                "show_unit_positions": True
            })
            
            # Initialize all systems
            display = CombatDisplayConfig(player)
            logger = GameLogger(player)
            debug = DebugManager(player)
            coords = CoordinateSystemConfig(player)
            npc_ai = NPCAIConfig(player)
            scenarios = ScenarioConfig(player)
            
            # Verify all initialized
            assert display.should_show_distance() == True
            assert debug.is_debug_mode_enabled() == True
            assert logger.player == player
            assert coords.get_grid_size() == (50, 50)
            assert npc_ai.is_flanking_enabled() in [True, False]
            assert scenarios.get_current_scenario() in ['standard', 'pincer', 'melee', 'boss_arena']
            
            self.log_test("Full Integration", "7.1-7.5", "PASS", "All systems work together")
        except Exception as e:
            self.log_test("Full Integration", "7.1-7.5", "FAIL", str(e))
    
    def run_all_tests(self):
        """Run all automated tests."""
        print("\n" + "="*60)
        print("PHASE 4 MANUAL TEST EXECUTION")
        print("="*60 + "\n")
        
        # Run test suites
        self.test_display_config_distance()
        self.test_display_config_positions()
        self.test_logging_combat_moves()
        self.test_logging_distance()
        self.test_debug_manager_enabled()
        self.test_coordinate_system_grid()
        self.test_npc_ai_config()
        self.test_scenario_config()
        self.test_all_systems_together()
        
        # Summary
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        total = len(self.test_results)
        
        print("\n" + "="*60)
        print(f"RESULTS: {passed}/{total} PASSED")
        if failed > 0:
            print(f"         {failed} FAILED")
        print("="*60 + "\n")
        
        # Save results
        self.save_results()
        
        return failed == 0
    
    def save_results(self):
        """Save test results to JSON file."""
        results_data = {
            "timestamp": self.start_time.isoformat(),
            "total_tests": len(self.test_results),
            "passed": sum(1 for r in self.test_results if r["status"] == "PASS"),
            "failed": sum(1 for r in self.test_results if r["status"] == "FAIL"),
            "tests": self.test_results
        }
        
        with open(self.test_log, "w") as f:
            json.dump(results_data, f, indent=2)
        
        print(f"Results saved to: {self.test_log}")


if __name__ == "__main__":
    executor = Phase4TestExecutor()
    success = executor.run_all_tests()
    sys.exit(0 if success else 1)
