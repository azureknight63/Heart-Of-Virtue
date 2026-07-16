"""Serializers for shop/merchant state exposed to the web API."""

import math
from typing import Any, Dict, List


def _effective_modifier(merchant: Any, player: Any, attr: str, base_default: float,
                        sign: int) -> float:
    """Compute ``base * (1 + sign * price_mod)`` as a finite float, defensively.

    Shared by the buy/sell modifier helpers. A degraded merchant/player (missing
    or wrong-type ``buy_modifier``/``sell_modifier``/``reputation``) falls back
    to a sane finite base rather than raising or returning a non-numeric value —
    these feed downstream price arithmetic, so they must always be a float
    (issue #295).
    """
    from src.api.serializers.reputation import NPCRelationshipSerializer

    base = getattr(merchant, attr, base_default)
    try:
        base = float(base)
    except (TypeError, ValueError):
        base = base_default
    if not math.isfinite(base):
        base = base_default
    try:
        rep_map = getattr(player, "reputation", {})
        reputation = rep_map.get(getattr(merchant, "name", ""), 0) \
            if isinstance(rep_map, dict) else 0
        price_mod = float(NPCRelationshipSerializer.get_price_modifier(reputation))
        result = base * (1 + sign * price_mod)
        return result if math.isfinite(result) else base
    except Exception:  # noqa: BLE001 - reputation math must never break pricing
        return base


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
        "merchandise": getattr(item, "merchandise", False),
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
        "merchandise": True,
    }


class ShopSerializer:
    """Serialize merchant shop state for the web API."""

    @staticmethod
    def get_effective_buy_modifier(merchant: Any, player: Any) -> float:
        """Merchant's buy_modifier adjusted by the player's reputation with them.

        Friendly merchants charge less; hostile merchants charge more. Shared
        by serialize_state and GameService.shop_buy so displayed and charged
        prices always match.
        """
        return _effective_modifier(merchant, player, "buy_modifier", 1.0, sign=-1)

    @staticmethod
    def get_effective_sell_modifier(merchant: Any, player: Any) -> float:
        """Merchant's sell_modifier adjusted by the player's reputation with them.

        Friendly merchants pay more; hostile merchants pay less. Shared by
        serialize_state and GameService.shop_sell so displayed and paid
        prices always match.
        """
        return _effective_modifier(merchant, player, "sell_modifier", 0.5, sign=1)

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
            merchant: Merchant NPC instance (has .buy_modifier, .sell_modifier,
                .shop_name, .inventory, ._buyback_ledger).
            player: Player instance (has .inventory, .weight_current, .weight_tolerance).
            current_game_tick: player.universe.game_tick value.

        Returns:
            JSON-safe dict with stock, buyback_items, player state, merchant gold.
        """
        buy_mod = ShopSerializer.get_effective_buy_modifier(merchant, player)
        sell_mod = ShopSerializer.get_effective_sell_modifier(merchant, player)
        shop_name = getattr(merchant, "shop_name", None) or f"{merchant.name}'s Shop"

        # Serialize regular stock (exclude Gold items and non-merchandise items;
        # only merchandise==True items belong in the BUY tab)
        merchant_inv = getattr(merchant, "inventory", [])
        ledger: List[Dict] = getattr(merchant, "_buyback_ledger", [])
        buyback_ids = {e["item_id"] for e in ledger}
        stock = [
            _serialize_shop_item(item, buy_mod)
            for item in merchant_inv
            if getattr(item, "name", None) != "Gold"
            and str(id(item)) not in buyback_ids
            and getattr(item, "merchandise", False)
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
            # Merchandise items belong to the shop (BUY tab); exclude from SELL tab
            if getattr(item, "merchandise", False):
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
