import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from items import AncientRelic, DragonHeartGem, unique_items_spawned
from npc import Merchant
from objects import Container

class DummyRoom:
    def __init__(self):
        self.objects = []
        self.universe = None  # will be set after universe creation

class DummyUniverse:
    def __init__(self, rooms):
        self.map = rooms


def test_unique_items_deregistered_on_reset_inventory_and_containers():
    unique_items_spawned.clear()
    m = Merchant(name="Test Merchant", description="desc", damage=1, aggro=False, exp_award=0, stock_count=0)

    # Unique item directly in merchant inventory
    relic = AncientRelic(merchandise=True)
    # Unique item inside a merchant container
    gem = DragonHeartGem(merchandise=True)

    # Register them as spawned
    unique_items_spawned.add(relic.__class__.__name__)
    unique_items_spawned.add(gem.__class__.__name__)

    m.inventory = [relic]

    # Build a fake world with a container linked to merchant
    room = DummyRoom()
    universe = DummyUniverse([room])
    room.universe = universe
    m.current_room = room

    cont = Container(name="Chest", merchant=m, items=[gem])
    room.objects.append(cont)

    assert relic.__class__.__name__ in unique_items_spawned
    assert gem.__class__.__name__ in unique_items_spawned
    assert len(cont.inventory) == 1
    assert len(m.inventory) == 1

    containers = m._reset_stock_state()

    # Both inventories cleared
    assert m.inventory == []
    assert cont.inventory == []

    # Unique classes removed from registry
    assert relic.__class__.__name__ not in unique_items_spawned
    assert gem.__class__.__name__ not in unique_items_spawned

    # Container returned
    assert cont in containers


def test_unique_items_deregistered_no_room():
    unique_items_spawned.clear()
    m = Merchant(name="Test Merchant 2", description="desc", damage=1, aggro=False, exp_award=0, stock_count=0)
    relic = AncientRelic(merchandise=True)
    unique_items_spawned.add(relic.__class__.__name__)
    m.inventory = [relic]

    returned = m._reset_stock_state()

    assert relic.__class__.__name__ not in unique_items_spawned
    assert m.inventory == []
    # No room/universe so should return empty container list
    assert returned == []


# ---------------- New Tests for Expanded _reset_stock_state Coverage ----------------
from items import CrystalTear  # placed after existing tests to avoid circular import concerns

def test_unique_items_deregistered_two_containers():
    """Merchant has two containers each with a different unique item. All should deregister and containers cleared."""
    unique_items_spawned.clear()
    m = Merchant(name="Test Merchant 3", description="desc", damage=1, aggro=False, exp_award=0, stock_count=0)
    room = DummyRoom()
    universe = DummyUniverse([room])
    room.universe = universe
    m.current_room = room
    # Create two unique items, register them manually (mirrors injection registration behavior)
    gem = DragonHeartGem(merchandise=True)
    tear = CrystalTear(merchandise=True)
    unique_items_spawned.update({gem.__class__.__name__, tear.__class__.__name__})
    c1 = Container(name="Case1", merchant=m, items=[gem])
    c2 = Container(name="Case2", merchant=m, items=[tear])
    room.objects.extend([c1, c2])
    assert gem.__class__.__name__ in unique_items_spawned
    assert tear.__class__.__name__ in unique_items_spawned
    containers = m._reset_stock_state()
    # Both inventories cleared
    assert c1.inventory == []
    assert c2.inventory == []
    # Both unique classes deregistered
    assert gem.__class__.__name__ not in unique_items_spawned
    assert tear.__class__.__name__ not in unique_items_spawned
    # Both containers returned
    returned = set(containers)
    assert c1 in returned and c2 in returned


def test_reset_stock_state_room_without_universe():
    """Exercise early return path: current_room set but universe is None. Unique items in inventory deregistered."""
    unique_items_spawned.clear()
    m = Merchant(name="Test Merchant 4", description="desc", damage=1, aggro=False, exp_award=0, stock_count=0)
    relic = AncientRelic(merchandise=True)
    unique_items_spawned.add(relic.__class__.__name__)
    m.inventory = [relic]
    m.current_room = DummyRoom()  # universe remains None
    containers = m._reset_stock_state()
    assert containers == []  # early return yields no containers
    assert relic.__class__.__name__ not in unique_items_spawned  # deregistered
    assert m.inventory == []  # cleared


def test_reset_stock_state_no_room_no_universe_return_value():
    """Explicitly test branch where neither room nor universe exists: should not crash and return empty list."""
    unique_items_spawned.clear()
    m = Merchant(name="Test Merchant 5", description="desc", damage=1, aggro=False, exp_award=0, stock_count=0)
    relic = AncientRelic(merchandise=True)
    unique_items_spawned.add(relic.__class__.__name__)
    m.inventory = [relic]
    # No current_room assigned at all
    result = m._reset_stock_state()
    assert result == []
    assert relic.__class__.__name__ not in unique_items_spawned
    assert m.inventory == []
