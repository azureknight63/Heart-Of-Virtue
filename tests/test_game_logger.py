"""Tests for the game logging system (Phase 2.2)."""

import sys
from pathlib import Path
import tempfile

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.game_logger import GameLogger  # type: ignore
from src.config_manager import GameConfig  # type: ignore
from src.player import Player  # type: ignore


def test_game_logger_initializes_with_player():
    """Test that GameLogger initializes with player reference."""
    player = Player()
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        log_file = f.name
    
    logger = GameLogger(player, log_file=log_file)
    
    assert logger.player is player
    assert Path(log_file).exists()
    
    # Cleanup
    Path(log_file).unlink()


def test_game_logger_respects_combat_moves_flag(tmp_path):
    """Test that log_combat_move respects config flag."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    config = GameConfig()
    config.log_combat_moves = True
    player.game_config = config
    
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_combat_move("Jean", "Attack", "Enemy1", "Critical!")
    
    # Check log was written
    assert log_file.exists()
    content = log_file.read_text()
    assert "MOVE: Jean uses Attack on Enemy1" in content
    assert "Critical!" in content


def test_game_logger_respects_distance_calculations_flag(tmp_path):
    """Test that log_distance_calculation respects config flag."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    config = GameConfig()
    config.log_distance_calculations = True
    player.game_config = config
    
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_distance_calculation("Jean", "Enemy1", 25.5, "Euclidean")
    
    content = log_file.read_text()
    assert "DISTANCE: Jean to Enemy1 = 25.50 ft" in content
    assert "Euclidean" in content


def test_game_logger_respects_angle_calculations_flag(tmp_path):
    """Test that log_angle_calculation respects config flag."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    config = GameConfig()
    config.log_angle_calculations = True
    player.game_config = config
    
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_angle_calculation("Jean", "Enemy1", 45.0, "NE")
    
    content = log_file.read_text()
    assert "ANGLE: Jean to Enemy1 = 45.0°" in content
    assert "(NE)" in content


def test_game_logger_respects_npc_decisions_flag(tmp_path):
    """Test that log_npc_decision respects config flag."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    config = GameConfig()
    config.log_npc_decisions = True
    player.game_config = config
    
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_npc_decision("Enemy1", "Flank", "Target has low health", 0.85)
    
    content = log_file.read_text()
    assert "NPC: Enemy1 decides: Flank" in content
    assert "Target has low health" in content
    assert "85.00%" in content


def test_game_logger_skips_logging_when_flag_disabled(tmp_path):
    """Test that logger respects disabled flags."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    config = GameConfig()
    config.log_combat_moves = False
    config.log_distance_calculations = False
    player.game_config = config
    
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_combat_move("Jean", "Attack", "Enemy1")
    logger.log_distance_calculation("Jean", "Enemy1", 25.0)
    
    content = log_file.read_text()
    # Should not contain move or distance logs
    assert "MOVE:" not in content
    assert "DISTANCE:" not in content


def test_game_logger_performance_metric_logging(tmp_path):
    """Test performance metric logging."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    config = GameConfig()
    config.log_performance = True
    player.game_config = config
    
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_performance_metric("Frame Time", 16.67, "ms")
    
    content = log_file.read_text()
    assert "PERF: Frame Time = 16.67 ms" in content


def test_game_logger_bps_monitoring(tmp_path):
    """Test bytes per second monitoring."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    config = GameConfig()
    config.monitor_bps = True
    player.game_config = config
    
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_bytes_per_second(1024.5, "network")
    
    content = log_file.read_text()
    assert "BPS: 1024.50 bytes/sec" in content
    assert "(network)" in content


def test_game_logger_combat_event_logging(tmp_path):
    """Test combat event logging."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_combat_event("Combat Started", ["Jean", "Enemy1", "Enemy2"], "3v2")
    
    content = log_file.read_text()
    assert "EVENT: Combat Started" in content
    assert "Jean" in content
    assert "Enemy1" in content


def test_game_logger_session_end_logging(tmp_path):
    """Test session end logging."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_session_end(victory=True, duration_seconds=45.5)
    
    content = log_file.read_text()
    assert "SESSION_END: VICTORY" in content
    assert "45.5s" in content


def test_game_logger_session_end_defeat(tmp_path):
    """Test session end logging for defeat."""
    log_file = tmp_path / "test.log"
    
    player = Player()
    logger = GameLogger(player, log_file=str(log_file))
    logger.log_session_end(victory=False)
    
    content = log_file.read_text()
    assert "SESSION_END: DEFEAT" in content


def test_game_logger_handles_missing_config_gracefully():
    """Test that logger handles players without game_config."""
    player = Player()
    # Remove game_config if present
    if hasattr(player, 'game_config'):
        player.game_config = None
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        log_file = f.name
    
    logger = GameLogger(player, log_file=log_file)
    # Should not raise error
    logger.log_combat_move("Jean", "Attack", "Enemy1")
    
    # Cleanup
    Path(log_file).unlink()


def test_game_logger_uses_config_log_file(tmp_path):
    """Test that logger uses log_file from config if provided."""
    log_file = tmp_path / "custom.log"
    
    player = Player()
    config = GameConfig()
    config.log_file = str(log_file)
    player.game_config = config
    
    logger = GameLogger(player)  # No explicit log_file parameter
    logger.log_combat_move("Test", "Move")
    
    # Should have written to config-specified file
    assert log_file.exists()


def test_game_logger_defaults_to_combat_testing_log():
    """Test that logger defaults to combat_testing_phase4.log."""
    player = Player()
    
    logger = GameLogger(player, log_file=None)
    # Should use default
    assert "combat_testing_phase4.log" in logger._get_log_file_path() or logger._get_log_file_path() == "combat_testing_phase4.log"
