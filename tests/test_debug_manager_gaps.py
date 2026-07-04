"""Additional coverage for src/debug_manager.py — closes gaps left by
tests/test_debug_manager.py: the default (no-config) branches of
should_debug_movement/damage_calc/accuracy/ai_decisions/npc_positions, the
debug-mode-disabled early returns for cmd_spawn_enemy/cmd_accuracy_info/
cmd_npc_decision_trace/cmd_performance_monitor/cmd_toggle_feature/
cmd_spawn_item/cmd_list_stats, display_ai_debug_info end to end (disabled,
enabled+details, and the cprint console-output branch), execute_command's
TypeError-triggers-no-arg-retry branch, and DebugValidator.validate_all_commands'
not-callable branch.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.debug_manager import DebugManager, DebugValidator  # type: ignore
from src.config_manager import GameConfig  # type: ignore
from src.player import Player  # type: ignore


def _enabled_manager(**config_overrides):
    player = Player()
    config = GameConfig()
    config.debug_mode = True
    for key, value in config_overrides.items():
        setattr(config, key, value)
    player.game_config = config
    return DebugManager(player)


def _disabled_manager():
    player = Player()
    player.game_config = None
    return DebugManager(player)


def test_should_debug_movement_defaults_false_without_config():
    assert _disabled_manager().should_debug_movement() is False


def test_should_debug_damage_calc_defaults_false_without_config():
    assert _disabled_manager().should_debug_damage_calc() is False


def test_should_debug_accuracy_defaults_false_without_config():
    assert _disabled_manager().should_debug_accuracy() is False


def test_should_debug_ai_decisions_defaults_false_without_config():
    assert _disabled_manager().should_debug_ai_decisions() is False


def test_should_debug_npc_positions_defaults_false_without_config():
    assert _disabled_manager().should_debug_npc_positions() is False


def test_cmd_spawn_enemy_disabled_returns_message():
    mgr = _disabled_manager()
    assert mgr.cmd_spawn_enemy("Slime", 3) == "Debug mode disabled"


def test_cmd_accuracy_info_disabled_returns_message():
    mgr = _disabled_manager()
    assert mgr.cmd_accuracy_info("Jean", "Slime") == "Accuracy debug disabled"


def test_cmd_npc_decision_trace_disabled_returns_message():
    mgr = _disabled_manager()
    assert mgr.cmd_npc_decision_trace("Slime") == "AI decision debug disabled"


def test_cmd_performance_monitor_disabled_returns_message():
    mgr = _disabled_manager()
    assert mgr.cmd_performance_monitor() == "Debug mode disabled"


def test_cmd_toggle_feature_disabled_returns_message():
    mgr = _disabled_manager()
    assert mgr.cmd_toggle_feature("debug_positions") == "Debug mode disabled"


def test_cmd_spawn_item_disabled_returns_message():
    mgr = _disabled_manager()
    assert mgr.cmd_spawn_item("Potion", 2) == "Debug mode disabled"


def test_cmd_list_stats_disabled_returns_message():
    mgr = _disabled_manager()
    assert mgr.cmd_list_stats("Jean") == "Debug mode disabled"


def test_display_ai_debug_info_returns_early_when_disabled():
    mgr = _disabled_manager()
    npc = MagicMock(name="Slime")
    mgr.display_ai_debug_info(npc, "Selected Attack")
    assert mgr.get_command_history() == []


def test_display_ai_debug_info_logs_and_prints_when_enabled():
    mgr = _enabled_manager(debug_ai_decisions=True)
    npc = MagicMock()
    npc.name = "Slime"
    with patch("neotermcolor.cprint") as mock_cprint:
        mgr.display_ai_debug_info(
            npc, "Selected Attack", details={"fatigue_cost": 5, "weight": 3}
        )
    mock_cprint.assert_called_once()
    printed_text = mock_cprint.call_args[0][0]
    assert "Slime" in printed_text
    assert "Selected Attack" in printed_text
    assert "fatigue_cost=5" in printed_text
    assert "weight=3" in printed_text

    history = mgr.get_command_history()
    assert history[-1]["command"] == "display_ai_debug_info"


def test_execute_command_falls_back_to_no_args_on_type_error():
    mgr = _enabled_manager()
    calls = []

    def strict_command():
        calls.append("no-arg")
        return "ok"

    mgr.registered_commands["strict"] = strict_command
    result = mgr.execute_command("strict", args=["unexpected", "args"])
    assert result == "ok"
    assert calls == ["no-arg"]


def test_validate_all_commands_flags_non_callable_entry():
    mgr = _enabled_manager()
    validator = DebugValidator(mgr)
    mgr.registered_commands["broken"] = "not a function"

    all_valid, issues = validator.validate_all_commands()
    assert all_valid is False
    assert any("broken" in issue for issue in issues)
