"""Unit tests for src/display_config.py.

Coverage targets:
  - CombatDisplayConfig: all should_show_* methods (with and without game_config)
  - display_enemy_status: all conditional branches
  - display_all_enemies: empty list, single enemy, multiple enemies
  - display_damage_modifier_info: range/melee/positioning branches
  - display_accuracy_modifier_info: speed and fatigue branches
  - display_full_coordinate_grid: no game_config, with positions
  - format_enemy_list_for_targeting: distance, position, hp branches
"""

import pathlib
import sys
from unittest.mock import MagicMock

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.display_config import (
    CombatDisplayConfig,
    display_enemy_status,
    display_all_enemies,
    display_damage_modifier_info,
    display_accuracy_modifier_info,
    display_full_coordinate_grid,
    format_enemy_list_for_targeting,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game_config(**kwargs):
    cfg = MagicMock()
    cfg.show_combat_distance = kwargs.get("show_combat_distance", True)
    cfg.show_unit_positions = kwargs.get("show_unit_positions", True)
    cfg.show_facing_directions = kwargs.get("show_facing_directions", True)
    cfg.show_damage_modifiers = kwargs.get("show_damage_modifiers", True)
    cfg.show_accuracy_modifiers = kwargs.get("show_accuracy_modifiers", True)
    cfg.show_coordinate_display = kwargs.get("show_coordinate_display", True)
    return cfg


def _make_player(**kwargs):
    player = MagicMock()
    player.name = "Jean"
    player.game_config = kwargs.get("game_config", None)
    player.combat_list = kwargs.get("combat_list", [])
    player.combat_list_allies = kwargs.get("combat_list_allies", [])
    player.combat_proximity = kwargs.get("combat_proximity", {})
    player.combat_position = kwargs.get("combat_position", None)
    player.speed = kwargs.get("speed", 10)
    player.finesse = kwargs.get("finesse", 10)
    player.fatigue = kwargs.get("fatigue", 100)
    player.maxfatigue = kwargs.get("maxfatigue", 200)
    return player


def _make_pos(x=5, y=3, facing_name="North"):
    pos = MagicMock()
    pos.x = x
    pos.y = y
    pos.facing = MagicMock()
    pos.facing.name = facing_name
    return pos


def _make_enemy(name="Slime", hp=80, maxhp=100, finesse=5):
    enemy = MagicMock()
    enemy.name = name
    enemy.hp = hp
    enemy.maxhp = maxhp
    enemy.finesse = finesse
    enemy.combat_position = None
    return enemy


# ---------------------------------------------------------------------------
# CombatDisplayConfig
# ---------------------------------------------------------------------------


class TestCombatDisplayConfig:
    def test_should_show_distance_no_game_config_defaults_true(self):
        player = _make_player(game_config=None)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_distance() is True

    def test_should_show_distance_respects_config(self):
        gc = _make_game_config(show_combat_distance=False)
        player = _make_player(game_config=gc)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_distance() is False

    def test_should_show_positions_no_game_config_defaults_true(self):
        player = _make_player(game_config=None)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_positions() is True

    def test_should_show_positions_respects_config(self):
        gc = _make_game_config(show_unit_positions=False)
        player = _make_player(game_config=gc)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_positions() is False

    def test_should_show_facing_no_game_config_defaults_true(self):
        player = _make_player(game_config=None)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_facing() is True

    def test_should_show_facing_respects_config(self):
        gc = _make_game_config(show_facing_directions=False)
        player = _make_player(game_config=gc)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_facing() is False

    def test_should_show_damage_modifiers_no_game_config_defaults_true(self):
        player = _make_player(game_config=None)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_damage_modifiers() is True

    def test_should_show_damage_modifiers_respects_config(self):
        gc = _make_game_config(show_damage_modifiers=False)
        player = _make_player(game_config=gc)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_damage_modifiers() is False

    def test_should_show_accuracy_modifiers_no_game_config_defaults_true(self):
        player = _make_player(game_config=None)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_accuracy_modifiers() is True

    def test_should_show_accuracy_modifiers_respects_config(self):
        gc = _make_game_config(show_accuracy_modifiers=False)
        player = _make_player(game_config=gc)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_accuracy_modifiers() is False

    def test_should_show_coordinate_display_no_game_config_defaults_true(self):
        player = _make_player(game_config=None)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_coordinate_display() is True

    def test_should_show_coordinate_display_respects_config(self):
        gc = _make_game_config(show_coordinate_display=False)
        player = _make_player(game_config=gc)
        cfg = CombatDisplayConfig(player)
        assert cfg.should_show_coordinate_display() is False


# ---------------------------------------------------------------------------
# display_enemy_status
# ---------------------------------------------------------------------------


class TestDisplayEnemyStatus:
    def _make_config(self, **flags):
        player = _make_player(game_config=_make_game_config(**flags))
        return CombatDisplayConfig(player)

    def test_returns_string(self):
        enemy = _make_enemy()
        cfg = self._make_config()
        result = display_enemy_status(enemy, cfg)
        assert isinstance(result, str)

    def test_contains_enemy_name(self):
        enemy = _make_enemy(name="Kobold")
        cfg = self._make_config()
        result = display_enemy_status(enemy, cfg)
        assert "Kobold" in result

    def test_hp_high_not_red(self):
        enemy = _make_enemy(hp=80, maxhp=100)
        cfg = self._make_config()
        result = display_enemy_status(enemy, cfg)
        assert "HP: 80%" in result

    def test_hp_low_25pct(self):
        enemy = _make_enemy(hp=20, maxhp=100)
        cfg = self._make_config()
        result = display_enemy_status(enemy, cfg)
        assert "HP: 20%" in result

    def test_hp_zero_maxhp(self):
        enemy = _make_enemy(hp=0, maxhp=0)
        cfg = self._make_config()
        result = display_enemy_status(enemy, cfg)
        assert "HP: 0%" in result

    def test_shows_position_when_configured(self):
        enemy = _make_enemy()
        enemy.combat_position = _make_pos(x=7, y=2)
        gc = _make_game_config(show_unit_positions=True)
        player = _make_player(game_config=gc)
        cfg = CombatDisplayConfig(player)
        result = display_enemy_status(enemy, cfg)
        assert "7" in result
        assert "2" in result

    def test_hides_position_when_not_configured(self):
        enemy = _make_enemy()
        enemy.combat_position = _make_pos(x=7, y=2)
        gc = _make_game_config(show_unit_positions=False)
        player = _make_player(game_config=gc)
        cfg = CombatDisplayConfig(player)
        result = display_enemy_status(enemy, cfg)
        assert "(7, 2)" not in result

    def test_shows_distance_when_configured(self):
        enemy = _make_enemy()
        gc = _make_game_config(show_combat_distance=True)
        player = _make_player(game_config=gc, combat_proximity={enemy: 12})
        cfg = CombatDisplayConfig(player)
        result = display_enemy_status(enemy, cfg)
        assert "12" in result

    def test_hides_distance_when_not_configured(self):
        enemy = _make_enemy()
        gc = _make_game_config(show_combat_distance=False)
        player = _make_player(game_config=gc, combat_proximity={enemy: 12})
        cfg = CombatDisplayConfig(player)
        result = display_enemy_status(enemy, cfg)
        assert "Dist: 12" not in result


# ---------------------------------------------------------------------------
# display_all_enemies
# ---------------------------------------------------------------------------


class TestDisplayAllEnemies:
    def test_no_enemies_returns_no_enemies(self):
        player = _make_player(combat_list=[])
        result = display_all_enemies(player)
        assert result == "No enemies"

    def test_creates_display_config_when_none_given(self):
        player = _make_player(combat_list=[])
        result = display_all_enemies(player, display_config=None)
        assert result == "No enemies"

    def test_single_enemy_includes_index(self):
        enemy = _make_enemy(name="Bat")
        player = _make_player(combat_list=[enemy])
        result = display_all_enemies(player)
        assert "1." in result
        assert "Bat" in result

    def test_multiple_enemies_numbered(self):
        e1 = _make_enemy(name="Slime")
        e2 = _make_enemy(name="Bat")
        player = _make_player(combat_list=[e1, e2])
        result = display_all_enemies(player)
        assert "1." in result
        assert "2." in result
        assert "Slime" in result
        assert "Bat" in result


# ---------------------------------------------------------------------------
# display_damage_modifier_info
# ---------------------------------------------------------------------------


class TestDisplayDamageModifierInfo:
    def test_returns_empty_when_modifiers_disabled(self):
        gc = _make_game_config(show_damage_modifiers=False)
        attacker = _make_player(game_config=gc)
        defender = _make_enemy()
        result = display_damage_modifier_info(attacker, defender, 20)
        assert result == ""

    def test_returns_empty_when_no_modifiers_apply(self):
        gc = _make_game_config(show_damage_modifiers=True)
        attacker = _make_player(game_config=gc)
        attacker.combat_proximity = {}
        attacker.combat_position = None
        defender = _make_enemy()
        defender.combat_position = None
        result = display_damage_modifier_info(attacker, defender, 20)
        assert result == ""

    def test_range_modifier_applied_when_far(self):
        gc = _make_game_config(show_damage_modifiers=True)
        attacker = _make_player(game_config=gc)
        defender = _make_enemy()
        attacker.combat_proximity = {defender: 35}  # > 30
        attacker.combat_position = None
        defender.combat_position = None
        result = display_damage_modifier_info(attacker, defender, 20)
        assert "Range" in result

    def test_melee_modifier_applied_when_close(self):
        gc = _make_game_config(show_damage_modifiers=True)
        attacker = _make_player(game_config=gc)
        defender = _make_enemy()
        attacker.combat_proximity = {defender: 3}  # < 5
        attacker.combat_position = None
        defender.combat_position = None
        result = display_damage_modifier_info(attacker, defender, 20)
        assert "Melee" in result

    def test_creates_display_config_when_none(self):
        attacker = _make_player(game_config=None)
        defender = _make_enemy()
        attacker.combat_proximity = {}
        attacker.combat_position = None
        defender.combat_position = None
        result = display_damage_modifier_info(attacker, defender, 20, display_config=None)
        # Returns empty (no config) — should not crash
        assert isinstance(result, str)

    def test_position_modifier_when_both_have_combat_position(self):
        gc = _make_game_config(show_damage_modifiers=True)
        attacker = _make_player(game_config=gc)
        attacker.combat_position = _make_pos()
        defender = _make_enemy()
        defender.combat_position = _make_pos(x=10, y=10)
        attacker.combat_proximity = {}
        result = display_damage_modifier_info(attacker, defender, 20)
        assert "Standard" in result


# ---------------------------------------------------------------------------
# display_accuracy_modifier_info
# ---------------------------------------------------------------------------


class TestDisplayAccuracyModifierInfo:
    def test_returns_empty_when_modifiers_disabled(self):
        gc = _make_game_config(show_accuracy_modifiers=False)
        attacker = _make_player(game_config=gc)
        defender = _make_enemy()
        result = display_accuracy_modifier_info(attacker, defender, 80)
        assert result == ""

    def test_returns_empty_when_no_modifiers_apply(self):
        gc = _make_game_config(show_accuracy_modifiers=True)
        attacker = _make_player(game_config=gc, speed=10, fatigue=100, maxfatigue=200)
        defender = _make_enemy(finesse=10)
        defender.speed = 10
        result = display_accuracy_modifier_info(attacker, defender, 80)
        assert result == ""

    def test_speed_bonus_when_much_faster(self):
        gc = _make_game_config(show_accuracy_modifiers=True)
        attacker = _make_player(game_config=gc, speed=20, fatigue=100, maxfatigue=200)
        defender = _make_enemy()
        defender.speed = 10  # attacker is 10 faster (> 5)
        result = display_accuracy_modifier_info(attacker, defender, 80)
        assert "Speed Bonus" in result

    def test_speed_penalty_when_much_slower(self):
        gc = _make_game_config(show_accuracy_modifiers=True)
        attacker = _make_player(game_config=gc, speed=5, fatigue=100, maxfatigue=200)
        defender = _make_enemy()
        defender.speed = 15  # defender 10 faster (< -5)
        result = display_accuracy_modifier_info(attacker, defender, 80)
        assert "Speed Penalty" in result

    def test_fatigue_penalty_when_exhausted(self):
        gc = _make_game_config(show_accuracy_modifiers=True)
        attacker = _make_player(game_config=gc, speed=10, fatigue=20, maxfatigue=200)
        defender = _make_enemy()
        defender.speed = 10
        result = display_accuracy_modifier_info(attacker, defender, 80)
        assert "Fatigued" in result

    def test_creates_config_when_none(self):
        attacker = _make_player(game_config=None, speed=10, fatigue=100, maxfatigue=200)
        defender = _make_enemy()
        defender.speed = 10
        result = display_accuracy_modifier_info(
            attacker, defender, 80, display_config=None
        )
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# display_full_coordinate_grid
# ---------------------------------------------------------------------------


class TestDisplayFullCoordinateGrid:
    def test_returns_empty_when_display_disabled(self):
        gc = _make_game_config(show_coordinate_display=False)
        player = _make_player(game_config=gc)
        result = display_full_coordinate_grid(player)
        assert result == ""

    def test_returns_empty_when_no_game_config(self):
        player = _make_player(game_config=None)
        result = display_full_coordinate_grid(player)
        assert result == ""

    def test_shows_grid_with_units(self):
        gc = _make_game_config(show_coordinate_display=True)
        ally = MagicMock()
        ally.name = "Jean"
        ally.combat_position = _make_pos(x=0, y=0)
        enemy = MagicMock()
        enemy.name = "Slime"
        enemy.combat_position = _make_pos(x=5, y=3)
        player = _make_player(
            game_config=gc,
            combat_list=[enemy],
            combat_list_allies=[ally],
        )
        result = display_full_coordinate_grid(player)
        assert "Combat Grid" in result
        assert "Jean" in result
        assert "Slime" in result

    def test_creates_config_when_none(self):
        gc = _make_game_config(show_coordinate_display=False)
        player = _make_player(game_config=gc)
        result = display_full_coordinate_grid(player, display_config=None)
        assert result == ""

    def test_skips_units_without_positions(self):
        gc = _make_game_config(show_coordinate_display=True)
        enemy = MagicMock()
        enemy.name = "Ghost"
        enemy.combat_position = None
        player = _make_player(
            game_config=gc,
            combat_list=[enemy],
            combat_list_allies=[],
        )
        result = display_full_coordinate_grid(player)
        # Grid header should appear but Ghost has no position to show
        assert "Combat Grid" in result
        assert "Ghost" not in result


# ---------------------------------------------------------------------------
# format_enemy_list_for_targeting
# ---------------------------------------------------------------------------


class TestFormatEnemyListForTargeting:
    def test_returns_string_with_header(self):
        player = _make_player(combat_list=[])
        result = format_enemy_list_for_targeting(player)
        assert "Available Targets" in result

    def test_single_enemy_shows_name(self):
        enemy = _make_enemy(name="Goblin", hp=60, maxhp=100)
        player = _make_player(combat_list=[enemy])
        result = format_enemy_list_for_targeting(player)
        assert "Goblin" in result

    def test_shows_distance_when_enabled(self):
        gc = _make_game_config(show_combat_distance=True)
        enemy = _make_enemy(name="Bat")
        player = _make_player(
            game_config=gc,
            combat_list=[enemy],
            combat_proximity={enemy: 15},
        )
        result = format_enemy_list_for_targeting(player)
        assert "15" in result

    def test_hides_distance_when_disabled(self):
        gc = _make_game_config(show_combat_distance=False)
        enemy = _make_enemy(name="Bat")
        player = _make_player(
            game_config=gc,
            combat_list=[enemy],
            combat_proximity={enemy: 15},
        )
        result = format_enemy_list_for_targeting(player)
        assert "[15" not in result

    def test_shows_position_when_enabled(self):
        gc = _make_game_config(show_unit_positions=True)
        enemy = _make_enemy(name="Goblin")
        enemy.combat_position = _make_pos(x=3, y=7)
        player = _make_player(game_config=gc, combat_list=[enemy])
        result = format_enemy_list_for_targeting(player)
        assert "3" in result
        assert "7" in result

    def test_hides_position_when_disabled(self):
        gc = _make_game_config(show_unit_positions=False)
        enemy = _make_enemy(name="Goblin")
        enemy.combat_position = _make_pos(x=3, y=7)
        player = _make_player(game_config=gc, combat_list=[enemy])
        result = format_enemy_list_for_targeting(player)
        assert "@(3,7)" not in result

    def test_hp_shown_as_percentage(self):
        enemy = _make_enemy(hp=30, maxhp=100)
        player = _make_player(combat_list=[enemy])
        result = format_enemy_list_for_targeting(player)
        assert "HP:30%" in result

    def test_hp_zero_maxhp_safe(self):
        enemy = _make_enemy(hp=0, maxhp=0)
        player = _make_player(combat_list=[enemy])
        result = format_enemy_list_for_targeting(player)
        assert "HP:0%" in result

    def test_creates_config_when_none(self):
        enemy = _make_enemy(name="Slime")
        player = _make_player(combat_list=[enemy])
        result = format_enemy_list_for_targeting(player, display_config=None)
        assert "Slime" in result

    def test_multiple_enemies_all_shown(self):
        e1 = _make_enemy(name="Rat")
        e2 = _make_enemy(name="Bat")
        player = _make_player(combat_list=[e1, e2])
        result = format_enemy_list_for_targeting(player)
        assert "Rat" in result
        assert "Bat" in result
