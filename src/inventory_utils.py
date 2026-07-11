"""Shared inventory/gold transfer utilities.

These pure helpers were extracted from the former terminal ``interface`` module
so the engine and web API can share them without depending on any terminal UI.
They contain no user-facing I/O; error conditions are logged rather than printed.
"""

import copy as _copy
import logging
from typing import TYPE_CHECKING, Optional, Union

from src.functions import stack_inv_items

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids circular imports
    from src.player import Player
    from src.npc import NPC
    from src.objects import Object
    from src.items import Item

logger = logging.getLogger(__name__)


def get_gold(inventory: list) -> int:
    """
    Calculate total gold amount in an inventory list.
    :param inventory:
    :return:
    """
    gold_amt = 0
    for item in inventory:
        if hasattr(item, "name") and item.name == "Gold":
            gold_amt += getattr(item, "amt", 0)
    return gold_amt


def transfer_gold(from_inventory: list, to_inventory: list, amt: int) -> None:
    """
    Transfer a quantity of gold between two inventories.

    Ensures each inventory has a `Gold` item (creates one with zero amount if missing),
    then subtracts `amt` from the `from_inventory` gold item and adds `amt` to the
    `to_inventory` gold item. Resulting negative amounts are clamped to zero.

    Parameters:
        from_inventory: list - inventory containing items; should contain or will be given a `Gold` item.
        to_inventory: list - inventory containing items; should contain or will be given a `Gold` item.
        amt: int - amount of gold to move from `from_inventory` to `to_inventory`.
                   Positive `amt` moves gold from `from_inventory` to `to_inventory`.
    """

    def _find_gold_item(inventory: list) -> "Optional[object]":
        for search_item in inventory:
            if hasattr(search_item, "name") and search_item.name == "Gold":
                return search_item
        return None

    def _create_new_gold_item(inventory: list) -> object:
        from src.items import Gold

        new_gold = Gold(0)
        inventory.append(new_gold)
        return new_gold

    gold_item_to = _find_gold_item(to_inventory)
    if not gold_item_to:
        gold_item_to = _create_new_gold_item(to_inventory)

    gold_item_from = _find_gold_item(from_inventory)
    if not gold_item_from:
        gold_item_from = _create_new_gold_item(from_inventory)

    if gold_item_from and gold_item_to:
        gold_item_from.amt -= amt
        gold_item_to.amt += amt
        if gold_item_from.amt < 0:
            gold_item_from.amt = 0
        if gold_item_to.amt < 0:
            gold_item_to.amt = 0

        # Sync count and update description
        for item in [gold_item_from, gold_item_to]:
            if hasattr(item, "count"):
                item.count = item.amt
            if hasattr(item, "stack_grammar") and callable(item.stack_grammar):
                item.stack_grammar()


def transfer_item(
    source: "Union[Player, NPC, Object]",
    target: "Union[Player, NPC, Object]",
    item: "Item",
    qty: int = 1,
) -> None:
    """
    Transfer an item (or a quantity of a stackable item) from `source` to `target`.

    Behavior:
    - Both `source` and `target` must have an `inventory` attribute (list-like). If not, a
      message is logged and the function returns.
    - If `item` is stackable (has `count`) and `qty` > 1, the requested quantity is clamped
      to the available `item.count`. The source `item.count` is reduced and a copy with the
      transferred quantity is appended to the target inventory.
    - If the item is not stackable or a single unit is transferred, the whole item object is
      moved from `source.inventory` to `target.inventory`.
    - The `merchandise` flag is set on moved items according to whether the `target` is a
      `Player` (False) or not (True).
    - After transfer, inventories may be stacked via `stack_inv_items` and `refresh_weight`
      is called on both `source` and `target` if available.
    - No exceptions are raised; failures are communicated via logged messages.
    """
    if not hasattr(source, "inventory") or not hasattr(target, "inventory"):
        logger.warning("transfer_item: source or target does not have an inventory")
        return
    from_inventory = source.inventory
    to_inventory = target.inventory

    # Helper to set merchandise flag consistently
    def _set_merch_flag(obj, item_target, item_source):
        if not hasattr(obj, "merchandise"):
            return

        def is_player(ent):
            return getattr(ent, "name", None) == "Jean"

        def is_merchant(ent):
            return hasattr(ent, "shop")

        def is_merchant_container(ent):
            return hasattr(ent, "merchant") and bool(getattr(ent, "merchant", ""))

        if is_player(item_target):
            if is_merchant(item_source):
                # Purchased from a merchant NPC -> no longer merchandise
                obj.merchandise = False
            else:
                # Check if we are in a shop (looting a shop container or player on a shop map)
                is_in_shop = False
                if is_merchant_container(item_source):
                    is_in_shop = True
                else:
                    current_map = getattr(item_target, "map", None)
                    if not current_map and hasattr(item_target, "current_room") and item_target.current_room:
                        current_map = getattr(item_target.current_room, "map", None)
                    if current_map and hasattr(current_map, "get"):
                        map_name = current_map.get("name")
                        if isinstance(map_name, str) and "shop" in map_name.lower():
                            is_in_shop = True
                obj.merchandise = is_in_shop
        elif is_player(item_source):
            if is_merchant(item_target) or is_merchant_container(item_target):
                # Sold/placed into a merchant/shop container -> becomes merchandise
                obj.merchandise = True
            else:
                # Sold/placed into a container inside a shop map -> becomes merchandise
                is_in_shop = False
                current_map = getattr(item_source, "map", None)
                if not current_map and hasattr(item_source, "current_room") and item_source.current_room:
                    current_map = getattr(item_source.current_room, "map", None)
                if current_map and hasattr(current_map, "get"):
                    map_name = current_map.get("name")
                    if isinstance(map_name, str) and "shop" in map_name.lower():
                        is_in_shop = True
                if is_in_shop:
                    obj.merchandise = True

    # Ensure qty is at least 1
    if qty < 1:
        qty = 1

    # If the item isn't in the source inventory, nothing to do
    if item not in from_inventory:
        logger.warning(
            "transfer_item: item %s not found in source inventory",
            getattr(item, "name", "Unknown"),
        )
        return

    # Handle stackable items
    if hasattr(item, "count") and getattr(item, "count", 0) > 1:
        available = getattr(item, "count", 0)
        # Clamp requested qty to available
        if qty >= available:
            # Move entire stack object
            try:
                from_inventory.remove(item)
            except ValueError:
                pass
            to_inventory.append(item)
            _set_merch_flag(item, target, source)
        else:
            # Split stack: decrement source and create a new instance for the transferred qty
            item.count = available - qty
            if hasattr(item, "stack_grammar") and callable(item.stack_grammar):
                item.stack_grammar()
            # Create a shallow copy of the item object then set count to qty
            new_item = item.__class__.__new__(item.__class__)
            if hasattr(item, "__dict__"):
                for k, v in item.__dict__.items():
                    try:
                        setattr(new_item, k, _copy.copy(v))
                    except Exception:
                        try:
                            setattr(new_item, k, v)
                        except Exception:
                            pass
            setattr(new_item, "count", qty)
            if hasattr(new_item, "stack_grammar") and callable(new_item.stack_grammar):
                new_item.stack_grammar()
            _set_merch_flag(new_item, target, source)
            to_inventory.append(new_item)
            # If source stack was reduced to zero for some reason, remove it
            if getattr(item, "count", 0) <= 0:
                try:
                    from_inventory.remove(item)
                except ValueError:
                    pass
    else:
        # Non-stackable or single-count item: move the object itself
        try:
            from_inventory.remove(item)
        except ValueError:
            pass
        to_inventory.append(item)
        _set_merch_flag(item, target, source)

    # Attempt to stack items on the receiving side if needed
    try:
        stack_inv_items(target)
    except Exception:
        pass

    # Refresh weights if possible
    if hasattr(source, "refresh_weight") and callable(source.refresh_weight):
        try:
            source.refresh_weight()
        except Exception:
            pass
    if hasattr(target, "refresh_weight") and callable(target.refresh_weight):
        try:
            target.refresh_weight()
        except Exception:
            pass
