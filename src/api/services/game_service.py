import os
import json
import glob
import uuid
import contextlib
import io
import re
from typing import Dict, Any, Optional, List
from unittest.mock import patch
import src.universe as universe_module
import src.player as player_module
from src.interface import get_gold
from src.api.serializers.item_serializer import ItemSerializer
from src.api.serializers.npc_serializer import NPCSerializer
from src.api.serializers.object_serializer import ObjectSerializer
from src.api.serializers.event_serializer import EventSerializer
from src.api.serializers.inventory import (
    InventorySerializer,
    EquipmentSerializer,
    ItemDetailSerializer,
    ItemComparisonSerializer,
)
from src.api.serializers.combat import (
    CombatStateSerializer,
    CombatantSerializer,
    MoveSerializer,
    StateEffectSerializer,
)
from src.api.serializers.npc_ai import (
    NPCAIStateSerializer,
    DialogueStateSerializer,
    QuestStateSerializer,
    NPCBehaviorProfileSerializer,
)
from src.api.serializers.npc_availability import (
    NPCLocationSerializer,
    NPCAvailabilitySerializer,
    LocationNPCSerializer,
    NPCTimelineSerializer,
    NPCEventTriggerSerializer,
    NPCStatusSerializer,
)
from src.api.serializers.dialogue_context import (
    DialogueNodeSerializer,
    DialogueChoiceSerializer,
    DialogueConditionSerializer,
    DialogueEffectSerializer,
    ConversationHistorySerializer,
    DialogueContextSerializer,
    DialogueNode,
    DialogueChoice,
    DialogueCondition,
    DialogueEffect,
    ConversationHistory,
    DialogueContext,
)


class GameService:
    """Provides stateless interface to game logic for API layer.

    This service wraps the existing game engine (Universe, Player, etc.)
    and exposes clean methods for REST endpoints to call.
    """

    def __init__(self):
        """Initialize GameService.

        No longer holds stateful universe reference.
        """
        pass

    @staticmethod
    def _story(player):
        """Get the story-gate dict from player's universe, or empty dict."""
        u = getattr(player, 'universe', None)
        return getattr(u, 'story', {}) if u else {}

    @staticmethod
    def _game_tick(player):
        """Get the current game tick from player's universe, or 0."""
        u = getattr(player, 'universe', None)
        return getattr(u, 'game_tick', 0) if u else 0

    def _get_event_target_modules(self, event, include_animations: bool = True) -> List[str]:
        modules = [
            "functions",
            "player",
            "interface",
            "items",
            "objects",
            "events",
            "effects",
            "story.effects",
            "src.functions",
            "src.player",
            "src.interface",
            "src.items",
            "src.objects",
            "src.events",
            "src.story.effects",
        ]
        if include_animations:
            modules.extend(["animations", "src.animations"])
        if hasattr(event, "__module__"):
            modules.append(event.__module__)
        return modules

    def _build_event_patches(self, target_modules, mock_input, mock_cprint, mock_print_slow) -> List[Any]:
        patches = [
            patch("builtins.input", mock_input),
            patch("neotermcolor.cprint", mock_cprint),
            patch("time.sleep", return_value=None),
        ]

        for mod in set(target_modules):
            patches.extend([
                patch(f"{mod}.cprint", mock_cprint, create=True),
                patch(f"{mod}.print_slow", mock_print_slow, create=True),
                patch(f"{mod}.await_input", return_value=None, create=True),
                patch(f"{mod}.animate_to_main_screen", return_value=None, create=True),
                patch(f"{mod}.time.sleep", return_value=None, create=True),
                patch(f"{mod}.input", mock_input, create=True),
            ])

        return patches

    def _clean_event_output(self, output: str) -> str:
        if not output:
            return ""

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        lines = output.splitlines()
        filtered_lines = [line for line in lines if not line.strip().startswith("DEBUG:")]
        return ansi_escape.sub("", "\n".join(filtered_lines)).strip()

    def _store_pending_event(
        self,
        event,
        event_data: Dict[str, Any],
        session_data: Optional[Dict[str, Any]],
        tile: Any = None,
    ) -> Dict[str, Any]:
        event_id = getattr(event, "api_event_id", None)
        if not event_id:
            # Deduplicate by event name: if an event with the same name is already
            # pending, reuse its UUID rather than creating a second blocking entry.
            event_name = event_data.get("name") or getattr(event, "name", None)
            if event_name and session_data is not None:
                for existing_id, existing in session_data.get("pending_events", {}).items():
                    if existing.get("event_data", {}).get("name") == event_name:
                        event_id = existing_id
                        event.api_event_id = event_id
                        break
            if not event_id:
                event_id = str(uuid.uuid4())
                event.api_event_id = event_id

        event_data["event_id"] = event_id

        if session_data is not None:
            pending = session_data.setdefault("pending_events", {})
            payload = {
                "event": event,
                "event_data": event_data,
            }
            if tile is not None and hasattr(tile, "x") and hasattr(tile, "y"):
                payload["tile_x"] = tile.x
                payload["tile_y"] = tile.y
            pending[event_id] = payload

        return event_data

    def _queue_interactive_event(
        self,
        event,
        event_data: Dict[str, Any],
        session_data: Optional[Dict[str, Any]],
        tile: Any = None,
    ) -> Optional[Dict[str, Any]]:
        if event_data.get("needs_input") and not getattr(event, "completed", False):
            return self._store_pending_event(event, event_data, session_data, tile=tile)

        return None

    # ========================
    # World Navigation Methods
    # ========================

    def _calculate_exits(self, universe, tile: Any, x: int, y: int) -> Dict[str, Dict[str, int]]:
        """Calculate available exits from a tile by checking adjacent tiles.
        
        Args:
            universe: The Universe instance
            tile: The MapTile instance
            x: Current x coordinate
            y: Current y coordinate
            
        Returns:
            Dictionary mapping direction -> {x, y} coordinates
        """
        # Direction vectors and names
        directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0),
            "northeast": (1, -1),
            "northwest": (-1, -1),
            "southeast": (1, 1),
            "southwest": (-1, 1),
        }
        
        exits = {}
        
        # Get blocked exits from tile
        blocked = getattr(tile, "block_exit", [])
        
        # Check each direction
        blocked = getattr(tile, "block_exit", [])
        
        exits = {}
        for direction, (dx, dy) in directions.items():
            if direction in blocked:
                continue
                
            new_x, new_y = x + dx, y + dy
            adjacent_tile = universe.get_tile(new_x, new_y)
            
            if adjacent_tile:
                exits[direction] = {"x": new_x, "y": new_y}
        
        return exits

    def get_current_room(self, player: "player_module.Player", session_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get current room/tile data.

        Args:
            player: The Player instance
            session_data: Optional session data for applying tile modifications

        Returns:
            Dictionary with room data (position, description, exits, items, npcs, objects)
        """
        tile = player.universe.get_tile(player.location_x, player.location_y)
        if not tile:
            return {"error": "Invalid player position"}

        # Apply any stored tile modifications from session
        if session_data:
            self.apply_tile_modifications(tile, session_data)

        # Calculate exits dynamically by checking adjacent tiles
        exits_data = self._calculate_exits(player.universe, tile, player.location_x, player.location_y)

        # Record exploration
        self._record_exploration(player, tile)

        # Serialize items in room
        items_data = []
        if hasattr(tile, "items_here"):
            items_data = ItemSerializer.serialize_list(tile.items_here)

        # Serialize NPCs in room
        npcs_data = []
        if hasattr(tile, "npcs_here"):
            npcs_data = NPCSerializer.serialize_list(tile.npcs_here)

        # Serialize objects in room
        objects_data = []
        if hasattr(tile, "objects_here"):
            objects_data = ObjectSerializer.serialize_list(tile.objects_here)

        current_map = getattr(player, "map", None)
        map_metadata = current_map.get("metadata", {}) if isinstance(current_map, dict) else {}
        map_name = current_map.get("name") if isinstance(current_map, dict) else None

        raw_name = getattr(tile, "name", None) or type(tile).__name__
        # Humanize CamelCase class names (e.g. "EmptyCave" → "Empty Cave")
        import re as _re
        tile_name = _re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', raw_name)

        return {
            "x": player.location_x,
            "y": player.location_y,
            "name": tile_name,
            "map_name": map_name,
            "description": getattr(tile, "description", ""),
            "exits": exits_data,
            "items": items_data,
            "npcs": npcs_data,
            "objects": objects_data,
            "is_passable": getattr(tile, "is_passable", True),
            "bgm": map_metadata.get("bgm"),
        }

    def _record_exploration(self, player: "player_module.Player", tile: Any) -> None:
        """Record a tile as explored in the player's history.
        
        Args:
            player: The Player instance
            tile: The MapTile instance to record
        """
        if not hasattr(player, "explored_tiles"):
            player.explored_tiles = {}
        
        tile_key = f"{tile.x},{tile.y}"
        
        # We need to manually serialize to avoid circular dependencies if we used TileSerializer here
        # (Though TileSerializer is imported at top level, let's keep it simple)
        
        # Calculate exits for this tile
        exits_data = self._calculate_exits(player.universe, tile, tile.x, tile.y)
        
        # Serialize items
        items_data = []
        if hasattr(tile, "items_here"):
            items_data = ItemSerializer.serialize_list(tile.items_here)
            
        # Serialize NPCs
        npcs_data = []
        if hasattr(tile, "npcs_here"):
            npcs_data = NPCSerializer.serialize_list(tile.npcs_here)
            
        # Serialize objects
        objects_data = []
        if hasattr(tile, "objects_here"):
            objects_data = ObjectSerializer.serialize_list(tile.objects_here)

        player.explored_tiles[tile_key] = {
            "items": items_data,
            "npcs": npcs_data,
            "objects": objects_data,
            "exits": exits_data
        }

    def get_explored_tiles(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get the player's explored tiles history.
        
        Args:
            player: The Player instance
            
        Returns:
            Dictionary mapping "x,y" strings to tile data
        """
        if not hasattr(player, "explored_tiles"):
            player.explored_tiles = {}
        return player.explored_tiles

    def store_tile_modification(self, session_data: Dict[str, Any], x: int, y: int, modification_type: str, data: Any) -> None:
        """Store a tile modification in session data for persistence.
        
        Args:
            session_data: The session data dictionary
            x: Tile x coordinate
            y: Tile y coordinate  
            modification_type: Type of modification (e.g., 'block_exit', 'objects_removed')
            data: The modification data
        """
        if "tile_modifications" not in session_data:
            session_data["tile_modifications"] = {}
        
        tile_key = f"{x},{y}"
        if tile_key not in session_data["tile_modifications"]:
            session_data["tile_modifications"][tile_key] = {}
        
        session_data["tile_modifications"][tile_key][modification_type] = data

    def apply_tile_modifications(self, tile, session_data: Dict[str, Any]) -> None:
        """Apply stored modifications to a tile.
        
        Args:
            tile: The MapTile object to modify
            session_data: The session data dictionary containing modifications
        """
        if not session_data or "tile_modifications" not in session_data:
            return
        
        tile_key = f"{tile.x},{tile.y}"
        if tile_key not in session_data["tile_modifications"]:
            return
        
        modifications = session_data["tile_modifications"][tile_key]
        
        # Apply block_exit modifications
        if "block_exit" in modifications:
            tile.block_exit = modifications["block_exit"].copy()
        
        # Apply objects_removed modifications
        if "objects_removed" in modifications:
            removed_ids = modifications["objects_removed"]
            tile.objects_here = [obj for obj in tile.objects_here if id(obj) not in removed_ids]

    def move_player(
        self, player: "player_module.Player", direction: str, session_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Move player in specified direction.

        Args:
            player: The Player instance
            direction: Direction to move (north, south, east, west, northeast, northwest, southeast, southwest)
            session_data: Optional session dictionary for storing pending events

        Returns:
            Dictionary with result of movement
        """
        valid_directions = ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]
        direction_lower = direction.lower()
        if direction_lower not in valid_directions:
            return {"error": f"Invalid direction: {direction}"}

        tile = player.universe.get_tile(player.location_x, player.location_y)
        if not tile:
            return {"error": "Cannot move from this location"}

        # Calculate available exits
        available_exits = self._calculate_exits(player.universe, tile, player.location_x, player.location_y)
        
        if direction_lower not in available_exits:
            return {"error": f"Cannot go {direction_lower} from here"}

        # Get new coordinates from exits
        exit_data = available_exits[direction_lower]
        new_x, new_y = exit_data["x"], exit_data["y"]
        
        # Validate new tile exists (should always exist after exits calculation, but be safe)
        new_tile = player.universe.get_tile(new_x, new_y)
        if not new_tile:
            return {"error": f"Cannot move {direction_lower} - blocked or out of bounds"}

        # Check for blocking objects/obstacles (if tile has validation)
        if hasattr(new_tile, "is_passable") and not new_tile.is_passable:
            return {"error": f"Cannot move {direction_lower} - path is blocked"}

        # Update player position
        player.location_x = new_x
        player.location_y = new_y
        player.current_room = new_tile

        # Move any party members to the new room (mirrors game.py terminal behaviour)
        if len(getattr(player, "combat_list_allies", [])) > 1:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    player.recall_friends()
                except Exception:
                    pass

        # Record exploration of the new tile
        self._record_exploration(player, new_tile)

        # Trigger tile entry events with session data for pending event storage
        events_triggered = self.trigger_tile_events(player, new_tile, session_data)

        # Store tile modifications after entry events have processed to capture state changes
        if session_data is not None:
            current_block_exit = new_tile.block_exit.copy() if hasattr(new_tile, 'block_exit') else []
            self.store_tile_modification(
                session_data, 
                new_tile.x, 
                new_tile.y, 
                'block_exit', 
                current_block_exit
            )

        # Check for combat initiation
        from src.functions import check_for_combat
        combat_enemies = check_for_combat(player)
        
        combat_started = False
        combat_state = None
        
        if combat_enemies:
            # Initialize combat
            self._initialize_combat(player, combat_enemies, session_data=session_data)
            combat_started = True
            
            # Get initial combat state from the adapter
            if hasattr(player, '_combat_adapter'):
                adapter_state = player._combat_adapter.get_combat_state()
                combat_state = adapter_state.get('battle_state')
            else:
                # Fallback to direct serialization if adapter not available
                combat_state = CombatStateSerializer.serialize_combat_state(
                    player, combat_enemies, 
                    current_turn_index=getattr(player, "combat_turn_index", 0), 
                    round_number=getattr(player, "combat_round", 1)
                )

        return {
            "success": True,
            "new_position": {"x": new_x, "y": new_y},
            "events_triggered": events_triggered,
            "room": self.get_current_room(player),
            "combat_started": combat_started,
            "combat_state": combat_state
        }

    def trigger_tile_events(
        self, player: "player_module.Player", tile: Any, session_data: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Trigger events on tile entry.

        Args:
            player: The Player instance
            tile: The MapTile being entered
            session_data: Optional session dictionary for storing pending events

        Returns:
            List of triggered event data with captured output
        """
        if getattr(player, "in_combat", False):
            return []
            
        events_triggered = []
        
        if not hasattr(tile, "events_here"):
            return events_triggered

        for event in list(tile.events_here):
            # Check if event requires input using EventSerializer
            event_data = EventSerializer.serialize_with_input(event)

            # If event is already in interactive state, ensure it's in session and skip processing
            event.player = player
            if hasattr(player, "current_room"):
                event.tile = player.current_room
            queued_event = self._queue_interactive_event(
                event,
                event_data,
                session_data,
                tile=tile,
            )
            if queued_event:
                events_triggered.append(queued_event)
                continue
            
            # For non-input events, process normally
            # Try to trigger the event and capture output
            if hasattr(event, "check_conditions"):
                f = io.StringIO()
                try:
                    # Patch functions to capture output without blocking
                    def mock_cprint(text, *args, **kwargs):
                        f.write(str(text) + '\n')
                    
                    def mock_print_slow(text, speed="slow"):
                        f.write(str(text) + '\n')
                    
                    def mock_input(prompt=""):
                        if prompt:
                            f.write(str(prompt) + '\n')
                        return "1"  # Default to first option
                        
                    target_modules = self._get_event_target_modules(event, include_animations=True)
                    patches = self._build_event_patches(
                        target_modules,
                        mock_input,
                        mock_cprint,
                        mock_print_slow,
                    )
                    
                    # Capture stdout/stderr and patch blocking functions
                    with contextlib.redirect_stdout(f), \
                         contextlib.redirect_stderr(f), \
                         contextlib.ExitStack() as stack:
                        
                        for p in patches:
                            try:
                                stack.enter_context(p)
                            except (AttributeError, ImportError, TypeError, ValueError):
                                pass 
                        
                        # Ensure event has current player and room references
                        event.player = player
                        if hasattr(player, "current_room"):
                            event.tile = player.current_room

                        event.check_conditions()
                        
                        # Refresh event data after processing
                        new_data = EventSerializer.serialize_with_input(event)
                        event_data.update(new_data)

                        # If event dynamically requested input during processing, 
                        # handle it as a pending event.
                        needs_input = getattr(event, "needs_input", False)
                        completed = getattr(event, "completed", False)
                        if needs_input and not completed:
                            event_data = self._store_pending_event(
                                event,
                                event_data,
                                session_data,
                                tile=tile,
                            )
                        
                except Exception as e:
                    # Log error but continue
                    event_data["error"] = str(e)
                    print(f"[ERROR] Event processing: {e}")
                
                # Capture and clean output
                clean_output = self._clean_event_output(f.getvalue())
                if clean_output:
                    event_data["output_text"] = clean_output
            
            events_triggered.append(event_data)

        return events_triggered

    def process_event_input(
        self,
        player: "player_module.Player",
        event_id: str,
        user_input: str,
        session_data: Dict
    ) -> Dict[str, Any]:
        """Process a pending event with user input.

        Args:
            player: The Player instance
            event_id: The UUID of the pending event
            user_input: The user's input (sanitized by caller)
            session_data: Session dictionary containing pending events

        Returns:
            Dictionary with event result and output
        """
        import contextlib
        import io
        import re
        from unittest.mock import patch
        from src.api.serializers.event_serializer import EventSerializer

        # Validate event exists
        if "pending_events" not in session_data:
            return {"success": False, "error": "No pending events in session"}
        
        if event_id not in session_data["pending_events"]:
            return {"success": False, "error": f"Event {event_id} not found"}
        
        pending = session_data["pending_events"][event_id]
        event = pending["event"]
        
        # Process the event with user input
        f = io.StringIO()
        result = {"success": True, "event_id": event_id}
        
        try:
            # Patch functions to capture output without blocking
            def mock_cprint(text, *args, **kwargs):
                f.write(str(text) + '\n')
            
            def mock_print_slow(text, speed="slow"):
                f.write(str(text) + '\n')
                
            def mock_input(prompt=""):
                return user_input

            # Build robust patch list across multiple core modules
            target_modules = self._get_event_target_modules(event, include_animations=False)
            patches = self._build_event_patches(
                target_modules,
                mock_input,
                mock_cprint,
                mock_print_slow,
            )

            # Process the event with captured output
            with contextlib.redirect_stdout(f), \
                 contextlib.redirect_stderr(f), \
                 contextlib.ExitStack() as stack:
                
                for p in patches:
                    try:
                        stack.enter_context(p)
                    except (AttributeError, ImportError, TypeError, ValueError):
                        pass

                # Ensure event has current player and room references
                event.player = player
                if hasattr(player, "current_room"):
                    event.tile = player.current_room

                # Call process() or check_conditions()
                if hasattr(event, 'process'):
                    event.process(user_input=user_input)
                elif hasattr(event, 'check_conditions'):
                    event.check_conditions()

                # Check outcome
                if getattr(event, "completed", False):
                    # Event finished, remove from pending safely
                    if "pending_events" in session_data:
                        session_data["pending_events"].pop(event_id, None)
                else:
                    # Event still needs more input, update metadata
                    result["needs_input"] = True
                    result["event"] = EventSerializer.serialize_with_input(event)
                    # Preserve ID
                    result["event"]["event_id"] = event_id
                    # Update session data
                    if "pending_events" in session_data and event_id in session_data["pending_events"]:
                        session_data["pending_events"][event_id]["event_data"] = result["event"]
                    
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            print(f"[ERROR] Event input processing: {e}")
        
        # Capture and clean output
        clean_output = self._clean_event_output(f.getvalue())
        if clean_output:
            result["output_text"] = clean_output
        
        # Check if event still needs input (persistent events)
        updated_event_data = EventSerializer.serialize_with_input(event)
        
        if updated_event_data.get("needs_input") and not getattr(event, "completed", False):
            # This event has transitioned to a new stage (still needs_input but not completed).
            # Assign a NEW UUID so the frontend does not treat the new stage as the
            # same interaction that was "recently processed" and silently skip it.
            # Without a fresh ID the frontend's deduplication would suppress stage 2+,
            # leaving pending_events populated and blocking all combat moves.
            old_event_id = event_id
            new_event_id = str(uuid.uuid4())
            event.api_event_id = new_event_id
            updated_event_data["event_id"] = new_event_id
            # Move the session entry from the old id to the new id
            if "pending_events" in session_data:
                session_data["pending_events"].pop(old_event_id, None)
                session_data["pending_events"][new_event_id] = {
                    "event": event,
                    "event_data": updated_event_data,
                }
            result["event"] = updated_event_data
            result["needs_input"] = True
        else:
            # Remove from pending events safely
            if "pending_events" in session_data:
                session_data["pending_events"].pop(event_id, None)
            result["needs_input"] = False

        # Trigger tile events after event processing to handle state changes (e.g., chest looted)
        # ONLY if the current event is completed, to allow subsequent events on the same tile to fire
        if not result.get("needs_input", False):
            tile = player.universe.get_tile(player.location_x, player.location_y)
            if tile:
                more_events = self.trigger_tile_events(player, tile, session_data)
                if more_events:
                    if "events_triggered" not in result:
                        result["events_triggered"] = []
                    for new_event in more_events:
                        # Avoid duplicates
                        if not any(e.get('name') == new_event.get('name') for e in result["events_triggered"]):
                            result["events_triggered"].append(new_event)

        # If we are already in combat, do not reinitialize combat from check_for_combat.
        # This preserves reinforcement additions made during combat event processing.
        if getattr(player, "in_combat", False):
            result["combat_started"] = True
            if hasattr(player, "_combat_adapter"):
                adapter = player._combat_adapter
                # If the event is fully resolved, refresh available_options so the frontend
                # gets move options targeting the current (post-reinforcement) enemy list.
                # Without this, the adapter holds stale viable_targets from before the event
                # fired, causing 400s when the frontend auto-selects a dead enemy's ID.
                if not result.get("needs_input", False):
                    adapter.awaiting_input = True
                    adapter.input_type = "move_selection"
                    adapter.available_options = adapter._get_available_moves()
                    adapter.pending_move_index = None
                adapter_state = adapter.get_combat_state()
                result["combat_state"] = adapter_state.get("battle_state") or adapter_state
            return result
        
        # Check for combat after event processing (in case event spawned enemies)
        # ONLY if the event doesn't still need input (wait for final resolution before continuing combat flow)
        from src.functions import check_for_combat
        combat_enemies = check_for_combat(player)
        
        if combat_enemies and not result.get("needs_input", False):
            # Initialize combat
            self._initialize_combat(player, combat_enemies, session_data=session_data)
            result["combat_started"] = True
            
            # Get initial combat state
            if hasattr(player, '_combat_adapter'):
                adapter_state = player._combat_adapter.get_combat_state()
                # If we resumed a move, the adapter state already contains the full battle_state
                result["combat_state"] = adapter_state.get('battle_state') or adapter_state
            else:
                # Fallback to direct serialization (CombatStateSerializer already imported at module level)
                result["combat_state"] = CombatStateSerializer.serialize_combat_state(
                    player, combat_enemies,
                    current_turn_index=getattr(player, "combat_turn_index", 0),
                    round_number=getattr(player, "combat_round", 1)
                )
        elif combat_enemies:
            # Combat is present but we are paused for narrative
            result["combat_started"] = True
        else:
            result["combat_started"] = False
        
        return result

    def get_tile(self, player: "player_module.Player", x: int, y: int) -> Dict[str, Any]:
        """Get tile data at specific coordinates with full serialization.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Dictionary with tile data including NPCs, items, and objects
        """
        tile = player.universe.get_tile(x, y)
        if not tile:
            return {"error": "Tile not found"}

        # Use serializers for consistent formatting
        items_data = ItemSerializer.serialize_list(getattr(tile, "items_here", []))
        npcs_data = NPCSerializer.serialize_list(getattr(tile, "npcs_here", []))
        objects_data = ObjectSerializer.serialize_list(getattr(tile, "objects_here", []))
        events_data = EventSerializer.serialize_list(getattr(tile, "events_here", []))

        # Get exits/connections
        exits_data = {}
        if hasattr(tile, "exits"):
            for direction, (ex, ey) in tile.exits.items():
                exits_data[direction] = {"x": ex, "y": ey}

        return {
            "x": x,
            "y": y,
            "name": getattr(tile, "name", "Unknown"),
            "description": getattr(tile, "description", ""),
            "items": items_data,
            "npcs": npcs_data,
            "objects": objects_data,
            "events": events_data,
            "exits": exits_data,
            "is_passable": getattr(tile, "is_passable", True),
        }

    def search(self, player: "player_module.Player") -> Dict[str, Any]:
        """Search the current room for hidden entities.

        Args:
            player: The Player instance

        Returns:
            Dictionary with search results
        """
        import random
        
        tile = player.universe.get_tile(player.location_x, player.location_y)
        if not tile:
            return {"success": False, "message": "Invalid location"}

        # Calculate search ability
        # Formula: (Finesse * 2 + Intelligence * 3 + Faith) * random(0.5, 1.5)
        finesse = getattr(player, "finesse", 10)
        intelligence = getattr(player, "intelligence", 10)
        faith = getattr(player, "faith", 10)
        
        search_ability = int(((finesse * 2) + (intelligence * 3) + faith) * random.uniform(0.5, 1.5))
        
        found_items = []
        messages = []
        something_found = False

        # Check NPCs
        if hasattr(tile, "npcs_here"):
            for npc in tile.npcs_here:
                if getattr(npc, "hidden", False):
                    hide_factor = getattr(npc, "hide_factor", 0)
                    if search_ability > hide_factor:
                        npc.hidden = False
                        discovery_msg = getattr(npc, "discovery_message", f"a hidden {getattr(npc, 'name', 'NPC')}")
                        messages.append(f"{player.name} uncovered {discovery_msg}")
                        something_found = True
                        found_items.append({"type": "npc", "name": getattr(npc, "name", "Unknown"), "id": str(id(npc))})

        # Check Items
        if hasattr(tile, "items_here"):
            for item in tile.items_here:
                if getattr(item, "hidden", False):
                    hide_factor = getattr(item, "hide_factor", 0)
                    if search_ability > hide_factor:
                        item.hidden = False
                        discovery_msg = getattr(item, "discovery_message", f"a hidden {getattr(item, 'name', 'Item')}")
                        messages.append(f"{player.name} found {discovery_msg}")
                        something_found = True
                        found_items.append({"type": "item", "name": getattr(item, "name", "Unknown"), "id": str(id(item))})

        # Check Objects
        if hasattr(tile, "objects_here"):
            for obj in tile.objects_here:
                if getattr(obj, "hidden", False):
                    hide_factor = getattr(obj, "hide_factor", 0)
                    if search_ability > hide_factor:
                        obj.hidden = False
                        discovery_msg = getattr(obj, "discovery_message", f"a hidden {getattr(obj, 'name', 'Object')}")
                        messages.append(f"{player.name} found {discovery_msg}")
                        something_found = True
                        found_items.append({"type": "object", "name": getattr(obj, "name", "Unknown"), "id": str(id(obj))})

        if not something_found:
            messages.append(f"{player.name} searches around the area... but couldn't find anything of interest.")
        else:
            messages.insert(0, f"{player.name} searches around the area...")

        return {
            "success": True,
            "messages": messages,
            "found": found_items,
            "room": self.get_current_room(player)  # Return updated room data
        }

    # ========================
    # Interaction Methods
    # ========================

    def interact_with_target(
        self, 
        player: "player_module.Player", 
        target_id: str, 
        action: str, 
        quantity: Optional[int] = None,
        session_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Interact with an object or NPC.

        Args:
            player: The Player instance
            target_id: ID of the target object/NPC
            action: The action keyword to execute
            quantity: Optional quantity for stacked items
            session_data: Optional session dictionary for storing pending events

        Returns:
            Dictionary with interaction result and output text
        """
        import contextlib
        import io
        import src.functions as functions
        from unittest.mock import patch
        import inspect
        import re
        import uuid
        from src.api.serializers.event_serializer import EventSerializer

        # Find target
        tile = player.universe.get_tile(player.location_x, player.location_y)
        # Ensure player knows where they are for interactions that modify the room (like taking items)
        player.current_room = tile
        target = None
        
        # Check NPCs
        if hasattr(tile, "npcs_here"):
            for npc in tile.npcs_here:
                if str(id(npc)) == target_id:
                    target = npc
                    break
        
        # Check Objects
        if not target and hasattr(tile, "objects_here"):
            for obj in tile.objects_here:
                if str(id(obj)) == target_id:
                    target = obj
                    break

        # Check Items
        if not target and hasattr(tile, "items_here"):
            for item in tile.items_here:
                if str(id(item)) == target_id:
                    target = item
                    break
                    
        # Try to find target in items inside open containers
        if not target:
            from src.objects import Container
            for obj in tile.objects_here:
                is_container = type(obj).__name__ == "Container" or isinstance(obj, Container)
                if is_container and getattr(obj, "state", "") == "opened" and hasattr(obj, "inventory"):
                    for item in obj.inventory:
                        if str(id(item)) == target_id:
                            target = item
                            target._parent_container = obj
                            break
                if target: break

        if not target:
            return {"success": False, "message": "Target not found."}

        is_valid = False
        if hasattr(target, "keywords") and action in target.keywords:
            is_valid = True
        elif hasattr(target, action):
            # Allow calling method if it exists, even if not in keywords (fallback)
            is_valid = True
            
        if not is_valid:
            return {"success": False, "message": f"Cannot {action} this target."}

        # Execute action and capture output
        f = io.StringIO()
        events_triggered = []
        try:
            # We need to patch await_input to prevent blocking, and time.sleep to prevent delays
            # Also patch cprint and print_slow to capture colored output
            def mock_cprint(text, *args, **kwargs):
                f.write(str(text) + '\n')
            
            def mock_print_slow(text, speed="slow"):
                # Just write the text directly without character-by-character delays
                f.write(str(text) + '\n')

            def mock_input(prompt=""):
                # Return 'x' to exit any terminal-based interactive loops (like loot menus)
                return "x"
            
            # Patch at multiple levels since different modules import differently
            with contextlib.redirect_stdout(f), \
                 contextlib.redirect_stderr(f), \
                 patch('builtins.input', mock_input), \
                 patch('functions.await_input', return_value=None), \
                 patch('functions.print_slow', mock_print_slow), \
                 patch('time.sleep', return_value=None), \
                 patch('neotermcolor.cprint', mock_cprint), \
                 patch('src.functions.await_input', return_value=None), \
                 patch('src.functions.print_slow', mock_print_slow), \
                 patch('src.items.cprint', mock_cprint), \
                 patch('items.cprint', mock_cprint):
                
                try:
                    from objects import Container
                except ImportError:
                    from src.objects import Container
                try:
                    from items import Item
                except ImportError:
                    from src.items import Item
                try:
                    from interface import transfer_item
                except ImportError:
                    from src.interface import transfer_item
                try:
                    from events import LootEvent
                except ImportError:
                    from src.events import LootEvent
                
                is_container = type(target).__name__ == "Container" or isinstance(target, Container)
                # More robust item check that handles subclasses and module mismatches
                item_types = ["Item", "Weapon", "Armor", "Consumable", "Gold", "Key", "Tool", "Usable"]
                is_item = type(target).__name__ in item_types or isinstance(target, Item) or hasattr(target, "_parent_container")
                
                if is_container and action in ["loot", "check"]:
                    target.open()
                    # Create a LootEvent and store it
                    loot_event = LootEvent(f"Looting {target.name}", player, tile, target)
                    event_data = EventSerializer.serialize_with_input(loot_event)
                    
                    if session_data is not None:
                        event_id = str(uuid.uuid4())
                        event_data["event_id"] = event_id
                        
                        if "pending_events" not in session_data:
                            session_data["pending_events"] = {}
                        session_data["pending_events"][event_id] = {
                            "event": loot_event,
                            "tile_x": tile.x,
                            "tile_y": tile.y,
                            "event_data": event_data
                        }
                    
                    events_triggered.append(event_data)
                elif is_item and action in ["take", "equip"] and hasattr(target, "_parent_container"):
                    # Use transfer_item for items in containers
                    qty_to_take = quantity if quantity is not None else getattr(target, 'count', 1)
                    transfer_item(target._parent_container, player, target, qty_to_take)
                    if hasattr(target._parent_container, "refresh_description"):
                        target._parent_container.refresh_description()
                    
                    if action == "take":
                        print(f"{player.name} takes {target.name}.")
                    else:
                        # Proceed with equipment logic
                        target.equip(player)
                else:
                    method = getattr(target, action)
                    # Check signature to see if we need to pass player
                    sig = inspect.signature(method)
                    # Get parameter names excluding 'self'
                    param_names = [p for p in sig.parameters.keys() if p != 'self']
                    
                    # If there are parameters beyond 'self', pass player
                    if len(param_names) > 0:
                        # If the method accepts quantity, pass it
                        if 'quantity' in param_names:
                            method(player, quantity=quantity)
                        else:
                            method(player)
                    else:
                        method()
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "message": f"Error executing action: {str(e)}"}

        output = f.getvalue()
        
        # Clean up output (remove ANSI codes)
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_output = ansi_escape.sub('', output)
        
        # Remove excessive newlines and clean up whitespace
        clean_output = re.sub(r'\n\s*\n', '\n', clean_output)  # Replace multiple newlines with single
        clean_output = clean_output.strip()
        
        # Provide fallback message if no output was captured
        if not clean_output:
            if action == 'take_all':
                clean_output = "Jean collects all of the available items."
            else:
                clean_output = f"Jean successfully completes the '{action}' action."

        # Trigger tile events after action execution to handle state changes (e.g., chest looted or wall opened)
        more_events = self.trigger_tile_events(player, tile, session_data)
        if more_events:
            for new_event in more_events:
                # Avoid duplicates if they somehow got in
                if not any(e.get('name') == new_event.get('name') for e in events_triggered):
                    events_triggered.append(new_event)

        # Store tile modifications AFTER all events have processed to capture state changes
        if session_data is not None:
            # 1. Store blocked exits
            current_block_exit = tile.block_exit.copy() if hasattr(tile, 'block_exit') else []
            self.store_tile_modification(
                session_data, 
                tile.x, 
                tile.y, 
                'block_exit', 
                current_block_exit
            )
            
            # 2. Store removed objects (using object names as stable identifiers)
            if hasattr(tile, 'objects_here'):
                # We need to consider what was there originally vs now
                # This is a bit complex in a stateless environment, but for now 
                # we'll trust that the event removed what it needed to.
                pass

        # Check for combat initiation
        from src.functions import check_for_combat
        combat_enemies = check_for_combat(player)
        
        combat_started = False
        combat_state = None
        
        if combat_enemies:
            # Initialize combat
            self._initialize_combat(player, combat_enemies, session_data=session_data)
            combat_started = True
            
            # Get initial combat state from the adapter
            if hasattr(player, '_combat_adapter'):
                adapter_state = player._combat_adapter.get_combat_state()
                combat_state = adapter_state.get('battle_state')
            else:
                # Fallback to direct serialization if adapter not available
                combat_state = CombatStateSerializer.serialize_combat_state(
                    player, combat_enemies, 
                    current_turn_index=getattr(player, "combat_turn_index", 0), 
                    round_number=getattr(player, "combat_round", 1)
                )

        return {
            "success": True, 
            "message": clean_output,
            "target_name": getattr(target, "name", "Unknown"),
            "action": action,
            "events_triggered": events_triggered,
            "combat_started": combat_started,
            "combat_state": combat_state
        }

    # ========================
    # Inventory Methods
    # ========================

    def get_inventory(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get player inventory.

        Args:
            player: The Player instance

        Returns:
            Dictionary with full inventory data using InventorySerializer
        """
        return InventorySerializer.serialize(player)

    def take_item(
        self, player: "player_module.Player", item_id: str
    ) -> Dict[str, Any]:
        """Take an item from the ground.

        Args:
            player: The Player instance
            item_id: ID of item to take

        Returns:
            Result of action
        """
        # TODO: Implement item pickup logic
        return {"success": True, "item_id": item_id, "message": "Item taken"}

    def drop_item(
        self, player: "player_module.Player", item_id: str
    ) -> Dict[str, Any]:
        """Drop an item from inventory.

        Args:
            player: The Player instance
            item_id: ID of item to drop

        Returns:
            Result of action
        """
        # TODO: Implement item drop logic
        return {"success": True, "item_id": item_id, "message": "Item dropped"}

    def examine_item(
        self, player: "player_module.Player", item_id: str
    ) -> Dict[str, Any]:
        """Examine an item in inventory.

        Args:
            player: The Player instance
            item_id: ID of item to examine

        Returns:
            Dictionary with item details
        """
        # TODO: Implement item examination logic
        return {"item_id": item_id, "message": "Unknown item"}

    # ========================
    # Equipment Methods
    # ========================

    def get_equipment(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get player equipment status.

        Args:
            player: The Player instance

        Returns:
            Dictionary with equipped items and stats using EquipmentSerializer
        """
        return EquipmentSerializer.serialize(player)

    def equip_item(
        self, player: "player_module.Player", item_index: int
    ) -> Dict[str, Any]:
        """Equip an item from inventory by index.

        Args:
            player: The Player instance
            item_index: Index of item in inventory to equip

        Returns:
            Result of action with equipment changes
        """
        inventory = getattr(player, "inventory", [])
        
        # Validate index
        if not isinstance(item_index, int) or item_index < 0 or item_index >= len(inventory):
            return {"success": False, "error": f"Invalid item index: {item_index}"}
        
        item = inventory[item_index]
        
        # Check if item can be equipped
        if not hasattr(item, "isequipped"):
            return {"success": False, "error": f"Item '{getattr(item, 'name', 'Unknown')}' cannot be equipped"}
        
        try:
            # Mark as equipped
            item.isequipped = True
            
            # Update player's equipment based on item type
            maintype = getattr(item, "maintype", None)
            
            if maintype == "Weapon":
                player.eq_weapon = item
            elif maintype == "Shield":
                player.shield = item
            elif maintype in ["Armor", "Helm", "Boots", "Gloves"]:
                # Map maintype to common player slot names
                slot_map = {
                    "Armor": "body",
                    "Helm": "head",
                    "Boots": "feet",
                    "Gloves": "hands"
                }
                slot_name = slot_map.get(maintype)
                
                # Check for item-defined slot name as well
                if hasattr(item, "type_s"):
                    slot_name = item.type_s.lower()
                elif hasattr(item, "subtype") and not slot_name:
                    slot_name = item.subtype.lower()
                
                if slot_name and hasattr(player, slot_name):
                    setattr(player, slot_name, item)
                elif slot_name == "armor" and hasattr(player, "body"):
                    player.body = item

            
            # Refresh stat bonuses after equipment change
            from src import functions
            functions.refresh_stat_bonuses(player)
            
            # Extract item type for response (use maintype, type_s, or subtype in order of preference)
            item_type = maintype or getattr(item, "type_s", None) or getattr(item, "subtype", "Unknown")
            
            return {
                "success": True,
                "item_name": getattr(item, "name", "Unknown"),
                "item_type": item_type,
                "equipment": EquipmentSerializer.serialize(player),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def unequip_item(self, player: "player_module.Player", slot: str) -> Dict[str, Any]:
        """Unequip item from slot.

        Args:
            player: The Player instance
            slot: Equipment slot name (weapon, shield, head, body, etc.)

        Returns:
            Result of action
        """
        # Map slot names to player attributes
        slot_mapping = {
            "weapon": "eq_weapon",
            "shield": "shield",
            "head": "head",
            "body": "body",
            "legs": "legs",
            "feet": "feet",
            "hands": "hands",
            "accessory_1": "accessory_1",
            "accessory_2": "accessory_2",
        }
        
        if slot not in slot_mapping:
            return {"success": False, "error": f"Unknown slot: {slot}"}
        
        attr_name = slot_mapping[slot]
        item = getattr(player, attr_name, None)
        
        if not item:
            return {"success": False, "error": f"No item equipped in slot: {slot}"}
        
        try:
            # Mark as unequipped
            if hasattr(item, "isequipped"):
                item.isequipped = False
            
            # Clear the slot
            if slot == "weapon":
                # Equip fists if no weapon
                if hasattr(player, "fists"):
                    player.eq_weapon = player.fists
            else:
                setattr(player, attr_name, None)
            
            # Refresh stat bonuses after equipment change
            from src import functions
            functions.refresh_stat_bonuses(player)
            
            return {
                "success": True,
                "item_name": getattr(item, "name", "Unknown"),
                "slot": slot,
                "equipment": EquipmentSerializer.serialize(player),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================
    # Combat Methods
    # ========================

    # ========================
    # ========================
    # Combat Methods
    # ========================

    def trigger_combat_events(
        self, player: "player_module.Player", session_data: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Trigger combat-specific events.

        Args:
            player: The Player instance
            session_data: Optional session data for storing pending events

        Returns:
            List of triggered events
        """
        tile = getattr(player, "current_room", None)
        if tile is None and hasattr(player, "universe"):
            tile = player.universe.get_tile(player.location_x, player.location_y)

        combat_events = list(getattr(player, "combat_events", []) or [])
        tile_events = list(getattr(tile, "events_here", []) or []) if tile else []

        if not combat_events and not tile_events:
            return []

        events_triggered = []
        from src.api.serializers.event_serializer import EventSerializer

        for event in list(combat_events + tile_events):
            if not getattr(event, "combat_effect", False):
                continue
            # Check if event requires input using EventSerializer
            event_data = EventSerializer.serialize_with_input(event)
            
            # If event is already in interactive state, ensure it's in session and skip processing
            if event_data.get("needs_input") and not getattr(event, "completed", False):
                # Keep references aligned to the current room for combat-driven events.
                event.player = player
                if hasattr(player, "current_room"):
                    event.tile = player.current_room

                queued_event = self._queue_interactive_event(
                    event,
                    event_data,
                    session_data,
                )
                if queued_event:
                    events_triggered.append(queued_event)
                    continue
            
            # Ensure event has current player and room references
            # (Crucial when loading from session where events might hold stale refs)
            event.player = player
            if tile is not None:
                event.tile = tile

            # For non-input events, process normally
            # Try to trigger the event and capture output
            method_name = "check_combat_conditions" if hasattr(event, "check_combat_conditions") else "check_conditions"
            
            if hasattr(event, method_name):
                f = io.StringIO()
                try:
                    # Patch functions to capture output without blocking
                    def mock_cprint(text, *args, **kwargs):
                        f.write(str(text) + '\n')
                    
                    def mock_print_slow(text, speed="slow"):
                        f.write(str(text) + '\n')
                        
                    def mock_input(prompt=""):
                        if prompt:
                            f.write(str(prompt) + '\n')
                        return "1"

                    target_modules = self._get_event_target_modules(event, include_animations=True)
                    patches = self._build_event_patches(
                        target_modules,
                        mock_input,
                        mock_cprint,
                        mock_print_slow,
                    )
                    
                    # Capture stdout/stderr and patch blocking functions
                    with contextlib.redirect_stdout(f), \
                         contextlib.redirect_stderr(f), \
                         contextlib.ExitStack() as stack:
                        
                        for p in patches:
                            try:
                                stack.enter_context(p)
                            except (AttributeError, ImportError, TypeError, ValueError, Exception):
                                pass 
                        
                        # Call the appropriate check method
                        getattr(event, method_name)()
                        
                        # Refresh event data after processing
                        new_data = EventSerializer.serialize_with_input(event)
                        event_data.update(new_data)

                        # If event dynamically requested input during processing, 
                        # handle it as a pending event.
                        needs_input = getattr(event, "needs_input", False)
                        completed = getattr(event, "completed", False)
                        if needs_input and not completed:
                            event_data = self._store_pending_event(
                                event,
                                event_data,
                                session_data,
                            )
                        
                except Exception as e:
                    event_data["error"] = str(e)
                
                # Capture and clean output
                clean_output = self._clean_event_output(f.getvalue())
                triggered = False
                if clean_output:
                    event_data["output_text"] = clean_output
                    triggered = True

                # Mark as triggered if input required
                if getattr(event, "needs_input", False):
                    triggered = True
                
                # Only add to results if it actually did something
                if triggered:
                    events_triggered.append(event_data)

        return events_triggered

    # ========================
    # Player Status Methods
    # ========================

    def start_combat(self, player: "player_module.Player", enemy_id: str, session_id: str = None) -> Dict[str, Any]:
        """Start combat with a specific enemy (e.g. from dialogue/interaction)."""
        # Find enemy in current room
        enemy = None
        
        # 1. Try universe tile
        if hasattr(player, 'universe') and player.universe:
            tile = player.universe.get_tile(player.location_x, player.location_y)
            if hasattr(tile, "npcs_here"):
                for npc in tile.npcs_here:
                    if str(id(npc)) == enemy_id:
                        enemy = npc
                        break
        
        # 2. Try player.current_room (fallback for tests/specific events)
        if not enemy and hasattr(player, "current_room") and player.current_room:
            if hasattr(player.current_room, "npcs_here"):
                for npc in player.current_room.npcs_here:
                    if str(id(npc)) == enemy_id:
                        enemy = npc
                        break
        
        if not enemy:
            return {"error": "Enemy not found"}

        result = self._initialize_combat(player, [enemy], session_id=session_id)

        # Attach API-contract fields so routes don't need to reach into player internals
        import uuid as _uuid
        combatants = []
        for ally in getattr(player, "combat_list_allies", []):
            combatants.append({
                "id": "player" if ally is player else f"ally_{id(ally)}",
                "name": getattr(ally, "name", "Ally"),
                "is_player": ally is player,
                "is_ally": True,
            })
        for e in getattr(player, "combat_list", []):
            combatants.append({
                "id": f"enemy_{id(e)}",
                "name": getattr(e, "name", "Enemy"),
                "is_player": False,
                "is_ally": False,
            })
        result["combat_id"] = str(_uuid.uuid4())
        result["combatants"] = combatants
        result["turn_order"] = [c["id"] for c in combatants]
        return result

    def execute_move(self, player: "player_module.Player", move_type: str, move_id: str, target_id: str = None, direction: str = None, session_id: str = None, session_data: Dict = None) -> Dict[str, Any]:
        """Execute a combat move."""

        # Check if player is in combat
        if not player.in_combat:
            return {"success": False, "error": "Not in combat"}
        
        # Check for blocking pending events - events that need input should block combat moves
        # This prevents players from acting before event dialogs appear (e.g., rumbler announcement)
        if session_data and session_data.get("pending_events"):
            # Only block if there are events that actually need input (not stale/completed events)
            blocking_events = [
                e for e in session_data["pending_events"].values()
                if e.get("event_data", {}).get("needs_input") and not e.get("event_data", {}).get("completed")
            ]
            if blocking_events:
                return {
                    "success": False,
                    "error": "Event pending",
                    "message": "Please resolve the current event before taking combat actions.",
                    "pending_events_count": len(blocking_events)
                }
            # If no blocking events, clean up stale pending_events
            else:
                session_data["pending_events"] = {}
            
        # Ensure adapter exists
        if not hasattr(player, "_combat_adapter"):
            from src.api.combat_adapter import ApiCombatAdapter
            # Create a wrapper for trigger_combat_events that matches the expected signature
            def event_callback(p):
                return self.trigger_combat_events(p, session_data=session_data)
                
            player._combat_adapter = ApiCombatAdapter(player, session_id=session_id, on_event_callback=event_callback)
        else:
            # Update existing adapter's callback to ensure it has access to current session_data
            def event_callback(p):
                return self.trigger_combat_events(p, session_data=session_data)
            
            player._combat_adapter.on_event_callback = event_callback
            if session_id:
                player._combat_adapter.session_id = session_id
            # Note: We do NOT re-initialize combat here - that would reset the adapter state
            # including input_type and pending_move_index, breaking multi-step moves like
            # select move -> select target
        
        adapter = player._combat_adapter
        # Update session_id if it changed or was missing
        if session_id:
            adapter.session_id = session_id

        # Check if adapter is ready for input (unless cancelling, which should always be allowed)
        if not adapter.awaiting_input and move_type != "cancel":
            return {
                "error": "Not awaiting input",
                "details": f"awaiting_input={adapter.awaiting_input}, input_type={adapter.input_type}"
            }
            
        # Handle different move types
        if move_type == "move":
            # Player is selecting a move
            # Try to handle as index first (preferred)
            move_index = None
            try:
                idx = int(move_id)
                # Verify index is valid
                if 0 <= idx < len(adapter.available_options):
                    move_index = idx
            except (ValueError, TypeError):
                pass
            
            # If not index, try to find by name match (fallback)
            if move_index is None:
                # We need to check against available options in the adapter
                for i, option in enumerate(adapter.available_options):
                    # Option can be dict or object
                    opt_name = option.get("name") if isinstance(option, dict) else getattr(option, "name", "")
                    if opt_name == move_id:
                        # Use the 'index' field from the option, not the loop index
                        move_index = option.get("index", i) if isinstance(option, dict) else getattr(option, "index", i)
                        break
            
            if move_index is None:
                return {"error": f"Invalid move ID or name: {move_id}"}
            
            command = {
                "type": "select_move",
                "move_index": move_index
            }
            
            result = adapter.process_command(command)
            
            # Auto-handle targeting if we have a target_id and the move requires it
            if not result.get("error") and result.get("battle_state", {}).get("input_type") == "target_selection" and target_id:
                # Only auto-send target if it's likely a valid ID
                if target_id and target_id != 'player':
                    target_command = {"type": "select_target", "target_id": target_id}
                    result = adapter.process_command(target_command)
                
            return result

        elif move_type == "target":
            if not isinstance(target_id, str) or not target_id:
                return {"error": "Invalid target"}
            command = {"type": "select_target", "target_id": target_id}
            return adapter.process_command(command)
        
        elif move_type == "direction":
            command = {"type": "select_direction", "direction": direction}
            return adapter.process_command(command)
        
        elif move_type == "number":
            try:
                value = int(target_id) if target_id else int(move_id)
            except (ValueError, TypeError):
                return {"error": "Invalid numeric value"}
            
            command = {"type": "select_number", "value": value}
            return adapter.process_command(command)
        
        elif move_type == "attack":
            return self.execute_move(player, "move", "Attack", target_id, direction)
        
        elif move_type == "defend":
            return self.execute_move(player, "move", "Wait", target_id, direction)
        
        elif move_type == "cancel":
            command = {"type": "cancel_selection"}
            return adapter.process_command(command)
            
        elif move_type == "select_move_and_target":
            if not isinstance(move_id, str) or not move_id:
                return {"error": "Invalid move name"}

            # Handle "DO IT AGAIN" (repeat_last) special case
            actual_move_id = move_id
            actual_target_id = target_id

            if move_id == "repeat_last":
                # Look up the last move and target from player state
                actual_move_id = getattr(player, "last_move_name", None)
                actual_target_id = getattr(player, "last_move_target_id", None)

                if not actual_move_id:
                    return {"error": "No previous move to repeat"}
                if not actual_target_id:
                    return {"error": "No valid target for repeat move"}

                # Check if the target is still alive
                target_enemy = None
                for enemy in player.combat_list:
                    if f"enemy_{id(enemy)}" == actual_target_id and enemy.is_alive():
                        target_enemy = enemy
                        break

                if not target_enemy:
                    return {"error": "Previous target is no longer available"}

            command = {
                "type": "select_move_and_target",
                "move_name": actual_move_id,
                "target_id": actual_target_id
            }
            return adapter.process_command(command)
            
        else:
            return {"error": f"Unknown move type: {move_type}"}
            
    def get_combat_status(self, player: "player_module.Player", session_id: str = None, session_data: Dict = None) -> Dict[str, Any]:
        """Get current combat status."""
        if not hasattr(player, "_combat_adapter"):
            # If player is in combat, try to re-initialize the adapter
            if getattr(player, "in_combat", False) and hasattr(player, "combat_list"):
                from src.api.combat_adapter import ApiCombatAdapter

                # Ensure the new adapter has the event callback
                def event_callback(p):
                    return self.trigger_combat_events(p)

                player._combat_adapter = ApiCombatAdapter(player, session_id=session_id, on_event_callback=event_callback)
                # Synchronize initial state for the new adapter
                player._combat_adapter.available_options = player._combat_adapter._get_available_moves()
                # Kick off suggestions once for the re-initialized adapter
                if not getattr(player, "suggestions_loading", False):
                    player._combat_adapter.refresh_suggestions()
            else:
                return {
                    "combat_active": getattr(player, "in_combat", False),
                    "log": getattr(player, "combat_log", []),
                    "battle_state": None
                }
        else:
            adapter = player._combat_adapter

            # Resume logic: If battle is active but not awaiting input, check why
            # This handles cases where combat was paused for narrative events
            if player.in_combat and not adapter.awaiting_input:
                blocking_events = session_data.get("pending_events", {}) if session_data else {}
                if not blocking_events:
                    # No pending events, we should be resuming or finishing
                    if len(player.combat_list) == 0:
                        # All enemies defeated after event finished - trigger victory
                        adapter._handle_victory()
                    elif hasattr(player, "current_move") and player.current_move:
                        # Resume the current move if it was interrupted
                        return adapter._execute_move(player.current_move)
                    else:
                        # Otherwise, reset to move selection
                        adapter.awaiting_input = True
                        adapter.input_type = "move_selection"
                        adapter.available_options = adapter._get_available_moves()
                        if session_id:
                            adapter.session_id = session_id
                        # Only start a suggestion fetch if one isn't already running
                        if not getattr(player, "suggestions_loading", False):
                            adapter.refresh_suggestions()

            # Refresh available_options if we're in move selection mode.
            # This ensures viable_targets are updated when enemies are added/removed mid-combat.
            # DO NOT call refresh_suggestions() here — it is polled every 3 s and repeatedly
            # calling refresh_suggestions() resets suggestions_loading and clears suggested_moves,
            # creating an infinite loop where suggestions never land.
            # Suggestions are already kicked off by _execute_move() after each player action.
            if adapter.input_type == "move_selection" and adapter.awaiting_input:
                adapter.available_options = adapter._get_available_moves()
                if session_id:
                    adapter.session_id = session_id
                # Only start a fetch if suggestions haven't been generated yet this turn
                # (i.e., still empty AND not currently loading).
                if (
                    not getattr(player, "suggestions_loading", False)
                    and not getattr(player, "suggested_moves", [])
                ):
                    adapter.refresh_suggestions()

        return player._combat_adapter.get_combat_state()

    def get_available_moves(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get available combat moves."""
        if not hasattr(player, "_combat_adapter"):
            return {"moves": []}
            
        # Helper to serialize moves from adapter
        moves = []
        if hasattr(player._combat_adapter, "available_options"):
            # If options are moves (not targets/directions)
            if player._combat_adapter.input_type == "move_selection":
                for i, move in enumerate(player._combat_adapter.available_options):
                    # Handle both object and dict (adapter returns dicts now)
                    name = move.get("name") if isinstance(move, dict) else getattr(move, "name", "Unknown")
                    description = move.get("description") if isinstance(move, dict) else getattr(move, "description", "")
                    fatigue_cost = move.get("fatigue_cost") if isinstance(move, dict) else getattr(move, "fatigue_cost", 0)
                    category = move.get("category") if isinstance(move, dict) else getattr(move, "category", "Miscellaneous")
                    beats_left = move.get("beats_left") if isinstance(move, dict) else getattr(move, "beats_left", 0)
                    
                    moves.append({
                        "id": str(i),
                        "name": name,
                        "description": description,
                        "fatigue_cost": fatigue_cost,
                        "category": category,
                        "beats_left": beats_left
                    })
        
        return {"moves": moves}

    def get_player_status(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get player status (name, level, health, etc.).

        Args:
            player: The Player instance

        Returns:
            Dictionary with player status
        """
        # Consolidate gold and refresh weight before serializing
        if hasattr(player, "stack_gold"):
            player.stack_gold()
        if hasattr(player, "refresh_weight"):
            player.refresh_weight()

        weight = getattr(player, "weight_current", 0)
        max_weight = getattr(player, "weight_tolerance", 100)
        weight_pct = (weight / max_weight * 100) if max_weight > 0 else 0

        return {
            "name": getattr(player, "name", "Unknown"),
            "level": getattr(player, "level", 1),
            "exp": getattr(player, "exp", 0),
            "max_exp": getattr(player, "exp_to_level", 100),
            "hp": getattr(player, "hp", 0),
            "max_hp": getattr(player, "maxhp", 0),
            "fatigue": getattr(player, "fatigue", 0),
            "max_fatigue": getattr(player, "maxfatigue", 0),
            "gold": get_gold(getattr(player, "inventory", [])),
            "weight": weight,
            "max_weight": max_weight,
            "weight_pct": weight_pct,
            "state": "normal",  # TODO: Get actual status effects
            "party_members": [
                {
                    "name": getattr(a, "name", "Unknown"),
                    "hp": getattr(a, "hp", 0),
                    "max_hp": getattr(a, "maxhp", 0),
                    "level": getattr(a, "level", 1),
                    "description": getattr(a, "description", "").strip(),
                }
                for a in getattr(player, "combat_list_allies", [])[1:]
            ],
        }

    def get_player_stats(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get player stats.

        Args:
            player: The Player instance

        Returns:
            Dictionary with player stats
        """
        stats = {}
        stat_names = [
            "strength",
            "finesse",
            "speed",
            "endurance",
            "charisma",
            "intelligence",
            "faith",
        ]

        for stat_name in stat_names:
            current = getattr(player, stat_name, 10)
            base = getattr(player, stat_name + "_base", 10)
            stats[stat_name] = current
            stats[stat_name + "_base"] = base

        # Add other status data
        stats["hp"] = getattr(player, "hp", 0)
        stats["max_hp"] = getattr(player, "maxhp", 0)
        stats["fatigue"] = getattr(player, "fatigue", 0)
        stats["max_fatigue"] = getattr(player, "maxfatigue", 0)
        
        weight = getattr(player, "weight_current", 0)
        max_weight = getattr(player, "weight_tolerance", 100)
        
        stats["weight_current"] = weight
        stats["carrying_capacity"] = max_weight
        stats["weight"] = weight
        stats["max_weight"] = max_weight
        stats["gold"] = get_gold(getattr(player, "inventory", []))
        stats["protection"] = getattr(player, "protection", 0)
        
        # Calculate combat stats
        weapon = getattr(player, "eq_weapon", None)
        if weapon:
            power = getattr(weapon, "damage", 0) + \
                    (getattr(player, "strength", 10) * getattr(weapon, "str_mod", 0)) + \
                    (getattr(player, "finesse", 10) * getattr(weapon, "fin_mod", 0))
            
            # Apply heat if available (default to 1.0)
            heat = getattr(player, "heat", 1.0)
            
            stats["attack_damage_min"] = int(power * heat * 0.8)
            stats["attack_damage_max"] = int(power * heat * 1.2)
        else:
            stats["attack_damage_min"] = 0
            stats["attack_damage_max"] = 0

        # Accuracy and Evasion
        # Base hit chance formula: (98 - target.finesse) + user.finesse
        # We'll show accuracy as (98 + player.finesse) and evasion as player.finesse
        stats["hit_accuracy"] = 98 + getattr(player, "finesse", 10)
        stats["evasion_chance"] = getattr(player, "finesse", 10)

        stats["resistance"] = getattr(player, "resistance", {})
        stats["status_resistance"] = getattr(player, "status_resistance", {})
        stats["states"] = [{"name": state.name, "steps_left": state.steps_left} 
                          for state in getattr(player, "states", [])]

        return stats

    def get_player_skills(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get player skills and experience.

        Args:
            player: The Player instance

        Returns:
            Dictionary with skills data
        """
        # Serialize known moves
        known_moves = []
        for move in getattr(player, "known_moves", []):
            known_moves.append({
                "name": getattr(move, "name", "Unknown"),
                "category": getattr(move, "category", "Miscellaneous"),
                "description": getattr(move, "description", ""),
                "fatigue_cost": getattr(move, "fatigue_cost", 0),
                "beats_left": getattr(move, "beats_left", 0),
                "xp_gain": getattr(move, "xp_gain", 0),
            })

        skill_tree = {}
        if hasattr(player, "skilltree") and hasattr(player.skilltree, "subtypes"):
            for category, skills in player.skilltree.subtypes.items():
                category_skills = []
                for skill, req_exp in skills.items():
                    # Check if already known
                    is_known = any(km["name"] == skill.name for km in known_moves)
                    
                    category_skills.append({
                        "name": skill.name,
                        "description": getattr(skill, "description", ""),
                        "required_exp": req_exp,
                        "is_known": is_known,
                        "can_learn": player.skill_exp.get(category, 0) >= req_exp and not is_known
                    })
                skill_tree[category] = category_skills

        return {
            "known_moves": known_moves,
            "skill_exp": getattr(player, "skill_exp", {}),
            "skill_tree": skill_tree
        }

    def learn_skill(self, player: "player_module.Player", skill_name: str, category: str) -> Dict[str, Any]:
        """Learn a skill from the skill tree.

        Args:
            player: The Player instance
            skill_name: Name of the skill to learn
            category: Skill category (e.g. "Basic", "Dagger")

        Returns:
            Dictionary with result
        """
        if not hasattr(player, "skilltree") or not hasattr(player.skilltree, "subtypes"):
            return {"success": False, "error": "Skill tree not initialized"}

        if category not in player.skilltree.subtypes:
            return {"success": False, "error": f"Invalid category: {category}"}

        # Find the skill object and requirement
        skill_obj = None
        req_exp = 0
        
        for skill, req in player.skilltree.subtypes[category].items():
            if skill.name == skill_name:
                skill_obj = skill
                req_exp = req
                break
        
        if not skill_obj:
            return {"success": False, "error": f"Skill '{skill_name}' not found in category '{category}'"}

        # Check if already known
        for move in player.known_moves:
            if move.name == skill_name:
                return {"success": False, "error": "Skill already learned"}

        # Check experience
        current_exp = player.skill_exp.get(category, 0)
        if current_exp < req_exp:
            return {"success": False, "error": f"Not enough experience. Required: {req_exp}, Available: {current_exp}"}

        # Learn the skill
        player.learn_skill(skill_obj)
        player.skill_exp[category] -= req_exp

        return {
            "success": True,
            "message": f"Learned {skill_name}!",
            "remaining_exp": player.skill_exp[category],
            "skills": self.get_player_skills(player)
        }

    def get_available_commands(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get available commands/actions for the player in current room.

        Args:
            player: The Player instance

        Returns:
            Dictionary with available commands
        """
        import logging
        commands = []
        
        # Get the current tile and its available actions
        current_tile = player.universe.get_tile(player.location_x, player.location_y)
        if current_tile and hasattr(current_tile, "available_actions"):
            try:
                available_actions = current_tile.available_actions(callerIsApi=True, player=player)
                for action in available_actions:
                    commands.append({
                        "name": getattr(action, "name", "Unknown"),
                        "hotkey": getattr(action, "hotkey", []),
                        "debug": getattr(action, "debug", False),
                    })
            except Exception as e:
                logging.error(f"Error getting available actions: {e}")

        # Add default system commands if not already present
        if not any(c.get("name") == "Save" for c in commands):
            commands.append({"name": "Save", "hotkey": ["ctrl", "s"], "debug": False})
        
        if not any(c.get("name") == "Menu" for c in commands):
            commands.append({"name": "Menu", "hotkey": ["esc"], "debug": False})

        return {
            "commands": commands,
            "count": len(commands),
        }

    # ========================
    # Save/Load Methods
    # ========================

    def _get_saves_dir(self) -> str:
        """Get the directory for save files."""
        import os
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        saves_dir = os.path.join(base_path, "saves")
        if not os.path.exists(saves_dir):
            os.makedirs(saves_dir)
        return saves_dir

    async def save_game(self, player: "player_module.Player", name: str, user_id: str, is_autosave: bool = False) -> str:
        """Save the game to Turso database.

        Args:
            player: The Player instance
            name: Name for the save
            user_id: The DB user ID
            is_autosave: Whether this is an autosave

        Returns:
            Save ID
        """
        import uuid
        import pickle
        from datetime import datetime
        from src.api.db import db

        # 1. Enforcement of manual save limit
        if not is_autosave:
            count_sql = "SELECT COUNT(*) FROM saves WHERE user_id = ? AND is_autosave = FALSE"
            res = await db.execute(count_sql, [user_id])
            count = res.rows[0][0]
            if count >= 20:
                raise ValueError("Maximum number of manual saves reached (20). Please delete an existing save to create a new one.")

        save_id = str(uuid.uuid4())

        # Serialize player state.
        # _combat_adapter holds a closure and a threading.Lock — neither is picklable.
        # Strip it before serializing; restore immediately after.
        combat_adapter = player.__dict__.pop("_combat_adapter", None)
        try:
            save_data = pickle.dumps(player)
        finally:
            if combat_adapter is not None:
                player._combat_adapter = combat_adapter

        # 2. Hybrid Autosave Logic: UPSERT for the single autosave
        if is_autosave:
            # Check if an autosave already exists for this user
            check_sql = "SELECT id FROM saves WHERE user_id = ? AND is_autosave = TRUE"
            check_res = await db.execute(check_sql, [user_id])
            
            if check_res.rows:
                # Update existing autosave
                save_id = check_res.rows[0][0]
                sql = """
                UPDATE saves 
                SET data = ?, timestamp = CURRENT_TIMESTAMP, 
                    level = ?, map_name = ?, room_title = ?, playtime = ?
                WHERE id = ?
                """
                params = [
                    save_data,
                    getattr(player, "level", 1),
                    getattr(getattr(player, "map", None), "name", "Unknown"),
                    getattr(getattr(player, "current_room", None), "name", "Unknown"),
                    getattr(player, "time_elapsed", 0),
                    save_id
                ]
            else:
                # Create first autosave
                sql = """
                INSERT INTO saves (id, user_id, name, data, is_autosave, level, map_name, room_title, playtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = [
                    save_id, user_id, "Autosave", save_data, True,
                    getattr(player, "level", 1),
                    getattr(getattr(player, "map", None), "name", "Unknown"),
                    getattr(getattr(player, "current_room", None), "name", "Unknown"),
                    getattr(player, "time_elapsed", 0)
                ]
        else:
            # Manual save
            sql = """
            INSERT INTO saves (id, user_id, name, data, is_autosave, level, map_name, room_title, playtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = [
                save_id, user_id, name, save_data, False,
                getattr(player, "level", 1),
                getattr(getattr(player, "map", None), "name", "Unknown"),
                getattr(getattr(player, "current_room", None), "name", "Unknown"),
                getattr(player, "time_elapsed", 0)
            ]

        await db.execute(sql, params)
        return save_id

    async def load_game(self, save_id: str, user_id: str) -> Optional["player_module.Player"]:
        """Load a saved game from Turso.

        Args:
            save_id: ID of save to load
            user_id: The DB user ID (for security validation)

        Returns:
            Loaded Player instance or None
        """
        import pickle
        from src.api.db import db
        
        sql = "SELECT data FROM saves WHERE id = ? AND user_id = ?"
        result = await db.execute(sql, [save_id, user_id])
        
        if not result.rows:
            return None

        try:
            save_data = result.rows[0][0]
            player = pickle.loads(save_data)
            
            if player:
                # Re-initialize universe connections
                if not hasattr(player, "universe") or player.universe is None:
                    import src.universe as universe_module
                    player.universe = universe_module.Universe(player)
                
                # Force rebuild of transient state if needed
                if not hasattr(player.universe, "maps") or not player.universe.maps:
                     player.universe.build(player)
                
                if hasattr(player, "map"):
                     start_tile = player.universe.get_tile(player.location_x, player.location_y)
                     if start_tile:
                         player.current_room = start_tile

            return player
        except Exception as e:
            print(f"Error loading save {save_id}: {e}")
            return None

    async def list_saves(self, user_id: str) -> List[Dict[str, Any]]:
        """List all saved games for a user from Turso.

        Returns:
            List of save metadata dictionaries
        """
        from src.api.db import db
        
        sql = """
        SELECT id, name, timestamp, is_autosave, level, map_name, room_title, playtime 
        FROM saves 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
        """
        result = await db.execute(sql, [user_id])
        
        saves = []
        for row in result.rows:
            saves.append({
                "id": str(row[0]),
                "name": str(row[1]),
                "timestamp": str(row[2]),
                "is_autosave": bool(row[3]),
                "level": int(row[4]) if row[4] is not None else "?",
                "map_name": str(row[5]) if row[5] else "Unknown",
                "room_title": str(row[6]) if row[6] else "Unknown",
                "playtime": int(row[7]) if row[7] is not None else 0
            })
                
        return saves

    async def delete_save(self, save_id: str, user_id: str) -> bool:
        """Delete a save from Turso.

        Args:
            save_id: ID of save to delete
            user_id: The DB user ID

        Returns:
            True if deleted, False otherwise
        """
        from src.api.db import db
        
        sql = "DELETE FROM saves WHERE id = ? AND user_id = ?"
        result = await db.execute(sql, [save_id, user_id])
        
        return result.rows_affected > 0

    # ========================
    # Combat Methods
    # ========================

    def _initialize_combat(self, player: "player_module.Player", enemies: List[Any], session_id: str = None, session_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Initialize combat state for player and enemies using the combat adapter.
        
        Args:
            player: Player object
            enemies: List of enemy NPCs
        """
        # Detect if this is a re-initialization (enemies joining an already active combat)
        is_reinit = getattr(player, "in_combat", False)

        # Idempotency check: If player is already in combat with these enemies, do nothing.
        if is_reinit and hasattr(player, "combat_list"):
            # Check if we are fighting the same group of enemies
            current_combatants = set(getattr(e, "name", str(e)) for e in player.combat_list)
            new_combatants = set(getattr(e, "name", str(e)) for e in enemies)
            
            # If the set of enemies is the same, we assume this is a duplicate request
            if current_combatants == new_combatants:
                return

        from src.api.combat_adapter import ApiCombatAdapter
        
        # Set combat lists on player (required by adapter)
        player.combat_list = enemies
        # Preserve existing party members (e.g. Gorran already recruited) — only player is reset
        existing_allies = [a for a in getattr(player, "combat_list_allies", []) if a is not player]
        player.combat_list_allies = [player] + existing_allies
        player.in_combat = True

        # Initialize last move tracking for "DO IT AGAIN" button
        player.last_move_name = None
        player.last_move_target_id = None
        
        # Create or get combat adapter
        from src.api.combat_adapter import ApiCombatAdapter
        if not hasattr(player, '_combat_adapter'):
            # Define event callback for logic during beats
            def event_callback(p):
                return self.trigger_combat_events(p, session_data=session_data)
                
            player._combat_adapter = ApiCombatAdapter(player, session_id=session_id, on_event_callback=event_callback)
        elif session_id:
            player._combat_adapter.session_id = session_id
        
        # Initialize combat through the adapter
        # This will set up all combat state, process initial NPC turns if needed,
        # and return the initial combat state
        return player._combat_adapter.initialize_combat(enemies, reinit=is_reinit)

    # [Legacy methods removed]


    def _execute_attack(self, player: "player_module.Player", enemies: List[Any], target_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute a basic attack.
        
        Args:
            player: Player object
            enemies: List of enemy NPCs
            target_id: ID of target (defaults to first)
            
        Returns:
            Dictionary with attack result
        """
        target = enemies[0] if not target_id else next((e for e in enemies if str(getattr(e, "id", "")) == target_id), enemies[0])
        
        # Simple damage calculation
        damage = getattr(player, "damage", 10) + 5
        target.health = max(0, getattr(target, "health", 1) - damage)
        
        return {
            "success": True,
            "action": "attack",
            "damage_dealt": damage,
            "target": getattr(target, "name", "Enemy"),
            "target_health": getattr(target, "health", 0),
            "target_defeated": getattr(target, "health", 1) <= 0,
            "battle_state": CombatStateSerializer.serialize_combat_state(player, enemies),
        }


    def _execute_spell(self, player: "player_module.Player", enemies: List[Any], spell_name: str, target_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute a spell/ability.
        
        Args:
            player: Player object
            enemies: List of enemy NPCs
            spell_name: Name of spell
            target_id: ID of target
            
        Returns:
            Dictionary with spell result
        """
        # TODO: Implement actual spell lookup and effects
        target = enemies[0] if not target_id else next((e for e in enemies if str(getattr(e, "id", "")) == target_id), enemies[0])
        
        damage = 20  # Spell default damage
        target.health = max(0, getattr(target, "health", 1) - damage)
        
        return {
            "success": True,
            "action": "cast",
            "spell": spell_name,
            "damage_dealt": damage,
            "target": getattr(target, "name", "Enemy"),
            "target_health": getattr(target, "health", 0),
            "target_defeated": getattr(target, "health", 1) <= 0,
            "battle_state": CombatStateSerializer.serialize_combat_state(player, enemies),
        }

    def defend(self, player: "player_module.Player") -> Dict[str, Any]:
        """Take a defensive stance in combat.

        Args:
            player: Player object

        Returns:
            Dictionary with action result
        """
        if not getattr(player, "in_combat", False):
            return {"error": "Not in combat"}

        # Increase defense temporarily (stub)
        player.armor = getattr(player, "armor", 0) + 5

        enemies = getattr(player, "combat_list", [])
        return {
            "success": True,
            "action": "defend",
            "message": "Player takes a defensive stance",
            "battle_state": CombatStateSerializer.serialize_combat_state(
                player, enemies
            ),
        }

    def use_item_in_combat(
        self, player: "player_module.Player", item_index: int, target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Use an item in combat.

        Args:
            player: Player object
            item_index: Index of item in inventory
            target_id: ID of target (default: self)

        Returns:
            Dictionary with action result
        """
        if not getattr(player, "in_combat", False):
            return {"error": "Not in combat"}

        if not hasattr(player, "inventory") or not getattr(player, "inventory"):
            return {"error": "No items in inventory"}

        inventory = getattr(player, "inventory", [])
        if item_index < 0 or item_index >= len(inventory):
            return {"error": "Invalid item index"}

        item = inventory[item_index]
        item_name = getattr(item, "name", "Unknown Item")

        # TODO: Apply item effects
        # For now, remove item and return stub
        return {
            "success": True,
            "action": "use_item",
            "item": item_name,
            "effect": "Item used",
            "items_remaining": len(inventory) - 1,
        }

    def flee_combat(self, player: "player_module.Player") -> Dict[str, Any]:
        """Attempt to flee from combat.

        Args:
            player: Player object

        Returns:
            Dictionary with flee result
        """
        if not getattr(player, "in_combat", False):
            return {"error": "Not in combat"}

        # 50% chance to flee (stub)
        success = True  # In real implementation, would check speed/chance

        if success:
            player.in_combat = False
            return {
                "success": True,
                "fled": True,
                "message": "Fled from combat successfully",
            }
        else:
            enemies = getattr(player, "combat_list", [])
            return {
                "success": False,
                "fled": False,
                "message": "Failed to flee!",
                "battle_state": CombatStateSerializer.serialize_combat_state(
                    player, enemies
                ),
            }

    def _get_turn_order(self, player: "player_module.Player", enemies: List[Any]) -> List[str]:
        """Calculate turn order based on speed stats.
        
        Args:
            player: Player object
            enemies: List of enemy NPCs
            
        Returns:
            List of combatant identifiers in turn order
        """
        combatants = [("player", getattr(player, "speed", 10))] + [
            (f"enemy_{i}", getattr(e, "speed", 5)) for i, e in enumerate(enemies)
        ]
        # Sort by speed (descending) - higher speed goes first
        combatants.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in combatants]
    
    def _advance_turn(self, player: "player_module.Player", enemies: List[Any]) -> None:
        """Advance to the next combatant's turn.
        
        Args:
            player: Player object
            enemies: List of enemy NPCs
        """
        turn_order = self._get_turn_order(player, enemies)
        player.combat_turn_index = (player.combat_turn_index + 1) % len(turn_order)
        
        # If we wrapped around, increment round
        if player.combat_turn_index == 0:
            player.combat_round += 1
            player.combat_log.append({
                "round": player.combat_round,
                "message": f"--- Round {player.combat_round} ---",
                "type": "system"
            })
    
    def _process_npc_turns(self, player: "player_module.Player", enemies: List[Any], turn_order: List[str]) -> None:
        """Process NPC turns until it's the player's turn again.
        
        Args:
            player: Player object
            enemies: List of enemy NPCs
            turn_order: Ordered list of combatant identifiers
        """
        import random
        
        while player.combat_turn_index < len(turn_order):
            current_combatant = turn_order[player.combat_turn_index]
            
            # If it's player's turn, stop processing
            if current_combatant == "player":
                break
            
            # Process NPC turn
            if current_combatant.startswith("enemy_"):
                enemy_index = int(current_combatant.split("_")[1])
                if enemy_index < len(enemies):
                    enemy = enemies[enemy_index]
                    
                    # Simple AI: attack the player
                    damage = random.randint(5, 15)
                    player.hp = max(0, player.hp - damage)
                    
                    player.combat_log.append({
                        "round": player.combat_round,
                        "message": f"{enemy.name} attacks for {damage} damage! (Player HP: {player.hp}/{player.maxhp})",
                        "type": "enemy_action",
                        "actor": enemy.name,
                        "damage": damage
                    })
                    
                    # Check if player is defeated
                    if player.hp <= 0:
                        player.combat_log.append({
                            "round": player.combat_round,
                            "message": "You have been defeated!",
                            "type": "system"
                        })
                        player.in_combat = False
                        return
            
            # Advance to next turn
            self._advance_turn(player, enemies)


    def end_combat(
        self, player: "player_module.Player", victory: bool
    ) -> Dict[str, Any]:
        """End combat and return results.

        Args:
            player: Player object
            victory: Whether player won

        Returns:
            Dictionary with combat results
        """
        enemies = getattr(player, "combat_list", [])
        player.in_combat = False

        result = CombatStateSerializer.serialize_battle_summary(player, enemies, victory)

        # Reset combat lists
        player.combat_list = []
        player.combat_list_allies = []

        return result

    # =====================
    # NPC Methods (Phase 5)
    # =====================

    def get_npc_state(self, player: "player_module.Player", npc_id: str) -> Dict[str, Any]:
        """Get current state of an NPC.

        Args:
            player: Player object
            npc_id: NPC identifier

        Returns:
            Dictionary with NPC state
        """
        # Find NPC in current tile
        current_tile = player.universe.get_tile(player.location_x, player.location_y)
        if not current_tile:
            return {"success": False, "error": "Not on a valid tile"}

        for npc in getattr(current_tile, "npcs_here", []):
            if getattr(npc, "name", "") == npc_id:
                return {
                    "success": True,
                    "npc": NPCAIStateSerializer.serialize_npc_ai_state(npc),
                }

        return {"success": False, "error": f"NPC '{npc_id}' not found"}

    def get_npc_dialogue(
        self, player: "player_module.Player", npc_id: str
    ) -> Dict[str, Any]:
        """Get dialogue options from an NPC.

        Args:
            player: Player object
            npc_id: NPC identifier

        Returns:
            Dictionary with dialogue state
        """
        # Find NPC in current tile
        current_tile = player.universe.get_tile(player.location_x, player.location_y)
        if not current_tile:
            return {"success": False, "error": "Not on a valid tile"}

        for npc in getattr(current_tile, "npcs_here", []):
            if getattr(npc, "name", "") == npc_id:
                dialogue_state = DialogueStateSerializer.serialize_dialogue_state(
                    npc, current_node="start"
                )
                return {"success": True, "dialogue": dialogue_state}

        return {"success": False, "error": f"NPC '{npc_id}' not found"}

    def select_dialogue_option(
        self, player: "player_module.Player", npc_id: str, option_id: int
    ) -> Dict[str, Any]:
        """Select a dialogue option from an NPC.

        Args:
            player: Player object
            npc_id: NPC identifier
            option_id: Selected option index

        Returns:
            Dictionary with next dialogue state
        """
        # Find NPC in current tile
        current_tile = player.universe.get_tile(player.location_x, player.location_y)
        if not current_tile:
            return {"success": False, "error": "Not on a valid tile"}

        for npc in getattr(current_tile, "npcs_here", []):
            if getattr(npc, "name", "") == npc_id:
                # Update conversation history
                if not hasattr(npc, "conversation_history"):
                    npc.conversation_history = []

                # Mark dialogue interaction
                npc.last_interaction_time = str(__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ))

                # Return next dialogue node (stub implementation)
                dialogue_state = DialogueStateSerializer.serialize_dialogue_state(
                    npc, current_node="option_response"
                )
                return {"success": True, "dialogue": dialogue_state}

        return {"success": False, "error": f"NPC '{npc_id}' not found"}

    def get_npc_behavior_profile(
        self, player: "player_module.Player", npc_id: str
    ) -> Dict[str, Any]:
        """Get NPC behavior profile.

        Args:
            player: Player object
            npc_id: NPC identifier

        Returns:
            Dictionary with NPC behavior profile
        """
        # Find NPC in current tile
        current_tile = player.universe.get_tile(player.location_x, player.location_y)
        if not current_tile:
            return {"success": False, "error": "Not on a valid tile"}

        for npc in getattr(current_tile, "npcs_here", []):
            if getattr(npc, "name", "") == npc_id:
                profile = NPCBehaviorProfileSerializer.serialize_behavior_profile(npc)
                return {"success": True, "profile": profile}

        return {"success": False, "error": f"NPC '{npc_id}' not found"}

    def get_active_quests(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get list of active quests.

        Args:
            player: Player object

        Returns:
            Dictionary with active quests
        """
        quests = QuestStateSerializer.serialize_active_quests(player)
        return {
            "success": True,
            "quests": quests,
            "count": len(quests),
        }

    def start_quest(
        self, player: "player_module.Player", quest_id: str
    ) -> Dict[str, Any]:
        """Start a quest.

        Args:
            player: Player object
            quest_id: Quest identifier

        Returns:
            Dictionary with quest details
        """
        # Find quest in player's available quests
        available_quests = getattr(player, "available_quests", [])

        for quest in available_quests:
            if quest.get("id") == quest_id:
                # Move to active quests
                if not hasattr(player, "active_quests"):
                    player.active_quests = []

                player.active_quests.append(quest)
                available_quests.remove(quest)

                return {
                    "success": True,
                    "message": f"Started quest: {quest.get('title', quest_id)}",
                    "quest": QuestStateSerializer.serialize_quest(quest),
                }

        return {"success": False, "error": f"Quest '{quest_id}' not found"}

    def update_quest_progress(
        self,
        player: "player_module.Player",
        quest_id: str,
        objective_id: str,
    ) -> Dict[str, Any]:
        """Update progress on a quest objective.

        Args:
            player: Player object
            quest_id: Quest identifier
            objective_id: Objective identifier

        Returns:
            Dictionary with updated quest progress
        """
        # Find active quest
        active_quests = getattr(player, "active_quests", [])

        for quest in active_quests:
            if quest.get("id") == quest_id:
                # Mark objective complete
                for objective in quest.get("objectives", []):
                    if objective.get("id") == objective_id:
                        objective["completed"] = True

                # Update progress
                completed = sum(
                    1 for obj in quest.get("objectives", [])
                    if obj.get("completed", False)
                )
                total = len(quest.get("objectives", []))
                quest["progress"] = int((completed / total * 100)) if total > 0 else 0

                return {
                    "success": True,
                    "message": "Objective completed",
                    "quest": QuestStateSerializer.serialize_quest_progress(quest),
                }

        return {"success": False, "error": f"Quest '{quest_id}' not found or not active"}

    def get_quest_status(
        self, player: "player_module.Player", quest_id: str
    ) -> Dict[str, Any]:
        """Get status of a specific quest.

        Args:
            player: Player object
            quest_id: Quest identifier

        Returns:
            Dictionary with quest status
        """
        # Check active quests
        active_quests = getattr(player, "active_quests", [])
        for quest in active_quests:
            if quest.get("id") == quest_id:
                return {
                    "success": True,
                    "status": "active",
                    "quest": QuestStateSerializer.serialize_quest_progress(quest),
                }

        # Check completed quests
        completed_quests = getattr(player, "completed_quests", [])
        for quest in completed_quests:
            if quest.get("id") == quest_id:
                return {
                    "success": True,
                    "status": "completed",
                    "quest": QuestStateSerializer.serialize_quest(quest),
                }

        return {"success": False, "error": f"Quest '{quest_id}' not found"}

    # ========================
    # Quest Reward Methods (Phase 3)
    # ========================

    def get_quest_rewards(self, player: "player_module.Player", quest_id: str) -> Dict[str, Any]:
        """Get rewards for a specific quest.

        Args:
            player: Player object
            quest_id: Quest identifier

        Returns:
            Dictionary with quest reward details
        """
        from src.api.serializers.quest_rewards import QuestRewardSerializer

        # Find quest in completed or available quests
        quest = None

        # Check active quests first
        active_quests = getattr(player, "active_quests", [])
        for q in active_quests:
            if q.get("id") == quest_id:
                quest = q
                break

        # Check completed quests
        if not quest:
            completed_quests = getattr(player, "completed_quests", [])
            for q in completed_quests:
                if q.get("id") == quest_id:
                    quest = q
                    break

        if not quest:
            return {"success": False, "error": f"Quest '{quest_id}' not found"}

        rewards_data = QuestRewardSerializer.serialize_quest_rewards(quest)

        return {"success": True, "rewards": rewards_data}

    def complete_quest(
        self,
        player: "player_module.Player",
        quest_id: str,
        difficulty: str = "normal",
        no_deaths: bool = True,
        bonus_objectives_completed: bool = False,
    ) -> Dict[str, Any]:
        """Complete a quest and distribute rewards.

        Args:
            player: Player object
            quest_id: Quest to complete
            difficulty: Quest difficulty (easy, normal, hard, nightmare)
            no_deaths: Whether quest was completed without deaths
            bonus_objectives_completed: Whether all bonus objectives completed

        Returns:
            Dictionary with completion details and rewards distributed
        """
        from src.api.serializers.quest_rewards import (
            RewardConditionValidator,
            RewardDistributionSerializer,
            LevelingProgressSerializer,
        )

        # Find and remove quest from active quests
        active_quests = getattr(player, "active_quests", [])
        quest = None

        for i, q in enumerate(active_quests):
            if q.get("id") == quest_id:
                quest = active_quests.pop(i)
                break

        if not quest:
            return {"success": False, "error": f"Quest '{quest_id}' not active"}

        # Apply conditions to calculate final rewards
        base_rewards, conditions_met = RewardConditionValidator.check_reward_conditions(
            player, quest
        )

        # Add condition modifiers
        reward_modifier = 1.0

        # Difficulty multiplier
        difficulty_multipliers = {
            "easy": 0.5,
            "normal": 1.0,
            "hard": 1.5,
            "nightmare": 2.0,
        }
        reward_modifier *= difficulty_multipliers.get(difficulty, 1.0)

        # No-deaths bonus
        if no_deaths:
            reward_modifier *= 1.2

        # Bonus objectives bonus
        if bonus_objectives_completed:
            reward_modifier *= 1.25

        # Calculate final rewards
        final_rewards = {
            "gold": int(base_rewards.get("gold", 0) * reward_modifier),
            "experience": int(base_rewards.get("experience", 0) * reward_modifier),
            "items": base_rewards.get("items", []),
            "reputation": base_rewards.get("reputation", {}),
        }

        # Distribute rewards to player
        old_level = getattr(player, "level", 1)
        old_gold = getattr(player, "gold", 0)
        old_xp = getattr(player, "experience", 0)

        # Award gold
        player.gold = old_gold + final_rewards["gold"]

        # Award experience and check for level up
        player.experience = old_xp + final_rewards["experience"]
        new_level = old_level
        level_up = False

        # Simple leveling: 100 XP per level
        while player.experience >= new_level * 100:
            new_level += 1
            level_up = True

        if level_up:
            player.level = new_level

        # Award items (simplified - just add to inventory if space)
        inventory = getattr(player, "inventory", [])
        for item in final_rewards["items"]:
            if len(inventory) < getattr(player, "max_inventory", 20):
                inventory.append(item)

        # Award reputation (simplified - just track)
        if not hasattr(player, "reputation"):
            player.reputation = {}

        for npc_id, rep_change in final_rewards["reputation"].items():
            if npc_id not in player.reputation:
                player.reputation[npc_id] = 0
            player.reputation[npc_id] += rep_change

        # Move quest to completed
        completed_quests = getattr(player, "completed_quests", [])
        if not completed_quests:
            player.completed_quests = []
        player.completed_quests.append(quest)

        # Serialize results
        distribution_result = RewardDistributionSerializer.serialize_distributed_rewards(
            player, quest_id, final_rewards
        )

        # Add level up info if applicable
        if level_up:
            level_up_info = LevelingProgressSerializer.serialize_level_up(
                player, old_level, new_level, final_rewards["experience"]
            )
            distribution_result["level_up"] = level_up_info

        # Add conditions info
        distribution_result["conditions_applied"] = conditions_met

        return {"success": True, "quest_completion": distribution_result}

    def award_gold(self, player: "player_module.Player", amount: int) -> Dict[str, Any]:
        """Award gold to player.

        Args:
            player: Player object
            amount: Gold amount to award

        Returns:
            Dictionary with gold update info
        """
        from src.api.serializers.quest_rewards import RewardDistributionSerializer
        import src.items as items

        # Create a gold item and add it to inventory
        gold_item = items.Gold(amount)
        player.inventory.append(gold_item)
        
        # Consolidate gold and refresh weight
        if hasattr(player, "stack_gold"):
            player.stack_gold()
        if hasattr(player, "refresh_weight"):
            player.refresh_weight()

        result = RewardDistributionSerializer.serialize_gold_gain(player, amount)

        return {"success": True, "gold_update": result}

    def award_experience(
        self, player: "player_module.Player", amount: int
    ) -> Dict[str, Any]:
        """Award experience to player.

        Args:
            player: Player object
            amount: Experience amount to award

        Returns:
            Dictionary with experience update and level up info if applicable
        """
        from src.api.serializers.quest_rewards import (
            RewardDistributionSerializer,
            LevelingProgressSerializer,
        )

        old_level = getattr(player, "level", 1)
        old_xp = getattr(player, "experience", 0)

        player.experience = old_xp + amount
        new_level = old_level
        level_up = False

        # Simple leveling: 100 XP per level
        while player.experience >= new_level * 100:
            new_level += 1
            level_up = True

        if level_up:
            player.level = new_level

        result = RewardDistributionSerializer.serialize_xp_gain(
            player, amount, level_up=level_up, old_level=old_level
        )

        if level_up:
            level_up_info = LevelingProgressSerializer.serialize_level_up(
                player, old_level, new_level, amount
            )
            result["level_up"] = level_up_info

        return {"success": True, "experience_update": result}

    def award_item(
        self,
        player: "player_module.Player",
        item_id: str,
        item_name: str,
        quantity: int = 1,
    ) -> Dict[str, Any]:
        """Award item to player inventory.

        Args:
            player: Player object
            item_id: Item identifier
            item_name: Item name
            quantity: Quantity to award

        Returns:
            Dictionary with item award info
        """
        from src.api.serializers.quest_rewards import RewardDistributionSerializer
        import src.items as items

        # Simplified item award (tries to find class in src.items)
        # In a real game, you'd have a factory or registry
        item_class = getattr(items, item_id, None)
        if item_class:
            item = item_class()
            if hasattr(item, "count"):
                item.count = quantity
            if hasattr(item, "amt") and item.name == "Gold":
                item.amt = quantity
        else:
            # Fallback to generic item dictionary ONLY if class not found
            # (Warning: engine may not support this everywhere)
            item = {
                "id": item_id,
                "name": item_name,
                "quantity": quantity,
                "maintype": "Special",
            }

        # Check weight limit if it's an object with weight
        if not isinstance(item, dict) and hasattr(item, "weight"):
            item_weight = item.weight * getattr(item, "count", 1)
            capacity = getattr(player, "weight_tolerance", 100)
            if player.weight_current + item_weight > capacity:
                return {
                    "success": False,
                    "error": "Too heavy to carry",
                    "item_id": item_id,
                }

        player.inventory.append(item)
        
        # Consolidate inventory if it's a real item
        if not isinstance(item, dict) and hasattr(player, "stack_inv_items"):
            player.stack_inv_items()
            if hasattr(item, "name") and item.name == "Gold":
                player.stack_gold()
        
        if hasattr(player, "refresh_weight"):
            player.refresh_weight()

        result = RewardDistributionSerializer.serialize_item_reward(
            item_id, item_name, quantity
        )

        return {"success": True, "item_award": result}

    def award_reputation(
        self,
        player: "player_module.Player",
        npc_id: str,
        npc_name: str,
        amount: int,
    ) -> Dict[str, Any]:
        """Award reputation with an NPC.

        Args:
            player: Player object
            npc_id: NPC identifier
            npc_name: NPC name
            amount: Reputation change amount

        Returns:
            Dictionary with reputation update info
        """
        from src.api.serializers.quest_rewards import RewardDistributionSerializer

        if not hasattr(player, "reputation"):
            player.reputation = {}

        old_rep = player.reputation.get(npc_id, 0)
        player.reputation[npc_id] = old_rep + amount

        result = RewardDistributionSerializer.serialize_reputation_gain(
            npc_id, npc_name, amount
        )

        return {"success": True, "reputation_update": result}

    def get_player_progression(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get player progression stats.

        Args:
            player: Player object

        Returns:
            Dictionary with progression data
        """
        from src.api.serializers.quest_rewards import LevelingProgressSerializer

        quests_completed = len(getattr(player, "completed_quests", []))

        result = LevelingProgressSerializer.serialize_progression(
            player, quests_completed
        )

        return {"success": True, "progression": result}

    # ========================
    # Reputation Methods (Stage 2)
    # ========================

    def get_player_reputation(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get player's complete reputation state.

        Args:
            player: Player object

        Returns:
            All reputation data for all NPCs
        """
        from src.api.serializers.reputation import PlayerReputationSerializer

        result = PlayerReputationSerializer.serialize_all_reputation(player)
        return {"success": True, "reputation": result}

    def get_npc_relationship(
        self, player: "player_module.Player", npc_id: str
    ) -> Dict[str, Any]:
        """Get relationship with a specific NPC.

        Args:
            player: Player object
            npc_id: NPC identifier

        Returns:
            Relationship data for the NPC
        """
        from src.api.serializers.reputation import (
            NPCRelationshipSerializer,
            RelationshipFlagSerializer,
        )

        reputation = getattr(player, "reputation", {}).get(npc_id, 0)
        npc_name = NPCRelationshipSerializer._get_npc_name(npc_id)

        relationship = NPCRelationshipSerializer.serialize_relationship(
            npc_id, npc_name, reputation
        )

        flags = RelationshipFlagSerializer.get_flags(player, npc_id)

        return {
            "success": True,
            "relationship": relationship,
            "flags": flags,
        }

    def update_reputation(
        self,
        player: "player_module.Player",
        npc_id: str,
        amount: int,
        reason: str = "unknown",
    ) -> Dict[str, Any]:
        """Update player's reputation with an NPC.

        Args:
            player: Player object
            npc_id: NPC identifier
            amount: Reputation change amount (-100 to +100)
            reason: Reason for reputation change

        Returns:
            Reputation change result
        """
        from src.api.serializers.reputation import (
            NPCRelationshipSerializer,
            PlayerReputationSerializer,
        )

        if not hasattr(player, "reputation"):
            player.reputation = {}

        npc_name = NPCRelationshipSerializer._get_npc_name(npc_id)
        old_rep = player.reputation.get(npc_id, 0)

        # Clamp reputation to -100 to +100
        new_rep = max(-100, min(100, old_rep + amount))

        player.reputation[npc_id] = new_rep

        result = PlayerReputationSerializer.serialize_reputation_change(
            npc_id, npc_name, old_rep, new_rep, reason
        )

        return {"success": True, "reputation_change": result}

    def set_relationship_flag(
        self, player: "player_module.Player", npc_id: str, flag_name: str, value: bool
    ) -> Dict[str, Any]:
        """Set a relationship flag for an NPC.

        Args:
            player: Player object
            npc_id: NPC identifier
            flag_name: Flag name (romance, betrayed, alliance, etc.)
            value: Flag value

        Returns:
            Flag update result
        """
        from src.api.serializers.reputation import RelationshipFlagSerializer

        result = RelationshipFlagSerializer.set_flag(player, npc_id, flag_name, value)

        return {"success": result.get("success", True), "flag_update": result}

    def check_dialogue_available(
        self, player: "player_module.Player", npc_id: str, dialogue_node: str
    ) -> Dict[str, Any]:
        """Check if a dialogue node is available based on reputation.

        Args:
            player: Player object
            npc_id: NPC identifier
            dialogue_node: Dialogue node identifier

        Returns:
            Availability status and reason if locked
        """
        from src.api.serializers.reputation import ReputationThresholdValidator

        available, reason = ReputationThresholdValidator.check_dialogue_available(
            player, npc_id, dialogue_node
        )

        return {
            "success": True,
            "dialogue_node": dialogue_node,
            "available": available,
            "locked_reason": reason,
        }

    def check_quest_available(
        self, player: "player_module.Player", npc_id: str, quest_type: str
    ) -> Dict[str, Any]:
        """Check if a quest is available based on reputation.

        Args:
            player: Player object
            npc_id: NPC identifier
            quest_type: Type of quest

        Returns:
            Availability status and reason if locked
        """
        from src.api.serializers.reputation import ReputationThresholdValidator

        available, reason = ReputationThresholdValidator.check_quest_available(
            player, npc_id, quest_type
        )

        return {
            "success": True,
            "quest_type": quest_type,
            "available": available,
            "locked_reason": reason,
        }

    # ========================
    # Quest Chain Methods (Stage 3)
    # ========================

    def get_chain_progress(
        self, player: "player_module.Player", chain_id: str
    ) -> Dict[str, Any]:
        """Get player's progress in a quest chain.

        Args:
            player: Player object
            chain_id: Chain identifier

        Returns:
            Chain progress data
        """
        from src.api.serializers.quest_chains import ChainProgressionSerializer

        result = ChainProgressionSerializer.get_chain_progress(player, chain_id)

        return {"success": True, "progress": result}

    def advance_chain_stage(
        self,
        player: "player_module.Player",
        chain_id: str,
        current_stage: int,
        next_stage: int,
    ) -> Dict[str, Any]:
        """Advance player to next stage in a chain.

        Args:
            player: Player object
            chain_id: Chain identifier
            current_stage: Current stage index
            next_stage: Next stage index

        Returns:
            Updated progression
        """
        from src.api.serializers.quest_chains import ChainProgressionSerializer

        result = ChainProgressionSerializer.advance_to_next_stage(
            player, chain_id, current_stage, next_stage
        )

        return {"success": result.get("success", True), "advancement": result}

    def complete_chain(
        self, player: "player_module.Player", chain_id: str
    ) -> Dict[str, Any]:
        """Mark a chain as completed.

        Args:
            player: Player object
            chain_id: Chain identifier

        Returns:
            Completion result
        """
        from src.api.serializers.quest_chains import ChainProgressionSerializer

        result = ChainProgressionSerializer.complete_chain(player, chain_id)

        return {"success": result.get("success", True), "completion": result}

    def get_all_chains_progress(
        self, player: "player_module.Player"
    ) -> Dict[str, Any]:
        """Get player's progress across all chains.

        Args:
            player: Player object

        Returns:
            All chains progress
        """
        from src.api.serializers.quest_chains import ChainProgressionSerializer

        result = ChainProgressionSerializer.serialize_all_chains_progress(player)

        return {"success": True, "all_chains": result}

    def check_chain_prerequisites(
        self,
        player: "player_module.Player",
        chain_id: str,
        prerequisites: List[str],
    ) -> Dict[str, Any]:
        """Check if a chain's prerequisites are met.

        Args:
            player: Player object
            chain_id: Chain identifier
            prerequisites: List of required completed chains

        Returns:
            Prerequisite check result
        """
        from src.api.serializers.quest_chains import ChainDependencySerializer

        if not hasattr(player, "completed_chains"):
            player.completed_chains = {}

        is_valid, error = ChainDependencySerializer.validate_chain_dependencies(
            chain_id, prerequisites, player.completed_chains
        )

        return {
            "success": True,
            "chain_id": chain_id,
            "prerequisites_met": is_valid,
            "error_reason": error,
        }

    # ========================
    # NPC Availability Methods
    # ========================

    def get_npc_status(self, player: Any, npc_id: str) -> Dict[str, Any]:
        """
        Get current status and availability of an NPC.

        Args:
            player: The player object
            npc_id: ID of the NPC to check

        Returns:
            Dict with NPC status including availability and location
        """
        # Get NPC data - for now, mock structure
        # In full implementation, would load from NPC database/config
        npc_data = {
            "npc_id": npc_id,
            "name": f"NPC_{npc_id}",
            "description": "An NPC",
            "availability_conditions": {
                "story_gates": [],
                "min_ticks_after_gate": 0,
            },
            "locations": [],
            "triggers": [],
        }

        status = NPCStatusSerializer.serialize(
            npc_data,
            self._game_tick(player),
            self._story(player),
        )

        return {
            "success": True,
            "data": status,
        }

    def get_npcs_at_location(self, player: Any, location_id: str) -> Dict[str, Any]:
        """
        Get all NPCs currently at a specific location.

        Args:
            player: The player object
            location_id: ID of the location to check

        Returns:
            Dict with list of NPCs at that location
        """
        # For now, mock empty list
        # In full implementation, would load all NPCs and check their locations
        all_npcs = []

        location_npcs = LocationNPCSerializer.serialize(
            location_id,
            location_id,  # location_name
            all_npcs,
            self._game_tick(player),
            self._story(player),
        )

        return {
            "success": True,
            "data": location_npcs,
        }

    def check_npc_availability(self, player: Any, npc_id: str,
                               reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Check if an NPC is available for interaction.

        Args:
            player: The player object
            npc_id: ID of the NPC to check
            reason: Optional reason for availability check (for logging)

        Returns:
            Dict with availability status and reasons if unavailable
        """
        # Get NPC data
        npc_data = {
            "npc_id": npc_id,
            "name": f"NPC_{npc_id}",
            "description": "An NPC",
            "availability_conditions": {
                "story_gates": [],
                "min_ticks_after_gate": 0,
            },
            "locations": [],
            "triggers": [],
        }

        is_available, availability_reason = NPCAvailabilitySerializer.is_available(
            npc_data,
            self._game_tick(player),
            self._story(player),
        )

        availability_info = NPCAvailabilitySerializer.serialize(
            npc_data,
            self._game_tick(player),
            self._story(player),
        )

        return {
            "success": True,
            "data": {
                "npc_id": npc_id,
                "available": is_available,
                "reason": availability_reason.value,
                "details": availability_info,
            },
        }

    def update_npc_location(self, player: Any, npc_id: str,
                           new_location_id: str) -> Dict[str, Any]:
        """
        Update an NPC's location (used for quest events/progression).

        Args:
            player: The player object
            npc_id: ID of the NPC to move
            new_location_id: ID of the new location

        Returns:
            Dict with update status
        """
        # For now, simple mock response
        # In full implementation, would validate and update NPC location data
        return {
            "success": True,
            "data": {
                "npc_id": npc_id,
                "moved_to": new_location_id,
                "game_tick": self._game_tick(player),
            },
        }

    def get_npc_timeline(self, player: Any, npc_id: str) -> Dict[str, Any]:
        """
        Get the location progression timeline for an NPC.

        Shows where NPCs appear as the story progresses.

        Args:
            player: The player object
            npc_id: ID of the NPC

        Returns:
            Dict with NPC's location timeline
        """
        # Get NPC data
        npc_data = {
            "npc_id": npc_id,
            "name": f"NPC_{npc_id}",
            "description": "An NPC",
            "locations": [],
            "triggers": [],
        }

        timeline = NPCTimelineSerializer.serialize(npc_data)

        return {
            "success": True,
            "data": timeline,
        }

    # ========================
    # Dialogue Context Methods
    # ========================

    def start_dialogue(
        self, player: "player_module.Player", npc_id: str, dialogue_id: str
    ) -> Dict[str, Any]:
        """Start a new dialogue with an NPC.

        Creates a conversation and loads initial dialogue node.
        Validates NPC availability before starting.

        Args:
            player: The player instance
            npc_id: ID of NPC to dialogue with
            dialogue_id: ID of dialogue tree to load

        Returns:
            Dict with success status and dialogue context
        """
        import uuid
        from datetime import datetime

        # TODO: Check NPC availability (uses Stage 4 system)
        # For now, assume NPC is available

        # Create conversation record
        conversation_id = str(uuid.uuid4())
        history = ConversationHistory(
            conversation_id=conversation_id,
            npc_id=npc_id,
            player_id=getattr(player, "name", "Jean"),
            dialogue_id=dialogue_id,
            started_at=datetime.now().isoformat(),
            status="ongoing"
        )

        # TODO: Load dialogue tree from universe.dialogues[dialogue_id]
        # For now, create a minimal starting node
        initial_node = DialogueNode(
            node_id="start",
            text="[Dialogue would start here]",
            speaker=npc_id,
            npc_tone="neutral"
        )

        # Record initial node visit
        ConversationHistorySerializer.add_node_visit(history, initial_node.node_id)

        # Get available choices for initial node
        available_choices = DialogueNodeSerializer.get_available_choices(
            initial_node,
            player_story=self._story(player),
            player_reputation=getattr(player, 'reputation', {}),
            player_level=getattr(player, 'level', 1),
            player_completed_dialogues=getattr(player, "completed_dialogues", [])
        )

        # Create dialogue context
        context = DialogueContext(
            conversation_id=conversation_id,
            current_node=initial_node,
            available_choices=available_choices,
            conversation_history=history,
            is_complete=False
        )

        # TODO: Store context in player session for later retrieval
        if not hasattr(player, "dialogue_contexts"):
            player.dialogue_contexts = {}
        player.dialogue_contexts[conversation_id] = context

        return {
            "success": True,
            "data": DialogueContextSerializer.serialize(context)
        }

    def get_dialogue_node(
        self, player: "player_module.Player", node_id: str
    ) -> Dict[str, Any]:
        """Get a specific dialogue node.

        Loads node from dialogue tree and filters choices by player conditions.

        Args:
            player: The player instance
            node_id: ID of dialogue node to retrieve

        Returns:
            Dict with success status and node data
        """
        # TODO: Load node from universe.dialogue_nodes[node_id]
        # For now, return a sample node
        node = DialogueNode(
            node_id=node_id,
            text="[Sample dialogue node]",
            speaker="npc_1",
            npc_tone="friendly"
        )

        available_choices = DialogueNodeSerializer.get_available_choices(
            node,
            player_story=self._story(player),
            player_reputation=getattr(player, 'reputation', {}),
            player_level=getattr(player, 'level', 1),
            player_completed_dialogues=getattr(player, "completed_dialogues", [])
        )

        return {
            "success": True,
            "data": {
                "node": DialogueNodeSerializer.serialize(node),
                "available_choices": [
                    DialogueChoiceSerializer.serialize(c) for c in available_choices
                ]
            }
        }

    def select_dialogue_choice(
        self,
        player: "player_module.Player",
        conversation_id: str,
        choice_id: str
    ) -> Dict[str, Any]:
        """Process a dialogue choice selection.

        Applies choice effects (story gates, reputation, items) and
        transitions to next node.

        Args:
            player: The player instance
            conversation_id: ID of current conversation
            choice_id: ID of choice selected

        Returns:
            Dict with success status and updated context
        """
        # TODO: Load conversation context from player.dialogue_contexts
        # For now, create a minimal response
        next_node = DialogueNode(
            node_id="next_node",
            text="[Next dialogue node]",
            speaker="npc_1",
            npc_tone="neutral"
        )

        available_choices = DialogueNodeSerializer.get_available_choices(
            next_node,
            player_story=self._story(player),
            player_reputation=getattr(player, 'reputation', {}),
            player_level=getattr(player, 'level', 1),
            player_completed_dialogues=getattr(player, "completed_dialogues", [])
        )

        # Create updated context
        history = ConversationHistory(
            conversation_id=conversation_id,
            npc_id="npc_1",
            player_id=getattr(player, "name", "Jean"),
            dialogue_id="dial_1",
            started_at="2025-11-10T10:00:00Z"
        )

        context = DialogueContext(
            conversation_id=conversation_id,
            current_node=next_node,
            available_choices=available_choices,
            conversation_history=history,
            is_complete=False
        )

        return {
            "success": True,
            "data": DialogueContextSerializer.serialize(context)
        }

    def get_conversation_history(
        self, player: "player_module.Player", npc_id: str
    ) -> Dict[str, Any]:
        """Get all past conversations with an NPC.

        Returns list of all dialogues ever had with this NPC.

        Args:
            player: The player instance
            npc_id: ID of NPC to get history for

        Returns:
            Dict with success status and conversation list
        """
        # TODO: Load from player.conversation_history[npc_id]
        # For now, return empty list
        conversations = []

        return {
            "success": True,
            "data": {
                "npc_id": npc_id,
                "total_conversations": len(conversations),
                "conversations": [
                    ConversationHistorySerializer.serialize(c) for c in conversations
                ]
            }
        }

    def get_available_dialogues(
        self, player: "player_module.Player", npc_id: str
    ) -> Dict[str, Any]:
        """Get all available dialogue options with an NPC.

        Filters dialogues by player's story state and conditions.

        Args:
            player: The player instance
            npc_id: ID of NPC to get dialogues for

        Returns:
            Dict with success status and available dialogue list
        """
        # TODO: Load NPC's dialogues from universe.npc_dialogues[npc_id]
        # Filter by player conditions
        # For now, return empty list
        available = []

        return {
            "success": True,
            "data": {
                "npc_id": npc_id,
                "total_available": len(available),
                "dialogues": available
            }
        }





