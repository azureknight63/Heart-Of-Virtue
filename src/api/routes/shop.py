"""
Shop routes for the Flask API.

Provides endpoints for:
- Fetching merchant stock and player sell inventory
- Buying items from a merchant
- Selling items to a merchant
- Buying back recently sold items (before the game beat advances)

All price computation, gold validation, and weight validation happen in
GameService — the client only sends identifiers and quantity.

URL prefix: /api/shop  (registered in app.py)
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from src.api.services.validators import validate_required_fields
from src.api.middleware.auth import get_session_and_player

shop_bp = Blueprint("shop", __name__)

logger = logging.getLogger(__name__)


@shop_bp.route("/state", methods=["GET"])
def get_shop_state():
    """Fetch merchant stock, buyback items, and player's sellable inventory.

    Query params:
        npc_id (str): str(id(npc)) of the merchant on the current tile.

    Returns:
        {
            "success": true,
            "shop_state": {
                "npc_id", "npc_name", "shop_name",
                "buy_modifier", "sell_modifier",
                "stock": [...],
                "buyback_items": [...],
                "merchant_gold", "player_gold",
                "player_weight_current", "player_weight_max"
            },
            "sell_inventory": [...]
        }
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    npc_id = request.args.get("npc_id", "")
    if not npc_id:
        return jsonify({"success": False, "error": "Missing npc_id query parameter"}), 400

    try:
        result = current_app.game_service.get_shop_state(player, npc_id)
        return jsonify(result), 200 if result.get("success") else 404
    except Exception:
        logger.exception("Unhandled error in get_shop_state")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@shop_bp.route("/buy", methods=["POST"])
def buy_item():
    """Purchase an item from a merchant.

    Request body:
        {
            "npc_id": str,
            "item_id": str,
            "quantity": int  (optional, default 1)
        }

    Returns:
        {
            "success": true,
            "message": str,
            "gold_spent": int,
            "shop_state": {...},
            "sell_inventory": [...]
        }
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    try:
        data = request.get_json() or {}
        is_valid, error_msg = validate_required_fields(data, ["npc_id", "item_id"])
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        quantity = int(data.get("quantity", 1))
        if quantity < 1:
            return jsonify({"success": False, "error": "Quantity must be at least 1"}), 400

        result = current_app.game_service.shop_buy(
            player, data["npc_id"], data["item_id"], quantity
        )

        if result.get("success"):
            current_app.session_manager.save_session(session.session_id)

        return jsonify(result), 200 if result.get("success") else 400
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"Invalid input: {e}"}), 400
    except Exception:
        logger.exception("Unhandled error in buy_item")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@shop_bp.route("/sell", methods=["POST"])
def sell_item():
    """Sell an item from the player's inventory to a merchant.

    Request body:
        {
            "npc_id": str,
            "item_id": str,
            "quantity": int  (optional, default 1)
        }

    Returns:
        {
            "success": true,
            "message": str,
            "gold_gained": int,
            "shop_state": {...},
            "sell_inventory": [...]
        }
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    try:
        data = request.get_json() or {}
        is_valid, error_msg = validate_required_fields(data, ["npc_id", "item_id"])
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        quantity = int(data.get("quantity", 1))
        if quantity < 1:
            return jsonify({"success": False, "error": "Quantity must be at least 1"}), 400

        result = current_app.game_service.shop_sell(
            player, data["npc_id"], data["item_id"], quantity
        )

        if result.get("success"):
            current_app.session_manager.save_session(session.session_id)

        return jsonify(result), 200 if result.get("success") else 400
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"Invalid input: {e}"}), 400
    except Exception:
        logger.exception("Unhandled error in sell_item")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@shop_bp.route("/buyback", methods=["POST"])
def buyback_item():
    """Repurchase a recently sold item at the original sell price.

    Buyback offers expire when the game beat (game_tick) advances. The server
    validates eligibility — clients cannot submit prices.

    Request body:
        {
            "npc_id": str,
            "item_id": str   (the item_id from the buyback_items list)
        }

    Returns:
        {
            "success": true,
            "message": str,
            "gold_spent": int,
            "shop_state": {...},
            "sell_inventory": [...]
        }
    """
    _, session, player, error = get_session_and_player()
    if error:
        return error

    try:
        data = request.get_json() or {}
        is_valid, error_msg = validate_required_fields(data, ["npc_id", "item_id"])
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        result = current_app.game_service.shop_buyback(
            player, data["npc_id"], data["item_id"]
        )

        if result.get("success"):
            current_app.session_manager.save_session(session.session_id)

        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        logger.exception("Unhandled error in buyback_item")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
