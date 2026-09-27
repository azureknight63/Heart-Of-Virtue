"""Restock (``_reset_stock_state``) releases unique-item claims.

Claims live on the merchant's universe (``Universe.unique_items_spawned``,
issue #727), so every release is checked against that world's registry.
"""

from src.items import AncientRelic, CrystalTear, DragonHeartGem
from src.npc import Merchant
from src.objects import Container


class DummyRoom:
    def __init__(self):
        self.objects = []
        self.universe = None  # will be set after universe creation


class DummyUniverse:
    def __init__(self, rooms):
        self.map = rooms
        self.unique_items_spawned = set()


def _merchant(name):
    return Merchant(name=name, description="desc", damage=1, aggro=False, exp_award=0, stock_count=0)


def _merchant_in_world(name):
    m = _merchant(name)
    room = DummyRoom()
    universe = DummyUniverse([room])
    room.universe = universe
    m.current_room = room
    return m, room, universe


def test_unique_items_deregistered_on_reset_inventory_and_containers():
    m, room, universe = _merchant_in_world("Test Merchant")
    relic = AncientRelic(merchandise=True)  # directly in merchant inventory
    gem = DragonHeartGem(merchandise=True)  # inside a merchant container
    universe.unique_items_spawned.update({"AncientRelic", "DragonHeartGem"})
    m.inventory = [relic]
    cont = Container(name="Chest", merchant=m, items=[gem])
    room.objects.append(cont)

    containers = m._reset_stock_state()

    assert m.inventory == []
    assert cont.inventory == []
    assert universe.unique_items_spawned == set()
    assert cont in containers


def test_unique_items_deregistered_two_containers():
    """Two containers each with a different unique item: both released, both cleared."""
    m, room, universe = _merchant_in_world("Test Merchant 3")
    gem = DragonHeartGem(merchandise=True)
    tear = CrystalTear(merchandise=True)
    universe.unique_items_spawned.update({"DragonHeartGem", "CrystalTear"})
    c1 = Container(name="Case1", merchant=m, items=[gem])
    c2 = Container(name="Case2", merchant=m, items=[tear])
    room.objects.extend([c1, c2])

    containers = m._reset_stock_state()

    assert c1.inventory == []
    assert c2.inventory == []
    assert universe.unique_items_spawned == set()
    assert {c1, c2} <= set(containers)


def test_release_touches_only_the_claims_of_released_items():
    m, _room, universe = _merchant_in_world("Test Merchant 6")
    m.inventory = [AncientRelic(merchandise=True)]
    universe.unique_items_spawned.update({"AncientRelic", "CrystalTear"})

    m._reset_stock_state()

    assert universe.unique_items_spawned == {"CrystalTear"}


def test_reset_stock_state_room_without_universe():
    """current_room set but universe is None: nothing to release into, and
    the reset still clears the merchant without crashing."""
    m = _merchant("Test Merchant 4")
    m.inventory = [AncientRelic(merchandise=True)]
    m.current_room = DummyRoom()  # universe remains None
    assert m._reset_stock_state() == []
    assert m.inventory == []


def test_reset_stock_state_no_room_no_universe_return_value():
    """Neither room nor universe: should not crash and return empty list."""
    m = _merchant("Test Merchant 5")
    m.inventory = [AncientRelic(merchandise=True)]
    assert m._reset_stock_state() == []
    assert m.inventory == []
