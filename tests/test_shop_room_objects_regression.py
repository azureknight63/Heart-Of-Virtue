"""Regression tests for the shop room/container walk.

Merchant restock, shop pricing and unique-item injection all have to find the
containers a merchant owns by walking the rooms of the current map. Every one of
those walks used to read a ``room.objects`` attribute that real rooms do not
have — real rooms expose ``objects_here`` (``src/tiles.py``) — so the walks
silently found nothing:

* issue #373 — container-housed unique items were destroyed without releasing
  their unique-item registry entry (now ``Universe.unique_items_spawned``), so they could never
  respawn.
* issue #374 — container-housed stock never received ``ValueModifierCondition``
  pricing while merchant-inventory stock in the same shop did.
* issue #375 — ``UniqueItemInjectionCondition`` also iterated the map dict's
  ``(x, y)`` keys instead of its rooms, so the container-placement path was
  dead and the fault was swallowed by a bare ``except``.

The rooms in these tests therefore use the *real* ``objects_here`` attribute and
a coordinate-keyed dict map, exactly like the live engine.

The same walk is where issue #611's two restock defects lived, so their
regressions are here too: unplaceable random stock abandoned on the merchant's
floor, and never-stock families (``Special`` above all) filtered by exact
membership instead of by subclass.
"""

import logging
import random
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from src.items import (
    AncientRelic,
    Antidote,
    Consumable,
    DragonHeartGem,
    Draught,
    MineralSolvent,
    Restorative,
    SlimeFlask,
    Weapon,
    unique_item_factories,
)
from src.npc import Merchant
from src.npc._shop import _NEVER_STOCK_FAMILIES
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
        self.unique_items_spawned = set()


def _claims(merchant):
    """The unique-item claims of the world ``merchant`` stands in."""
    return merchant.current_room.universe.unique_items_spawned


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
    merchant, room = _merchant_in_world()

    gem = DragonHeartGem(merchandise=True)
    _claims(merchant).add(gem.__class__.__name__)
    container = Container(name="Relic Case", merchant=merchant, items=[gem])
    room.objects_here.append(container)

    containers = merchant._reset_stock_state()

    # The container is cleared (and returned for restocking)...
    assert container in containers
    assert container.inventory == []
    # ...and the unique item it held is released back into the registry so it
    # can spawn again, rather than being destroyed while still claimed.
    assert gem.__class__.__name__ not in _claims(merchant)


def test_reset_stock_state_releases_unique_items_from_inventory_and_container():
    merchant, room = _merchant_in_world()

    relic = AncientRelic(merchandise=True)
    gem = DragonHeartGem(merchandise=True)
    _claims(merchant).update({relic.__class__.__name__, gem.__class__.__name__})
    merchant.inventory = [relic]
    room.objects_here.append(Container(name="Case", merchant=merchant, items=[gem]))

    merchant._reset_stock_state()

    assert merchant.inventory == []
    assert relic.__class__.__name__ not in _claims(merchant)
    assert gem.__class__.__name__ not in _claims(merchant)


def test_reset_stock_state_ignores_containers_owned_by_other_merchants():
    merchant, room = _merchant_in_world()

    gem = DragonHeartGem(merchandise=True)
    _claims(merchant).add(gem.__class__.__name__)
    foreign = Container(name="Rival Case", merchant="Someone Else", items=[gem])
    room.objects_here.append(foreign)

    containers = merchant._reset_stock_state()

    assert containers == []
    assert foreign.inventory == [gem]
    assert gem.__class__.__name__ in _claims(merchant)


def test_reset_stock_state_matches_container_owned_by_merchant_name():
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
    merchant, room = _merchant_in_world()
    container = Container(name="Curio Cabinet", merchant=merchant, items=[])
    room.objects_here.append(container)

    injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

    assert len(injected) == 1
    assert injected[0] in container.inventory
    assert injected[0] not in merchant.inventory


def test_inject_unique_items_falls_back_to_inventory_without_container():
    merchant, _room = _merchant_in_world()

    injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

    assert len(injected) == 1
    assert injected[0] in merchant.inventory


def test_inject_unique_items_logs_when_container_lookup_fails(caplog):
    merchant, _room = _merchant_in_world()
    merchant.inventory = []

    class ExplodingUniverse:
        def __init__(self):
            self.unique_items_spawned = set()

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
    merchant, room = _merchant_in_world()
    room.objects_here.append(Container(name="Case", merchant=merchant, items=[]))

    injected = UniqueItemInjectionCondition().inject_unique_items(merchant)

    assert len(_claims(merchant)) == 1
    assert injected[0].__class__.__name__ in _claims(merchant)
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

    # ...and isolate the unique-injection pass too, which is the other
    # non-always_stock writer update_goods() drives. It picks its item with a
    # bare `random.choice(available_factories)`
    # (UniqueItemInjectionCondition.inject_unique_items, src/shop_conditions.py)
    # and places it into a *merchant-owned* container -- which the Crate below
    # is -- so leaving it live made this test assert on an unseeded roll, the
    # one thing CLAUDE.md says never to do. It surfaced as a CrystalTear in the
    # crate once six new test files shifted xdist's --dist loadfile grouping and
    # with it the per-worker random state; the shop path itself never changed.
    # Marking every factory as already spawned empties `available_factories`,
    # so the pass returns [] deterministically (`_unique_injection_disarmed`).
    with _unique_injection_disarmed(merchant):
        merchant.update_goods()

    inventory_names = {type(it).__name__ for it in merchant.inventory}
    crate_names = [type(it).__name__ for it in crate.inventory]
    always_stock_names = {"Restorative", "Draught", "Antidote"}

    assert always_stock_names <= inventory_names, (
        "always_stock potions must be reachable via merchant.inventory (the "
        f"Buy tab); merchant.inventory had {inventory_names}, but the Crate "
        f"(allowed_subtypes=[Consumable]) swallowed {crate_names}"
    )
    assert not crate_names, (
        "always_stock items must never be routed into a container; found "
        f"{crate_names} in the Crate instead of merchant.inventory"
    )


# ---------------------------------------------------------------------------
# Issue #611 — unplaceable random stock must not be abandoned on the floor
# ---------------------------------------------------------------------------


def _jambo_like_merchant():
    """Build the shipped Jambo configuration: 5 always_stock, 1 spare slot.

    Mirrors ``grondia-jambos_shop.json`` tile (2, 2) -- ``stock_count`` 6
    against five ``always_stock`` potions, so exactly one merchant slot is
    free, plus the tile (3, 2) storage Crate that accepts ``[Consumable]``
    only with a cap of 12. That combination is what makes the random-fill
    pass roll far more classes than it can house.
    """
    merchant, room = _merchant_in_world(
        name="Jambo",
        stock_count=6,
        always_stock=[
            Restorative(count=5, merchandise=True),
            Draught(count=4, merchandise=True),
            Antidote(count=3, merchandise=True),
            SlimeFlask(count=1, merchandise=True),
            MineralSolvent(count=1, merchandise=True),
        ],
        specialties=[Consumable],
        enchantment_rate=0.0,
    )
    room.spawn_item = _stub_spawn_item(room)
    crate = Container(
        name="Jambo's Tent Storage",
        merchant=merchant,
        allowed_subtypes=[Consumable],
        stock_count=12,
    )
    room.objects_here.append(crate)
    return merchant, room, crate


@contextmanager
def _unique_injection_disarmed(merchant):
    """Neutralise ``UniqueItemInjectionCondition`` for the duration.

    Its pick is a bare ``random.choice(available_factories)`` into a
    merchant-owned container, so leaving it live makes a restock assertion
    depend on an unseeded roll. Marking every factory as already spawned
    empties ``available_factories``. Derived from ``unique_item_factories``,
    not a hand-written list of names, so a new unique cannot reopen the hole.
    """
    assert unique_item_factories, "no unique factories to isolate -- check the import"
    claims = _claims(merchant)
    spawned_before = set(claims)
    claims.update(f.__name__ for f in unique_item_factories)
    try:
        yield
    finally:
        claims.clear()
        claims.update(spawned_before)


def _restock_without_unique_injection(merchant, seed):
    """Run ``update_goods`` deterministically with the unique pass neutralised.

    ``_fill_remaining_stock`` picks with ``random.choice``/``random.uniform``,
    so the roll is seeded rather than left to the engine's ~220 unseeded
    ``random.*`` calls.
    """
    with _unique_injection_disarmed(merchant):
        random.seed(seed)
        merchant.update_goods()


def _floor_merchandise(room):
    return [it for it in room.items_here if getattr(it, "merchandise", False)]


#: The leak is roll-dependent, so one seed is not evidence of a fix.
_LEAK_SEEDS = range(5)


@pytest.mark.parametrize("seed", _LEAK_SEEDS)
def test_restock_leaves_no_merchandise_on_the_merchants_floor(seed):
    """Regression test for issue #611 (unexplained floor items in Jambo's tent).

    ``_fill_remaining_stock`` spawns each candidate into ``current_room``
    first and places it afterwards. When neither an eligible container nor a
    free merchant slot accepted the roll it used to ``continue``, skipping
    ``_remove_placed_item_from_room`` -- so the item stayed in
    ``room.items_here``, merchandise-flagged, takeable, and absent from the
    Buy panel. With the shipped Jambo numbers that abandoned roughly 23 items
    per restock on the tent entrance tile.
    """
    merchant, room, crate = _jambo_like_merchant()

    _restock_without_unique_injection(merchant, seed=seed)

    # The restock must actually have happened, or "no litter" proves nothing.
    assert crate.inventory, "the Crate took no stock -- the fill pass never ran"
    litter = _floor_merchandise(room)
    assert litter == [], (
        f"seed {seed}: restocking must not abandon merchandise in the "
        f"merchant's room; {len(litter)} item(s) were left on the floor: "
        f"{sorted(type(it).__name__ for it in litter)}"
    )


# ---------------------------------------------------------------------------
# Issue #611 — the Special family must never be random merchant stock
# ---------------------------------------------------------------------------


def _merchant_with_only_container(allowed, cap=20):
    """A merchant with no shelves of his own and one container accepting ``allowed``.

    ``stock_count=0`` means every roll has to find a home in the container or
    nowhere, so the container's contents are a direct readout of which classes
    the random-fill pass considers stockable -- no dependence on which roll
    happened to land in a merchant slot.
    """
    merchant, room = _merchant_in_world(name="Curio Dealer", stock_count=0)
    room.spawn_item = _stub_spawn_item(room)
    container = Container(
        name="Curio Case",
        merchant=merchant,
        allowed_subtypes=[allowed],
        stock_count=cap,
    )
    room.objects_here.append(container)
    return merchant, room, container


def test_the_never_stock_families_are_declared():
    """Non-vacuity for the parametrized test below: an emptied tuple would
    parametrize it over nothing and pass."""
    assert _NEVER_STOCK_FAMILIES, "no never-stock families declared"


@pytest.mark.parametrize(
    "family", _NEVER_STOCK_FAMILIES, ids=lambda cls: cls.__name__
)
def test_random_stock_never_contains_a_never_stock_family(family):
    """Regression test for issue #611 (an unbuyable, unreadable book in Jambo's tent).

    The old ``disallowed_classes`` set listed ``Special``, but the filter was
    ``obj in disallowed_classes`` -- exact membership, not a subclass test.
    Every concrete ``Special`` subclass therefore stayed a valid random-stock
    candidate: quest tokens, lore fragments, and bare ``Book`` (name "Book",
    value 5, ``text_file_path=None``), which spawns merchandise-flagged,
    invisible to the Buy panel, and reads as "This book is mysteriously blank."

    Parametrized over the engine's own ``_NEVER_STOCK_FAMILIES``, so a family
    added there is covered here without anyone remembering to. ``Relic`` has
    no subclasses today; its row asserts the rule rather than a live leak.
    """
    merchant, _room, case = _merchant_with_only_container(family)

    _restock_without_unique_injection(merchant, seed=0)

    stocked = sorted(type(it).__name__ for it in case.inventory)
    assert stocked == [], (
        f"no {family.__name__}-family item may be rolled as random stock; "
        f"the pass stocked {stocked}"
    )


def test_random_stock_still_contains_ordinary_merchandise():
    """Positive control: the exclusion must not have emptied the candidate pool.

    ``Weapon`` is excluded too, but by exact membership and for the opposite
    reason -- it is an abstract base nobody should instantiate directly, while
    its concrete subclasses are exactly what an armourer sells. A subclass test
    applied to it would take those with it, so this is the test that fails if
    the fix is made too broad.
    """
    merchant, _room, case = _merchant_with_only_container(Weapon)

    _restock_without_unique_injection(merchant, seed=0)

    stocked = [type(it).__name__ for it in case.inventory]
    assert stocked, "the random-fill pass stocked no weapons at all"
    assert all(
        issubclass(type(it), Weapon) and type(it) is not Weapon for it in case.inventory
    ), f"a Weapon-only container took something else: {stocked}"


def test_container_matching_still_honours_a_spoofed_dunder_class():
    """The instance-level match must keep ``isinstance`` semantics.

    ``_containers_accepting_type`` began as a plain ``isinstance`` call and is
    now a wrapper over the class-level rule. ``isinstance`` consults
    ``__class__`` and ``type()`` bypasses it, so writing the wrapper with
    ``type(item)`` would silently stop honouring the exact test-double pattern
    CLAUDE.md prescribes ("to pass an engine ``isinstance``, set
    ``mock.__class__`` to the real class"). Nothing in the suite happened to
    exercise that, which is why it gets a test of its own rather than trust.
    """
    merchant, room = _merchant_in_world()
    crate = Container(
        name="Potion Crate", merchant=merchant, allowed_subtypes=[Consumable]
    )
    double = MagicMock()
    double.__class__ = Restorative

    assert isinstance(double, Consumable), "the double no longer spoofs its class"
    assert merchant._containers_accepting_type([crate], double) == [crate], (
        "a double whose __class__ is a real Consumable must match a "
        "Consumable-only container, exactly as isinstance would"
    )
