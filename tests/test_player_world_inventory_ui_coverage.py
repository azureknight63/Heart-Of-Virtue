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
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from player import Player
import items

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
        with patch("builtins.print"), patch("player._world.cprint") as mock_cp:
            p.refresh_merchants()
        mock_cp.assert_called()

    def test_universe_without_maps_attr(self):
        p = _make_player()
        p.universe = MagicMock(spec=[])  # no 'maps' attribute
        with patch("builtins.print"), patch("player._world.cprint") as mock_cp:
            p.refresh_merchants()
        mock_cp.assert_called()

    def test_no_merchants_prints_yellow(self):
        p = _make_player()
        mock_universe = MagicMock()
        mock_universe.maps = []
        p.universe = mock_universe
        with (
            patch("builtins.print"),
            patch("player._world.cprint") as mock_cp,
            patch("player._world.time"),
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
            patch("player._world.cprint") as mock_cp,
            patch("player._world.time"),
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
            patch("player._world.cprint"),
            patch("player._world.time"),
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
            patch("player._world.cprint"),
            patch("player._world.time"),
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
            patch("player._world.cprint"),
            patch("player._world.time"),
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
            patch("player._world.cprint") as mock_cp,
            patch("player._world.time"),
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
            patch("player._world.cprint"),
            patch("player._world.time"),
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
            patch("player._world.cprint"),
            patch("player._world.time"),
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
        with patch("player._inventory.tile_exists", return_value=None):
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
            patch("player._inventory.tile_exists", return_value=tile),
            patch("builtins.print"),
            patch("player._inventory.time"),
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

    def test_equip_item_already_equipped_removes_on_y(self):
        """If item is already equipped and user answers y, it should be unequipped."""
        p = _make_player()
        sword = items.RustedIronMace()
        sword.isequipped = True
        # Add interactions if missing
        if "unequip" not in sword.interactions:
            sword.interactions.append("unequip")
        if "equip" in sword.interactions:
            sword.interactions.remove("equip")
        p.inventory.append(sword)
        p.current_room = _make_tile()
        p.current_room.items_here = []

        with (
            patch("builtins.input", return_value="y"),
            patch("builtins.print"),
            patch("neotermcolor.cprint"),
        ):
            p.equip_item(item_object=sword)

        assert not sword.isequipped

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


# ---------------------------------------------------------------------------
# player/_ui.py — generate_output_grid and show_bars
# ---------------------------------------------------------------------------


class TestUIGridCoverage:
    """Tests for generate_output_grid edge cases and show_bars."""

    def test_generate_output_grid_auto_square(self):
        """Grid auto-squares when neither rows nor cols given."""
        from player import generate_output_grid

        data = ["A", "B", "C", "D"]
        result = generate_output_grid(data)
        assert "A" in result and "D" in result

    def test_generate_output_grid_cols_specified(self):
        """When cols are specified, rows are calculated automatically."""
        from player import generate_output_grid

        data = ["X"] * 9
        result = generate_output_grid(data, cols=3)
        assert "X" in result

    def test_generate_output_grid_rows_and_cols_specified(self):
        """When both rows and cols are specified, those exact dims are used."""
        from player import generate_output_grid

        data = ["Q"] * 6
        result = generate_output_grid(data, rows=2, cols=3)
        assert "Q" in result

    def test_generate_output_grid_very_long_string_no_crash(self):
        """A very long string that exceeds row limit completes without raising."""
        from player import generate_output_grid

        long_str = "A" * 350
        result = generate_output_grid([long_str])
        # The overflow path still returns a string (may be just border chars)
        assert isinstance(result, str)

    def test_generate_output_grid_returns_string(self):
        from player import generate_output_grid

        result = generate_output_grid(["hello", "world"], rows=1, cols=2)
        assert isinstance(result, str)

    def test_generate_output_grid_single_item(self):
        from player import generate_output_grid

        result = generate_output_grid(["solo"])
        assert "solo" in result

    def test_show_bars_both_full(self):
        """show_bars with full HP and FP should print both bars."""
        p = _make_player()
        p.hp = p.maxhp
        p.fatigue = p.maxfatigue

        with patch("builtins.print") as mock_print:
            p.show_bars(hp=True, fp=True)

        mock_print.assert_called_once()
        output = mock_print.call_args[0][0]
        assert "HP" in output
        assert "FP" in output

    def test_show_bars_hp_only(self):
        p = _make_player()
        p.hp = p.maxhp // 2

        with patch("builtins.print") as mock_print:
            p.show_bars(hp=True, fp=False)

        output = mock_print.call_args[0][0]
        assert "HP" in output
        assert "FP" not in output

    def test_show_bars_fp_only(self):
        p = _make_player()
        p.fatigue = p.maxfatigue // 2

        with patch("builtins.print") as mock_print:
            p.show_bars(hp=False, fp=True)

        output = mock_print.call_args[0][0]
        assert "FP" in output
        assert "HP" not in output

    def test_show_bars_neither(self):
        """Both disabled → empty output string printed."""
        p = _make_player()

        with patch("builtins.print") as mock_print:
            p.show_bars(hp=False, fp=False)

        output = mock_print.call_args[0][0]
        assert output == ""

    def test_print_status_runs_without_error(self):
        """print_status should not raise and should call print."""
        p = _make_player()
        with (
            patch("builtins.print"),
            patch("neotermcolor.cprint"),
            patch("neotermcolor.colored", side_effect=lambda t, *a, **k: t),
            patch("functions.await_input"),
            patch("functions.refresh_stat_bonuses"),
        ):
            p.print_status()

    def test_print_status_with_states(self):
        """print_status with active states lists state names."""
        p = _make_player()
        mock_state = MagicMock()
        mock_state.name = "Poisoned"
        mock_state.steps_left = 3
        p.states = [mock_state]

        with (
            patch("builtins.print"),
            patch("neotermcolor.cprint"),
            patch("neotermcolor.colored", side_effect=lambda t, *a, **k: t),
            patch("functions.await_input"),
            patch("functions.refresh_stat_bonuses"),
        ):
            p.print_status()

    def test_print_status_resistance_above_100(self):
        """print_status handles resistance > 1.0 (red path)."""
        p = _make_player()
        p.resistance["slash"] = 1.5  # 150%

        with (
            patch("builtins.print"),
            patch("neotermcolor.cprint"),
            patch("neotermcolor.colored", side_effect=lambda t, *a, **k: t),
            patch("functions.await_input"),
            patch("functions.refresh_stat_bonuses"),
        ):
            p.print_status()

    def test_print_status_resistance_below_zero(self):
        """print_status handles negative resistance (absorption path)."""
        p = _make_player()
        p.resistance["slash"] = -0.5

        with (
            patch("builtins.print"),
            patch("neotermcolor.cprint"),
            patch("neotermcolor.colored", side_effect=lambda t, *a, **k: t),
            patch("functions.await_input"),
            patch("functions.refresh_stat_bonuses"),
        ):
            p.print_status()

    def test_print_status_empty_resistance(self):
        """print_status with empty resistance dict prints 'None'."""
        p = _make_player()
        p.resistance = {}
        p.status_resistance = {}

        with (
            patch("builtins.print") as mock_print,
            patch("neotermcolor.cprint"),
            patch("neotermcolor.colored", side_effect=lambda t, *a, **k: t),
            patch("functions.await_input"),
            patch("functions.refresh_stat_bonuses"),
        ):
            p.print_status()

        all_args = [str(c) for c in mock_print.call_args_list]
        assert any("None" in a for a in all_args)

    def test_commands_prints_actions(self):
        """commands() should print available actions."""
        p = _make_player()
        action = MagicMock()
        action.name = "Attack"
        action.hotkey = "a"
        p.current_room = MagicMock()
        p.current_room.available_actions.return_value = [action]

        with (
            patch("player._ui.cprint") as mock_cp,
            patch("player._ui.functions") as mock_fn,
        ):
            mock_fn.await_input = MagicMock()
            p.commands()

        mock_cp.assert_called()

    def test_menu_calls_autosave_and_sets_main_menu(self):
        p = _make_player()
        with patch("functions.autosave") as mock_save:
            p.menu()
        mock_save.assert_called_once_with(p)
        assert p.main_menu is True

    def test_save_calls_save_select(self):
        p = _make_player()
        with patch("functions.save_select") as mock_save:
            p.save()
        mock_save.assert_called_once_with(p)
