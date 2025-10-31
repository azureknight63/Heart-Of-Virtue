"""Tests for display configuration module."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.display_config import CombatDisplayConfig, display_all_enemies, format_enemy_list_for_targeting  # type: ignore
from src.config_manager import GameConfig  # type: ignore
from src.player import Player  # type: ignore


def test_combat_display_config_defaults_without_config():
    """Test that display config uses sensible defaults without game_config."""
    player = Player()
    display_cfg = CombatDisplayConfig(player)
    
    # Should default to showing most things
    assert display_cfg.should_show_distance() is True
    assert display_cfg.should_show_positions() is True
    assert display_cfg.should_show_facing() is True
    # Should also show modifiers by default
    assert display_cfg.should_show_damage_modifiers() is True
    assert display_cfg.should_show_accuracy_modifiers() is True


def test_combat_display_config_respects_game_config():
    """Test that display config respects GameConfig flags."""
    player = Player()
    config = GameConfig()
    config.show_combat_distance = False
    config.show_unit_positions = False
    config.show_facing_directions = False
    config.show_damage_modifiers = True
    config.show_accuracy_modifiers = True
    
    player.game_config = config
    display_cfg = CombatDisplayConfig(player)
    
    # Should respect all flags
    assert display_cfg.should_show_distance() is False
    assert display_cfg.should_show_positions() is False
    assert display_cfg.should_show_facing() is False
    assert display_cfg.should_show_damage_modifiers() is True
    assert display_cfg.should_show_accuracy_modifiers() is True


def test_display_config_with_no_game_config_attribute():
    """Test that display config handles players without game_config gracefully."""
    player = Player()
    # Explicitly remove game_config if it exists
    if hasattr(player, 'game_config'):
        delattr(player, 'game_config')
    
    display_cfg = CombatDisplayConfig(player)
    
    # Should still return defaults
    assert display_cfg.should_show_distance() is True
    assert display_cfg.should_show_positions() is True


def test_display_all_enemies_without_enemies():
    """Test display of empty enemy list."""
    player = Player()
    display_cfg = CombatDisplayConfig(player)
    
    result = display_all_enemies(player, display_cfg)
    assert "No enemies" in result


def test_display_all_enemies_format():
    """Test that display_all_enemies produces formatted output."""
    from src.npc import NPC  # type: ignore
    
    player = Player()
    # Create a dummy enemy with proper initialization
    enemy = NPC("TestEnemy", "A test enemy", 10, aggro=1.0, exp_award=100)
    player.combat_list = [enemy]
    
    display_cfg = CombatDisplayConfig(player)
    result = display_all_enemies(player, display_cfg)
    
    # Should contain the enemy name
    assert "TestEnemy" in result
    # Should contain a numbered list
    assert "1." in result


def test_format_enemy_list_for_targeting():
    """Test targeting list format."""
    from src.npc import NPC  # type: ignore
    
    player = Player()
    enemy1 = NPC("Enemy1", "An enemy", 10, aggro=1.0, exp_award=100)
    enemy1.hp = 50
    enemy1.maxhp = 100
    enemy2 = NPC("Enemy2", "Another enemy", 15, aggro=1.0, exp_award=150)
    enemy2.hp = 100
    enemy2.maxhp = 100
    
    player.combat_list = [enemy1, enemy2]
    
    display_cfg = CombatDisplayConfig(player)
    result = format_enemy_list_for_targeting(player, display_cfg)
    
    # Should contain targeting header
    assert "Available Targets:" in result
    # Should contain enemy names
    assert "Enemy1" in result
    assert "Enemy2" in result
    # Should contain HP percentages
    assert "50%" in result
    assert "100%" in result


def test_display_config_created_automatically_if_not_provided():
    """Test that display functions create CombatDisplayConfig if not provided."""
    player = Player()
    
    # Should not raise error even without providing display_config
    result = display_all_enemies(player)
    assert isinstance(result, str)


def test_display_config_with_coordinate_display_flag():
    """Test coordinate display flag in game_config."""
    player = Player()
    config = GameConfig()
    config.show_coordinate_display = True
    player.game_config = config
    
    display_cfg = CombatDisplayConfig(player)
    assert display_cfg.should_show_coordinate_display() is True
    
    # Test with flag disabled
    config.show_coordinate_display = False
    assert display_cfg.should_show_coordinate_display() is False


def test_display_config_damage_modifiers_defaults_to_true():
    """Test that damage modifiers default to showing (per GameConfig defaults)."""
    player = Player()
    config = GameConfig()
    # Don't explicitly set - should use default
    player.game_config = config
    
    display_cfg = CombatDisplayConfig(player)
    # Should be True by default (per GameConfig dataclass)
    assert display_cfg.should_show_damage_modifiers() is True


def test_display_config_accuracy_modifiers_defaults_to_true():
    """Test that accuracy modifiers default to showing (per GameConfig defaults)."""
    player = Player()
    config = GameConfig()
    # Don't explicitly set - should use default
    player.game_config = config
    
    display_cfg = CombatDisplayConfig(player)
    # Should be True by default (per GameConfig dataclass)
    assert display_cfg.should_show_accuracy_modifiers() is True
