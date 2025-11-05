"""Display configuration and utilities for Phase 2 combat visualization.

Provides functions to display combat information based on player config settings.
Respects flags like show_combat_distance, show_unit_positions, show_damage_modifiers, etc.
"""

from neotermcolor import colored, cprint


class CombatDisplayConfig:
    """Centralized combat display configuration."""
    
    def __init__(self, player):
        """Initialize with player reference for accessing config."""
        self.player = player
    
    def should_show_distance(self):
        """Check if combat distance should be displayed."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.show_combat_distance
        return True  # Default to showing
    
    def should_show_positions(self):
        """Check if unit positions should be displayed."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.show_unit_positions
        return True  # Default to showing
    
    def should_show_facing(self):
        """Check if facing directions should be displayed."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.show_facing_directions
        return True  # Default to showing
    
    def should_show_damage_modifiers(self):
        """Check if damage modifiers should be displayed."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.show_damage_modifiers
        return True  # Default to showing
    
    def should_show_accuracy_modifiers(self):
        """Check if accuracy modifiers should be displayed."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.show_accuracy_modifiers
        return True  # Default to showing
    
    def should_show_coordinate_display(self):
        """Check if full coordinate display should be shown."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.show_coordinate_display
        return True  # Default to showing


def display_enemy_status(enemy, display_config):
    """Display enemy status line with configurable information.
    
    Args:
        enemy: NPC enemy object
        display_config: CombatDisplayConfig instance
        
    Returns:
        Formatted status line string
    """
    status_parts = []
    
    # Basic name and health
    name = colored(enemy.name, "red", attrs=["bold"])
    hp_pct = int((enemy.hp / enemy.maxhp) * 100) if enemy.maxhp > 0 else 0
    hp_str = colored(f"HP: {hp_pct}%", "red" if hp_pct < 25 else "yellow" if hp_pct < 50 else "green")
    status_parts.append(f"{name} - {hp_str}")
    
    # Show position if configured
    if display_config.should_show_positions() and hasattr(enemy, 'combat_position') and enemy.combat_position:
        pos = enemy.combat_position
        pos_str = colored(f"({pos.x}, {pos.y})", "cyan")
        status_parts.append(pos_str)
    
    # Show distance if configured
    if display_config.should_show_distance() and hasattr(display_config.player, 'combat_proximity'):
        if enemy in display_config.player.combat_proximity:
            distance = display_config.player.combat_proximity[enemy]
            dist_str = colored(f"Dist: {distance}", "yellow")
            status_parts.append(dist_str)
    
    return " | ".join(status_parts)


def display_all_enemies(player, display_config=None):
    """Display all current enemies in a formatted list.
    
    Args:
        player: Player object
        display_config: CombatDisplayConfig instance (created if not provided)
        
    Returns:
        Formatted display string
    """
    if display_config is None:
        display_config = CombatDisplayConfig(player)
    
    if not player.combat_list:
        return "No enemies"
    
    lines = []
    for i, enemy in enumerate(player.combat_list, 1):
        status_line = display_enemy_status(enemy, display_config)
        lines.append(f"{i}. {status_line}")
    
    return "\n".join(lines)


def display_damage_modifier_info(attacker, defender, damage_base, display_config=None):
    """Display damage modifier calculation if configured.
    
    Args:
        attacker: Attacking unit
        defender: Defending unit
        damage_base: Base damage before modifiers
        display_config: CombatDisplayConfig instance
        
    Returns:
        Formatted modifier info string or empty string
    """
    if display_config is None:
        display_config = CombatDisplayConfig(attacker)
    
    if not display_config.should_show_damage_modifiers():
        return ""
    
    # Calculate modifiers (placeholder logic)
    modifiers = []
    
    # Distance modifier
    if hasattr(attacker, 'combat_proximity') and defender in attacker.combat_proximity:
        distance = attacker.combat_proximity[defender]
        if distance > 30:
            modifiers.append("Range (0.8x)")
        elif distance < 5:
            modifiers.append("Melee (1.2x)")
    
    # Positioning modifier
    if hasattr(attacker, 'combat_position') and hasattr(defender, 'combat_position'):
        if attacker.combat_position and defender.combat_position:
            # Simple flanking check
            modifiers.append("Flanked (1.5x)" if False else "Standard (1.0x)")  # Placeholder
    
    if not modifiers:
        return ""
    
    return " | " + colored("Modifiers: " + ", ".join(modifiers), "magenta")


def display_accuracy_modifier_info(attacker, defender, base_accuracy, display_config=None):
    """Display accuracy modifier calculation if configured.
    
    Args:
        attacker: Attacking unit
        defender: Defending unit
        base_accuracy: Base accuracy before modifiers
        display_config: CombatDisplayConfig instance
        
    Returns:
        Formatted accuracy info string or empty string
    """
    if display_config is None:
        display_config = CombatDisplayConfig(attacker)
    
    if not display_config.should_show_accuracy_modifiers():
        return ""
    
    # Calculate accuracy modifiers
    modifiers = []
    
    # Speed-based accuracy
    speed_mod = attacker.speed - defender.speed
    if speed_mod > 5:
        modifiers.append("Speed Bonus")
    elif speed_mod < -5:
        modifiers.append("Speed Penalty")
    
    # Fatigue-based accuracy
    if hasattr(attacker, 'fatigue') and hasattr(attacker, 'maxfatigue'):
        fatigue_pct = attacker.fatigue / attacker.maxfatigue if attacker.maxfatigue > 0 else 1.0
        if fatigue_pct < 0.3:
            modifiers.append("Fatigued (-10%)")
    
    if not modifiers:
        return ""
    
    return " | " + colored("Accuracy: " + ", ".join(modifiers), "cyan")


def display_full_coordinate_grid(player, display_config=None):
    """Display full coordinate grid of combat positions if configured.
    
    Args:
        player: Player object
        display_config: CombatDisplayConfig instance
        
    Returns:
        Formatted grid string or empty string
    """
    if display_config is None:
        display_config = CombatDisplayConfig(player)
    
    if not display_config.should_show_coordinate_display():
        return ""
    
    if not hasattr(player, 'game_config') or not player.game_config:
        return ""
    
    grid_size = player.game_config.coordinate_grid_size
    
    # Create position map
    positions_map = {}
    all_units = player.combat_list_allies + player.combat_list
    
    for unit in all_units:
        if hasattr(unit, 'combat_position') and unit.combat_position:
            pos = unit.combat_position
            if (pos.x, pos.y) not in positions_map:
                positions_map[(pos.x, pos.y)] = []
            positions_map[(pos.x, pos.y)].append(unit)
    
    # Build grid string (simplified - full grid can be very large)
    lines = [colored("Combat Grid:", "cyan", attrs=["bold"])]
    
    # Show only occupied coordinates for readability
    for (x, y), units in sorted(positions_map.items()):
        unit_names = ", ".join([u.name for u in units])
        lines.append(f"  ({x:3}, {y:3}): {unit_names}")
    
    return "\n".join(lines)


def format_enemy_list_for_targeting(player, display_config=None):
    """Format enemy list for move targeting display.
    
    Args:
        player: Player object
        display_config: CombatDisplayConfig instance
        
    Returns:
        Formatted target list with distance/position info
    """
    if display_config is None:
        display_config = CombatDisplayConfig(player)
    
    lines = [colored("Available Targets:", "yellow")]
    
    for i, enemy in enumerate(player.combat_list, 1):
        # Basic enemy info
        enemy_line = f"  {i}. {colored(enemy.name, 'red')}"
        
        # Add distance if configured
        if display_config.should_show_distance() and hasattr(player, 'combat_proximity'):
            if enemy in player.combat_proximity:
                distance = player.combat_proximity[enemy]
                enemy_line += f" {colored(f'[{distance} ft]', 'yellow')}"
        
        # Add position if configured
        if display_config.should_show_positions() and hasattr(enemy, 'combat_position') and enemy.combat_position:
            pos = enemy.combat_position
            enemy_line += f" {colored(f'@({pos.x},{pos.y})', 'cyan')}"
        
        # Add HP
        hp_pct = int((enemy.hp / enemy.maxhp) * 100) if enemy.maxhp > 0 else 0
        hp_color = "red" if hp_pct < 25 else "yellow" if hp_pct < 50 else "green"
        enemy_line += f" {colored(f'HP:{hp_pct}%', hp_color)}"
        
        lines.append(enemy_line)
    
    return "\n".join(lines)
