"""tests/test_inventory_utils_coverage.py

Coverage tests for src/inventory_utils.py targeting the assigned missing-line
ranges: 51-85 (transfer_gold), 112-113, 120, 143, 155-164, 168, 172-176,
186-187, 201-205, 213-216, 221-222, 229-230, 236-237, 241-242 (transfer_item
and its nested _set_merch_flag helper).

Lines 213-216 (`if getattr(item, "count", 0) <= 0: ... except ValueError`) are
defensive dead code under the split-stack invariant enforced a few lines above
it (qty is always strictly less than available in that branch, so item.count
can never reach <= 0 there) and are intentionally left uncovered.
"""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inventory_utils import get_gold, transfer_gold, transfer_item  # noqa: E402
from items import Gold, Restorative  # noqa: E402


# ---------------------------------------------------------------------------
# get_gold
# ---------------------------------------------------------------------------


class TestGetGold:
    def test_sums_gold_items_and_ignores_others(self):
        gold1 = Gold(amt=10)
        gold2 = Gold(amt=5)
        other = Restorative(count=1)
        total = get_gold([gold1, gold2, other])
        assert total == gold1.amt + gold2.amt

    def test_empty_inventory_returns_zero(self):
        assert get_gold([]) == 0

    def test_item_without_amt_defaults_to_zero(self):
        gold = MagicMock()
        gold.name = "Gold"
        del gold.amt
        assert get_gold([gold]) == 0


# ---------------------------------------------------------------------------
# transfer_gold
# ---------------------------------------------------------------------------


class TestTransferGold:
    def test_creates_gold_items_when_missing(self):
        from_inv = []
        to_inv = []
        transfer_gold(from_inv, to_inv, 50)

        from_gold = [i for i in from_inv if isinstance(i, Gold)][0]
        to_gold = [i for i in to_inv if isinstance(i, Gold)][0]
        assert from_gold.amt == 0
        assert to_gold.amt == 50

    def test_moves_amount_between_existing_gold_items(self):
        from_gold = Gold(amt=100)
        to_gold = Gold(amt=10)
        from_inv = [from_gold]
        to_inv = [to_gold]

        transfer_gold(from_inv, to_inv, 30)

        assert from_gold.amt == 70
        assert to_gold.amt == 40

    def test_clamps_negative_from_amount_to_zero(self):
        from_gold = Gold(amt=5)
        to_gold = Gold(amt=0)
        from_inv = [from_gold]
        to_inv = [to_gold]

        transfer_gold(from_inv, to_inv, 20)

        assert from_gold.amt == 0
        assert to_gold.amt == 20

    def test_negative_amount_clamps_recipient_to_zero(self):
        """Covers line 78: a negative transfer can drive the recipient's
        amount below zero, which must be clamped back to 0."""
        from_gold = Gold(amt=5)
        to_gold = Gold(amt=10)
        from_inv = [from_gold]
        to_inv = [to_gold]

        transfer_gold(from_inv, to_inv, -50)

        assert from_gold.amt == 55
        assert to_gold.amt == 0

    def test_syncs_count_and_calls_stack_grammar(self):
        from_gold = Gold(amt=10)
        to_gold = Gold(amt=0)
        from_inv = [from_gold]
        to_inv = [to_gold]

        transfer_gold(from_inv, to_inv, 4)

        assert from_gold.count == from_gold.amt
        assert to_gold.count == to_gold.amt
        # description is rewritten by stack_grammar() using the new amount
        assert str(from_gold.amt) in from_gold.description
        assert str(to_gold.amt) in to_gold.description


# ---------------------------------------------------------------------------
# transfer_item — guard clauses and edge branches
# ---------------------------------------------------------------------------


class _NoInventory:
    pass


class _PlainInventoryHolder:
    def __init__(self, inventory=None, name=None):
        self.inventory = inventory if inventory is not None else []
        if name is not None:
            self.name = name


class _RemoveRaisingList(list):
    """A list whose `remove` always raises ValueError, simulating the item
    having been concurrently removed from the inventory by other code."""

    def remove(self, item):
        raise ValueError("simulated concurrent removal")


class _BlockedAttrItem:
    """An item with one attribute that cannot be shallow-copied *or* reset via
    setattr — used to exercise the innermost defensive except block."""

    def __init__(self, count=1):
        self.count = count
        # Bypass the property setter below to seed an unpicklable attribute.
        self.__dict__["locked"] = threading.Lock()

    @property
    def locked(self):
        return self.__dict__.get("locked")

    @locked.setter
    def locked(self, value):
        raise RuntimeError("cannot set locked directly")

    def stack_grammar(self):
        pass


class TestTransferItemGuards:
    def test_missing_inventory_attr_logs_and_returns(self):
        source = _NoInventory()
        target = _PlainInventoryHolder()
        item = Restorative(count=1)
        # Should not raise despite source lacking .inventory
        transfer_item(source, target, item, qty=1)

    def test_qty_less_than_one_is_clamped_to_one(self):
        source = _PlainInventoryHolder(name="Jean")
        item = Restorative(count=1)
        source.inventory = [item]
        target = _PlainInventoryHolder()

        transfer_item(source, target, item, qty=0)

        assert item in target.inventory
        assert item not in source.inventory

    def test_item_not_in_source_inventory_logs_and_returns(self):
        source = _PlainInventoryHolder(name="Jean")
        target = _PlainInventoryHolder()
        item = Restorative(count=1)
        # item never added to source.inventory
        transfer_item(source, target, item, qty=1)
        assert item not in target.inventory

    def test_merch_flag_skipped_when_obj_has_no_merchandise_attr(self):
        source = _PlainInventoryHolder(name="Jean")
        target = _PlainInventoryHolder()
        item = MagicMock(spec=["name"])
        item.name = "Weird Object"
        source.inventory = [item]

        # Should not raise even though `item` has no `merchandise` attribute
        transfer_item(source, target, item, qty=1)
        assert item in target.inventory

    def test_player_target_falls_back_to_current_room_map_for_shop_check(self):
        """Covers line 143: item_target has no .map but has current_room.map."""
        source = _PlainInventoryHolder()
        source.merchant = "Jambo"  # is_merchant_container(source) truthy is avoided
        del source.merchant
        target = _PlainInventoryHolder(name="Jean")
        target.map = None
        target.current_room = MagicMock()
        target.current_room.map = {"name": "milos-shop"}
        item = Restorative(count=1, merchandise=False)
        source.inventory = [item]

        transfer_item(source, target, item, qty=1)

        assert item.merchandise is True

    def test_player_source_falls_back_to_current_room_map_for_shop_check(self):
        """Covers lines 155-164: item_source (player) has no .map but has
        current_room.map indicating a shop — selling into a plain container."""
        source = _PlainInventoryHolder(name="Jean")
        source.map = None
        source.current_room = MagicMock()
        source.current_room.map = {"name": "milos-shop"}
        item = Restorative(count=1, merchandise=False)
        source.inventory = [item]
        target = _PlainInventoryHolder()  # plain container, not a merchant

        transfer_item(source, target, item, qty=1)

        assert item.merchandise is True

    def test_player_source_outside_shop_leaves_merchandise_false(self):
        source = _PlainInventoryHolder(name="Jean")
        source.map = {"name": "grondia-wilderness"}
        item = Restorative(count=1, merchandise=False)
        source.inventory = [item]
        target = _PlainInventoryHolder()

        transfer_item(source, target, item, qty=1)

        assert item.merchandise is False

    def test_shallow_copy_failure_falls_back_to_direct_assignment(self):
        """Covers lines 200-205: an attribute that can't be shallow-copied AND
        can't be set directly is silently skipped rather than raising."""
        source = _PlainInventoryHolder(name="Jean")
        item = _BlockedAttrItem(count=5)
        source.inventory = [item]
        target = _PlainInventoryHolder()

        # qty (2) < available (5) -> split-stack branch, which builds a new
        # instance and copies every attribute from item.__dict__.
        transfer_item(source, target, item, qty=2)

        assert item.count == 3
        new_items = [i for i in target.inventory if isinstance(i, _BlockedAttrItem)]
        assert len(new_items) == 1
        assert new_items[0].count == 2

    def test_full_stack_remove_valueerror_is_swallowed(self):
        """Covers lines 186-187: item is confirmed present via `in`, but the
        subsequent `.remove()` call raises — the item should still land in
        the target inventory rather than the transfer crashing."""
        source = _PlainInventoryHolder(name="Jean")
        item = Restorative(count=5)
        source.inventory = _RemoveRaisingList([item])
        target = _PlainInventoryHolder()

        transfer_item(source, target, item, qty=5)  # qty >= available -> full move

        assert item in target.inventory

    def test_non_stackable_remove_valueerror_is_swallowed(self):
        """Covers lines 221-222: same defensive handling on the non-stackable
        (single object move) path."""
        source = _PlainInventoryHolder(name="Jean")
        item = _BlockedAttrItem(count=1)  # count==1 -> non-stackable branch
        source.inventory = _RemoveRaisingList([item])
        target = _PlainInventoryHolder()

        transfer_item(source, target, item, qty=1)

        assert item in target.inventory

    def test_stack_inv_items_exception_is_swallowed(self):
        """Covers lines 229-230: a failure inside stack_inv_items must not
        propagate out of transfer_item."""
        source = _PlainInventoryHolder(name="Jean")
        item = Restorative(count=1)
        source.inventory = [item]
        target = _PlainInventoryHolder()

        with patch(
            "inventory_utils.stack_inv_items", side_effect=RuntimeError("boom")
        ):
            transfer_item(source, target, item, qty=1)

        assert item in target.inventory

    def test_refresh_weight_exceptions_are_swallowed_on_both_sides(self):
        source = _PlainInventoryHolder(name="Jean")
        source.refresh_weight = MagicMock(side_effect=RuntimeError("source boom"))
        item = Restorative(count=1)
        source.inventory = [item]
        target = _PlainInventoryHolder()
        target.refresh_weight = MagicMock(side_effect=RuntimeError("target boom"))

        transfer_item(source, target, item, qty=1)

        assert item in target.inventory
        source.refresh_weight.assert_called_once()
        target.refresh_weight.assert_called_once()
