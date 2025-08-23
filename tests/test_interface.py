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

class DummyContainer:
    def __init__(self, nickname="chest", inventory=None):
        self.nickname = nickname
        self.inventory = inventory if inventory is not None else []
        self.events = []
        self.description = ""

    def refresh_description(self):
        if self.inventory:
            self.description = f"A {self.nickname} with items inside."
        else:
            self.description = f"An empty {self.nickname}."

    def process_events(self):
        # Simulate event processing
        pass

class DummyContainerItem:
    def __init__(self, name, description="A test item"):
        self.name = name
        self.description = description

class TestContainerLootInterface(unittest.TestCase):
    def setUp(self):
        self.player = DummyPlayer()
        self.player.inventory = []  # Start with empty inventory

        # Create test items
        self.item1 = DummyContainerItem("Sword", "A sharp blade")
        self.item2 = DummyContainerItem("Shield", "A sturdy defense")
        self.item3 = DummyContainerItem("Potion", "A healing draught")

        # Create container with items
        self.container = DummyContainer("chest", [self.item1, self.item2, self.item3])

    def test_init_with_items(self):
        """Test that ContainerLootInterface initializes correctly with items"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)

        # Should have 3 item choices + 1 "take all" choice
        self.assertEqual(len(loot_interface.choices), 4)
        self.assertEqual(loot_interface.title, "Looting chest")
        self.assertEqual(loot_interface.exit_label, "Cancel")

        # Check item choices
        self.assertEqual(loot_interface.choices[0]['label'], "Sword - A sharp blade")
        self.assertEqual(loot_interface.choices[1]['label'], "Shield - A sturdy defense")
        self.assertEqual(loot_interface.choices[2]['label'], "Potion - A healing draught")
        self.assertEqual(loot_interface.choices[3]['label'], "Take all items")

    def test_init_empty_container(self):
        """Test that ContainerLootInterface handles empty containers"""
        empty_container = DummyContainer("empty_chest", [])
        loot_interface = interface.ContainerLootInterface(empty_container, self.player)

        # Should have no choices for empty container
        self.assertEqual(len(loot_interface.choices), 0)

    @patch('builtins.print')
    def test_display_title(self, mock_print):
        """Test that display_title shows correct information"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)
        loot_interface.display_title()

        calls = [strip_ansi(str(call.args[0])) for call in mock_print.call_args_list]
        self.assertIn("\n=== Looting chest ===\n", calls)
        self.assertIn("Jean rifles through the contents of the chest.", calls)
        self.assertIn("Choose which items to take:\n", calls)  # Fixed: added \n

    @patch('builtins.print')
    def test_handle_choice_individual_item(self, mock_print):
        """Test taking individual items"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)

        # Take the first item (index 0)
        loot_interface.handle_choice(0)

        # Check that item was transferred
        self.assertEqual(len(self.player.inventory), 1)
        self.assertEqual(self.player.inventory[0], self.item1)
        self.assertEqual(len(self.container.inventory), 2)

        # Check print output
        PatchedPrint(mock_print).assert_any_call_stripped("Jean takes Sword.")

    @patch('builtins.print')
    def test_handle_choice_take_all(self, mock_print):
        """Test taking all items at once"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)

        # Take all items (should be the last choice)
        loot_interface.handle_choice(3)  # "Take all items" choice

        # Check that all items were transferred
        self.assertEqual(len(self.player.inventory), 3)
        self.assertEqual(len(self.container.inventory), 0)

        # Check print output
        calls = [strip_ansi(str(call.args[0])) for call in mock_print.call_args_list]
        self.assertIn("Jean takes Sword.", calls)
        self.assertIn("Jean takes Shield.", calls)
        self.assertIn("Jean takes Potion.", calls)
        self.assertIn("Jean has taken everything from the chest.", calls)

    def test_rebuild_choices_after_taking_item(self):
        """Test that choices are rebuilt correctly after taking an item"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)

        # Initially should have 4 choices (3 items + take all)
        self.assertEqual(len(loot_interface.choices), 4)

        # Take first item
        loot_interface.handle_choice(0)

        # Should now have 3 choices (2 items + take all)
        self.assertEqual(len(loot_interface.choices), 3)
        self.assertEqual(loot_interface.choices[0]['label'], "Shield - A sturdy defense")
        self.assertEqual(loot_interface.choices[1]['label'], "Potion - A healing draught")
        self.assertEqual(loot_interface.choices[2]['label'], "Take all items")

    def test_rebuild_choices_empty_after_take_all(self):
        """Test that choices are cleared after taking all items"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)

        # Take all items
        loot_interface.handle_choice(3)

        # Should have no choices left
        self.assertEqual(len(loot_interface.choices), 0)

    @patch('builtins.input', side_effect=["0", "x"])
    @patch('builtins.print')
    def test_run_take_one_item_then_exit(self, mock_print, mock_input):
        """Test full run workflow: take one item then exit"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)
        loot_interface.run()

        # Check that one item was taken
        self.assertEqual(len(self.player.inventory), 1)
        self.assertEqual(self.player.inventory[0], self.item1)

        # Check exit message
        PatchedPrint(mock_print).assert_any_call_stripped("Jean closes the container without taking anything.")

    @patch('builtins.input', side_effect=["3"])  # Take all items
    @patch('builtins.print')
    def test_run_take_all_items(self, mock_print, mock_input):
        """Test full run workflow: take all items (auto-exits when empty)"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)
        loot_interface.run()

        # Check that all items were taken
        self.assertEqual(len(self.player.inventory), 3)
        self.assertEqual(len(self.container.inventory), 0)

        # Check final message
        PatchedPrint(mock_print).assert_any_call_stripped("The chest is now empty.")

    @patch('builtins.print')
    def test_run_empty_container(self, mock_print):
        """Test running interface with empty container"""
        empty_container = DummyContainer("empty_box", [])
        loot_interface = interface.ContainerLootInterface(empty_container, self.player)
        loot_interface.run()

        # Should show empty message and not enter main loop
        PatchedPrint(mock_print).assert_any_call_stripped("It's empty. Very sorry.")

    @patch('builtins.input', side_effect=["invalid", "5", "0", "x"])
    @patch('builtins.print')
    def test_run_invalid_input_handling(self, mock_print, mock_input):
        """Test that invalid inputs are handled properly"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)
        loot_interface.run()

        # Should show invalid selection message
        calls = [strip_ansi(str(call.args[0])) for call in mock_print.call_args_list]
        invalid_messages = [call for call in calls if "Invalid selection" in call]
        self.assertGreaterEqual(len(invalid_messages), 2)  # Should appear twice

    def test_take_all_empty_container_handling(self):
        """Test _take_all_items when container is already empty"""
        empty_container = DummyContainer("empty_chest", [])
        loot_interface = interface.ContainerLootInterface(empty_container, self.player)

        with patch('builtins.print') as mock_print:
            loot_interface._take_all_items()
            PatchedPrint(mock_print).assert_any_call_stripped("The container is already empty.")

    def test_handle_choice_invalid_index(self):
        """Test handling choice with invalid item index"""
        loot_interface = interface.ContainerLootInterface(self.container, self.player)

        # Manually set an invalid index in choices
        loot_interface.choices[0]['index'] = 999

        # Should not crash when trying to access invalid index
        with patch('builtins.print'):
            loot_interface.handle_choice(0)

        # Item should not be transferred due to invalid index
        self.assertEqual(len(self.player.inventory), 0)
        self.assertEqual(len(self.container.inventory), 3)

    @patch('builtins.input', side_effect=["0", "1", "0"])  # Take items until empty
    @patch('builtins.print')
    def test_run_until_empty(self, mock_print, mock_input):
        """Test running until container is completely empty"""
        # Start with only 2 items for simpler test
        small_container = DummyContainer("small_chest", [self.item1, self.item2])
        loot_interface = interface.ContainerLootInterface(small_container, self.player)
        loot_interface.run()

        # Should take both items and exit automatically when empty
        self.assertEqual(len(self.player.inventory), 2)
        self.assertEqual(len(small_container.inventory), 0)

        # Should show empty message
        PatchedPrint(mock_print).assert_any_call_stripped("The small_chest is now empty.")

if __name__ == "__main__":
    unittest.main()
