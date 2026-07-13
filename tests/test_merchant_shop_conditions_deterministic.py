import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import random
import pytest

from src.npc import Merchant
from src.items import Restorative
from src.shop_conditions import ShopCondition, ValueModifierCondition, RestockWeightBoostCondition, UniqueItemInjectionCondition


class DummyRoom:
    def __init__(self):
        self.objects = []
        self.universe = None

    def spawn_item(self, item_type, amt=1, hidden=False, hfactor=0, merchandise=False):
        import src.items as items_module
        cls = getattr(items_module, item_type, None)
        if cls is None:
            return None
        return cls(merchandise=merchandise)

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


def test_restock_weight_boost_exercised_end_to_end_via_update_goods(monkeypatch):
    """Confirm RestockWeightBoostCondition.adjust_restock_weights is actually invoked by
    the live restock path (update_goods -> _fill_remaining_stock), not just callable in
    isolation, and that its boost measurably skews which class gets stocked.

    A condition instance produced the normal way (no explicit target_class, so it goes
    through random_item_base_class like _update_shop_conditions really constructs it)
    is injected in place of the dice roll, then update_goods() is run unmodified end to
    end: reset -> fill -> value/unique application -> gold. The spy subclass records the
    weight_map it receives from the real merchant fill loop to prove the wiring, and a
    heavily skewed weight is used to make the resulting stock deterministic.
    """
    m = make_merchant()
    m.stock_count = 1
    m.specialties = []
    m.always_stock = None

    captured = {}

    class SpyCondition(RestockWeightBoostCondition):
        def adjust_restock_weights(self, weight_map):
            super().adjust_restock_weights(weight_map)
            captured['weight_map'] = dict(weight_map)

    # target_class left unset so the constructor exercises random_item_base_class,
    # exactly as _update_shop_conditions does; pin its result to Restorative here.
    monkeypatch.setattr(ShopCondition, 'random_item_base_class', staticmethod(lambda candidates=None: Restorative))
    cond = SpyCondition(weight_multiplier=1000.0)
    assert cond.target_class is Restorative

    # Bypass the dice roll (already covered by the value-stack test above) and inject
    # the boosted condition directly into the slot _fill_remaining_stock reads from.
    monkeypatch.setattr(
        m, '_update_shop_conditions',
        lambda: setattr(m, 'shop_conditions', {'value': [], 'availability': [cond], 'unique': []}),
    )

    # Pick the midpoint of the weighted range: Restorative's 1000x boost dwarfs every
    # other candidate's baseline weight of 1.0, so its slice covers the vast majority
    # of the cumulative range regardless of dict iteration order.
    monkeypatch.setattr(random, 'uniform', lambda a, b: b * 0.5)

    m.update_goods()

    assert 'weight_map' in captured, "adjust_restock_weights was never invoked by update_goods()'s restock path"
    assert captured['weight_map'][Restorative] == pytest.approx(1000.0)

    non_gold = [i for i in m.inventory if getattr(i, 'name', None) != 'Gold']
    assert len(non_gold) == 1
    assert isinstance(non_gold[0], Restorative), (
        f"Expected the weight-boosted class to be stocked, got {type(non_gold[0])}"
    )
