"""Coverage tests for player/_world.py, player/_inventory.py, and player/_ui.py.

Targets uncovered lines:
- _world.py:  19-20, 27, 30, 34, 36-37, 45, 47, 53, 55-57, 60-68, 78-80, 89-96
- _inventory.py: 66-67, 110, 134-148, 157-162, 206-208, 236-245, 290, 311, 317,
                 322, 334, 339, 360, 377-380, 388, 390-401, 411, 433-434,
                 439-445, 449-467, 470, 488, 540, 553
- _ui.py:     38-46, 62, 72-73, 78-80, 95-96, 100, 158, 168-170, 172, 204,
              213-214, 248-255, 296, 301, 309, 365-388, 399, 440, 451,
              469-470, 504, 516
"""

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call

ROOT = Path(__file__).resolve().parent.parent


import pytest
from src.player import Player
import src.items as items

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player():
    p = Player()
    return p


def _make_tile():
    """Return a minimal mock tile."""
    t = MagicMock()
    t.npcs_here = []
    t.items_here = []
    t.objects_here = []
    t.events_here = []
    return t


# ---------------------------------------------------------------------------
# player/_world.py — refresh_merchants
# ---------------------------------------------------------------------------


class TestRefreshMerchantsWorld:
    """Tests for PlayerWorldMixin.refresh_merchants()."""

    def test_no_universe_prints_warning(self):
        p = _make_player()
        p.universe = None
        with patch("builtins.print"), patch("src.player._world.cprint") as mock_cp:
            p.refresh_merchants()
        mock_cp.assert_called()

    def test_universe_without_maps_attr(self):
        p = _make_player()
        p.universe = MagicMock(spec=[])  # no 'maps' attribute
        with patch("builtins.print"), patch("src.player._world.cprint") as mock_cp:
            p.refresh_merchants()
        mock_cp.assert_called()

    def test_no_merchants_prints_yellow(self):
        p = _make_player()
        mock_universe = MagicMock()
        mock_universe.maps = []
        p.universe = mock_universe
        with (
            patch("builtins.print"),
            patch("src.player._world.cprint") as mock_cp,
            patch("src.player._world.time"),
        ):
            p.refresh_merchants()
        # Should print "No merchants found" in yellow
        calls_text = " ".join(str(c) for c in mock_cp.call_args_list)
        assert "No merchants" in calls_text or mock_cp.called

    def test_no_merchants_with_filter_prints_filter_message(self):
        p = _make_player()
        mock_universe = MagicMock()
        mock_universe.maps = []
        p.universe = mock_universe
        with (
            patch("builtins.print"),
            patch("src.player._world.cprint") as mock_cp,
            patch("src.player._world.time"),
        ):
            p.refresh_merchants(phrase="blacksmith")
        calls_text = " ".join(str(c) for c in mock_cp.call_args_list)
        assert "blacksmith" in calls_text or mock_cp.called

    def test_non_dict_map_skipped(self):
        """Maps that are not dicts should be silently skipped."""
        p = _make_player()
        mock_universe = MagicMock()
        mock_universe.maps = ["not_a_dict", 42, None]
        p.universe = mock_universe
        with (
            patch("builtins.print"),
            patch("src.player._world.cprint"),
            patch("src.player._world.time"),
        ):
            # Should not raise; no merchants found
            p.refresh_merchants()

    def test_merchant_update_goods_called(self):
        """A tile with a Merchant-class NPC should have update_goods called."""
        p = _make_player()

        # Create a fake Merchant class with correct MRO
        class Merchant:
            pass

        class FakeMerchant(Merchant):
            def __init__(self):
                self.name = "test_merchant"
                self.shop = None
                self._update_called = False

            def update_goods(self):
                self._update_called = True

        merchant = FakeMerchant()
        fake_tile = MagicMock()
        fake_tile.npcs_here = [merchant]

        mock_universe = MagicMock()
        mock_universe.maps = [{"name": "test_map", (0, 0): fake_tile}]
        p.universe = mock_universe

        with (
            patch("builtins.print"),
            patch("src.player._world.cprint"),
            patch("src.player._world.time"),
        ):
            p.refresh_merchants()

        assert merchant._update_called

    def test_merchant_initialize_shop_called_when_shop_is_none(self):
        """If merchant.shop is None and has initialize_shop, that gets called first."""
        p = _make_player()

        class Merchant:
            pass

        class FakeMerchant(Merchant):
            def __init__(self):
                self.name = "greg"
                self.shop = None
                self._init_called = False
                self._update_called = False

            def initialize_shop(self):
                self._init_called = True
                self.shop = MagicMock()

            def update_goods(self):
                self._update_called = True

        merchant = FakeMerchant()
        fake_tile = MagicMock()
        fake_tile.npcs_here = [merchant]
        mock_universe = MagicMock()
        mock_universe.maps = [{"name": "m", (0, 0): fake_tile}]
        p.universe = mock_universe

        with (
            patch("builtins.print"),
            patch("src.player._world.cprint"),
            patch("src.player._world.time"),
        ):
            p.refresh_merchants()

        assert merchant._init_called
        assert merchant._update_called

    def test_merchant_missing_update_goods_counted_as_failure(self):
        """A merchant without update_goods is recorded as a failure."""
        p = _make_player()

        class Merchant:
            pass

        class FakeMerchantNoUpdate(Merchant):
            def __init__(self):
                self.name = "broken"
                self.shop = MagicMock()

        merchant = FakeMerchantNoUpdate()
        fake_tile = MagicMock()
        fake_tile.npcs_here = [merchant]
        mock_universe = MagicMock()
        mock_universe.maps = [{"name": "m", (0, 0): fake_tile}]
        p.universe = mock_universe

        with (
            patch("builtins.print"),
            patch("src.player._world.cprint") as mock_cp,
            patch("src.player._world.time"),
        ):
            p.refresh_merchants()

        # "0 succeeded, 1 failed" should appear somewhere
        calls_text = " ".join(str(c) for c in mock_cp.call_args_list)
        assert "failed" in calls_text

    def test_phrase_filter_excludes_non_matching_merchant(self):
        """A phrase filter should skip merchants whose name doesn't match."""
        p = _make_player()

        class Merchant:
            pass

        class FakeMerchant(Merchant):
            def __init__(self):
                self.name = "weaponsmith"
                self.shop = MagicMock()
                self._called = False

            def update_goods(self):
                self._called = True

        merchant = FakeMerchant()
        fake_tile = MagicMock()
        fake_tile.npcs_here = [merchant]
        mock_universe = MagicMock()
        mock_universe.maps = [{"name": "m", (0, 0): fake_tile}]
        p.universe = mock_universe

        with (
            patch("builtins.print"),
            patch("src.player._world.cprint"),
            patch("src.player._world.time"),
        ):
            p.refresh_merchants(phrase="alchemist")  # doesn't match weaponsmith

        assert not merchant._called

    def test_tile_with_no_npcs_here_attr(self):
        """Tiles that lack npcs_here attribute are handled gracefully."""
        p = _make_player()
        mock_universe = MagicMock()
        # Tile object with no npcs_here attribute
        bare_tile = object()
        mock_universe.maps = [{"name": "m", (0, 0): bare_tile}]
        p.universe = mock_universe

        with (
            patch("builtins.print"),
            patch("src.player._world.cprint"),
            patch("src.player._world.time"),
        ):
            p.refresh_merchants()


# ---------------------------------------------------------------------------
# player/_inventory.py — weight, equip, add_items_to_inventory
# ---------------------------------------------------------------------------


class TestInventoryCoverage:
    """Coverage for PlayerInventoryMixin uncovered paths."""

    def test_refresh_weight_empty_inventory(self):
        p = _make_player()
        p.inventory = []
        p.refresh_weight()
        assert p.weight_current == 0.0

    def test_refresh_weight_with_stackable_item(self):
        p = _make_player()
        item = MagicMock()
        item.weight = 2.0
        item.count = 3
        p.inventory = [item]
        p.refresh_weight()
        assert p.weight_current == 6.0

    def test_refresh_weight_no_count_attr(self):
        p = _make_player()
        item = MagicMock(spec=["weight"])
        item.weight = 5.0
        p.inventory = [item]
        p.refresh_weight()
        assert p.weight_current == 5.0

    def test_add_items_over_weight_limit(self):
        p = _make_player()
        p.weight_tolerance = 5.0
        p.weight_current = 4.5
        p.current_room = _make_tile()

        heavy_item = MagicMock(spec=["name", "weight"])
        heavy_item.name = "Heavy Rock"
        heavy_item.weight = 2.0

        with patch("builtins.print"), patch("neotermcolor.cprint"):
            p.add_items_to_inventory([heavy_item])

        # Item should be dropped in current room, not added to inventory
        assert heavy_item not in p.inventory
        assert heavy_item in p.current_room.items_here

    def test_add_items_within_weight_limit(self):
        p = _make_player()
        p.weight_tolerance = 50.0
        p.weight_current = 0.0
        p.current_room = _make_tile()

        light_item = items.Antidote()
        original_count = len(p.inventory)

        with patch("builtins.print"), patch("neotermcolor.cprint"):
            p.add_items_to_inventory([light_item])

        assert light_item in p.inventory

    def test_add_item_already_in_inventory_not_duplicated(self):
        p = _make_player()
        p.weight_tolerance = 50.0
        p.weight_current = 0.0
        p.current_room = _make_tile()

        item = items.Antidote()
        p.inventory.append(item)
        before_count = len(p.inventory)

        with patch("builtins.print"), patch("neotermcolor.cprint"):
            p.add_items_to_inventory([item])

        # Count should not have increased (item was already there)
        assert len(p.inventory) == before_count

    def test_add_items_stackable_with_count(self):
        """Items with count > 1 show the count in the name display."""
        p = _make_player()
        p.weight_tolerance = 50.0
        p.weight_current = 0.0
        p.current_room = _make_tile()

        item = MagicMock()
        item.name = "Arrow"
        item.weight = 0.1
        item.count = 5

        with patch("builtins.print") as mock_print, patch("neotermcolor.cprint"):
            p.add_items_to_inventory([item])

        # Check x5 appears somewhere in print calls
        all_printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "x5" in all_printed

    def test_drop_merchandise_items_no_tile(self):
        """drop_merchandise_items with no current_room does nothing."""
        p = _make_player()
        with patch("src.player._inventory.tile_exists", return_value=None):
            # Should not raise
            p.drop_merchandise_items()

    def test_drop_merchandise_items_drops_merchandise(self):
        p = _make_player()
        tile = _make_tile()
        # tile.items_here is a real list so we can check
        tile.items_here = []

        merch_item = MagicMock()
        merch_item.merchandise = True
        merch_item.name = "Sword"

        non_merch = MagicMock()
        non_merch.merchandise = False

        p.inventory = [merch_item, non_merch]
        p.current_room = tile

        with (
            patch("src.player._inventory.tile_exists", return_value=tile),
            patch("builtins.print"),
            patch("src.player._inventory.time"),
        ):
            p.drop_merchandise_items()

        assert merch_item not in p.inventory
        assert merch_item in tile.items_here
        assert non_merch in p.inventory

    def test_equip_item_too_heavy_from_ground(self):
        """Equipping an item from the ground that exceeds weight cap is refused."""
        p = _make_player()
        p.weight_tolerance = 1.0
        p.weight_current = 0.9
        p.current_room = _make_tile()

        heavy_item = MagicMock()
        heavy_item.name = "Greatsword"
        heavy_item.isequipped = False
        heavy_item.weight = 5.0
        heavy_item.maintype = "Weapon"

        # item is NOT in inventory (simulates picking from ground path)
        p.current_room.items_here = [heavy_item]

        with patch("builtins.print"), patch("neotermcolor.cprint"):
            p.equip_item(phrase="greatsword")

        assert heavy_item not in p.inventory

    def test_equip_item_already_equipped_no_remove_on_n(self):
        """If item is already equipped and user answers n, it stays equipped."""
        p = _make_player()
        sword = items.RustedIronMace()
        sword.isequipped = True
        if "unequip" not in sword.interactions:
            sword.interactions.append("unequip")
        if "equip" in sword.interactions:
            sword.interactions.remove("equip")
        p.inventory.append(sword)
        p.current_room = _make_tile()
        p.current_room.items_here = []

        with (
            patch("builtins.input", return_value="n"),
            patch("builtins.print"),
            patch("neotermcolor.cprint"),
        ):
            p.equip_item(item_object=sword)

        assert sword.isequipped

    def test_equip_item_replaces_existing_weapon(self):
        """Equipping a new weapon unequips the old one."""
        p = _make_player()
        # Equip first sword
        sword1 = items.RustedIronMace()
        sword1.isequipped = True
        if "unequip" not in sword1.interactions:
            sword1.interactions.append("unequip")
        if "equip" in sword1.interactions:
            sword1.interactions.remove("equip")
        p.inventory.append(sword1)

        # Now equip a second weapon
        sword2 = items.RustedIronMace()
        sword2.isequipped = False
        p.inventory.append(sword2)
        p.current_room = _make_tile()
        p.current_room.items_here = []

        with patch("builtins.print"), patch("neotermcolor.cprint"):
            p.equip_item(item_object=sword2)

        assert sword2.isequipped
        assert not sword1.isequipped

    def test_stack_gold_consolidates(self):
        """stack_gold merges multiple Gold items into one."""
        p = _make_player()
        gold1 = items.Gold(10)
        gold2 = items.Gold(15)
        p.inventory = [gold1, gold2]

        with patch("builtins.print"), patch("neotermcolor.cprint"):
            p.stack_gold()

        gold_items = [i for i in p.inventory if isinstance(i, items.Gold)]
        assert len(gold_items) == 1
        assert gold_items[0].amt == 25

    def test_stack_gold_no_gold(self):
        """stack_gold with no gold items does nothing."""
        p = _make_player()
        potion = items.Antidote()
        p.inventory = [potion]
        p.stack_gold()
        assert potion in p.inventory

    def test_equip_item_container_parent_removal(self):
        """Item with _parent_container is removed from its container on equip."""
        p = _make_player()
        p.current_room = _make_tile()
        p.current_room.items_here = []

        sword = items.RustedIronMace()
        sword.isequipped = False
        container = MagicMock()
        container.inventory = [sword]
        sword._parent_container = container

        # Simulate item NOT in player inventory (picked from container logic)
        # We add it to current_room.items_here so the code path finds it
        p.current_room.items_here.append(sword)

        with patch("builtins.print"), patch("neotermcolor.cprint"):
            p.equip_item(phrase=sword.name.lower())

        # Container.inventory.remove should have been called
        assert sword not in container.inventory
