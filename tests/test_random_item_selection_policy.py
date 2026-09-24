"""Issue #647: every random ``Item``-class enumerator honours one policy.

#632 taught ``MerchantShopMixin._fill_remaining_stock`` to skip classes
flagged ``stockable = False`` (story items, quest keys, lore documents). Two
other enumerators reflected over ``src.items`` with no such check:

- ``ShopCondition.random_item_base_class`` -- the "all X 25% off today" pick
  -- could choose ``JeanWeddingBand`` or a lore document outright.
- ``loot_tables.Loot.random_equipment`` was safe only by accident: it keys on
  ``obj.level``, and story items happen to have none. Give one a real level
  and it becomes loot.

The excluded population is derived from the live ``Item`` registry, never
hand-listed, and asserted non-empty so the tests cannot pass vacuously.
"""

import inspect

import pytest

import src.items as items_module
from src.items import Item
from src.loot_tables import Loot
from src.shop_conditions import ShopCondition
from tests.test_shop_stock_excludes_story_items import _MockMerchant, _PoolRecorder


def _item_classes():
    return [
        obj
        for _name, obj in inspect.getmembers(items_module, inspect.isclass)
        if issubclass(obj, Item) and obj is not Item
    ]


@pytest.fixture(scope="module")
def excluded():
    """Every Item subclass the class-level policy flag keeps out of random rolls."""
    found = {cls for cls in _item_classes() if not cls.stockable}
    assert found, "no Item subclass is flagged stockable=False -- population derivation is broken"
    return found


def test_random_item_base_class_never_offers_an_excluded_class(excluded, monkeypatch):
    """The whole pool handed to ``random.choice`` is inspected, not one draw."""
    pools = []

    def record(seq):
        pools.append(list(seq))
        return seq[0]

    monkeypatch.setattr("src.shop_conditions.random.choice", record)
    ShopCondition.random_item_base_class()

    assert pools and pools[0], "random_item_base_class offered an empty pool"
    leaked = sorted(cls.__name__ for cls in set(pools[0]) & excluded)
    assert not leaked, f"random_item_base_class can pick excluded classes: {leaked}"


def test_random_item_base_class_keeps_explicit_candidates():
    """An authored candidate list is the caller's choice and is used as given."""
    band = items_module.JeanWeddingBand
    assert ShopCondition.random_item_base_class([band]) is band


class _SpawnRecorder:
    def __init__(self):
        self.names = []

    def spawn_item(self, name, **_kwargs):
        self.names.append(name)
        return object()


def _equipment_pool(level, monkeypatch):
    """Every class name ``random_equipment`` can drop at ``level``.

    ``random.randint`` is pinned to each index in turn, so the whole candidate
    list is observed through the real function rather than re-derived here.
    """
    monkeypatch.setattr("src.loot_tables.functions.add_random_enchantments", lambda *a: None)
    bounds = []

    def first(lo, hi):
        bounds.append(hi)
        return lo

    monkeypatch.setattr("src.loot_tables.random.randint", first)
    Loot.random_equipment(_SpawnRecorder(), level, 0)
    tile = _SpawnRecorder()
    for index in range(bounds[0] + 1):
        monkeypatch.setattr("src.loot_tables.random.randint", lambda lo, hi, i=index: i)
        Loot.random_equipment(tile, level, 0)
    return set(tile.names)


def test_random_equipment_excludes_flagged_classes_that_carry_a_real_level(excluded, monkeypatch):
    """The by-accident safety removed: give every excluded class level 0."""
    for cls in excluded:
        monkeypatch.setattr(cls, "level", 0, raising=False)

    pool = _equipment_pool(0, monkeypatch)

    assert pool, "random_equipment offered nothing at level 0"
    leaked = sorted(pool & {cls.__name__ for cls in excluded})
    assert not leaked, f"random_equipment can drop excluded classes: {leaked}"


def test_all_enumerators_route_through_the_shared_predicate(monkeypatch):
    """Rejecting everything at the predicate empties every random pool.

    This is what makes the policy single-sourced: the next enumerator that
    calls the predicate inherits any future change to it.
    """
    monkeypatch.setattr(items_module, "is_randomly_selectable", lambda cls: False)

    assert ShopCondition.random_item_base_class() is None

    recorder = _PoolRecorder()
    merchant = _MockMerchant()
    merchant.shop_conditions["availability"].append(recorder)
    merchant._fill_remaining_stock([])
    assert recorder.pool == set()
    assert merchant.inventory == []

    # An empty equipment pool is no drop, not a randint(0, -1) crash (#674).
    tile = _SpawnRecorder()
    assert Loot.random_equipment(tile, 0, 0) is None
    assert tile.names == []
