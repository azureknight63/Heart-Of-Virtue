import sys, os
import unittest
from unittest.mock import patch

# Ensure src is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from functions import enumerate_for_interactions  # noqa

class DummyPlayer:
    name = "Jean"

class DummyItem:
    def __init__(self, name):
        self.name = name
        self.interactions = ["drop"]
        self.hidden = False
        self.announce = ''
        self.idle_message = ''
        self.description = ''
    def drop(self, player):
        # No-op for testing
        pass

class DummyGold(DummyItem):
    def __init__(self, flag_container):
        super().__init__('Gold')
        self._flag_container = flag_container
    def drop(self, player):
        self._flag_container['called'] = True

class TestDropGoldVisibility(unittest.TestCase):
    def test_gold_hidden_in_single_token_drop_menu(self):
        # Inventory with multiple items including Gold
        player = DummyPlayer()
        items = [DummyItem('Tattered Cloth'), DummyItem('Cloth Hood'), DummyItem('Wedding Band'), DummyItem('Gold')]
        # Force ambiguous selection path by patching input to cancel
        with patch('builtins.input', return_value='x'), patch('builtins.print') as mock_print:
            enumerate_for_interactions(items, player, ['drop'], 'drop')
            printed = '\n'.join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
            # Ensure Gold not shown in the menu
            self.assertNotIn('Gold', printed, "Gold should be excluded from single-token drop menu")

    def test_explicit_drop_gold_disallowed(self):
        player = DummyPlayer()
        flag = {'called': False}
        gold = DummyGold(flag)
        other = DummyItem('Cloth Hood')
        # Explicit target 'gold' should still not allow dropping gold (no candidates -> False)
        result = enumerate_for_interactions([gold, other], player, ['drop', 'gold'], 'drop gold')
        self.assertFalse(result, "Explicit 'drop gold' should not allow dropping Gold")
        self.assertFalse(flag['called'], "Gold drop method should not be executed")

if __name__ == '__main__':
    unittest.main()
