import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import random
import pytest

from npc import Merchant
from items import Restorative
from shop_conditions import ShopCondition, ValueModifierCondition, RestockWeightBoostCondition, UniqueItemInjectionCondition


class DummyRoom:
    def __init__(self):
        self.objects = []
        self.universe = None

class DummyUniverse:
    def __init__(self, rooms):
        self.map = rooms


def make_merchant():
    m = Merchant(name="Tester", description="desc", damage=1, aggro=False, exp_award=0,
                 stock_count=0, always_stock=None, specialties=None, enchantment_rate=0.0)
    room = DummyRoom()
    universe = DummyUniverse([room])
    room.universe = universe
    m.current_room = room
    return m


def test_update_shop_conditions_deterministic_value_stack(monkeypatch):
    """Force _update_shop_conditions to create:
    - 3 value conditions (all targeting Restorative) with multipliers 1.5, 1.2, 0.8
    - 2 availability conditions
    - 1 unique item injection condition
    Then verify compounded value application: 100 * 1.5 * 1.2 * 0.8 = 144.
    """
    m = make_merchant()
    # Seed inventory with a Restorative having base_value
    item = Restorative(merchandise=True)
    item.base_value = 100
    m.inventory.append(item)

    # Sequence of random.random calls: 3 (value loop) + 2 (availability loop) + 1 (unique) = 6
    random_values = [0.10, 0.10, 0.10, 0.10, 0.10, 0.01]
    def fake_random():
        return random_values.pop(0) if random_values else 0.99
    monkeypatch.setattr(random, 'random', fake_random)

    # Deterministic random.randrange for value multipliers: 150%, 120%, 80%
    randrange_values = [150, 120, 80]
    def fake_randrange(start, stop=None, step=None):  # matches random.randrange signature flexibility
        return randrange_values.pop(0)
    monkeypatch.setattr(random, 'randrange', fake_randrange)

    # Deterministic random.uniform for availability weight boosts (values don't matter for this assertion)
    monkeypatch.setattr(random, 'uniform', lambda a, b: a)  # always lowest bound

    # Force all ValueModifierCondition target_class to Restorative for stacking
    monkeypatch.setattr(ShopCondition, 'random_item_base_class', staticmethod(lambda candidates=None: Restorative))

    # Execute condition update
    m._update_shop_conditions()

    # Assertions on condition counts and types
    assert len(m.shop_conditions['value']) == 3
    assert all(isinstance(c, ValueModifierCondition) for c in m.shop_conditions['value'])
    assert len(m.shop_conditions['availability']) == 2
    assert all(isinstance(c, RestockWeightBoostCondition) for c in m.shop_conditions['availability'])
    assert len(m.shop_conditions['unique']) == 1
    assert isinstance(m.shop_conditions['unique'][0], UniqueItemInjectionCondition)

    # Apply stacked value conditions
    m._apply_value_conditions()
    assert item.value == 144, f"Expected compounded value 144, got {item.value}"

    # Sanity: multipliers recorded in order
    multipliers = [c.multiplier for c in m.shop_conditions['value']]
    assert multipliers == [1.5, 1.2, 0.8]

