"""NPC AI Configuration for Phase 2.4.

Manages tactical behavior flags for NPCs, including flanking, retreat, and positioning logic.
Provides decision framework that integrates with combat.py AI decision-making.
"""

from typing import Any, Dict, List, Optional, Tuple

from src import positions
import src.terrain as terrain


class NPCAIConfig:
    """Manages NPC AI behavior configuration from GameConfig."""

    #: Moves that reposition toward or around the target; rewarded when the
    #: ground favours moving (terrain rules) or a flank is worth taking.
    _REPOSITION_MOVES = ("advance", "flanking maneuver", "tactical positioning")
    #: Moves that open distance; rewarded when standing in a hazard.
    _RETREAT_MOVES = ("withdraw", "tactical retreat")
    #: Defensive fallbacks preferred when health is low.
    _LOW_HEALTH_MOVES = ("withdraw", "dodge", "parry", "npc_rest")

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
        self,
        attacker,
        target,
        ignore_unit: Optional[object] = None,
        distance: Optional[int] = None,
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
            distance: Stand-off from the target the maneuver will use this
                beat (terrain scoring lands on that cell); defaults to
                ``positions.FLANK_OFFSET``

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
            grid = terrain.grid_for(attacker)
            if grid is not None:
                # With terrain the nearer blind side may be a wall; score both
                # landing cells (reachability, cover, elevation) at the same
                # stand-off the maneuver will walk to.
                bearing = terrain.best_flank_bearing(
                    grid,
                    a_pos,
                    t_pos,
                    distance if distance is not None else positions.FLANK_OFFSET,
                )
                if bearing is not None:
                    return bearing
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

    def calculate_retreat_priority(self, npc, _enemies: list) -> float:
        """Calculate priority score for retreat (0.0-1.0, higher = more urgent).

        Args:
            npc: The NPC being evaluated
            _enemies: List of enemies the NPC faces. Currently unused -- the
                priority is a pure health-ratio calculation (see below) and
                does not weigh threat count. Kept as a parameter (leading
                underscore signals intentionally-unused) rather than dropped,
                since the sole production caller (``src/npc/_combat.py``)
                already passes it positionally; wiring enemy count/threat
                into the score is a balance decision, not made here.

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
        # At threshold: priority = 0.0
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
            if move_l in self._LOW_HEALTH_MOVES:
                bonus += 3

        bonus += self.get_terrain_move_bonus(npc, move_name)

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
                        elif move_l in self._REPOSITION_MOVES:
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

    def _terrain_context(self, npc) -> Optional[Dict[str, Any]]:
        """Everything the terrain rules need, computed once per move selection.

        ``select_move`` weights every known move in a loop; the ground under
        the NPC and its line to the target do not change between iterations,
        so the lookups (``standing_on`` and ``engagement``, a line-of-sight
        walk) are cached on the NPC keyed by the two cells. None when terrain
        is inactive or the NPC has no target.
        """
        grid = terrain.grid_for(npc)
        target = getattr(npc, "target", None)
        if grid is None or target is None:
            return None
        npc_pos = getattr(npc, "combat_position", None)
        target_pos = getattr(target, "combat_position", None)
        if npc_pos is None or target_pos is None:
            return None
        key = (id(grid), positions.as_cell(npc_pos), positions.as_cell(target_pos))
        cached = getattr(npc, "_terrain_ai_context", None)
        if isinstance(cached, tuple) and cached[0] == key:
            return cached[1]
        here = terrain.standing_on(npc)
        # Scored as a shot: the cover/LOS numbers only matter to ranged moves,
        # and the per-move branch checks the move's own kind.
        info = terrain.engagement(npc, target, ranged=True)
        known = getattr(npc, "known_moves", None) or []
        take_ground = next(
            (m for m in known if getattr(m, "name", "").lower() == "take ground"), None
        )
        context = {
            "on_hazard": bool(here and here["kind"] == terrain.HAZARD),
            "elevation": info["elevation"] if info else 0,
            "cover": info["cover"] if info else 0,
            "blocked_los": bool(info and info["blocked_los"]),
            "can_reposition": any(
                getattr(m, "name", "").lower() in self._REPOSITION_MOVES
                and self._move_viable(m)
                for m in known
            ),
            "better_ground": take_ground is not None and self._move_viable(take_ground),
        }
        try:
            npc._terrain_ai_context = (key, context)
        except AttributeError:
            pass
        return context

    @staticmethod
    def _move_viable(move) -> bool:
        try:
            return bool(move.viable())
        except Exception:
            return False

    def get_terrain_move_bonus(self, npc, move_name: str) -> int:
        """Terrain-awareness half of ``get_weighted_move_bonus``.

        Returns 0 whenever terrain is inactive, so legacy proximity-only
        fights and test doubles are untouched. Rules, all cheap and local:

        * standing in a hazard -- get off it (movement moves +3)
        * target holds higher ground and a reposition move is viable --
          close or flank rather than trade blows uphill (+2 movement,
          -1 offensive); with nothing to reposition with, no penalty
        * we hold higher ground -- press it (+2 offensive)
        * target sits behind cover -- a ranged move is worth less (-2, or -4
          with no line of sight at all); reposition instead (+2 movement)
        * better ground is within reach (``Take Ground`` viable) and the
          field is working against us -- take it (+3)
        """
        context = self._terrain_context(npc)
        if context is None:
            return 0
        move_l = move_name.lower()
        reposition = move_l in self._REPOSITION_MOVES
        bonus = 0
        if context["on_hazard"] and (reposition or move_l in self._RETREAT_MOVES):
            bonus += 3
        offensive = self._move_is_offensive(npc, move_name)
        if context["elevation"] < 0 and context["can_reposition"]:
            if reposition:
                bonus += 2
            elif offensive:
                bonus -= 1
        elif context["elevation"] > 0 and offensive:
            bonus += 2
        ranged = self._move_is_ranged(npc, move_name)
        if context["cover"] and reposition:
            bonus += 2
        if context["cover"] and ranged:
            bonus -= 4 if context["blocked_los"] else 2
        pressured = context["on_hazard"] or context["elevation"] < 0 or context["cover"]
        if move_l == "take ground" and context["better_ground"] and pressured:
            bonus += 3
        return bonus

    @staticmethod
    def _move_is_ranged(npc, move_name: str) -> bool:
        """Whether the named move is a shot (``Move.is_ranged``), by roster."""
        move_l = move_name.lower()
        for move in getattr(npc, "known_moves", None) or []:
            if getattr(move, "name", "").lower() == move_l:
                return bool(getattr(move, "is_ranged", False))
        return False

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
