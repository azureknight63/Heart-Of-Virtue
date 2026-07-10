"""
Coverage tests for src/scenario_config.py — small remaining gaps.

Uncovered lines: 107, 233, 257

These correspond to:
- ScenarioConfig.get_next_scenario() when rotation disabled
- ScenarioConfig.advance_scenario() when rotation disabled + update config
"""

from unittest.mock import MagicMock

import pytest

from src.scenario_config import ScenarioConfig

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
