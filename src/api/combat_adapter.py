"""
API Combat Adapter

This module adapts the existing terminal-based combat system for API use.
It captures output, manages state between API calls, and processes commands
without blocking for user input.
"""

import contextlib
import uuid
import threading
import logging
import re
import random
from datetime import datetime
from typing import Dict, Any, List, Optional, TYPE_CHECKING

import positions  # type: ignore
from src.api.serializers.combat import (
    CombatStateSerializer,
    CombatantSerializer,
)
from src.api.constants import ITEM_USE_RANGE, ALLY_HEAL_THRESHOLD
from ai.combat_strategist import CombatStrategist

if TYPE_CHECKING:
    from player import Player

# Compiled once at module level for performance
_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\_-]|\[[0-?]*[ -/]*[@-~])")

logger = logging.getLogger(__name__)


def _strip_combatant_prefix(target_id: str) -> str:
    """Strip 'enemy_' or 'ally_' prefix and return the raw Python id string."""
    for prefix in ("enemy_", "ally_"):
        if target_id.startswith(prefix):
            return target_id[len(prefix) :]
    return target_id


class CombatOutputCapture:
    """Captures print statements and stores them in a combat log."""

    def __init__(self, player=None):
        self.log_entries = []
        self.current_round = 1
        self.player = player  # Reference to player for animation tracking
        # Set by the adapter around each entity's advance() call so write() knows
        # exactly which combatant's pending animation to match against impact text.
        self.active_entity = None

    def write(self, text):
        """Capture text output."""
        if text and text.strip():
            # Clean ANSI codes
            clean_text = _ANSI_ESCAPE.sub("", text).strip()

            if clean_text:
                # Skip technical debug lines and animation errors
                if (
                    clean_text.startswith("DEBUG:")
                    or "Animation not found" in clean_text
                ):
                    return

                trigger_anim_data = None
                # Detect combat outcomes — only check the entity whose move is
                # currently advancing so we never misattribute an impact line to
                # a different combatant's pending animation.
                entity = self.active_entity if self.active_entity is not None else self.player
                if entity is not None and hasattr(entity, "_pending_animation"):
                    is_impact = False
                    if "struck" in clean_text and "damage" in clean_text:
                        entity._pending_animation["outcome"] = "hit"
                        is_impact = True
                    elif "parried" in clean_text:
                        entity._pending_animation["outcome"] = "parry"
                        is_impact = True
                    elif "missed" in clean_text or "just missed" in clean_text:
                        entity._pending_animation["outcome"] = "miss"
                        is_impact = True

                    if is_impact:
                        trigger_anim_data = entity._pending_animation
                        delattr(entity, "_pending_animation")

                entry = {
                    "round": self.current_round,
                    "message": clean_text,
                    "type": "combat",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                }
                if trigger_anim_data:
                    entry["trigger_animation"] = True
                    entry["animation_data"] = trigger_anim_data

                self.log_entries.append(entry)

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

    def __init__(
        self,
        player: "Player",
        session_id: str = None,
        on_event_callback: callable = None,
    ):
        self.player = player
        self.session_id = session_id
        self.on_event_callback = on_event_callback
        self.output_capture = CombatOutputCapture(player)
        self.current_beat_state_index = (
            0  # Track which beat state we're currently building
        )
        self.combat_grid_size = (
            13,
            13,
        )  # Set by initialize_combat; default matches legacy map size
        self.strategist = CombatStrategist()

        # Initialize persistent state if missing
        if not hasattr(self.player, "combat_adapter_state"):
            self.player.combat_adapter_state = {
                "awaiting_input": False,
                "input_type": None,
                "pending_move_index": None,
                "available_options": [],
            }

        # Track async suggestion loading state
        self.player.suggestions_loading = False
        self._suggestion_thread = None
        self._suggestion_generation = (
            0  # Generation counter for race condition prevention
        )
        self._suggestion_lock = (
            threading.Lock()
        )  # Guards generation counter and result writes

        # Suppress terminal animations in API mode.
        # Must set the flag on both possible module identities: moves.py imports
        # the bare 'animations' module, while this file lives under 'src.animations'.
        # They are different sys.modules entries so we set both.
        for _anim_name in ("animations", "src.animations"):
            try:
                import importlib
                import sys as _sys

                _anim_mod = _sys.modules.get(_anim_name) or importlib.import_module(
                    _anim_name
                )
                _anim_mod.set_api_mode(True)
            except Exception:
                pass

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

    def _add_log_entry(
        self,
        round_num: int,
        message: str,
        entry_type: str = "combat",
        beat_index: int = 0,
        animation_data: dict = None,
        timestamp: str = None,
    ):
        """Add a log entry with deduplication check.

        Args:
            round_num: Combat round number
            message: Log message text
            entry_type: Type of log entry (combat, system, etc.)
            beat_index: Index of the beat state this log entry corresponds to (for map sync)
            animation_data: Optional animation metadata for frontend
                Format: {
                    "type": "attack",  # Animation type
                    "source_id": "enemy_123",  # Entity performing move
                    "target_id": "enemy_456",  # Target entity (if targeted)
                    "outcome": "hit",  # "hit", "miss", "parry", etc.
                    "move_name": "Attack"
                }
        """
        if not hasattr(self.player, "combat_log"):
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
                "timestamp": timestamp or datetime.now().strftime("%H:%M:%S"),
                "beat_index": beat_index,  # For syncing with beat_states array
            }

            # Add animation metadata if provided
            if animation_data:
                entry["animation"] = animation_data

            self.player.combat_log.append(entry)

            # Emit socket event if session is known
            if self.session_id:
                try:
                    from flask import current_app

                    if hasattr(current_app, "socketio"):
                        room = f"combat_{self.session_id}"
                        current_app.socketio.emit("combat:log", entry, room=room)
                except Exception as e:
                    print(f"[SOCKET ERROR] Failed to emit log: {e}")

    def initialize_combat(
        self, enemies: List[Any], reinit: bool = False
    ) -> Dict[str, Any]:
        """
        Initialize combat with the given enemies.

        Args:
            enemies: List of enemy NPCs
            reinit: If True, this is a mid-combat update (reinforcements)

        Returns:
            Initial or updated combat state
        """
        try:
            # Import here to avoid circular dependencies

            if not reinit:
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

            if not reinit:
                self.player.heat = 1.0

            # Initialize positions
            scenario_type = "standard"
            if len(self.player.combat_list) > 1 and len(
                self.player.combat_list_allies
            ) < len(self.player.combat_list):
                scenario_type = "pincer"
            elif (
                len(self.player.combat_list_allies) == 1
                and len(self.player.combat_list) == 1
            ):
                scenario_type = "boss_arena"

            try:
                from src.coordinate_config import CoordinateSystemConfig

                coord_config = CoordinateSystemConfig(self.player)
                total_combatants = len(self.player.combat_list_allies) + len(
                    self.player.combat_list
                )
                grid_w, grid_h = coord_config.get_dynamic_grid_size(total_combatants)
                self.combat_grid_size = (grid_w, grid_h)

                positions.initialize_combat_positions(
                    allies=self.player.combat_list_allies,
                    enemies=self.player.combat_list,
                    scenario_type=scenario_type,
                    grid_width=grid_w,
                    grid_height=grid_h,
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
                            enemy.default_proximity = (
                                10  # Default distance - enemies start in striking range
                            )
                        if enemy not in ally.combat_proximity:
                            distance = int(
                                enemy.default_proximity * random.uniform(0.75, 1.25)
                            )
                            ally.combat_proximity[enemy] = distance
                            enemy.combat_proximity[ally] = distance

            if not reinit:
                # Reset moves only for new combat
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
                        logger.warning(
                            "Could not set player_ref on enemy %s",
                            getattr(enemy, "name", enemy),
                        )
                    for move in enemy.known_moves:
                        move.current_stage = 0
                        move.beats_left = 0
            else:
                # For re-init, ensure ALL combatants are properly flagged and
                # reset player move stages so prior cooldowns don't block new combat.
                for ally in self.player.combat_list_allies:
                    ally.in_combat = True
                    for move in ally.known_moves:
                        move.current_stage = 0
                        move.beats_left = 0
                for enemy in self.player.combat_list:
                    enemy.in_combat = True
                    try:
                        enemy.player_ref = self.player
                    except Exception:
                        logger.warning(
                            "Could not set player_ref on enemy %s",
                            getattr(enemy, "name", enemy),
                        )
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

            # Process initial NPC turns only for new combats
            if not reinit:
                self._process_initial_turns()

            # Set up for player's move selection OR resume existing move
            if reinit and self.player.current_move is not None:
                # RESUME the current move if we were mid-combat
                # This ensures recoil/cooldown beats continue after reinforcements
                return self._execute_move(self.player.current_move)

            self.awaiting_input = True
            self.input_type = "move_selection"
            self.available_options = self._get_available_moves()
            # Start async suggestion fetch (non-blocking)
            self.refresh_suggestions()

            result = self.get_combat_state()

            # Emit combat started event
            if self.session_id:
                try:
                    from flask import current_app

                    serialized_state = result
                    if hasattr(current_app, "socketio"):
                        current_app.socketio.emit(
                            "combat:started",
                            {"battle_state": serialized_state},
                            room=f"combat_{self.session_id}",
                        )
                except Exception:
                    import traceback

                    traceback.print_exc()
            return result

        except Exception as e:
            import traceback

            error_msg = (
                f"Combat initialization error: {str(e)}\n{traceback.format_exc()}"
            )
            print(error_msg)
            return {
                "error": "Failed to initialize combat",
                "details": str(e),
                "combat_active": False,
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
        elif command_type == "select_number":
            return self._handle_number_selection(command.get("value"))
        elif command_type == "select_move_and_target":
            return self._handle_combined_selection(
                command.get("move_name"), command.get("target_id")
            )
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

        return self.get_combat_state()

    def _handle_combined_selection(
        self, move_name: str, target_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle player selecting a move and target in one command."""
        if not isinstance(move_name, str) or not move_name.strip():
            return {"error": "Invalid move name"}

        if target_id is not None and not isinstance(target_id, str):
            return {"error": "Invalid target"}

        if self.input_type != "move_selection":
            return {"error": "Not expecting move selection"}

        # Find move by name (case-insensitive)
        move_index = -1
        for i, m in enumerate(self.player.known_moves):
            if m.name.strip().lower() == move_name.strip().lower():
                move_index = i
                break

        if move_index == -1:
            # Try partial match if no exact match
            for i, m in enumerate(self.player.known_moves):
                if move_name.strip().lower() in m.name.strip().lower():
                    move_index = i
                    break

        if move_index == -1:
            return {"error": f"Move '{move_name}' not found"}

        selected_move = self.player.known_moves[move_index]
        if not selected_move.viable():
            return {"error": "Move is not currently available"}

        if (
            selected_move.fatigue_cost > 0
            and self.player.fatigue < selected_move.fatigue_cost
        ):
            return {"error": "Not enough fatigue"}

        # If move is targeted, find target
        if selected_move.targeted:
            target = None
            viable_targets = self._get_available_targets(selected_move)

            if target_id:
                # Try to find the specified target
                target_obj_id = _strip_combatant_prefix(target_id)
                all_combatants = (
                    self.player.combat_list + self.player.combat_list_allies
                )
                for combatant in all_combatants:
                    if str(id(combatant)) == target_obj_id:
                        target = combatant
                        break

            # If no specific target found, try to auto-resolve if there's only one viable target
            if not target:
                if len(viable_targets) == 1:
                    single_target_id = (
                        viable_targets[0].get("id")
                        if isinstance(viable_targets[0], dict)
                        else None
                    )
                    if not isinstance(single_target_id, str):
                        return {"error": "Invalid target"}

                    target_obj_id = _strip_combatant_prefix(single_target_id)
                    all_combatants = (
                        self.player.combat_list + self.player.combat_list_allies
                    )
                    for combatant in all_combatants:
                        if str(id(combatant)) == target_obj_id:
                            target = combatant
                            break
                elif len(viable_targets) > 1:
                    # Multiple viable targets — request target selection
                    self.input_type = "target_selection"
                    self.available_options = viable_targets
                    self.pending_move_index = (
                        self.player.known_moves.index(selected_move)
                        if selected_move in self.player.known_moves
                        else -1
                    )
                    return self.get_combat_state()

            if not target:
                return {"error": "No viable targets available for this move."}

            selected_move.target = target
        else:
            selected_move.target = self.player

        self.player.current_move = selected_move
        self.player.current_move.user = self.player
        self._add_log_entry(
            self.output_capture.current_round,
            f"{self.player.name} uses {selected_move.name}!",
            "player_action",
        )

        return self._execute_move(selected_move)

    def _handle_move_selection(self, move_index: int) -> Dict[str, Any]:
        """Handle player selecting a move."""

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

        # Check if move is available (only check fatigue if move actually costs fatigue)
        if (
            selected_move.fatigue_cost > 0
            and self.player.fatigue < selected_move.fatigue_cost
        ):
            return {"error": "Not enough fatigue"}

        if selected_move.current_stage != 0:
            return {"error": "Move not ready yet"}

        self.player.current_move = selected_move
        self.player.current_move.user = self.player

        self._add_log_entry(
            self.output_capture.current_round,
            f"{self.player.name} uses {selected_move.name}!",
            "player_action",
        )

        # Check if move needs targeting
        if selected_move.targeted:
            viable_targets = self._get_available_targets(selected_move)

            # Check if we can auto-select target (exactly one viable target)
            if len(viable_targets) == 1:
                single_target_id = (
                    viable_targets[0].get("id")
                    if isinstance(viable_targets[0], dict)
                    else None
                )
                if not isinstance(single_target_id, str):
                    return {"error": "Invalid target"}

                target_obj_id = _strip_combatant_prefix(single_target_id)
                target = None
                all_combatants = (
                    self.player.combat_list + self.player.combat_list_allies
                )
                for combatant in all_combatants:
                    if str(id(combatant)) == target_obj_id:
                        target = combatant
                        break

                if target:
                    selected_move.target = target
                    self.pending_move_index = None
                    return self._execute_move(selected_move)
                else:
                    return {"error": "Failed to resolve single target"}

            if len(viable_targets) == 0:
                return {"error": "No valid targets available for this move"}

            # Multiple targets - standard flow
            self.input_type = "target_selection"
            self.available_options = viable_targets
            self.pending_move_index = move_index
            # Keep awaiting_input True so frontend knows to send target
            return self.get_combat_state()

        # Check if move needs duration input (e.g., Wait move)
        if hasattr(selected_move, "needs_duration") and selected_move.needs_duration:
            self.input_type = "number_input"
            self.available_options = {
                "prompt": "How many beats do you want to wait?",
                "min": 3,
                "max": 10,
                "default": 5,
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

        if not isinstance(target_id, str) or not target_id:
            return {"error": "Invalid target"}

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
        target_obj_id = _strip_combatant_prefix(target_id)

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
        if hasattr(pending_move, "target_direction"):
            # Convert string to Direction enum
            direction_map = {
                "north": positions.Direction.N,
                "south": positions.Direction.S,
                "east": positions.Direction.E,
                "west": positions.Direction.W,
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
        if hasattr(pending_move, "duration"):
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
            if hasattr(unit, "combat_position") and unit.combat_position is not None:
                unit.combat_proximity = positions.recalculate_proximity_dict(
                    unit, all_combatants
                )

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
                    each_enemy.combat_proximity[each_ally] = each_ally.combat_proximity[
                        each_enemy
                    ]
                else:
                    # Enemy not in list (legacy/fallback), add with random distance
                    # But ONLY if we don't have positions (which would have handled it above)
                    if not (
                        hasattr(each_enemy, "combat_position")
                        and each_enemy.combat_position is not None
                        and hasattr(each_ally, "combat_position")
                        and each_ally.combat_position is not None
                    ):

                        default = getattr(each_enemy, "default_proximity", 20)
                        each_distance = int(default * random.uniform(0.75, 1.25))
                        each_ally.combat_proximity[each_enemy] = each_distance
                        each_enemy.combat_proximity[each_ally] = each_distance

        # Ensure reverse mapping for enemies
        for each_enemy in player.combat_list:
            for each_ally in player.combat_list_allies:
                if each_ally not in each_enemy.combat_proximity:
                    # If missed above, sync
                    if each_enemy in each_ally.combat_proximity:
                        each_enemy.combat_proximity[each_ally] = (
                            each_ally.combat_proximity[each_enemy]
                        )

    def _move_deals_damage(self, move) -> bool:
        """Check if a move deals damage (for animation fallback logic).

        Args:
            move: The move to check

        Returns:
            True if the move is likely to deal damage, False otherwise
        """
        # Check move category
        if hasattr(move, "category"):
            damage_categories = ["Attack", "Offensive", "Special"]
            if move.category in damage_categories:
                return True

        # Check move name patterns
        damage_keywords = [
            "attack",
            "strike",
            "slash",
            "stab",
            "smash",
            "crush",
            "punch",
            "kick",
        ]
        move_name_lower = move.name.lower()
        if any(keyword in move_name_lower for keyword in damage_keywords):
            return True

        return False

    def _execute_move(self, move) -> Dict[str, Any]:
        """Execute a move and process the combat beat(s)."""
        try:
            return self._execute_move_inner(move)
        except Exception as e:
            logger.exception(
                "Unhandled exception in _execute_move for move '%s'",
                getattr(move, "name", "?"),
            )
            # Reset to a consistent baseline so subsequent moves are not blocked
            self.input_type = "move_selection"
            self.pending_move_index = None
            self.awaiting_input = True
            try:
                self.available_options = self._get_available_moves()
            except Exception:
                self.available_options = []
            return {"error": f"Move execution failed: {e}"}

    def _execute_move_inner(self, move) -> Dict[str, Any]:
        """Inner move execution — called only via _execute_move which handles state recovery."""
        # Reset beat state index for this move execution
        self.current_beat_state_index = 0

        is_instant = hasattr(move, "instant") and move.instant
        beat_states = []

        # Cast the move (capture output for initial cast message)
        with self._capture_output():
            # Store for repeat functionality
            self.player.last_move_name = move.name
            self.player.last_move_target_id = (
                getattr(move.target, "id", f"enemy_{id(move.target)}")
                if getattr(move, "target", None)
                else None
            )

            # Determine animation type using fallback logic
            animation_type = getattr(move, "web_animation", None)
            if animation_type is None:
                # Apply fallback logic
                if move.targeted and self._move_deals_damage(move):
                    animation_type = "attack"
                else:
                    animation_type = "pulse"

            # Create animation metadata
            animation_data = {
                "type": animation_type,
                "source_id": "player",
                "target_id": (
                    (
                        f"enemy_{id(move.target)}"
                        if move.target != self.player
                        else "player"
                    )
                    if move.targeted and move.target
                    else None
                ),
                "move_name": move.name,
            }

            # Store for outcome tracking (will be updated when combat output is captured)
            self.player._pending_animation = animation_data
            # Tag the active entity so write() can find the right pending animation
            self.output_capture.active_entity = self.player

            move.cast()

        self.output_capture.active_entity = None

        # For instant moves, process all stages immediately without advancing beats
        if is_instant:
            with self._capture_output():
                self.output_capture.active_entity = self.player
                while self.player.current_move == move:
                    move.advance(self.player)
                    if self.player.current_move is None:
                        break
                self.output_capture.active_entity = None
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
                    # Advance all player moves — tag so write() matches the right animation
                    self.output_capture.active_entity = self.player
                    for m in self.player.known_moves:
                        m.advance(self.player)
                    self.output_capture.active_entity = None

                    # Process NPC turns (each NPC sets active_entity internally)
                    self._process_npc_turns()

                    # Cycle states
                    self.player.cycle_states()

                    # Update heat
                    self._update_heat()

                    # Increment beat
                    self.player.combat_beat += 1

                # Check for combat events after each beat
                if self.on_event_callback:
                    events = self.on_event_callback(self.player)
                    if events:
                        # Narrative pause: record events and stop processing beats for now
                        if not hasattr(self.player, "combat_adapter_state"):
                            self.player.combat_adapter_state = {}
                        self.player.combat_adapter_state["events_triggered"] = events

                        # Stop processing beats
                        break

                # Capture state for this beat AFTER processing
                beat_state = CombatStateSerializer.serialize_combat_state(
                    self.player,
                    self.player.combat_list,
                    round_number=self.player.combat_beat,
                    allies=self.player.combat_list_allies[1:],
                )

                # Add log to beat state (snapshot of log at this point)
                beat_state["log"] = list(getattr(self.player, "combat_log", []))
                beat_states.append(beat_state)

                beats_processed += 1

                # Check win/loss conditions inside loop
                if not self.player.is_alive() or len(self.player.combat_list) == 0:
                    break

                # Check if the current move has finished executing (entered cooldown or
                # completed). Return control as soon as at least one move is back at
                # stage 0 — meaning the player has something they can do. Only keep
                # advancing if every move is still in cooldown (player would have no
                # available actions), to avoid leaving the player with zero options.
                if self.player.current_move is None:
                    # Guard: no moves at all — don't burn remaining max_beats
                    if not self.player.known_moves:
                        break
                    if any(m.current_stage == 0 for m in self.player.known_moves):
                        break
                    # All moves still cooling — re-check survival before the next drain beat
                    if not self.player.is_alive() or len(self.player.combat_list) == 0:
                        break
                    # Keep advancing beats until one opens up

        # Capture last move summary from the log entries of this move
        move_logs = [
            s["message"]
            for s in self.player.combat_log
            if s.get("type") in ("combat", "player_action")
        ][
            -5:
        ]  # Last 5 relevant entries
        self.player.last_move_summary = " ".join(move_logs)

        # Fallback: emit any animation that never found a matching impact line.
        # This can happen when a move deals no damage (e.g. a miss with unusual text),
        # ensuring the animation is never silently dropped.
        for entity in self._all_combatants():
            if hasattr(entity, "_pending_animation"):
                animation_data = entity._pending_animation
                self._add_log_entry(
                    self.player.combat_beat,
                    f"{animation_data.get('move_name', 'Move')} animation",
                    "animation",
                    beat_index=self.current_beat_state_index,
                    animation_data=animation_data,
                )
                delattr(entity, "_pending_animation")

        # Move execution finished

        # Check win/loss conditions
        if not self.player.is_alive():
            self.player.in_combat = False
            self.awaiting_input = False
            self._add_log_entry(
                self.player.combat_beat, "You have been defeated!", "system"
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
                    "id": str(uuid.uuid4()),
                    "status": "defeat",
                    "message": "You have been defeated.",
                    "game_over": True,
                }

            result = self.get_combat_state()
            result["beat_states"] = beat_states
            return result

        # Evaluate all combat events one final time when enemies are defeated
        # This allows events (like reinforcement spawners) to inject new enemies before victory
        if len(self.player.combat_list) == 0:
            # All enemies defeated — the move is done regardless of remaining cooldown beats.
            # Clearing current_move prevents initialize_combat(reinit=True), called later by
            # story events like Ch01PostRumbler, from re-executing a stale attack against the
            # newly spawned reinforcements.
            self.player.current_move = None
            if self.on_event_callback:
                # Use the bridge to GameService so results are consistent
                new_events = self.on_event_callback(self.player)
                if new_events:
                    if not hasattr(self.player, "combat_adapter_state"):
                        self.player.combat_adapter_state = {}
                    existing = self.player.combat_adapter_state.get(
                        "events_triggered", []
                    )
                    self.player.combat_adapter_state["events_triggered"] = (
                        existing + new_events
                    )

            # After event callbacks run, any newly-spawned enemies that were added via
            # combat_engage() won't have a combat_position (they only got a legacy proximity
            # entry).  Initialize positions for them now so _synchronize_distances() won't
            # drop them from Jean's proximity dict on the next beat.
            new_enemies_without_position = [
                e
                for e in self.player.combat_list
                if not hasattr(e, "combat_position") or e.combat_position is None
            ]
            if new_enemies_without_position:
                try:
                    from src.coordinate_config import CoordinateSystemConfig

                    # Only pass the new (unpositioned) enemies — initialize_combat_positions
                    # unconditionally overwrites combat_position on every unit it receives,
                    # so passing the full combat_list would teleport already-placed combatants.
                    total = len(self.player.combat_list_allies) + len(
                        new_enemies_without_position
                    )
                    coord_config = CoordinateSystemConfig(self.player)
                    grid_w, grid_h = coord_config.get_dynamic_grid_size(total)
                    self.combat_grid_size = (grid_w, grid_h)
                    positions.initialize_combat_positions(
                        allies=[],
                        enemies=new_enemies_without_position,
                        scenario_type="standard",
                        grid_width=grid_w,
                        grid_height=grid_h,
                    )
                except Exception as e:
                    logger.warning("Position init for reinforcements failed: %s", e)
                # Immediately sync proximity so Attack.viable() can see new enemies on
                # the next get_available_moves() call without waiting for the next beat.
                try:
                    self._synchronize_distances()
                except Exception:
                    pass

        # Check if events triggered (BEFORE calling get_combat_state which consumes them)
        event_just_triggered = (
            hasattr(self.player, "combat_adapter_state")
            and "events_triggered" in self.player.combat_adapter_state
        )

        # ALWAYS handle victory when all enemies are defeated
        # (even if post-combat events like Ch01PostRumbler3 are firing).
        # Events should not suppress the victory state — the frontend needs
        # combat_end_summary to know when combat has ended.
        if len(self.player.combat_list) == 0 and self.player.in_combat:
            self._handle_victory()

            # If no events are blocking, return victory immediately
            if not event_just_triggered:
                result = self.get_combat_state()
                result["beat_states"] = beat_states
                return result

        # Set up for next move selection if battle continues and no event is blocking
        if not event_just_triggered:
            self.awaiting_input = True
            self.input_type = "move_selection"
            self.available_options = self._get_available_moves()
            self.pending_move_index = None
            # Start async suggestion fetch (non-blocking)
            self.refresh_suggestions()
        else:
            # Events just fired (e.g., reinforcement wave spawned). Clear stale
            # pending-move state so when the player dismisses events and returns
            # to combat they get a fresh move_selection prompt instead of a
            # phantom target_selection loop with 0-damage attacks.
            #
            # Also reset any in-progress move (stages 1-2 = execute/recoil) back to
            # stage 0. When the beat loop breaks early on an event, the selected move
            # is left mid-execution. _handle_move_selection checks current_stage != 0
            # and returns "Move not ready yet", creating a permanent deadlock where the
            # interrupted move can never be selected again.
            if self.player.current_move is not None:
                try:
                    self.player.current_move.current_stage = 0
                    self.player.current_move.beats_left = 0
                except Exception:
                    pass
                self.player.current_move = None
            self.awaiting_input = True
            self.input_type = "move_selection"
            self.pending_move_index = None
            try:
                self.available_options = self._get_available_moves()
            except Exception:
                self.available_options = []

        # Final state capture (consumes events_triggered)
        result = self.get_combat_state()
        result["beat_states"] = beat_states

        # Emit final state update
        if self.session_id:
            try:
                from flask import current_app

                if hasattr(current_app, "socketio"):
                    room = f"combat_{self.session_id}"
                    current_app.socketio.emit("combat:update", result, room=room)

                    # If awaiting input, also emit turn notification
                    if self.awaiting_input:
                        current_app.socketio.emit(
                            "combat:turn",
                            {
                                "input_type": self.input_type,
                                "available_options_count": len(self.available_options),
                            },
                            room=room,
                        )
            except Exception as e:
                logger.warning("Failed to emit socket update after process_move: %s", e)

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
                    if (
                        hasattr(self.player, "combat_proximity")
                        and enemy in self.player.combat_proximity
                    ):
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
                # Ally-healing check: use a consumable on a nearby friendly below threshold
                if self._npc_try_heal_ally(npc):
                    return

                # Select target
                if not npc.friend:
                    npc.target = random.choice(self.player.combat_list_allies)
                else:
                    npc.target = random.choice(self.player.combat_list)

                # Select and cast move
                npc.select_move()
                if npc.current_move:
                    npc.current_move.target = npc.target

                    # Determine animation type
                    animation_type = getattr(npc.current_move, "web_animation", None)
                    if animation_type is None:
                        if npc.current_move.targeted and self._move_deals_damage(
                            npc.current_move
                        ):
                            animation_type = "attack"
                        else:
                            animation_type = "pulse"

                    # Create animation data
                    animation_data = {
                        "type": animation_type,
                        "source_id": f"enemy_{id(npc)}",
                        "target_id": (
                            "player"
                            if npc.target == self.player
                            else (f"enemy_{id(npc.target)}" if npc.target else None)
                        ),
                        "move_name": npc.current_move.name,
                    }

                    # Store pending animation on the NPC; write() will pair it with
                    # the impact line printed during a future advance() call.
                    npc._pending_animation = animation_data

                    with self._capture_output():
                        # Tag entity so write() matches the cast prep text correctly
                        self.output_capture.active_entity = npc
                        if hasattr(npc.current_move, "cast") and callable(
                            npc.current_move.cast
                        ):
                            npc.current_move.cast()
                        self.output_capture.active_entity = None

        # Advance moves — tag active_entity so write() resolves the impact animation
        # to this NPC rather than any other combatant that also has _pending_animation.
        moves_to_advance = list(getattr(npc, "known_moves", []))
        if npc.current_move is not None and npc.current_move not in moves_to_advance:
            moves_to_advance.append(npc.current_move)

        self.output_capture.active_entity = npc
        try:
            for move in moves_to_advance:
                move.advance(npc)
        finally:
            # Always clear so a subsequent entity doesn't inherit this NPC's context
            self.output_capture.active_entity = None

    def _npc_try_heal_ally(self, npc) -> bool:
        """Check whether this NPC should spend its turn healing a nearby ally.

        Applies to any NPC that has consumable items in its inventory.  Returns
        True and executes the heal (consuming the item) if a valid target was
        found; returns False so normal move-selection proceeds otherwise.
        """
        import items as items_module

        inventory = getattr(npc, "inventory", [])
        consumables = [
            it
            for it in inventory
            if isinstance(it, items_module.Consumable) and hasattr(it, "use")
        ]
        if not consumables:
            return False

        # Build list of friendlies (allies share the same faction)
        if npc.friend:
            # Friendly NPC: allies are player + other friends; enemies are combat_list
            friendlies = list(getattr(self.player, "combat_list_allies", []))
        else:
            # Enemy NPC: allies are other enemies
            friendlies = list(getattr(self.player, "combat_list", []))

        # Find a living friendly below the heal threshold that is within range
        heal_target = None
        for friendly in friendlies:
            if friendly is npc or not friendly.is_alive():
                continue
            maxhp = getattr(friendly, "maxhp", 1) or 1
            hp_frac = getattr(friendly, "hp", maxhp) / maxhp
            if hp_frac >= ALLY_HEAL_THRESHOLD:
                continue
            dist = npc.combat_proximity.get(friendly, 9999)
            if dist > ITEM_USE_RANGE:
                continue
            # Prefer the most-injured friendly
            if heal_target is None:
                heal_target = friendly
            elif (getattr(friendly, "hp", 0) / maxhp) < (
                getattr(heal_target, "hp", 0) / (getattr(heal_target, "maxhp", 1) or 1)
            ):
                heal_target = friendly

        if heal_target is None:
            return False

        item = consumables[0]
        item_name = getattr(item, "name", "item")
        try:
            with self._capture_output():
                item.use(heal_target, user=npc)
        except Exception:
            logger.exception(
                "%s failed to use %s on %s", npc.name, item_name, heal_target.name
            )
            return False

        # Stacked consumables self-remove via the user= parameter when count
        # hits zero. This guard handles any item type that does NOT remove
        # itself inside use() (e.g. a future reusable NPC consumable).
        if item in inventory:
            inventory.remove(item)

        target_label = (
            "player" if heal_target == self.player else f"ally_{id(heal_target)}"
        )
        self._add_log_entry(
            self.player.combat_beat,
            f"{npc.name} uses {item_name} on {heal_target.name}!",
            "combat",
        )
        self._add_log_entry(
            self.player.combat_beat,
            f"{npc.name} uses {item_name}",
            "animation",
            beat_index=self.current_beat_state_index,
            animation_data={
                "type": "pulse",
                "source_id": f"{'ally' if npc.friend else 'enemy'}_{id(npc)}",
                "target_id": target_label,
                "move_name": f"Use {item_name}",
            },
        )
        return True

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

    def refresh_suggestions(self):
        """Fetch tactical suggestions asynchronously without blocking combat."""
        import logging

        logger = logging.getLogger(__name__)

        # Set loading state
        self.player.suggestions_loading = True
        self.player.suggested_moves = []  # Clear previous suggestions while loading

        # Increment generation counter to invalidate any in-flight requests
        with self._suggestion_lock:
            self._suggestion_generation += 1
            current_gen = self._suggestion_generation

        # Get flask app to pass to the thread
        try:
            from flask import current_app

            flask_app = current_app._get_current_object()
            logger.debug(
                f"Flask app context captured for suggestion thread (App: {flask_app})"
            )
        except Exception as e:
            logger.warning(f"Failed to capture flask app context: {e}")
            flask_app = None

        # Create and start a new thread for fetching suggestions
        def fetch_suggestions_worker():
            logger.debug(f"Suggestion worker started (Gen: {current_gen})")

            def run_with_context():
                logger.debug(f"Suggestion fetch started (Gen: {current_gen})")
                try:
                    # Calculate allowed suggestions count
                    count = getattr(self.player, "base_suggested_move_count", 1)
                    for m in self.player.known_moves:
                        if m.name in ["Strategic Insight", "Master Tactician"]:
                            count += 1

                    # Ensure combat_log exists
                    if not hasattr(self.player, "combat_log"):
                        self.player.combat_log = []

                    logger.debug(
                        f"Preparing strategist context: {len(self.player.combat_list)} enemies, {len(self.available_options)} available moves"
                    )
                    # Gather context
                    ctx = {
                        "player": CombatantSerializer.serialize_combatant(self.player),
                        "enemies": [
                            CombatantSerializer.serialize_combatant(
                                e, reference=self.player
                            )
                            for e in self.player.combat_list
                        ],
                        "history": [
                            entry["message"] for entry in self.player.combat_log[-20:]
                        ],  # Last 20 messages
                        "last_move": getattr(self.player, "last_move_summary", "None"),
                        # Only send moves that are available AND (if targeted) have
                        # at least one viable target — prevents TA from suggesting
                        # attacks that cannot resolve at execution time.
                        "available_moves": [
                            m
                            for m in self.available_options
                            if isinstance(m, dict)
                            and m.get("available", True)
                            and (
                                not m.get("targeted")
                                or len(m.get("viable_targets", [])) > 0
                            )
                        ],
                    }

                    logger.debug(f"Combat context keys: {list(ctx.keys())}")

                    # Fetch from strategist (this is the slow part)
                    suggestions = self.strategist.get_suggestions(
                        ctx, max_suggestions=count
                    )

                    # Filter out suggestions for moves that are not currently available
                    available_move_names = {
                        m["name"]
                        for m in self._get_available_moves()
                        if m.get("available", True)
                    }
                    suggestions = [
                        s
                        for s in suggestions
                        if s.get("move_name") in available_move_names
                    ]

                    # Store results (only if this generation is still current)
                    with self._suggestion_lock:
                        is_current = current_gen == self._suggestion_generation
                    if is_current:
                        self.player.suggested_moves = suggestions
                        self.player.suggestions_loading = False
                        logger.debug(
                            f"Suggestion fetch complete (Gen: {current_gen}, {len(suggestions)} suggestions)"
                        )

                        # Emit socket event to notify frontend that suggestions are ready
                        if self.session_id:
                            try:
                                if flask_app and hasattr(flask_app, "socketio"):
                                    logger.debug(
                                        f"Emitting combat:suggestions_ready to room combat_{self.session_id} ({len(suggestions)} suggestions)"
                                    )
                                    flask_app.socketio.emit(
                                        "combat:suggestions_ready",
                                        {"suggested_moves": suggestions},
                                        room=f"combat_{self.session_id}",
                                    )
                                else:
                                    logger.warning(
                                        f"Cannot emit suggestions - flask_app is {flask_app} or socketio missing"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error emitting suggestions_ready event: {e}"
                                )
                        else:
                            logger.warning(
                                "Cannot emit suggestions - session_id is missing"
                            )

                except Exception as e:
                    logger.error(f"Error in async suggestion fetch: {e}", exc_info=True)
                    with self._suggestion_lock:
                        is_current = current_gen == self._suggestion_generation
                    if is_current:
                        self.player.suggested_moves = []
                        self.player.suggestions_loading = False
                        logger.info(
                            f"DEBUG: Reset suggestions_loading after error (Gen: {current_gen})"
                        )

            if flask_app:
                with flask_app.app_context():
                    run_with_context()
            else:
                run_with_context()

        import threading

        threading.Thread(target=fetch_suggestions_worker, daemon=True).start()

    def _evaluate_combat_events(self):
        """
        Evaluate all active combat events when enemies are defeated.

        This allows events (like reinforcement spawners) to inject new enemies
        before combat ends, preventing premature victory declarations.

        Each event's check_combat_conditions() is called safely with error
        handling to prevent one failing event from crashing combat.

        Combat events check conditions and can trigger processes that might
        add new enemies to combat_list, which should continue the battle
        rather than declaring victory.
        """
        if len(self.player.combat_events) == 0:
            return

        # Evaluate each combat event's conditions safely
        for event in self.player.combat_events[
            :
        ]:  # Use slice copy to avoid modification issues
            try:
                if hasattr(event, "check_combat_conditions"):
                    event.check_combat_conditions()
            except Exception as e:
                event_name = getattr(event, "name", "UnknownEvent")
                logger.warning("Error evaluating combat event '%s': %s", event_name, e)

    def _handle_victory(self):
        """Handle combat victory."""
        self.player.in_combat = False
        self.awaiting_input = False
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

        self._add_log_entry(self.output_capture.current_round, victory_msg, "system")

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
            "attribute_points_available": int(
                getattr(self.player, "pending_attribute_points", 0) or 0
            ),
            "exp_to_next_level": int(
                (getattr(self.player, "exp_to_level", 0) or 0)
                - (getattr(self.player, "exp", 0) or 0)
            ),
            "attributes": {
                "strength_base": int(getattr(self.player, "strength_base", 0) or 0),
                "finesse_base": int(getattr(self.player, "finesse_base", 0) or 0),
                "speed_base": int(getattr(self.player, "speed_base", 0) or 0),
                "endurance_base": int(getattr(self.player, "endurance_base", 0) or 0),
                "charisma_base": int(getattr(self.player, "charisma_base", 0) or 0),
                "intelligence_base": int(
                    getattr(self.player, "intelligence_base", 0) or 0
                ),
            },
        }

        # Check for beta end: player just defeated the Lurker in Verdette Caverns.
        # Mirrors AfterDefeatingLurker.check_conditions() — no Lurker on tile,
        # but that tile still carries the AfterDefeatingLurker event marker.
        tile = getattr(self.player, "current_room", None)
        if tile:
            has_lurker_event = any(
                e.__class__.__name__ == "AfterDefeatingLurker"
                for e in getattr(tile, "events_here", [])
            )
            lurker_still_present = any(
                n.__class__.__name__ == "Lurker" for n in getattr(tile, "npcs_here", [])
            )
            if has_lurker_event and not lurker_still_present:
                self.player.combat_end_summary["beta_end"] = True

    def _get_available_moves(self) -> List[Dict[str, Any]]:
        """Get list of all moves for the player with availability status."""
        moves = []

        # Get all known moves, not just viable ones
        for i, move in enumerate(self.player.known_moves):
            if getattr(move, "passive", False):
                continue
            is_viable = move.viable()

            is_targeted = getattr(move, "targeted", False)
            viable_targets = []
            if is_targeted and is_viable:
                viable_targets = self._get_available_targets(move)

            move_data = {
                "id": str(i),
                "index": i,
                "name": move.name,
                "description": getattr(move, "description", ""),
                "category": getattr(move, "category", "Miscellaneous"),
                "fatigue_cost": move.fatigue_cost,
                "available": True,
                "reason": None,
                "targeted": is_targeted,
                "viable_targets": viable_targets,
                "requires_target_selection": is_targeted and len(viable_targets) > 1,
            }

            # Check various conditions that might make the move unavailable
            if move.current_stage == 3:
                if move.beats_left > 0:
                    move_data["available"] = False
                    move_data["reason"] = f"Available in {move.beats_left + 1} beats"
                else:
                    move_data["available"] = False
                    move_data["reason"] = "Available next beat"
            elif move.fatigue_cost > 0 and self.player.fatigue < move.fatigue_cost:
                move_data["available"] = False
                move_data["reason"] = "Not enough fatigue"
            elif not is_viable:
                # Move is not viable - try to determine why
                move_data["available"] = False

                # Check for common reasons
                if is_targeted:
                    # Check if it's a range issue
                    mvrange = getattr(move, "mvrange", None)
                    if mvrange:
                        range_min, range_max = mvrange
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
                elif move.name == "Attack" and not getattr(
                    self.player, "eq_weapon", None
                ):
                    move_data["reason"] = "No weapon equipped"
                else:
                    move_data["reason"] = "Cannot use this move"

            moves.append(move_data)

        return moves

    def _get_available_targets(self, move) -> List[Dict[str, Any]]:
        """Get list of available targets for a move."""
        targets = []

        # Get range from move
        if hasattr(move, "mvrange"):
            range_min, range_max = move.mvrange
        else:
            # Default to adjacent if no range specified but targeted
            range_min, range_max = 0, 5

        # Special handling for bow
        if move.name == "Shoot Bow" and self.player.eq_weapon:
            range_max = self.player.eq_weapon.range_base + (
                100 / self.player.eq_weapon.range_decay
            )

        # Iterate over combat_list instead of combat_proximity to ensure we use the correct enemy instances
        for enemy in self.player.combat_list:
            # Explicitly skip the player if they somehow ended up in the combat_list
            if enemy == self.player:
                continue

            if not enemy.is_alive():
                continue

            # Get distance from combat_proximity
            distance = self.player.combat_proximity.get(enemy, 0)

            if range_min <= distance <= range_max:
                target_data = {
                    "id": f"enemy_{id(enemy)}",
                    "name": enemy.name,
                    "distance": distance,
                    "is_ally": False,
                    "health": {
                        "current": getattr(enemy, "hp", getattr(enemy, "health", 0)),
                        "max": getattr(
                            enemy, "maxhp", getattr(enemy, "max_health", 100)
                        ),
                    },
                }

                # Add hit chance if verbose targeting
                if move.verbose_targeting and hasattr(move, "calculate_hit_chance"):
                    target_data["hit_chance"] = move.calculate_hit_chance(enemy)

                targets.append(target_data)

        # Include allies when the move explicitly accepts them (e.g. Advance for healing setup)
        if getattr(move, "accepts_ally_target", False):
            for ally in self.player.combat_list_allies:
                if ally == self.player or not ally.is_alive():
                    continue
                distance = self.player.combat_proximity.get(ally, 0)
                if range_min <= distance <= range_max:
                    targets.append(
                        {
                            "id": f"ally_{id(ally)}",
                            "name": ally.name,
                            "distance": distance,
                            "is_ally": True,
                            "health": {
                                "current": getattr(ally, "hp", 0),
                                "max": getattr(ally, "maxhp", 100),
                            },
                        }
                    )

        # Sort by distance
        targets.sort(key=lambda t: t["distance"])
        return targets

    def _all_combatants(self) -> List[Any]:
        """Return a flat list of every entity currently in combat (player + allies + enemies)."""
        return (
            [self.player]
            + list(getattr(self.player, "combat_list", []))
            + list(getattr(self.player, "combat_list_allies", []))
        )

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
                self._add_log_entry(
                    current_beat,
                    entry["message"],
                    "combat",
                    self.current_beat_state_index,
                    timestamp=entry.get("timestamp"),
                )
                if entry.get("trigger_animation") and "animation_data" in entry:
                    animation_data = entry["animation_data"]
                    self._add_log_entry(
                        current_beat,
                        f"{animation_data.get('move_name', 'Move')} animation",
                        "animation",
                        beat_index=self.current_beat_state_index,
                        animation_data=animation_data,
                    )

            # Clear capture for next time
            self.output_capture.clear()

    def get_combat_state(self) -> Dict[str, Any]:
        """
        Get the current combat state for the frontend.
        """
        # Serialize combat state (allies excludes the player who is always index 0)
        battle_state = CombatStateSerializer.serialize_combat_state(
            self.player,
            self.player.combat_list,
            current_turn_index=0,  # Not used in API version
            round_number=getattr(self.player, "combat_beat", 0),
            allies=self.player.combat_list_allies[1:],
        )

        # Add API-specific fields
        battle_state["beat"] = getattr(self.player, "combat_beat", 0)
        battle_state["heat"] = int(self.player.heat * 100)
        battle_state["awaiting_input"] = self.awaiting_input
        battle_state["input_type"] = self.input_type
        battle_state["available_options"] = self.available_options

        # Include check_data if available (from Check move)
        if (
            hasattr(self.player, "combat_adapter_state")
            and "check_data" in self.player.combat_adapter_state
        ):
            battle_state["check_data"] = self.player.combat_adapter_state["check_data"]
            # Clear check_data after including it once
            del self.player.combat_adapter_state["check_data"]

        grid_size = self.combat_grid_size
        result: Dict[str, Any] = {
            "combat_active": self.player.in_combat,
            "map_size": grid_size[0],
            "battle_state": battle_state,
            "beat_states": [battle_state],  # Initial state as a single beat state
            "log": getattr(self.player, "combat_log", []),
            "suggested_moves": getattr(self.player, "suggested_moves", []),
            "suggestions_loading": getattr(self.player, "suggestions_loading", False),
            "last_move_outcome": getattr(self.player, "last_move_summary", ""),
            "last_move_name": getattr(self.player, "last_move_name", ""),
            "last_move_target_id": getattr(self.player, "last_move_target_id", None),
        }

        # Include triggered events if any (narrative pause)
        if (
            hasattr(self.player, "combat_adapter_state")
            and "events_triggered" in self.player.combat_adapter_state
        ):
            result["events_triggered"] = self.player.combat_adapter_state[
                "events_triggered"
            ]
            # Clear after including
            del self.player.combat_adapter_state["events_triggered"]

        # Include end-of-combat summary (victory/defeat) if present
        if not self.player.in_combat and getattr(
            self.player, "combat_end_summary", None
        ):
            summary = self.player.combat_end_summary
            # Refresh dynamic values if it's a victory
            if summary.get("status") == "victory":
                summary["attribute_points_available"] = int(
                    getattr(self.player, "pending_attribute_points", 0) or 0
                )
                summary["exp_to_next_level"] = int(
                    (getattr(self.player, "exp_to_level", 0) or 0)
                    - (getattr(self.player, "exp", 0) or 0)
                )
                summary["attributes"] = {
                    "strength_base": int(getattr(self.player, "strength_base", 0) or 0),
                    "finesse_base": int(getattr(self.player, "finesse_base", 0) or 0),
                    "speed_base": int(getattr(self.player, "speed_base", 0) or 0),
                    "endurance_base": int(
                        getattr(self.player, "endurance_base", 0) or 0
                    ),
                    "charisma_base": int(getattr(self.player, "charisma_base", 0) or 0),
                    "intelligence_base": int(
                        getattr(self.player, "intelligence_base", 0) or 0
                    ),
                }
            result["end_state"] = summary

        return result
