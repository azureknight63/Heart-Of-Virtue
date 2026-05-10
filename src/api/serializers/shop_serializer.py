"""Serializers for shop/merchant state exposed to the web API."""

from typing import Any, Dict, List


def _get_gold(inventory: list) -> int:
    """Mirror of interface.get_gold without importing the terminal module."""
    total = 0
    for item in inventory:
        if getattr(item, "name", None) == "Gold":
            total += getattr(item, "amt", 0)
    return total


def _serialize_shop_item(item: Any, price_modifier: float) -> Dict:
    """Serialize a single merchant stock item with a computed price."""
    count = 1
    if hasattr(item, "count"):
        count = item.count
    elif hasattr(item, "quantity"):
        count = item.quantity

    base_value = getattr(item, "value", 0)
    price = max(1, int(base_value * price_modifier))

    return {
        "id": str(id(item)),
        "name": getattr(item, "name", "Unknown"),
        "type": type(item).__name__,
        "subtype": getattr(item, "subtype", ""),
        "description": getattr(item, "description", ""),
        "value": base_value,
        "price": price,
        "weight": getattr(item, "weight", 0.0),
        "count": count,
        "is_stackable": count > 1,
        "power": getattr(item, "power", None),
        "is_buyback": False,
    }


def _serialize_buyback_item(entry: Dict) -> Dict:
    """Serialize a buyback ledger entry for display in the buy tab."""
    return {
        "id": entry["item_id"],
        "name": entry["item_name"],
        "type": entry.get("type", ""),
        "subtype": entry.get("subtype", ""),
        "description": entry.get("description", ""),
        "value": entry.get("value", 0),
        "price": entry["buyback_price"],
        "weight": entry["weight"],
        "count": entry["count"],
        "is_stackable": entry["count"] > 1,
        "power": entry.get("power"),
        "is_buyback": True,
    }


class ShopSerializer:
    """Serialize merchant shop state for the web API."""

    @staticmethod
    def flush_stale_buyback(merchant: Any, current_game_tick: int) -> None:
        """Remove buyback ledger entries that were acquired before the current game tick.

        Separated from serialize_state so callers can flush before performing
        ledger lookups (e.g. shop_buyback) without coupling flush to serialization.
        """
        ledger: List[Dict] = getattr(merchant, "_buyback_ledger", [])
        merchant._buyback_ledger = [
            e for e in ledger if e["beat_acquired"] >= current_game_tick
        ]

    @staticmethod
    def serialize_state(
        merchant: Any,
        player: Any,
        current_game_tick: int,
    ) -> Dict:
        """Return the full shop state for GET /api/shop/state.

        Does NOT flush the buyback ledger — callers are responsible for calling
        flush_stale_buyback(merchant, tick) before serialize_state if needed.

        Args:
            merchant: Merchant NPC instance (has .shop, .inventory, ._buyback_ledger).
            player: Player instance (has .inventory, .weight_current, .weight_tolerance).
            current_game_tick: player.universe.game_tick value.

        Returns:
            JSON-safe dict with stock, buyback_items, player state, merchant gold.
        """
        shop = getattr(merchant, "shop", None)
        buy_mod = getattr(shop, "buy_modifier", 1.0) if shop else 1.0
        sell_mod = getattr(shop, "sell_modifier", 0.5) if shop else 0.5
        shop_name = getattr(shop, "title", None) or f"{merchant.name}'s Shop"

        # Serialize regular stock (exclude Gold items)
        merchant_inv = getattr(merchant, "inventory", [])
        ledger: List[Dict] = getattr(merchant, "_buyback_ledger", [])
        buyback_ids = {e["item_id"] for e in ledger}
        stock = [
            _serialize_shop_item(item, buy_mod)
            for item in merchant_inv
            if getattr(item, "name", None) != "Gold"
            and str(id(item)) not in buyback_ids
        ]

        # Serialize buyback items
        buyback_items = [_serialize_buyback_item(e) for e in ledger]

        player_inv = getattr(player, "inventory", [])
        player.refresh_weight()

        return {
            "npc_id": str(id(merchant)),
            "npc_name": getattr(merchant, "name", "Merchant"),
            "shop_name": shop_name,
            "buy_modifier": buy_mod,
            "sell_modifier": sell_mod,
            "stock": stock,
            "buyback_items": buyback_items,
            "merchant_gold": _get_gold(merchant_inv),
            "player_gold": _get_gold(player_inv),
            "player_weight_current": getattr(player, "weight_current", 0.0),
            "player_weight_max": getattr(player, "weight_tolerance", 100.0),
        }

    @staticmethod
    def serialize_player_sellable(player: Any, sell_modifier: float) -> List[Dict]:
        """Return the player's inventory formatted for the sell tab.

        Excludes Gold items and equipped items (can't sell what you're wearing).

        Args:
            player: Player instance.
            sell_modifier: Price multiplier for selling (e.g. 0.5).

        Returns:
            List of item dicts with offer price computed.
        """
        result = []
        player_inv = getattr(player, "inventory", [])
        for item in player_inv:
            if getattr(item, "name", None) == "Gold":
                continue
            if getattr(item, "is_equipped", False) or getattr(item, "isequipped", False):
                continue
            base_value = getattr(item, "value", 0)
            if not base_value:
                continue
            offer = max(1, int(base_value * sell_modifier))
            count = getattr(item, "count", getattr(item, "quantity", 1))
            result.append({
                "id": str(id(item)),
                "name": getattr(item, "name", "Unknown"),
                "type": type(item).__name__,
                "subtype": getattr(item, "subtype", ""),
                "description": getattr(item, "description", ""),
                "value": base_value,
                "offer": offer,
                "weight": getattr(item, "weight", 0.0),
                "count": count,
                "is_stackable": count > 1,
                "power": getattr(item, "power", None),
            })
        return result
