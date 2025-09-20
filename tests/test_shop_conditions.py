from shop_conditions import (
    ShopCondition,
    ValueModifierCondition,
    RestockWeightBoostCondition,
    UniqueItemInjectionCondition,
)
from items import Item, Weapon


class DummyItem(Item):
    def __init__(self):
        super().__init__(
            name="Dummy",
            description="Test item",
            value=100,
            maintype="Test",
            subtype="Test",
            discovery_message="a dummy item.",
            merchandise=True,
        )


class DummyMerchant:
    def __init__(self):
        self.inventory = []
        self.current_room = None  # triggers fallback path for injection


def test_value_modifier_condition_price_change():
    item = DummyItem()
    cond = ValueModifierCondition(name="", description="", multiplier=1.5, target_class=DummyItem)
    base_price = item.value
    new_price = cond.apply_to_price(item, base_price)
    assert new_price == base_price * 1.5


def test_value_modifier_condition_non_match():
    item = DummyItem()
    cond = ValueModifierCondition(name="", description="", multiplier=2.0, target_class=Weapon)
    base_price = item.value
    new_price = cond.apply_to_price(item, base_price)
    assert new_price == base_price  # no change when class doesn't match


def test_restock_weight_boost_condition():
    cond = RestockWeightBoostCondition(name="", description="", weight_multiplier=3.0, target_class=Item)
    weight_map = {Item: 1.0, Weapon: 2.0, DummyItem: 4.0}
    cond.adjust_restock_weights(weight_map)
    assert weight_map[Item] == 3.0
    assert weight_map[Weapon] == 6.0
    assert weight_map[DummyItem] == 12.0


def test_unique_item_injection_condition():
    merchant = DummyMerchant()
    cond = UniqueItemInjectionCondition(name="", description="")
    injected = cond.inject_unique_items(merchant)
    assert len(injected) == 1
    assert injected[0] in merchant.inventory
    assert getattr(injected[0], 'unique', False) is True
    assert getattr(injected[0], 'unique_condition') == cond.name or 'Unique Item Injection'
    assert injected[0].name in {"Ancient Relic", "Dragon Heart Gem", "Crystal Tear"}


def test_unique_item_injection_no_duplicates():
    from items import unique_items_spawned
    unique_items_spawned.clear()
    merchants = [DummyMerchant() for _ in range(4)]  # one more than number of unique items
    conditions = [UniqueItemInjectionCondition(name="", description="") for _ in range(4)]
    injected_all = []
    for cond, merchant in zip(conditions, merchants):
        injected = cond.inject_unique_items(merchant)
        if injected:
            injected_all.extend(injected)
    # Expect exactly 3 (number of predefined unique items)
    assert len(injected_all) == 3
    # All class names should be distinct
    assert len({item.__class__.__name__ for item in injected_all}) == 3
    # Further attempt after exhaustion yields no injection
    extra_cond = UniqueItemInjectionCondition(name="", description="")
    extra_result = extra_cond.inject_unique_items(DummyMerchant())
    assert extra_result == []
