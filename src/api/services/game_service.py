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
            Dictionary with room data (position, description, exits, etc.)
        """
        tile = self.universe.get_tile(player.x, player.y)
        if not tile:
            return {"error": "Invalid player position"}

        # Calculate exits dynamically by checking adjacent tiles
        exits_data = self._calculate_exits(tile, player.x, player.y)

        return {
            "x": player.x,
            "y": player.y,
            "name": getattr(tile, "name", "Unknown"),
            "description": getattr(tile, "description", ""),
            "exits": exits_data,
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

        tile = self.universe.get_tile(player.x, player.y)
        if not tile:
            return {"error": "Cannot move from this location"}

        # Calculate available exits
        available_exits = self._calculate_exits(tile, player.x, player.y)
        
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
        player.x = new_x
        player.y = new_y

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

    def start_combat(
        self, player: "player_module.Player", enemy_id: str
    ) -> Dict[str, Any]:
        """Initiate combat with an enemy.

        Args:
            player: The Player instance
            enemy_id: ID of enemy to fight

        Returns:
            Dictionary with combat initialization data
        """
        # TODO: Initialize combat session
        return {
            "combat_active": True,
            "combat_id": enemy_id,
            "combatants": [],
            "turn_order": [],
        }

    def execute_move(
        self,
        player: "player_module.Player",
        move_type: str,
        move_id: str,
        target_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a move during combat.

        Args:
            player: The Player instance
            move_type: Type of move (attack, defend, cast, item)
            move_id: ID of the move
            target_id: ID of target (if applicable)

        Returns:
            Result of move execution
        """
        # TODO: Implement move execution
        return {"success": True, "move_type": move_type, "result": "Move queued"}

    def get_combat_status(self, player: "player_module.Player") -> Dict[str, Any]:
        """Get current combat status.

        Args:
            player: The Player instance

        Returns:
            Dictionary with combat state
        """
        # TODO: Retrieve combat status
        return {"combat_active": False, "combatants": [], "log": []}

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
            "hp": getattr(player, "current_hp", 0),
            "max_hp": getattr(player, "max_hp", 0),
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
            "dexterity",
            "vitality",
            "intelligence",
            "wisdom",
            "speed",
        ]

        for stat_name in stat_names:
            stats[stat_name] = getattr(player, stat_name, 0)

        return stats

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
            True if successful
        """
        # TODO: Implement save deletion
        return True
