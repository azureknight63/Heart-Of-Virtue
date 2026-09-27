"""Regression coverage for issue #739: injected uniques land in the merchant's crate.

``UniqueItemInjectionCondition.inject_unique_items`` looked for the merchant's
container through ``merchant.current_room.universe.map``. A real ``Universe``
has ``maps`` (every loaded map), not ``map``, so the walk found nothing and
every unique fell back to the merchant's own inventory. Only test fakes that
invented ``universe.map`` made it look like the crate path worked.

These tests use a real built world, so no fake can supply the missing attribute.
"""

from src.shop_conditions import UniqueItemInjectionCondition, merchant_rooms_source
from tests._real_map_helpers import map_named
from tests._world_fixtures import fresh_built_world, merchant_on_map

JAMBOS_SHOP = "grondia-jambos_shop"
STORAGE = (3, 2)  # "Jambo's Tent Storage": the crate bound to Jambo


def _jambos_crate(universe, jambo):
    """The crate the map binds to Jambo (by name, or rebound to the object)."""
    storage = map_named(universe, JAMBOS_SHOP)[STORAGE]
    return next(
        obj for obj in storage.objects_here
        if getattr(obj, "merchant", None) in ("Jambo", jambo)
    )


def test_injected_unique_lands_in_jambos_back_room_crate():
    player = fresh_built_world()  # seeds random, so the factory pick is fixed
    jambo = merchant_on_map(player.universe, JAMBOS_SHOP, "Jambo")
    crate = _jambos_crate(player.universe, jambo)
    counter_before = list(jambo.inventory)

    injected = UniqueItemInjectionCondition().inject_unique_items(jambo)

    assert len(injected) == 1
    assert injected[0] in crate.inventory
    assert injected[0] not in jambo.inventory
    assert jambo.inventory == counter_before


def test_rooms_source_of_a_real_merchant_is_its_current_map():
    """The shared room resolver finds the merchant's map on a real world."""
    player = fresh_built_world()
    jambo = merchant_on_map(player.universe, JAMBOS_SHOP, "Jambo")

    assert merchant_rooms_source(jambo) is map_named(player.universe, JAMBOS_SHOP)
    assert jambo._resolve_rooms_source() is merchant_rooms_source(jambo)
