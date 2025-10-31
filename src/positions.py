"""
Combat positioning system for coordinate-based tactical combat.

This module provides the core data structures and utility functions for the new
2D coordinate-based combat positioning system (HV-1). It replaces the old 1D
distance-based proximity model while maintaining backward compatibility.

Grid Specification:
- 50×50 grid of coordinates (0-50, 0-50)
- Each grid square ≈ 1 foot for distance calculations
- Supports 8 directional movement (cardinal + diagonal)

Key Classes:
- Direction: Enum for 8 compass directions
- CombatPosition: Dataclass storing x, y, and facing direction
- CombatScenario: Configuration for combat initialization

Distance Conversion:
- Old system: combat_proximity dict with distance in feet
- New system: CombatPosition objects with x, y coordinates
- Backward compatibility: distance_from_coords() converts coordinates to feet
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, Dict, List, TYPE_CHECKING, Any
import math
import random

if TYPE_CHECKING:
    from npc import NPC


class Direction(Enum):
    """8 compass directions for unit facing.
    
    Values correspond to angles:
    N=0°, NE=45°, E=90°, SE=135°, S=180°, SW=225°, W=270°, NW=315°
    """
    N = 0       # North
    NE = 45     # Northeast
    E = 90      # East
    SE = 135    # Southeast
    S = 180     # South
    SW = 225    # Southwest
    W = 270     # West
    NW = 315    # Northwest


@dataclass
class CombatPosition:
    """Represents a combatant's position and facing direction on the battlefield.
    
    Attributes:
        x: Horizontal coordinate (0-50, left to right)
        y: Vertical coordinate (0-50, front to back)
        facing: Direction the combatant is facing (affects attack angle calculations)
    """
    x: int
    y: int
    facing: Direction = Direction.N
    
    def __post_init__(self):
        """Validate coordinates are within grid bounds."""
        if not (0 <= self.x <= 50):
            raise ValueError(f"X coordinate must be 0-50, got {self.x}")
        if not (0 <= self.y <= 50):
            raise ValueError(f"Y coordinate must be 0-50, got {self.y}")
        if not isinstance(self.facing, Direction):
            raise ValueError(f"Facing must be Direction enum, got {self.facing}")
    
    def copy(self) -> "CombatPosition":
        """Create an independent copy of this position."""
        return CombatPosition(x=self.x, y=self.y, facing=self.facing)


@dataclass
class CombatScenario:
    """Configuration for how a combat encounter initializes positions.
    
    Scenarios define spawn zones and formation types for allies and enemies.
    This allows varied tactical situations (standard, pincer, melee, boss arena, etc.)
    """
    scenario_type: str  # "standard", "pincer", "melee", "boss_arena", "custom"
    ally_spawn_zone: Tuple[Tuple[int, int], Tuple[int, int]]  # ((x_min, y_min), (x_max, y_max))
    enemy_spawn_zones: List[Tuple[Tuple[int, int], Tuple[int, int]]]  # List of zones
    formation_type: str  # "spread", "cluster", "random"
    min_spacing: int = 1  # Minimum grid squares between units
    seed: Optional[int] = None  # For reproducible positioning


# Predefined combat scenarios
COMBAT_SCENARIOS = {
    "standard": CombatScenario(
        scenario_type="standard",
        ally_spawn_zone=((10, 15), (20, 35)),
        enemy_spawn_zones=[((35, 15), (45, 35))],
        formation_type="spread",
        min_spacing=2
    ),
    "pincer": CombatScenario(
        scenario_type="pincer",
        ally_spawn_zone=((20, 20), (30, 30)),
        enemy_spawn_zones=[
            ((5, 10), (15, 20)),    # Left flank
            ((5, 30), (15, 40))     # Right flank
        ],
        formation_type="cluster",
        min_spacing=1
    ),
    "melee": CombatScenario(
        scenario_type="melee",
        ally_spawn_zone=((0, 0), (50, 50)),
        enemy_spawn_zones=[((0, 0), (50, 50))],
        formation_type="random",
        min_spacing=2
    ),
    "boss_arena": CombatScenario(
        scenario_type="boss_arena",
        ally_spawn_zone=((15, 40), (35, 50)),
        enemy_spawn_zones=[((20, 5), (30, 15))],
        formation_type="spread",
        min_spacing=3
    ),
}


# ============================================================================
# Distance and Angle Calculations
# ============================================================================

def distance_from_coords(pos1: CombatPosition, pos2: CombatPosition) -> int:
    """Calculate Euclidean distance between two positions in feet.
    
    Each grid square represents approximately 1 foot for combat purposes.
    This function converts 2D coordinates back to 1D distance for backward
    compatibility with the old proximity-based system.
    
    Args:
        pos1: First combat position
        pos2: Second combat position
    
    Returns:
        Distance in feet (rounded to nearest integer)
    """
    dx = pos1.x - pos2.x
    dy = pos1.y - pos2.y
    euclidean = math.sqrt(dx * dx + dy * dy)
    return int(round(euclidean))


def distance_squared(pos1: CombatPosition, pos2: CombatPosition) -> float:
    """Calculate squared Euclidean distance (faster for comparisons).
    
    Useful when only comparing distances, not displaying them.
    
    Args:
        pos1: First combat position
        pos2: Second combat position
    
    Returns:
        Squared distance (no square root)
    """
    dx = pos1.x - pos2.x
    dy = pos1.y - pos2.y
    return dx * dx + dy * dy


def angle_to_target(from_pos: CombatPosition, to_pos: CombatPosition) -> float:
    """Calculate angle from one position to another (0-360°).
    
    Used to determine the direction of an attack relative to target's facing.
    
    Args:
        from_pos: Position of attacker
        to_pos: Position of target
    
    Returns:
        Angle in degrees (0-360), where 0° is North, 90° is East, etc.
    """
    dx = to_pos.x - from_pos.x
    dy = to_pos.y - from_pos.y
    
    # atan2 gives angle from -π to π
    # We want 0-360 where 0° = North (positive Y) and 90° = East (positive X)
    # Standard atan2 has 0° pointing East, so we need to adjust
    angle_rad = math.atan2(dx, dy)  # Swap x/y to make North = 0°
    angle_deg = math.degrees(angle_rad)
    
    # Normalize to 0-360
    if angle_deg < 0:
        angle_deg += 360
    
    return angle_deg


def attack_angle_difference(attack_angle: float, target_facing: Direction) -> int:
    """Calculate angular difference between attack direction and target's facing.
    
    Returns the acute angle (0-180°) between where the attack comes from
    and where the target is facing. Used to determine damage/accuracy modifiers.
    
    - 0° = attack from front (target facing attacker)
    - 90° = attack from flank
    - 180° = attack from rear (target facing away)
    
    Args:
        attack_angle: Angle of attack (0-360°)
        target_facing: Direction target is facing
    
    Returns:
        Angular difference in degrees (0-180)
    """
    diff = abs(attack_angle - target_facing.value)
    
    # Take the acute angle (shortest rotation)
    if diff > 180:
        diff = 360 - diff
    
    return int(round(diff))


def get_damage_modifier(angle_diff: int) -> float:
    """Get damage multiplier based on attack angle relative to target's facing.
    
    Frontal attacks are defended, while flanking and rear attacks bypass defense.
    
    Args:
        angle_diff: Angular difference (0-180°)
    
    Returns:
        Damage multiplier (e.g., 1.0 = normal, 1.15 = +15% damage)
    """
    if 0 <= angle_diff <= 45:           # Front quarter
        return 0.85  # -15% damage
    elif 45 < angle_diff <= 90:         # Flanking
        return 1.15  # +15% damage
    elif 90 < angle_diff <= 135:        # Deep flank
        return 1.25  # +25% damage
    else:                               # Rear (135-180)
        return 1.40  # +40% damage


def get_accuracy_modifier(angle_diff: int) -> float:
    """Get accuracy multiplier based on attack angle relative to target's facing.
    
    Frontal attacks are easier to see/defend against. Rear attacks are nearly
    impossible to defend.
    
    Args:
        angle_diff: Angular difference (0-180°)
    
    Returns:
        Accuracy multiplier (e.g., 1.0 = normal, 1.10 = +10% accuracy)
    """
    if 0 <= angle_diff <= 45:           # Front quarter
        return 0.95  # -5% accuracy
    elif 45 < angle_diff <= 90:         # Flanking
        return 1.10  # +10% accuracy
    elif 90 < angle_diff <= 135:        # Deep flank
        return 1.20  # +20% accuracy
    else:                               # Rear (135-180)
        return 1.30  # +30% accuracy


# ============================================================================
# Position Generation and Movement
# ============================================================================

def random_position_in_zone(
    zone: Tuple[Tuple[int, int], Tuple[int, int]],
    seed: Optional[int] = None
) -> CombatPosition:
    """Generate a random position within a spawn zone.
    
    Args:
        zone: Rectangular zone ((x_min, y_min), (x_max, y_max))
        seed: Random seed for reproducibility (optional)
    
    Returns:
        CombatPosition with random x, y within zone bounds
    """
    if seed is not None:
        random.seed(seed)
    
    (x_min, y_min), (x_max, y_max) = zone
    x = random.randint(x_min, x_max)
    y = random.randint(y_min, y_max)
    
    return CombatPosition(x=x, y=y)


def clamp_position(pos: CombatPosition) -> CombatPosition:
    """Clamp position to grid bounds (0-50 for both x and y).
    
    Args:
        pos: Position to clamp
    
    Returns:
        New CombatPosition with clamped coordinates
    """
    x = max(0, min(50, pos.x))
    y = max(0, min(50, pos.y))
    return CombatPosition(x=x, y=y, facing=pos.facing)


def move_toward(
    current: CombatPosition,
    target: CombatPosition,
    distance: int
) -> CombatPosition:
    """Move from current position toward target by specified distance.
    
    Moves in a straight line (8-directional) as close as possible to the
    target without overshooting. Returns clamped position within grid bounds.
    
    Args:
        current: Starting position
        target: Target position
        distance: How many grid squares to move (each ≈ 1 foot)
    
    Returns:
        New CombatPosition after movement
    """
    if current.x == target.x and current.y == target.y:
        return current.copy()  # Already at target
    
    # Calculate direction (normalized to -1, 0, or 1)
    dx = 0 if current.x == target.x else (1 if target.x > current.x else -1)
    dy = 0 if current.y == target.y else (1 if target.y > current.y else -1)
    
    # Move in that direction
    new_x = current.x + (dx * distance)
    new_y = current.y + (dy * distance)
    
    # Clamp to grid bounds
    new_x = max(0, min(50, new_x))
    new_y = max(0, min(50, new_y))
    
    return CombatPosition(x=new_x, y=new_y, facing=current.facing)


def move_away_from(
    current: CombatPosition,
    threat: CombatPosition,
    distance: int
) -> CombatPosition:
    """Move from current position away from a threat by specified distance.
    
    Args:
        current: Starting position
        threat: Position to move away from
        distance: How many grid squares to move
    
    Returns:
        New CombatPosition after movement away
    """
    if current.x == threat.x and current.y == threat.y:
        # Can't move away from same position; pick random direction
        directions = [
            CombatPosition(current.x + distance, current.y, current.facing),
            CombatPosition(current.x - distance, current.y, current.facing),
            CombatPosition(current.x, current.y + distance, current.facing),
            CombatPosition(current.x, current.y - distance, current.facing),
        ]
        return clamp_position(random.choice(directions))
    
    # Calculate direction away from threat (opposite of toward threat)
    dx = 0 if current.x == threat.x else (1 if current.x > threat.x else -1)
    dy = 0 if current.y == threat.y else (1 if current.y > threat.y else -1)
    
    # Move away
    new_x = current.x + (dx * distance)
    new_y = current.y + (dy * distance)
    
    return clamp_position(CombatPosition(x=new_x, y=new_y, facing=current.facing))


def move_to_flank(
    current: CombatPosition,
    target: CombatPosition,
    distance: int = 3
) -> CombatPosition:
    """Move to a flanking position (90° perpendicular to target's facing).
    
    Args:
        current: Starting position
        target: Target position to flank
        distance: How many squares away from target to position
    
    Returns:
        New CombatPosition at flanking angle
    """
    # Calculate perpendicular angle (90° from target's facing)
    target_facing_angle = target.facing.value
    flank_angle = (target_facing_angle + 90) % 360
    
    # Convert to radians and calculate offset
    flank_rad = math.radians(flank_angle)
    offset_x = math.cos(flank_rad) * distance
    offset_y = math.sin(flank_rad) * distance
    
    new_x = target.x + offset_x
    new_y = target.y + offset_y
    
    return clamp_position(CombatPosition(x=int(round(new_x)), y=int(round(new_y)), facing=current.facing))


def turn_toward(
    current: CombatPosition,
    target: CombatPosition
) -> Direction:
    """Calculate which direction to face to look at target.
    
    Args:
        current: Observer position
        target: Target position to face
    
    Returns:
        Direction to face target (one of 8 cardinal directions)
    """
    angle = angle_to_target(current, target)
    
    # Round angle to nearest cardinal/diagonal direction
    # 0=N, 45=NE, 90=E, 135=SE, 180=S, 225=SW, 270=W, 315=NW
    direction_angle = round(angle / 45) * 45 % 360
    
    for direction in Direction:
        if direction.value == direction_angle:
            return direction
    
    return Direction.N  # Fallback


# ============================================================================
# Backward Compatibility Helpers
# ============================================================================

def recalculate_proximity_dict(
    unit: Any,
    all_combatants: List[Any]
) -> Dict[Any, int]:
    """Recalculate combat_proximity dict from coordinate positions.
    
    Called after any position change to maintain backward compatibility
    with the old proximity-based system.
    
    Args:
        unit: The unit to calculate proximities for (should have combat_position attribute)
        all_combatants: All combatants in the encounter
    
    Returns:
        Updated proximity dict {combatant: distance_in_feet}
    """
    proximity = {}
    if not hasattr(unit, 'combat_position') or unit.combat_position is None:
        return proximity
    
    for combatant in all_combatants:
        if combatant == unit:
            continue
        if not hasattr(combatant, 'combat_position') or combatant.combat_position is None:
            continue
        
        distance = distance_from_coords(unit.combat_position, combatant.combat_position)
        proximity[combatant] = distance
    
    return proximity


# ============================================================================
# Combat Initialization
# ============================================================================

def initialize_combat_positions(
    allies: List[Any],
    enemies: List[Any],
    scenario_type: str = "standard"
) -> None:
    """Initialize combat positions for all combatants based on scenario.
    
    Sets CombatPosition on each unit and initializes facing directions toward
    opponent teams. Updates combat_proximity dicts for backward compatibility.
    
    Args:
        allies: List of allied units (player party)
        enemies: List of enemy units
        scenario_type: Name of scenario ("standard", "pincer", "melee", "boss_arena", "custom")
    
    Raises:
        ValueError: If scenario_type is not recognized
    """
    if scenario_type not in COMBAT_SCENARIOS:
        raise ValueError(f"Unknown scenario type: {scenario_type}")
    
    scenario = COMBAT_SCENARIOS[scenario_type]
    
    # Spawn allies in their zone
    _spawn_units_in_zone(
        units=allies,
        zone=scenario.ally_spawn_zone,
        formation_type=scenario.formation_type,
        min_spacing=scenario.min_spacing,
        seed=scenario.seed
    )
    
    # Spawn enemies in their zones
    for zone_index, zone in enumerate(scenario.enemy_spawn_zones):
        # Distribute enemies across zones
        enemies_for_zone = _distribute_units_across_zones(
            units=enemies,
            total_zones=len(scenario.enemy_spawn_zones),
            zone_index=zone_index
        )
        
        _spawn_units_in_zone(
            units=enemies_for_zone,
            zone=zone,
            formation_type=scenario.formation_type,
            min_spacing=scenario.min_spacing,
            seed=scenario.seed
        )
    
    # Set initial facing directions
    for ally in allies:
        if len(enemies) > 0:
            # Face toward center of enemy group
            enemy_center = _calculate_center_position(enemies)
            ally.combat_position.facing = turn_toward(ally.combat_position, enemy_center)
    
    for enemy in enemies:
        if len(allies) > 0:
            # Face toward center of ally group
            ally_center = _calculate_center_position(allies)
            enemy.combat_position.facing = turn_toward(enemy.combat_position, ally_center)
    
    # Update proximity dicts for backward compatibility
    all_combatants = allies + enemies
    for unit in all_combatants:
        unit.combat_proximity = recalculate_proximity_dict(unit, all_combatants)


def _spawn_units_in_zone(
    units: List[Any],
    zone: Tuple[Tuple[int, int], Tuple[int, int]],
    formation_type: str = "spread",
    min_spacing: int = 1,
    seed: Optional[int] = None
) -> None:
    """Spawn units within a zone using the specified formation.
    
    Args:
        units: Units to spawn
        zone: Spawn zone boundaries
        formation_type: "spread", "cluster", or "random"
        min_spacing: Minimum grid squares between units
        seed: Random seed for reproducibility
    """
    if seed is not None:
        random.seed(seed)
    
    spawned = []
    
    for unit in units:
        if formation_type == "spread":
            # Distribute units across zone with spacing
            position = _find_spaced_position(
                zone,
                spawned,
                min_spacing
            )
        elif formation_type == "cluster":
            # Cluster units tightly in center of zone
            position = _find_clustered_position(zone, spawned, min_spacing)
        else:  # "random"
            # Random placement with minimum spacing
            position = _find_random_position(zone, spawned, min_spacing)
        
        unit.combat_position = position
        spawned.append(position)


def _find_spaced_position(
    zone: Tuple[Tuple[int, int], Tuple[int, int]],
    occupied: List[CombatPosition],
    min_spacing: int
) -> CombatPosition:
    """Find a position in zone with minimum spacing from occupied positions.
    
    Attempts to find a valid position, with fallback to random if too constrained.
    """
    (x_min, y_min), (x_max, y_max) = zone
    max_attempts = 20
    
    for _ in range(max_attempts):
        pos = random_position_in_zone(zone)
        
        # Check spacing constraint
        valid = True
        for occupied_pos in occupied:
            dist = distance_from_coords(pos, occupied_pos)
            if dist < min_spacing:
                valid = False
                break
        
        if valid:
            return pos
    
    # Fallback: return random position anyway
    return random_position_in_zone(zone)


def _find_clustered_position(
    zone: Tuple[Tuple[int, int], Tuple[int, int]],
    occupied: List[CombatPosition],
    min_spacing: int
) -> CombatPosition:
    """Find position clustered near other units in zone.
    
    For cluster formation: positions are close together rather than spread.
    """
    if not occupied:
        # First unit in cluster: center of zone
        (x_min, y_min), (x_max, y_max) = zone
        center_x = (x_min + x_max) // 2
        center_y = (y_min + y_max) // 2
        return CombatPosition(x=center_x, y=center_y)
    
    # Subsequent units: near existing cluster
    cluster_center = _calculate_center_position(occupied)
    
    # Try positions in spiral around cluster center
    for distance in range(1, 5):
        for dx in range(-distance, distance + 1):
            for dy in range(-distance, distance + 1):
                if abs(dx) != distance and abs(dy) != distance:
                    continue  # Only check perimeter
                
                x = cluster_center.x + dx
                y = cluster_center.y + dy
                
                if not (0 <= x <= 50 and 0 <= y <= 50):
                    continue
                
                # Check if position is in zone and has spacing
                if _is_in_zone((x, y), zone):
                    pos = CombatPosition(x=x, y=y)
                    
                    # Verify spacing
                    valid = True
                    for occupied_pos in occupied:
                        if distance_from_coords(pos, occupied_pos) < min_spacing:
                            valid = False
                            break
                    
                    if valid:
                        return pos
    
    # Fallback
    return random_position_in_zone(zone)


def _find_random_position(
    zone: Tuple[Tuple[int, int], Tuple[int, int]],
    occupied: List[CombatPosition],
    min_spacing: int
) -> CombatPosition:
    """Find random position in zone with minimum spacing.
    
    Simpler than spread formation - just ensures min_spacing.
    """
    return _find_spaced_position(zone, occupied, min_spacing)


def _is_in_zone(
    point: Tuple[int, int],
    zone: Tuple[Tuple[int, int], Tuple[int, int]]
) -> bool:
    """Check if a point is within a zone."""
    (x_min, y_min), (x_max, y_max) = zone
    x, y = point
    return x_min <= x <= x_max and y_min <= y <= y_max


def _calculate_center_position(
    positions: List[Any]
) -> CombatPosition:
    """Calculate center point of all combat positions.
    
    Args:
        positions: List of units with combat_position attribute
    
    Returns:
        CombatPosition at center (average x, y)
    """
    valid_positions = [
        u.combat_position for u in positions
        if hasattr(u, 'combat_position') and u.combat_position is not None
    ]
    
    if not valid_positions:
        return CombatPosition(x=25, y=25)  # Grid center as fallback
    
    avg_x = sum(p.x for p in valid_positions) // len(valid_positions)
    avg_y = sum(p.y for p in valid_positions) // len(valid_positions)
    
    return CombatPosition(x=avg_x, y=avg_y)


def _distribute_units_across_zones(
    units: List[Any],
    total_zones: int,
    zone_index: int
) -> List[Any]:
    """Distribute units across multiple spawn zones.
    
    Args:
        units: All units to spawn
        total_zones: Total number of zones
        zone_index: Current zone index (0-based)
    
    Returns:
        Subset of units for this zone
    """
    if total_zones == 1:
        return units
    
    # Simple round-robin distribution
    return [u for i, u in enumerate(units) if i % total_zones == zone_index]


__all__ = [
    'Direction',
    'CombatPosition',
    'CombatScenario',
    'COMBAT_SCENARIOS',
    'distance_from_coords',
    'distance_squared',
    'angle_to_target',
    'attack_angle_difference',
    'get_damage_modifier',
    'get_accuracy_modifier',
    'random_position_in_zone',
    'clamp_position',
    'move_toward',
    'move_away_from',
    'move_to_flank',
    'turn_toward',
    'recalculate_proximity_dict',
    'initialize_combat_positions',
]
