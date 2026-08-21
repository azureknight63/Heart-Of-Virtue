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

import pytest

import src.enchant_tables as enchant_tables
from src.enchant_tables import Enchantment


def _all_enchantment_classes():
    return [
        obj
        for name, obj in vars(enchant_tables).items()
        if inspect.isclass(obj)
        and issubclass(obj, Enchantment)
        and obj is not Enchantment
        # Exclude internal shared-logic base classes (e.g.
        # _DamagePercentBoostEnchantment, added for #424) that don't define
        # their own __init__ and therefore aren't independently constructible
        # concrete enchantments the way every real subclass below is.
        and "__init__" in vars(obj)
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
    e = Enchantment(item, name="Test", group="Prefix", value=1)
    e._add_resistance("poison", 0.4)
    assert item.add_resistance == {"poison": 0.4}


def test_add_resistance_dict_branch_increments_existing_key():
    item = _FakeItem(maintype="Armor")
    item.add_resistance = {"poison": 0.2}
    e = Enchantment(item, name="Test", group="Prefix", value=1)
    e._add_resistance("poison", 0.3)
    assert item.add_resistance["poison"] == 0.5


def test_add_resistance_object_branch_increments_existing_attribute():
    class ResObj:
        pass

    item = _FakeItem(maintype="Armor")
    res_obj = ResObj()
    res_obj.fire = 0.1
    item.add_resistance = res_obj
    e = Enchantment(item, name="Test", group="Prefix", value=1)
    e._add_resistance("fire", 0.2)
    assert abs(item.add_resistance.fire - 0.3) < 1e-9


def test_add_resistance_object_branch_sets_new_attribute():
    class ResObj:
        pass

    item = _FakeItem(maintype="Armor")
    item.add_resistance = ResObj()
    e = Enchantment(item, name="Test", group="Prefix", value=1)
    e._add_resistance("cold", 0.25)
    assert item.add_resistance.cold == 0.25


_SHAPES = [
    ("Sword", "Weapon"),
    ("Hammer", "Weapon"),
    ("Bow", "Weapon"),
    ("Chestplate", "Armor"),
    ("Ring", "Accessory"),
]


def test_every_requirements_returns_a_real_bool():
    """``requirements()`` gates enchantment selection with ``if``-style truthiness,
    so a class returning a truthy string/list would silently always qualify."""
    wrong = [
        f"{cls.__name__}({subtype}/{maintype}) -> {result!r}"
        for cls in _all_enchantment_classes()
        for subtype, maintype in _SHAPES
        for result in [cls(_FakeItem(subtype, maintype)).requirements()]
        if not isinstance(result, bool)
    ]
    assert wrong == []


def test_every_enchantment_is_reachable_by_some_item_shape():
    """An enchantment whose requirements() can never be satisfied is dead loot.

    The old sweep here called requirements() and asserted nothing at all — it
    would have passed for a class hard-wired to ``return False``.
    """
    unreachable = [
        cls.__name__ for cls in _all_enchantment_classes()
        if not any(cls(_FakeItem(subtype, maintype)).requirements()
                   for subtype, maintype in _SHAPES)
    ]
    assert unreachable == []


def test_every_modify_actually_changes_a_numeric_stat():
    """Folding the name in is not enough: an enchantment that renames the item
    without altering damage/value/protection/resistance is a no-op the player
    pays gold for."""
    inert = []
    for cls in _all_enchantment_classes():
        item = _FakeItem()
        before = (item.damage, item.value, item.weight, item.protection,
                  dict(item.add_resistance))
        cls(item).modify()
        after = (item.damage, item.value, item.weight, item.protection,
                 dict(item.add_resistance))
        if before == after:
            inert.append(cls.__name__)
    assert inert == []


@pytest.mark.parametrize("cls_name, subtype", [
    ("Sharp", "Sword"), ("Weighted", "Hammer"), ("Balanced", "Bow"),
])
def test_damage_percent_prefixes_stay_inside_their_declared_bounds(
        cls_name, subtype, seeded):
    """Damage and value must move together, within the class's own declared
    ``_mod_low``/``_mod_high``/``_value_scale`` envelope.

    Bounds come from the class attributes rather than from re-running the same
    arithmetic the implementation uses, so this fails if the shared modify()
    body stops honouring a subclass's declared range.
    """
    cls = getattr(enchant_tables, cls_name)
    lo = cls._mod_low - cls._mod_offset
    hi = cls._mod_high - cls._mod_offset

    with seeded(20240101):
        for _ in range(50):
            item = _FakeItem(subtype=subtype, maintype="Weapon")
            cls(item).modify()
            gained = item.damage - 10
            assert gained >= 1                   # the floor in modify()
            assert gained <= 10 * hi + 1e-9
            # value multiplier = frac * _value_scale + 1
            assert item.value >= int(100 * (lo * cls._value_scale + 1)) - 1
            assert item.value <= int(100 * (hi * cls._value_scale + 1)) + 1


@pytest.mark.parametrize("cls_name, low, high", [
    ("Studded", 1, 3),
    ("Reinforced", 3, 5),
])
def test_protection_prefixes_add_their_declared_range_and_price_it(
        cls_name, low, high, seeded):
    """Protection prefixes add a flat 1-3 / 3-5 and charge 21 gold per point."""
    cls = getattr(enchant_tables, cls_name)
    seen = set()
    with seeded(20240101):
        for _ in range(60):
            item = _FakeItem(subtype="Chestplate", maintype="Armor")
            cls(item).modify()
            gained = item.protection - 2
            assert low <= gained <= high
            assert item.value == 100 + gained * 21
            seen.add(gained)
    assert seen == set(range(low, high + 1)), (
        f"{cls_name} never produced every value in {low}..{high}: {sorted(seen)}")


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
    e = Enchantment(item, name="Base", group="Prefix", value=1)
    assert e.modify() is None
    assert e.requirements() is True
