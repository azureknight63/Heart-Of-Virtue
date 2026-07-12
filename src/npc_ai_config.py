"""NPC AI Configuration for Phase 2.4.

Manages tactical behavior flags for NPCs, including flanking, retreat, and positioning logic.
Provides decision framework that integrates with combat.py AI decision-making.
"""

from typing import Tuple, Optional, List

from src import positions


class NPCAIConfig:
    """Manages NPC AI behavior configuration from GameConfig."""

    def __init__(self, player):
        """Initialize with player reference for accessing config.

        Args:
            player: Player object with game_config
        """
        self.player = player

    def is_flanking_enabled(self) -> bool:
        """Check if NPC flanking behavior is enabled.

        Returns:
            True if flanking is enabled, False otherwise
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.npc_flanking_enabled
        return True  # Default enabled

    def is_tactical_retreat_enabled(self) -> bool:
        """Check if NPC tactical retreat behavior is enabled.

        Returns:
            True if tactical retreat is enabled, False otherwise
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.npc_tactical_retreat
        return True  # Default enabled

    def get_flanking_threshold(self) -> float:
        """Get angle threshold for flanking detection (degrees).

        Returns:
            Angle threshold in degrees (default 45.0)
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.npc_flanking_threshold
        return 45.0

    def get_retreat_health_threshold(self) -> float:
        """Get health percentage threshold for tactical retreat.

        Returns:
            Health ratio (0.0-1.0, default 0.3 = 30%)
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            return self.player.game_config.npc_retreat_health_threshold
        return 0.3

    def get_flanking_distance_range(self) -> Tuple[float, float]:
        """Get valid distance range for flanking attacks.

        Returns:
            Tuple of (min_distance, max_distance)
        """
        if hasattr(self.player, "game_config") and self.player.game_config:
            range_str = self.player.game_config.npc_flanking_distance_range
            # Parse "min to max" format
            try:
                parts = range_str.split("to")
                if len(parts) == 2:
                    min_dist = float(parts[0].strip())
                    max_dist = float(parts[1].strip())
                    return (min_dist, max_dist)
            except (ValueError, AttributeError):
                pass
        return (20.0, 40.0)  # Default range

    def should_attempt_flank(self, npc, allies: list, enemies: list) -> bool:
        """Determine if NPC should attempt to flank.

        Args:
            npc: The NPC considering the action
            allies: List of allied NPCs
            enemies: List of enemies

        Returns:
            True if flanking should be attempted, False otherwise
        """
        if not self.is_flanking_enabled():
            return False

        if not npc or not enemies:
            return False

        # Check if NPC has enough allies to support flanking
        if len(allies) < 2:
            return False

        # Check if target is available
        if not hasattr(npc, "target") or npc.target is None:
            return False

        # Check if we're in valid flanking range
        if not hasattr(npc, "combat_proximity") or not npc.target:
            return False

        distance = npc.combat_proximity.get(npc.target, 0)
        min_range, max_range = self.get_flanking_distance_range()

        if distance < min_range or distance > max_range:
            return False

        return True

    def should_attempt_retreat(self, npc) -> bool:
        """Determine if NPC should attempt tactical retreat.

        Args:
            npc: The NPC considering retreat

        Returns:
            True if retreat should be attempted, False otherwise
        """
        if not self.is_tactical_retreat_enabled():
            return False

        if not npc or not hasattr(npc, "hp") or not hasattr(npc, "maxhp"):
            return False

        # Check if health is below threshold
        health_ratio = npc.hp / max(1, npc.maxhp)
        threshold = self.get_retreat_health_threshold()

        return health_ratio <= threshold

    def get_current_angle_diff(self, attacker, target) -> Optional[float]:
        """Angular difference (0-180°) between the attack line and target's facing.

        Uses the coordinate positioning system (``src.positions``). 0° means the
        attacker is striking the target head-on; 90° is a clean flank; 180° is a
        strike from directly behind.

        Args:
            attacker: The unit making the attack
            target: The unit being attacked

        Returns:
            The angular difference in degrees, or None when either unit lacks a
            ``combat_position`` (e.g. legacy proximity-only combat or unit tests).
        """
        if not attacker or not target:
            return None

        a_pos = getattr(attacker, "combat_position", None)
        t_pos = getattr(target, "combat_position", None)
        if a_pos is None or t_pos is None:
            return None

        try:
            attack_angle = positions.angle_to_target(t_pos, a_pos)
            return float(positions.attack_angle_difference(attack_angle, t_pos.facing))
        except (AttributeError, TypeError):
            return None

    def get_flank_position_angle(
        self, attacker, target, ignore_unit: Optional[object] = None
    ) -> Optional[float]:
        """Calculate the bearing the attacker should approach from to flank target.

        A target's blind sides sit perpendicular to its facing (facing ± 90°).
        This returns whichever of those two bearings is closer to the attacker's
        current position, so the maneuver is the shortest one available. The
        result is a world-angle (0-360°, 0 = North) usable with the movement
        helpers in ``src.positions`` (e.g. to steer ``move_to_flank``).

        Args:
            attacker: The NPC attempting to flank
            target: The enemy being targeted
            ignore_unit: Optional unit to ignore in calculations (e.g., self)

        Returns:
            The approach bearing in degrees, or None if flanking is disabled or
            either unit lacks positional (``combat_position``) data.
        """
        if not self.is_flanking_enabled():
            return None

        if not attacker or not target:
            return None

        a_pos = getattr(attacker, "combat_position", None)
        t_pos = getattr(target, "combat_position", None)
        if a_pos is None or t_pos is None:
            return None

        try:
            return positions.nearest_flank_bearing(a_pos, t_pos)
        except (AttributeError, TypeError):
            return None

    def _derive_combat_sides(self, npc) -> Tuple[List, List]:
        """Split the active combat into (allies, enemies) from the NPC's view.

        Allies are the combatants sharing the NPC's side (including the NPC
        itself); enemies are the opposing side. Combat rosters live on the
        player: ``combat_list`` (enemies of the player) and
        ``combat_list_allies`` (friendly NPCs).

        Returns:
            (allies, enemies) lists, or ([], []) when no combat context exists.
        """
        player = getattr(npc, "player_ref", None) or self.player
        if player is None:
            return [], []

        enemy_side = list(getattr(player, "combat_list", []) or [])
        ally_side = list(getattr(player, "combat_list_allies", []) or [])

        if getattr(npc, "friend", False):
            return [player] + ally_side, enemy_side
        return enemy_side, [player] + ally_side

    def calculate_retreat_priority(self, npc, enemies: list) -> float:
        """Calculate priority score for retreat (0.0-1.0, higher = more urgent).

        Args:
            npc: The NPC being evaluated
            enemies: List of enemies the NPC faces

        Returns:
            Priority score (0.0 = no retreat needed, 1.0 = critical retreat needed)
        """
        if not npc or not hasattr(npc, "hp") or not hasattr(npc, "maxhp"):
            return 0.0

        if not self.is_tactical_retreat_enabled():
            return 0.0

        # Base priority on health ratio
        health_ratio = npc.hp / max(1, npc.maxhp)
        threshold = self.get_retreat_health_threshold()

        if health_ratio > threshold:
            return 0.0  # No retreat needed

        # Scale priority between threshold and 0 HP
        # At threshold: 0.3, priority = ~0.3
        # At 0 HP: priority = 1.0
        priority = 1.0 - (health_ratio / max(0.001, threshold))
        return min(1.0, max(0.0, priority))

    @staticmethod
    def _move_is_offensive(npc, move_name: str) -> bool:
        """Whether the named move is an attack, by the NPC's own move roster.

        Looks the move up on ``npc.known_moves`` and checks its ``category`` so
        the flank-capitalize bonus applies to every offensive move (PowerStrike,
        VenomClaw, BatBite, …), not just the generic ``NPC_Attack``. Falls back
        to the generic attack names when the move object isn't available.
        """
        move_l = move_name.lower()
        for move in getattr(npc, "known_moves", None) or []:
            if getattr(move, "name", "").lower() == move_l:
                return getattr(move, "category", "") == "Offensive"
        return move_l in ("npc_attack", "attack")

    def get_weighted_move_bonus(self, npc, move_name: str) -> int:
        """Get bonus weight for a move based on AI config.

        Args:
            npc: The NPC selecting the move
            move_name: Name of the move being considered

        Returns:
            Weight bonus (0 = no change, positive = increase weight, negative = decrease)
        """
        bonus = 0

        move_l = move_name.lower()

        # Bonus for retreat moves when health is low
        if self.should_attempt_retreat(npc):
            if move_l in ["withdraw", "dodge", "parry", "npc_rest"]:
                bonus += 3

        # Bonus for flanking moves when conditions are right
        if self.is_flanking_enabled() and getattr(npc, "target", None):
            target = npc.target
            angle_diff = self.get_current_angle_diff(npc, target)

            if angle_diff is not None:
                # Real positional data: steer the NPC by the target's true facing.
                if angle_diff > self.get_flanking_threshold():
                    # Already on the target's flank/rear — press the attack to
                    # cash in the positional damage/accuracy bonus.
                    if self._move_is_offensive(npc, move_name):
                        bonus += 2
                else:
                    # Facing the target head-on. If flanking is worthwhile, reward
                    # the moves that actually reposition to the target's blind side.
                    allies, enemies = self._derive_combat_sides(npc)
                    if self.should_attempt_flank(npc, allies, enemies):
                        if move_l == "flanking maneuver":
                            bonus += 3
                        elif move_l in ["advance", "tactical positioning"]:
                            bonus += 2
            else:
                # No coordinate data (legacy proximity-only combat): fall back to
                # the distance-band heuristic.
                if move_l in ["advance", "npc_attack", "tactical positioning"]:
                    if (
                        hasattr(npc, "combat_proximity")
                        and target in npc.combat_proximity
                    ):
                        distance = npc.combat_proximity[target]
                        min_range, max_range = self.get_flanking_distance_range()
                        if min_range <= distance <= max_range:
                            bonus += 2

        return bonus

    def get_ai_config_summary(self) -> str:
        """Get human-readable summary of current AI configuration.

        Returns:
            Formatted string with all AI settings
        """
        flanking_enabled = self.is_flanking_enabled()
        retreat_enabled = self.is_tactical_retreat_enabled()
        flank_threshold = self.get_flanking_threshold()
        retreat_threshold = self.get_retreat_health_threshold()
        flank_range = self.get_flanking_distance_range()

        summary = (
            f"NPC AI Configuration:\n"
            f"  Flanking Enabled: {flanking_enabled}\n"
            f"  Flanking Threshold: {flank_threshold}°\n"
            f"  Flanking Distance Range: {flank_range[0]}-{flank_range[1]} units\n"
            f"  Tactical Retreat Enabled: {retreat_enabled}\n"
            f"  Retreat Health Threshold: {retreat_threshold * 100:.1f}%"
        )
        return summary
