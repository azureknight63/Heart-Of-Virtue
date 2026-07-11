"""Lock in removal of the terminal menu interface layer.

The game is web-only. The terminal menu classes (BaseInterface and its
subclasses InventoryInterface / InventoryCategorySubmenu / RoomTakeInterface)
have been removed, along with the Player verbs that only launched them
(Player.take / Player.print_inventory). Room-item pickup is handled by
Item.take() + GameService.interact_with_target; inventory browsing is handled by
the /inventory routes.

`interface` survives only as a thin re-export of the shared inventory/gold
helpers that callers and tests still import from it.
"""

import importlib

from src.player import Player


class TestTerminalMenusRemoved:
    def test_interface_has_no_menu_classes(self):
        interface = importlib.import_module("src.interface")
        for name in (
            "BaseInterface",
            "InventoryInterface",
            "InventoryCategorySubmenu",
            "RoomTakeInterface",
        ):
            assert not hasattr(interface, name), f"{name} should be deleted"

    def test_inventory_helpers_still_reexported(self):
        interface = importlib.import_module("src.interface")
        assert hasattr(interface, "get_gold")
        assert hasattr(interface, "transfer_item")
        assert hasattr(interface, "transfer_gold")

    def test_player_has_no_terminal_ui_verbs(self):
        # These only launched terminal menus; the web client uses the API paths.
        assert not hasattr(Player, "take")
        assert not hasattr(Player, "print_inventory")

    def test_item_take_still_exists(self):
        """The real ground-pickup verb (used by the API) must remain."""
        from src.items import Item

        assert hasattr(Item, "take")
