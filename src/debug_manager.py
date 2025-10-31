"""Debug Manager for Phase 2.6.

Provides centralized debug commands and information display for testing and development.
Integrates with config flags to enable/disable different debug features during combat testing.
"""

from typing import Dict, Any, List, Tuple, Optional, Callable


class DebugManager:
    """Manages debug commands and output during testing."""
    
    def __init__(self, player):
        """Initialize debug manager with player reference.
        
        Args:
            player: Player object with game_config
        """
        self.player = player
        self.debug_command_history = []
        self.max_history = 50
        self.registered_commands: Dict[str, Callable] = {}
        self._register_default_commands()
    
    def is_debug_mode_enabled(self) -> bool:
        """Check if debug mode is enabled.
        
        Returns:
            True if debug mode enabled, False otherwise
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.debug_mode
        return False
    
    def should_debug_positions(self) -> bool:
        """Check if position debugging is enabled.
        
        Returns:
            True if position debug enabled
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.debug_positions
        return False
    
    def should_debug_movement(self) -> bool:
        """Check if movement debugging is enabled.
        
        Returns:
            True if movement debug enabled
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.debug_movement
        return False
    
    def should_debug_damage_calc(self) -> bool:
        """Check if damage calculation debugging is enabled.
        
        Returns:
            True if damage calc debug enabled
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.debug_damage_calc
        return False
    
    def should_debug_accuracy(self) -> bool:
        """Check if accuracy debugging is enabled.
        
        Returns:
            True if accuracy debug enabled
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.debug_accuracy
        return False
    
    def should_debug_ai_decisions(self) -> bool:
        """Check if AI decision debugging is enabled.
        
        Returns:
            True if AI decision debug enabled
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.debug_ai_decisions
        return False
    
    def should_debug_npc_positions(self) -> bool:
        """Check if NPC position debugging is enabled.
        
        Returns:
            True if NPC position debug enabled
        """
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.debug_npc_positions
        return False
    
    def log_command(self, command_name: str, args: List[str] = None, result: str = "") -> None:
        """Log a debug command execution.
        
        Args:
            command_name: Name of command executed
            args: Optional arguments list
            result: Optional result message
        """
        if len(self.debug_command_history) >= self.max_history:
            self.debug_command_history.pop(0)
        
        entry = {
            'command': command_name,
            'args': args or [],
            'result': result
        }
        self.debug_command_history.append(entry)
    
    def get_command_history(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent command history.
        
        Args:
            count: Number of recent commands to return
            
        Returns:
            List of command history entries
        """
        return self.debug_command_history[-count:]
    
    def _register_default_commands(self) -> None:
        """Register default debug commands."""
        self.registered_commands = {
            'instant_win': self.cmd_instant_win,
            'spawn_enemy': self.cmd_spawn_enemy,
            'damage_output': self.cmd_damage_output,
            'accuracy_info': self.cmd_accuracy_info,
            'npc_decision_trace': self.cmd_npc_decision_trace,
            'performance_monitor': self.cmd_performance_monitor,
            'toggle_feature': self.cmd_toggle_feature,
            'spawn_item': self.cmd_spawn_item,
            'list_stats': self.cmd_list_stats,
        }
    
    def cmd_instant_win(self) -> str:
        """Debug command: Grant instant victory in current combat.
        
        Returns:
            Status message
        """
        if not self.is_debug_mode_enabled():
            return "Debug mode disabled"
        
        # Would mark combat as won
        self.log_command('instant_win', result="Combat marked for instant victory")
        return "Combat: Set for instant victory on next beat"
    
    def cmd_spawn_enemy(self, enemy_name: str = "", count: int = 1) -> str:
        """Debug command: Spawn additional enemy in combat.
        
        Args:
            enemy_name: Name of enemy type to spawn
            count: Number to spawn
            
        Returns:
            Status message
        """
        if not self.is_debug_mode_enabled():
            return "Debug mode disabled"
        
        self.log_command('spawn_enemy', args=[enemy_name, str(count)], result=f"Spawned {count} {enemy_name}")
        return f"Spawned {count} x {enemy_name} in current combat"
    
    def cmd_damage_output(self, attacker_name: str = "", target_name: str = "") -> str:
        """Debug command: Display damage calculation details.
        
        Args:
            attacker_name: Name of attacker
            target_name: Name of target
            
        Returns:
            Detailed damage calculation info
        """
        if not self.is_debug_mode_enabled() or not self.should_debug_damage_calc():
            return "Damage debug disabled"
        
        info = (
            f"Damage Calculation Debug:\n"
            f"  Attacker: {attacker_name}\n"
            f"  Target: {target_name}\n"
            f"  (Detailed calculations would be shown here)"
        )
        self.log_command('damage_output', args=[attacker_name, target_name])
        return info
    
    def cmd_accuracy_info(self, attacker_name: str = "", target_name: str = "") -> str:
        """Debug command: Display accuracy calculation details.
        
        Args:
            attacker_name: Name of attacker
            target_name: Name of target
            
        Returns:
            Detailed accuracy info
        """
        if not self.is_debug_mode_enabled() or not self.should_debug_accuracy():
            return "Accuracy debug disabled"
        
        info = (
            f"Accuracy Calculation Debug:\n"
            f"  Attacker: {attacker_name}\n"
            f"  Target: {target_name}\n"
            f"  (Accuracy modifiers would be shown here)"
        )
        self.log_command('accuracy_info', args=[attacker_name, target_name])
        return info
    
    def cmd_npc_decision_trace(self, npc_name: str = "") -> str:
        """Debug command: Trace NPC's last few decisions with reasoning.
        
        Args:
            npc_name: Name of NPC to trace
            
        Returns:
            NPC decision trace info
        """
        if not self.is_debug_mode_enabled() or not self.should_debug_ai_decisions():
            return "AI decision debug disabled"
        
        info = (
            f"NPC Decision Trace: {npc_name}\n"
            f"  Last Move: (would be shown)\n"
            f"  Reasoning: (would be shown)\n"
            f"  Available Moves: (would be listed)"
        )
        self.log_command('npc_decision_trace', args=[npc_name])
        return info
    
    def cmd_performance_monitor(self) -> str:
        """Debug command: Display performance metrics.
        
        Returns:
            Performance metrics
        """
        if not self.is_debug_mode_enabled():
            return "Debug mode disabled"
        
        info = (
            f"Performance Monitor:\n"
            f"  Frame Time: (would be shown) ms\n"
            f"  Combat Rounds: (would be shown)\n"
            f"  Memory Usage: (would be shown) MB"
        )
        self.log_command('performance_monitor', result="Performance data retrieved")
        return info
    
    def cmd_toggle_feature(self, feature_name: str) -> str:
        """Debug command: Toggle a debug feature on/off.
        
        Args:
            feature_name: Name of feature to toggle
            
        Returns:
            Status message
        """
        if not self.is_debug_mode_enabled():
            return "Debug mode disabled"
        
        features = [
            'debug_positions', 'debug_movement', 'debug_damage_calc',
            'debug_accuracy', 'debug_ai_decisions', 'debug_npc_positions'
        ]
        
        if feature_name not in features:
            return f"Unknown feature: {feature_name}"
        
        # Would toggle the feature in config
        self.log_command('toggle_feature', args=[feature_name])
        return f"Toggled feature: {feature_name}"
    
    def cmd_spawn_item(self, item_name: str = "", quantity: int = 1) -> str:
        """Debug command: Spawn item in player inventory.
        
        Args:
            item_name: Name of item to spawn
            quantity: Quantity to spawn
            
        Returns:
            Status message
        """
        if not self.is_debug_mode_enabled():
            return "Debug mode disabled"
        
        self.log_command('spawn_item', args=[item_name, str(quantity)])
        return f"Spawned {quantity} x {item_name} in inventory"
    
    def cmd_list_stats(self, target_name: str = "") -> str:
        """Debug command: Display all stats for player or NPC.
        
        Args:
            target_name: Name of target (player if empty)
            
        Returns:
            Formatted stats display
        """
        if not self.is_debug_mode_enabled():
            return "Debug mode disabled"
        
        target = target_name if target_name else "Player"
        info = (
            f"Stats for {target}:\n"
            f"  HP: (would be shown)\n"
            f"  Damage: (would be shown)\n"
            f"  Speed: (would be shown)\n"
            f"  Finesse: (would be shown)\n"
            f"  Protection: (would be shown)\n"
            f"  Awareness: (would be shown)"
        )
        self.log_command('list_stats', args=[target_name])
        return info
    
    def execute_command(self, command_name: str, args: List[str] = None) -> str:
        """Execute a registered debug command.
        
        Args:
            command_name: Name of command to execute
            args: List of arguments for command
            
        Returns:
            Command output
        """
        if not self.is_debug_mode_enabled():
            return "Debug mode is disabled"
        
        if command_name not in self.registered_commands:
            return f"Unknown command: {command_name}"
        
        command_func = self.registered_commands[command_name]
        
        # Call with args if provided
        if args:
            try:
                result = command_func(*args)
            except TypeError:
                result = command_func()
        else:
            result = command_func()
        
        return result
    
    def get_available_commands(self) -> List[str]:
        """Get list of available debug commands.
        
        Returns:
            List of command names
        """
        return list(self.registered_commands.keys())
    
    def get_debug_info_string(self) -> str:
        """Get human-readable summary of debug settings.
        
        Returns:
            Formatted debug settings
        """
        debug_enabled = self.is_debug_mode_enabled()
        pos_debug = self.should_debug_positions()
        move_debug = self.should_debug_movement()
        dmg_debug = self.should_debug_damage_calc()
        acc_debug = self.should_debug_accuracy()
        ai_debug = self.should_debug_ai_decisions()
        npc_pos_debug = self.should_debug_npc_positions()
        
        info = (
            f"Debug Manager Status:\n"
            f"  Overall Debug Mode: {debug_enabled}\n"
            f"  Debug Positions: {pos_debug}\n"
            f"  Debug Movement: {move_debug}\n"
            f"  Debug Damage Calc: {dmg_debug}\n"
            f"  Debug Accuracy: {acc_debug}\n"
            f"  Debug AI Decisions: {ai_debug}\n"
            f"  Debug NPC Positions: {npc_pos_debug}\n"
            f"  Available Commands: {len(self.registered_commands)}"
        )
        return info


class DebugValidator:
    """Validates debug commands and parameters."""
    
    def __init__(self, debug_manager: DebugManager):
        """Initialize with debug manager.
        
        Args:
            debug_manager: DebugManager instance
        """
        self.debug_manager = debug_manager
    
    def is_valid_command(self, command_name: str) -> Tuple[bool, str]:
        """Validate if command exists.
        
        Args:
            command_name: Command to validate
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        if not self.debug_manager.is_debug_mode_enabled():
            return (False, "Debug mode is disabled")
        
        if command_name not in self.debug_manager.get_available_commands():
            return (False, f"Unknown command: {command_name}")
        
        return (True, f"Valid command: {command_name}")
    
    def is_valid_spawn_count(self, count: int) -> Tuple[bool, str]:
        """Validate spawn count parameter.
        
        Args:
            count: Count to validate
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        if count <= 0:
            return (False, f"Count must be positive: {count}")
        
        if count > 100:
            return (False, f"Count too high: {count} > 100")
        
        return (True, f"Valid spawn count: {count}")
    
    def is_valid_feature_name(self, feature_name: str) -> Tuple[bool, str]:
        """Validate debug feature name.
        
        Args:
            feature_name: Feature to validate
            
        Returns:
            Tuple of (is_valid, reason_string)
        """
        valid_features = [
            'debug_positions', 'debug_movement', 'debug_damage_calc',
            'debug_accuracy', 'debug_ai_decisions', 'debug_npc_positions'
        ]
        
        if feature_name not in valid_features:
            return (False, f"Unknown feature: {feature_name}")
        
        return (True, f"Valid feature: {feature_name}")
    
    def validate_all_commands(self) -> Tuple[bool, List[str]]:
        """Validate all registered commands are callable.
        
        Returns:
            Tuple of (all_valid, list_of_issues)
        """
        issues = []
        
        for cmd_name, cmd_func in self.debug_manager.registered_commands.items():
            if not callable(cmd_func):
                issues.append(f"Command {cmd_name} is not callable")
        
        return (len(issues) == 0, issues)
