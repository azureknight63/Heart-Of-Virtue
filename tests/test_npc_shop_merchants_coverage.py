import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure both project root and src directory are on path for direct module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.npc import Merchant, MiloCurioDealer, JamboHealsU
from src.npc._shop import MerchantShopMixin
from src.items import Item, Shortsword, Restorative, Gold, Consumable
from src.objects import Container
from src.shop_conditions import ValueModifierCondition, RestockWeightBoostCondition, UniqueItemInjectionCondition

# Fakes for room/universe/player
class FakeRoom:
    def __init__(self):
        self.objects = []
        self.objects_here = []
        self.spawned = []
        self.items_here = []
        self.universe = None
    def spawn_item(self, item_type, amt=1, hidden=False, hfactor=0, merchandise=False):
        import src.items as items_module
        cls = getattr(items_module, item_type, None)
        if cls is None:
            return None
        item = cls(merchandise=merchandise)
        if not hasattr(item, 'base_value'):
            setattr(item, 'base_value', getattr(item, 'value', 1))
        self.spawned.append(item)
        return item

class FakeUniverse:
    def __init__(self, rooms):
        self.map = rooms

class FakePlayer:
    def __init__(self):
        self.inventory = []

# Concrete test class for testing MerchantShopMixin directly
class MockMerchant(MerchantShopMixin):
    def __init__(self):
        self.name = "TestMerchant"
        self.inventory = []
        self.stock_count = 5
        self.always_stock = None
        self.specialties = []
        self.enchantment_rate = 1.0
        self.base_gold = 300
        self.shop_conditions = {"value": [], "availability": [], "unique": []}
        self.shop = None
        self.current_room = None

def test_collect_player_merchandise_edge_cases():
    m = MockMerchant()
    player = FakePlayer()
    
    # 1. player has no inventory
    assert m._collect_player_merchandise(None) == []
    
    # 2. ValueError when removing from player inventory, and self.inventory is None
    item = Restorative(merchandise=True)
    
    # Use a custom list subclass to raise ValueError on remove
    class FaultyList(list):
        def remove(self, x):
            raise ValueError("Simulated remove error")
            
    player.inventory = FaultyList([item])
    m.inventory = None
    
    msgs = m._collect_player_merchandise(player, silent=True)
    assert msgs == []
    assert m.inventory is None
    
    # Restore standard list
    player.inventory = [item]
    m.inventory = []
    
    # 3. self.inventory is None but remove succeeds
    m.inventory = None
    msgs = m._collect_player_merchandise(player, silent=True)
    assert len(msgs) == 1
    assert m.inventory == [item]

    # 4. silent=False path with print and sleep
    player.inventory = [Restorative(merchandise=True)]
    m.inventory = []
    with patch('builtins.print') as mock_print, patch('time.sleep') as mock_sleep:
        msgs = m._collect_player_merchandise(player, silent=False)
        assert len(msgs) == 1
        assert mock_print.called
        assert mock_sleep.called

def test_initialize_shop_import_fails():
    m = MockMerchant()
    m.inventory = None
    
    # Temporarily hide interface from sys.modules to raise import exception
    import sys
    orig_interface = sys.modules.get('interface')
    sys.modules['interface'] = None
    try:
        m.initialize_shop()
        assert m.inventory == []
        assert m.shop is None
    finally:
        if orig_interface:
            sys.modules['interface'] = orig_interface
        else:
            sys.modules.pop('interface', None)

def test_remove_placed_item_from_room_exception():
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    
    item = Shortsword()
    # Mock room.items_here to support contains but raise error on remove
    class FaultyList(list):
        def remove(self, x):
            raise Exception("Simulated list remove failure")
    
    faulty_list = FaultyList([item])
    room.items_here = faulty_list
    
    # Should handle exception gracefully
    m._remove_placed_item_from_room(item)
    assert item in faulty_list

def test_reset_stock_state_edge_cases():
    m = MockMerchant()
    
    # 1. No current room
    m.inventory = [Shortsword(merchandise=True)]
    m.inventory[0].unique = True
    import src.items as items_module
    items_module.unique_items_spawned.add('Shortsword')
    
    containers = m._reset_stock_state()
    assert containers == []
    assert m.inventory == []
    assert 'Shortsword' not in items_module.unique_items_spawned
    
    # 2. current_room is present but resolve_rooms_source returns None
    room = FakeRoom()
    m.current_room = room
    # room has no map and room.universe is None, so resolve_rooms_source returns None
    m.inventory = [Shortsword(merchandise=True)]
    m.inventory[0].unique = True
    items_module.unique_items_spawned.add('Shortsword')
    
    containers = m._reset_stock_state()
    assert containers == []
    assert m.inventory == []
    assert 'Shortsword' not in items_module.unique_items_spawned
    
    # 3. room_items list remove throws exception & isinstance(room, str) check (L288)
    uni = FakeUniverse([room, "string_room_to_trigger_L288"])
    room.universe = uni
    
    class FaultyList(list):
        def remove(self, x):
            raise Exception("Cannot remove")
            
    item = Shortsword(merchandise=True)
    room.items_here = FaultyList([item])
    
    # should run and not crash
    containers = m._reset_stock_state()
    assert item in room.items_here

def test_create_always_stock_item_edge_cases():
    m = MockMerchant()
    
    # 1. Invalid item spec with no __name__
    assert m._create_always_stock_item(object()) is None
    
    # 2. Spec with no current room
    assert m._create_always_stock_item(Restorative) is None
    
    # 3. Spec with count > 1
    room = FakeRoom()
    m.current_room = room
    
    class RestorativeSpec:
        count = 5
    RestorativeSpec.__name__ = 'Restorative'
        
    created = m._create_always_stock_item(RestorativeSpec)
    assert created is not None
    assert created.count == 5

def test_place_item_no_acceptable_containers():
    m = MockMerchant()
    # Container with no allowed_item_types
    cont = Container(name="Box", merchant=m)
    if hasattr(cont, 'allowed_item_types'):
        del cont.allowed_item_types
    
    assert m._place_item(Shortsword(), [cont]) is False

# ---------------------------------------------------------------------------
# _fill_remaining_stock — restock guards and failure isolation
#
# The three tests replaced here (``..._edge_cases``, ``test_weighted_choice_
# edge_cases``, ``..._eligible_containers_and_failures``) contained **no
# assertion at all**: each one walked ``_fill_remaining_stock`` through a
# sequence of exception-swallowing branches and ended. They executed the lines
# — which is why they existed — but they could not distinguish "the branch was
# handled" from "the branch silently dropped every item on the floor", and a
# ``_fill_remaining_stock`` rewritten as ``def _fill_remaining_stock(self, c):
# return`` would have passed all three.
#
# Each guard now asserts the state that guard exists to protect.
# ---------------------------------------------------------------------------


def test_restock_without_a_room_stocks_nothing():
    """Guard 1: ``if not self.current_room: return``. There is nowhere to spawn
    items from, so the inventory must be left empty rather than half-built."""
    m = MockMerchant()
    m.current_room = None
    m.stock_count = 5

    m._fill_remaining_stock([])

    assert m.inventory == []


def test_restock_stops_once_the_merchant_and_containers_are_full():
    """Guard 2: ``all_full()``. A merchant with ``stock_count == 0`` has no
    slots; a zero-capacity container has none either, so nothing spawns."""
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 0
    cont = Container(name="Box", merchant=m)
    cont.stock_count = 0

    m._fill_remaining_stock([cont])

    assert m.inventory == []
    assert cont.inventory == []
    assert room.spawned == []


def test_restock_fills_the_merchant_to_exactly_its_stock_count():
    """The happy path none of the three original tests covered: the loop must
    terminate at the cap, not under- or over-fill it."""
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 4
    m.inventory = []

    m._fill_remaining_stock([])

    assert len(m.inventory) == 4
    assert all(isinstance(i, Item) for i in m.inventory)
    assert all(i.merchandise for i in m.inventory)
    # Everything placed is removed from the room floor.
    assert room.items_here == []


def test_restock_never_stocks_a_disallowed_class():
    """``disallowed_classes`` is the guard that keeps Gold, Relic and the bare
    equipment base classes out of shop stock — a Relic on a shelf would sell
    for nothing and break a story item."""
    from src.items import Gold, Relic

    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 30
    m.inventory = []

    m._fill_remaining_stock([])

    banned = {Gold, Relic, Consumable, Item}
    assert not [i for i in m.inventory if type(i) in banned]


def test_a_missing_unique_item_registry_does_not_stop_the_restock():
    """``items.unique_item_factories`` missing raises inside the ``try``; the
    fallback is an empty exclusion set, not an aborted restock."""
    import src.items as items_module

    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 3

    saved = getattr(items_module, "unique_item_factories", None)
    if hasattr(items_module, "unique_item_factories"):
        del items_module.unique_item_factories
    try:
        m._fill_remaining_stock([])
    finally:
        if saved is not None:
            items_module.unique_item_factories = saved

    assert len(m.inventory) == 3


def test_a_non_class_member_of_the_items_module_is_skipped_not_fatal():
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 2

    with patch("inspect.getmembers", lambda *a, **k: [
        ("Shortsword", Shortsword), ("Faulty", "not_a_class")
    ]):
        m._fill_remaining_stock([])

    assert len(m.inventory) == 2
    assert all(isinstance(i, Shortsword) for i in m.inventory)


def test_no_candidate_classes_at_all_means_no_stock_and_no_crash():
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 3

    with patch("inspect.getmembers", lambda *a, **k: []):
        m._fill_remaining_stock([])

    assert m.inventory == []
    assert room.spawned == []


def test_a_junk_specialty_entry_is_ignored_without_losing_the_restock():
    """``issubclass("string", Item)`` raises TypeError inside the specialty
    loop. The entry is skipped; stocking continues at base weight."""
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 2
    m.specialties = ["invalid_specialty_not_a_class"]

    m._fill_remaining_stock([])

    assert len(m.inventory) == 2


def test_a_specialty_class_is_weighted_three_times_a_plain_candidate():
    """The documented 3x specialty weight — previously unasserted anywhere."""
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 1
    m.specialties = [Shortsword]

    captured = {}

    def capture_uniform(low, high):
        captured["total"] = high
        return 0.0

    with patch("inspect.getmembers", lambda *a, **k: [
        ("Shortsword", Shortsword), ("Restorative", Restorative)
    ]):
        with patch("random.uniform", capture_uniform):
            m._fill_remaining_stock([])

    # Shortsword (specialty, 3.0) + Restorative (plain, 1.0)
    assert captured["total"] == 4.0


def test_a_condition_that_raises_while_reweighting_is_skipped():
    """A broken shop condition must not deprive the merchant of stock."""
    class FaultyCondition:
        def adjust_restock_weights(self, weight_map):
            raise RuntimeError("Weight adjustment failed")

    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 3
    m.shop_conditions = {"availability": [FaultyCondition()]}

    m._fill_remaining_stock([])

    assert len(m.inventory) == 3


def test_a_condition_that_zeroes_every_weight_stops_the_restock_cleanly():
    """``weight_map`` filtered to ``w > 0`` and then empty -> early return."""
    class ZeroingCondition:
        def adjust_restock_weights(self, weight_map):
            for cls in list(weight_map):
                weight_map[cls] = 0.0

    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 3
    m.shop_conditions = {"availability": [ZeroingCondition()]}

    m._fill_remaining_stock([])

    assert m.inventory == []


def test_a_roll_past_the_end_of_the_weight_map_ends_the_loop():
    """``weighted_choice`` returns None when the roll exceeds the accumulated
    total; the loop must ``break`` rather than spin to the 1000 safety cap."""
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 5

    with patch("random.uniform", return_value=9999.0) as roll:
        m._fill_remaining_stock([])

    assert m.inventory == []
    assert roll.call_count == 1


def test_a_container_whose_allowed_types_are_junk_is_skipped_for_the_merchant():
    """``isinstance(item, object())`` raises TypeError. The container is
    treated as ineligible and the item goes to the merchant instead of being
    lost."""
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 2
    cont = Container(name="Cabinet", merchant=m)
    cont.stock_count = 5
    cont.allowed_item_types = [object()]

    m._fill_remaining_stock([cont])

    assert cont.inventory == []
    assert len(m.inventory) == 2


def test_items_route_into_an_eligible_container_ahead_of_the_merchant():
    """The placement preference the container guard above is the negative of."""
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 5
    cont = Container(name="Cabinet", merchant=m)
    cont.stock_count = 3
    cont.allowed_item_types = [Shortsword]

    with patch("inspect.getmembers", lambda *a, **k: [("Shortsword", Shortsword)]):
        m._fill_remaining_stock([cont])

    assert len(cont.inventory) == 3
    assert all(isinstance(i, Shortsword) for i in cont.inventory)


def test_a_room_that_cannot_spawn_stocks_nothing_and_does_not_hang():
    """``spawn_item`` raising is caught per-iteration; with every spawn failing
    the loop must still terminate (via the 1000-iteration safety cap) and leave
    the inventory empty rather than partially populated."""
    m = MockMerchant()
    room = FakeRoom()

    def faulty_spawn(*args, **kwargs):
        raise RuntimeError("Failed to spawn")

    room.spawn_item = faulty_spawn
    m.current_room = room
    m.stock_count = 2

    m._fill_remaining_stock([])

    assert m.inventory == []


def test_an_item_whose_value_raises_is_still_stocked_without_a_base_value(monkeypatch):
    """``setattr(spawned, "base_value", spawned.value)`` raises for an item
    with a broken ``value`` property. The item must still reach the shelf —
    ``_apply_value_conditions`` separately tolerates a missing base_value."""
    import src.items as items_module

    class BadItem(Item):
        def __init__(self, merchandise=False):
            super().__init__(
                name="Bad Item",
                description="An item whose value cannot be read.",
                value=1,
                maintype="Misc",
                subtype="Misc",
                discovery_message="a broken thing.",
                merchandise=merchandise,
            )
            # Shadow the instance attribute the base class just set with a
            # property that raises, and drop base_value so the setattr path runs.
            type(self).value = property(BadItem._raise_value)
            if hasattr(self, "base_value"):
                del self.base_value

        @staticmethod
        def _raise_value(self):
            raise AttributeError("Value not accessible")

    monkeypatch.setattr(items_module, "BadItem", BadItem, raising=False)
    monkeypatch.setattr("inspect.getmembers", lambda *a, **k: [("BadItem", BadItem)])

    m = MockMerchant()
    room = FakeRoom()
    room.spawn_item = lambda item_type, **kw: BadItem(merchandise=kw.get("merchandise", False))
    m.current_room = room
    m.stock_count = 1
    m.inventory = []

    m._fill_remaining_stock([])

    assert len(m.inventory) == 1
    assert isinstance(m.inventory[0], BadItem)
    assert not hasattr(m.inventory[0], "base_value")


def test_apply_value_conditions_edge_cases():
    m = MockMerchant()
    
    # 1. Item without base_value
    item = Shortsword()
    if hasattr(item, 'base_value'):
        del item.base_value
    m.inventory = [item]
    
    class DummyCondition:
        def apply_to_price(self, *args):
            return 10
            
    m.shop_conditions = {"value": [DummyCondition()]}
    m._apply_value_conditions() # should return immediately on line 548
    
    # 2. TypeError on apply_to_price (fallback to 1-arg)
    item.base_value = 100
    
    class FallbackCondition:
        def apply_to_price(self, val, other=None):
            if other is not None:
                raise TypeError("Custom error")
            return val * 2
            
    m.shop_conditions = {"value": [FallbackCondition()]}
    m._apply_value_conditions()
    assert item.value == 200

def _merchandise(name):
    goods = MagicMock()
    goods.merchandise = True
    goods.name = name
    return goods


def test_merchant_verbs():
    # Test base Merchant verb methods (talk, trade, buy, sell)
    m = Merchant(name="BaseMerchant", description="desc", damage=1, aggro=False, exp_award=0, stock_count=5)
    player = FakePlayer()

    # talk narrates a flavor line without error
    m.talk(player)

    # Pricing lives on the merchant now (ShopInterface removed)
    assert m.buy_modifier == 1.0
    assert m.sell_modifier == 0.5
    assert m.shop_name == "BaseMerchant's Shop"

    # trade absorbs any merchandise Jean carries; no terminal UI is launched
    goods = _merchandise("Trinket")
    player.inventory = [goods]
    m.inventory = []
    m.trade(player)
    assert goods in m.inventory
    assert goods not in player.inventory

    # buy/sell delegate to trade and stay safe on an empty inventory
    m.buy(player)
    m.sell(player)


def test_milo_verbs():
    # Test MiloCurioDealer talk/trade
    milo = MiloCurioDealer()
    player = FakePlayer()

    milo.talk(player)
    assert milo.shop_name == "The Wandering Curiosities Shop"

    goods = _merchandise("Curio")
    player.inventory = [goods]
    milo.inventory = []
    milo.trade(player)
    assert goods in milo.inventory


def test_jambo_verbs():
    # Test JamboHealsU pricing + trade
    jambo = JamboHealsU()
    player = FakePlayer()

    assert jambo.buy_modifier == 1.0
    assert jambo.sell_modifier == 0.5
    assert jambo.shop_name == "Jambo Heals U"

    goods = _merchandise("Potion")
    player.inventory = [goods]
    jambo.inventory = []
    jambo.trade(player)
    assert goods in jambo.inventory
