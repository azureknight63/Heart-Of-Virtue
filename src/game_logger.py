"""Centralized logging system for combat and game events (Phase 2.2).

Provides structured logging for combat moves, distance calculations, angle calculations,
NPC decisions, and performance monitoring. Respects config flags from game_config.
"""

import os
import sys
from datetime import datetime
from pathlib import Path


class GameLogger:
    """Centralized logger for game events."""
    
    def __init__(self, player, log_file: str = None):
        """Initialize logger with player reference for accessing config.
        
        Args:
            player: Player object with game_config
            log_file: Override log file path (defaults to config or combat_testing_phase4.log)
        """
        self.player = player
        self.log_file = log_file
        self.session_start_time = datetime.now()
        self._ensure_log_file_ready()
    
    def _get_log_file_path(self) -> str:
        """Get the log file path, respecting config settings.
        
        Returns:
            Full path to log file
        """
        if self.log_file:
            return self.log_file
        
        # Try to get from config
        if hasattr(self.player, 'game_config') and self.player.game_config:
            config_file = self.player.game_config.log_file
            if config_file:
                return config_file
        
        # Default
        return "combat_testing_phase4.log"
    
    def _ensure_log_file_ready(self) -> None:
        """Ensure log file exists and is writable."""
        log_path = Path(self._get_log_file_path())
        try:
            # Try to create/open log file
            with open(log_path, 'a') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"Session started: {self.session_start_time.isoformat()}\n")
                f.write(f"{'='*80}\n")
        except Exception as e:
            print(f"[Warning] Could not open log file {log_path}: {e}", file=sys.stderr)
    
    def _should_log_combat_moves(self) -> bool:
        """Check if combat moves should be logged."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.log_combat_moves
        return True
    
    def _should_log_distance_calculations(self) -> bool:
        """Check if distance calculations should be logged."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.log_distance_calculations
        return True
    
    def _should_log_angle_calculations(self) -> bool:
        """Check if angle calculations should be logged."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.log_angle_calculations
        return True
    
    def _should_log_npc_decisions(self) -> bool:
        """Check if NPC decisions should be logged."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.log_npc_decisions
        return True
    
    def _should_monitor_bps(self) -> bool:
        """Check if bytes per second should be monitored."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.monitor_bps
        return False
    
    def _should_log_performance(self) -> bool:
        """Check if performance metrics should be logged."""
        if hasattr(self.player, 'game_config') and self.player.game_config:
            return self.player.game_config.log_performance
        return False
    
    def _format_timestamp(self) -> str:
        """Get formatted timestamp for log entries.
        
        Returns:
            Timestamp string
        """
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    def _write_log(self, message: str) -> None:
        """Write message to log file.
        
        Args:
            message: Message to log
        """
        try:
            with open(self._get_log_file_path(), 'a') as f:
                f.write(f"[{self._format_timestamp()}] {message}\n")
        except Exception as e:
            print(f"[Warning] Could not write to log file: {e}", file=sys.stderr)
    
    def log_combat_move(self, actor: str, move_name: str, target: str = None, details: str = None) -> None:
        """Log a combat move.
        
        Args:
            actor: Name of unit performing the move
            move_name: Name of the move
            target: Optional target name
            details: Optional additional details
        """
        if not self._should_log_combat_moves():
            return
        
        message = f"MOVE: {actor} uses {move_name}"
        if target:
            message += f" on {target}"
        if details:
            message += f" ({details})"
        
        self._write_log(message)
    
    def log_distance_calculation(self, unit1: str, unit2: str, distance: float, details: str = None) -> None:
        """Log a distance calculation.
        
        Args:
            unit1: Name of first unit
            unit2: Name of second unit
            distance: Calculated distance
            details: Optional calculation details
        """
        if not self._should_log_distance_calculations():
            return
        
        message = f"DISTANCE: {unit1} to {unit2} = {distance:.2f} ft"
        if details:
            message += f" ({details})"
        
        self._write_log(message)
    
    def log_angle_calculation(self, observer: str, target: str, angle: float, quadrant: str = None) -> None:
        """Log an angle calculation.
        
        Args:
            observer: Name of observing unit
            target: Name of target unit
            angle: Calculated angle (0-360)
            quadrant: Optional quadrant description (N, NE, E, SE, etc.)
        """
        if not self._should_log_angle_calculations():
            return
        
        message = f"ANGLE: {observer} to {target} = {angle:.1f}°"
        if quadrant:
            message += f" ({quadrant})"
        
        self._write_log(message)
    
    def log_npc_decision(self, npc_name: str, decision: str, reasoning: str = None, confidence: float = None) -> None:
        """Log an NPC AI decision.
        
        Args:
            npc_name: Name of the NPC
            decision: Decision made (e.g., "Attack", "Retreat", "Flank")
            reasoning: Optional reasoning
            confidence: Optional confidence level (0.0-1.0)
        """
        if not self._should_log_npc_decisions():
            return
        
        message = f"NPC: {npc_name} decides: {decision}"
        if reasoning:
            message += f" (reason: {reasoning})"
        if confidence is not None:
            message += f" [confidence: {confidence:.2%}]"
        
        self._write_log(message)
    
    def log_performance_metric(self, metric_name: str, value: float, unit: str = None) -> None:
        """Log a performance metric.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Optional unit (e.g., "ms", "fps", "bytes")
        """
        if not self._should_log_performance():
            return
        
        message = f"PERF: {metric_name} = {value:.2f}"
        if unit:
            message += f" {unit}"
        
        self._write_log(message)
    
    def log_bytes_per_second(self, bps: float, context: str = None) -> None:
        """Log bytes per second (BPS) metric.
        
        Args:
            bps: Bytes per second value
            context: Optional context (e.g., "network", "disk")
        """
        if not self._should_monitor_bps():
            return
        
        message = f"BPS: {bps:.2f} bytes/sec"
        if context:
            message += f" ({context})"
        
        self._write_log(message)
    
    def log_combat_event(self, event_name: str, participants: list = None, outcome: str = None) -> None:
        """Log a significant combat event.
        
        Args:
            event_name: Name of the event (e.g., "Combat Started", "Unit Defeated")
            participants: List of participant names
            outcome: Optional outcome description
        """
        message = f"EVENT: {event_name}"
        
        if participants:
            message += f" [{', '.join(participants)}]"
        if outcome:
            message += f" -> {outcome}"
        
        self._write_log(message)
    
    def log_session_end(self, victory: bool, duration_seconds: float = None) -> None:
        """Log end of combat session.
        
        Args:
            victory: True if player won, False if lost
            duration_seconds: Optional duration in seconds
        """
        outcome = "VICTORY" if victory else "DEFEAT"
        message = f"SESSION_END: {outcome}"
        
        if duration_seconds is not None:
            message += f" (duration: {duration_seconds:.1f}s)"
        
        self._write_log(message)
    
    def get_session_log_summary(self) -> str:
        """Get a summary of the current session log.
        
        Returns:
            Summary string
        """
        log_path = Path(self._get_log_file_path())
        
        if not log_path.exists():
            return "No log file found"
        
        try:
            with open(log_path, 'r') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            session_lines = [l for l in lines if 'Session started' in l or 'SESSION_END' in l]
            move_lines = [l for l in lines if 'MOVE:' in l]
            decision_lines = [l for l in lines if 'NPC:' in l]
            
            summary = f"Log Summary:\n"
            summary += f"  Total entries: {total_lines}\n"
            summary += f"  Moves logged: {len(move_lines)}\n"
            summary += f"  NPC decisions logged: {len(decision_lines)}\n"
            summary += f"  Sessions: {len(session_lines) // 2}\n"
            
            return summary
        
        except Exception as e:
            return f"Could not read log: {e}"
