"""Tests for coordinate system configuration.

Pruned per issue #450: CoordinateSystemConfig was cut down to just
get_dynamic_grid_size, the only method with any production callers. The rest
(get_grid_size, is_coordinate_valid, clamp_coordinate, get_zone_bounds, ...)
read a `coordinate_grid_size` GameConfig attribute that doesn't exist on the
real dataclass, or a `[testing_locations]` config section no shipped config
defines -- dead on both ends.
"""

from src.coordinate_config import CoordinateSystemConfig  # type: ignore
from src.player import Player  # type: ignore


def test_get_dynamic_grid_size_scales_with_combatant_count():
    player = Player()
    coord_config = CoordinateSystemConfig(player)

    assert coord_config.get_dynamic_grid_size(0) == (9, 9)
    assert coord_config.get_dynamic_grid_size(1) == (9, 9)
    assert coord_config.get_dynamic_grid_size(5) == (18, 18)


def test_get_dynamic_grid_size_floors_at_nine():
    player = Player()
    coord_config = CoordinateSystemConfig(player)

    # combatant_count * 3 + 3 would be below 9 for very small counts
    assert coord_config.get_dynamic_grid_size(0)[0] >= 9


def test_get_dynamic_grid_size_caps_at_one_hundred():
    player = Player()
    coord_config = CoordinateSystemConfig(player)

    width, height = coord_config.get_dynamic_grid_size(1000)
    assert width == 100
    assert height == 100


def test_get_dynamic_grid_size_returns_square():
    player = Player()
    coord_config = CoordinateSystemConfig(player)

    width, height = coord_config.get_dynamic_grid_size(10)
    assert width == height
