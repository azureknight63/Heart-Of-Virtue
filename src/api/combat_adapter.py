"""
API Combat Adapter

This module adapts the existing terminal-based combat system for API use.
It captures output, manages state between API calls, and processes commands
without blocking for user input.
"""

import io
import sys
import contextlib
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from unittest.mock import patch
import random

if TYPE_CHECKING:
    from player import Player

from src.api.serializers.combat import CombatStateSerializer


class CombatOutputCapture:
    """Captures print statements and stores them in a combat log."""
    
    def __init__(self):
        self.log_entries = []
        self.current_round = 1
        
    def write(self, text):
        """Capture text output."""
        if text and text.strip():
            # Clean ANSI codes
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\_-]|\[[0-?]*[ -/]*[@-~])')
            clean_text = ansi_escape.sub('', text).strip()
            
            if clean_text:
                self.log_entries.append({
                    "round": self.current_round,
                    "message": clean_text,
                    "type": "combat"
                })
    
    def flush(self):
        """Required for file-like object."""
        pass
    
    def get_log(self):
        """Get all captured log entries."""
        return self.log_entries
    
    def clear(self):
        """Clear the log."""
        self.log_entries = []


class ApiCombatAdapter:
    """
    Adapts the terminal combat system for API use.
    
    This class manages combat state between API calls and processes
    player commands without blocking for input.
    """
    
    def __init__(self, player: "Player"):
        self.player = player
        self.output_capture = CombatOutputCapture()
        self.awaiting_input = False
        self.input_type = None  # 'move_selection', 'target_selection', 'direction_selection'
        self.pending_move = None
        self.available_options = []
        
    def initialize_combat(self, enemies: List[Any]) -> Dict[str, Any]:
        """
        Initialize combat with the given enemies.
        
        Args:
            enemies: List of enemy NPCs
            
        Returns:
            Initial combat state
        """
        try:
            # Import here to avoid circular dependencies
            if not hasattr(self.player, "combat_beat"):
                self.player.combat_beat = 0
            if not hasattr(self.player, "combat_log"):
                self.player.combat_log = []
            
            # Initialize combat_proximity if it doesn't exist
            if not hasattr(self.player, "combat_proximity"):
                self.player.combat_proximity = {}
            
            self.player.heat = 1.0
            
            # Initialize positions
            scenario_type = "standard"
            if len(self.player.combat_list) > 1 and len(self.player.combat_list_allies) < len(self.player.combat_list):
                scenario_type = "pincer"
            elif len(self.player.combat_list_allies) == 1 and len(self.player.combat_list) == 1:
                scenario_type = "boss_arena"
            
            try:
                positions.initialize_combat_positions(
                    allies=self.player.combat_list_allies,
                    enemies=self.player.combat_list,
                    scenario_type=scenario_type
                )
            except Exception as e:
                print(f"Warning: Position initialization failed: {e}")
                # Fallback to old proximity system
                for ally in self.player.combat_list_allies:
                    if not hasattr(ally, "combat_proximity"):
                        ally.combat_proximity = {}
                    for enemy in self.player.combat_list:
                        if not hasattr(enemy, "combat_proximity"):
                            enemy.combat_proximity = {}
                        if not hasattr(enemy, "default_proximity"):
                            enemy.default_proximity = 50  # Default distance
                        if enemy not in ally.combat_proximity:
                            distance = int(enemy.default_proximity * random.uniform(0.75, 1.25))
                            ally.combat_proximity[enemy] = distance
                            enemy.combat_proximity[ally] = distance
            
            # Reset moves
            for ally in self.player.combat_list_allies:
                ally.in_combat = True
                for move in ally.known_moves:
                    move.current_stage = 0
                    move.beats_left = 0
            
            for enemy in self.player.combat_list:
                for move in enemy.known_moves:
                    move.current_stage = 0
                    move.beats_left = 0
            
            # Add initial log entry
            enemy_names = ", ".join([getattr(e, "name", "Enemy") for e in enemies])
            self.player.combat_log.append({
                "round": 1,
                "message": f"Combat started! {enemy_names} appear{'s' if len(enemies) == 1 else ''}!",
                "type": "system"
            })
            
            # Check if enemies go first
            self._process_initial_turns()
            
            # Set up for player's first move selection
            self.awaiting_input = True
            self.input_type = "move_selection"
            self.available_options = self._get_available_moves()
            
            return self.get_combat_state()
        
        except Exception as e:
            import traceback
            error_msg = f"Combat initialization error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return {
                "error": "Failed to initialize combat",
                "details": str(e),
                "combat_active": False
            }
    
    def process_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a command from the frontend.
        
        Args:
            command: Dictionary with command type and parameters
                Examples:
                - {"type": "select_move", "move_index": 2}
                - {"type": "select_target", "target_id": "enemy_0"}
                - {"type": "select_direction", "direction": "north"}
        
        Returns:
            Updated combat state
        """
        if not self.awaiting_input:
            return {"error": "Not awaiting input"}
        
        command_type = command.get("type")
        
        if command_type == "select_move":
            return self._handle_move_selection(command.get("move_index"))
        elif command_type == "select_target":
            return self._handle_target_selection(command.get("target_id"))
        elif command_type == "select_direction":
            return self._handle_direction_selection(command.get("direction"))
        else:
            return {"error": f"Unknown command type: {command_type}"}
    
    def _handle_move_selection(self, move_index: int) -> Dict[str, Any]:
        """Handle player selecting a move."""
        if self.input_type != "move_selection":
            return {"error": "Not expecting move selection"}
        
        viable_moves = self.player.refresh_moves()
        
        if move_index < 0 or move_index >= len(viable_moves):
            return {"error": "Invalid move index"}
        
        selected_move = viable_moves[move_index]
        
        # Check if move is available
        if self.player.fatigue < selected_move.fatigue_cost:
            return {"error": "Not enough fatigue"}
        
        if selected_move.current_stage != 0:
            return {"error": "Move not ready yet"}
        
        self.player.current_move = selected_move
        self.player.current_move.user = self.player
        
        # Log move selection
        self.player.combat_log.append({
            "round": self.output_capture.current_round,
            "message": f"Jean uses {selected_move.name}!",
            "type": "player_action"
        })
        
        # Check if move needs targeting
        if selected_move.targeted:
            self.input_type = "target_selection"
            self.available_options = self._get_available_targets(selected_move)
            self.pending_move = selected_move
            return self.get_combat_state()
        
        # Check if move needs direction (Turn move)
        if selected_move.name == "Turn":
            self.input_type = "direction_selection"
            self.available_options = ["north", "south", "east", "west"]
            self.pending_move = selected_move
            return self.get_combat_state()
        
        # Non-targeted move - execute immediately
        selected_move.target = self.player
        return self._execute_move(selected_move)
    
    def _handle_target_selection(self, target_id: str) -> Dict[str, Any]:
        """Handle player selecting a target."""
        if self.input_type != "target_selection":
            return {"error": "Not expecting target selection"}
        
        # Find target in available options
        target = None
        for option in self.available_options:
            if option.get("id") == target_id:
                target = option.get("enemy")
                break
        
        if not target:
            return {"error": "Invalid target"}
        
        self.pending_move.target = target
        return self._execute_move(self.pending_move)
    
    def _handle_direction_selection(self, direction: str) -> Dict[str, Any]:
        """Handle player selecting a direction."""
        if self.input_type != "direction_selection":
            return {"error": "Not expecting direction selection"}
        
        if direction not in self.available_options:
            return {"error": "Invalid direction"}
        
        # Set direction on the move
        if hasattr(self.pending_move, 'target_direction'):
            self.pending_move.target_direction = direction
        
        return self._execute_move(self.pending_move)
    
    def _execute_move(self, move) -> Dict[str, Any]:
        """Execute a move and process the combat beat."""
        # Capture output during move execution
        with self._capture_output():
            # Cast the move
            move.cast()
            
            # Process instant moves
            if hasattr(move, 'instant') and move.instant:
                while move.instant:
                    move.advance(self.player)
                    if self.player.current_move is None:
                        break
            
            # Advance all player moves
            for m in self.player.known_moves:
                m.advance(self.player)
            
            # Process NPC turns
            self._process_npc_turns()
            
            # Cycle states
            self.player.cycle_states()
            
            # Update heat
            self._update_heat()
            
            # Increment beat
            self.player.combat_beat += 1
        
        # Check win/loss conditions
        if not self.player.is_alive():
            self.player.in_combat = False
            self.player.combat_log.append({
                "round": self.output_capture.current_round,
                "message": "You have been defeated!",
                "type": "system"
            })
            return self.get_combat_state()
        
        if len(self.player.combat_list) == 0:
            self._handle_victory()
            return self.get_combat_state()
        
        # Set up for next move selection
        self.awaiting_input = True
        self.input_type = "move_selection"
        self.available_options = self._get_available_moves()
        self.pending_move = None
        
        return self.get_combat_state()
    
    def _process_initial_turns(self):
        """Process NPC turns if they go first."""
        # Simple speed check - if any enemy is faster, they go first
        player_speed = getattr(self.player, "speed", 10)
        
        for enemy in self.player.combat_list:
            enemy_speed = getattr(enemy, "speed", 5)
            if enemy_speed > player_speed:
                with self._capture_output():
                    self._process_npc_turns()
                break
    
    def _process_npc_turns(self):
        """Process all NPC turns (allies and enemies)."""
        from src.functions import refresh_stat_bonuses
        
        # Refresh stats
        for friendly in self.player.combat_list_allies:
            refresh_stat_bonuses(friendly)
        for enemy in self.player.combat_list:
            refresh_stat_bonuses(enemy)
        
        # Process friendly NPCs
        for ally in self.player.combat_list_allies:
            if ally != self.player and ally.is_alive():
                self._process_npc(ally)
        
        # Process enemies
        for enemy in self.player.combat_list[:]:  # Copy list as it may be modified
            if enemy.is_alive():
                self._process_npc(enemy)
                # Check if enemy died
                if not enemy.is_alive():
                    enemy.die()
                    if not enemy.is_alive():
                        self.player.current_room.npcs_here.remove(enemy)
                        self.player.combat_list.remove(enemy)
                        for ally in self.player.combat_list_allies:
                            if enemy in ally.combat_proximity:
                                del ally.combat_proximity[enemy]
    
    def _process_npc(self, npc):
        """Process a single NPC's turn."""
        npc.cycle_states()
        
        # Initialize combat_delay if it doesn't exist
        if not hasattr(npc, "combat_delay"):
            npc.combat_delay = 0
        
        if npc.combat_delay > 0:
            npc.combat_delay -= 1
        else:
            if npc.current_move is None:
                # Select target
                if not npc.friend:
                    npc.target = random.choice(self.player.combat_list_allies)
                else:
                    npc.target = random.choice(self.player.combat_list)
                
                # Select and cast move
                npc.select_move()
                if npc.current_move:
                    npc.current_move.target = npc.target
                    if hasattr(npc.current_move, "cast") and callable(npc.current_move.cast):
                        npc.current_move.cast()
        
        # Advance moves
        for move in npc.known_moves:
            move.advance(npc)
    
    def _update_heat(self):
        """Update the heat multiplier."""
        if self.player.heat < 1:
            amt = (1 - self.player.heat) / 20
            if amt < 0.001:
                amt = 0.001
            self.player.heat += amt
        elif self.player.heat > 1:
            amt = (self.player.heat - 1) / 20
            if amt < 0.001:
                amt = 0.001
            self.player.heat -= amt
    
    def _handle_victory(self):
        """Handle combat victory."""
        self.player.in_combat = False
        self.player.fatigue = self.player.maxfatigue
        
        # Calculate exp
        exp_summary = []
        for subtype, value in self.player.combat_exp.items():
            if value > 0:
                exp_summary.append(f"{subtype}: {int(value)}")
                self.player.gain_exp(int(value), exp_type=subtype)
                self.player.combat_exp[subtype] = 0
        
        victory_msg = "Victory! "
        if exp_summary:
            victory_msg += "Gained exp: " + ", ".join(exp_summary)
        
        self.player.combat_log.append({
            "round": self.output_capture.current_round,
            "message": victory_msg,
            "type": "system"
        })
    
    def _get_available_moves(self) -> List[Dict[str, Any]]:
        """Get list of available moves for the player."""
        viable_moves = self.player.refresh_moves()
        moves = []
        
        for i, move in enumerate(viable_moves):
            move_data = {
                "index": i,
                "name": move.name,
                "fatigue_cost": move.fatigue_cost,
                "available": True,
                "reason": None
            }
            
            if move.current_stage == 3:
                if move.beats_left > 0:
                    move_data["available"] = False
                    move_data["reason"] = f"Available in {move.beats_left + 1} beats"
                else:
                    move_data["available"] = False
                    move_data["reason"] = "Available next beat"
            elif self.player.fatigue < move.fatigue_cost:
                move_data["available"] = False
                move_data["reason"] = "Not enough fatigue"
            
            moves.append(move_data)
        
        return moves
    
    def _get_available_targets(self, move) -> List[Dict[str, Any]]:
        """Get list of available targets for a move."""
        targets = []
        range_min, range_max = move.mvrange
        
        # Special handling for bow
        if move.name == "Shoot Bow":
            range_max = self.player.eq_weapon.range_base + (100 / self.player.eq_weapon.range_decay)
        
        for enemy, distance in self.player.combat_proximity.items():
            if enemy.is_alive() and range_min <= distance <= range_max:
                target_data = {
                    "id": f"enemy_{id(enemy)}",
                    "name": enemy.name,
                    "distance": distance,
                    "enemy": enemy  # Store reference for later use
                }
                
                # Add hit chance if verbose targeting
                if move.verbose_targeting and hasattr(move, 'calculate_hit_chance'):
                    target_data["hit_chance"] = move.calculate_hit_chance(enemy)
                
                targets.append(target_data)
        
        # Sort by distance
        targets.sort(key=lambda t: t["distance"])
        return targets
    
    def _capture_output(self):
        """Context manager to capture print output."""
        return contextlib.redirect_stdout(self.output_capture)
    
    def get_combat_state(self) -> Dict[str, Any]:
        """
        Get the current combat state for the frontend.
        
        Returns:
            Dictionary with complete combat state
        """
        # Serialize combat state
        battle_state = CombatStateSerializer.serialize_combat_state(
            self.player,
            self.player.combat_list,
            current_turn_index=0,  # Not used in API version
            round_number=self.output_capture.current_round
        )
        
        # Add API-specific fields
        battle_state["beat"] = getattr(self.player, "combat_beat", 0)
        battle_state["heat"] = int(self.player.heat * 100)
        battle_state["awaiting_input"] = self.awaiting_input
        battle_state["input_type"] = self.input_type
        battle_state["available_options"] = self.available_options
        
        return {
            "combat_active": self.player.in_combat,
            "battle_state": battle_state,
            "log": self.player.combat_log
        }
