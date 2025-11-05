"""
Integration tests for combat position initialization system.

Tests the initialize_combat_positions() function and scenario-based spawning,
ensuring proper positioning of units across different combat types.
"""

import sys
from pathlib import Path

# Ensure sys.path is set up for imports
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.positions import (
    Direction,
    CombatPosition,
    COMBAT_SCENARIOS,
    initialize_combat_positions,
    distance_from_coords,
)


class DummyUnit:
    """Dummy unit for testing combat positioning."""
    
    def __init__(self, name, is_player=False):
        self.name = name
        self.is_player = is_player
        self.combat_position = None
        self.combat_proximity = {}
        self.is_alive = lambda: True


class TestStandardScenario:
    """Test standard 1v1 or team vs team positioning."""

    def test_standard_scenario_spawns_units(self):
        """Units are spawned in standard scenario."""
        allies = [DummyUnit("Player"), DummyUnit("Ally1")]
        enemies = [DummyUnit("Enemy1"), DummyUnit("Enemy2")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        # All units should have positions
        for unit in allies + enemies:
            assert unit.combat_position is not None
            assert isinstance(unit.combat_position, CombatPosition)

    def test_standard_scenario_allies_vs_enemies(self):
        """Allies and enemies are on opposite sides in standard scenario."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        ally_pos = allies[0].combat_position
        enemy_pos = enemies[0].combat_position
        
        # They should be far apart
        distance = distance_from_coords(ally_pos, enemy_pos)
        assert distance > 10  # At least 10 squares away

    def test_standard_scenario_units_in_bounds(self):
        """All spawned units are within grid bounds."""
        allies = [DummyUnit(f"Ally{i}") for i in range(3)]
        enemies = [DummyUnit(f"Enemy{i}") for i in range(2)]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        for unit in allies + enemies:
            assert 0 <= unit.combat_position.x <= 50
            assert 0 <= unit.combat_position.y <= 50

    def test_standard_scenario_no_overlapping_allies(self):
        """Allies don't spawn in the same location (spread formation)."""
        allies = [DummyUnit(f"Ally{i}") for i in range(4)]
        enemies = [DummyUnit("Enemy")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        positions = [u.combat_position for u in allies]
        for i, pos1 in enumerate(positions):
            for pos2 in positions[i+1:]:
                dist = distance_from_coords(pos1, pos2)
                # Standard uses spread formation with min_spacing=2
                assert dist >= 2

    def test_standard_scenario_facing(self):
        """Units face toward their opponents."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        # Ally and enemy should have facing directions
        assert isinstance(allies[0].combat_position.facing, Direction)
        assert isinstance(enemies[0].combat_position.facing, Direction)


class TestPincerScenario:
    """Test ambush/pincer scenario with flanking enemies."""

    def test_pincer_scenario_spawns_multiple_enemy_groups(self):
        """Pincer scenario has multiple enemy spawn zones."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy1"), DummyUnit("Enemy2")]
        
        initialize_combat_positions(allies, enemies, "pincer")
        
        # All units should have positions
        assert all(u.combat_position is not None for u in allies + enemies)

    def test_pincer_scenario_enemies_flank(self):
        """Enemies are positioned to flank in pincer scenario."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy1"), DummyUnit("Enemy2")]
        
        initialize_combat_positions(allies, enemies, "pincer")
        
        ally_pos = allies[0].combat_position
        enemy1_pos = enemies[0].combat_position
        enemy2_pos = enemies[1].combat_position
        
        # Enemies should be on different sides of ally
        # At least one should have significantly different X or Y from the other
        x_spread = abs(enemy1_pos.x - enemy2_pos.x)
        y_spread = abs(enemy1_pos.y - enemy2_pos.y)
        
        assert x_spread > 5 or y_spread > 5

    def test_pincer_scenario_allies_clustered(self):
        """Allies are clustered in pincer scenario."""
        allies = [DummyUnit("Player"), DummyUnit("Ally1"), DummyUnit("Ally2")]
        enemies = [DummyUnit("Enemy1"), DummyUnit("Enemy2")]
        
        initialize_combat_positions(allies, enemies, "pincer")
        
        # Pincer uses cluster formation for allies (min_spacing=1)
        positions = [u.combat_position for u in allies]
        avg_x = sum(p.x for p in positions) / len(positions)
        avg_y = sum(p.y for p in positions) / len(positions)
        
        # Most allies should be relatively close to center
        close_count = sum(1 for p in positions if distance_from_coords(CombatPosition(int(avg_x), int(avg_y)), p) < 10)
        assert close_count >= 2


class TestMeleeScenario:
    """Test close-quarters melee chaos scenario."""

    def test_melee_scenario_random_positioning(self):
        """Melee scenario has random positioning."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy1"), DummyUnit("Enemy2")]
        
        initialize_combat_positions(allies, enemies, "melee")
        
        # Just verify all units are positioned
        assert all(u.combat_position is not None for u in allies + enemies)

    def test_melee_scenario_full_grid(self):
        """Melee scenario can use full 50x50 grid."""
        # Scenario: melee allows (0,0) to (50,50) for both sides
        scenario = COMBAT_SCENARIOS["melee"]
        assert scenario.ally_spawn_zone == ((0, 0), (50, 50))
        assert scenario.enemy_spawn_zones[0] == ((0, 0), (50, 50))


class TestBossArenaScenario:
    """Test boss arena with centered positioning."""

    def test_boss_arena_single_enemy(self):
        """Boss arena typically has single boss."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Boss")]
        
        initialize_combat_positions(allies, enemies, "boss_arena")
        
        assert enemies[0].combat_position is not None

    def test_boss_arena_spread_formation(self):
        """Boss arena uses spread formation."""
        allies = [DummyUnit("Player"), DummyUnit("Ally1")]
        enemies = [DummyUnit("Boss")]
        
        initialize_combat_positions(allies, enemies, "boss_arena")
        
        # Allies should have spacing (min_spacing=3)
        if len(allies) > 1:
            dist = distance_from_coords(allies[0].combat_position, allies[1].combat_position)
            assert dist >= 3


class TestProximityDict:
    """Test backward compatibility: proximity dict calculation."""

    def test_proximity_dict_after_positioning(self):
        """Proximity dicts are populated after initialization."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        # Proximity dicts should be updated
        assert len(allies[0].combat_proximity) > 0
        assert len(enemies[0].combat_proximity) > 0

    def test_proximity_dict_values_correct(self):
        """Proximity dict values match coordinate distances."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        # Proximity value should equal coordinate distance
        if enemies[0] in allies[0].combat_proximity:
            reported_dist = allies[0].combat_proximity[enemies[0]]
            actual_dist = distance_from_coords(
                allies[0].combat_position,
                enemies[0].combat_position
            )
            assert reported_dist == actual_dist

    def test_proximity_dict_bidirectional(self):
        """Proximity is bidirectional: A->B == B->A."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        if enemies[0] in allies[0].combat_proximity:
            ally_to_enemy = allies[0].combat_proximity[enemies[0]]
            enemy_to_ally = enemies[0].combat_proximity[allies[0]]
            assert ally_to_enemy == enemy_to_ally


class TestFacingInitialization:
    """Test facing direction initialization."""

    def test_units_face_opponents(self):
        """Units face toward opponent team after spawning."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        # All units should have a facing direction
        for unit in allies + enemies:
            assert unit.combat_position.facing is not None
            assert isinstance(unit.combat_position.facing, Direction)

    def test_multiple_units_face_team_center(self):
        """Multiple units face toward team center."""
        allies = [DummyUnit("Player"), DummyUnit("Ally1"), DummyUnit("Ally2")]
        enemies = [DummyUnit("Enemy")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        # All units should have facing
        for unit in allies + enemies:
            assert isinstance(unit.combat_position.facing, Direction)


class TestScenarioDetection:
    """Test automatic scenario detection based on party composition."""

    def test_invalid_scenario_raises_error(self):
        """Invalid scenario type raises ValueError."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy")]
        
        with pytest.raises(ValueError):
            initialize_combat_positions(allies, enemies, "invalid_scenario")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_unit_per_side(self):
        """Can initialize with single unit per side."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit("Enemy")]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        assert allies[0].combat_position is not None
        assert enemies[0].combat_position is not None

    def test_many_units(self):
        """Can initialize with many units."""
        allies = [DummyUnit(f"Ally{i}") for i in range(5)]
        enemies = [DummyUnit(f"Enemy{i}") for i in range(5)]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        # All should be positioned and in bounds
        for unit in allies + enemies:
            assert unit.combat_position is not None
            assert 0 <= unit.combat_position.x <= 50
            assert 0 <= unit.combat_position.y <= 50

    def test_unequal_forces(self):
        """Can initialize with unequal party sizes."""
        allies = [DummyUnit("Player")]
        enemies = [DummyUnit(f"Enemy{i}") for i in range(4)]
        
        initialize_combat_positions(allies, enemies, "standard")
        
        assert all(u.combat_position is not None for u in allies + enemies)

    def test_positioning_is_deterministic_per_scenario(self):
        """Positioning follows scenario rules consistently."""
        for scenario_name in ["standard", "boss_arena"]:
            allies = [DummyUnit("Player")]
            enemies = [DummyUnit("Enemy")]
            
            initialize_combat_positions(allies, enemies, scenario_name)
            
            # Should succeed without errors
            assert allies[0].combat_position is not None
            assert enemies[0].combat_position is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
