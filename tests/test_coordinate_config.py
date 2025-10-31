"""Tests for coordinate system configuration (Phase 2.3)."""

import sys
import math
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.coordinate_config import CoordinateSystemConfig, GridValidator  # type: ignore
from src.config_manager import GameConfig  # type: ignore
from src.player import Player  # type: ignore


def test_coordinate_system_config_default_grid_size():
    """Test default grid size is 50x50."""
    player = Player()
    coord_config = CoordinateSystemConfig(player)
    
    assert coord_config.get_grid_size() == (50, 50)
    assert coord_config.get_grid_width() == 50
    assert coord_config.get_grid_height() == 50


def test_coordinate_system_config_from_game_config():
    """Test that grid size comes from GameConfig."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (100, 150)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    assert coord_config.get_grid_size() == (100, 150)
    assert coord_config.get_grid_width() == 100
    assert coord_config.get_grid_height() == 150


def test_coordinate_system_config_is_coordinate_valid():
    """Test coordinate validation."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    # Valid coordinates
    assert coord_config.is_coordinate_valid(0, 0) is True
    assert coord_config.is_coordinate_valid(25, 25) is True
    assert coord_config.is_coordinate_valid(50, 50) is True
    
    # Invalid coordinates
    assert coord_config.is_coordinate_valid(-1, 0) is False
    assert coord_config.is_coordinate_valid(51, 25) is False
    assert coord_config.is_coordinate_valid(25, 51) is False


def test_coordinate_system_config_clamp_coordinate():
    """Test coordinate clamping."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    # Should clamp to bounds
    assert coord_config.clamp_coordinate(-10, 25) == (0, 25)
    assert coord_config.clamp_coordinate(60, 25) == (50, 25)
    assert coord_config.clamp_coordinate(25, -5) == (25, 0)
    assert coord_config.clamp_coordinate(25, 60) == (25, 50)
    
    # Valid coordinates unchanged
    assert coord_config.clamp_coordinate(25, 25) == (25, 25)


def test_coordinate_system_config_grid_center():
    """Test grid center calculation."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    center = coord_config.get_grid_center()
    assert center == (25.0, 25.0)


def test_coordinate_system_config_grid_center_asymmetric():
    """Test grid center with asymmetric grid."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (100, 200)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    center = coord_config.get_grid_center()
    assert center == (50.0, 100.0)


def test_coordinate_system_config_grid_area():
    """Test grid area calculation."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    assert coord_config.get_grid_area() == 2500


def test_coordinate_system_config_distance_between_points():
    """Test Euclidean distance calculation."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    # Distance from (0,0) to (3,4) should be 5
    distance = coord_config.get_distance_between_points(0, 0, 3, 4)
    assert abs(distance - 5.0) < 0.001
    
    # Distance from same point should be 0
    distance = coord_config.get_distance_between_points(10, 10, 10, 10)
    assert distance == 0


def test_coordinate_system_config_angle_between_points():
    """Test angle calculation between points."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    # Angle south (0° in this system - y decreasing)
    angle = coord_config.get_angle_between_points(25, 25, 25, 50)
    assert abs(angle - 0.0) < 1
    
    # Angle east (90°)
    angle = coord_config.get_angle_between_points(25, 25, 50, 25)
    assert abs(angle - 90.0) < 1
    
    # Angle north (180° in this system - y increasing)
    angle = coord_config.get_angle_between_points(25, 25, 25, 0)
    assert abs(angle - 180.0) < 1
    
    # Angle west (270°)
    angle = coord_config.get_angle_between_points(25, 25, 0, 25)
    assert abs(angle - 270.0) < 1


def test_coordinate_system_config_zone_bounds():
    """Test zone bounds retrieval."""
    player = Player()
    config = GameConfig()
    config.standard_player_x = 10
    config.standard_player_y = 20
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    bounds = coord_config.get_zone_bounds('standard_player')
    assert bounds == ((10, 20), (10, 20))


def test_coordinate_system_config_scale_distance_to_grid():
    """Test distance scaling based on grid size."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (100, 100)  # Double the default 50x50
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    # Distance of 10 on 50x50 grid should scale to 20 on 100x100 grid
    scaled = coord_config.scale_distance_to_grid(10, reference_grid_size=50)
    assert abs(scaled - 20.0) < 0.001


def test_coordinate_system_config_grid_info_string():
    """Test grid info string generation."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    info = coord_config.get_grid_info_string()
    assert "50" in info
    assert "2500" in info
    assert "25.0" in info


def test_grid_validator_initialization():
    """Test GridValidator initialization."""
    player = Player()
    coord_config = CoordinateSystemConfig(player)
    validator = GridValidator(coord_config)
    
    assert validator.coord_config is coord_config


def test_grid_validator_validate_position_valid():
    """Test position validation for valid coordinates."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    validator = GridValidator(coord_config)
    
    is_valid, msg = validator.validate_position(25, 25)
    assert is_valid is True


def test_grid_validator_validate_position_invalid_strict():
    """Test position validation fails in strict mode."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    validator = GridValidator(coord_config)
    
    is_valid, msg = validator.validate_position(60, 25, strict=True)
    assert is_valid is False
    assert "outside grid bounds" in msg


def test_grid_validator_validate_position_invalid_non_strict():
    """Test position validation clamps in non-strict mode."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    validator = GridValidator(coord_config)
    
    is_valid, msg = validator.validate_position(60, 25, strict=False)
    assert is_valid is True


def test_grid_validator_validate_distance():
    """Test distance validation."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    validator = GridValidator(coord_config)
    
    # Valid distance
    is_valid, msg = validator.validate_distance(25.0)
    assert is_valid is True
    
    # Invalid distance (exceeds max)
    is_valid, msg = validator.validate_distance(1000.0)
    assert is_valid is False


def test_grid_validator_validate_zone_bounds():
    """Test zone bounds validation."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    validator = GridValidator(coord_config)
    
    # Valid zone
    is_valid, msg = validator.validate_zone_bounds((10, 10), (40, 40))
    assert is_valid is True
    
    # Invalid zone - outside grid
    is_valid, msg = validator.validate_zone_bounds((10, 10), (60, 60))
    assert is_valid is False
    
    # Invalid zone - min >= max
    is_valid, msg = validator.validate_zone_bounds((40, 40), (10, 10))
    assert is_valid is False


def test_coordinate_system_config_respects_config_changes():
    """Test that config changes are reflected."""
    player = Player()
    config = GameConfig()
    config.coordinate_grid_size = (50, 50)
    player.game_config = config
    
    coord_config = CoordinateSystemConfig(player)
    
    # Initial check
    assert coord_config.get_grid_width() == 50
    
    # Change config
    config.coordinate_grid_size = (100, 100)
    
    # Should reflect change
    assert coord_config.get_grid_width() == 100
