"""Tests for the `interface` compatibility shim.

The terminal menu interface classes have been removed (the game is web-only).
`interface` now only re-exports the shared inventory/gold helpers, so this suite
covers the surviving public surface: get_gold.
"""

import unittest

import interface  # noqa


class DummyItem:
    def __init__(self, name, amt=0):
        self.name = name
        self.amt = amt


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


if __name__ == "__main__":
    unittest.main()
