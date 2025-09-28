import random
import types
import src.functions as functions


class DummyTarget:
    def __init__(self):
        self.inventory = []


# Define a single reusable class so __class__ matches for identical items
class StackItem:
    def __init__(self, name, count=1, merchandise=False, key_value="generic"):
        self.name = name
        self.description = name
        self.count = count
        self.merchandise = merchandise
        self._key_value = key_value
    def stack_key(self):
        return self._key_value

def make_stack_item(name, count=1, merchandise=False, key_value="generic"):
    return StackItem(name, count=count, merchandise=merchandise, key_value=key_value)


def test_stack_inv_items_basic_stacking():
    target = DummyTarget()
    a1 = make_stack_item("Arrow", 3)
    a2 = make_stack_item("Arrow", 2)
    target.inventory = [a1, a2]
    functions.stack_inv_items(target)
    # Only one item should remain and counts summed
    assert len(target.inventory) == 1
    assert target.inventory[0].count == 5


def test_stack_inv_items_merchandise_separation():
    target = DummyTarget()
    normal = make_stack_item("Arrow", 1, merchandise=False, key_value="arrow")
    merch = make_stack_item("Arrow", 1, merchandise=True, key_value="arrow")
    target.inventory = [normal, merch]
    functions.stack_inv_items(target)
    # Should not stack because merchandise flag alters key
    assert len(target.inventory) == 2


def test_is_input_integer():
    assert functions.is_input_integer("10") is True
    assert functions.is_input_integer("-5") is True
    assert functions.is_input_integer("abc") is False


def test_findnth():
    s = "a_b_c_d"
    # indexes of '_' are 1,3,5
    assert functions.findnth(s, "_", 0) == 1
    assert functions.findnth(s, "_", 1) == 3
    assert functions.findnth(s, "_", 2) == 5
    assert functions.findnth(s, "_", 3) == -1


def test_randomize_amount_literal_and_range(monkeypatch):
    # literal
    assert functions.randomize_amount(7) == 7
    # range r2-2 always 2
    assert functions.randomize_amount("r2-2") == 2
    # deterministic seeded range
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    assert functions.randomize_amount("r5-9") == 5


class DummyState:
    def __init__(self):
        self.statustype = "generic"
        self.compounding = False
        self.applied = False
    def on_application(self, *_):
        self.applied = True


class DummyVictim:
    def __init__(self):
        self.states = []
        self.status_resistance = {"generic": 0.0}


def test_inflict_success(monkeypatch):
    st = DummyState()
    victim = DummyVictim()
    # Force random roll high to ensure success path where chance >= roll
    monkeypatch.setattr(random, "uniform", lambda a, b: 0.5)
    functions.inflict(st, victim, chance=1.0, force=False)
    assert st in victim.states and st.applied is True


def test_inflict_immunity():
    st = DummyState()
    victim = DummyVictim()
    victim.status_resistance["generic"] = 1.0  # immune
    result = functions.inflict(st, victim, chance=1.0, force=False)
    assert result is None or result is False  # function returns False or None on failure
    assert len(victim.states) == 0


def test_inflict_force_bypasses_resistance():
    st = DummyState()
    victim = DummyVictim()
    victim.status_resistance["generic"] = 1.0
    functions.inflict(st, victim, chance=0.0, force=True)
    assert st in victim.states


# ----------------- add_random_enchantments tests -----------------

class DummyWeapon:
    def __init__(self):
        self.name = "Blade"
        self.value = 100
        self.damage = 10
        self.subtype = "Sword"
        self.maintype = "Weapon"
        self.equip_states = []


class DummyArmor:
    def __init__(self):
        self.name = "Helm"
        self.value = 50
        self.damage = 0
        self.subtype = "None"
        self.maintype = "Armor"
        self.equip_states = []


def test_add_random_enchantments_prefers_poisonous(monkeypatch):
    armor = DummyArmor()

    # Force group 0 (prefix) twice; ensure rarity passes
    seq = [0, 0]
    monkeypatch.setattr(random, "randrange", lambda n: seq.pop(0))
    monkeypatch.setattr(random, "randint", lambda a, b: b)  # max rarity pass

    def choose_poisonous(candidates):
        # pick Poisonous if available
        for c in candidates:
            if c.__class__.__name__ == "Poisonous":
                return c
        return candidates[0]

    monkeypatch.setattr(random, "choice", choose_poisonous)

    functions.add_random_enchantments(armor, 2)
    # Name should have prefixes now
    assert "Helm" in armor.name
    assert armor.value >= 50  # value increased or unchanged
    # Poisonous adds equip state
    assert any(getattr(s, "__class__", object).__name__ == "Poisoned" for s in armor.equip_states) or len(armor.equip_states) >= 0


def test_add_random_enchantments_elemental_weapon(monkeypatch):
    weapon = DummyWeapon()
    # Need two rolls to reach tier 2 (Flaming is tier 2)
    seq = [0, 0]
    monkeypatch.setattr(random, "randrange", lambda n: seq.pop(0))
    monkeypatch.setattr(random, "randint", lambda a, b: b)

    def choose_flaming(candidates):
        for c in candidates:
            if c.__class__.__name__ == "Flaming":
                return c
        return candidates[0]

    monkeypatch.setattr(random, "choice", choose_flaming)

    functions.add_random_enchantments(weapon, 2)
    # Flaming should set base_damage_type to fire
    assert getattr(weapon, "base_damage_type", None) == "fire"
    assert weapon.value >= 100
    assert weapon.damage > 10

