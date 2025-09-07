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

    m._reset_stock_state()

    assert relic.__class__.__name__ not in unique_items_spawned
    assert m.inventory == []

