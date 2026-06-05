import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure both project root and src directory are on path for direct module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from npc import Merchant, MiloCurioDealer, JamboHealsU
from npc._shop import MerchantShopMixin
from items import Item, Shortsword, Restorative, Gold, Consumable
from objects import Container
from shop_conditions import ValueModifierCondition, RestockWeightBoostCondition, UniqueItemInjectionCondition

# Fakes for room/universe/player
class FakeRoom:
    def __init__(self):
        self.objects = []
        self.objects_here = []
        self.spawned = []
        self.items_here = []
        self.universe = None
    def spawn_item(self, item_type, amt=1, hidden=False, hfactor=0, merchandise=False):
        import items as items_module
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
    import items as items_module
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

def test_fill_remaining_stock_edge_cases():
    m = MockMerchant()
    
    # 1. No current room
    m._fill_remaining_stock([]) # should return immediately
    
    room = FakeRoom()
    m.current_room = room
    
    # 2. Container slots remaining check with stock_count <= 0
    cont = Container(name="Box", merchant=m)
    cont.stock_count = 0
    
    # 3. all_full returns True
    m.stock_count = 0
    m._fill_remaining_stock([cont]) # should return immediately
    
    # 4. unique_factories raises Exception
    m.stock_count = 5
    import items as items_module
    orig_factories = getattr(items_module, 'unique_item_factories', None)
    if hasattr(items_module, 'unique_item_factories'):
        del items_module.unique_item_factories
        
    try:
        # Patch inspect.getmembers to raise Exception for one candidate
        import inspect
        orig_getmembers = inspect.getmembers
        def faulty_getmembers(*args, **kwargs):
            return [("Shortsword", Shortsword), ("Faulty", "not_a_class")]
        with patch('inspect.getmembers', faulty_getmembers):
            # This will cover line 413-414, 438-439
            m._fill_remaining_stock([])
    finally:
        if orig_factories is not None:
            items_module.unique_item_factories = orig_factories
            
    # 5. Specialties list with invalid/exception prone entry
    m.specialties = ["invalid_specialty_not_a_class"] # issubclass on string will raise TypeError
    # Should handle exception and continue
    m._fill_remaining_stock([])
    
    # 6. RestockWeightBoostCondition raising exception during weight adjustment
    class FaultyCondition:
        def adjust_restock_weights(self, weight_map):
            raise Exception("Weight adjustment failed")
            
    m.shop_conditions = {"availability": [FaultyCondition()]}
    # Should handle exception and continue
    m._fill_remaining_stock([])
    
    # 7. No candidates or weight map is empty
    with patch('inspect.getmembers', lambda *args: []):
        m._fill_remaining_stock([])

def test_weighted_choice_edge_cases():
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 1
    
    # Set up weight map that sums to <= 0 or fails to choice
    # We can mock random.uniform to return a value higher than total
    with patch('random.uniform', return_value=9999.0):
        # We need candidates to exist
        m._fill_remaining_stock([])
        # If it returns None due to r > total, it exits weighted_choice loop

def test_fill_remaining_stock_eligible_containers_and_failures(monkeypatch):
    m = MockMerchant()
    room = FakeRoom()
    m.current_room = room
    m.stock_count = 1
    
    # Container with allowed_item_types raising Exception when checked
    cont = Container(name="Cabinet", merchant=m)
    cont.stock_count = 5
    cont.allowed_item_types = [object()] # isinstance(item, object()) will raise TypeError
    
    m._fill_remaining_stock([cont])
    
    # Spawn item raising Exception
    orig_spawn = room.spawn_item
    def faulty_spawn(*args, **kwargs):
        raise Exception("Failed to spawn")
    room.spawn_item = faulty_spawn
    
    m._fill_remaining_stock([])
    room.spawn_item = orig_spawn

    # Trigger line 511-512 by spawning an item where getattr/setattr value raises Exception
    import items as items_module
    class BadItem(Item):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
        @property
        def value(self):
            raise AttributeError("Value not accessible")
    
    # Register BadItem
    monkeypatch.setattr(items_module, 'BadItem', BadItem, raising=False)
    
    # Re-setup mock candidates to only return BadItem
    def fake_getmembers(module, predicate):
        return [("BadItem", BadItem)]
    monkeypatch.setattr('inspect.getmembers', fake_getmembers)
    
    # Reset room spawned and set merchant to allow spawning
    room.spawned = []
    m.stock_count = 1
    m.inventory = []
    
    # This will spawn BadItem, and try to get/set base_value, throwing Exception and catching it
    m._fill_remaining_stock([])

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

def test_merchant_verbs():
    # Test base Merchant verb methods (talk, trade, buy, sell)
    m = Merchant(name="BaseMerchant", description="desc", damage=1, aggro=False, exp_award=0, stock_count=5)
    player = FakePlayer()
    
    # Verify talk prints something
    with patch('builtins.print') as mock_print:
        m.talk(player)
        mock_print.assert_called_with("BaseMerchant has nothing to say.")
        
    # Verify trade / buy / sell call shop interface or collect
    m.shop = MagicMock()
    m.trade(player)
    assert m.shop.run.called
    
    m.shop.reset_mock()
    m.buy(player)
    assert m.shop.run.called
    
    m.shop.reset_mock()
    m.sell(player)
    assert m.shop.run.called

def test_milo_verbs():
    # Test MiloCurioDealer talk/trade
    milo = MiloCurioDealer()
    player = FakePlayer()
    
    with patch('builtins.print') as mock_print:
        milo.talk(player)
        mock_print.assert_any_call("Milo grins: 'Looking for something rare, friend? I've got just the thing!'")
        
    with patch('interface.ShopInterface') as mock_shop_cls:
        mock_shop = MagicMock()
        mock_shop_cls.return_value = mock_shop
        milo.trade(player)
        assert mock_shop.run.called

def test_jambo_verbs():
    # Test JamboHealsU initialize_shop, trade
    jambo = JamboHealsU()
    player = FakePlayer()
    
    # Test shop import fails in JamboHealsU and inventory is None (line 227)
    import sys
    orig_interface = sys.modules.get('interface')
    sys.modules['interface'] = None
    try:
        jambo.inventory = None
        jambo.initialize_shop()
        assert jambo.shop is None
        assert jambo.inventory == []
    finally:
        sys.modules['interface'] = orig_interface
        
    # Test Jambo trade
    with patch('interface.ShopInterface') as mock_shop_cls:
        mock_shop = MagicMock()
        mock_shop_cls.return_value = mock_shop
        jambo.trade(player)
        assert mock_shop.run.called
        assert mock_shop.exit_message is not None
