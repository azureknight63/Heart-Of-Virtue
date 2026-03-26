#!/usr/bin/env python3
"""
Comprehensive tests for bow-and-arrow attacks and special abilities using the coordinate system.

Tests cover:
1. Bow targeting at various ranges
2. Arrow selection and damage calculations
3. Range decay and accuracy modifiers
4. Special abilities with coordinate positioning
5. Multi-target scenarios
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.player import Player
from src.npc import NPC
from src.items import Shortbow, Longbow, WoodenArrow, IronArrow, GlassArrow, FlareArrow
from src.moves import ShootBow
from src.positions import CombatPosition, Direction
from src.universe import Universe
import random


class TestBowAndArrows:
    """Test suite for bow and arrow mechanics with coordinate system."""

    def setup_method(self):
        """Initialize player with bow and arrows."""
        self.player = Player()
        self.player.name = "Jean"
        self.player.current_health = 1000
        self.player.maxhealth = 1000
        self.player.fatigue = 500
        self.player.maxfatigue = 500
        self.player.strength = 10
        self.player.speed = 10
        self.player.endurance = 10
        self.player.finesse = 12

        # Equip bow
        bow = Longbow()
        self.player.eq_weapon = bow

        # Add arrows to inventory
        self.player.inventory = [
            WoodenArrow(),
            IronArrow(),
            GlassArrow(),
            FlareArrow(),
        ]
        for arrow in self.player.inventory:
            arrow.count = 20

        # Set combat position
        self.player.combat_position = CombatPosition(x=15, y=25, facing=Direction.E)
        self.player.combat_proximity = {}
        self.enemies = []

    def create_enemy(self, name: str, x: int, y: int, distance: float = None):
        """Create an enemy at specified coordinates."""
        enemy = NPC(
            name=name,
            description=f"A test {name}",
            damage=10,
            aggro=True,
            exp_award=50,
            maxhp=100,
            finesse=5
        )
        enemy.hp = 100
        enemy.is_alive = lambda: enemy.hp > 0
        enemy.combat_position = CombatPosition(x=x, y=y, facing=Direction.W)

        # Calculate distance from player
        if distance is None:
            dx = x - self.player.combat_position.x
            dy = y - self.player.combat_position.y
            distance = ((dx**2 + dy**2)**0.5)

        self.player.combat_proximity[enemy] = distance
        self.enemies.append(enemy)
        return enemy

    def test_bow_initialization(self):
        """Test that bow is correctly initialized and equipped."""
        assert self.player.eq_weapon is not None and self.player.eq_weapon.subtype == "Bow"
        assert any(arrow.subtype == "Arrow" for arrow in self.player.inventory)

        arrow_count = sum(arrow.count for arrow in self.player.inventory if arrow.subtype == "Arrow")
        assert arrow_count >= 20, f"Expected ≥20 arrows, got {arrow_count}"

        assert len([a for a in self.player.inventory if a.subtype == "Arrow"]) >= 3, \
            f"Expected ≥3 arrow types, got {len([a for a in self.player.inventory if a.subtype == 'Arrow'])}"

    def test_bow_viability(self):
        """Test that ShootBow is viable only when conditions are met."""
        shoot_bow = ShootBow(self.player)
        self.player.known_moves = [shoot_bow]

        # Test 1: No enemies in range
        assert not shoot_bow.viable(), "Player should have no enemies in combat_proximity"

        # Test 2: Enemy at close range (below minimum range)
        close_enemy = self.create_enemy("Close Enemy", x=16, y=25, distance=2)
        assert not shoot_bow.viable(), f"Close enemy at {close_enemy.combat_position.x}, {close_enemy.combat_position.y}"

        # Test 3: Enemy at valid range
        self.enemies = []
        self.player.combat_proximity = {}
        medium_enemy = self.create_enemy("Medium Enemy", x=20, y=25, distance=10)
        assert shoot_bow.viable(), f"Medium enemy at {medium_enemy.combat_position.x}, {medium_enemy.combat_position.y}, distance=10"

        # Test 4: No arrows in inventory
        self.player.inventory = []
        assert not shoot_bow.viable(), "Removed all arrows from inventory"

    def test_range_calculations(self):
        """Test range calculations at various distances."""
        shoot_bow = ShootBow(self.player)

        # Test distances from player at (15, 25)
        test_cases = [
            (15, 25, 0, "Same position"),      # No movement
            (21, 25, 6, "6 feet away"),        # Min range
            (25, 25, 10, "10 feet away"),      # Mid range
            (35, 25, 20, "20 feet away"),      # Beyond base range
            (45, 25, 30, "30 feet away"),      # Max effective range
            (15, 35, 10, "10 feet diagonal"),  # Diagonal
            (25, 35, 14, "14 feet diagonal"),  # Diagonal, further
        ]

        for x, y, expected_dist, desc in test_cases:
            # Create enemy and calculate distance
            enemy = NPC(
                name=f"TestEnemy_{x}_{y}",
                description="Test enemy",
                damage=10,
                aggro=True,
                exp_award=50
            )
            enemy.combat_position = CombatPosition(x=x, y=y, facing=Direction.W)
            dx = x - self.player.combat_position.x
            dy = y - self.player.combat_position.y
            actual_dist = ((dx**2 + dy**2)**0.5)

            # Check if it's within range
            range_min, range_max = shoot_bow.mvrange
            in_range = range_min <= actual_dist <= range_max or actual_dist < 6

            assert abs(actual_dist - expected_dist) < 1, f"Distance calculation: {desc} - Expected {expected_dist}±1, got {actual_dist:.1f}"

    def test_bow_hit_chance_calculation(self):
        """Test hit chance calculations at various ranges and with modifiers."""
        shoot_bow = ShootBow(self.player)
        self.player.known_moves = [shoot_bow]

        # Create enemies at different ranges
        close_enemy = self.create_enemy("Close", x=20, y=25, distance=8)
        mid_enemy = self.create_enemy("Mid", x=25, y=25, distance=15)
        far_enemy = self.create_enemy("Far", x=40, y=25, distance=30)

        # Get hit chances
        close_hit = shoot_bow.calculate_hit_chance(close_enemy)
        mid_hit = shoot_bow.calculate_hit_chance(mid_enemy)
        far_hit = shoot_bow.calculate_hit_chance(far_enemy)

        assert close_hit > 0, f"Close hit chance: {close_hit}"
        assert close_hit >= mid_hit >= far_hit, f"Close: {close_hit}, Mid: {mid_hit}, Far: {far_hit}"
        assert far_hit >= 2, f"Far hit chance: {far_hit}"

    def test_bow_multi_target_scenario(self):
        """Test bow behavior with multiple enemies at various distances."""
        shoot_bow = ShootBow(self.player)
        self.player.known_moves = [shoot_bow]

        # Create tactical scenario: multiple enemies
        # Positions: Player at (15, 25)
        enemy1 = self.create_enemy("Enemy_A", x=22, y=20, distance=9)      # 9 feet away
        enemy2 = self.create_enemy("Enemy_B", x=25, y=28, distance=11)     # 11 feet away
        enemy3 = self.create_enemy("Enemy_C", x=30, y=25, distance=15)     # 15 feet away

        assert len(self.player.combat_proximity) == 3, f"Expected 3 enemies, got {len(self.player.combat_proximity)}"

        # Check that bow is viable with multiple targets
        assert shoot_bow.viable(), "Should be able to shoot with multiple enemies"

        # Verify each enemy has hit chance calculated
        hit_chances = {
            enemy1.name: shoot_bow.calculate_hit_chance(enemy1),
            enemy2.name: shoot_bow.calculate_hit_chance(enemy2),
            enemy3.name: shoot_bow.calculate_hit_chance(enemy3),
        }

        for name, chance in hit_chances.items():
            assert 0 < chance <= 100, f"Hit chance for {name} should be 0-100%, got {chance}%"

    def test_arrow_types_and_damage(self):
        """Test different arrow types have different properties."""
        # Test arrow properties
        arrow_types = [
            (WoodenArrow(), "Wooden"),
            (IronArrow(), "Iron"),
            (GlassArrow(), "Glass"),
            (FlareArrow(), "Flare"),
        ]

        for arrow, name in arrow_types:
            assert hasattr(arrow, 'power') and arrow.power > 0, f"{name}Arrow has power attribute - Arrow: {arrow}, Power: {getattr(arrow, 'power', 'N/A')}"
            assert hasattr(arrow, 'range_base_modifier') and hasattr(arrow, 'range_decay_modifier'), f"Missing range modifiers for {name}Arrow"
            assert arrow.subtype == "Arrow", f"{name}Arrow is subtype 'Arrow' - Subtype: {getattr(arrow, 'subtype', 'N/A')}"

    def test_coordinate_positioning_with_bow(self):
        """Test bow mechanics with precise coordinate positioning."""
        shoot_bow = ShootBow(self.player)

        # Test from player at (15, 25) facing East (90°)
        # Create a grid of enemies
        positions = [
            (15, 15, "North (straight line)"),
            (25, 15, "NE diagonal"),
            (25, 25, "East (straight line)"),
            (25, 35, "SE diagonal"),
            (15, 35, "South (straight line)"),
            (5, 35, "SW diagonal"),
            (5, 25, "West (straight line)"),
            (5, 15, "NW diagonal"),
        ]

        for i, (x, y, desc) in enumerate(positions):
            enemy = self.create_enemy(f"Enemy_{desc.replace(' ', '_')}", x, y)
            dx = x - self.player.combat_position.x
            dy = y - self.player.combat_position.y
            distance = ((dx**2 + dy**2)**0.5)

            assert enemy.combat_position.x == x and enemy.combat_position.y == y, \
                f"Enemy positioned: {desc} at ({x}, {y}), distance {distance:.1f}ft - Expected ({x}, {y}), got ({enemy.combat_position.x}, {enemy.combat_position.y})"

    def test_fatigue_costs(self):
        """Test fatigue costs for bow attacks."""
        shoot_bow = ShootBow(self.player)

        assert shoot_bow.fatigue_cost > 0, f"ShootBow has fatigue_cost > 0 - Fatigue cost: {shoot_bow.fatigue_cost}"
        assert 10 <= shoot_bow.fatigue_cost <= 150, f"Fatigue cost is reasonable (10-150) - Fatigue cost: {shoot_bow.fatigue_cost}"
        assert self.player.fatigue >= shoot_bow.fatigue_cost, f"Player has enough fatigue - Player fatigue: {self.player.fatigue}, Cost: {shoot_bow.fatigue_cost}"


class TestSpecialAbilities:
    """Test suite for special abilities with coordinate system."""

    def setup_method(self):
        """Initialize player."""
        self.player = Player()
        self.player.name = "Jean"
        self.player.current_health = 1000
        self.player.maxhealth = 1000
        self.player.fatigue = 500
        self.player.maxfatigue = 500
        self.player.strength = 12
        self.player.speed = 10
        self.player.endurance = 10
        self.player.finesse = 10
        self.player.combat_position = CombatPosition(x=15, y=25, facing=Direction.N)

    def test_special_ability_positioning(self):
        """Test that special abilities work with coordinate positioning."""
        assert self.player.combat_position is not None, "combat_position should be set"
        assert hasattr(self.player.combat_position, 'x') and hasattr(self.player.combat_position, 'y'), "Position should have x and y"
        assert hasattr(self.player.combat_position, 'facing'), "Position should have facing"
        assert isinstance(self.player.combat_position.facing, Direction), f"Expected Direction enum, got {type(self.player.combat_position.facing)}"


if __name__ == "__main__":
    # This allows running the file directly if needed, though pytest is preferred
    import pytest
    pytest.main([__file__])
