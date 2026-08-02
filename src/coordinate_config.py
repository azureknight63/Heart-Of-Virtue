"""Coordinate system configuration for Phase 2.3.

Pruned per issue #450: every method except get_dynamic_grid_size had zero
production callers (get_grid_size and friends read a `coordinate_grid_size`
GameConfig attribute that doesn't exist; get_zone_bounds read a
`[testing_locations]` config section no shipped config file defines).
get_dynamic_grid_size is the one method actually used, always via a fresh
throwaway instance at each combat-positioning call site.
"""

from typing import Tuple


class CoordinateSystemConfig:
    """Calculates the dynamic combat grid size for a given combatant count."""

    def __init__(self, player):
        """Initialize with player reference (unused by get_dynamic_grid_size,
        kept for call-site compatibility).

        Args:
            player: Player object with game_config
        """
        self.player = player

    def get_dynamic_grid_size(self, combatant_count: int) -> Tuple[int, int]:
        """Calculate dynamic grid size based on combatant count.

        Scales linearly from 9×9 for small skirmishes up to 100×100 for
        large battles, giving roughly 9 cells of breathing room per combatant.

        Args:
            combatant_count: Total number of units (allies + enemies)

        Returns:
            (width, height) tuple in the range [9, 100].
        """
        size = max(9, min(100, combatant_count * 3 + 3))
        return (size, size)
