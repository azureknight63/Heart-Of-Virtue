"""
Coverage tests for src/scenario_config.py — small remaining gaps.

Uncovered lines: 107, 233, 257, 279-283, 295, 312, 327, 369, 431, 436, 441, 446

These correspond to:
- ScenarioConfig.get_next_scenario() when rotation disabled
- ScenarioConfig.advance_scenario() when rotation disabled + update config
- DifficultyProgressionManager methods: apply_difficulty_to_npc_stats,
  get_enemy_count_by_difficulty, get_loot_multiplier, get_experience_multiplier,
  increment_difficulty_after_combat
- ScenarioValidator.validate_all_settings() various issue branches
"""

from unittest.mock import MagicMock

import pytest

from src.scenario_config import (
    DifficultyProgressionManager,
    ScenarioConfig,
    ScenarioValidator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    scenario="standard",
    rotation_enabled=False,
    rotation_order=None,
    starting_diff=1.0,
    scaling=0.1,
    max_rounds=50,
    combat_count=0,
):
    player = MagicMock()
    player.game_config = None
    cfg = ScenarioConfig(player)
    if hasattr(cfg, "_scenario"):
        cfg._scenario = scenario
    if hasattr(cfg, "rotation_enabled"):
        cfg.rotation_enabled = rotation_enabled
    if rotation_order is not None and hasattr(cfg, "scenario_order"):
        cfg.scenario_order = rotation_order
    # Force values via the player's game_config mock where needed
    cfg._starting_difficulty = starting_diff
    cfg._scaling = scaling
    cfg._max_rounds = max_rounds
    cfg.combat_count = combat_count
    return cfg, player


# ===========================================================================
# ScenarioConfig
# ===========================================================================


class TestScenarioConfigGetNextScenario:
    def test_get_next_scenario_rotation_disabled(self):
        """When rotation is disabled, get_next_scenario returns current scenario."""
        cfg, _ = _make_config()
        # Disable rotation explicitly
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cfg, "is_scenario_rotation_enabled", lambda: False)
            mp.setattr(cfg, "get_current_scenario", lambda: "standard")
            result = cfg.get_next_scenario()
        assert result == "standard"

    def test_get_next_scenario_rotation_enabled_cycles(self):
        cfg, _ = _make_config()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cfg, "is_scenario_rotation_enabled", lambda: True)
            mp.setattr(cfg, "scenario_order", ["standard", "boss_arena", "pincer"])
            cfg.current_rotation_index = 0
            result = cfg.get_next_scenario()
        assert result == "boss_arena"


class TestScenarioConfigAdvanceScenario:
    def test_advance_scenario_rotation_disabled(self):
        """When rotation disabled, advance returns current scenario unchanged."""
        cfg, _ = _make_config()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cfg, "is_scenario_rotation_enabled", lambda: False)
            mp.setattr(cfg, "get_current_scenario", lambda: "standard")
            result = cfg.advance_scenario()
        assert result == "standard"

    def test_advance_scenario_updates_rotation_index(self):
        cfg, _ = _make_config()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cfg, "is_scenario_rotation_enabled", lambda: True)
            mp.setattr(cfg, "scenario_order", ["standard", "boss_arena", "pincer"])
            cfg.current_rotation_index = 0
            result = cfg.advance_scenario()
        assert result == "boss_arena"
        assert cfg.current_rotation_index == 1

    def test_advance_scenario_wraps_around(self):
        cfg, _ = _make_config()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cfg, "is_scenario_rotation_enabled", lambda: True)
            mp.setattr(cfg, "scenario_order", ["standard", "boss_arena"])
            cfg.current_rotation_index = 1
            result = cfg.advance_scenario()
        assert result == "standard"
        assert cfg.current_rotation_index == 0

    def test_advance_scenario_updates_game_config(self):
        cfg, player = _make_config()
        game_config = MagicMock()
        player.game_config = game_config
        cfg.player = player
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cfg, "is_scenario_rotation_enabled", lambda: True)
            mp.setattr(cfg, "scenario_order", ["standard", "boss_arena"])
            cfg.current_rotation_index = 0
            result = cfg.advance_scenario()
        assert game_config.current_scenario == "boss_arena"


class TestScenarioConfigGetAllScenarios:
    def test_get_all_scenarios_returns_copy(self):
        cfg, _ = _make_config()
        all_s = cfg.get_all_scenarios()
        assert isinstance(all_s, list)
        assert len(all_s) > 0

    def test_get_scenario_rotation_order_returns_list(self):
        cfg, _ = _make_config()
        order = cfg.get_scenario_rotation_order()
        assert isinstance(order, list)


# ===========================================================================
# DifficultyProgressionManager
# ===========================================================================


class TestDifficultyProgressionManager:
    def _make_dpm(self, starting_diff=1.0, combat_count=0, scaling=0.1):
        player = MagicMock()
        cfg = ScenarioConfig(player)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cfg, "get_starting_difficulty", lambda: starting_diff)
            mp.setattr(cfg, "get_difficulty_scaling_factor", lambda: scaling)
            mp.setattr(
                cfg,
                "calculate_current_difficulty",
                lambda: starting_diff + combat_count * scaling,
            )
        dpm = DifficultyProgressionManager(cfg)
        # Override methods directly
        dpm.scenario_config.get_starting_difficulty = lambda: starting_diff
        dpm.scenario_config.get_difficulty_scaling_factor = lambda: scaling
        dpm.scenario_config.calculate_current_difficulty = (
            lambda: starting_diff + combat_count * scaling
        )
        return dpm

    def test_get_difficulty_multiplier_normal(self):
        dpm = self._make_dpm(starting_diff=1.0, combat_count=5, scaling=0.1)
        mult = dpm.get_difficulty_multiplier()
        assert mult >= 1.0

    def test_get_difficulty_multiplier_zero_starting_diff(self):
        """Zero starting diff should return 1.0 (avoid division by zero)."""
        player = MagicMock()
        cfg = ScenarioConfig(player)
        cfg.get_starting_difficulty = lambda: 0
        cfg.calculate_current_difficulty = lambda: 1.0
        dpm = DifficultyProgressionManager(cfg)
        assert dpm.get_difficulty_multiplier() == 1.0

    def test_apply_difficulty_damage_stat(self):
        dpm = self._make_dpm()
        dpm.get_difficulty_multiplier = lambda: 1.5
        result = dpm.apply_difficulty_to_npc_stats(MagicMock(), "damage", 100)
        assert result == 150.0

    def test_apply_difficulty_maxhp_stat(self):
        dpm = self._make_dpm()
        dpm.get_difficulty_multiplier = lambda: 2.0
        result = dpm.apply_difficulty_to_npc_stats(MagicMock(), "maxhp", 200)
        assert result == 400.0

    def test_apply_difficulty_speed_stat(self):
        dpm = self._make_dpm()
        dpm.get_difficulty_multiplier = lambda: 1.5
        result = dpm.apply_difficulty_to_npc_stats(MagicMock(), "speed", 10)
        # Speed gets smaller boost: 10 * (1 + 0.5 * 0.5) = 12.5
        assert result == pytest.approx(12.5)

    def test_apply_difficulty_finesse_stat(self):
        dpm = self._make_dpm()
        dpm.get_difficulty_multiplier = lambda: 1.5
        result = dpm.apply_difficulty_to_npc_stats(MagicMock(), "finesse", 10)
        assert result == pytest.approx(12.5)

    def test_apply_difficulty_unknown_stat_unchanged(self):
        dpm = self._make_dpm()
        dpm.get_difficulty_multiplier = lambda: 2.0
        result = dpm.apply_difficulty_to_npc_stats(MagicMock(), "charisma", 5)
        assert result == 5

    def test_get_enemy_count_by_difficulty_uses_current(self):
        dpm = self._make_dpm()
        dpm.get_difficulty_multiplier = lambda: 1.0
        count = dpm.get_enemy_count_by_difficulty()
        assert count == 2

    def test_get_enemy_count_by_difficulty_explicit(self):
        dpm = self._make_dpm()
        count = dpm.get_enemy_count_by_difficulty(difficulty=2.0)
        assert count == 4

    def test_get_enemy_count_by_difficulty_clamped_max(self):
        dpm = self._make_dpm()
        count = dpm.get_enemy_count_by_difficulty(difficulty=100.0)
        assert count == 8

    def test_get_enemy_count_by_difficulty_clamped_min(self):
        dpm = self._make_dpm()
        count = dpm.get_enemy_count_by_difficulty(difficulty=0.0)
        assert count == 1

    def test_get_loot_multiplier_uses_current(self):
        dpm = self._make_dpm()
        dpm.get_difficulty_multiplier = lambda: 1.5
        loot = dpm.get_loot_multiplier()
        assert loot == 1.5

    def test_get_loot_multiplier_explicit(self):
        dpm = self._make_dpm()
        loot = dpm.get_loot_multiplier(difficulty=2.0)
        assert loot == 2.0

    def test_get_loot_multiplier_floor(self):
        dpm = self._make_dpm()
        loot = dpm.get_loot_multiplier(difficulty=0.0)
        assert loot == 0.5

    def test_get_experience_multiplier_uses_current(self):
        dpm = self._make_dpm()
        dpm.get_difficulty_multiplier = lambda: 1.3
        xp = dpm.get_experience_multiplier()
        assert xp == 1.3

    def test_get_experience_multiplier_explicit(self):
        dpm = self._make_dpm()
        xp = dpm.get_experience_multiplier(difficulty=2.5)
        assert xp == 2.5

    def test_increment_difficulty_after_combat(self):
        player = MagicMock()
        cfg = ScenarioConfig(player)
        cfg.increment_combat_count = lambda: 1
        cfg.calculate_current_difficulty = lambda: 1.1
        dpm = DifficultyProgressionManager(cfg)
        result = dpm.increment_difficulty_after_combat()
        assert result == 1.1


# ===========================================================================
# ScenarioValidator — validate_all_settings branches
# ===========================================================================


class TestScenarioValidatorAllSettings:
    def _make_valid_cfg(self):
        player = MagicMock()
        cfg = ScenarioConfig(player)
        return cfg

    def test_validate_all_settings_valid(self):
        cfg = self._make_valid_cfg()
        # Force all valid values
        cfg.get_current_scenario = lambda: "standard"
        cfg.is_scenario_valid = lambda x: True
        cfg.get_test_scenario = lambda: None
        cfg.get_starting_difficulty = lambda: 1.0
        cfg.get_difficulty_scaling_factor = lambda: 0.1
        cfg.get_max_rounds_before_auto_victory = lambda: 50
        validator = ScenarioValidator(cfg)
        is_valid, issues = validator.validate_all_settings()
        assert is_valid is True
        assert issues == []

    def test_validate_all_settings_invalid_current_scenario(self):
        cfg = self._make_valid_cfg()
        cfg.get_current_scenario = lambda: "invalid_scenario"
        cfg.is_scenario_valid = lambda x: x != "invalid_scenario"
        cfg.get_test_scenario = lambda: None
        cfg.get_starting_difficulty = lambda: 1.0
        cfg.get_difficulty_scaling_factor = lambda: 0.1
        cfg.get_max_rounds_before_auto_victory = lambda: 50
        validator = ScenarioValidator(cfg)
        is_valid, issues = validator.validate_all_settings()
        assert is_valid is False
        assert any("invalid_scenario" in i for i in issues)

    def test_validate_all_settings_invalid_test_scenario(self):
        cfg = self._make_valid_cfg()
        cfg.get_current_scenario = lambda: "standard"
        cfg.is_scenario_valid = lambda x: x == "standard"
        cfg.get_test_scenario = lambda: "bad_scenario"
        cfg.get_starting_difficulty = lambda: 1.0
        cfg.get_difficulty_scaling_factor = lambda: 0.1
        cfg.get_max_rounds_before_auto_victory = lambda: 50
        validator = ScenarioValidator(cfg)
        is_valid, issues = validator.validate_all_settings()
        assert is_valid is False
        assert any("bad_scenario" in i for i in issues)

    def test_validate_all_settings_negative_difficulty(self):
        cfg = self._make_valid_cfg()
        cfg.get_current_scenario = lambda: "standard"
        cfg.is_scenario_valid = lambda x: True
        cfg.get_test_scenario = lambda: None
        cfg.get_starting_difficulty = lambda: -1.0
        cfg.get_difficulty_scaling_factor = lambda: 0.1
        cfg.get_max_rounds_before_auto_victory = lambda: 50
        validator = ScenarioValidator(cfg)
        is_valid, issues = validator.validate_all_settings()
        assert is_valid is False
        assert any("negative" in i.lower() for i in issues)

    def test_validate_all_settings_negative_scaling(self):
        cfg = self._make_valid_cfg()
        cfg.get_current_scenario = lambda: "standard"
        cfg.is_scenario_valid = lambda x: True
        cfg.get_test_scenario = lambda: None
        cfg.get_starting_difficulty = lambda: 1.0
        cfg.get_difficulty_scaling_factor = lambda: -0.5
        cfg.get_max_rounds_before_auto_victory = lambda: 50
        validator = ScenarioValidator(cfg)
        is_valid, issues = validator.validate_all_settings()
        assert is_valid is False
        assert any("scaling" in i.lower() for i in issues)

    def test_validate_all_settings_zero_max_rounds(self):
        cfg = self._make_valid_cfg()
        cfg.get_current_scenario = lambda: "standard"
        cfg.is_scenario_valid = lambda x: True
        cfg.get_test_scenario = lambda: None
        cfg.get_starting_difficulty = lambda: 1.0
        cfg.get_difficulty_scaling_factor = lambda: 0.1
        cfg.get_max_rounds_before_auto_victory = lambda: 0
        validator = ScenarioValidator(cfg)
        is_valid, issues = validator.validate_all_settings()
        assert is_valid is False
        assert any("max_rounds" in i or "rounds" in i.lower() for i in issues)

    def test_validate_all_settings_with_valid_test_scenario(self):
        """Test scenario present and valid — should not add to issues."""
        cfg = self._make_valid_cfg()
        cfg.get_current_scenario = lambda: "standard"
        cfg.is_scenario_valid = lambda x: True
        cfg.get_test_scenario = lambda: "boss_arena"
        cfg.get_starting_difficulty = lambda: 1.0
        cfg.get_difficulty_scaling_factor = lambda: 0.1
        cfg.get_max_rounds_before_auto_victory = lambda: 50
        validator = ScenarioValidator(cfg)
        is_valid, issues = validator.validate_all_settings()
        assert is_valid is True
        assert issues == []


# ===========================================================================
# ScenarioValidator — other methods
# ===========================================================================


class TestScenarioValidatorOther:
    def _make_validator(self):
        player = MagicMock()
        cfg = ScenarioConfig(player)
        return ScenarioValidator(cfg)

    def test_valid_scenario_transition(self):
        v = self._make_validator()
        v.scenario_config.is_scenario_valid = lambda x: True
        ok, reason = v.is_valid_scenario_transition("standard", "boss_arena")
        assert ok is True

    def test_invalid_source_scenario(self):
        v = self._make_validator()
        v.scenario_config.is_scenario_valid = lambda x: x != "bad"
        ok, reason = v.is_valid_scenario_transition("bad", "standard")
        assert ok is False

    def test_invalid_target_scenario(self):
        v = self._make_validator()
        v.scenario_config.is_scenario_valid = lambda x: x != "bad"
        ok, reason = v.is_valid_scenario_transition("standard", "bad")
        assert ok is False

    def test_difficulty_level_negative(self):
        v = self._make_validator()
        ok, reason = v.is_valid_difficulty_level(-1.0)
        assert ok is False

    def test_difficulty_level_too_high(self):
        v = self._make_validator()
        ok, reason = v.is_valid_difficulty_level(101.0)
        assert ok is False

    def test_difficulty_level_valid(self):
        v = self._make_validator()
        ok, reason = v.is_valid_difficulty_level(1.5)
        assert ok is True

    def test_round_count_negative(self):
        v = self._make_validator()
        v.scenario_config.get_max_rounds_before_auto_victory = lambda: 50
        ok, reason = v.is_valid_round_count(-1)
        assert ok is False

    def test_round_count_exceeds_max(self):
        v = self._make_validator()
        v.scenario_config.get_max_rounds_before_auto_victory = lambda: 50
        ok, reason = v.is_valid_round_count(100)
        assert ok is False

    def test_round_count_valid(self):
        v = self._make_validator()
        v.scenario_config.get_max_rounds_before_auto_victory = lambda: 50
        ok, reason = v.is_valid_round_count(25)
        assert ok is True
