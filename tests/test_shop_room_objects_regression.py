"""Regression tests for the shop room/container walk.

Merchant restock, shop pricing and unique-item injection all have to find the
containers a merchant owns by walking the rooms of the current map. Every one of
those walks used to read a ``room.objects`` attribute that real rooms do not
have — real rooms expose ``objects_here`` (``src/tiles.py``) — so the walks
silently found nothing:

* issue #373 — container-housed unique items were destroyed without releasing
  their ``items.unique_items_spawned`` registry entry, so they could never
  respawn.
* issue #374 — container-housed stock never received ``ValueModifierCondition``
  pricing while merchant-inventory stock in the same shop did.
* issue #375 — ``UniqueItemInjectionCondition`` also iterated the map dict's
  ``(x, y)`` keys instead of its rooms, so the container-placement path was
  dead and the fault was swallowed by a bare ``except``.

The rooms in these tests therefore use the *real* ``objects_here`` attribute and
a coordinate-keyed dict map, exactly like the live engine.
"""

import logging

from src.items import (
    AncientRelic,
    Antidote,
    Consumable,
    DragonHeartGem,
    Draught,
    Restorative,
    unique_items_spawned,
)
from src.npc import Merchant
from src.objects import Container
from src.shop_conditions import UniqueItemInjectionCondition, ValueModifierCondition


class RealisticRoom:
    """Room stand-in that only exposes the attributes a real MapTile has."""

    def __init__(self, universe=None):
        self.objects_here = []
        self.items_here = []
        self.universe = universe
        self.map = None


class RealisticUniverse:
    """Universe stand-in whose ``map`` is coordinate-keyed, as in universe.py."""

    def __init__(self, rooms):
        self.map = {(index, 0): room for index, room in enumerate(rooms)}


def _merchant_in_world(name="Objects Here Tester", stock_count=0, **merchant_kwargs):
    merchant = Merchant(
        name=name,
        description="desc",
        damage=1,
        aggro=False,
        exp_award=0,
        stock_count=stock_count,
        **merchant_kwargs,
    )
    room = RealisticRoom()
    room.universe = RealisticUniverse([room])
    merchant.current_room = room
    return merchant, room


def _stub_spawn_item(room):
    """Build a ``room.spawn_item`` stand-in that resolves any real item class by name.

    Real rooms resolve ``item_type`` (a class name string) against
    ``src.items`` -- this mirrors that instead of hardcoding a single class,
    so every test in this file that needs a spawnable room shares one
    implementation.
    """

    def spawn_item(item_type, amt=1, hidden=False, hfactor=0, merchandise=False):
        import src.items as items_module

        cls = getattr(items_module, item_type)
        item = cls(merchandise=merchandise)
        room.items_here.append(item)
        return item

    return spawn_item


# ---------------------------------------------------------------------------
# Issue #373 — unique items in containers must release their registry entry
# ---------------------------------------------------------------------------


def test_reset_stock_state_releases_unique_item_housed_in_container():
    unique_items_spawned.clear()
    merchant, room = _merchant_in_world()

    gem = DragonHeartGem(merchandise=True)
    unique_items_spawned.add(gem.__class__.__name__)
    container = Container(name="Relic Case", merchant=merchant, items=[gem])
    room.objects_here.append(container)

    containers = merchant._reset_stock_state()

    # The container is cleared (and returned for restocking)...
    assert container in containers
    assert container.inventory == []
    # ...and the unique item it held is released back into the registry so it
    # can spawn again, rather than being destroyed while still claimed.
    assert gem.__class__.__name__ not in unique_items_spawned


def test_reset_stock_state_releases_unique_items_from_inventory_and_container():
    unique_items_spawned.clear()
    merchant, room = _merchant_in_world()

    relic = AncientRelic(merchandise=True)
    gem = DragonHeartGem(merchandise=True)
    unique_items_spawned.update({relic.__class__.__name__, gem.__class__.__name__})
    merchant.inventory = [relic]
    room.objects_here.append(Container(name="Case", merchant=merchant, items=[gem]))

    merchant._reset_stock_state()

    assert merchant.inventory == []
    assert relic.__class__.__name__ not in unique_items_spawned
    assert gem.__class__.__name__ not in unique_items_spawned


def test_reset_stock_state_ignores_containers_owned_by_other_merchants():
    unique_items_spawned.clear()
    merchant, room = _merchant_in_world()

    gem = DragonHeartGem(merchandise=True)
    unique_items_spawned.add(gem.__class__.__name__)
    foreign = Container(name="Rival Case", merchant="Someone Else", items=[gem])
    room.objects_here.append(foreign)

    containers = merchant._reset_stock_state()

    assert containers == []
    assert foreign.inventory == [gem]
    assert gem.__class__.__name__ in unique_items_spawned


def test_reset_stock_state_matches_container_owned_by_merchant_name():
    unique_items_spawned.clear()
    merchant, room = _merchant_in_world()
    container = Container(name="Case", merchant=merchant.name, items=[Restorative()])
    room.objects_here.append(container)

    containers = merchant._reset_stock_state()

    assert containers == [container]
    assert container.inventory == []


# ---------------------------------------------------------------------------
# Issue #374 — container-housed stock must be priced like merchant stock
# ---------------------------------------------------------------------------


def test_apply_value_conditions_prices_items_in_objects_here_containers():
    merchant, room = _merchant_in_world()
    shelved = Restorative(merchandise=True)
    shelved.base_value = shelved.value
    on_merchant = Restorative(merchandise=True)
    on_merchant.base_value = on_merchant.value
    merchant.inventory = [on_merchant]
    room.objects_here.append(
        Container(name="Shelf", merchant=merchant, items=[shelved])
    )
    merchant.shop_conditions["value"] = [
        ValueModifierCondition(multiplier=1.5, target_class=Restorative)
    ]

    merchant._apply_value_conditions()

    expected = max(1, int(shelved.base_value * 1.5))
    assert on_merchant.value == expected
    # Same shop, same restock cycle -> same price treatment.
    assert shelved.value == expected


# ---------------------------------------------------------------------------
# Issue #375 — unique-item injection must reach merchant-owned containers
# ---------------------------------------------------------------------------


def test_inject_unique_items_places_item_in_container_from_dict_map():
    unique_items_spawned.clear()
    merchant, room = _merchant_in_world()
    container = Container(name="Curio Cabinet", merchant=merchant, items=[])
    room.objects_here.append(container)

    injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

    assert len(injected) == 1
    assert injected[0] in container.inventory
    assert injected[0] not in merchant.inventory


def test_inject_unique_items_falls_back_to_inventory_without_container():
    unique_items_spawned.clear()
    merchant, _room = _merchant_in_world()

    injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

    assert len(injected) == 1
    assert injected[0] in merchant.inventory


def test_inject_unique_items_logs_when_container_lookup_fails(caplog):
    unique_items_spawned.clear()
    merchant, _room = _merchant_in_world()
    merchant.inventory = []

    class ExplodingUniverse:
        @property
        def map(self):
            raise RuntimeError("map unavailable")

    merchant.current_room.universe = ExplodingUniverse()

    with caplog.at_level(logging.WARNING, logger="src.shop_conditions"):
        injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

    # The failure is survivable (item still placed) but no longer silent.
    assert len(injected) == 1
    assert injected[0] in merchant.inventory
    assert any("container lookup failed" in rec.message for rec in caplog.records)


def test_container_injection_claims_exactly_one_registry_entry():
    """The container path must keep the same registry bookkeeping as the fallback."""
    unique_items_spawned.clear()
    merchant, room = _merchant_in_world()
    room.objects_here.append(Container(name="Case", merchant=merchant, items=[]))

    injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

    assert len(unique_items_spawned) == 1
    assert injected[0].__class__.__name__ in unique_items_spawned
    assert getattr(injected[0], "unique", False) is True


# ---------------------------------------------------------------------------
# Issue #376 — always-stock items must snapshot base_value like restock items
# ---------------------------------------------------------------------------


def test_create_always_stock_item_snapshots_base_value():
    merchant, room = _merchant_in_world()
    room.spawn_item = _stub_spawn_item(room)

    created = merchant._create_always_stock_item(Restorative)

    assert created is not None
    assert created.base_value == created.value


def test_always_stock_items_receive_value_conditions():
    """base_value is what lets value conditions price an item at all."""
    merchant, room = _merchant_in_world()
    room.spawn_item = _stub_spawn_item(room)
    created = merchant._create_always_stock_item(Restorative)
    merchant.inventory = [created]
    merchant.shop_conditions["value"] = [
        ValueModifierCondition(multiplier=2.0, target_class=Restorative)
    ]

    merchant._apply_value_conditions()

    assert created.value == max(1, int(created.base_value * 2.0))


# ---------------------------------------------------------------------------
# Issue #546 — always_stock items must never be swallowed by a container
# ---------------------------------------------------------------------------


def test_update_goods_always_stock_items_land_in_inventory_not_container():
    """Regression test for issue #546 (Jambo's Tent sells no healing items).

    Jambo's always_stock potions (Restorative/Draught/Antidote) are all
    Consumable subclasses, and his back-room storage Crate is authored with
    allowed_item_types=[Consumable] -- so routing always_stock through
    _place_item's container-matching logic silently diverts every guaranteed
    potion into the Crate's inventory. ShopSerializer.serialize_state() and
    GameService._sellable_items() both read only merchant.inventory, so the
    Buy tab (and shop_buy/shop_sell) never see them: the potions are always
    stocked, just never reachable by the shop API.

    _fill_remaining_stock (the random-fill pass) is stubbed out here so this
    test isolates the always_stock placement path specifically; the random
    fill's legitimate use of containers is covered by the existing tests
    above (and by test_merchant.py / test_npc_shop_merchants_coverage.py).
    """
    merchant, room = _merchant_in_world(
        name="Jambo",
        stock_count=6,
        always_stock=[
            Restorative(count=5, merchandise=True),
            Draught(count=4, merchandise=True),
            Antidote(count=3, merchandise=True),
        ],
        specialties=[Consumable],
        enchantment_rate=0.0,
    )
    room.spawn_item = _stub_spawn_item(room)

    crate = Container(
        name="Jambo's Tent Storage",
        merchant=merchant,
        allowed_subtypes=[Consumable],
    )
    room.objects_here.append(crate)

    # Isolate the always_stock path: the random-fill pass legitimately uses
    # containers and is exercised by other tests, not this one.
    merchant._fill_remaining_stock = lambda containers: None

    merchant.update_goods()

    inventory_names = {type(it).__name__ for it in merchant.inventory}
    crate_names = [type(it).__name__ for it in crate.inventory]
    always_stock_names = {"Restorative", "Draught", "Antidote"}

    assert always_stock_names <= inventory_names, (
        "always_stock potions must be reachable via merchant.inventory (the "
        f"Buy tab); merchant.inventory had {inventory_names}, but the Crate "
        f"(allowed_item_types=[Consumable]) swallowed {crate_names}"
    )
    assert not crate_names, (
        "always_stock items must never be routed into a container; found "
        f"{crate_names} in the Crate instead of merchant.inventory"
    )
