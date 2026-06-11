"""Compatibility shim.

The terminal menu interface classes (BaseInterface and its subclasses
ShopInterface / InventoryInterface / RoomTakeInterface / ContainerLootInterface,
etc.) have been removed — the game is web-only and drives all interaction
through the Flask API. This module survives only to re-export the shared
inventory/gold helpers that engine code and tests still import from `interface`.
"""

from inventory_utils import get_gold, transfer_gold, transfer_item  # noqa: F401
