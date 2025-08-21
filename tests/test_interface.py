import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import unittest
from unittest.mock import patch, call
import interface  # noqa
import player  # noqa
import re

# Utility to strip ANSI color codes
ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
def strip_ansi(s):
    return ansi_escape.sub('', s)

class PatchedPrint:
    def __init__(self, mock_print):
        self.mock_print = mock_print
    def assert_any_call_stripped(self, expected):
        calls = [strip_ansi(str(call.args[0])) for call in self.mock_print.call_args_list]
        assert expected in calls, f"Expected '{expected}' in print calls, got: {calls}"
    def assert_called_with_stripped(self, expected):
        call = self.mock_print.call_args
        actual = strip_ansi(str(call[0][0]))
        assert actual == expected, f"Expected '{expected}', got '{actual}'"

class DummyItem:
    def __init__(self, name, amt=0):
        self.name = name
        self.amt = amt

class DummyWeapon:
    def __init__(self, name, count=1, isequipped=False):
        self.name = name
        self.maintype = "Weapon"
        self.count = count
        self.isequipped = isequipped
        self.interactions = ["equip"]
    def equip(self, player):
        player.eq_weapon = self

class DummyArmor:
    def __init__(self, name, count=1):
        self.name = name
        self.maintype = "Armor"
        self.count = count
        self.interactions = ["equip"]
    def equip(self, player):
        pass

class DummyPlayer(player.Player):
    def __init__(self):
        super().__init__()
        self.inventory = [DummyWeapon("Sword", count=2), DummyArmor("Shield", count=1)]
        self.preferences = {"arrow": "Wooden Arrow"}
        self.eq_weapon = None

class TestBaseInterface(unittest.TestCase):
    def setUp(self):
        self.interface = interface.BaseInterface(title="Test Menu", choices=[{'label': 'Choice 1'}, {'label': 'Choice 2'}], exit_label="Quit", exit_message="Bye!")

    @patch('builtins.print')
    def test_display_title(self, mock_print):
        self.interface.display_title()
        PatchedPrint(mock_print).assert_called_with_stripped("\n=== Test Menu ===\n")

    @patch('builtins.print')
    def test_display_choices(self, mock_print):
        self.interface.display_choices()
        expected = ["0: Choice 1", "1: Choice 2", "x: Quit"]
        calls = [strip_ansi(str(call.args[0])) for call in mock_print.call_args_list]
        for e in expected:
            assert e in calls, f"Expected '{e}' in print calls, got: {calls}"

    @patch('builtins.print')
    def test_handle_exit(self, mock_print):
        self.interface.handle_exit()
        PatchedPrint(mock_print).assert_called_with_stripped("Bye!")

    @patch('builtins.input', side_effect=["x"])
    @patch('builtins.print')
    def test_run_exit(self, mock_print, mock_input):
        self.interface.run()
        PatchedPrint(mock_print).assert_any_call_stripped("Bye!")

    @patch('builtins.input', side_effect=["0", "x"])
    @patch('builtins.print')
    def test_run_valid_choice_then_exit(self, mock_print, mock_input):
        self.interface.run()
        PatchedPrint(mock_print).assert_any_call_stripped("You selected: Choice 1")
        PatchedPrint(mock_print).assert_any_call_stripped("Bye!")

    @patch('builtins.input', side_effect=["5", "x"])
    @patch('builtins.print')
    def test_run_invalid_choice(self, mock_print, mock_input):
        self.interface.run()
        PatchedPrint(mock_print).assert_any_call_stripped("Invalid selection. Please try again.")
        PatchedPrint(mock_print).assert_any_call_stripped("Bye!")

    @patch('builtins.print')
    def test_handle_choice(self, mock_print):
        self.interface.handle_choice(1)
        PatchedPrint(mock_print).assert_called_with_stripped("You selected: Choice 2")

    def test_empty_choices(self):
        iface = interface.BaseInterface(title="Empty", choices=[])
        with patch('builtins.print') as mock_print:
            iface.display_choices()
            PatchedPrint(mock_print).assert_called_with_stripped("x: Exit")

class TestGetGold(unittest.TestCase):
    def test_no_gold(self):
        inventory = [DummyItem('Silver', 10), DummyItem('Bronze', 5)]
        self.assertEqual(interface.get_gold(inventory), 0)

    def test_single_gold(self):
        inventory = [DummyItem('Gold', 15)]
        self.assertEqual(interface.get_gold(inventory), 15)

    def test_multiple_gold(self):
        inventory = [DummyItem('Gold', 10), DummyItem('Gold', 5)]
        self.assertEqual(interface.get_gold(inventory), 15)

    def test_gold_with_missing_amt(self):
        class NoAmt:
            def __init__(self):
                self.name = 'Gold'
        inventory = [NoAmt()]
        self.assertEqual(interface.get_gold(inventory), 0)

    def test_mixed_inventory(self):
        inventory = [DummyItem('Gold', 7), DummyItem('Silver', 3), DummyItem('Gold', 8)]
        self.assertEqual(interface.get_gold(inventory), 15)

class DummyMerchant:
    def __init__(self, name):
        self.name = name

class TestShopInterface(unittest.TestCase):
    def test_shop_interface_init(self):
        merchant = DummyMerchant('Bob')
        shop = interface.ShopInterface(merchant)
        self.assertEqual(shop.title, "Bob's Shop")
        self.assertEqual(shop.exit_label, "Leave Shop")
        self.assertEqual(len(shop.choices), 2)
        self.assertEqual(shop.choices[0]['label'], 'Buy')
        self.assertEqual(shop.choices[1]['label'], 'Sell')
        self.assertIs(shop.merchant, merchant)
        self.assertIsNone(shop.player)

    def test_shop_interface_custom_name(self):
        merchant = DummyMerchant('Alice')
        shop = interface.ShopInterface(merchant, shop_name="Alice's Magic Emporium")
        self.assertEqual(shop.title, "Alice's Magic Emporium")

class TestSubmenu(unittest.TestCase):
    @patch('builtins.input', side_effect=["0", "x", "x"])
    @patch('builtins.print')
    def test_submenu_loop_and_exit(self, mock_print, mock_input):
        submenu = interface.BaseInterface(title="Submenu", choices=[{'label': 'Subchoice'}], exit_label="Back", exit_message="Leaving submenu!")
        main_menu = interface.BaseInterface(title="Main Menu", choices=[{'label': 'Go to Submenu', 'submenu': submenu}], exit_label="Quit", exit_message="Bye!")
        main_menu.run()
        PatchedPrint(mock_print).assert_any_call_stripped("You selected: Go to Submenu")
        PatchedPrint(mock_print).assert_any_call_stripped("Leaving submenu!")
        PatchedPrint(mock_print).assert_any_call_stripped("Bye!")

class TestInventoryInterface(unittest.TestCase):
    @patch('builtins.input', side_effect=["w", "0", "x", "x", "x"])
    @patch('builtins.print')
    def test_weapon_category_selection_and_item_interaction(self, mock_print, mock_input):
        player = DummyPlayer()
        iface = interface.InventoryInterface(player)
        iface.run()
        PatchedPrint(mock_print).assert_any_call_stripped("0: Sword  (2)")

    @patch('builtins.input', side_effect=["a", "0", "x", "x", "x"])
    @patch('builtins.print')
    def test_armor_category_selection(self, mock_print, mock_input):
        player = DummyPlayer()
        iface = interface.InventoryInterface(player)
        iface.run()
        PatchedPrint(mock_print).assert_any_call_stripped("0: Shield ")

    @patch('builtins.input', side_effect=["w", "x", "x", "x"])
    @patch('builtins.print')
    def test_back_navigation_from_item_submenu(self, mock_print, mock_input):
        player = DummyPlayer()
        iface = interface.InventoryInterface(player)
        iface.run()
        PatchedPrint(mock_print).assert_any_call_stripped("Returning to category selection...")

class TestInventoryCategorySubmenu(unittest.TestCase):
    @patch('builtins.input', side_effect=["0", "x", "x"])
    @patch('builtins.print')
    def test_item_selection_and_interaction(self, mock_print, mock_input):
        player = DummyPlayer()
        items = [DummyWeapon("Sword", count=2)]
        submenu = interface.InventoryCategorySubmenu(items, player, "Weapon")
        submenu.run()
        PatchedPrint(mock_print).assert_any_call_stripped("0: Sword  (2)")

    @patch('builtins.input', side_effect=["x", "x"])
    @patch('builtins.print')
    def test_back_navigation(self, mock_print, mock_input):
        player = DummyPlayer()
        items = [DummyWeapon("Sword", count=2)]
        submenu = interface.InventoryCategorySubmenu(items, player, "Weapon")
        submenu.run()
        PatchedPrint(mock_print).assert_any_call_stripped("Returning to category selection...")

class TestPlayerPrintInventory(unittest.TestCase):
    @patch('builtins.input', side_effect=["w", "0", "x", "x", "x"])
    @patch('builtins.print')
    def test_print_inventory_integration(self, mock_print, mock_input):
        player = DummyPlayer()
        player.print_inventory()
        PatchedPrint(mock_print).assert_any_call_stripped("0: Sword  (2)")

if __name__ == "__main__":
    unittest.main()
