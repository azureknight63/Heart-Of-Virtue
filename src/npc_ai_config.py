"""NPC AI Configuration for Phase 2.4.

Manages tactical behavior flags for NPCs, including flanking, retreat, and positioning logic.
Provides decision framework that integrates with combat.py AI decision-making.
"""

from typing import Tuple, Optional


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
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.npc_flanking_enabled
        return True  # Default enabled
    
    def is_tactical_retreat_enabled(self) -> bool:
        """Check if NPC tactical retreat behavior is enabled.
        
        Returns:
            True if tactical retreat is enabled, False otherwise
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.npc_tactical_retreat
        return True  # Default enabled
    
    def get_flanking_threshold(self) -> float:
        """Get angle threshold for flanking detection (degrees).
        
        Returns:
            Angle threshold in degrees (default 45.0)
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.npc_flanking_threshold
        return 45.0
    
    def get_retreat_health_threshold(self) -> float:
        """Get health percentage threshold for tactical retreat.
        
        Returns:
            Health ratio (0.0-1.0, default 0.3 = 30%)
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.npc_retreat_health_threshold
        return 0.3
    
    def get_flanking_distance_range(self) -> Tuple[float, float]:
        """Get valid distance range for flanking attacks.
        
        Returns:
            Tuple of (min_distance, max_distance)
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            range_str = self.player.game_config.npc_flanking_distance_range
            # Parse "min to max" format
            try:
                parts = range_str.split('to')
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
        if not hasattr(npc, 'target') or npc.target is None:
            return False
        
        # Check if we're in valid flanking range
        if not hasattr(npc, 'combat_proximity') or not npc.target:
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
        
        if not npc or not hasattr(npc, 'hp') or not hasattr(npc, 'maxhp'):
            return False
        
        # Check if health is below threshold
        health_ratio = npc.hp / max(1, npc.maxhp)
        threshold = self.get_retreat_health_threshold()
        
        return health_ratio <= threshold
    
    def get_flank_position_angle(self, attacker, target, ignore_unit: Optional[object] = None) -> Optional[float]:
        """Calculate optimal flanking angle relative to target and attacker.
        
        Args:
            attacker: The NPC attempting to flank
            target: The enemy being targeted
            ignore_unit: Optional unit to ignore in calculations (e.g., self)
            
        Returns:
            Angle in degrees where flank should be attempted, or None if no flank available
        """
        if not self.is_flanking_enabled():
            return None
        
        if not attacker or not target:
            return None
        
        # Ideal flank angle is 90-180 degrees from attacker's line to target
        # This represents attacking from the side or rear
        threshold = self.get_flanking_threshold()
        
        # Would need position/angle tracking to implement fully
        # For now, return a calculated flank angle
        ideal_flank = 90.0  # Perpendicular to direct attack line
        
        return ideal_flank
    
    def calculate_retreat_priority(self, npc, enemies: list) -> float:
        """Calculate priority score for retreat (0.0-1.0, higher = more urgent).
        
        Args:
            npc: The NPC being evaluated
            enemies: List of enemies the NPC faces
            
        Returns:
            Priority score (0.0 = no retreat needed, 1.0 = critical retreat needed)
        """
        if not npc or not hasattr(npc, 'hp') or not hasattr(npc, 'maxhp'):
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
    
    def get_weighted_move_bonus(self, npc, move_name: str) -> int:
        """Get bonus weight for a move based on AI config.
        
        Args:
            npc: The NPC selecting the move
            move_name: Name of the move being considered
            
        Returns:
            Weight bonus (0 = no change, positive = increase weight, negative = decrease)
        """
        bonus = 0
        
        # Bonus for retreat moves when health is low
        if self.should_attempt_retreat(npc):
            if move_name.lower() in ['withdraw', 'dodge', 'parry', 'npc_rest']:
                bonus += 3
        
        # Bonus for flanking moves when conditions are right
        if self.is_flanking_enabled() and hasattr(npc, 'target') and npc.target:
            if move_name.lower() in ['advance', 'npc_attack', 'tactical_positioning']:
                # Check if currently in flank range
                if hasattr(npc, 'combat_proximity') and npc.target in npc.combat_proximity:
                    distance = npc.combat_proximity[npc.target]
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


class AIDecisionValidator:
    """Validates NPC AI decisions based on config rules."""
    
    def __init__(self, ai_config: NPCAIConfig):
        """Initialize with AI config.
        
        Args:
            ai_config: NPCAIConfig instance
        """
        self.ai_config = ai_config
    
    def is_valid_flank_decision(self, npc, target, allies: list) -> Tuple[bool, str]:
        """Validate if flanking decision is valid for this NPC.
        
        Args:
            npc: The NPC making the decision
            target: The target being considered
            allies: List of allied NPCs
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        if not self.ai_config.is_flanking_enabled():
            return (False, "Flanking is disabled")
        
        if not npc:
            return (False, "NPC is None")
        
        if not target:
            return (False, "No target available")
        
        if len(allies) < 2:
            return (False, f"Insufficient allies for flank ({len(allies)} < 2)")
        
        if not hasattr(npc, 'combat_proximity') or target not in npc.combat_proximity:
            return (False, "Target not in proximity range")
        
        distance = npc.combat_proximity[target]
        min_range, max_range = self.ai_config.get_flanking_distance_range()
        
        if distance < min_range or distance > max_range:
            return (False, f"Target outside flank range ({distance:.1f} not in {min_range}-{max_range})")
        
        return (True, "Flanking conditions met")
    
    def is_valid_retreat_decision(self, npc) -> Tuple[bool, str]:
        """Validate if retreat decision is valid for this NPC.
        
        Args:
            npc: The NPC making the decision
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        if not self.ai_config.is_tactical_retreat_enabled():
            return (False, "Tactical retreat is disabled")
        
        if not npc:
            return (False, "NPC is None")
        
        if not hasattr(npc, 'hp') or not hasattr(npc, 'maxhp'):
            return (False, "NPC missing health attributes")
        
        health_ratio = npc.hp / max(1, npc.maxhp)
        threshold = self.ai_config.get_retreat_health_threshold()
        
        if health_ratio > threshold:
            return (False, f"Health above threshold ({health_ratio:.1%} > {threshold:.1%})")
        
        return (True, f"Health critical ({health_ratio:.1%} <= {threshold:.1%})")
    
    def is_valid_flank_distance(self, distance: float) -> Tuple[bool, str]:
        """Validate if distance is within flanking range.
        
        Args:
            distance: Distance to validate
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        min_range, max_range = self.ai_config.get_flanking_distance_range()
        
        if distance < min_range:
            return (False, f"Distance too close ({distance:.1f} < {min_range})")
        
        if distance > max_range:
            return (False, f"Distance too far ({distance:.1f} > {max_range})")
        
        return (True, f"Distance in valid range ({distance:.1f} in {min_range}-{max_range})")
    
    def is_valid_retreat_priority(self, priority: float) -> Tuple[bool, str]:
        """Validate if retreat priority is reasonable.
        
        Args:
            priority: Priority score (0.0-1.0)
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        if priority < 0.0 or priority > 1.0:
            return (False, f"Priority out of range ({priority:.2f} not in 0.0-1.0)")
        
        if priority < 0.3:
            return (True, f"Low retreat priority ({priority:.2%})")
        elif priority < 0.7:
            return (True, f"Moderate retreat priority ({priority:.2%})")
        else:
            return (True, f"High retreat priority ({priority:.2%})")
    
    def validate_all_settings(self) -> Tuple[bool, list]:
        """Validate all AI configuration settings.
        
        Returns:
            Tuple of (all_valid, list_of_issues)
        """
        issues = []
        
        # Check flanking threshold
        threshold = self.ai_config.get_flanking_threshold()
        if threshold < 0 or threshold > 180:
            issues.append(f"Flanking threshold out of range: {threshold}° (must be 0-180°)")
        
        # Check retreat threshold
        retreat_threshold = self.ai_config.get_retreat_health_threshold()
        if retreat_threshold < 0.0 or retreat_threshold > 1.0:
            issues.append(f"Retreat threshold out of range: {retreat_threshold} (must be 0.0-1.0)")
        
        # Check distance range
        min_range, max_range = self.ai_config.get_flanking_distance_range()
        if min_range < 0 or max_range < 0:
            issues.append(f"Flank distance range contains negative value: {min_range}-{max_range}")
        if min_range > max_range:
            issues.append(f"Flank distance min ({min_range}) > max ({max_range})")
        
        return (len(issues) == 0, issues)
