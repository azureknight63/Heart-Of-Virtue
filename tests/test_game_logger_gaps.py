"""Additional coverage for src/game_logger.py — closes gaps left by
tests/test_game_logger.py: the config-present branches of each
_should_log_*/_should_monitor_bps method, the file-write exception paths,
the optional-detail branches of angle/npc-decision/performance/bps logging,
and get_session_log_summary end to end.
"""

import sys
from pathlib import Path
from unittest.mock import mock_open, patch

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.game_logger import GameLogger  # type: ignore
from src.config_manager import GameConfig  # type: ignore
from src.player import Player  # type: ignore


def _logger_with_config(tmp_path, **config_overrides):
    player = Player()
    config = GameConfig()
    for key, value in config_overrides.items():
        setattr(config, key, value)
    player.game_config = config
    log_file = tmp_path / "test.log"
    return GameLogger(player, log_file=str(log_file)), log_file


def test_ensure_log_file_ready_handles_open_failure(tmp_path, capsys):
    player = Player()
    # A path in a directory that doesn't exist -> open() raises.
    bad_path = tmp_path / "nonexistent_dir" / "combat.log"
    GameLogger(player, log_file=str(bad_path))
    assert "Could not open log file" in capsys.readouterr().err


def test_should_log_combat_moves_reads_from_config(tmp_path):
    logger, _ = _logger_with_config(tmp_path, log_combat_moves=False)
    assert logger._should_log_combat_moves() is False


def test_should_log_distance_calculations_reads_from_config(tmp_path):
    logger, _ = _logger_with_config(tmp_path, log_distance_calculations=False)
    assert logger._should_log_distance_calculations() is False


def test_should_log_angle_calculations_reads_from_config(tmp_path):
    logger, _ = _logger_with_config(tmp_path, log_angle_calculations=False)
    assert logger._should_log_angle_calculations() is False


def test_should_log_npc_decisions_reads_from_config(tmp_path):
    logger, _ = _logger_with_config(tmp_path, log_npc_decisions=False)
    assert logger._should_log_npc_decisions() is False


def test_should_monitor_bps_reads_from_config(tmp_path):
    logger, _ = _logger_with_config(tmp_path, monitor_bps=True)
    assert logger._should_monitor_bps() is True


def _logger_without_config(tmp_path):
    player = Player()
    player.game_config = None
    log_file = tmp_path / "no_config.log"
    return GameLogger(player, log_file=str(log_file))


def test_should_log_distance_calculations_defaults_true_without_config(tmp_path):
    logger = _logger_without_config(tmp_path)
    assert logger._should_log_distance_calculations() is True


def test_should_log_angle_calculations_defaults_true_without_config(tmp_path):
    logger = _logger_without_config(tmp_path)
    assert logger._should_log_angle_calculations() is True


def test_should_log_npc_decisions_defaults_true_without_config(tmp_path):
    logger = _logger_without_config(tmp_path)
    assert logger._should_log_npc_decisions() is True


def test_should_monitor_bps_defaults_false_without_config(tmp_path):
    logger = _logger_without_config(tmp_path)
    assert logger._should_monitor_bps() is False


def test_should_log_performance_defaults_false_without_config(tmp_path):
    logger = _logger_without_config(tmp_path)
    assert logger._should_log_performance() is False


def test_write_log_handles_write_failure(tmp_path, capsys):
    logger, _ = _logger_with_config(tmp_path)
    with patch("builtins.open", side_effect=OSError("disk full")):
        logger._write_log("hello")
    assert "Could not write to log file" in capsys.readouterr().err


def test_log_angle_calculation_returns_early_when_disabled(tmp_path):
    logger, log_file = _logger_with_config(tmp_path, log_angle_calculations=False)
    logger.log_angle_calculation("Jean", "Slime", 42.5, quadrant="NE")
    assert "ANGLE" not in log_file.read_text()


def test_log_npc_decision_returns_early_when_disabled(tmp_path):
    logger, log_file = _logger_with_config(tmp_path, log_npc_decisions=False)
    logger.log_npc_decision("Slime", "Attack")
    assert "NPC:" not in log_file.read_text()


def test_log_performance_metric_returns_early_when_disabled(tmp_path):
    logger, log_file = _logger_with_config(tmp_path, log_performance=False)
    logger.log_performance_metric("frame_time", 16.67, unit="ms")
    assert "PERF" not in log_file.read_text()


def test_log_bytes_per_second_returns_early_when_disabled(tmp_path):
    logger, log_file = _logger_with_config(tmp_path, monitor_bps=False)
    logger.log_bytes_per_second(1024.0, context="network")
    assert "BPS" not in log_file.read_text()


def test_log_angle_calculation_with_quadrant(tmp_path):
    logger, log_file = _logger_with_config(tmp_path, log_angle_calculations=True)
    logger.log_angle_calculation("Jean", "Slime", 42.5, quadrant="NE")
    content = log_file.read_text()
    assert "ANGLE: Jean to Slime = 42.5°" in content
    assert "(NE)" in content


def test_log_npc_decision_with_reasoning_and_confidence(tmp_path):
    logger, log_file = _logger_with_config(tmp_path, log_npc_decisions=True)
    logger.log_npc_decision("Slime", "Attack", reasoning="in range", confidence=0.75)
    content = log_file.read_text()
    assert "reason: in range" in content
    assert "confidence: 75.00%" in content


def test_log_performance_metric_with_unit(tmp_path):
    logger, log_file = _logger_with_config(tmp_path, log_performance=True)
    logger.log_performance_metric("frame_time", 16.67, unit="ms")
    content = log_file.read_text()
    assert "PERF: frame_time = 16.67 ms" in content


def test_log_bytes_per_second_with_context(tmp_path):
    logger, log_file = _logger_with_config(tmp_path, monitor_bps=True)
    logger.log_bytes_per_second(1024.0, context="network")
    content = log_file.read_text()
    assert "BPS: 1024.00 bytes/sec (network)" in content


def test_get_session_log_summary_no_file(tmp_path):
    player = Player()
    logger = GameLogger(player, log_file=str(tmp_path / "unwritten.log"))
    # Delete the file the constructor created, to hit the "not exists" branch.
    Path(logger.log_file).unlink()
    assert logger.get_session_log_summary() == "No log file found"


def test_get_session_log_summary_counts_entries(tmp_path):
    logger, log_file = _logger_with_config(
        tmp_path,
        log_combat_moves=True,
        log_npc_decisions=True,
    )
    logger.log_combat_move("Jean", "Attack", "Slime")
    logger.log_npc_decision("Slime", "Attack")
    logger.log_session_end(victory=True, duration_seconds=12.5)

    summary = logger.get_session_log_summary()
    assert "Total entries:" in summary
    assert "Moves logged: 1" in summary
    assert "NPC decisions logged: 1" in summary
    assert "Sessions:" in summary


def test_get_session_log_summary_handles_read_failure(tmp_path):
    logger, log_file = _logger_with_config(tmp_path)
    with patch("builtins.open", side_effect=OSError("read failed")):
        summary = logger.get_session_log_summary()
    assert "Could not read log" in summary
