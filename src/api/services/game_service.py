"""GameService - Stateless wrapper around the game engine."""

from typing import Dict, Any, Optional, List
import src.universe as universe_module
import src.player as player_module


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

        return {
            "x": player.x,
            "y": player.y,
            "name": tile.name if hasattr(tile, "name") else "Unknown",
            "description": tile.description if hasattr(tile, "description") else "",
            "exits": list(tile.exits.keys()) if hasattr(tile, "exits") else [],
        }

    def move_player(self, player: "player_module.Player", direction: str) -> Dict[str, Any]:
        """Move player in specified direction.

        Args:
            player: The Player instance
            direction: Direction to move (north, south, east, west)

        Returns:
            Dictionary with result of movement
        """
        valid_directions = ["north", "south", "east", "west"]
        direction_lower = direction.lower()
        if direction_lower not in valid_directions:
            return {"error": f"Invalid direction: {direction}"}

        tile = self.universe.get_tile(player.x, player.y)
        if not tile or not hasattr(tile, "exits"):
            return {"error": "Cannot move from this location"}

        if direction_lower not in tile.exits:
            return {"error": f"Cannot go {direction_lower} from here"}

        # Get new coordinates
        new_x, new_y = tile.exits[direction_lower]
        
        # Validate new tile exists
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

        for event in tile.events_here:
            event_data = {
                "event_id": str(id(event)),
                "type": type(event).__name__,
                "description": getattr(event, "description", ""),
            }
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

        # Serialize items with key properties
        items_data = []
        for i, item in enumerate(getattr(tile, "items_here", [])):
            item_obj = {
                "id": str(i),
                "name": getattr(item, "name", type(item).__name__),
                "type": type(item).__name__,
                "description": getattr(item, "description", ""),
            }
            # Add quantity if available (for stackable items)
            if hasattr(item, "quantity"):
                item_obj["quantity"] = item.quantity
            items_data.append(item_obj)

        # Serialize NPCs with basic stats
        npcs_data = []
        for i, npc in enumerate(getattr(tile, "npcs_here", [])):
            npc_obj = {
                "id": str(i),
                "name": getattr(npc, "name", "Unknown"),
                "type": type(npc).__name__,
                "level": getattr(npc, "level", 1),
                "health": getattr(npc, "health", 0),
                "max_health": getattr(npc, "max_health", 0),
                "is_hostile": getattr(npc, "is_hostile", False),
            }
            npcs_data.append(npc_obj)

        # Serialize objects on tile
        objects_data = []
        for i, obj in enumerate(getattr(tile, "objects_here", [])):
            obj_data = {
                "id": str(i),
                "name": getattr(obj, "name", type(obj).__name__),
                "type": type(obj).__name__,
                "description": getattr(obj, "description", ""),
                "is_passable": getattr(obj, "is_passable", True),
            }
            objects_data.append(obj_data)

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
            Dictionary with inventory data
        """
        items = getattr(player, "inventory", [])
        return {
            "items": [
                {
                    "id": str(i),
                    "name": getattr(item, "name", "Unknown"),
                    "type": type(item).__name__,
                }
                for i, item in enumerate(items)
            ],
            "count": len(items),
            "weight": getattr(player, "weight", 0),
            "max_weight": getattr(player, "max_carrying_capacity", 500),
        }

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
            Dictionary with equipped items
        """
        # TODO: Parse equipment from player state
        return {
            "head": None,
            "body": None,
            "hands": None,
            "feet": None,
            "back": None,
            "neck": None,
        }

    def equip_item(
        self, player: "player_module.Player", item_id: str
    ) -> Dict[str, Any]:
        """Equip an item.

        Args:
            player: The Player instance
            item_id: ID of item to equip

        Returns:
            Result of action with stat changes
        """
        # TODO: Implement equipment logic
        return {"success": True, "item_id": item_id, "stat_changes": {}}

    def unequip_item(self, player: "player_module.Player", slot: str) -> Dict[str, Any]:
        """Unequip item from slot.

        Args:
            player: The Player instance
            slot: Equipment slot (head, body, etc.)

        Returns:
            Result of action
        """
        # TODO: Implement unequip logic
        return {"success": True, "slot": slot}

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
