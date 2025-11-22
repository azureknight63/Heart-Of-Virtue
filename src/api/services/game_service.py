"""GameService - Stateless wrapper around the game engine."""

from typing import Dict, Any, Optional, List
import src.universe as universe_module
import src.player as player_module
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

    def __init__(self, universe: "universe_module.Universe"):
        """Initialize GameService.

        Args:
            universe: The Universe instance containing all game state
        """
        self.universe = universe

    # ========================
    # World Navigation Methods
    # ========================

    def _calculate_exits(self, tile: Any, x: int, y: int) -> Dict[str, Dict[str, int]]:
        """Calculate available exits from a tile by checking adjacent tiles.
        
        Args:
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
        for direction, (dx, dy) in directions.items():
            if direction in blocked:
                continue
                
            new_x, new_y = x + dx, y + dy
            adjacent_tile = self.universe.get_tile(new_x, new_y)
            
            if adjacent_tile:
                exits[direction] = {"x": new_x, "y": new_y}
        
        return exits

    def get_current_room(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get current room/tile data.

        Args:
            player: The Player instance

        Returns:
            Dictionary with room data (position, description, exits, items, npcs, objects)
        """
        tile = self.universe.get_tile(player.location_x, player.location_y)
        if not tile:
            return {"error": "Invalid player position"}

        # Calculate exits dynamically by checking adjacent tiles
        exits_data = self._calculate_exits(tile, player.location_x, player.location_y)

        # Serialize items in room
        items_data = []
        if hasattr(tile, "items_here"):
            for item in tile.items_here:
                items_data.append({
                    "name": getattr(item, "name", "Unknown Item"),
                    "quantity": getattr(item, "quantity", 1),
                    "announce": getattr(item, "announce", ""),
                })

        # Serialize NPCs in room
        npcs_data = []
        if hasattr(tile, "npcs_here"):
            npcs_data = NPCSerializer.serialize_list(tile.npcs_here)

        # Serialize objects in room
        objects_data = []
        if hasattr(tile, "objects_here"):
            objects_data = ObjectSerializer.serialize_list(tile.objects_here)

        return {
            "x": player.location_x,
            "y": player.location_y,
            "name": getattr(tile, "name", "Unknown"),
            "description": getattr(tile, "description", ""),
            "exits": exits_data,
            "items": items_data,
            "npcs": npcs_data,
            "objects": objects_data,
        }

    def move_player(self, player: "player_module.Player", direction: str) -> Dict[str, Any]:
        """Move player in specified direction.

        Args:
            player: The Player instance
            direction: Direction to move (north, south, east, west, northeast, northwest, southeast, southwest)

        Returns:
            Dictionary with result of movement
        """
        valid_directions = ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]
        direction_lower = direction.lower()
        if direction_lower not in valid_directions:
            return {"error": f"Invalid direction: {direction}"}

        tile = self.universe.get_tile(player.location_x, player.location_y)
        if not tile:
            return {"error": "Cannot move from this location"}

        # Calculate available exits
        available_exits = self._calculate_exits(tile, player.location_x, player.location_y)
        
        if direction_lower not in available_exits:
            return {"error": f"Cannot go {direction_lower} from here"}

        # Get new coordinates from exits
        exit_data = available_exits[direction_lower]
        new_x, new_y = exit_data["x"], exit_data["y"]
        
        # Validate new tile exists (should always exist after exits calculation, but be safe)
        new_tile = self.universe.get_tile(new_x, new_y)
        if not new_tile:
            return {"error": f"Cannot move {direction_lower} - blocked or out of bounds"}

        # Check for blocking objects/obstacles (if tile has validation)
        if hasattr(new_tile, "is_passable") and not new_tile.is_passable:
            return {"error": f"Cannot move {direction_lower} - path is blocked"}

        # Update player position
        player.location_x = new_x
        player.location_y = new_y

        # Trigger tile entry events
        events_triggered = self.trigger_tile_events(player, new_tile)

        return {
            "success": True,
            "new_position": {"x": new_x, "y": new_y},
            "events_triggered": events_triggered,
            "room": self.get_current_room(player),
        }

    def trigger_tile_events(
        self, player: "player_module.Player", tile: Any
    ) -> List[Dict[str, Any]]:
        """Trigger events on tile entry.

        Args:
            player: The Player instance
            tile: The MapTile being entered

        Returns:
            List of triggered event data
        """
        events_triggered = []
        
        if not hasattr(tile, "events_here"):
            return events_triggered

        # Serialize all events on the tile
        for event in tile.events_here:
            # Serialize the event using EventSerializer
            event_data = EventSerializer.serialize(event)
            events_triggered.append(event_data)
            
            # Try to trigger the event if it has a process method
            if hasattr(event, "process"):
                try:
                    event.process()
                except Exception:
                    # Silently fail on event processing errors
                    pass

        return events_triggered

    def get_tile(self, x: int, y: int) -> Dict[str, Any]:
        """Get tile data at specific coordinates with full serialization.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Dictionary with tile data including NPCs, items, and objects
        """
        tile = self.universe.get_tile(x, y)
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

    # ========================
    # Interaction Methods
    # ========================

    def interact_with_target(self, player: "player_module.Player", target_id: str, action: str) -> Dict[str, Any]:
        """Interact with an object or NPC.

        Args:
            player: The Player instance
            target_id: ID of the target object/NPC
            action: The action keyword to execute

        Returns:
            Dictionary with interaction result and output text
        """
        import contextlib
        import io
        import src.functions as functions
        from unittest.mock import patch
        import inspect
        import re

        # Find target
        tile = self.universe.get_tile(player.location_x, player.location_y)
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
                    
        if not target:
            return {"success": False, "message": "Target not found."}

        # Validate action
        # Check keywords first, then check if method exists
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
        try:
            # We need to patch await_input to prevent blocking, and time.sleep to prevent delays
            # Also patch cprint to capture colored output
            def mock_cprint(text, *args, **kwargs):
                f.write(str(text) + '\n')
            
            with contextlib.redirect_stdout(f), \
                 contextlib.redirect_stderr(f), \
                 patch('src.functions.await_input', return_value=None), \
                 patch('time.sleep', return_value=None), \
                 patch('neotermcolor.cprint', mock_cprint):
                
                method = getattr(target, action)
                # Check signature to see if we need to pass player
                sig = inspect.signature(method)
                # Most object methods are (self) only, not (self, player)
                # Try calling without args first
                try:
                    method()
                except TypeError as e:
                    # If that fails, try with player
                    if len(sig.parameters) > 0:
                        method(player)
                    else:
                        raise
                    
        except Exception as e:
            return {"success": False, "message": f"Error executing action: {str(e)}"}

        output = f.getvalue()
        
        # Clean up output (remove ANSI codes)
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_output = ansi_escape.sub('', output)

        return {
            "success": True, 
            "message": clean_output,
            "target_name": getattr(target, "name", "Unknown"),
            "action": action
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
            item_type = type(item).__name__
            
            if item_type == "Weapon":
                player.eq_weapon = item
                player.weapon = item
            elif item_type == "Shield":
                player.shield = item
            elif item_type == "Armor" or item_type == "Helm" or item_type == "Boots" or item_type == "Gloves":
                # Find appropriate slot
                if hasattr(item, "type_s"):
                    slot_name = item.type_s.lower()
                    if hasattr(player, slot_name):
                        setattr(player, slot_name, item)
            
            # Refresh stat bonuses after equipment change
            if hasattr(player, "refresh_stat_bonuses"):
                player.refresh_stat_bonuses()
            
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
                    player.weapon = player.fists
            else:
                setattr(player, attr_name, None)
            
            # Refresh stat bonuses after equipment change
            if hasattr(player, "refresh_stat_bonuses"):
                player.refresh_stat_bonuses()
            
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
    # Player Status Methods
    # ========================

    def get_player_status(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get player status (name, level, health, etc.).

        Args:
            player: The Player instance

        Returns:
            Dictionary with player status
        """
        return {
            "name": getattr(player, "name", "Unknown"),
            "level": getattr(player, "level", 1),
            "exp": getattr(player, "exp", 0),
            "max_exp": getattr(player, "exp_to_level", 100),
            "hp": getattr(player, "current_hp", 0),
            "max_hp": getattr(player, "max_hp", 0),
            "fatigue": getattr(player, "fatigue", 0),
            "max_fatigue": getattr(player, "max_fatigue", 0),
            "state": "normal",  # TODO: Get actual status effects
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
        stats["max_hp"] = getattr(player, "max_hp", 0)
        stats["fatigue"] = getattr(player, "fatigue", 0)
        stats["max_fatigue"] = getattr(player, "max_fatigue", 0)
        stats["weight_current"] = getattr(player, "weight_current", 0)
        stats["carrying_capacity"] = getattr(player, "carrying_capacity", 100)
        stats["protection"] = getattr(player, "protection", 0)
        stats["resistance"] = getattr(player, "resistance", {})
        stats["status_resistance"] = getattr(player, "status_resistance", {})
        stats["states"] = [{"name": state.name, "steps_left": state.steps_left} 
                          for state in getattr(player, "states", [])]

        return stats

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
        current_tile = self.universe.get_tile(player.location_x, player.location_y)
        if current_tile and hasattr(current_tile, "available_actions"):
            try:
                available_actions = current_tile.available_actions(callerIsApi=True)
                for action in available_actions:
                    commands.append({
                        "name": getattr(action, "name", "Unknown"),
                        "hotkey": getattr(action, "hotkey", []),
                    })
            except Exception as e:
                logging.error(f"Error getting available actions: {e}")

        return {
            "commands": commands,
            "count": len(commands),
        }

    # ========================
    # Save/Load Methods
    # ========================

    def save_game(self, player: "player_module.Player", name: str) -> str:
        """Save the game.

        Args:
            player: The Player instance
            name: Name for the save

        Returns:
            Save ID
        """
        # TODO: Implement save persistence
        import uuid

        save_id = str(uuid.uuid4())
        return save_id

    def load_game(self, save_id: str) -> Optional["player_module.Player"]:
        """Load a saved game.

        Args:
            save_id: ID of save to load

        Returns:
            Loaded Player instance or None
        """
        # TODO: Implement save loading
        return None

    def list_saves(self) -> List[Dict[str, Any]]:
        """List all saved games.

        Returns:
            List of save metadata dictionaries
        """
        # TODO: Implement save listing
        return []

    def delete_save(self, save_id: str) -> bool:
        """Delete a save.

        Args:
            save_id: ID of save to delete

        Returns:
            True if deleted, False otherwise
        """
        # TODO: Implement save deletion
        return False

    # ========================
    # Combat Methods
    # ========================

    def start_combat(self, player: "player_module.Player", enemy_id: str) -> Dict[str, Any]:
        """Start combat between player and enemy.

        Args:
            player: Player object
            enemy_id: ID of enemy to find and fight (NPC name or identifier)

        Returns:
            Dictionary with combat state
        """
        # Look up enemy in current tile or universe
        current_tile = self.get_current_room(player)
        if isinstance(current_tile, dict) and "error" in current_tile:
            return {"error": f"Cannot find player location: {current_tile['error']}"}

        # Get the actual tile object
        player_x = getattr(player, "x", 1)
        player_y = getattr(player, "y", 1)
        tile = self.universe.get_tile(player_x, player_y)

        if not tile:
            return {"error": "Player tile not found"}

        # Search for enemy NPC on the tile
        enemy = None
        for npc in getattr(tile, "npcs_here", []):
            if getattr(npc, "name", "").lower() == enemy_id.lower() or str(
                getattr(npc, "id", "")
            ) == enemy_id:
                enemy = npc
                break

        if not enemy:
            return {"error": f"Enemy '{enemy_id}' not found on this tile"}

        # Initialize combat system
        if not hasattr(player, "combat_list"):
            player.combat_list = []
        if not hasattr(player, "combat_list_allies"):
            player.combat_list_allies = [player]

        player.combat_list = [enemy]
        player.in_combat = True

        # Get initial state
        return CombatStateSerializer.serialize_combat_state(
            player, [enemy], current_turn_index=0, round_number=1
        )

    def get_combat_status(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get current combat status.

        Args:
            player: Player object

        Returns:
            Dictionary with combat state
        """
        in_combat = getattr(player, "in_combat", False)
        
        if not in_combat:
            return {
                "combat_active": False,
                "combatants": [],
                "log": []
            }
        
        enemies = getattr(player, "combat_list", [])
        return {
            "combat_active": True,
            "battle_state": CombatStateSerializer.serialize_combat_state(player, enemies),
            "log": []
        }

    def get_combat_state(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get current combat state.

        Args:
            player: Player object

        Returns:
            Dictionary with current battle state
        """
        if not getattr(player, "in_combat", False):
            return {"error": "Not in combat", "in_combat": False}

        enemies = getattr(player, "combat_list", [])
        return CombatStateSerializer.serialize_combat_state(
            player, enemies, current_turn_index=0, round_number=1
        )

    def get_available_moves(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get available moves/actions for player in combat.

        Args:
            player: Player object

        Returns:
            Dictionary with available actions
        """
        if not getattr(player, "in_combat", False):
            return {"error": "Not in combat"}

        actions = ["attack", "defend", "flee"]

        moves = []
        if hasattr(player, "moves"):
            for move in getattr(player, "moves", []):
                moves.append(MoveSerializer.serialize_move(move))

        items = []
        if hasattr(player, "inventory"):
            for item in getattr(player, "inventory", []):
                if hasattr(item, "combat_usable") and getattr(item, "combat_usable"):
                    items.append(
                        {"name": getattr(item, "name", "Unknown"), "index": 0}
                    )

        return {
            "actions": actions,
            "moves": moves,
            "items": items,
        }

    def execute_move(
        self, player: "player_module.Player", move_type: str, move_id: str, target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a combat move.

        Args:
            player: Player object
            move_type: Type of action (attack, defend, cast, item)
            move_id: ID/name of the specific move or ability
            target_id: ID of target (optional, defaults to first enemy)

        Returns:
            Dictionary with action result
        """
        if not getattr(player, "in_combat", False):
            return {"error": "Not in combat"}

        enemies = getattr(player, "combat_list", [])
        if not enemies:
            return {"error": "No enemies in combat"}

        # Route move based on type
        if move_type == "attack":
            return self._execute_attack(player, enemies, target_id)
        elif move_type == "defend":
            return self.defend(player)
        elif move_type == "cast":
            return self._execute_spell(player, enemies, move_id, target_id)
        elif move_type == "item":
            # move_id should be item index
            try:
                item_index = int(move_id)
                return self.use_item_in_combat(player, item_index, target_id)
            except ValueError:
                return {"error": "Invalid item index"}
        else:
            return {"error": f"Unknown move type: {move_type}"}

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
        damage = getattr(player, "damage", 10) + 5  # Base damage + random
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
        current_tile = self.universe.get_tile(player.x, player.y)
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
        current_tile = self.universe.get_tile(player.x, player.y)
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
        current_tile = self.universe.get_tile(player.x, player.y)
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
        current_tile = self.universe.get_tile(player.x, player.y)
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

        old_gold = getattr(player, "gold", 0)
        player.gold = old_gold + amount

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

        inventory = getattr(player, "inventory", [])
        max_inventory = getattr(player, "max_inventory", 20)

        if len(inventory) >= max_inventory:
            return {
                "success": False,
                "error": "Inventory full",
                "item_id": item_id,
            }

        # Add item to inventory (simplified)
        item = {
            "id": item_id,
            "name": item_name,
            "quantity": quantity,
        }
        inventory.append(item)

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
            self.universe.game_tick,
            player.story,
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
            self.universe.game_tick,
            player.story,
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
            self.universe.game_tick,
            player.story,
        )

        availability_info = NPCAvailabilitySerializer.serialize(
            npc_data,
            self.universe.game_tick,
            player.story,
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
                "game_tick": self.universe.game_tick,
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
            player_id=player.name,
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
            player_story=player.story,
            player_reputation=player.reputation,
            player_level=player.level,
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
            player_story=player.story,
            player_reputation=player.reputation,
            player_level=player.level,
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
            player_story=player.story,
            player_reputation=player.reputation,
            player_level=player.level,
            player_completed_dialogues=getattr(player, "completed_dialogues", [])
        )

        # Create updated context
        history = ConversationHistory(
            conversation_id=conversation_id,
            npc_id="npc_1",
            player_id=player.name,
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





