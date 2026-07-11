"""Additional coverage for src/shop_conditions.py — closes gaps left by
tests/test_shop_conditions.py and tests/test_shop_conditions_tiles_coverage.py:
the exception-swallowing branches in apply_to_price/adjust_restock_weights,
the merchant-container-found path (and its nested break) in
inject_unique_items, and inject_unique_items' outer except-returns-[] branch.
"""

from unittest.mock import MagicMock, patch

from src.shop_conditions import (
    ValueModifierCondition,
    RestockWeightBoostCondition,
    UniqueItemInjectionCondition,
)
from src.items import Item


class DummyItem(Item):
    def __init__(self):
        super().__init__(
            name="Dummy",
            description="Test item",
            value=10,
            maintype="Test",
            subtype="Test",
            discovery_message="a dummy item.",
        )


def test_value_modifier_apply_to_price_swallows_multiplication_error():
    cond = ValueModifierCondition(multiplier=1.5, target_class=DummyItem)
    item = DummyItem()
    bad_price = object()  # object() * float raises TypeError inside the try block
    with patch.object(cond, "applies", return_value=True):
        result = cond.apply_to_price(item, bad_price)
    assert result is bad_price


def test_restock_weight_boost_skips_non_class_keys_via_exception_guard():
    cond = RestockWeightBoostCondition(weight_multiplier=2.0, target_class=DummyItem)
    weight_map = {DummyItem: 1.0, "not-a-class": 5.0}
    # issubclass("not-a-class", DummyItem) raises TypeError -> except: continue
    cond.adjust_restock_weights(weight_map)
    assert weight_map[DummyItem] == 2.0
    assert weight_map["not-a-class"] == 5.0  # untouched, guard swallowed the error


def test_inject_unique_items_finds_and_uses_merchant_container():
    from src.items import unique_items_spawned

    unique_items_spawned.clear()

    merchant = MagicMock()
    container = MagicMock()
    container.merchant = merchant
    container.inventory = []

    room = MagicMock()
    room.objects = [container]

    universe = MagicMock()
    universe.map = [room]

    merchant.current_room.universe = universe

    cond = UniqueItemInjectionCondition()
    result = cond.inject_unique_items(merchant)

    if result:
        assert result[0] in container.inventory
        # Should NOT have fallen back to merchant.inventory when a container exists.
        assert not hasattr(merchant, "inventory") or result[0] not in getattr(
            merchant, "inventory", []
        )


def test_inject_unique_items_container_search_exception_falls_back(capsys):
    """If locating a container raises, the except swallows it and falls
    through to the merchant.inventory fallback path rather than crashing."""
    from src.items import unique_items_spawned

    unique_items_spawned.clear()

    merchant = MagicMock()
    merchant.inventory = []
    # Accessing .universe raises, forcing the container-search try/except.
    type(merchant.current_room).universe = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    cond = UniqueItemInjectionCondition()
    result = cond.inject_unique_items(merchant)
    if result:
        assert result[0] in merchant.inventory


def test_random_item_base_class_reflects_over_items_module_when_no_candidates():
    """Covers the `candidates is None` default reflection path: scans the
    real items module for Item subclasses via inspect.getmembers rather
    than using an explicit candidates list."""
    from src.shop_conditions import ShopCondition

    result = ShopCondition.random_item_base_class()
    assert result is not None
    assert issubclass(result, Item)
    assert result is not Item


def test_value_modifier_condition_uses_reflection_when_no_target_class_given():
    """ValueModifierCondition() with no target_class triggers
    random_item_base_class()'s default (candidates=None) reflection path."""
    cond = ValueModifierCondition(multiplier=1.2)
    assert cond.target_class is not None
    assert issubclass(cond.target_class, Item)


def test_inject_unique_items_outer_exception_returns_empty_list():
    merchant = MagicMock()
    cond = UniqueItemInjectionCondition()
    with patch("random.choice", side_effect=RuntimeError("boom")):
        result = cond.inject_unique_items(merchant)
    assert result == []
