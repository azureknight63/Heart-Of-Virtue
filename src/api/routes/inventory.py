"""
Inventory and equipment management routes for the Flask API.

Provides endpoints for:
- Inventory management (list, examine, take, drop)
- Equipment management (equip, unequip, compare)
- Currency/stat queries
"""

from flask import Blueprint, current_app, jsonify, request

from src.api.services.validators import (
    validate_currency_amount,
    validate_equipment_slot,
    validate_item_index,
    validate_required_fields,
    validate_weight_limit,
)
from src.api.serializers.inventory import (
    EquipmentSerializer,
    ItemComparisonSerializer,
    InventorySerializer,
    ItemDetailSerializer,
)

# Create blueprint
inventory_bp = Blueprint("inventory", __name__)


def get_session_and_player():
    """Extract session and player from request."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, jsonify({"success": False, "error": "Missing authorization"}), 401

    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)

    if not session:
        return None, None, jsonify({"success": False, "error": "Invalid or expired session"}), 401

    player = session_manager.get_player(session_id)
    if not player:
        return None, None, jsonify({"success": False, "error": "Player not found"}), 404

    return session, player, None, None


def get_item_and_index(player, item_id=None, item_index=None):
    """
    Find item by ID or index.
    
    Args:
        player: Player object
        item_id: String ID of the item (Python id())
        item_index: Numeric index in inventory
        
    Returns:
        Tuple of (item, index) or (None, None) if not found
    """
    inventory_list = getattr(player, "inventory_list", None) or getattr(player, "inventory", [])
    
    # Try finding by ID first
    if item_id:
        for idx, item in enumerate(inventory_list):
            if str(id(item)) == item_id:
                return item, idx
        return None, None
    
    # Fall back to index
    if item_index is not None:
        if 0 <= item_index < len(inventory_list):
            return inventory_list[item_index], item_index
        return None, None
    
    return None, None


@inventory_bp.route("/inventory", methods=["GET"])
def get_inventory():
    """Get player inventory.

    Returns:
        JSON with complete inventory including weight and items
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        inventory_data = InventorySerializer.serialize(player)
        return (
            jsonify({"success": True, "inventory": inventory_data}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/examine", methods=["GET"])
def examine_item():
    """Examine specific item in inventory.

    Query params:
        index: Item index in inventory

    Returns:
        JSON with detailed item information
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        item_index = request.args.get("index", type=int)
        if item_index is None:
            return (
                jsonify({"success": False, "error": "Missing index parameter"}),
                400,
            )

        # Get inventory (handle both naming conventions)
        inventory_list = getattr(player, "inventory_list", None) or getattr(player, "inventory", [])
        is_valid, error_msg = validate_item_index(item_index, len(inventory_list))
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        item = inventory_list[item_index]
        item_data = ItemDetailSerializer.serialize(
            item, inventory_index=item_index
        )

        return (
            jsonify({"success": True, "item": item_data}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/take", methods=["POST"])
def take_item():
    """Take item from current tile into inventory.

    JSON body:
        index: Item index on tile

    Returns:
        JSON with updated inventory
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        data = request.get_json() or {}
        is_valid, error_msg = validate_required_fields(data, ["index"])
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        item_index = data["index"]

        # Get current tile
        x, y = int(player.x), int(player.y)
        tile_data = current_app.game_service.get_tile(x, y)
        if not tile_data or "error" in tile_data:
            return jsonify({"success": False, "error": "Tile not found"}), 404

        # For now, just validate the index and return success
        # Full implementation requires game engine state manipulation
        is_valid, error_msg = validate_item_index(item_index, len(tile_data.get("items", [])))
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        inventory_data = InventorySerializer.serialize(player)
        return (
            jsonify({
                "success": True,
                "message": f"Item taken",
                "inventory": inventory_data,
            }),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/drop", methods=["POST"])
def drop_item():
    """Drop item from inventory onto current tile.

    JSON body:
        item_id: Unique ID of the item (preferred)
        item_index: Item index in inventory (fallback)

    Returns:
        JSON with updated inventory
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        data = request.get_json() or {}
        
        # Get item ID or index from request
        item_id = data.get("item_id")
        item_index = data.get("item_index")
        
        if not item_id and item_index is None:
            return jsonify({"success": False, "error": "Missing item_id or item_index"}), 400

        # Find the item
        item_to_drop, actual_index = get_item_and_index(player, item_id, item_index)
        if item_to_drop is None:
            return jsonify({"success": False, "error": "Item not found in inventory"}), 400

        # Get player's current position
        player_x = getattr(player, "x", 0)
        player_y = getattr(player, "y", 0)

        # Get the tile at player's current position
        tile = current_app.game_service.universe.get_tile(player_x, player_y)
        if not tile:
            return jsonify({"success": False, "error": "Current tile not found"}), 400

        # Remove item from inventory and add to tile
        inventory_list = getattr(player, "inventory_list", None) or getattr(player, "inventory", [])
        inventory_list.pop(actual_index)
        items_here = getattr(tile, "items_here", [])
        items_here.append(item_to_drop)

        # Return updated inventory
        inventory_data = InventorySerializer.serialize(player)
        return (
            jsonify({
                "success": True,
                "message": f"Item dropped",
                "inventory": inventory_data,
            }),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/equipment", methods=["GET"])
def get_equipment():
    """Get current equipment status.

    Returns:
        JSON with equipped items and stat bonuses
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        equipment_data = EquipmentSerializer.serialize(player)
        return (
            jsonify({"success": True, "equipment": equipment_data}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/equip", methods=["POST"])
def equip_item():
    """Equip an item from inventory.

    JSON body:
        item_id: Unique ID of the item (preferred)
        item_index: Item index in inventory (fallback)

    Returns:
        JSON with updated equipment and stats
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        data = request.get_json() or {}
        
        # Get item ID or index from request
        item_id = data.get("item_id")
        item_index = data.get("item_index")
        
        if not item_id and item_index is None:
            return jsonify({"success": False, "error": "Missing item_id or item_index"}), 400

        # Find the item
        item, actual_index = get_item_and_index(player, item_id, item_index)
        if item is None:
            return jsonify({"success": False, "error": "Item not found in inventory"}), 400

        # Check if equippable
        if not hasattr(item, "isequipped"):
            return (
                jsonify({"success": False, "error": f"{getattr(item, 'name', 'Item')} cannot be equipped"}),
                400,
            )

        # Check if already equipped
        if getattr(item, "isequipped", False):
            # Unequip it
            item.isequipped = False
            if hasattr(item, "on_unequip"):
                item.on_unequip(player)
            message = f"{item.name} unequipped"
        else:
            # Check if merchandise - can't equip until purchased
            if getattr(item, "merchandise", False):
                return (
                    jsonify({"success": False, "error": f"You must purchase {item.name} before equipping it"}),
                    400,
                )
            
            # Unequip other items of same maintype if needed
            inventory_list = getattr(player, "inventory_list", None) or getattr(player, "inventory", [])
            maintype = getattr(item, "maintype", None)
            if maintype:
                for other_item in inventory_list:
                    if other_item != item and getattr(other_item, "isequipped", False):
                        other_maintype = getattr(other_item, "maintype", None)
                        # For accessories, only replace same subtype (except multiple jewelry)
                        if maintype == "Accessory" and other_maintype == "Accessory":
                            other_subtype = getattr(other_item, "subtype", None)
                            item_subtype = getattr(item, "subtype", None)
                            if item_subtype == other_subtype:
                                # Check if it's a type that allows multiples (Ring, Bracelet, Earring)
                                if item_subtype in ["Ring", "Bracelet", "Earring"]:
                                    # Don't auto-unequip for these; let player manage multiples
                                    continue
                                # For single-slot accessories, replace
                                other_item.isequipped = False
                                if hasattr(other_item, "on_unequip"):
                                    other_item.on_unequip(player)
                        elif maintype == other_maintype:
                            # For non-accessories, replace the old one
                            other_item.isequipped = False
                            if hasattr(other_item, "on_unequip"):
                                other_item.on_unequip(player)
            
            # Equip the item
            item.isequipped = True
            if hasattr(item, "on_equip"):
                item.on_equip(player)
            
            # Update weapon reference if applicable
            if maintype == "Weapon":
                player.eq_weapon = item
            
            # Refresh stat bonuses
            from src import functions
            functions.refresh_stat_bonuses(player)
            
            message = f"{item.name} equipped"

        # Get updated equipment data
        from src.api.serializers.inventory import EquipmentSerializer
        equipment_data = EquipmentSerializer.serialize(player)
        inventory_data = InventorySerializer.serialize(player)
        
        return (
            jsonify({
                "success": True,
                "message": message,
                "equipment": equipment_data,
                "inventory": inventory_data,
            }),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/use", methods=["POST"])
def use_item():
    """Use an item from inventory.

    JSON body:
        item_id: Unique ID of the item (preferred)
        item_index: Item index in inventory (fallback)

    Returns:
        JSON with result of item use
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        data = request.get_json() or {}
        
        # Get item ID or index from request
        item_id = data.get("item_id")
        item_index = data.get("item_index")
        
        if not item_id and item_index is None:
            return jsonify({"success": False, "error": "Missing item_id or item_index"}), 400

        # Find the item
        item, actual_index = get_item_and_index(player, item_id, item_index)
        if item is None:
            return jsonify({"success": False, "error": "Item not found in inventory"}), 400

        # Check if merchandise - can't use until purchased
        if getattr(item, "merchandise", False):
            return (
                jsonify({"success": False, "error": f"You must purchase {item.name} before using it"}),
                400,
            )

        # Check if item is usable
        if not hasattr(item, "use"):
            return (
                jsonify({"success": False, "error": f"{getattr(item, 'name', 'Item')} cannot be used"}),
                400,
            )

        # Call the item's use method
        item.use(player)
        
        # Remove the item if it's consumable
        from src import items as items_module
        inventory_list = getattr(player, "inventory_list", None) or getattr(player, "inventory", [])
        if isinstance(item, items_module.Consumable):
            inventory_list.pop(actual_index)
            message = f"{item.name} consumed"
        else:
            message = f"{item.name} used"

        # Get updated inventory
        inventory_data = InventorySerializer.serialize(player)
        return (
            jsonify({
                "success": True,
                "message": message,
                "inventory": inventory_data,
            }),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/unequip", methods=["POST"])
def unequip_item():
    """Unequip an item from a slot.

    JSON body:
        slot: Equipment slot name (head, chest, etc.)

    Returns:
        JSON with updated equipment
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        data = request.get_json() or {}
        is_valid, error_msg = validate_required_fields(data, ["slot"])
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        slot_name = data["slot"]

        # Validate slot
        is_valid, error_msg = validate_equipment_slot(slot_name)
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        # Check if slot has item (handle both equipped and equipment)
        equipment_dict = getattr(player, "equipped", None) or getattr(player, "equipment", {})
        if not equipment_dict or slot_name not in equipment_dict:
            return (
                jsonify({"success": False, "error": f"Invalid slot: {slot_name}"}),
                400,
            )

        item = equipment_dict.get(slot_name)
        if not item:
            return (
                jsonify({"success": False, "error": f"No item equipped in {slot_name}"}),
                400,
            )

        # For now, just validate and return success
        # Full implementation requires game engine state manipulation
        equipment_data = EquipmentSerializer.serialize(player)
        return (
            jsonify({
                "success": True,
                "message": f"Unequipped item",
                "equipment": equipment_data,
            }),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/compare", methods=["GET"])
def compare_items():
    """Compare two items.

    Query params:
        current_index: Index of currently equipped item (optional)
        candidate_index: Index of item to compare

    Returns:
        JSON with comparison details and recommendation
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        current_index = request.args.get("current_index", type=int)
        candidate_index = request.args.get("candidate_index", type=int)

        if candidate_index is None:
            return (
                jsonify({"success": False, "error": "Missing candidate_index parameter"}),
                400,
            )

        # Get inventory (handle both naming conventions)
        inventory_list = getattr(player, "inventory_list", None) or getattr(player, "inventory", [])

        # Validate candidate index
        is_valid, error_msg = validate_item_index(candidate_index, len(inventory_list))
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        current_item = None
        if current_index is not None:
            is_valid, error_msg = validate_item_index(current_index, len(inventory_list))
            if not is_valid:
                return jsonify({"success": False, "error": error_msg}), 400
            current_item = inventory_list[current_index]

        candidate_item = inventory_list[candidate_index]

        # Compare items
        comparison_data = ItemComparisonSerializer.serialize(current_item, candidate_item)

        return (
            jsonify({"success": True, "comparison": comparison_data}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/stats", methods=["GET"])
def get_stats():
    """Get player stats with equipment bonuses.

    Returns:
        JSON with all player statistics
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        stats = {
            "health": getattr(player, "health", 100),
            "max_health": getattr(player, "max_health", 100),
            "stamina": getattr(player, "stamina", 100),
            "max_stamina": getattr(player, "max_stamina", 100),
            "attack": getattr(player, "attack", 10),
            "defense": getattr(player, "defense", 5),
            "magic_attack": getattr(player, "magic_attack", 8),
            "magic_defense": getattr(player, "magic_defense", 5),
            "speed": getattr(player, "speed", 10),
            "accuracy": getattr(player, "accuracy", 85),
            "evasion": getattr(player, "evasion", 10),
            "crit_chance": getattr(player, "crit_chance", 5),
            "level": getattr(player, "level", 1),
            "experience": getattr(player, "experience", 0),
        }

        return (
            jsonify({"success": True, "stats": stats}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/currency", methods=["GET"])
def get_currency():
    """Get player currency information.

    Returns:
        JSON with gold and other currency amounts
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        currency = {
            "gold": getattr(player, "gold", 0),
            "platinum": getattr(player, "platinum", 0),
        }

        return (
            jsonify({"success": True, "currency": currency}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
