"""Tests for coordinate system configuration.

Pruned per issue #450: CoordinateSystemConfig was cut down to just
get_dynamic_grid_size, the only method with any production callers. The rest
(get_grid_size, is_coordinate_valid, clamp_coordinate, get_zone_bounds, ...)
read a `coordinate_grid_size` GameConfig attribute that doesn't exist on the
real dataclass, or a `[testing_locations]` config section no shipped config
defines -- dead on both ends.
"""

import pytest

from src.coordinate_config import CoordinateSystemConfig
from src.player import Player


@pytest.fixture(scope="module")
def coord_config():
    """The player reference is unused by get_dynamic_grid_size and the method
    is pure, so one instance is safe to share across the module."""
    return CoordinateSystemConfig(Player())


# size = clamp(combatant_count * 3 + 3, 9, 100) -- the boundaries of both
# clamps are covered, plus the first count where each stops binding.
@pytest.mark.parametrize(
    "count,expected",
    [
        (-5, 9),     # negative counts cannot produce a degenerate grid
        (0, 9),      # floor
        (1, 9),      # floor still binding
        (2, 9),      # last count where the floor binds (2*3+3 == 9)
        (3, 12),     # first count where the formula takes over
        (4, 15),
        (5, 18),
        (32, 99),    # last count below the cap
        (33, 100),   # first count at the cap (33*3+3 == 102 -> clamped)
        (1000, 100),  # cap
    ],
)
def test_get_dynamic_grid_size(coord_config, count, expected):
    assert coord_config.get_dynamic_grid_size(count) == (expected, expected)


def test_grid_is_always_square_and_within_bounds(coord_config):
    for count in range(0, 60):
        width, height = coord_config.get_dynamic_grid_size(count)
        assert width == height
        assert 9 <= width <= 100


def test_grid_size_is_monotonic_in_combatant_count(coord_config):
    """More combatants never shrink the arena."""
    sizes = [coord_config.get_dynamic_grid_size(n)[0] for n in range(0, 60)]
    assert sizes == sorted(sizes)
