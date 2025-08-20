import unittest
from unittest.mock import patch, call
from src.interface import BaseInterface, get_gold, ShopInterface

class DummyItem:
    def __init__(self, name, amt=0):
        self.name = name
        self.amt = amt

class TestBaseInterface(unittest.TestCase):
    def setUp(self):
        self.interface = BaseInterface(title="Test Menu", choices=[{'label': 'Choice 1'}, {'label': 'Choice 2'}], exit_label="Quit", exit_message="Bye!")

    @patch('builtins.print')
    def test_display_title(self, mock_print):
        self.interface.display_title()
        mock_print.assert_called_with("\n=== Test Menu ===\n")

    @patch('builtins.print')
    def test_display_choices(self, mock_print):
        self.interface.display_choices()
        expected_calls = [call("0: Choice 1"), call("1: Choice 2"), call("x: Quit")]
        mock_print.assert_has_calls(expected_calls, any_order=False)

    @patch('builtins.print')
    def test_handle_exit(self, mock_print):
        self.interface.handle_exit()
        mock_print.assert_called_with("Bye!")

    @patch('builtins.input', side_effect=["x"])
    @patch('builtins.print')
    def test_run_exit(self, mock_print, mock_input):
        self.interface.run()
        mock_print.assert_any_call("Bye!")

    @patch('builtins.input', side_effect=["0", "x"])
    @patch('builtins.print')
    def test_run_valid_choice_then_exit(self, mock_print, mock_input):
        self.interface.run()
        mock_print.assert_any_call("You selected: Choice 1")
        mock_print.assert_any_call("Bye!")

    @patch('builtins.input', side_effect=["5", "x"])
    @patch('builtins.print')
    def test_run_invalid_choice(self, mock_print, mock_input):
        self.interface.run()
        mock_print.assert_any_call("Invalid selection. Please try again.")
        mock_print.assert_any_call("Bye!")

    @patch('builtins.print')
    def test_handle_choice(self, mock_print):
        self.interface.handle_choice(1)
        mock_print.assert_called_with("You selected: Choice 2")

    def test_empty_choices(self):
        interface = BaseInterface(title="Empty", choices=[])
        with patch('builtins.print') as mock_print:
            interface.display_choices()
            mock_print.assert_called_with("x: Exit")

class TestGetGold(unittest.TestCase):
    def test_no_gold(self):
        inventory = [DummyItem('Silver', 10), DummyItem('Bronze', 5)]
        self.assertEqual(get_gold(inventory), 0)

    def test_single_gold(self):
        inventory = [DummyItem('Gold', 15)]
        self.assertEqual(get_gold(inventory), 15)

    def test_multiple_gold(self):
        inventory = [DummyItem('Gold', 10), DummyItem('Gold', 5)]
        self.assertEqual(get_gold(inventory), 15)

    def test_gold_with_missing_amt(self):
        class NoAmt:
            def __init__(self):
                self.name = 'Gold'
        inventory = [NoAmt()]
        self.assertEqual(get_gold(inventory), 0)

    def test_mixed_inventory(self):
        inventory = [DummyItem('Gold', 7), DummyItem('Silver', 3), DummyItem('Gold', 8)]
        self.assertEqual(get_gold(inventory), 15)

class DummyMerchant:
    def __init__(self, name):
        self.name = name

class TestShopInterface(unittest.TestCase):
    def test_shop_interface_init(self):
        merchant = DummyMerchant('Bob')
        shop = ShopInterface(merchant)
        self.assertEqual(shop.title, "Bob's Shop")
        self.assertEqual(shop.exit_label, "Leave Shop")
        self.assertEqual(len(shop.choices), 2)
        self.assertEqual(shop.choices[0]['label'], 'Buy')
        self.assertEqual(shop.choices[1]['label'], 'Sell')
        self.assertIs(shop.merchant, merchant)
        self.assertIsNone(shop.player)

    def test_shop_interface_custom_name(self):
        merchant = DummyMerchant('Alice')
        shop = ShopInterface(merchant, shop_name="Alice's Magic Emporium")
        self.assertEqual(shop.title, "Alice's Magic Emporium")

class TestSubmenu(unittest.TestCase):
    @patch('builtins.input', side_effect=["0", "x", "x"])
    @patch('builtins.print')
    def test_submenu_loop_and_exit(self, mock_print, mock_input):
        submenu = BaseInterface(title="Submenu", choices=[{'label': 'Subchoice'}], exit_label="Back", exit_message="Leaving submenu!")
        main_menu = BaseInterface(title="Main Menu", choices=[{'label': 'Go to Submenu', 'submenu': submenu}], exit_label="Quit", exit_message="Bye!")
        main_menu.run()
        # Check that submenu was entered and exited, then main menu exited
        mock_print.assert_any_call("You selected: Go to Submenu")
        mock_print.assert_any_call("Leaving submenu!")
        mock_print.assert_any_call("Bye!")

if __name__ == "__main__":
    unittest.main()
