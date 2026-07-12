"""
Inventory and equipment management routes for the Flask API.

Provides endpoints for:
- Inventory management (list, examine, take, drop)
- Equipment management (equip, unequip, compare)
- Currency/stat queries
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from src.api.services.validators import (
    validate_item_index,
)
from src.api.serializers.inventory import (
    EquipmentSerializer,
    ItemComparisonSerializer,
    InventorySerializer,
    ItemDetailSerializer,
)
from src.api.middleware.auth import get_session_and_player

# Create blueprint
inventory_bp = Blueprint("inventory", __name__)

logger = logging.getLogger(__name__)


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


def _resolve_ally_target(player, target_id: str):
    """Resolve a target_id string to an NPC ally object.

    Accepts IDs in the form "ally_<python-id>" as produced by the party_members
    serializer and the combat serializer.  Returns None if not found.
    """
    if target_id.startswith("ally_"):
        target_id = target_id[len("ally_"):]
    raw_id = target_id
    # Skip index 0 (the player) — allies start at index 1
    for ally in getattr(player, "combat_list_allies", [])[1:]:
        if str(id(ally)) == raw_id:
            return ally
    return None


@inventory_bp.route("/inventory", methods=["GET"])
def get_inventory():
    """Get player inventory.

    Returns:
        JSON with complete inventory including weight and items
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    try:
        inventory_data = InventorySerializer.serialize(player)
        return (
            jsonify({"success": True, "inventory": inventory_data}),
            200,
        )
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@inventory_bp.route("/inventory/examine", methods=["GET"])
def examine_item():
    """Examine specific item in inventory.

    Query params:
        index: Item index in inventory

    Returns:
        JSON with detailed item information
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

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
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@inventory_bp.route("/inventory/drop", methods=["POST"])
def drop_item():
    """Drop item from inventory onto current tile.

    JSON body:
        item_id: Unique ID of the item (preferred)
        item_index: Item index in inventory (fallback)

    Returns:
        JSON with updated inventory
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

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
        item_to_drop, _actual_index = get_item_and_index(player, item_id, item_index)
        if item_to_drop is None:
            return (
                jsonify({"success": False, "error": "Item not found in inventory"}),
                400,
            )

        # Delegate the drop (and any unequip-before-drop) to the engine layer.
        result = current_app.game_service.drop_item(player, item_to_drop)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        # Return updated inventory
        inventory_data = InventorySerializer.serialize(player)
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Item dropped",
                    "messages": result.get("messages", []),
                    "inventory": inventory_data,
                }
            ),
            200,
        )
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@inventory_bp.route("/equipment", methods=["GET"])
def get_equipment():
    """Get current equipment status.

    Returns:
        JSON with equipped items and stat bonuses
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    try:
        equipment_data = EquipmentSerializer.serialize(player)
        return (
            jsonify({"success": True, "equipment": equipment_data}),
            200,
        )
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@inventory_bp.route("/inventory/equip", methods=["POST"])
def equip_item():
    """Equip an item from inventory.

    JSON body:
        item_id: Unique ID of the item (preferred)
        item_index: Item index in inventory (fallback)

    Returns:
        JSON with updated equipment and stats
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

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
        item, _actual_index = get_item_and_index(player, item_id, item_index)
        if item is None:
            return (
                jsonify({"success": False, "error": "Item not found in inventory"}),
                400,
            )

        # Delegate the equip/unequip toggle to the engine layer.
        result = current_app.game_service.equip_item(player, item)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        equipment_data = EquipmentSerializer.serialize(player)
        inventory_data = InventorySerializer.serialize(player)

        return (
            jsonify(
                {
                    "success": True,
                    "message": result["message"],
                    "messages": result.get("messages", []),
                    "equipment": equipment_data,
                    "inventory": inventory_data,
                }
            ),
            200,
        )
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@inventory_bp.route("/inventory/use", methods=["POST"])
def use_item():
    """Use an item from inventory.

    JSON body:
        item_id: Unique ID of the item (preferred)
        item_index: Item index in inventory (fallback)
        target_id: Optional ally ID (e.g. "ally_<python-id>"). When provided
                   the item's effect is applied to that ally instead of self.
                   In combat the target must be within 5 ft.

    Returns:
        JSON with result of item use
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    try:
        data = request.get_json() or {}

        # Get item ID or index from request
        item_id = data.get("item_id")
        item_index = data.get("item_index")
        target_id = data.get("target_id")

        if not item_id and item_index is None:
            return (
                jsonify({"success": False, "error": "Missing item_id or item_index"}),
                400,
            )

        # Find the item
        item, _actual_index = get_item_and_index(player, item_id, item_index)
        if item is None:
            return (
                jsonify({"success": False, "error": "Item not found in inventory"}),
                400,
            )

        # Resolve optional ally target (transport-layer ID → engine object).
        item_target = player
        if target_id:
            resolved = _resolve_ally_target(player, target_id)
            if resolved is None:
                return (
                    jsonify({"success": False, "error": "Target not found"}),
                    400,
                )
            item_target = resolved

        # Delegate the effect (gating, range check, narration capture, and
        # combat-log mirroring) to the engine layer.
        result = current_app.game_service.use_item(player, item, target=item_target)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        # Get updated inventory
        inventory_data = InventorySerializer.serialize(player)

        # Prepare response
        response_data = {
            "success": True,
            "message": result["message"],
            "messages": result.get("messages", []),
            "inventory": inventory_data,
            "target_name": result.get("target_name"),
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
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@inventory_bp.route("/inventory/unequip", methods=["POST"])
def unequip_item():
    """Unequip an item from inventory.

    JSON body:
        item_id: Unique ID of the item (preferred)
        item_index: Item index in inventory (fallback)

    Returns:
        JSON with updated equipment and inventory
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    try:
        data = request.get_json() or {}

        item_id = data.get("item_id")
        item_index = data.get("item_index")

        if not item_id and item_index is None:
            return (
                jsonify({"success": False, "error": "Missing item_id or item_index"}),
                400,
            )

        # Find the item
        item, _actual_index = get_item_and_index(player, item_id, item_index)
        if item is None:
            return (
                jsonify({"success": False, "error": "Item not found in inventory"}),
                400,
            )

        # Delegate the unequip to the engine layer.
        result = current_app.game_service.unequip_item(player, item)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        equipment_data = EquipmentSerializer.serialize(player)
        inventory_data = InventorySerializer.serialize(player)

        return (
            jsonify(
                {
                    "success": True,
                    "message": result["message"],
                    "messages": result.get("messages", []),
                    "equipment": equipment_data,
                    "inventory": inventory_data,
                }
            ),
            200,
        )
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@inventory_bp.route("/inventory/compare", methods=["GET"])
def compare_items():
    """Compare two items.

    Query params:
        current_index: Index of currently equipped item (optional)
        candidate_index: Index of item to compare

    Returns:
        JSON with comparison details and recommendation
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

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
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@inventory_bp.route("/inventory/stats", methods=["GET"])
def get_stats():
    """Get player stats with equipment bonuses.

    Delegates to game_service.get_player_stats to keep attribute access
    centralised and avoid directly reaching into engine internals.

    Returns:
        JSON with all player statistics
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    try:
        stats = current_app.game_service.get_player_stats(player)
        return jsonify({"success": True, "stats": stats}), 200
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@inventory_bp.route("/inventory/currency", methods=["GET"])
def get_currency():
    """Get player currency information.

    Returns:
        JSON with gold and other currency amounts
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    try:
        currency = {
            "gold": getattr(player, "gold", 0),
            "platinum": getattr(player, "platinum", 0),
        }

        return (
            jsonify({"success": True, "currency": currency}),
            200,
        )
    except Exception:
        logger.exception("Unhandled error in inventory route")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
