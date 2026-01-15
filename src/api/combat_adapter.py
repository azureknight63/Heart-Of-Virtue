"""
API Combat Adapter

This module adapts the existing terminal-based combat system for API use.
It captures output, manages state between API calls, and processes commands
without blocking for user input.
"""

import io
import sys
import contextlib
import uuid
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from unittest.mock import patch
import random

if TYPE_CHECKING:
    from player import Player

import positions  # type: ignore
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
    
    def __init__(self, player: "Player", session_id: str = None):
        self.player = player
        self.session_id = session_id
        self.output_capture = CombatOutputCapture()
        self.current_beat_state_index = 0  # Track which beat state we're currently building
        
        # Initialize persistent state if missing
        if not hasattr(self.player, "combat_adapter_state"):
            self.player.combat_adapter_state = {
                "awaiting_input": False,
                "input_type": None,
                "pending_move_index": None,
                "available_options": []
            }
            
    @property
    def awaiting_input(self):
        return self.player.combat_adapter_state.get("awaiting_input", False)
    
    @awaiting_input.setter
    def awaiting_input(self, value):
        self.player.combat_adapter_state["awaiting_input"] = value

    @property
    def input_type(self):
        return self.player.combat_adapter_state.get("input_type", None)
    
    @input_type.setter
    def input_type(self, value):
        self.player.combat_adapter_state["input_type"] = value

    @property
    def pending_move_index(self):
        return self.player.combat_adapter_state.get("pending_move_index", None)
    
    @pending_move_index.setter
    def pending_move_index(self, value):
        self.player.combat_adapter_state["pending_move_index"] = value

    @property
    def available_options(self):
        return self.player.combat_adapter_state.get("available_options", [])
    
    @available_options.setter
    def available_options(self, value):
        self.player.combat_adapter_state["available_options"] = value

    def _add_log_entry(self, round_num: int, message: str, entry_type: str = "combat", beat_index: int = 0):
        """Add a log entry with deduplication check.
        
        Args:
            round_num: Combat round number
            message: Log message text
            entry_type: Type of log entry (combat, system, etc.)
            beat_index: Index of the beat state this log entry corresponds to (for map sync)
        """
        if not hasattr(self.player, 'combat_log'):
            self.player.combat_log = []
        
        # Check for duplicate
        # We check both message and round to allow the same event in different rounds
        is_duplicate = any(
            existing.get("message") == message and existing.get("round") == round_num
            for existing in self.player.combat_log
        )
        if not is_duplicate:
            entry = {
                "round": round_num,
                "message": message,
                "type": entry_type,
                "beat_index": beat_index  # For syncing with beat_states array
            }
            self.player.combat_log.append(entry)
            
            # Emit socket event if session is known
            if self.session_id:
                try:
                    from flask import current_app
                    if hasattr(current_app, 'socketio'):
                        room = f"combat_{self.session_id}"
                        current_app.socketio.emit('combat:log', entry, room=room)
                except Exception as e:
                    print(f"[SOCKET ERROR] Failed to emit log: {e}")

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
            # Reset combat state for new combat
            self.player.combat_beat = 1  # Start at beat 1 for synchronization
            self.player.combat_log = []  # Clear log for new combat
            # Clear any prior end-of-combat summary/drops from previous encounters
            self.player.combat_end_summary = None
            self.player.combat_drops = []
            self.output_capture.clear()  # Clear captured output
            self.current_beat_state_index = 0  # Reset beat state tracking
            
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
                from src.coordinate_config import CoordinateSystemConfig
                coord_config = CoordinateSystemConfig(self.player)
                total_combatants = len(self.player.combat_list_allies) + len(self.player.combat_list)
                grid_w, grid_h = coord_config.get_dynamic_grid_size(total_combatants)
                
                positions.initialize_combat_positions(
                    allies=self.player.combat_list_allies,
                    enemies=self.player.combat_list,
                    scenario_type=scenario_type,
                    grid_width=grid_w,
                    grid_height=grid_h
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
                            enemy.default_proximity = 10  # Default distance - enemies start in striking range
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
                # Provide a back-reference for API-mode drop/loot tracking
                try:
                    enemy.player_ref = self.player
                except Exception:
                    pass
                for move in enemy.known_moves:
                    move.current_stage = 0
                    move.beats_left = 0
            
            # Initialize combat lists for all participants (Enemies and Allies)
            # This ensures collision detection works correctly for everyone
            
            # For Player's Allies:
            # - Their enemies are the Player's enemies
            # - Their allies are the Player's allies
            for ally in self.player.combat_list_allies:
                if ally == self.player:
                    continue
                ally.combat_list = self.player.combat_list
                ally.combat_list_allies = self.player.combat_list_allies
            
            # For Enemies:
            # - Their enemies are the Player's allies (including Player)
            # - Their allies are the Player's enemies (other enemies)
            for enemy in self.player.combat_list:
                enemy.combat_list = self.player.combat_list_allies
                enemy.combat_list_allies = self.player.combat_list
            
            # Add initial log entry for each enemy
            for enemy in enemies:
                name = getattr(enemy, "name", "Enemy")
                alert = getattr(enemy, "alert_message", "appears!")
                self._add_log_entry(1, f"{name} {alert}", "system")

            # Process initial NPC turns (this will capture alert messages and initial actions via print statements)
            self._process_initial_turns()
            
            # Set up for player's first move selection
            self.awaiting_input = True
            self.input_type = "move_selection"
            self.available_options = self._get_available_moves()
            
            result = self.get_combat_state()
            
            # Emit combat started event
            if self.session_id:
                print(f"[DEBUG] Emitting combat:started for session {self.session_id}")
                try:
                    from flask import current_app
                    from src.api.serializers.combat import CombatStateSerializer
                    serialized_state = CombatStateSerializer.serialize(result)
                    if hasattr(current_app, 'socketio'):
                        current_app.socketio.emit(
                            'combat:started', 
                            {'battle_state': serialized_state}, 
                            room=f"combat_{self.session_id}"
                        )
                        print(f"[DEBUG] Successfully emitted combat:started to room combat_{self.session_id}")
                except Exception as e:
                    print(f"[DEBUG] Error emitting combat:started: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[DEBUG] No session_id in ApiCombatAdapter, skipping combat:started emission")
                
            return result
        
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
        print(f"[DEBUG] process_command called: {command}")
        print(f"[DEBUG] awaiting_input={self.awaiting_input}, input_type={self.input_type}")
        
        if not self.awaiting_input:
            return {"error": "Not awaiting input"}
        
        command_type = command.get("type")
        
        if command_type == "select_move":
            return self._handle_move_selection(command.get("move_index"))
        elif command_type == "select_target":
            return self._handle_target_selection(command.get("target_id"))
        elif command_type == "select_direction":
            return self._handle_direction_selection(command.get("direction"))
        elif command_type == "select_number":
            return self._handle_number_selection(command.get("value"))
        elif command_type == "cancel_selection":
            return self._handle_cancel_selection()
        else:
            return {"error": f"Unknown command type: {command_type}"}

    def _handle_cancel_selection(self) -> Dict[str, Any]:
        """
        Handle canceling the current selection (target/direction/number).
        Reverts back to move selection.
        """
        if self.input_type == "move_selection":
            # Can't cancel back further than move selection
            return {"error": "Cannot cancel selection at this stage"}
            
        # Reverting to move selection
        self.pending_move_index = None
        self.input_type = "move_selection"
        self.available_options = self._get_available_moves()
        
        # Log cancellation (optional, but good for debugging)
        print("[DEBUG] Cancelled selection, reverted to move selection")
        
        return self.get_combat_state()
    
    def _handle_move_selection(self, move_index: int) -> Dict[str, Any]:
        """Handle player selecting a move."""
        print(f"[DEBUG] _handle_move_selection: move_index={move_index}, input_type={self.input_type}")
        
        if self.input_type != "move_selection":
            return {"error": "Not expecting move selection"}
        
        # Use all known moves, not just viable ones
        all_moves = self.player.known_moves
        
        if move_index < 0 or move_index >= len(all_moves):
            return {"error": "Invalid move index"}
        
        selected_move = all_moves[move_index]
        
        # Check if move is viable
        if not selected_move.viable():
            return {"error": "Move is not currently available"}
        
        # Check if move is available
        if self.player.fatigue < selected_move.fatigue_cost:
            return {"error": "Not enough fatigue"}
        
        if selected_move.current_stage != 0:
            return {"error": "Move not ready yet"}
        
        self.player.current_move = selected_move
        self.player.current_move.user = self.player
        
        # Log move selection
        # Log move selection
        self._add_log_entry(
            self.output_capture.current_round,
            f"Jean uses {selected_move.name}!",
            "player_action"
        )
        
        # Check if move needs targeting
        if selected_move.targeted:
            self.input_type = "target_selection"
            self.available_options = self._get_available_targets(selected_move)
            self.pending_move_index = move_index
            # Keep awaiting_input True so frontend knows to send target
            return self.get_combat_state()
        
        # Check if move needs duration input (e.g., Wait move)
        if hasattr(selected_move, 'needs_duration') and selected_move.needs_duration:
            self.input_type = "number_input"
            self.available_options = {
                "prompt": "How many beats do you want to wait?",
                "min": 3,
                "max": 10,
                "default": 5
            }
            self.pending_move_index = move_index
            # Keep awaiting_input True so frontend knows to send number
            return self.get_combat_state()
        
        # Check if move needs direction (Turn move)
        if selected_move.name == "Turn":
            self.input_type = "direction_selection"
            self.available_options = ["north", "south", "east", "west"]
            self.pending_move_index = move_index
            # Keep awaiting_input True so frontend knows to send direction
            return self.get_combat_state()
        
        # Non-targeted move - execute immediately
        selected_move.target = self.player
        return self._execute_move(selected_move)
    
    def _handle_target_selection(self, target_id: str) -> Dict[str, Any]:
        """Handle player selecting a target."""
        if self.input_type != "target_selection":
            return {"error": "Not expecting target selection"}
        
        # Reconstruct pending move
        if self.pending_move_index is None:
            return {"error": "No pending move"}
            
        all_moves = self.player.known_moves
        if self.pending_move_index >= len(all_moves):
            return {"error": "Invalid pending move index"}
            
        pending_move = all_moves[self.pending_move_index]
        pending_move.user = self.player
        
        # Find target in available options
        target = None
        # Look up target by ID from player's combat list (enemies) or allies
        # We need to parse the target_id (e.g. "enemy_123456")
        target_obj_id = target_id.replace("enemy_", "")
        
        all_combatants = self.player.combat_list + self.player.combat_list_allies
        for combatant in all_combatants:
            if str(id(combatant)) == target_obj_id:
                target = combatant
                break
        
        if not target:
            return {"error": "Invalid target"}
        
        pending_move.target = target
        
        # Clear pending move index
        self.pending_move_index = None
        
        return self._execute_move(pending_move)
    
    def _handle_direction_selection(self, direction: str) -> Dict[str, Any]:
        """Handle player selecting a direction."""
        if self.input_type != "direction_selection":
            return {"error": "Not expecting direction selection"}
        
        if direction not in self.available_options:
            return {"error": "Invalid direction"}
        
        # Reconstruct pending move
        if self.pending_move_index is None:
            return {"error": "No pending move"}
            
        all_moves = self.player.known_moves
        if self.pending_move_index >= len(all_moves):
            return {"error": "Invalid pending move index"}
            
        pending_move = all_moves[self.pending_move_index]
        pending_move.user = self.player
        
        # Set direction on the move
        if hasattr(pending_move, 'target_direction'):
            # Convert string to Direction enum
            direction_map = {
                "north": positions.Direction.N,
                "south": positions.Direction.S,
                "east": positions.Direction.E,
                "west": positions.Direction.W
            }
            # Fallback to N if mapping fails (though validation above catches it)
            enum_dir = direction_map.get(direction.lower(), positions.Direction.N)
            pending_move.target_direction = enum_dir
            
        # Clear pending move index
        self.pending_move_index = None
        
        return self._execute_move(pending_move)
    
    def _handle_number_selection(self, value: int) -> Dict[str, Any]:
        """Handle player entering a numeric value."""
        if self.input_type != "number_input":
            return {"error": "Not expecting number input"}
        
        # Reconstruct pending move
        if self.pending_move_index is None:
            return {"error": "No pending move"}
            
        all_moves = self.player.known_moves
        if self.pending_move_index >= len(all_moves):
            return {"error": "Invalid pending move index"}
            
        pending_move = all_moves[self.pending_move_index]
        pending_move.user = self.player
        
        # Validate the number is within acceptable range
        if isinstance(self.available_options, dict):
            min_val = self.available_options.get("min", 1)
            max_val = self.available_options.get("max", 100)
            
            if value < min_val or value > max_val:
                return {"error": f"Value must be between {min_val} and {max_val}"}
        
        # Set the duration on the move (for Wait move)
        if hasattr(pending_move, 'duration'):
            pending_move.duration = value
            
        # Clear pending move index
        self.pending_move_index = None
        
        return self._execute_move(pending_move)
    
    def _synchronize_distances(self):
        """
        Synchronize distances between combatants.
        Updates combat_proximity based on combat_position, and handles legacy fallback.
        Mirrors logic from combat.py.
        """
        player = self.player
        
        # Calculate proximity from coordinates for units with combat_position set
        all_combatants = player.combat_list_allies + player.combat_list
        for unit in all_combatants:
            if hasattr(unit, 'combat_position') and unit.combat_position is not None:
                unit.combat_proximity = positions.recalculate_proximity_dict(unit, all_combatants)
        
        # Original proximity synchronization logic for backward compatibility/fallback
        # Logic adapted from combat.py
        for each_ally in player.combat_list_allies:
            remove_these = []
            for each_enemy in each_ally.combat_proximity:
                if not each_enemy.is_alive():
                    remove_these.append(each_enemy)
            for each_enemy in remove_these:
                del each_ally.combat_proximity[each_enemy]
                
            for each_enemy in player.combat_list:
                remove_these = []
                for each_ally_in_prox in each_enemy.combat_proximity:
                    if not each_ally.is_alive():
                        remove_these.append(each_ally_in_prox)
                for each_ally_that_died in remove_these:
                    del each_enemy.combat_proximity[each_ally_that_died]
                    
                if each_enemy in each_ally.combat_proximity:
                    each_enemy.combat_proximity[each_ally] = each_ally.combat_proximity[each_enemy]
                else:
                    # Enemy not in list (legacy/fallback), add with random distance
                    # But ONLY if we don't have positions (which would have handled it above)
                    if not (hasattr(each_enemy, 'combat_position') and each_enemy.combat_position is not None and
                            hasattr(each_ally, 'combat_position') and each_ally.combat_position is not None):
                        
                        default = getattr(each_enemy, 'default_proximity', 20)
                        each_distance = int(default * random.uniform(0.75, 1.25))
                        each_ally.combat_proximity[each_enemy] = each_distance
                        each_enemy.combat_proximity[each_ally] = each_distance

        # Ensure reverse mapping for enemies
        for each_enemy in player.combat_list:
            for each_ally in player.combat_list_allies:
                if each_ally not in each_enemy.combat_proximity:
                    # If missed above, sync
                    if each_enemy in each_ally.combat_proximity:
                        each_enemy.combat_proximity[each_ally] = each_ally.combat_proximity[each_enemy]
    
    def _execute_move(self, move) -> Dict[str, Any]:
        """Execute a move and process the combat beat(s)."""
        print(f"[DEBUG] _execute_move called for move: {move.name}")
        print(f"[DEBUG] _execute_move: player={self.player.name}, eq_weapon={self.player.eq_weapon.name}")
        print(f"[DEBUG] Current beat before execution: {self.player.combat_beat}")
        
        # Reset beat state index for this move execution
        self.current_beat_state_index = 0
        
        is_instant = hasattr(move, 'instant') and move.instant
        beat_states = []
        
        # Cast the move (capture output for initial cast message)
        with self._capture_output():
            move.cast()
            
        # For instant moves, process all stages immediately without advancing beats
        if is_instant:
            with self._capture_output():
                while self.player.current_move == move:
                    move.advance(self.player)
                    if self.player.current_move is None:
                        break
        else:
            # Loop until player is ready for input again
            # This handles multi-beat moves like Wait
            max_beats = 20  # Safety break
            beats_processed = 0
            
            while beats_processed < max_beats:
                # Synchronize distances at start of beat (just like combat.py)
                self._synchronize_distances()
                
                # Set the beat state index for this beat BEFORE processing
                # so all log messages get tagged with the correct index
                current_beat_index = len(beat_states)
                self.current_beat_state_index = current_beat_index
                
                # Capture output for THIS beat only
                with self._capture_output():
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
                    print(f"[DEBUG] Beat incremented to: {self.player.combat_beat}")
                
                # Capture state for this beat AFTER processing
                beat_state = CombatStateSerializer.serialize_combat_state(
                    self.player,
                    self.player.combat_list,
                    round_number=self.player.combat_beat
                )
                
                # Add log to beat state (snapshot of log at this point)
                beat_state["log"] = list(getattr(self.player, "combat_log", []))
                beat_states.append(beat_state)
                
                beats_processed += 1
                
                # Check if player is done with current move
                if self.player.current_move is None:
                    break
                
                # Check win/loss conditions inside loop
                if not self.player.is_alive() or len(self.player.combat_list) == 0:
                    break
        
        # Move execution finished
        result = self.get_combat_state()
        
        # Emit final state update
        if self.session_id:
            try:
                from flask import current_app
                if hasattr(current_app, 'socketio'):
                    room = f"combat_{self.session_id}"
                    current_app.socketio.emit('combat:update', result, room=room)
                    
                    # If awaiting input, also emit turn notification
                    if self.awaiting_input:
                        current_app.socketio.emit('combat:turn', {
                            'input_type': self.input_type,
                            'available_options_count': len(self.available_options)
                        }, room=room)
            except: pass
            
        # Check win/loss conditions
        if not self.player.is_alive():
            self.player.in_combat = False
            self._add_log_entry(
                self.output_capture.current_round,
                "You have been defeated!",
                "system"
            )

            # Set end-of-combat summary for defeat so frontend can show a game-over dialog
            try:
                import uuid
                self.player.combat_end_summary = {
                    "id": str(uuid.uuid4()),
                    "status": "defeat",
                    "message": "You have been defeated.",
                    "game_over": True,
                }
            except Exception:
                self.player.combat_end_summary = {
                    "id": "defeat",
                    "status": "defeat",
                    "message": "You have been defeated.",
                    "game_over": True,
                }

            result = self.get_combat_state()
            result["beat_states"] = beat_states
            return result
        
        if len(self.player.combat_list) == 0:
            self._handle_victory()
            result = self.get_combat_state()
            result["beat_states"] = beat_states
            return result
        
        # Set up for next move selection
        self.awaiting_input = True
        self.input_type = "move_selection"
        self.available_options = self._get_available_moves()
        self.pending_move_index = None
        
        result = self.get_combat_state()
        result["beat_states"] = beat_states
        print(f"[DEBUG] Returning {len(beat_states)} beat states")
        return result
    
    def _process_initial_turns(self):
        """Process NPC turns if they go first."""
        # Simple speed check - if any enemy is faster, they go first
        player_speed = getattr(self.player, "speed", 10)
        
        # Sync distances before start
        self._synchronize_distances()
        
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
        # Use a copy of the list because we might modify it (remove dead enemies)
        enemies_to_process = self.player.combat_list[:]
        
        for enemy in enemies_to_process:
            # If enemy is alive, process their turn
            if enemy.is_alive():
                self._process_npc(enemy)
            
            # Check if enemy died (was dead before or died during turn/recoil)
            # This check must happen regardless of whether they took a turn
            if not enemy.is_alive():
                enemy.die()
                if not enemy.is_alive():
                    # Death message is handled by enemy.die() -> print() -> captured by output capture
                    # Explicit logging removed to avoid duplication/mismatch

                    if enemy in self.player.current_room.npcs_here:
                        self.player.current_room.npcs_here.remove(enemy)
                    
                    if enemy in self.player.combat_list:
                        self.player.combat_list.remove(enemy)
                        
                    for ally in self.player.combat_list_allies:
                        if enemy in ally.combat_proximity:
                            del ally.combat_proximity[enemy]
                            
                    # Cleanup from player proximity as well to be safe
                    if hasattr(self.player, 'combat_proximity') and enemy in self.player.combat_proximity:
                         del self.player.combat_proximity[enemy]
    
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
        exp_gained: Dict[str, int] = {}
        level_ups: List[Dict[str, Any]] = []
        for subtype, value in self.player.combat_exp.items():
            if value > 0:
                gained = int(value)
                exp_gained[subtype] = gained
                exp_summary.append(f"{subtype}: {gained}")
                maybe_events = self.player.gain_exp(gained, exp_type=subtype)
                if isinstance(maybe_events, list) and maybe_events:
                    level_ups.extend(maybe_events)
                self.player.combat_exp[subtype] = 0
        
        victory_msg = "Victory! "
        if exp_summary:
            victory_msg += "Gained exp: " + ", ".join(exp_summary)
        
        self._add_log_entry(
            self.output_capture.current_round,
            victory_msg,
            "system"
        )

        # Aggregate combat drops collected during the encounter (API mode)
        drops_raw = getattr(self.player, "combat_drops", []) or []
        drops_by_name: Dict[str, int] = {}
        for d in drops_raw:
            name = (d or {}).get("name")
            qty = int((d or {}).get("quantity", 1) or 1)
            if not name:
                continue
            drops_by_name[name] = drops_by_name.get(name, 0) + max(0, qty)

        items_dropped = [
            {"name": name, "quantity": qty}
            for name, qty in sorted(drops_by_name.items(), key=lambda kv: kv[0].lower())
            if qty > 0
        ]

        # Capture a structured end-of-combat summary for the frontend
        self.player.combat_end_summary = {
            "id": str(uuid.uuid4()),
            "status": "victory",
            "message": "Victory!",
            "exp_gained": exp_gained,
            "items_dropped": items_dropped,
            "level_ups": level_ups,
            "attribute_points_available": int(getattr(self.player, "pending_attribute_points", 0) or 0),
            "attributes": {
                "strength_base": int(getattr(self.player, "strength_base", 0) or 0),
                "finesse_base": int(getattr(self.player, "finesse_base", 0) or 0),
                "speed_base": int(getattr(self.player, "speed_base", 0) or 0),
                "endurance_base": int(getattr(self.player, "endurance_base", 0) or 0),
                "charisma_base": int(getattr(self.player, "charisma_base", 0) or 0),
                "intelligence_base": int(getattr(self.player, "intelligence_base", 0) or 0),
            },
        }
    
    def _get_available_moves(self) -> List[Dict[str, Any]]:
        """Get list of all moves for the player with availability status."""
        moves = []
        
        # Get all known moves, not just viable ones
        for i, move in enumerate(self.player.known_moves):
            is_viable = move.viable()
            
            move_data = {
                "id": str(i),
                "index": i,
                "name": move.name,
                "description": getattr(move, "description", ""),
                "category": getattr(move, "category", "Miscellaneous"),
                "fatigue_cost": move.fatigue_cost,
                "available": True,
                "reason": None
            }
            
            # Check various conditions that might make the move unavailable
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
            elif not is_viable:
                # Move is not viable - try to determine why
                move_data["available"] = False
                
                # Check for common reasons
                if hasattr(move, 'targeted') and move.targeted:
                    # Check if it's a range issue
                    if hasattr(move, 'mvrange'):
                        range_min, range_max = move.mvrange
                        enemies_in_range = any(
                            range_min <= dist <= range_max 
                            for dist in self.player.combat_proximity.values()
                        )
                        if not enemies_in_range:
                            if range_max <= 5:
                                move_data["reason"] = "Enemy out of range (too far)"
                            else:
                                move_data["reason"] = "No valid target in range"
                        else:
                            move_data["reason"] = "Cannot use this move"
                    else:
                        move_data["reason"] = "No valid target"
                elif move.name == "Attack" and not getattr(self.player, 'eq_weapon', None):
                    move_data["reason"] = "No weapon equipped"
                else:
                    move_data["reason"] = "Cannot use this move"
            
            moves.append(move_data)
        
        return moves
    
    def _get_available_targets(self, move) -> List[Dict[str, Any]]:
        """Get list of available targets for a move."""
        targets = []
        range_min, range_max = move.mvrange
        
        # Special handling for bow
        if move.name == "Shoot Bow":
            range_max = self.player.eq_weapon.range_base + (100 / self.player.eq_weapon.range_decay)
        
        # Iterate over combat_list instead of combat_proximity to ensure we use the correct enemy instances
        for enemy in self.player.combat_list:
            if not enemy.is_alive():
                continue
                
            # Get distance from combat_proximity
            distance = self.player.combat_proximity.get(enemy, 0)
            
            if range_min <= distance <= range_max:
                target_data = {
                    "id": f"enemy_{id(enemy)}",
                    "name": enemy.name,
                    "distance": distance,
                }
                
                # Add hit chance if verbose targeting
                if move.verbose_targeting and hasattr(move, 'calculate_hit_chance'):
                    target_data["hit_chance"] = move.calculate_hit_chance(enemy)
                
                targets.append(target_data)
        
        # Sort by distance
        targets.sort(key=lambda t: t["distance"])
        return targets
    
    @contextlib.contextmanager
    def _capture_output(self):
        """Context manager to capture print output and sync to player log."""
        # Redirect stdout to our capture object
        with contextlib.redirect_stdout(self.output_capture):
            yield
            
        # Sync captured entries to player log (with deduplication)
        new_entries = self.output_capture.get_log()
        if new_entries:
            current_beat = getattr(self.player, "combat_beat", 0)
            for entry in new_entries:
                self._add_log_entry(current_beat, entry["message"], "combat", self.current_beat_state_index)
            
            # Clear capture for next time
            self.output_capture.clear()
    
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
            round_number=getattr(self.player, "combat_beat", 0)
        )
        
        # Add API-specific fields
        battle_state["beat"] = getattr(self.player, "combat_beat", 0)
        battle_state["heat"] = int(self.player.heat * 100)
        battle_state["awaiting_input"] = self.awaiting_input
        battle_state["input_type"] = self.input_type
        battle_state["available_options"] = self.available_options
        
        # Include check_data if available (from Check move)
        if hasattr(self.player, 'combat_adapter_state') and 'check_data' in self.player.combat_adapter_state:
            battle_state["check_data"] = self.player.combat_adapter_state['check_data']
            # Clear check_data after including it once
            del self.player.combat_adapter_state['check_data']

        result: Dict[str, Any] = {
            "combat_active": self.player.in_combat,
            "battle_state": battle_state,
            "beat_states": [battle_state],  # Initial state as a single beat state
            "log": self.player.combat_log,
        }

        # Include end-of-combat summary (victory/defeat) if present
        if not self.player.in_combat and getattr(self.player, "combat_end_summary", None):
            result["end_state"] = self.player.combat_end_summary

        return result
