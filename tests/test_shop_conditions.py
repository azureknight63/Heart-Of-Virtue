"""Behaviour of the shop condition system (src/shop_conditions.py).

Consolidated home for every ShopCondition test. Two other files used to cover
the same three classes: tests/test_shop_conditions_gaps.py (deleted) and the
shop half of tests/test_shop_conditions_tiles_coverage.py (now tiles-only).
Several of those tests wrapped their assertions in ``if result:``, so they
passed unchanged when injection returned nothing at all — the assertions here
are unconditional.
"""

import logging
from types import SimpleNamespace

import pytest

from src.items import Consumable, Item, Weapon
from src.shop_conditions import (
    RestockWeightBoostCondition,
    ShopCondition,
    UniqueItemInjectionCondition,
    ValueModifierCondition,
    iter_merchant_containers,
    iter_rooms,
)


class DummyItem(Item):
    def __init__(self, value=100):
        super().__init__(
            name="Dummy",
            description="Test item",
            value=value,
            maintype="Test",
            subtype="Test",
            discovery_message="a dummy item.",
            merchandise=True,
        )


class ConcreteCondition(ShopCondition):
    """Minimal concrete subclass, to exercise the base-class hook defaults."""


@pytest.fixture(autouse=True)
def isolated_unique_registry():
    """`items.unique_items_spawned` is process-global; snapshot and restore it.

    Injection permanently claims a factory name, so a test that injects would
    otherwise starve every later test (in this file or any other running in
    the same worker) of unique items.
    """
    from src.items import unique_items_spawned

    saved = set(unique_items_spawned)
    unique_items_spawned.clear()
    try:
        yield unique_items_spawned
    finally:
        unique_items_spawned.clear()
        unique_items_spawned.update(saved)


@pytest.fixture
def bare_merchant():
    """A merchant with no room, so injection takes the inventory fallback."""
    return SimpleNamespace(name="Testy", inventory=[], current_room=None)


# ---------------------------------------------------------------------------
# ShopCondition base class
# ---------------------------------------------------------------------------


class TestShopConditionBaseHooks:
    def test_apply_to_price_is_a_passthrough(self):
        cond = ConcreteCondition(name="c", description="d")
        assert cond.apply_to_price(DummyItem(), 42.0) == 42.0

    def test_adjust_restock_weights_is_a_noop(self):
        cond = ConcreteCondition(name="c", description="d")
        weights = {Item: 1.0, Weapon: 2.0}
        assert cond.adjust_restock_weights(weights) is None
        assert weights == {Item: 1.0, Weapon: 2.0}

    def test_inject_unique_items_returns_nothing(self, bare_merchant):
        cond = ConcreteCondition(name="c", description="d")
        assert cond.inject_unique_items(bare_merchant) == []
        assert bare_merchant.inventory == []

    def test_random_item_base_class_picks_from_candidates(self):
        picks = {
            ShopCondition.random_item_base_class([Weapon, Consumable])
            for _ in range(30)
        }
        assert picks == {Weapon, Consumable}

    def test_random_item_base_class_returns_none_for_empty_candidates(self):
        assert ShopCondition.random_item_base_class([]) is None

    def test_random_item_base_class_reflects_over_the_items_module(self):
        """With no candidates it scans src.items for real Item subclasses."""
        import src.items as items_module

        for _ in range(20):
            result = ShopCondition.random_item_base_class()
            assert issubclass(result, Item)
            assert result is not Item
            assert getattr(items_module, result.__name__, None) is result


# ---------------------------------------------------------------------------
# ValueModifierCondition
# ---------------------------------------------------------------------------


class TestValueModifierCondition:
    def test_matching_item_is_repriced_by_the_multiplier(self):
        cond = ValueModifierCondition(multiplier=1.5, target_class=DummyItem)
        assert cond.apply_to_price(DummyItem(), 100) == 150.0

    def test_non_matching_item_keeps_its_price(self):
        cond = ValueModifierCondition(multiplier=2.0, target_class=Weapon)
        assert cond.apply_to_price(DummyItem(), 100) == 100

    def test_subclasses_of_the_target_also_match(self):
        cond = ValueModifierCondition(multiplier=1.5, target_class=Item)
        assert cond.applies(DummyItem()) is True

    def test_applies_is_false_for_a_sibling_class(self):
        cond = ValueModifierCondition(multiplier=1.5, target_class=Weapon)
        assert cond.applies(DummyItem()) is False

    def test_price_is_clamped_at_zero_never_negative(self):
        cond = ValueModifierCondition(multiplier=-5.0, target_class=Item)
        assert cond.apply_to_price(DummyItem(), 10.0) == 0.0

    def test_unique_items_are_exempt_from_repricing(self):
        cond = ValueModifierCondition(multiplier=10.0, target_class=Item)
        item = DummyItem()
        item.unique = True
        assert cond.apply_to_price(item, 100.0) == 100.0

    def test_an_unmultipliable_price_falls_back_to_the_original(self):
        """The guard exists so a degraded price value can't break a shop."""
        cond = ValueModifierCondition(multiplier=1.5, target_class=DummyItem)
        sentinel = object()  # object() * float raises TypeError
        assert cond.apply_to_price(DummyItem(), sentinel) is sentinel

    @pytest.mark.parametrize(
        "multiplier,expected_description",
        [
            (1.25, "Weapon items +25% value"),
            (0.75, "Weapon items -25% value"),
            (1.0, "Weapon items +0% value"),
        ],
    )
    def test_auto_generated_name_and_description(
        self, multiplier, expected_description
    ):
        cond = ValueModifierCondition(multiplier=multiplier, target_class=Weapon)
        assert cond.name == "Weapon Value Modifier"
        assert cond.description == expected_description

    def test_fallback_naming_when_no_target_class_resolves(self, monkeypatch):
        monkeypatch.setattr(
            ShopCondition, "random_item_base_class", staticmethod(lambda *a: None)
        )
        cond = ValueModifierCondition(multiplier=3.0)
        assert cond.target_class is None
        assert cond.name == "Value Modifier"
        assert cond.description == "Value modifier x3.0"
        # With no target class nothing ever matches, so prices pass through.
        assert cond.apply_to_price(DummyItem(), 100) == 100

    def test_metadata_records_the_target_class_name(self):
        cond = ValueModifierCondition(multiplier=1.0, target_class=Item)
        assert cond.metadata["target_class_name"] == "Item"

    def test_omitting_target_class_picks_a_real_item_subclass(self):
        cond = ValueModifierCondition(multiplier=1.2)
        assert issubclass(cond.target_class, Item)
        assert cond.metadata["target_class_name"] == cond.target_class.__name__


# ---------------------------------------------------------------------------
# RestockWeightBoostCondition
# ---------------------------------------------------------------------------


class TestRestockWeightBoostCondition:
    def test_boost_applies_to_the_target_and_all_its_subclasses(self):
        cond = RestockWeightBoostCondition(weight_multiplier=3.0, target_class=Item)
        weights = {Item: 1.0, Weapon: 2.0, DummyItem: 4.0}
        cond.adjust_restock_weights(weights)
        assert weights == {Item: 3.0, Weapon: 6.0, DummyItem: 12.0}

    def test_classes_outside_the_target_branch_are_untouched(self):
        cond = RestockWeightBoostCondition(weight_multiplier=3.0, target_class=Weapon)
        weights = {Item: 1.0, Weapon: 2.0, DummyItem: 4.0}
        cond.adjust_restock_weights(weights)
        assert weights == {Item: 1.0, Weapon: 6.0, DummyItem: 4.0}

    def test_non_class_keys_are_skipped_rather_than_raising(self):
        cond = RestockWeightBoostCondition(weight_multiplier=2.0, target_class=Item)
        weights = {DummyItem: 1.0, "not-a-class": 5.0}
        cond.adjust_restock_weights(weights)  # issubclass(str, ...) -> TypeError
        assert weights == {DummyItem: 2.0, "not-a-class": 5.0}

    def test_weights_are_clamped_at_zero(self):
        cond = RestockWeightBoostCondition(weight_multiplier=-2.0, target_class=Item)
        weights = {Item: 5.0}
        cond.adjust_restock_weights(weights)
        assert weights == {Item: 0.0}

    def test_no_target_class_leaves_every_weight_alone(self, monkeypatch):
        monkeypatch.setattr(
            ShopCondition, "random_item_base_class", staticmethod(lambda *a: None)
        )
        cond = RestockWeightBoostCondition(weight_multiplier=9.0)
        assert cond.target_class is None
        assert cond.name == "Restock Boost"
        assert cond.description == "Restock weight x9.0 for chosen class"
        weights = {Item: 1.0, Weapon: 2.0}
        cond.adjust_restock_weights(weights)
        assert weights == {Item: 1.0, Weapon: 2.0}

    def test_auto_generated_name_and_description(self):
        cond = RestockWeightBoostCondition(weight_multiplier=2.5, target_class=Weapon)
        assert cond.name == "Weapon Restock Boost"
        assert cond.description == "Increased chance (+150%) for Weapon items"
        assert cond.metadata["target_class_name"] == "Weapon"


# ---------------------------------------------------------------------------
# Room / container traversal helpers
# ---------------------------------------------------------------------------


class TestRoomTraversalHelpers:
    def test_iter_rooms_unwraps_a_coordinate_keyed_map(self):
        rooms = [SimpleNamespace(n=1), SimpleNamespace(n=2)]
        game_map = {"name": "a-map", (0, 0): rooms[0], (1, 0): rooms[1]}
        # The "name" string entry must be skipped, not yielded as a room.
        assert list(iter_rooms(game_map)) == rooms

    def test_iter_rooms_accepts_a_plain_list(self):
        rooms = [SimpleNamespace(n=1)]
        assert list(iter_rooms(rooms)) == rooms

    @pytest.mark.parametrize("source", [None, {}, [], 7])
    def test_iter_rooms_yields_nothing_for_degenerate_sources(self, source):
        assert list(iter_rooms(source)) == []

    def test_iter_merchant_containers_matches_by_object_and_by_name(self):
        merchant = SimpleNamespace(name="Bartho", inventory=[])
        by_object = SimpleNamespace(inventory=[], merchant=merchant)
        by_name = SimpleNamespace(inventory=[], merchant="Bartho")
        someone_else = SimpleNamespace(inventory=[], merchant="Grond")
        not_a_container = SimpleNamespace(merchant=merchant)  # no inventory
        room = SimpleNamespace(
            objects_here=[by_object, by_name, someone_else, not_a_container]
        )

        assert list(iter_merchant_containers(room, merchant)) == [by_object, by_name]

    def test_iter_merchant_containers_reads_the_legacy_objects_alias(self):
        """Real rooms use objects_here; test harnesses use objects (#373-375)."""
        merchant = SimpleNamespace(name="Bartho")
        container = SimpleNamespace(inventory=[], merchant=merchant)
        room = SimpleNamespace(objects=[container])
        assert list(iter_merchant_containers(room, merchant)) == [container]


# ---------------------------------------------------------------------------
# UniqueItemInjectionCondition
# ---------------------------------------------------------------------------


class TestUniqueItemInjection:
    def test_default_name_and_description(self):
        cond = UniqueItemInjectionCondition()
        assert cond.name == "Unique Item Injection"
        assert cond.description == "Injects a unique item into merchant inventory"

    def test_injects_exactly_one_flagged_item_into_the_merchant(
        self, bare_merchant
    ):
        cond = UniqueItemInjectionCondition()

        injected = cond.inject_unique_items(bare_merchant)

        assert len(injected) == 1
        item = injected[0]
        assert bare_merchant.inventory == [item]
        assert item.unique is True
        assert item.unique_condition == "Unique Item Injection"
        assert item.name in {"Ancient Relic", "Dragon Heart Gem", "Crystal Tear"}

    def test_unique_condition_records_a_custom_condition_name(self, bare_merchant):
        cond = UniqueItemInjectionCondition(name="Festival Stock")

        injected = cond.inject_unique_items(bare_merchant)

        assert injected[0].unique_condition == "Festival Stock"

    def test_creates_the_inventory_list_when_the_merchant_lacks_one(self):
        merchant = SimpleNamespace(name="Bare", current_room=None)

        injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

        assert merchant.inventory == injected

    def test_a_blank_description_is_replaced_with_the_injected_item_name(
        self, bare_merchant
    ):
        cond = UniqueItemInjectionCondition()
        cond.description = ""

        injected = cond.inject_unique_items(bare_merchant)

        assert cond.description == f"Injected unique item: {injected[0].name}"

    def test_each_unique_item_spawns_at_most_once_world_wide(self):
        merchants = [
            SimpleNamespace(name=f"m{i}", inventory=[], current_room=None)
            for i in range(4)
        ]

        injected = []
        for merchant in merchants:
            injected.extend(
                UniqueItemInjectionCondition().inject_unique_items(merchant)
            )

        # There are exactly three unique factories; the fourth merchant gets none.
        assert len(injected) == 3
        assert len({type(item) for item in injected}) == 3
        assert merchants[3].inventory == []

        # And the registry now names every one of them.
        from src.items import unique_item_factories, unique_items_spawned

        assert unique_items_spawned == {f.__name__ for f in unique_item_factories}

    def test_returns_empty_when_every_unique_is_already_spawned(
        self, bare_merchant, isolated_unique_registry
    ):
        from src.items import unique_item_factories

        isolated_unique_registry.update(f.__name__ for f in unique_item_factories)

        assert UniqueItemInjectionCondition().inject_unique_items(bare_merchant) == []
        assert bare_merchant.inventory == []

    def test_injects_into_a_merchant_owned_container_when_one_exists(self):
        merchant = SimpleNamespace(name="Bartho", inventory=[])
        container = SimpleNamespace(inventory=[], merchant=merchant)
        room = SimpleNamespace(objects_here=[container])
        universe = SimpleNamespace(map={(0, 0): room})
        merchant.current_room = SimpleNamespace(universe=universe)

        injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

        assert container.inventory == injected
        assert merchant.inventory == []  # container wins over the fallback

    def test_container_lookup_failure_logs_and_falls_back_to_the_merchant(
        self, caplog
    ):
        class Exploding:
            @property
            def universe(self):
                raise RuntimeError("malformed world")

        merchant = SimpleNamespace(
            name="Bartho", inventory=[], current_room=Exploding()
        )

        with caplog.at_level(logging.WARNING, logger="src.shop_conditions"):
            injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

        assert merchant.inventory == injected
        assert len(injected) == 1
        # The swallow is deliberately noisy: silence is what hid issue #375.
        assert any("container lookup failed" in r.message for r in caplog.records)

    def test_an_unrecoverable_failure_returns_an_empty_list(
        self, monkeypatch, caplog, bare_merchant
    ):
        import src.shop_conditions as shop_conditions

        def _boom(_seq):
            raise RuntimeError("boom")

        monkeypatch.setattr(shop_conditions.random, "choice", _boom)

        with caplog.at_level(logging.WARNING, logger="src.shop_conditions"):
            result = UniqueItemInjectionCondition().inject_unique_items(bare_merchant)

        assert result == []
        assert bare_merchant.inventory == []
        assert any("injection aborted" in r.message for r in caplog.records)
