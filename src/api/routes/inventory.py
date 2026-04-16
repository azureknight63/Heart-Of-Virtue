"""
Inventory and equipment management routes for the Flask API.

Provides endpoints for:
- Inventory management (list, examine, take, drop)
- Equipment management (equip, unequip, compare)
- Currency/stat queries
"""

from flask import Blueprint, current_app, jsonify, request
import contextlib
import io
import re
from unittest.mock import patch

from src.api.services.validators import (
    validate_equipment_slot,
    validate_item_index,
    validate_required_fields,
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
        return (
            None,
            None,
            jsonify({"success": False, "error": "Missing authorization"}),
            401,
        )

    session_id = auth_header[7:]
    session_manager = current_app.session_manager
    session = session_manager.get_session(session_id)

    if not session:
        return (
            None,
            None,
            jsonify({"success": False, "error": "Invalid or expired session"}),
            401,
        )

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
    inventory_list = getattr(player, "inventory_list", None) or getattr(
        player, "inventory", []
    )

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
        inventory_list = getattr(player, "inventory_list", None) or getattr(
            player, "inventory", []
        )
        is_valid, error_msg = validate_item_index(item_index, len(inventory_list))
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        item = inventory_list[item_index]
        item_data = ItemDetailSerializer.serialize(item, inventory_index=item_index)

        return (
            jsonify({"success": True, "item": item_data}),
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
            return (
                jsonify({"success": False, "error": "Missing item_id or item_index"}),
                400,
            )

        # Find the item
        item_to_drop, actual_index = get_item_and_index(player, item_id, item_index)
        if item_to_drop is None:
            return (
                jsonify({"success": False, "error": "Item not found in inventory"}),
                400,
            )

        # Get player's current position
        player_x = getattr(player, "location_x", 0)
        player_y = getattr(player, "location_y", 0)

        # Get the tile at player's current position
        tile = player.universe.get_tile(player_x, player_y)
        if not tile:
            return jsonify({"success": False, "error": "Current tile not found"}), 400

        # If equipped, unequip cleanly before dropping
        if getattr(item_to_drop, "isequipped", False):
            item_to_drop.isequipped = False
            if hasattr(item_to_drop, "on_unequip"):
                item_to_drop.on_unequip(player)
            if getattr(item_to_drop, "maintype", None) == "Weapon":
                player.eq_weapon = getattr(player, "fists", None)
            from src import functions

            functions.refresh_stat_bonuses(player)

        # Remove item from inventory and add to tile
        inventory_list = getattr(player, "inventory_list", None) or getattr(
            player, "inventory", []
        )
        inventory_list.pop(actual_index)
        items_here = getattr(tile, "items_here", [])
        items_here.append(item_to_drop)
        # Update item description if it's stackable
        if hasattr(item_to_drop, "stack_grammar"):
            item_to_drop.stack_grammar()

        # Return updated inventory
        inventory_data = InventorySerializer.serialize(player)
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Item dropped",
                    "inventory": inventory_data,
                }
            ),
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
            return (
                jsonify({"success": False, "error": "Missing item_id or item_index"}),
                400,
            )

        # Find the item
        item, actual_index = get_item_and_index(player, item_id, item_index)
        if item is None:
            return (
                jsonify({"success": False, "error": "Item not found in inventory"}),
                400,
            )

        # Check if equippable
        if not hasattr(item, "isequipped"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"{getattr(item, 'name', 'Item')} cannot be equipped",
                    }
                ),
                400,
            )

        # Check if already equipped
        if getattr(item, "isequipped", False):
            # Unequip it
            item.isequipped = False
            if hasattr(item, "on_unequip"):
                item.on_unequip(player)
            if getattr(item, "maintype", None) == "Weapon":
                player.eq_weapon = getattr(player, "fists", None)
            from src import functions

            functions.refresh_stat_bonuses(player)
            message = f"{item.name} unequipped"
        else:
            # Check if merchandise - can't equip until purchased
            if getattr(item, "merchandise", False):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": f"You must purchase {item.name} before equipping it",
                        }
                    ),
                    400,
                )

            # Unequip other items of same maintype if needed
            inventory_list = getattr(player, "inventory_list", None) or getattr(
                player, "inventory", []
            )
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
            jsonify(
                {
                    "success": True,
                    "message": message,
                    "equipment": equipment_data,
                    "inventory": inventory_data,
                }
            ),
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
            return (
                jsonify({"success": False, "error": "Missing item_id or item_index"}),
                400,
            )

        # Find the item
        item, actual_index = get_item_and_index(player, item_id, item_index)
        if item is None:
            return (
                jsonify({"success": False, "error": "Item not found in inventory"}),
                400,
            )

        # Check if merchandise - can't use until purchased
        if getattr(item, "merchandise", False):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"You must purchase {item.name} before using it",
                    }
                ),
                400,
            )

        # Check if item is usable
        if not hasattr(item, "use"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"{getattr(item, 'name', 'Item')} cannot be used",
                    }
                ),
                400,
            )

        # Capture output from item use
        f = io.StringIO()

        def mock_cprint(text, *args, **kwargs):
            f.write(str(text) + "\n")

        def mock_print_slow(text, speed="slow"):
            f.write(str(text) + "\n")

        with contextlib.redirect_stdout(f), patch(
            "neotermcolor.cprint", mock_cprint
        ), patch("src.functions.print_slow", mock_print_slow), patch(
            "functions.print_slow", mock_print_slow
        ), patch(
            "time.sleep", return_value=None
        ):
            # Call the item's use method
            item.use(player)

        output = f.getvalue()
        # Clean up output (remove ANSI codes)
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_output = ansi_escape.sub("", output).strip()

        if not clean_output:
            clean_output = f"{item.name} used"

        # If in combat, add to combat log
        if getattr(player, "in_combat", False):
            if hasattr(player, "_combat_adapter"):
                adapter = player._combat_adapter
                current_beat = getattr(player, "combat_beat", 0)
                # Split by lines and add each as a log entry
                for line in clean_output.split("\n"):
                    if line.strip():
                        adapter._add_log_entry(current_beat, line.strip(), "combat")
            else:
                # Fallback if adapter not initialized
                if not hasattr(player, "combat_log"):
                    player.combat_log = []
                for line in clean_output.split("\n"):
                    if line.strip():
                        player.combat_log.append(
                            {
                                "round": getattr(player, "combat_beat", 0),
                                "message": line.strip(),
                                "type": "combat",
                            }
                        )

        # Get updated inventory
        inventory_data = InventorySerializer.serialize(player)

        # Prepare response
        response_data = {
            "success": True,
            "message": clean_output,
            "inventory": inventory_data,
        }

        # If in combat, also return updated combat state
        if getattr(player, "in_combat", False):
            from src.api.serializers.combat import CombatStateSerializer

            combat_state = CombatStateSerializer.serialize_combat_state(
                player,
                getattr(player, "combat_list", []),
                round_number=getattr(player, "combat_beat", 0),
            )
            response_data["combat_state"] = combat_state

        return (
            jsonify(response_data),
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
        equipment_dict = getattr(player, "equipped", None) or getattr(
            player, "equipment", {}
        )
        if not equipment_dict or slot_name not in equipment_dict:
            return (
                jsonify({"success": False, "error": f"Invalid slot: {slot_name}"}),
                400,
            )

        item = equipment_dict.get(slot_name)
        if not item:
            return (
                jsonify(
                    {"success": False, "error": f"No item equipped in {slot_name}"}
                ),
                400,
            )

        # For now, just validate and return success
        # Full implementation requires game engine state manipulation
        equipment_data = EquipmentSerializer.serialize(player)
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Unequipped item",
                    "equipment": equipment_data,
                }
            ),
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
                jsonify(
                    {"success": False, "error": "Missing candidate_index parameter"}
                ),
                400,
            )

        # Get inventory (handle both naming conventions)
        inventory_list = getattr(player, "inventory_list", None) or getattr(
            player, "inventory", []
        )

        # Validate candidate index
        is_valid, error_msg = validate_item_index(candidate_index, len(inventory_list))
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        current_item = None
        if current_index is not None:
            is_valid, error_msg = validate_item_index(
                current_index, len(inventory_list)
            )
            if not is_valid:
                return jsonify({"success": False, "error": error_msg}), 400
            current_item = inventory_list[current_index]

        candidate_item = inventory_list[candidate_index]

        # Compare items
        comparison_data = ItemComparisonSerializer.serialize(
            current_item, candidate_item
        )

        return (
            jsonify({"success": True, "comparison": comparison_data}),
            200,
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/inventory/stats", methods=["GET"])
def get_stats():
    """Get player stats with equipment bonuses.

    Delegates to game_service.get_player_stats to keep attribute access
    centralised and avoid directly reaching into engine internals.

    Returns:
        JSON with all player statistics
    """
    session, player, error, status = get_session_and_player()
    if error:
        return error, status

    try:
        stats = current_app.game_service.get_player_stats(player)
        return jsonify({"success": True, "stats": stats}), 200
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
