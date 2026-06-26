import logging
import uuid
import contextlib
import re
from typing import TYPE_CHECKING, Dict, Any, Optional, List
from unittest.mock import patch

from src.api.constants import ITEM_USE_RANGE
from src.functions import check_for_combat
from inventory_utils import get_gold
from narration import capture_narration, narrate

if TYPE_CHECKING:
    from src import player as player_module
from src.api.serializers.item_serializer import ItemSerializer
from src.api.serializers.npc_serializer import NPCSerializer
from src.api.serializers.object_serializer import ObjectSerializer
from src.api.serializers.event_serializer import EventSerializer
from src.api.serializers.inventory import (
    InventorySerializer,
    EquipmentSerializer,
)
from src.api.serializers.combat import (
    CombatStateSerializer,
)
from src.api.serializers.npc_ai import (
    NPCAIStateSerializer,
    DialogueStateSerializer,
    NPCBehaviorProfileSerializer,
)

_log = logging.getLogger(__name__)

# Internal LLM diagnostic strings that must never reach the UI.
# Originate from ai/llm_client.py logger calls captured via redirect_stdout,
# plus echoed Mynx system-prompt fragments returned by low-quality model runs.
_LLM_NOISE_PREFIXES = (
    "OpenRouter returned",
    "Primary model",
    "Searching for fallback",
    "Fallback model",
    "marking as unusable",
    "generate_structured received",
    "it need to output",
    "it quotes",
    "present-tense",
    "no code fences",
    "<=2 short",
    "one immediate",
    "nonverbal action",
    "plain description",
    "[MYNX_LLM_DEBUG]",
    "[DEBUG]",
    "[ERROR]",
    "[WARNING]",
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
        u = getattr(player, "universe", None)
        return getattr(u, "story", {}) if u else {}

    @staticmethod
    def _game_tick(player):
        """Get the current game tick from player's universe, or 0."""
        u = getattr(player, "universe", None)
        return getattr(u, "game_tick", 0) if u else 0

    @staticmethod
    def _serialize_active_states(combatant: Any) -> List[Dict[str, Any]]:
        """Serialize a combatant's non-hidden active status effects."""
        return [
            {
                "name": s.name,
                "status_type": getattr(s, "statustype", "generic"),
                "beats_left": getattr(s, "beats_left", 0),
            }
            for s in getattr(combatant, "states", [])
            if not getattr(s, "hidden", False)
        ]

    def _get_event_target_modules(
        self, event, include_animations: bool = True
    ) -> List[str]:
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

    def _build_event_patches(self, target_modules) -> List[Any]:
        """Build patches that neutralize terminal timing/animation during events.

        Engine narrative output flows through the narration sink (captured via
        ``capture_narration``), and the engine no longer calls ``input()`` on any
        event/interact-reachable path (the terminal menus were removed), so input
        is no longer mocked here.  We still suppress terminal pauses
        (``await_input``), animation playback, and ``time.sleep`` so events resolve
        instantly without blocking the API request.
        """
        patches = [
            patch("time.sleep", return_value=None),
        ]

        for mod in set(target_modules):
            patches.extend(
                [
                    patch(f"{mod}.await_input", return_value=None, create=True),
                    patch(
                        f"{mod}.animate_to_main_screen",
                        return_value=None,
                        create=True,
                    ),
                    patch(f"{mod}.time.sleep", return_value=None, create=True),
                ]
            )

        return patches

    # Prefixes that indicate internal error/diagnostic output — must never reach the UI.
    _ERROR_PREFIXES = (
        "[ERROR]",
        "[WARNING]",
        "Traceback (most recent call last):",
        "  File ",
        "NameError:",
        "AttributeError:",
        "TypeError:",
        "ValueError:",
        "KeyError:",
        "IndexError:",
        "Exception:",
        "RuntimeError:",
        "DEBUG:",
    )

    def _clean_event_output(self, output: str) -> str:
        if not output:
            return ""

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        lines = output.splitlines()
        filtered_lines = [
            line
            for line in lines
            if not any(line.strip().startswith(p) for p in self._ERROR_PREFIXES)
            and not any(line.lstrip().startswith(p) for p in _LLM_NOISE_PREFIXES)
        ]
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
                for existing_id, existing in session_data.get(
                    "pending_events", {}
                ).items():
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

    def _resolve_bgm(self, tile: Any, player: Any) -> Optional[str]:
        """Resolve the BGM track for a tile.

        Checks (in order): tile-level bgm attribute, map metadata bgm, map-name fallback.
        """
        current_map = getattr(player, "map", None)
        map_metadata = (
            current_map.get("metadata", {}) if isinstance(current_map, dict) else {}
        )
        map_name = current_map.get("name") if isinstance(current_map, dict) else None

        bgm = getattr(tile, "bgm", None) or map_metadata.get("bgm")
        if not bgm and map_name:
            name_lower = map_name.lower()
            if "dark-grotto" in name_lower:
                bgm = "dark_grotto"
            elif "eastern" in name_lower:
                bgm = "eastern_descent"
            elif "verdette" in name_lower:
                bgm = "verdette_caverns"
            elif "mineral" in name_lower:
                bgm = "mineral_pools"
            elif "nomad" in name_lower:
                bgm = "nomad_camp"
            elif "grondia" in name_lower:
                bgm = "grondia"
        return bgm

    def _calculate_exits(
        self, universe, tile: Any, x: int, y: int
    ) -> Dict[str, Dict[str, int]]:
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

    def get_current_room(
        self,
        player: "player_module.Player",
        session_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Get current room/tile data.

        Args:
            player: The Player instance
            session_data: Optional session data for applying tile modifications

        Returns:
            Dictionary with room data (position, description, exits, items, npcs, objects)
        """
        # FIX 4: Add None check for universe
        if not hasattr(player, "universe") or player.universe is None:
            return {"error": "Player universe not initialized"}

        tile = player.universe.get_tile(player.location_x, player.location_y)
        if not tile:
            return {"error": "Invalid player position"}

        # Apply any stored tile modifications from session
        if session_data:
            self.apply_tile_modifications(tile, session_data)

        # On first world fetch, trigger tile events for the starting tile so
        # intro/entry events fire even though the player never "moved" there.
        if session_data is not None and not session_data.get(
            "initial_tile_events_done"
        ):
            session_data["initial_tile_events_done"] = True
            try:
                self.trigger_tile_events(player, tile, session_data)
            except Exception as e:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "Initial tile event trigger failed: %s", e
                )

        # Calculate exits dynamically by checking adjacent tiles
        exits_data = self._calculate_exits(
            player.universe, tile, player.location_x, player.location_y
        )

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

        bgm = self._resolve_bgm(tile, player)

        current_map = getattr(player, "map", None)
        map_name = current_map.get("name") if isinstance(current_map, dict) else None

        raw_name = getattr(tile, "name", None) or type(tile).__name__
        # Humanize CamelCase class names (e.g. "EmptyCave" → "Empty Cave")
        tile_name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", raw_name)

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
            "bgm": bgm,
        }

    def _record_exploration(self, player: "player_module.Player", tile: Any) -> None:
        """Record a tile as explored in the player's history.

        Args:
            player: The Player instance
            tile: The MapTile instance to record
        """
        if not hasattr(player, "explored_tiles"):
            player.explored_tiles = {}

        current_map = getattr(player, "map", None)
        map_name = current_map.get("name") if isinstance(current_map, dict) else None
        tile_key = f"{map_name}:{tile.x},{tile.y}"

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
            "exits": exits_data,
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

    def store_tile_modification(
        self,
        session_data: Dict[str, Any],
        x: int,
        y: int,
        modification_type: str,
        data: Any,
    ) -> None:
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
            tile.objects_here = [
                obj for obj in tile.objects_here if id(obj) not in removed_ids
            ]

    def move_player(
        self,
        player: "player_module.Player",
        direction: str,
        session_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Move player in specified direction.

        Args:
            player: The Player instance
            direction: Direction to move (north, south, east, west, northeast, northwest, southeast, southwest)
            session_data: Optional session dictionary for storing pending events

        Returns:
            Dictionary with result of movement
        """
        # FIX 5: Add defensive checks at method start
        if not hasattr(player, "universe") or player.universe is None:
            return {"error": "Player universe not initialized"}

        if not hasattr(player, "location_x") or not hasattr(player, "location_y"):
            return {"error": "Player position not initialized"}

        valid_directions = [
            "north",
            "south",
            "east",
            "west",
            "northeast",
            "northwest",
            "southeast",
            "southwest",
        ]
        direction_lower = direction.lower()
        if direction_lower not in valid_directions:
            return {"error": f"Invalid direction: {direction}"}

        tile = player.universe.get_tile(player.location_x, player.location_y)
        if not tile:
            return {"error": "Cannot move from this location"}

        # Calculate available exits
        available_exits = self._calculate_exits(
            player.universe, tile, player.location_x, player.location_y
        )

        if direction_lower not in available_exits:
            return {"error": f"Cannot go {direction_lower} from here"}

        # Get new coordinates from exits
        exit_data = available_exits[direction_lower]
        new_x, new_y = exit_data["x"], exit_data["y"]

        # Validate new tile exists (should always exist after exits calculation, but be safe)
        new_tile = player.universe.get_tile(new_x, new_y)
        if not new_tile:
            return {
                "error": f"Cannot move {direction_lower} - blocked or out of bounds"
            }

        # Check for blocking objects/obstacles (if tile has validation)
        if hasattr(new_tile, "is_passable") and not new_tile.is_passable:
            return {"error": f"Cannot move {direction_lower} - path is blocked"}

        # Update player position
        player.location_x = new_x
        player.location_y = new_y
        player.current_room = new_tile

        # Move any party members to the new room (mirrors the terminal behaviour).
        # recall_friends() narrates via the narration sink; capture (and discard)
        # those messages so they don't echo to stdout.
        if len(getattr(player, "combat_list_allies", [])) > 1:
            with capture_narration():
                try:
                    player.recall_friends()
                except Exception:
                    pass

        # Record exploration of the new tile
        self._record_exploration(player, new_tile)

        # Trigger tile entry events with session data for pending event storage
        events_triggered = self.trigger_tile_events(player, new_tile, session_data)

        # Run universe game-tick events (increments tick counter and fires evaluate_for_map_entry
        # spawners like NPCSpawnerEvent). The terminal game loop calls this on every action via
        # game.py; the API must do the same so map-entry spawners (e.g. Lurker) trigger correctly.
        try:
            player.universe.game_tick_events()
        except Exception as e:
            import logging as _logging

            _logging.getLogger(__name__).warning("game_tick_events failed: %s", e)

        # Store tile modifications after entry events have processed to capture state changes
        if session_data is not None:
            current_block_exit = (
                new_tile.block_exit.copy() if hasattr(new_tile, "block_exit") else []
            )
            self.store_tile_modification(
                session_data,
                new_tile.x,
                new_tile.y,
                "block_exit",
                current_block_exit,
            )

        # Check for combat initiation
        combat_enemies = check_for_combat(player)

        combat_started = False
        combat_state = None

        if combat_enemies:
            # Do not initialize the new combat while the player has unspent level-up
            # attribute points — same race-condition guard as in process_event_input.
            pending_points = int(getattr(player, "pending_attribute_points", 0) or 0)
            if pending_points > 0:
                # Stash enemies so get_combat_status can auto-resume when points hit 0
                player._combat_deferred_enemies = combat_enemies
                combat_started = False
            else:
                # Initialize combat
                self._initialize_combat(
                    player, combat_enemies, session_data=session_data
                )
                combat_started = True

                # Get initial combat state from the adapter
                if hasattr(player, "_combat_adapter"):
                    adapter_state = player._combat_adapter.get_combat_state()
                    combat_state = adapter_state.get("battle_state")
                else:
                    # Fallback to direct serialization if adapter not available
                    combat_state = CombatStateSerializer.serialize_combat_state(
                        player,
                        combat_enemies,
                        current_turn_index=getattr(player, "combat_turn_index", 0),
                        round_number=getattr(player, "combat_round", 1),
                    )

        return {
            "success": True,
            "new_position": {"x": new_x, "y": new_y},
            "events_triggered": events_triggered,
            "room": self.get_current_room(player),
            "combat_started": combat_started,
            "combat_state": combat_state,
        }

    def trigger_tile_events(
        self,
        player: "player_module.Player",
        tile: Any,
        session_data: Optional[Dict] = None,
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
            # LootEvents are created when the player interacts with a container.
            # They must NOT auto-fire on room entry — skip them here so they are
            # only processed via process_event_input when the player opens/loots.
            event_type_name = type(event).__name__
            if event_type_name == "LootEvent":
                continue

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
                try:
                    target_modules = self._get_event_target_modules(
                        event, include_animations=True
                    )
                    patches = self._build_event_patches(target_modules)

                    # Capture structured narration emitted during event processing.
                    with capture_narration() as _msgs, contextlib.ExitStack() as stack:

                        for p in patches:
                            try:
                                stack.enter_context(p)
                            except (
                                AttributeError,
                                ImportError,
                                TypeError,
                                ValueError,
                            ):
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
                    _log.exception(
                        "Event processing failed for %s",
                        getattr(event, "name", type(event).__name__),
                    )

                # Capture and clean output
                clean_output = self._clean_event_output(
                    "\n".join(m.get("text", "") for m in _msgs)
                )
                if clean_output:
                    event_data["output_text"] = clean_output

            events_triggered.append(event_data)

        return events_triggered

    def process_event_input(
        self,
        player: "player_module.Player",
        event_id: str,
        user_input: str,
        session_data: Dict,
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
        from src.api.serializers.event_serializer import EventSerializer

        # Validate event exists
        if "pending_events" not in session_data:
            return {"success": False, "error": "No pending events in session"}

        if event_id not in session_data["pending_events"]:
            return {"success": False, "error": f"Event {event_id} not found"}

        pending = session_data["pending_events"][event_id]
        event = pending["event"]

        # Process the event with user input
        result = {"success": True, "event_id": event_id}

        try:
            # Structured choices come through process(user_input=...); the engine
            # no longer calls input() on event-reachable paths.
            target_modules = self._get_event_target_modules(
                event, include_animations=False
            )
            patches = self._build_event_patches(target_modules)

            # Capture structured narration emitted during event processing.
            with capture_narration() as _msgs, contextlib.ExitStack() as stack:

                for p in patches:
                    try:
                        stack.enter_context(p)
                    except (
                        AttributeError,
                        ImportError,
                        TypeError,
                        ValueError,
                    ):
                        pass

                # Ensure event has current player and room references.
                # Prefer tile_x/tile_y stored in the pending payload (set when
                # the event was first queued) so events that reference
                # self.tile (e.g. to remove themselves from events_here) work
                # correctly even when player.current_room is None in the API.
                event.player = player
                tile_x = pending.get("tile_x")
                tile_y = pending.get("tile_y")
                if tile_x is not None and tile_y is not None:
                    event.tile = player.universe.get_tile(tile_x, tile_y)
                elif (
                    hasattr(player, "current_room") and player.current_room is not None
                ):
                    event.tile = player.current_room

                # Call process() or check_conditions()
                if hasattr(event, "process"):
                    event.process(user_input=user_input)
                elif hasattr(event, "check_conditions"):
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
                    if (
                        "pending_events" in session_data
                        and event_id in session_data["pending_events"]
                    ):
                        session_data["pending_events"][event_id]["event_data"] = result[
                            "event"
                        ]

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            _log.exception("Event input processing failed for event_id=%s", event_id)

        # Capture and clean output
        clean_output = self._clean_event_output(
            "\n".join(m.get("text", "") for m in _msgs)
        )
        if clean_output:
            result["output_text"] = clean_output

        # Check if event still needs input (persistent events)
        updated_event_data = EventSerializer.serialize_with_input(event)

        if updated_event_data.get("needs_input") and not getattr(
            event, "completed", False
        ):
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
                        if not any(
                            e.get("name") == new_event.get("name")
                            for e in result["events_triggered"]
                        ):
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
                result["combat_state"] = (
                    adapter_state.get("battle_state") or adapter_state
                )
            return result

        # Check for combat after event processing (in case event spawned enemies)
        # ONLY if the event doesn't still need input (wait for final resolution before continuing combat flow)
        combat_enemies = check_for_combat(player)

        if combat_enemies and not result.get("needs_input", False):
            # Do NOT initialize the new combat while the player still has unspent
            # level-up attribute points.  _initialize_combat emits "combat:started"
            # which races with the level-up dialog and leaves the frontend in a
            # corrupt state — subsequent allocate calls get 400s ("Not enough points")
            # because the points counter is correct but the frontend has already
            # moved to the combat screen.
            #
            # Since the aggro NPCs remain in the room, check_for_combat will find
            # them again on the very next player action (move / event input) and
            # combat will initialize cleanly after level-up is resolved.
            pending_points = int(getattr(player, "pending_attribute_points", 0) or 0)
            if pending_points > 0:
                result["combat_started"] = False
                result["combat_deferred"] = True
                result["combat_deferred_reason"] = "level_up_pending"
                # Stash enemies so get_combat_status can auto-resume when points hit 0
                player._combat_deferred_enemies = combat_enemies
            else:
                # Initialize combat
                self._initialize_combat(
                    player, combat_enemies, session_data=session_data
                )
                result["combat_started"] = True

                # Get initial combat state
                if hasattr(player, "_combat_adapter"):
                    adapter_state = player._combat_adapter.get_combat_state()
                    # If we resumed a move, the adapter state already contains the full battle_state
                    result["combat_state"] = (
                        adapter_state.get("battle_state") or adapter_state
                    )
                else:
                    # Fallback to direct serialization (CombatStateSerializer already imported at module level)
                    result["combat_state"] = (
                        CombatStateSerializer.serialize_combat_state(
                            player,
                            combat_enemies,
                            current_turn_index=getattr(player, "combat_turn_index", 0),
                            round_number=getattr(player, "combat_round", 1),
                        )
                    )
        elif combat_enemies:
            # Combat is present but we are paused for narrative
            result["combat_started"] = True
        else:
            result["combat_started"] = False

        return result

    def get_tile(
        self, player: "player_module.Player", x: int, y: int
    ) -> Dict[str, Any]:
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
        objects_data = ObjectSerializer.serialize_list(
            getattr(tile, "objects_here", [])
        )
        events_data = EventSerializer.serialize_list(getattr(tile, "events_here", []))

        # Get exits/connections using the same calculated approach as get_current_room
        exits_data = self._calculate_exits(player.universe, tile, x, y)

        bgm = self._resolve_bgm(tile, player)

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
            "bgm": bgm,
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

        search_ability = int(
            ((finesse * 2) + (intelligence * 3) + faith) * random.uniform(0.5, 1.5)
        )

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
                        discovery_msg = getattr(
                            npc,
                            "discovery_message",
                            f"a hidden {getattr(npc, 'name', 'NPC')}",
                        )
                        messages.append(f"{player.name} uncovered {discovery_msg}")
                        something_found = True
                        found_items.append(
                            {
                                "type": "npc",
                                "name": getattr(npc, "name", "Unknown"),
                                "id": str(id(npc)),
                            }
                        )

        # Check Items
        items_to_remove = []
        if hasattr(tile, "items_here"):
            for item in tile.items_here:
                if getattr(item, "hidden", False):
                    hide_factor = getattr(item, "hide_factor", 0)
                    if search_ability > hide_factor:
                        item.hidden = False
                        discovery_msg = getattr(
                            item,
                            "discovery_message",
                            f"a hidden {getattr(item, 'name', 'Item')}",
                        )
                        something_found = True
                        found_entry = {
                            "type": "item",
                            "name": getattr(item, "name", "Unknown"),
                            "id": str(id(item)),
                        }

                        # Auto-take items with hide_factor == 0 (intentionally findable)
                        if hide_factor == 0:
                            inventory = getattr(
                                player, "inventory_list", None
                            ) or getattr(player, "inventory", [])
                            if isinstance(inventory, list):
                                total_weight = sum(
                                    getattr(i, "weight", 0) for i in inventory
                                )
                                capacity = getattr(player, "weight_tolerance", 20.0)
                                item_weight = getattr(item, "weight", 0)
                                if total_weight + item_weight <= capacity:
                                    inventory.append(item)
                                    items_to_remove.append(item)
                                    found_entry["auto_taken"] = True
                                    messages.append(
                                        f"{player.name} finds {discovery_msg} and takes it."
                                    )
                                else:
                                    messages.append(
                                        f"{player.name} found {discovery_msg}"
                                    )
                            else:
                                messages.append(f"{player.name} found {discovery_msg}")
                        else:
                            messages.append(f"{player.name} found {discovery_msg}")

                        found_items.append(found_entry)

        for item in items_to_remove:
            if hasattr(tile, "items_here") and item in tile.items_here:
                tile.items_here.remove(item)

        if items_to_remove and hasattr(player, "stack_inv_items"):
            player.stack_inv_items()

        # Check Objects
        if hasattr(tile, "objects_here"):
            for obj in tile.objects_here:
                if getattr(obj, "hidden", False):
                    hide_factor = getattr(obj, "hide_factor", 0)
                    if search_ability > hide_factor:
                        obj.hidden = False
                        discovery_msg = getattr(
                            obj,
                            "discovery_message",
                            f"a hidden {getattr(obj, 'name', 'Object')}",
                        )
                        messages.append(f"{player.name} found {discovery_msg}")
                        something_found = True
                        found_items.append(
                            {
                                "type": "object",
                                "name": getattr(obj, "name", "Unknown"),
                                "id": str(id(obj)),
                            }
                        )

        if not something_found:
            messages.append(
                f"{player.name} searches around the area... but couldn't find anything of interest."
            )
        else:
            messages.insert(0, f"{player.name} searches around the area...")

        return {
            "success": True,
            "messages": messages,
            "found": found_items,
            "room": self.get_current_room(player),  # Return updated room data
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
        session_data: Optional[Dict] = None,
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
                is_container = type(obj).__name__ == "Container" or isinstance(
                    obj, Container
                )
                if (
                    is_container
                    and getattr(obj, "state", "") == "opened"
                    and hasattr(obj, "inventory")
                ):
                    for item in obj.inventory:
                        if str(id(item)) == target_id:
                            target = item
                            target._parent_container = obj
                            break
                if target:
                    break

        if not target:
            return {"success": False, "message": "Target not found."}

        # Special case: attack action on NPCs should start combat
        if action.lower() == "attack":
            # Check if target is an NPC by looking in current tile's NPCs
            is_npc = hasattr(tile, "npcs_here") and target in tile.npcs_here
            if is_npc:
                # Redirect to start_combat instead of trying to call attack() method
                combat_result = self.start_combat(player, target_id)
                # Wrap start_combat response to match interact_with_target format
                if "error" in combat_result:
                    return {"success": False, "message": combat_result["error"]}
                else:
                    # Combat started successfully
                    return {
                        "success": True,
                        "message": f"Combat started with {target.name}!",
                        "combat_data": combat_result,
                    }

        is_valid = False
        if hasattr(target, "keywords") and action in target.keywords:
            is_valid = True
        elif hasattr(target, action):
            # Allow calling method if it exists, even if not in keywords (fallback)
            is_valid = True

        if not is_valid:
            return {
                "success": False,
                "message": f"Cannot {action} this target.",
            }

        # Record pre-action location to detect passageway teleportation
        _pre_map_name = player.map.get("name") if player.map else None
        _pre_x = player.location_x
        _pre_y = player.location_y

        # Execute action and capture output
        events_triggered = []
        try:
            # Narrative output is captured via the narration sink; we still
            # neutralize terminal pauses/timing. Interaction targets no longer
            # call input() (the terminal item/object menus were removed).
            with (
                capture_narration() as _msgs,
                patch("functions.await_input", return_value=None),
                patch("time.sleep", return_value=None),
                patch("src.functions.await_input", return_value=None),
            ):

                try:
                    from objects import Container
                except ImportError:
                    from src.objects import Container
                try:
                    from items import Item
                except ImportError:
                    from src.items import Item
                try:
                    from inventory_utils import transfer_item
                except ImportError:
                    from src.inventory_utils import transfer_item
                try:
                    from events import LootEvent
                except ImportError:
                    from src.events import LootEvent

                is_container = type(target).__name__ == "Container" or isinstance(
                    target, Container
                )
                # More robust item check that handles subclasses and module mismatches
                item_types = [
                    "Item",
                    "Weapon",
                    "Armor",
                    "Consumable",
                    "Gold",
                    "Key",
                    "Tool",
                    "Usable",
                ]
                is_item = (
                    type(target).__name__ in item_types
                    or isinstance(target, Item)
                    or hasattr(target, "_parent_container")
                )

                if is_container and action in [
                    "loot",
                    "check",
                    "view",
                    "examine",
                    "inspect",
                    "peruse",
                ]:
                    target.open()
                    # Only surface the loot menu if the container actually
                    # opened. A locked container's open() is a no-op (state
                    # stays "closed"); creating a LootEvent anyway would expose
                    # its contents and bypass the lock. open() narrates why it
                    # failed, which flows out via the narration sink below.
                    if getattr(target, "state", None) == "opened":
                        # Create a LootEvent and store it
                        loot_event = LootEvent(
                            f"Looting {target.name}", player, tile, target
                        )
                        event_data = EventSerializer.serialize_with_input(
                            loot_event
                        )

                        if session_data is not None:
                            event_id = str(uuid.uuid4())
                            event_data["event_id"] = event_id

                            if "pending_events" not in session_data:
                                session_data["pending_events"] = {}
                            session_data["pending_events"][event_id] = {
                                "event": loot_event,
                                "tile_x": tile.x,
                                "tile_y": tile.y,
                                "event_data": event_data,
                            }

                        events_triggered.append(event_data)
                elif (
                    is_item
                    and action in ["take", "equip"]
                    and hasattr(target, "_parent_container")
                ):
                    # Use transfer_item for items in containers
                    qty_to_take = (
                        quantity
                        if quantity is not None
                        else getattr(target, "count", 1)
                    )
                    transfer_item(target._parent_container, player, target, qty_to_take)
                    if hasattr(target._parent_container, "refresh_description"):
                        target._parent_container.refresh_description()

                    if action == "take":
                        narrate(f"{player.name} takes {target.name}.")
                    else:
                        # Proceed with equipment logic
                        target.equip(player)
                else:
                    method = getattr(target, action)
                    # Check signature to see if we need to pass player
                    sig = inspect.signature(method)
                    # Get parameter names excluding 'self'
                    param_names = [p for p in sig.parameters.keys() if p != "self"]

                    # If there are parameters beyond 'self', pass player
                    if len(param_names) > 0:
                        # If the method accepts quantity, pass it
                        if "quantity" in param_names:
                            method(player, quantity=quantity)
                        else:
                            method(player)
                    else:
                        method()

        except Exception as e:
            _log.exception("interact_with_target action failed")
            return {
                "success": False,
                "message": f"Error executing action: {str(e)}",
            }

        output = "\n".join(m.get("text", "") for m in _msgs)

        # Clean up output (remove ANSI codes)
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_output = ansi_escape.sub("", output)

        # Remove excessive newlines and clean up whitespace
        clean_output = re.sub(
            r"\n\s*\n", "\n", clean_output
        )  # Replace multiple newlines with single
        clean_output = clean_output.strip()

        # If a teleport occurred, strip the destination tile's description from the
        # interaction output — the frontend fetches the new room via /world/current-room.
        _post_map_name = player.map.get("name") if player.map else None
        if _post_map_name != _pre_map_name or player.location_x != _pre_x or player.location_y != _pre_y:
            dest_tile = player.universe.get_tile(player.location_x, player.location_y)
            if dest_tile and hasattr(dest_tile, "description"):
                dest_desc = ansi_escape.sub("", dest_tile.description).strip()
                if dest_desc:
                    clean_output = clean_output.replace(dest_desc, "").strip()

        # Strip internal LLM diagnostic lines that must never reach the UI.
        pre_filter_output = clean_output
        filtered_lines = [
            line
            for line in clean_output.splitlines()
            if not any(line.lstrip().startswith(p) for p in _LLM_NOISE_PREFIXES)
        ]
        clean_output = "\n".join(filtered_lines).strip()

        # If filtering removed everything and the raw output contained LLM noise
        # (indicating a Mynx LLM call occurred), use a safe ambient fallback.
        if not clean_output and any(
            p in pre_filter_output for p in _LLM_NOISE_PREFIXES
        ):
            clean_output = (
                "The Mynx shifts its weight, bioluminescent patches pulsing faintly."
            )

        # Provide fallback message if no output was captured
        if not clean_output:
            if action == "take_all":
                clean_output = "Jean collects all of the available items."
            elif action == "talk":
                target_name = getattr(target, "name", None)
                clean_output = (
                    f"{target_name} does not respond."
                    if target_name
                    else "No response."
                )
            else:
                clean_output = f"Jean successfully completes the '{action}' action."

        # Trigger tile events after action execution to handle state changes (e.g., chest looted or wall opened)
        more_events = self.trigger_tile_events(player, tile, session_data)
        if more_events:
            for new_event in more_events:
                # Avoid duplicates if they somehow got in
                if not any(
                    e.get("name") == new_event.get("name") for e in events_triggered
                ):
                    events_triggered.append(new_event)

        # Store tile modifications AFTER all events have processed to capture state changes
        if session_data is not None:
            # 1. Store blocked exits
            current_block_exit = (
                tile.block_exit.copy() if hasattr(tile, "block_exit") else []
            )
            self.store_tile_modification(
                session_data, tile.x, tile.y, "block_exit", current_block_exit
            )

            # 2. Store removed objects (using object names as stable identifiers)
            if hasattr(tile, "objects_here"):
                # We need to consider what was there originally vs now
                # This is a bit complex in a stateless environment, but for now
                # we'll trust that the event removed what it needed to.
                pass

        # Check for combat initiation
        combat_enemies = check_for_combat(player)

        combat_started = False
        combat_state = None

        if combat_enemies:
            # Initialize combat
            self._initialize_combat(player, combat_enemies, session_data=session_data)
            combat_started = True

            # Get initial combat state from the adapter
            if hasattr(player, "_combat_adapter"):
                adapter_state = player._combat_adapter.get_combat_state()
                combat_state = adapter_state.get("battle_state")
            else:
                # Fallback to direct serialization if adapter not available
                combat_state = CombatStateSerializer.serialize_combat_state(
                    player,
                    combat_enemies,
                    current_turn_index=getattr(player, "combat_turn_index", 0),
                    round_number=getattr(player, "combat_round", 1),
                )

        # Detect if player teleported
        teleported = _post_map_name != _pre_map_name or player.location_x != _pre_x or player.location_y != _pre_y

        return {
            "success": True,
            "message": clean_output,
            "target_name": getattr(target, "name", "Unknown"),
            "action": action,
            "events_triggered": events_triggered,
            "combat_started": combat_started,
            "combat_state": combat_state,
            "object_state": {
                "keywords": getattr(target, "keywords", []),
                "locked": getattr(target, "locked", False),
                "state": getattr(target, "state", ""),
            },
            "teleported": teleported,
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

    # ========================
    # Combat Methods
    # ========================

    # ========================
    # ========================
    # Combat Methods
    # ========================

    def trigger_combat_events(
        self,
        player: "player_module.Player",
        session_data: Dict[str, Any] = None,
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
            method_name = (
                "check_combat_conditions"
                if hasattr(event, "check_combat_conditions")
                else "check_conditions"
            )

            if hasattr(event, method_name):
                try:
                    target_modules = self._get_event_target_modules(
                        event, include_animations=True
                    )
                    patches = self._build_event_patches(target_modules)

                    # Capture structured narration emitted during processing.
                    with capture_narration() as _msgs, contextlib.ExitStack() as stack:

                        for p in patches:
                            try:
                                stack.enter_context(p)
                            except (
                                AttributeError,
                                ImportError,
                                TypeError,
                                ValueError,
                                Exception,
                            ):
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
                clean_output = self._clean_event_output(
                    "\n".join(m.get("text", "") for m in _msgs)
                )
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

    def start_combat(
        self,
        player: "player_module.Player",
        enemy_id: str,
        session_id: str = None,
    ) -> Dict[str, Any]:
        """Start combat with a specific enemy (e.g. from dialogue/interaction)."""
        # Find enemy in current room
        enemy = None
        tile = None

        # 1. Try universe tile
        if hasattr(player, "universe") and player.universe:
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

        # Ensure player.current_room is set to the resolved tile so that downstream
        # code (NPC death cleanup, event callbacks) always has a valid room reference.
        # Fall back to the existing player.current_room when universe.get_tile() returned
        # None (e.g. out-of-bounds coordinates) — at least one of the two will be valid
        # because we already found `enemy` through one of those two paths above.
        if tile is None:
            tile = getattr(player, "current_room", None)
        if tile is not None:
            player.current_room = tile

        # Mark the attacked enemy as aggro so it is always included in the combat roster.
        # Some enemies may already be aggro from room-entry announcements; the clicked one
        # may not be if the player attacked before passive detection triggered.
        enemy.aggro = True
        enemy.in_combat = True

        # Collect ALL aggro, non-friend NPCs from the tile directly — bypassing the random
        # finesse roll used by check_for_combat().  When the player deliberately chooses to
        # attack, stealth detection is irrelevant: every hostile creature in the room joins.
        # This mirrors what move_player() achieves in practice and prevents the
        # "one enemy enters, rest stay" bug that left combat stuck after the first kill.
        all_enemies = [
            npc for npc in getattr(tile, "npcs_here", [])
            if not getattr(npc, "friend", False)
            and getattr(npc, "aggro", False)
            and npc is not enemy  # enemy already forced-aggro above; prepend it below
        ]
        # Prepend the clicked enemy so it leads the combat roster regardless of list order.
        all_enemies.insert(0, enemy)
        # Propagate in_combat flag to every enrolled hostile (check_for_combat does the same).
        for e in all_enemies:
            e.in_combat = True

        result = self._initialize_combat(player, all_enemies, session_id=session_id)

        # _initialize_combat returns None in the idempotency branch (already in combat
        # with the same enemy set).  Treat this as a graceful no-op.
        if result is None:
            return {"error": "Already in combat with these enemies"}

        # Attach API-contract fields so routes don't need to reach into player internals
        combatants = [
            {
                "id": "player",
                "name": getattr(player, "name", "Jean Claire"),
                "is_player": True,
                "is_ally": False,
            }
        ]
        # combat_list_allies[0] is always the player — skip it to avoid a duplicate
        # entry in the combatants list (same pattern as the [1:] slice at line ~1898).
        for ally in getattr(player, "combat_list_allies", [])[1:]:
            combatants.append(
                {
                    "id": f"ally_{id(ally)}",
                    "name": getattr(ally, "name", "Ally"),
                    "is_player": False,
                    "is_ally": True,
                }
            )
        for e in getattr(player, "combat_list", []):
            combatants.append(
                {
                    "id": f"enemy_{id(e)}",
                    "name": getattr(e, "name", "Enemy"),
                    "is_player": False,
                    "is_ally": False,
                }
            )
        result["combat_id"] = str(uuid.uuid4())
        result["combatants"] = combatants
        result["turn_order"] = [c["id"] for c in combatants]
        return result

    def execute_move(
        self,
        player: "player_module.Player",
        move_type: str,
        move_id: str,
        target_id: str = None,
        direction: str = None,
        session_id: str = None,
        session_data: Dict = None,
    ) -> Dict[str, Any]:
        """Execute a combat move."""

        # Check if player is in combat
        if not player.in_combat:
            return {"success": False, "error": "Not in combat"}

        # Check for blocking pending events - events that need input should block combat moves
        # This prevents players from acting before event dialogs appear (e.g., rumbler announcement)
        if session_data and session_data.get("pending_events"):
            # Only block if there are events that actually need input (not stale/completed events)
            blocking_events = [
                e
                for e in session_data["pending_events"].values()
                if e.get("event_data", {}).get("needs_input")
                and not e.get("event_data", {}).get("completed")
            ]
            if blocking_events:
                return {
                    "success": False,
                    "error": "Event pending",
                    "message": "Please resolve the current event before taking combat actions.",
                    "pending_events_count": len(blocking_events),
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

            player._combat_adapter = ApiCombatAdapter(
                player, session_id=session_id, on_event_callback=event_callback
            )
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

        # Check if adapter is ready for input (unless cancelling/fleeing, which should always be allowed)
        if not adapter.awaiting_input and move_type not in ("cancel", "flee"):
            return {
                "error": "Not awaiting input",
                "details": f"awaiting_input={adapter.awaiting_input}, input_type={adapter.input_type}",
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
                    opt_name = (
                        option.get("name")
                        if isinstance(option, dict)
                        else getattr(option, "name", "")
                    )
                    if opt_name == move_id:
                        # Use the 'index' field from the option, not the loop index
                        move_index = (
                            option.get("index", i)
                            if isinstance(option, dict)
                            else getattr(option, "index", i)
                        )
                        break

            if move_index is None:
                return {"error": f"Invalid move ID or name: {move_id}"}

            command = {"type": "select_move", "move_index": move_index}

            result = adapter.process_command(command)

            # Auto-handle targeting if we have a target_id and the move requires it
            if (
                not result.get("error")
                and result.get("battle_state", {}).get("input_type")
                == "target_selection"
                and target_id
            ):
                # Only auto-send target if it's likely a valid ID
                if target_id and target_id != "player":
                    target_command = {
                        "type": "select_target",
                        "target_id": target_id,
                    }
                    result = adapter.process_command(target_command)
                    # Note: If the move needs additional input after targeting (e.g., distance),
                    # result will now contain that input_type (e.g., 'number_input') and will be
                    # returned to the client for further input.

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

        elif move_type == "flee":
            return self.flee_combat(player)

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
                "target_id": actual_target_id,
            }
            return adapter.process_command(command)

        else:
            return {"error": f"Unknown move type: {move_type}"}

    def get_combat_status(
        self,
        player: "player_module.Player",
        session_id: str = None,
        session_data: Dict = None,
    ) -> Dict[str, Any]:
        """Get current combat status."""
        # If a previous combat initialization was deferred (level-up pending) and the
        # player has now spent all their attribute points, auto-resume the deferred
        # combat. The frontend calls fetchCombatStatus() after every allocation, so the
        # last point spent will trigger this path and start combat seamlessly.
        deferred_enemies = getattr(player, "_combat_deferred_enemies", None)
        pending_points = int(getattr(player, "pending_attribute_points", 0) or 0)
        if deferred_enemies and pending_points == 0:
            player._combat_deferred_enemies = None
            self._initialize_combat(
                player,
                deferred_enemies,
                session_id=session_id,
                session_data=session_data,
            )

            # If player is in combat, try to re-initialize the adapter
            if getattr(player, "in_combat", False) and hasattr(player, "combat_list"):
                from src.api.combat_adapter import ApiCombatAdapter

                # Ensure the new adapter has the event callback
                def event_callback(p):
                    return self.trigger_combat_events(p)

                player._combat_adapter = ApiCombatAdapter(
                    player,
                    session_id=session_id,
                    on_event_callback=event_callback,
                )
                # Synchronize initial state for the new adapter
                player._combat_adapter.available_options = (
                    player._combat_adapter._get_available_moves()
                )
                # Kick off suggestions once for the re-initialized adapter
                if not getattr(player, "suggestions_loading", False):
                    player._combat_adapter.refresh_suggestions()
            else:
                return {
                    "combat_active": getattr(player, "in_combat", False),
                    "log": getattr(player, "combat_log", []),
                    "battle_state": None,
                }
        else:
            if not hasattr(player, "_combat_adapter"):
                return {
                    "combat_active": getattr(player, "in_combat", False),
                    "log": getattr(player, "combat_log", []),
                    "battle_state": None,
                }
            adapter = player._combat_adapter

            # Resume logic: If battle is active but not awaiting input, check why
            # This handles cases where combat was paused for narrative events
            if player.in_combat and not adapter.awaiting_input:
                blocking_events = (
                    session_data.get("pending_events", {}) if session_data else {}
                )
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
                if not getattr(player, "suggestions_loading", False) and not getattr(
                    player, "suggested_moves", []
                ):
                    adapter.refresh_suggestions()

        # After combat ends, surface any post-combat tile events (e.g.
        # AfterDefeatingKingSlime) through the standard trigger_tile_events
        # pipeline so print_slow output is captured as event dialog text.
        # The flag prevents re-firing on subsequent polls; the event removes
        # itself from tile.events_here, so duplicate calls are also harmless.
        _adapter = getattr(player, "_combat_adapter", None)
        if (
            _adapter is not None
            and not getattr(player, "in_combat", False)
            and not getattr(_adapter, "_post_combat_tile_events_fired", False)
        ):
            _adapter._post_combat_tile_events_fired = True
            # Use the tile captured at victory time, not the current room —
            # the player may have moved before this poll.
            _tile = getattr(_adapter, "_combat_tile", None) or getattr(
                player, "current_room", None
            )
            if _tile:
                if session_data is None:
                    _log.warning(
                        "post-combat tile events fired without session_data; "
                        "interactive events cannot be queued"
                    )
                try:
                    post_events = self.trigger_tile_events(player, _tile, session_data)
                    if post_events:
                        if not hasattr(player, "combat_adapter_state"):
                            player.combat_adapter_state = {}
                        existing = player.combat_adapter_state.get(
                            "events_triggered", []
                        )
                        existing.extend(post_events)
                        player.combat_adapter_state["events_triggered"] = existing
                except Exception:
                    _log.exception("Post-combat tile event processing failed")

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
                    name = (
                        move.get("name")
                        if isinstance(move, dict)
                        else getattr(move, "name", "Unknown")
                    )
                    description = (
                        move.get("description")
                        if isinstance(move, dict)
                        else getattr(move, "description", "")
                    )
                    fatigue_cost = (
                        move.get("fatigue_cost")
                        if isinstance(move, dict)
                        else getattr(move, "fatigue_cost", 0)
                    )
                    category = (
                        move.get("category")
                        if isinstance(move, dict)
                        else getattr(move, "category", "Miscellaneous")
                    )
                    beats_left = (
                        move.get("beats_left")
                        if isinstance(move, dict)
                        else getattr(move, "beats_left", 0)
                    )

                    moves.append(
                        {
                            "id": str(i),
                            "name": name,
                            "description": description,
                            "fatigue_cost": fatigue_cost,
                            "category": category,
                            "beats_left": beats_left,
                        }
                    )

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
        max_weight = getattr(player, "weight_tolerance", 20.0)
        weight_pct = (weight / max_weight * 100) if max_weight > 0 else 0

        player_states = self._serialize_active_states(player)

        return {
            "name": getattr(player, "name", "Unknown"),
            "level": getattr(player, "level", 1),
            "exp": getattr(player, "exp", 0),
            "max_exp": getattr(player, "exp_to_level", 100),
            "exp_to_next_level": int(
                max(0, (getattr(player, "exp_to_level", 0) or 0) - (getattr(player, "exp", 0) or 0))
            ),
            "pending_attribute_points": int(getattr(player, "pending_attribute_points", 0) or 0),
            "pending_level_ups": list(getattr(player, "pending_level_ups", None) or []),
            "hp": getattr(player, "hp", 0),
            "max_hp": getattr(player, "maxhp", 0),
            "fatigue": getattr(player, "fatigue", 0),
            "max_fatigue": getattr(player, "maxfatigue", 0),
            "gold": get_gold(getattr(player, "inventory", [])),
            "weight": weight,
            "max_weight": max_weight,
            "weight_pct": weight_pct,
            "state": player_states[0]["name"] if player_states else "normal",
            "states": player_states,
            "party_members": [
                {
                    "id": f"ally_{id(a)}",
                    "name": getattr(a, "name", "Unknown"),
                    "hp": getattr(a, "hp", 0),
                    "max_hp": getattr(a, "maxhp", 0),
                    "fatigue": getattr(a, "fatigue", 0),
                    "max_fatigue": getattr(a, "maxfatigue", 0),
                    "level": getattr(a, "level", 1),
                    "description": getattr(a, "description", "").strip(),
                    "in_range": (
                        getattr(player, "combat_proximity", {}).get(a, 0)
                        <= ITEM_USE_RANGE
                        if getattr(player, "in_combat", False)
                        else True
                    ),
                    "states": self._serialize_active_states(a),
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
        max_weight = getattr(player, "weight_tolerance", 20.0)

        stats["weight_current"] = weight
        stats["carrying_capacity"] = max_weight
        stats["weight"] = weight
        stats["max_weight"] = max_weight
        stats["gold"] = get_gold(getattr(player, "inventory", []))
        stats["protection"] = round(getattr(player, "protection", 0))

        # Calculate combat stats
        weapon = getattr(player, "eq_weapon", None)
        if weapon:
            power = (
                getattr(weapon, "damage", 0)
                + (getattr(player, "strength", 10) * getattr(weapon, "str_mod", 0))
                + (getattr(player, "finesse", 10) * getattr(weapon, "fin_mod", 0))
            )

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
        stats["states"] = [
            {"name": state.name, "steps_left": state.steps_left}
            for state in getattr(player, "states", [])
        ]

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
            known_moves.append(
                {
                    "name": getattr(move, "name", "Unknown"),
                    "category": getattr(move, "category", "Miscellaneous"),
                    "description": getattr(move, "description", ""),
                    "fatigue_cost": getattr(move, "fatigue_cost", 0),
                    "beats_left": getattr(move, "beats_left", 0),
                    "xp_gain": getattr(move, "xp_gain", 0),
                }
            )

        skill_tree = {}
        if hasattr(player, "skilltree") and hasattr(player.skilltree, "subtypes"):
            for category, skills in player.skilltree.subtypes.items():
                category_skills = []
                for skill, req_exp in skills.items():
                    # Check if already known
                    is_known = any(km["name"] == skill.name for km in known_moves)

                    stat_ok = (
                        not hasattr(skill, "learnable_when")
                        or skill.learnable_when(player)
                    )

                    # Stat-gated mastery skills stay hidden entirely until their
                    # linked stat is dominant — don't show them as a disabled
                    # option the player can never act on.
                    if not stat_ok and not is_known:
                        continue

                    category_skills.append(
                        {
                            "name": skill.name,
                            "description": getattr(skill, "description", ""),
                            "required_exp": req_exp,
                            "is_known": is_known,
                            "can_learn": (
                                player.skill_exp.get(category, 0) >= req_exp
                                and not is_known
                                and stat_ok
                            ),
                        }
                    )
                skill_tree[category] = category_skills

        return {
            "known_moves": known_moves,
            "skill_exp": getattr(player, "skill_exp", {}),
            "skill_tree": skill_tree,
        }

    def learn_skill(
        self, player: "player_module.Player", skill_name: str, category: str
    ) -> Dict[str, Any]:
        """Learn a skill from the skill tree.

        Args:
            player: The Player instance
            skill_name: Name of the skill to learn
            category: Skill category (e.g. "Basic", "Dagger")

        Returns:
            Dictionary with result
        """
        if not hasattr(player, "skilltree") or not hasattr(
            player.skilltree, "subtypes"
        ):
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
            return {
                "success": False,
                "error": f"Skill '{skill_name}' not found in category '{category}'",
            }

        # Check if already known
        for move in player.known_moves:
            if move.name == skill_name:
                return {"success": False, "error": "Skill already learned"}

        # Check experience
        current_exp = player.skill_exp.get(category, 0)
        if current_exp < req_exp:
            return {
                "success": False,
                "error": f"Not enough experience. Required: {req_exp}, Available: {current_exp}",
            }

        # Check stat requirements (mastery skills)
        if hasattr(skill_obj, "learnable_when") and not skill_obj.learnable_when(player):
            return {
                "success": False,
                "error": "Stat requirements not met. This skill requires its linked stat to exceed 30 and be your highest.",
            }

        # Learn the skill
        player.learn_skill(skill_obj)
        player.skill_exp[category] -= req_exp

        return {
            "success": True,
            "message": f"Learned {skill_name}!",
            "remaining_exp": player.skill_exp[category],
            "skills": self.get_player_skills(player),
        }

    def allocate_level_up_points(
        self, player: "player_module.Player", attribute: Optional[str], amount: Any
    ) -> Dict[str, Any]:
        """Allocate pending attribute points to a stat, or randomize distribution.

        Args:
            player: The Player instance
            attribute: One of the allowed attribute keys, or "randomize"
            amount: Points to allocate (ignored when attribute == "randomize")

        Returns:
            Dictionary with result. On success: {"success": True,
            "remaining_points": int, "stats": {...}}.
        """
        allowed = {
            "strength_base",
            "finesse_base",
            "speed_base",
            "endurance_base",
            "charisma_base",
            "intelligence_base",
            "faith_base",
            "randomize",
        }

        if attribute not in allowed:
            return {"success": False, "error": "Invalid attribute"}

        remaining = int(getattr(player, "pending_attribute_points", 0) or 0)

        if attribute == "randomize":
            if remaining <= 0:
                return {"success": False, "error": "No pending points to randomize"}

            import random

            attributes_list = [
                "strength_base",
                "finesse_base",
                "speed_base",
                "endurance_base",
                "charisma_base",
                "intelligence_base",
                "faith_base",
            ]
            weights = [random.random() for _ in attributes_list]
            remaining_points = remaining
            for idx, attr in enumerate(attributes_list):
                if idx == len(attributes_list) - 1:
                    share = remaining_points
                else:
                    sum_remaining_weights = sum(weights[idx:])
                    if sum_remaining_weights == 0:
                        share = 0
                    else:
                        share = round(
                            weights[idx] / sum_remaining_weights * remaining_points
                        )
                remaining_points -= share
                setattr(player, attr, int(getattr(player, attr, 0) or 0) + share)

            player.pending_attribute_points = 0
        else:
            try:
                amount_int = int(amount)
            except Exception:
                return {"success": False, "error": "Invalid amount"}

            if amount_int <= 0:
                return {"success": False, "error": "Amount must be positive"}

            if amount_int > remaining:
                return {"success": False, "error": "Not enough points"}

            setattr(
                player,
                attribute,
                int(getattr(player, attribute, 0) or 0) + amount_int,
            )
            player.pending_attribute_points = remaining - amount_int

        # Clear stale level-up events once all points are spent so they don't
        # accumulate across sessions and re-trigger SFX on future status polls.
        if player.pending_attribute_points == 0 and hasattr(
            player, "pending_level_ups"
        ):
            player.pending_level_ups = []

        try:
            from src import functions

            functions.refresh_stat_bonuses(player)
        except Exception:
            pass

        return {
            "success": True,
            "remaining_points": int(player.pending_attribute_points),
            "stats": self.get_player_stats(player),
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
                available_actions = current_tile.available_actions(
                    callerIsApi=True, player=player
                )
                for action in available_actions:
                    commands.append(
                        {
                            "name": getattr(action, "name", "Unknown"),
                            "hotkey": getattr(action, "hotkey", []),
                            "debug": getattr(action, "debug", False),
                        }
                    )
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

        base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        saves_dir = os.path.join(base_path, "saves")
        if not os.path.exists(saves_dir):
            os.makedirs(saves_dir)
        return saves_dir

    async def save_game(
        self,
        player: "player_module.Player",
        name: str,
        user_id: str,
        is_autosave: bool = False,
    ) -> str:
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
        from src.api.db import db

        # 1. Enforcement of manual save limit
        if not is_autosave:
            count_sql = (
                "SELECT COUNT(*) FROM saves WHERE user_id = ? AND is_autosave = FALSE"
            )
            res = await db.execute(count_sql, [user_id])
            count = res.rows[0][0]
            if count >= 20:
                raise ValueError(
                    "Maximum number of manual saves reached (20). Please delete an existing save to create a new one."
                )

        save_id = str(uuid.uuid4())

        # Serialize player state.
        # _combat_adapter holds a closure and a threading.Lock — neither is picklable.
        # Strip it before serializing; restore immediately after.
        combat_adapter = player.__dict__.pop("_combat_adapter", None)
        try:
            save_data = pickle.dumps(player, protocol=pickle.HIGHEST_PROTOCOL)
        finally:
            if combat_adapter is not None:
                player._combat_adapter = combat_adapter

        # Derive save metadata from current player state
        _map = getattr(player, "map", None)
        _map_name = (
            _map.get("name", "Unknown")
            if isinstance(_map, dict)
            else getattr(_map, "name", "Unknown")
        )
        _tile = getattr(player, "current_room", None)
        if _tile is not None:
            _raw = getattr(_tile, "name", None) or type(_tile).__name__
            _room_title = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", _raw)
        else:
            _room_title = "Unknown"

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
                    _map_name,
                    _room_title,
                    getattr(player, "time_elapsed", 0),
                    save_id,
                ]
            else:
                # Create first autosave
                sql = """
                INSERT INTO saves (id, user_id, name, data, is_autosave, level, map_name, room_title, playtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = [
                    save_id,
                    user_id,
                    "Autosave",
                    save_data,
                    True,
                    getattr(player, "level", 1),
                    _map_name,
                    _room_title,
                    getattr(player, "time_elapsed", 0),
                ]
        else:
            # Manual save
            sql = """
            INSERT INTO saves (id, user_id, name, data, is_autosave, level, map_name, room_title, playtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = [
                save_id,
                user_id,
                name,
                save_data,
                False,
                getattr(player, "level", 1),
                _map_name,
                _room_title,
                getattr(player, "time_elapsed", 0),
            ]

        await db.execute(sql, params)
        return save_id

    async def load_game(
        self, save_id: str, user_id: str
    ) -> Optional["player_module.Player"]:
        """Load a saved game from Turso.

        Args:
            save_id: ID of save to load
            user_id: The DB user ID (for security validation)

        Returns:
            Loaded Player instance or None
        """
        from src.api.db import db

        sql = "SELECT data FROM saves WHERE id = ? AND user_id = ?"
        result = await db.execute(sql, [save_id, user_id])

        if not result.rows:
            return None

        try:
            import io
            from src.functions import _safe_pickle_load

            save_data = result.rows[0][0]
            player = _safe_pickle_load(io.BytesIO(save_data))

            if player is None:
                print(f"Error loading save {save_id}: _safe_pickle_load returned None")
                return None

            if player:
                # Re-initialize universe connections
                if not hasattr(player, "universe") or player.universe is None:
                    import src.universe as universe_module

                    player.universe = universe_module.Universe(player)

                # Force rebuild of transient state if needed
                if not hasattr(player.universe, "maps") or not player.universe.maps:
                    player.universe.build(player)

                if hasattr(player, "map"):
                    start_tile = player.universe.get_tile(
                        player.location_x, player.location_y
                    )
                    if start_tile:
                        player.current_room = start_tile

                # Reset transient combat state so the player never loads mid-fight.
                # Saves captured during combat (e.g. autosave every 20 ticks) or after
                # a defeat whose cleanup was interrupted would otherwise resume into a
                # phantom combat with no enemies.
                player.in_combat = False
                player.combat_list = []
                # Preserve only living allies — dead allies must not be re-injected into
                # rooms via recall_friends or re-enrolled in the next combat.
                existing_allies = [
                    a for a in getattr(player, "combat_list_allies", [])
                    if a is not player and a.is_alive()
                ]
                for ally in existing_allies:
                    ally.in_combat = False
                player.combat_list_allies = [player] + existing_allies
                player.current_move = None
                # Strip non-persistent status effects that should have been cleared at
                # combat end (mirrors combat.py line 624 which the API adapter never runs).
                player.states = [
                    s for s in getattr(player, "states", [])
                    if getattr(s, "persistent", True)
                ]
                # Recharge equip-states (e.g. PhoenixRevive) consumed mid-battle —
                # combat state is wiped above, so this load is effectively a fresh
                # start that should restore any equipped item's granted states.
                player.recharge_equip_states()
                if hasattr(player, "_combat_adapter"):
                    del player._combat_adapter
                if hasattr(player, "combat_adapter_state"):
                    del player.combat_adapter_state
                if hasattr(player, "_combat_deferred_enemies"):
                    del player._combat_deferred_enemies
                if hasattr(player, "combat_end_summary"):
                    del player.combat_end_summary

            return player
        except Exception as e:
            print(f"Error loading save {save_id}: {e}")
            return None

    async def list_saves(
        self, user_id: str, timezone: str = "America/New_York"
    ) -> List[Dict[str, Any]]:
        """List all saved games for a user from Turso.

        Returns:
            List of save metadata dictionaries
        """
        from src.api.db import db
        import zoneinfo
        from datetime import datetime

        try:
            user_tz = zoneinfo.ZoneInfo(timezone)
        except Exception:
            user_tz = zoneinfo.ZoneInfo("America/New_York")

        sql = """
        SELECT id, name, timestamp, is_autosave, level, map_name, room_title, playtime
        FROM saves
        WHERE user_id = ?
        ORDER BY timestamp DESC
        """
        result = await db.execute(sql, [user_id])

        saves = []
        for row in result.rows:
            ts_str = str(row[2])
            try:
                # SQLite CURRENT_TIMESTAMP is in UTC 'YYYY-MM-DD HH:MM:SS'
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                dt_local = dt.astimezone(user_tz)
                # Format to a nice string e.g. "2026-04-23 18:15:00 EDT"
                ts_str = dt_local.strftime("%Y-%m-%d %H:%M:%S %Z")
            except Exception:
                pass  # fallback to original string

            saves.append(
                {
                    "id": str(row[0]),
                    "name": str(row[1]),
                    "timestamp": ts_str,
                    "is_autosave": bool(row[3]),
                    "level": int(row[4]) if row[4] is not None else "?",
                    "map_name": str(row[5]) if row[5] else "Unknown",
                    "room_title": str(row[6]) if row[6] else "Unknown",
                    "playtime": int(row[7]) if row[7] is not None else 0,
                }
            )

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

    def _initialize_combat(
        self,
        player: "player_module.Player",
        enemies: List[Any],
        session_id: str = None,
        session_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Initialize combat state for player and enemies using the combat adapter.

        Args:
            player: Player object
            enemies: List of enemy NPCs
        """
        # Detect if this is a re-initialization (enemies joining an already active combat)
        is_reinit = getattr(player, "in_combat", False)

        # Idempotency check: If player is already in combat with exactly these enemy objects,
        # do nothing. Keyed on object identity (id) rather than name so two enemies with the
        # same name (e.g. two Slimes) are treated as distinct combatants.
        if is_reinit and hasattr(player, "combat_list"):
            current_ids = set(id(e) for e in player.combat_list)
            new_ids = set(id(e) for e in enemies)
            if current_ids == new_ids:
                return

        from src.api.combat_adapter import ApiCombatAdapter

        # Set combat lists on player (required by adapter)
        player.combat_list = enemies
        # Preserve existing living party members — dead allies must not be re-enrolled.
        existing_allies = [
            a for a in getattr(player, "combat_list_allies", [])
            if a is not player and a.is_alive()
        ]
        player.combat_list_allies = [player] + existing_allies
        player.in_combat = True

        # Initialize last move tracking for "DO IT AGAIN" button
        player.last_move_name = None
        player.last_move_target_id = None

        # Create or get combat adapter
        if not hasattr(player, "_combat_adapter"):
            # Define event callback for logic during beats
            def event_callback(p):
                return self.trigger_combat_events(p, session_data=session_data)

            player._combat_adapter = ApiCombatAdapter(
                player, session_id=session_id, on_event_callback=event_callback
            )
        elif session_id:
            player._combat_adapter.session_id = session_id

        # Reset post-combat state so events fire correctly after this combat's
        # victory even when the adapter object is reused across fights.
        player._combat_adapter._post_combat_tile_events_fired = False
        player._combat_adapter._combat_tile = None

        # Initialize combat through the adapter
        # This will set up all combat state, process initial NPC turns if needed,
        # and return the initial combat state
        return player._combat_adapter.initialize_combat(enemies, reinit=is_reinit)

    def flee_combat(self, player: "player_module.Player") -> Dict[str, Any]:
        """Attempt to flee from combat.

        Args:
            player: Player object

        Returns:
            Dictionary with flee result
        """
        if not getattr(player, "in_combat", False):
            return {"error": "Not in combat"}

        enemies = getattr(player, "combat_list", [])
        for enemy in enemies:
            prox = getattr(enemy, "combat_proximity", 0)
            dist = prox.get(player, 0) if isinstance(prox, dict) else prox
            if dist < 20:
                return {
                    "success": False,
                    "fled": False,
                    "error": "Cannot flee — enemies are too close",
                }

        # Clear enemy combat state so they don't immediately re-engage on next interaction
        for enemy in list(getattr(player, "combat_list", [])):
            enemy.in_combat = False
            enemy.aggro = False

        player.in_combat = False
        player.combat_list = []

        # Clear ally combat state — filter to living allies first, then clear their flags
        living_allies = [
            a for a in getattr(player, "combat_list_allies", [])[1:] if a.is_alive()
        ]
        for ally in living_allies:
            ally.in_combat = False
        player.combat_list_allies = [player] + living_allies

        player.current_move = None

        # Strip non-persistent status effects (mirrors end-of-combat cleanup)
        player.states = [
            s for s in getattr(player, "states", [])
            if getattr(s, "persistent", True)
        ]

        if hasattr(player, "_combat_adapter"):
            del player._combat_adapter
        if hasattr(player, "combat_adapter_state"):
            del player.combat_adapter_state
        if hasattr(player, "_combat_deferred_enemies"):
            del player._combat_deferred_enemies
        if hasattr(player, "combat_end_summary"):
            del player.combat_end_summary

        return {
            "success": True,
            "fled": True,
            "message": "Fled from combat successfully",
        }

    # =====================
    # NPC Methods (Phase 5)
    # =====================

    def get_npc_state(
        self, player: "player_module.Player", npc_id: str
    ) -> Dict[str, Any]:
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
                npc.last_interaction_time = str(
                    __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    )
                )

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

    def _find_chat_npc(self, player: "player_module.Player", npc_key: str):
        """Find an NPC on the current tile matching the given npc_key.

        Tries multiple matching strategies:
        1. Exact _chat_npc_key attribute match
        2. Class name prefix match (e.g. "NomadCamper" from "NomadCamper_0")
        3. Name attribute match

        Args:
            player: The player instance
            npc_key: NPC identifier to search for

        Returns:
            NPC object if found, None otherwise
        """
        current_tile = player.universe.get_tile(player.location_x, player.location_y)
        if not current_tile:
            return None

        for npc in getattr(current_tile, "npcs_here", []):
            # Try _chat_npc_key match first
            if getattr(npc, "_chat_npc_key", None) == npc_key:
                return npc

            # Try class name prefix match (e.g. "NomadCamper" from "NomadCamper_0")
            class_name = type(npc).__name__
            if npc_key.startswith(class_name):
                return npc

            # Try name attribute match
            if getattr(npc, "name", "") == npc_key:
                return npc

        return None

    def npc_chat_open(
        self, player: "player_module.Player", npc_id: str
    ) -> Dict[str, Any]:
        """Start an LLM conversation with a human NPC.

        Args:
            player: The player instance
            npc_id: NPC identifier (name or class name)

        Returns:
            Dict with success status and conversation state
        """
        # Find NPC in current tile
        current_tile = player.universe.get_tile(player.location_x, player.location_y)
        if not current_tile:
            return {"success": False, "error": "Not on a valid tile"}

        npc = None
        for npc_candidate in getattr(current_tile, "npcs_here", []):
            if (
                type(npc_candidate).__name__ == npc_id
                or getattr(npc_candidate, "name", "") == npc_id
            ):
                npc = npc_candidate
                break

        if not npc:
            return {"success": False, "error": f"NPC '{npc_id}' not found"}

        # Check if NPC supports chat
        if not hasattr(npc, "chat_open"):
            return {"success": False, "error": "NPC does not support chat"}

        # Store active chat NPC ID
        player.__dict__["_active_chat_npc_id"] = npc_id

        # Call NPC's chat_open method
        try:
            result = npc.chat_open(player)
            return self._enrich_chat_result_with_relationship(result, npc)
        except Exception as e:
            return {"success": False, "error": f"Failed to open chat: {str(e)}"}

    def npc_chat_respond(
        self,
        player: "player_module.Player",
        npc_key: str,
        jean_text: str,
        jean_tone: str = "direct",
    ) -> Dict[str, Any]:
        """Process Jean's dialogue choice and get NPC response.

        Args:
            player: The player instance
            npc_key: NPC identifier for active chat
            jean_text: Jean's dialogue text
            jean_tone: Tone of Jean's response ("direct", "guarded", "open", etc.)

        Returns:
            Dict with success status and NPC response
        """
        # Find NPC on current tile
        npc = self._find_chat_npc(player, npc_key)
        if not npc:
            return {"success": False, "error": "Active chat NPC not found"}

        # Check if NPC supports chat_respond
        if not hasattr(npc, "chat_respond"):
            return {"success": False, "error": "NPC does not support respond"}

        # Call NPC's chat_respond method
        try:
            result = npc.chat_respond(player, jean_text, jean_tone)
            return self._enrich_chat_result_with_relationship(result, npc)
        except Exception as e:
            return {"success": False, "error": f"Failed to respond: {str(e)}"}

    def _enrich_chat_result_with_relationship(
        self, result: Dict[str, Any], npc
    ) -> Dict[str, Any]:
        """Attach a relationship badge (attitude/trust/emoji) to a chat result.

        The chat mixin (`src/npc/_chat_llm.py`) is engine code and cannot import
        API serializers, so it only returns the raw `reputation` int. This builds
        the frontend-facing badge from that value.

        Args:
            result: Dict returned by `npc.chat_open`/`npc.chat_respond`
            npc: The NPC instance being chatted with

        Returns:
            The same result dict, with a `relationship` key added if applicable
        """
        if not result.get("success") or "reputation" not in result:
            return result

        from src.api.serializers.reputation import NPCRelationshipSerializer

        npc_name = getattr(npc, "name", "")
        result["relationship"] = NPCRelationshipSerializer.serialize_relationship(
            npc_name, npc_name, result["reputation"]
        )
        return result

    def npc_chat_end(
        self, player: "player_module.Player", npc_key: str
    ) -> Dict[str, Any]:
        """End an NPC conversation and flush state.

        Args:
            player: The player instance
            npc_key: NPC identifier for active chat

        Returns:
            Dict with success status and conversation summary
        """
        # Clear active chat NPC
        player.__dict__.pop("_active_chat_npc_id", None)

        # Get conversation count from history if available
        count = 0
        if (
            hasattr(player, "npc_chat_histories")
            and npc_key in player.npc_chat_histories
        ):
            count = player.npc_chat_histories[npc_key].get("conversation_count", 0)

        return {"success": True, "data": {"conversation_count": count}}

    def npc_chat_history(
        self, player: "player_module.Player", npc_key: str
    ) -> Dict[str, Any]:
        """Get stored conversation history for an NPC.

        Args:
            player: The player instance
            npc_key: NPC identifier to retrieve history for

        Returns:
            Dict with success status and conversation exchanges
        """
        # Check if player has chat histories
        if not hasattr(player, "npc_chat_histories"):
            return {"success": False, "error": "No chat history available"}

        hist = player.npc_chat_histories.get(npc_key)
        if not hist:
            return {"success": False, "error": f"No history for '{npc_key}'"}

        # Get display name
        npc_name = npc_key.split("_")[0] if "_" in npc_key else npc_key
        personality = hist.get("personality")
        if personality and personality.get("given_name"):
            npc_name = personality["given_name"]

        return {
            "success": True,
            "data": {
                "npc_key": npc_key,
                "npc_name": npc_name,
                "exchanges": hist.get("exchanges", []),
                "conversation_count": hist.get("conversation_count", 0),
                "last_talked_tick": hist.get("last_talked_tick", 0),
                "loquacity_current": hist.get("loquacity_current", 0),
                "loquacity_max": hist.get("loquacity_max", 0),
            },
        }

    def collect_combat_loot(self, player: Any, item_names: list) -> Dict[str, Any]:
        """Move selected post-combat drops from the current tile into the player's inventory.

        Items listed in item_names are picked up; all others remain on the tile.
        combat_drops is cleared regardless so the loot phase cannot be repeated.

        Args:
            player: The Player instance.
            item_names: List of item names the player chose to take.

        Returns:
            Dict with success, collected list, and skipped list.
        """
        # FIX 3: Add parameter validation
        if item_names is None:
            item_names = []
        elif not isinstance(item_names, list):
            return {
                "success": False,
                "error": f"Invalid item_names parameter: expected list, got {type(item_names).__name__}",
            }

        # Validate each item name is a string
        for name in item_names:
            if not isinstance(name, str):
                return {
                    "success": False,
                    "error": f"Invalid item name in list: expected string, got {type(name).__name__}",
                }

        tile = getattr(player, "current_room", None)
        if not tile or not hasattr(tile, "items_here"):
            player.combat_drops = []
            return {"success": True, "collected": [], "skipped": []}

        inventory = getattr(player, "inventory_list", None)
        if inventory is None:
            inventory = getattr(player, "inventory", [])

        capacity = float(getattr(player, "weight_tolerance", 20.0) or 20.0)

        # Build a name → [item, ...] mapping from the tile (all matches per name)
        tile_by_name: Dict[str, list] = {}
        for item in list(tile.items_here):
            name = getattr(item, "name", None)
            if name:
                tile_by_name.setdefault(name, []).append(item)

        collected = []
        skipped = []
        current_weight = sum(float(getattr(i, "weight", 0) or 0) for i in inventory)

        for name in item_names:
            candidates = tile_by_name.get(name)
            if not candidates:
                skipped.append({"name": name, "reason": "not_found"})
                continue
            # Pick up every physical item object with this name (handles stacked drops)
            any_collected = False
            for item in list(candidates):
                item_weight = float(getattr(item, "weight", 0) or 0)
                if current_weight + item_weight > capacity:
                    skipped.append({"name": name, "reason": "over_capacity"})
                    break
                if item in tile.items_here:
                    tile.items_here.remove(item)
                    inventory.append(item)
                    collected.append(name)
                    current_weight += item_weight
                    any_collected = True
            if not any_collected and not any(s["name"] == name for s in skipped):
                skipped.append({"name": name, "reason": "not_found"})

        player.combat_drops = []

        if collected and hasattr(player, "stack_inv_items"):
            player.stack_inv_items()
        if hasattr(player, "refresh_weight"):
            player.refresh_weight()

        return {"success": True, "collected": collected, "skipped": skipped}

    # ── Shop ──────────────────────────────────────────────────────────────────

    def _find_merchant(self, player: Any, npc_id: str):
        """Return the merchant NPC on the player's current tile, or None."""
        tile = player.universe.get_tile(player.location_x, player.location_y)
        for npc in getattr(tile, "npcs_here", []):
            if str(id(npc)) == npc_id and hasattr(npc, "shop"):
                return npc
        return None

    def _validate_shop_transaction(
        self, merchant: Any, quantity: int, required_fields: list = None
    ) -> Dict[str, Any]:
        """FIX 6: Validate shop transaction prerequisites.

        Args:
            merchant: The merchant NPC
            quantity: Transaction quantity
            required_fields: Optional list of field names to validate on merchant

        Returns:
            Dict with error key if validation fails, empty dict if validation passes
        """
        if merchant is None:
            return {"error": "Merchant not found at this location"}

        if not hasattr(merchant, "buy_modifier"):
            merchant.initialize_shop()

        # Validate quantity
        if not isinstance(quantity, int) or quantity < 1:
            return {"error": "Invalid quantity"}

        # Validate required fields on merchant if specified
        if required_fields:
            for field in required_fields:
                if not hasattr(merchant, field):
                    return {
                        "error": f"Merchant configuration incomplete: missing {field}"
                    }

        return {}

    def get_shop_state(self, player: Any, npc_id: str) -> Dict[str, Any]:
        """Return the full shop state for a merchant NPC.

        Also serializes the player's sellable inventory so the frontend has
        everything it needs in one request.

        Args:
            player: The Player instance.
            npc_id: str(id(npc)) of the target merchant.

        Returns:
            Dict with success, shop_state, and sell_inventory.
        """
        from src.api.serializers.shop_serializer import ShopSerializer

        merchant = self._find_merchant(player, npc_id)
        if merchant is None:
            return {"success": False, "error": "Merchant not found at this location"}

        if not hasattr(merchant, "buy_modifier"):
            merchant.initialize_shop()

        # Stock the merchant on first API access — update_goods() is normally
        # triggered by game_tick events (every 1000 ticks) but the API skips
        # the terminal game loop entirely.
        non_gold = [
            item for item in getattr(merchant, "inventory", [])
            if getattr(item, "name", None) != "Gold"
        ]
        if not non_gold and hasattr(merchant, "update_goods"):
            merchant.update_goods()

        # Transfer any merchandise items the player is carrying to the merchant's
        # stock (silently for the API — no terminal prints or sleeps). Capture the
        # generated flavor phrases so the frontend can display them as a dialog.
        collected_messages: list = []
        if hasattr(merchant, "_collect_player_merchandise"):
            collected_messages = merchant._collect_player_merchandise(player, silent=True)
        else:
            # Fallback for test environments with fake merchants
            merchant_name = getattr(merchant, "name", "Merchant")
            for it in list(getattr(player, "inventory", [])):
                if getattr(it, "merchandise", False):
                    try:
                        player.inventory.remove(it)
                    except ValueError:
                        continue
                    if not hasattr(merchant, "inventory") or merchant.inventory is None:
                        merchant.inventory = []
                    merchant.inventory.append(it)
                    collected_messages.append(
                        f"{merchant_name.split(' ')[0]} deftly takes the "
                        f"{getattr(it, 'name', 'item')} and adds it to the display."
                    )

        current_tick = self._game_tick(player)
        ShopSerializer.flush_stale_buyback(merchant, current_tick)
        shop_state = ShopSerializer.serialize_state(merchant, player, current_tick)
        sell_inventory = ShopSerializer.serialize_player_sellable(
            player, shop_state["sell_modifier"]
        )

        message = "\n".join(collected_messages) if collected_messages else None

        return {
            "success": True,
            "shop_state": shop_state,
            "sell_inventory": sell_inventory,
            "message": message,
        }

    def shop_buy(
        self, player: Any, npc_id: str, item_id: str, quantity: int
    ) -> Dict[str, Any]:
        """Purchase an item from a merchant.

        All price computation and validation happens server-side. The client
        only sends identifiers and quantity.

        Args:
            player: The Player instance.
            npc_id: str(id(npc)) of the merchant.
            item_id: str(id(item)) of the item in merchant inventory.
            quantity: Number of units to purchase (≥ 1).

        Returns:
            Dict with success, updated shop_state, sell_inventory, and message.
        """
        from src.inventory_utils import transfer_gold, transfer_item
        from src.api.serializers.shop_serializer import ShopSerializer

        merchant = self._find_merchant(player, npc_id)
        # Use validation helper (FIX 6)
        validation_error = self._validate_shop_transaction(merchant, quantity)
        if validation_error:
            return {"success": False, **validation_error}

        buy_mod = ShopSerializer.get_effective_buy_modifier(merchant, player)

        # Locate item in merchant inventory
        target_item = None
        for item in getattr(merchant, "inventory", []):
            if getattr(item, "name", None) != "Gold" and str(id(item)) == item_id:
                target_item = item
                break

        if target_item is None:
            return {"success": False, "error": "Item not found in merchant inventory"}

        # Clamp and validate quantity
        quantity = max(1, int(quantity))
        if hasattr(target_item, "count") and quantity > target_item.count:
            quantity = target_item.count

        unit_price = max(1, int(getattr(target_item, "value", 0) * buy_mod))
        total_price = unit_price * quantity

        player_gold = get_gold(player.inventory)
        if player_gold < total_price:
            needed = total_price - player_gold
            return {
                "success": False,
                "error": f"Not enough gold — need {needed} more",
            }

        # Weight check
        player.refresh_weight()
        item_weight = getattr(target_item, "weight", 0.0)
        if player.weight_current + item_weight * quantity > player.weight_tolerance:
            return {"success": False, "error": "Exceeds carry limit"}

        # Execute transfer
        transfer_gold(player.inventory, merchant.inventory, total_price)
        transfer_item(merchant, player, target_item, quantity)

        current_tick = self._game_tick(player)
        ShopSerializer.flush_stale_buyback(merchant, current_tick)
        shop_state = ShopSerializer.serialize_state(merchant, player, current_tick)
        sell_inventory = ShopSerializer.serialize_player_sellable(
            player, shop_state["sell_modifier"]
        )

        return {
            "success": True,
            "message": f"Purchased {quantity}× {target_item.name} for {total_price} gold.",
            "gold_spent": total_price,
            "shop_state": shop_state,
            "sell_inventory": sell_inventory,
        }

    def shop_sell(
        self, player: Any, npc_id: str, item_id: str, quantity: int
    ) -> Dict[str, Any]:
        """Sell an item from the player's inventory to a merchant.

        After a successful sale the item is added to the merchant's buyback
        ledger at the exact price paid, tied to the current game_tick so the
        frontend can offer instant repurchase until the beat advances.

        Args:
            player: The Player instance.
            npc_id: str(id(npc)) of the merchant.
            item_id: str(id(item)) of the item in player inventory.
            quantity: Number of units to sell (≥ 1).

        Returns:
            Dict with success, updated shop_state, sell_inventory, and message.
        """
        from src.inventory_utils import transfer_gold, transfer_item
        from src.api.serializers.shop_serializer import ShopSerializer

        merchant = self._find_merchant(player, npc_id)
        # Use validation helper (FIX 6)
        validation_error = self._validate_shop_transaction(merchant, quantity)
        if validation_error:
            return {"success": False, **validation_error}

        sell_mod = ShopSerializer.get_effective_sell_modifier(merchant, player)

        # Locate item in player inventory
        target_item = None
        for item in getattr(player, "inventory", []):
            if getattr(item, "name", None) != "Gold" and str(id(item)) == item_id:
                target_item = item
                break

        if target_item is None:
            return {"success": False, "error": "Item not found in inventory"}

        if getattr(target_item, "is_equipped", False) or getattr(
            target_item, "isequipped", False
        ):
            return {"success": False, "error": "Cannot sell equipped items"}

        base_value = getattr(target_item, "value", 0)
        if not base_value:
            return {"success": False, "error": "This item has no sell value"}

        # Clamp and validate quantity
        quantity = max(1, int(quantity))
        if hasattr(target_item, "count") and quantity > target_item.count:
            quantity = target_item.count

        unit_offer = max(1, int(base_value * sell_mod))
        total_offer = unit_offer * quantity

        merchant_gold = get_gold(merchant.inventory)
        if merchant_gold < total_offer:
            return {"success": False, "error": "Merchant has insufficient funds"}

        # Capture pre-transfer metadata for the buyback ledger
        item_name = getattr(target_item, "name", "Unknown")
        item_weight = getattr(target_item, "weight", 0.0)
        item_type = type(target_item).__name__
        item_subtype = getattr(target_item, "subtype", "")
        item_description = getattr(target_item, "description", "")
        item_power = getattr(target_item, "power", None)

        # Execute transfer
        transfer_gold(merchant.inventory, player.inventory, total_offer)
        transfer_item(player, merchant, target_item, quantity)

        # For full-stack sells, transfer_item moves the same Python object so its
        # id is unchanged and still present in merchant.inventory. For partial-stack
        # splits, a new object is created and appended, but stack_inv_items may
        # immediately merge it into an existing same-name item. In that case the
        # original id is gone — fall back to the first name-matching merchant item.
        if any(str(id(i)) == item_id for i in getattr(merchant, "inventory", [])):
            buyback_item_id = item_id
        else:
            buyback_item_id = next(
                (str(id(i)) for i in getattr(merchant, "inventory", [])
                 if getattr(i, "name", None) == item_name),
                item_id,
            )

        if not hasattr(merchant, "_buyback_ledger"):
            merchant._buyback_ledger = []

        merchant._buyback_ledger.append({
            "item_id": buyback_item_id,
            "item_name": item_name,
            "buyback_price": unit_offer,
            "weight": item_weight,
            "count": quantity,
            "type": item_type,
            "subtype": item_subtype,
            "description": item_description,
            "value": base_value,
            "power": item_power,
            "beat_acquired": self._game_tick(player),
        })

        current_tick = self._game_tick(player)
        ShopSerializer.flush_stale_buyback(merchant, current_tick)
        shop_state = ShopSerializer.serialize_state(merchant, player, current_tick)
        sell_inventory = ShopSerializer.serialize_player_sellable(
            player, shop_state["sell_modifier"]
        )

        return {
            "success": True,
            "message": f"Sold {quantity}× {item_name} for {total_offer} gold.",
            "gold_gained": total_offer,
            "shop_state": shop_state,
            "sell_inventory": sell_inventory,
        }

    def shop_buyback(
        self, player: Any, npc_id: str, item_id: str
    ) -> Dict[str, Any]:
        """Repurchase a recently sold item from the merchant's buyback ledger.

        The buyback price equals what the merchant paid — no markup. The ledger
        entry is removed on success regardless of whether the game tick has
        advanced (the frontend is responsible for only showing active entries).

        Args:
            player: The Player instance.
            npc_id: str(id(npc)) of the merchant.
            item_id: The item_id from the buyback ledger entry.

        Returns:
            Dict with success, updated shop_state, sell_inventory, and message.
        """
        from src.inventory_utils import transfer_gold, transfer_item
        from src.api.serializers.shop_serializer import ShopSerializer

        merchant = self._find_merchant(player, npc_id)
        # Use validation helper (FIX 6) - quantity=1 for buyback
        validation_error = self._validate_shop_transaction(merchant, 1)
        if validation_error:
            return {"success": False, **validation_error}

        # Flush stale entries before ledger lookup
        current_tick = self._game_tick(player)
        ShopSerializer.flush_stale_buyback(merchant, current_tick)

        # Find the ledger entry
        entry = None
        for e in merchant._buyback_ledger:
            if e["item_id"] == item_id:
                entry = e
                break

        if entry is None:
            return {
                "success": False,
                "error": "Buyback offer has expired or was not found",
            }

        total_price = entry["buyback_price"] * entry["count"]

        player_gold = get_gold(player.inventory)
        if player_gold < total_price:
            needed = total_price - player_gold
            return {
                "success": False,
                "error": f"Not enough gold — need {needed} more",
            }

        # Weight check
        player.refresh_weight()
        added_weight = entry["weight"] * entry["count"]
        if player.weight_current + added_weight > player.weight_tolerance:
            return {"success": False, "error": "Exceeds carry limit"}

        # Find the actual item object in merchant inventory
        target_item = None
        for item in getattr(merchant, "inventory", []):
            if str(id(item)) == item_id:
                target_item = item
                break

        if target_item is None:
            # Item may have been re-stacked; search by name as fallback
            item_name = entry["item_name"]
            for item in getattr(merchant, "inventory", []):
                if getattr(item, "name", None) == item_name:
                    target_item = item
                    break

        if target_item is None:
            merchant._buyback_ledger.remove(entry)
            return {"success": False, "error": "Buyback item no longer in merchant stock"}

        # Execute transfer
        transfer_gold(player.inventory, merchant.inventory, total_price)
        transfer_item(merchant, player, target_item, entry["count"])

        # Remove ledger entry
        merchant._buyback_ledger.remove(entry)

        shop_state = ShopSerializer.serialize_state(merchant, player, current_tick)
        sell_inventory = ShopSerializer.serialize_player_sellable(
            player, shop_state["sell_modifier"]
        )

        return {
            "success": True,
            "message": (
                f"Bought back {entry['count']}× {entry['item_name']} "
                f"for {total_price} gold."
            ),
            "gold_spent": total_price,
            "shop_state": shop_state,
            "sell_inventory": sell_inventory,
        }

    def get_world_info(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get world information (maps, locations, explored areas).

        Args:
            player: The Player instance

        Returns:
            Dictionary with world information
        """
        universe = getattr(player, "universe", None)
        if not universe:
            return {}

        return {
            "current_position": {
                "x": player.location_x,
                "y": player.location_y,
            },
            "explored_tiles": getattr(player, "explored_tiles", {}),
            "story_flags": self._story(player),
            "game_tick": self._game_tick(player),
        }

    def get_current_tile(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get information about the current tile.

        Args:
            player: The Player instance

        Returns:
            Dictionary with current tile information
        """
        return self.get_current_room(player)

    def interact_with_tile(self, player: "player_module.Player", action: str) -> Dict[str, Any]:
        """Interact with the current tile (look, examine, search, etc).

        Args:
            player: The Player instance
            action: The interaction action (look, examine, search, etc)

        Returns:
            Dictionary with interaction result
        """
        tile = player.universe.get_tile(player.location_x, player.location_y)
        if not tile:
            return {"error": "No tile at this location"}

        # Return tile description and contents
        return {
            "action": action,
            "tile_name": getattr(tile, "name", "Unknown"),
            "description": getattr(tile, "description", ""),
            "items": ItemSerializer.serialize_list(getattr(tile, "items_here", [])),
            "npcs": NPCSerializer.serialize_list(getattr(tile, "npcs_here", [])),
            "objects": ObjectSerializer.serialize_list(getattr(tile, "objects_here", [])),
        }

    def use_item(self, player: "player_module.Player", item_index: int) -> Dict[str, Any]:
        """Use an item from the player's inventory.

        Args:
            player: The Player instance
            item_index: Index of the item to use

        Returns:
            Dictionary with use result
        """
        if not isinstance(player.inventory, list):
            return {"error": "Inventory not accessible"}

        if item_index < 0 or item_index >= len(player.inventory):
            return {"error": "Invalid item index"}

        item = player.inventory[item_index]

        # FIX 2: Add type validation to ensure item is an object with expected attributes
        if isinstance(item, (str, dict, int, float)):
            return {"error": f"Invalid inventory item: corrupted data type {type(item).__name__}"}

        if not hasattr(item, "name"):
            return {"error": "Invalid inventory item: missing name attribute"}

        # Try to use the item if it has a use method
        if hasattr(item, "use") and callable(item.use):
            try:
                item.use(player)
                return {"success": True, "message": f"Used {item.name}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": f"{item.name} cannot be used"}

    def drop_item(self, player: "player_module.Player", item_index: int) -> Dict[str, Any]:
        """Drop an item from the player's inventory.

        Args:
            player: The Player instance
            item_index: Index of the item to drop

        Returns:
            Dictionary with drop result
        """
        if not isinstance(player.inventory, list):
            return {"error": "Inventory not accessible"}

        if item_index < 0 or item_index >= len(player.inventory):
            return {"error": "Invalid item index"}

        # FIX 1: Add defensive checks for universe and tile BEFORE modifying inventory
        if not hasattr(player, "universe") or player.universe is None:
            return {"error": "Cannot drop item: player universe not accessible"}

        # Get the tile and validate it exists before popping from inventory
        tile = player.universe.get_tile(player.location_x, player.location_y)
        if not tile or not hasattr(tile, "items_here"):
            return {"error": "Cannot drop item: invalid current location"}

        # FIX 2: Add type validation for inventory items
        item = player.inventory[item_index]
        if not hasattr(item, "name"):
            return {"error": "Cannot drop item: corrupted inventory item"}

        # Now it's safe to remove from inventory
        player.inventory.pop(item_index)

        # Add item to the current tile
        tile.items_here.append(item)

        return {
            "success": True,
            "message": f"Dropped {item.name}",
            "item_name": item.name,
        }

    def get_combat_state(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get the current combat state.

        Args:
            player: The Player instance

        Returns:
            Dictionary with combat state
        """
        in_combat = getattr(player, "in_combat", False)

        if not in_combat:
            return {
                "in_combat": False,
                "message": "Not in combat",
            }

        # If in combat, get the combat status
        return self.get_combat_status(player)
