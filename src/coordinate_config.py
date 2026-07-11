"""Coordinate system configuration for Phase 2.3.

Manages coordinate grid sizing based on GameConfig settings.
Ensures all positioning respects the configured grid size.
"""

from typing import Tuple, Optional


class CoordinateSystemConfig:
    """Manages coordinate system configuration from GameConfig."""

    def __init__(self, player):
        """Initialize with player reference for accessing config.

        Args:
            player: Player object with game_config
        """
        self.player = player
        self._default_grid_size = (50, 50)

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

    def get_grid_size(self) -> Tuple[int, int]:
        """Get current grid size from config.

        Returns:
            Tuple of (width, height) in grid units
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.coordinate_grid_size
        return self._default_grid_size

    def get_grid_width(self) -> int:
        """Get grid width.

        Returns:
            Grid width in units
        """
        return self.get_grid_size()[0]

    def get_grid_height(self) -> int:
        """Get grid height.

        Returns:
            Grid height in units
        """
        return self.get_grid_size()[1]

    def is_coordinate_valid(self, x: int, y: int) -> bool:
        """Check if coordinate is within grid bounds.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if coordinate is valid, False otherwise
        """
        width, height = self.get_grid_size()
        return 0 <= x <= width and 0 <= y <= height

    def clamp_coordinate(self, x: int, y: int) -> Tuple[int, int]:
        """Clamp coordinate to grid bounds.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Clamped (x, y) tuple
        """
        width, height = self.get_grid_size()
        x = max(0, min(x, width))
        y = max(0, min(y, height))
        return (x, y)

    def get_grid_center(self) -> Tuple[float, float]:
        """Get center of grid.

        Returns:
            (x, y) center coordinates
        """
        width, height = self.get_grid_size()
        return (width / 2.0, height / 2.0)

    def get_grid_area(self) -> int:
        """Get total grid area.

        Returns:
            Total number of grid squares
        """
        width, height = self.get_grid_size()
        return width * height

    def get_distance_between_points(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> float:
        """Calculate Euclidean distance between two points.

        Args:
            x1, y1: First point
            x2, y2: Second point

        Returns:
            Euclidean distance in grid units
        """
        import math

        dx = x2 - x1
        dy = y2 - y1
        return math.sqrt(dx * dx + dy * dy)

    def get_angle_between_points(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> float:
        """Calculate angle from point 1 to point 2 in degrees.

        Args:
            x1, y1: First point
            x2, y2: Second point

        Returns:
            Angle in degrees (0-360, where 0=North, 90=East, 180=South, 270=West)
        """
        import math

        dx = x2 - x1
        dy = y2 - y1
        # atan2 gives angle from East (0°), but we want from North (0°)
        # So we need to rotate 90 degrees
        angle_rad = math.atan2(dx, dy)  # Note: switched x and y for North-based angle
        angle_deg = math.degrees(angle_rad)
        # Normalize to 0-360
        angle_deg = (angle_deg + 360) % 360
        return angle_deg

    def get_zone_bounds(
        self, zone_name: str
    ) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Get bounds for a named zone if available from config.

        Args:
            zone_name: Name of zone (e.g., 'standard_player', 'boss_arena')

        Returns:
            ((min_x, min_y), (max_x, max_y)) or None if zone not found
        """
        if not hasattr(self.player, "game_config") or not self.player.game_config:
            return None

        config = self.player.game_config

        # Map zone names to config attributes
        zone_map = {
            "standard_player": (
                config.standard_player_x,
                config.standard_player_y,
            ),
            "standard_enemy": (
                config.standard_enemy_x,
                config.standard_enemy_y,
            ),
            "pincer_player": (config.pincer_player_x, config.pincer_player_y),
            "pincer_enemy1": (config.pincer_enemy1_x, config.pincer_enemy1_y),
            "pincer_enemy2": (config.pincer_enemy2_x, config.pincer_enemy2_y),
            "melee_center": (config.melee_center_x, config.melee_center_y),
            "boss_arena": (config.boss_arena_x, config.boss_arena_y),
        }

        if zone_name in zone_map:
            x, y = zone_map[zone_name]
            return ((x, y), (x, y))  # Single point zones

        return None

    def scale_distance_to_grid(
        self, distance: float, reference_grid_size: int = 50
    ) -> float:
        """Scale distance based on current grid size vs reference.

        Useful for scenarios created with a different grid size.

        Args:
            distance: Distance in original reference units
            reference_grid_size: Size of original grid (default 50)

        Returns:
            Scaled distance for current grid size
        """
        current_size = self.get_grid_width()
        if reference_grid_size == 0:
            return distance
        return distance * (current_size / reference_grid_size)

    def get_grid_info_string(self) -> str:
        """Get informational string about current grid configuration.

        Returns:
            Formatted string describing grid
        """
        width, height = self.get_grid_size()
        area = self.get_grid_area()
        center_x, center_y = self.get_grid_center()

        return (
            f"Coordinate Grid Configuration:\n"
            f"  Size: {width} × {height} units\n"
            f"  Area: {area} total squares\n"
            f"  Center: ({center_x:.1f}, {center_y:.1f})\n"
            f"  Bounds: (0, 0) to ({width}, {height})"
        )
