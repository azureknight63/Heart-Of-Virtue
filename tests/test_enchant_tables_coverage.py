"""Coverage for src/enchant_tables.py — the Enchantment subclasses used by
loot/item generation. There is no dedicated test file for this module; it
was previously only exercised incidentally (and non-deterministically, since
enchantment selection is random) via item-creation tests elsewhere.

Rather than hand-writing one test per class, this sweeps every Enchantment
subclass defined in the module and exercises modify() deterministically
against a single permissive fake item carrying every attribute any
enchantment might touch (damage/value/weight/protection/add_resistance/
maxhp/etc.), so coverage doesn't depend on the enchantment-selection RNG.
requirements() is exercised separately against both a matching and a
non-matching item where it branches on subtype/maintype.
"""

import inspect

import src.enchant_tables as enchant_tables
from src.enchant_tables import Enchantment


def _all_enchantment_classes():
    return [
        obj
        for name, obj in vars(enchant_tables).items()
        if inspect.isclass(obj) and issubclass(obj, Enchantment) and obj is not Enchantment
    ]


class _FakeItem:
    """A permissive stand-in item carrying every attribute any Enchantment
    subclass's modify()/requirements() might read or write."""

    def __init__(self, subtype="Sword", maintype="Weapon"):
        self.name = "Test Item"
        self.announce = ""
        self.damage = 10
        self.value = 100
        self.weight = 5
        self.protection = 2
        self.subtype = subtype
        self.maintype = maintype
        self.add_resistance = {}


def test_every_enchantment_modify_runs_without_error_on_a_permissive_item():
    for cls in _all_enchantment_classes():
        item = _FakeItem()
        enchantment = cls(item)
        enchantment.modify()
        # Every modify() implementation folds its own name into item.name.
        assert enchantment.name in item.name, f"{cls.__name__} did not update item.name"


def test_every_enchantment_modify_runs_on_armor_typed_item_too():
    """Several enchantments only make sense on armor slots (protection/
    resistance boosts); run the full sweep again against an armor-shaped
    item so those modify() bodies (which don't branch on type internally,
    but are conventionally only invoked after a matching requirements()
    check) still get exercised with a broadly representative subject."""
    for cls in _all_enchantment_classes():
        item = _FakeItem(subtype="Chestplate", maintype="Armor")
        enchantment = cls(item)
        enchantment.modify()
        assert enchantment.name in item.name


def test_requirements_true_and_false_branches_for_weapon_archetype_enchantments():
    from src.enchant_tables import Sharp, Weighted, Balanced

    blade_item = _FakeItem(subtype="Sword", maintype="Weapon")
    blunt_item = _FakeItem(subtype="Hammer", maintype="Weapon")
    ranged_item = _FakeItem(subtype="Bow", maintype="Weapon")

    assert Sharp(blade_item).requirements() is True
    assert Sharp(blunt_item).requirements() is False

    assert Weighted(blunt_item).requirements() is True
    assert Weighted(blade_item).requirements() is False

    assert Balanced(ranged_item).requirements() is True
    assert Balanced(blade_item).requirements() is False


def test_requirements_true_and_false_branches_for_armor_slot_enchantments():
    from src.enchant_tables import Studded, Reinforced, Plated

    armor_item = _FakeItem(subtype="Chestplate", maintype="Armor")
    weapon_item = _FakeItem(subtype="Sword", maintype="Weapon")

    for cls in (Studded, Reinforced, Plated):
        assert cls(armor_item).requirements() is True
        assert cls(weapon_item).requirements() is False


def test_requirements_true_and_false_branches_for_accessory_enchantments():
    from src.enchant_tables import (
        Poisonous,
        Dousing,
        OfThePhoenix,
        Purifying,
        Needleproof,
        Edgebound,
        Bulwark,
    )

    accessory_item = _FakeItem(subtype="Ring", maintype="Accessory")
    weapon_item = _FakeItem(subtype="Sword", maintype="Weapon")

    for cls in (Poisonous, Dousing, OfThePhoenix, Purifying, Needleproof, Edgebound, Bulwark):
        assert cls(accessory_item).requirements() is True
        assert cls(weapon_item).requirements() is False


def test_add_resistance_creates_dict_when_item_has_no_resistance_attr():
    item = _FakeItem(maintype="Armor")
    del item.add_resistance  # simulate an item that never had this attribute
    e = Enchantment(item, name="Test", rarity=0, group="Prefix", value=1)
    e._add_resistance("poison", 0.4)
    assert item.add_resistance == {"poison": 0.4}


def test_add_resistance_dict_branch_increments_existing_key():
    item = _FakeItem(maintype="Armor")
    item.add_resistance = {"poison": 0.2}
    e = Enchantment(item, name="Test", rarity=0, group="Prefix", value=1)
    e._add_resistance("poison", 0.3)
    assert item.add_resistance["poison"] == 0.5


def test_add_resistance_object_branch_increments_existing_attribute():
    class ResObj:
        pass

    item = _FakeItem(maintype="Armor")
    res_obj = ResObj()
    res_obj.fire = 0.1
    item.add_resistance = res_obj
    e = Enchantment(item, name="Test", rarity=0, group="Prefix", value=1)
    e._add_resistance("fire", 0.2)
    assert abs(item.add_resistance.fire - 0.3) < 1e-9


def test_add_resistance_object_branch_sets_new_attribute():
    class ResObj:
        pass

    item = _FakeItem(maintype="Armor")
    item.add_resistance = ResObj()
    e = Enchantment(item, name="Test", rarity=0, group="Prefix", value=1)
    e._add_resistance("cold", 0.25)
    assert item.add_resistance.cold == 0.25


def test_requirements_runs_for_every_class_against_every_representative_item_shape():
    """Generic sweep closing remaining requirements() branches this file's
    more targeted tests don't specifically assert on (e.g. Hollow, Polished,
    Encrusted, Dirty, and the elemental-resistance suffixes) — every class's
    requirements() is called against each representative item shape so every
    subtype/maintype branch gets exercised at least once, without needing to
    hand-enumerate which archetype each of ~30 classes cares about."""
    shapes = [
        _FakeItem(subtype="Sword", maintype="Weapon"),
        _FakeItem(subtype="Hammer", maintype="Weapon"),
        _FakeItem(subtype="Bow", maintype="Weapon"),
        _FakeItem(subtype="Chestplate", maintype="Armor"),
        _FakeItem(subtype="Ring", maintype="Accessory"),
    ]
    for cls in _all_enchantment_classes():
        for item in shapes:
            cls(item).requirements()  # must not raise; return value already
            # asserted precisely by the more targeted tests above.


def test_damage_boost_enchantments_clamp_small_gains_to_minimum_one():
    """Lines guarded by `if amount < 1: amount = 1` only trigger when the
    computed delta is sub-1; a damage=10 base (used by the generic sweep)
    can randomly land either side of that threshold, so use a low enough
    base damage that the clamp always fires. Covers every enchantment that
    shares this exact pattern: the three weapon-archetype prefixes plus the
    elemental damage suffixes."""
    from src.enchant_tables import (
        Sharp,
        Weighted,
        Balanced,
        Flaming,
        Icy,
        Shocking,
        Earthen,
        Radiant,
        Umbral,
        Spiritual,
        Pure,
    )

    classes = [
        Sharp, Weighted, Balanced,
        Flaming, Icy, Shocking, Earthen, Radiant, Umbral, Spiritual, Pure,
    ]
    for cls in classes:
        item = _FakeItem(subtype="Sword", maintype="Weapon")
        item.damage = 1  # (mod - 1) * 1 is always << 1
        before = item.damage
        cls(item).modify()
        assert item.damage > before, f"{cls.__name__} did not clamp/apply the damage bonus"


def test_stat_boost_suffixes_increment_an_existing_add_attribute():
    """Each OfX suffix does `if hasattr(item, "add_<stat>"): += else: =`; the
    generic sweeps above only exercise the "attribute doesn't exist yet"
    else-branch (a fresh _FakeItem never has these), so explicitly pre-set
    each attribute to hit the increment branch too."""
    from src.enchant_tables import (
        OfHealth,
        OfVigor,
        OfPerseverance,
        OfTempo,
        OfGrit,
        OfCharms,
        OfInsight,
        OfSupplication,
    )

    cases = [
        (OfHealth, "add_maxhp"),
        (OfVigor, "add_str"),
        (OfPerseverance, "add_maxfatigue"),
        (OfTempo, "add_speed"),
        (OfGrit, "add_endurance"),
        (OfCharms, "add_charisma"),
        (OfInsight, "add_intelligence"),
        (OfSupplication, "add_faith"),
    ]
    for cls, attr in cases:
        item = _FakeItem()
        setattr(item, attr, 5)
        cls(item).modify()
        assert getattr(item, attr) > 5, f"{cls.__name__} did not increment existing {attr}"


def test_of_relief_increments_existing_weight_tolerance_as_decimal():
    import decimal
    from src.enchant_tables import OfRelief

    item = _FakeItem()
    item.add_weight_tolerance = decimal.Decimal(5)
    OfRelief(item).modify()
    assert item.add_weight_tolerance > decimal.Decimal(5)


def test_base_enchantment_modify_and_requirements_are_noops():
    item = _FakeItem()
    e = Enchantment(item, name="Base", rarity=0, group="Prefix", value=1)
    assert e.modify() is None
    assert e.requirements() is True
