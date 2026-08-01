"""
All the loot tables for NPCs can be found here. These are called from the npc module.
"""

import random
import decimal
from src.items import item_types
from src.states import Poisoned, PhoenixRevive


class Enchantment:
    def __init__(self, item, name, group, value):
        self.item = item  # item to be modified by the enchantment
        self.name = name  # will be added to the item's base name as either a prefix or suffix, depending on group
        self.group = group  # prefix or suffix
        self.value = value  # multiplier against the item's base value; 1.5 = 50% increase in gold value
        self.equip_states = (
            []
        )  # enchantments can cause states to be applied to the player when the item is equipped

    def _add_resistance(self, key, amount):
        """
        Safely add or increment a resistance on the item. Works whether add_resistance
        is a dict (e.g. loaded from JSON) or an object with attributes.
        """
        ar = getattr(self.item, "add_resistance", None)
        if ar is None:
            # create a dict by default
            self.item.add_resistance = {key: amount}
            return
        if isinstance(ar, dict):
            ar[key] = ar.get(key, 0) + amount
        else:
            # object-like: set or increment an attribute
            if hasattr(ar, key):
                setattr(ar, key, getattr(ar, key) + amount)
            else:
                setattr(ar, key, amount)

    def modify(self):
        """
        The modifications that take place against the item. Varies per enchantment
        :return:
        """
        pass

    def requirements(self):
        """
        Requirements that must be met for the enchantment to be selected
        :return: True or False
        """
        return True


# PREFIXES


class _DamagePercentBoostEnchantment(Enchantment):
    """
    Shared modify() for prefix enchantments that boost item.damage by a random
    percentage and scale item.value proportionally to that boost (#424). Concrete
    subclasses (Sharp, Weighted, Balanced, and the elemental damage prefixes)
    supply only the differing data as class attributes instead of each
    reimplementing this body.

    Not itself a real enchantment: it deliberately doesn't override __init__,
    so tests/enumeration code that walks module classes should exclude it (and
    any future helper base) by checking for an own __init__, same as they
    already exclude Enchantment itself.

    _mod_low / _mod_high: random.uniform() range sampled fresh each call
    _mod_offset: subtracted from the sampled value to get the fractional damage
                 boost (1 when the range is centered on 1.0, e.g. (1.05, 1.15);
                 0 when the range already IS the fraction, e.g. Weighted's
                 (0.05, 0.15))
    _value_scale: how much of the fractional boost carries into item.value
    _base_damage_type: if set, overwrites item.base_damage_type (elemental
                        prefixes force the weapon's damage type)
    _announce_template: format string with a single {} for the item name
    """

    _mod_low = 0.0
    _mod_high = 0.0
    _mod_offset = 1
    _value_scale = 0.5
    _base_damage_type = None
    _announce_template = "There's a {} here."

    def modify(self):
        mod = random.uniform(self._mod_low, self._mod_high)
        frac = mod - self._mod_offset
        amount = self.item.damage * frac
        if amount < 1:
            amount = 1
        self.item.damage += amount
        if self._base_damage_type is not None:
            self.item.base_damage_type = self._base_damage_type
        # scale value based on the extra damage in a manner consistent with Flaming
        value_mod = (frac * self._value_scale) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = self._announce_template.format(self.item.name)


class Sharp(_DamagePercentBoostEnchantment):
    tier = 1
    _mod_low, _mod_high = 1.05, 1.15

    def __init__(self, item):
        super().__init__(item, name="Sharp", group="Prefix", value=1)

    def requirements(self):
        allowed_subtypes = item_types["weapons"]["archetypes"]["Blade"]
        if self.item.subtype in allowed_subtypes:
            return True
        else:
            return False


class Weighted(_DamagePercentBoostEnchantment):
    tier = 1
    _mod_low, _mod_high = 0.05, 0.15
    _mod_offset = 0
    _value_scale = 1.0

    def __init__(self, item):
        super().__init__(item, name="Weighted", group="Prefix", value=1)

    def requirements(self):
        allowed_subtypes = item_types["weapons"]["archetypes"]["Blunt"]
        if self.item.subtype in allowed_subtypes:
            return True
        else:
            return False


class Balanced(_DamagePercentBoostEnchantment):
    tier = 1
    _mod_low, _mod_high = 1.05, 1.15

    def __init__(self, item):
        super().__init__(item, name="Balanced", group="Prefix", value=1)

    def requirements(self):
        allowed_subtypes = item_types["weapons"]["archetypes"]["Ranged"]
        if self.item.subtype in allowed_subtypes:
            return True
        else:
            return False


class Hollow(Enchantment):  # reduced weight and damage
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="Hollow", group="Prefix", value=1.1)

    def modify(self):
        self.item.weight *= 0.5
        self.item.damage *= 0.8
        self.item.value *= self.value
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_subtypes = item_types["weapons"]["archetypes"]["Ranged"]
        if self.item.subtype in allowed_subtypes:
            return True
        else:
            return False


class Polished(Enchantment):  # it's shiny! 10% increase in gold value
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="Polished", group="Prefix", value=1.1)

    def modify(self):
        self.item.value *= self.value
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class Encrusted(Enchantment):  # encrusted with gems; +30% gold value
    tier = 2

    def __init__(self, item):
        super().__init__(item, name="Encrusted", group="Prefix", value=1.3)

    def modify(self):
        self.item.value *= 1.3
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class Dirty(Enchantment):  # it's dirty! 10% decrease in gold value
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="Dirty", group="Prefix", value=0.9)

    def modify(self):
        self.item.value *= self.value
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class Studded(Enchantment):  # improves protection rating of armor by 1-3
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="Studded", group="Prefix", value=1)

    def modify(self):
        mod = random.randint(1, 3)
        self.item.protection += mod
        self.item.value += mod * 21
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = ["Armor", "Helm", "Gloves", "Boots"]
        if self.item.maintype in allowed_maintypes:
            return True
        else:
            return False


class Reinforced(Enchantment):  # improves protection rating of armor by 3-5
    tier = 2

    def __init__(self, item):
        super().__init__(item, name="Reinforced", group="Prefix", value=1)

    def modify(self):
        mod = random.randint(3, 5)
        self.item.protection += mod
        self.item.value += mod * 21
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = ["Armor", "Helm", "Gloves", "Boots"]
        if self.item.maintype in allowed_maintypes:
            return True
        else:
            return False


class Plated(Enchantment):  # improves protection rating of armor by 5-10
    tier = 3

    def __init__(self, item):
        super().__init__(item, name="Plated", group="Prefix", value=1)

    def modify(self):
        mod = random.randint(5, 10)
        self.item.protection += mod
        self.item.value += mod * 21
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = ["Armor", "Helm", "Gloves", "Boots"]
        if self.item.maintype in allowed_maintypes:
            return True
        else:
            return False


class Poisonous(
    Enchantment
):  # inflicts Poison state when equipped; non-permanent. Also adds resistance to poison.
    tier = 2

    def __init__(self, item):
        super().__init__(item, name="Poisonous", group="Prefix", value=1.3)
        self.equip_states = [Poisoned(None)]

    def modify(self):
        # safely add/increment poison resistance (works if add_resistance is dict or object)
        self._add_resistance("poison", 0.4)
        self.item.value *= self.value
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = ["Armor", "Helm", "Gloves", "Boots", "Accessory"]
        if self.item.maintype in allowed_maintypes:
            return True
        else:
            return False


class _ResistanceEnchantment(Enchantment):
    """
    Shared modify() for prefix enchantments that grant a flat resistance and
    scale item.value by the enchantment's own value multiplier (#424). Concrete
    subclasses (Dousing, Purifying, Needleproof, Edgebound, Bulwark) supply only
    the resistance type/amount and flavor announce as class attributes.

    Not itself a real enchantment: it deliberately doesn't override __init__, so
    class-enumeration code excludes it the same way it excludes Enchantment.

    _resist_type / _resist_amount: passed straight to Enchantment._add_resistance
    _announce_template: format string with a single {} for the item name
    _allowed_maintypes: item maintypes this enchantment may apply to
    """

    _resist_type = None
    _resist_amount = 0.0
    _announce_template = "There's a {} here."
    _allowed_maintypes = ["Armor", "Helm", "Gloves", "Boots", "Accessory"]

    def modify(self):
        self._add_resistance(self._resist_type, self._resist_amount)
        # scale value by the enchantment's own multiplier (self.value == the old
        # per-class literal, e.g. Dousing's 1.25)
        self.item.value = int(self.item.value * self.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = self._announce_template.format(self.item.name)

    def requirements(self):
        return self.item.maintype in self._allowed_maintypes


class Dousing(_ResistanceEnchantment):  # grants resistance to fire when equipped
    tier = 2
    _resist_type, _resist_amount = "fire", 0.3
    _announce_template = "There's a {} here, treated against flame."

    def __init__(self, item):
        super().__init__(item, name="Dousing", group="Prefix", value=1.25)


class Flaming(_DamagePercentBoostEnchantment):
    tier = 2
    _mod_low, _mod_high = 1.12, 1.28
    _base_damage_type = "fire"
    _announce_template = "There's a {} here, crackling with heat."

    def __init__(self, item):
        super().__init__(item, name="Flaming", group="Prefix", value=1.3)

    def requirements(self):
        return getattr(self.item, "maintype", None) == "Weapon"


class Icy(_DamagePercentBoostEnchantment):
    tier = 2
    _mod_low, _mod_high = 1.12, 1.28
    _base_damage_type = "ice"
    _announce_template = "There's a {} here, rimed in frost."

    def __init__(self, item):
        super().__init__(item, name="Icy", group="Prefix", value=1.25)

    def requirements(self):
        return getattr(self.item, "maintype", None) == "Weapon"


class Shocking(_DamagePercentBoostEnchantment):
    tier = 2
    _mod_low, _mod_high = 1.10, 1.25
    _base_damage_type = "shock"
    _announce_template = "There's a {} here, humming with electricity."

    def __init__(self, item):
        super().__init__(item, name="Shocking", group="Prefix", value=1.35)

    def requirements(self):
        return getattr(self.item, "maintype", None) == "Weapon"


class Earthen(_DamagePercentBoostEnchantment):
    tier = 2
    _mod_low, _mod_high = 1.08, 1.22
    _base_damage_type = "earth"
    _announce_template = "There's a {} here, bound with the weight of the earth."

    def __init__(self, item):
        super().__init__(item, name="Earthen", group="Prefix", value=1.2)

    def requirements(self):
        return getattr(self.item, "maintype", None) == "Weapon"


class Radiant(_DamagePercentBoostEnchantment):
    tier = 3
    _mod_low, _mod_high = 1.15, 1.30
    _base_damage_type = "light"
    _announce_template = "There's a {} here, glowing with a pure light."

    def __init__(self, item):
        super().__init__(item, name="Radiant", group="Prefix", value=1.5)

    def requirements(self):
        return getattr(self.item, "maintype", None) == "Weapon"


class Umbral(_DamagePercentBoostEnchantment):
    tier = 3
    _mod_low, _mod_high = 1.15, 1.30
    _base_damage_type = "dark"
    _announce_template = "There's a {} here, cloaked in shadow."

    def __init__(self, item):
        super().__init__(item, name="Umbral", group="Prefix", value=1.5)

    def requirements(self):
        return getattr(self.item, "maintype", None) == "Weapon"


class Spiritual(_DamagePercentBoostEnchantment):
    tier = 3
    _mod_low, _mod_high = 1.10, 1.25
    _base_damage_type = "spiritual"
    _announce_template = "There's a {} here, suffused with otherworldly power."

    def __init__(self, item):
        super().__init__(item, name="Spiritual", group="Prefix", value=1.4)

    def requirements(self):
        return getattr(self.item, "maintype", None) == "Weapon"


class Pure(_DamagePercentBoostEnchantment):
    # 'Pure' enchantment makes attacks ignore some resistances by converting to pure damage
    tier = 3
    _mod_low, _mod_high = 1.15, 1.30
    _base_damage_type = "pure"
    _announce_template = "There's a {} here, its edge humming with uncompromising force."

    def __init__(self, item):
        super().__init__(item, name="Pure", group="Prefix", value=1.4)

    def requirements(self):
        return getattr(self.item, "maintype", None) == "Weapon"


# SUFFIXES


class _StatBoostEnchantment(Enchantment):
    """
    Shared modify() for suffix enchantments that raise a single stat bonus on
    the item by a random amount and add a flat-per-point bump to item.value
    (#424). Concrete subclasses (of Health, of Vigor, ... of Relief) supply only
    their differing data as class attributes.

    Not itself a real enchantment: it deliberately doesn't override __init__, so
    class-enumeration code excludes it the same way it excludes Enchantment.

    _mod_low / _mod_high: random.randint() range for the stat increase
    _stat_attr: the item bonus attribute incremented (e.g. "add_str")
    _value_mult: gold added to item.value per point of the roll
    _stat_wrap: optional callable applied to the roll before it's stored
                (of Relief stores a decimal.Decimal); None means store the raw int
    """

    _mod_low = 0
    _mod_high = 0
    _stat_attr = None
    _value_mult = 0
    _stat_wrap = None
    _announce_template = "There's a {} here."

    def modify(self):
        mod = random.randint(self._mod_low, self._mod_high)
        delta = self._stat_wrap(mod) if self._stat_wrap is not None else mod
        if hasattr(self.item, self._stat_attr):
            setattr(
                self.item, self._stat_attr, getattr(self.item, self._stat_attr) + delta
            )
        else:
            setattr(self.item, self._stat_attr, delta)
        self.item.value += mod * self._value_mult
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = self._announce_template.format(self.item.name)

    def requirements(self):
        return True


class OfHealth(_StatBoostEnchantment):  # it's healthy! Increase maxhp by 10-30
    tier = 1
    _mod_low, _mod_high = 10, 30
    _stat_attr = "add_maxhp"
    _value_mult = 2

    def __init__(self, item):
        super().__init__(item, name="of Health", group="Suffix", value=1)


class OfVigor(_StatBoostEnchantment):  # it's strong! Increase strength by 1-3
    tier = 1
    _mod_low, _mod_high = 1, 3
    _stat_attr = "add_str"
    _value_mult = 20

    def __init__(self, item):
        super().__init__(item, name="of Vigor", group="Suffix", value=1)


class OfPerseverance(_StatBoostEnchantment):  # Increase max fatigue by 10-30
    tier = 1
    _mod_low, _mod_high = 10, 30
    _stat_attr = "add_maxfatigue"
    _value_mult = 2

    def __init__(self, item):
        super().__init__(
            item, name="of Perseverance", group="Suffix", value=1
        )


class OfTempo(_StatBoostEnchantment):  # it's fast! Increase speed by 1-3
    tier = 1
    _mod_low, _mod_high = 1, 3
    _stat_attr = "add_speed"
    _value_mult = 20

    def __init__(self, item):
        super().__init__(item, name="of Tempo", group="Suffix", value=1)


class OfGrit(_StatBoostEnchantment):  # Increase endurance by 1-3
    tier = 1
    _mod_low, _mod_high = 1, 3
    _stat_attr = "add_endurance"
    _value_mult = 20

    def __init__(self, item):
        super().__init__(item, name="of Grit", group="Suffix", value=1)


class OfCharms(_StatBoostEnchantment):  # Increase charisma by 1-3
    tier = 1
    _mod_low, _mod_high = 1, 3
    _stat_attr = "add_charisma"
    _value_mult = 20

    def __init__(self, item):
        super().__init__(item, name="of Charms", group="Suffix", value=1)


class OfInsight(_StatBoostEnchantment):  # Increase intelligence by 1-3
    tier = 1
    _mod_low, _mod_high = 1, 3
    _stat_attr = "add_intelligence"
    _value_mult = 20

    def __init__(self, item):
        super().__init__(item, name="of Insight", group="Suffix", value=1)


class OfSupplication(_StatBoostEnchantment):  # Increase faith by 1-3
    tier = 1
    _mod_low, _mod_high = 1, 3
    _stat_attr = "add_faith"
    _value_mult = 20

    def __init__(self, item):
        super().__init__(
            item, name="of Supplication", group="Suffix", value=1
        )


class OfRelief(_StatBoostEnchantment):  # Increase weight tolerance slightly
    tier = 1
    _mod_low, _mod_high = 3, 7
    _stat_attr = "add_weight_tolerance"
    _value_mult = 5
    _stat_wrap = decimal.Decimal  # weight tolerance is stored as a Decimal

    def __init__(self, item):
        super().__init__(item, name="of Relief", group="Suffix", value=1)


class OfThePhoenix(Enchantment):  # Grants a chance to revive on death once per combat
    tier = 3

    def __init__(self, item):
        super().__init__(item, name="of the Phoenix", group="Suffix", value=2)
        self.equip_states = [PhoenixRevive(None)]

    def modify(self):
        self.item.value *= self.value
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here, radiating warmth.".format(
            self.item.name
        )

    def requirements(self):
        # Can be applied to armor or accessories
        allowed_maintypes = ["Armor", "Helm", "Gloves", "Boots", "Accessory"]
        return self.item.maintype in allowed_maintypes


class Purifying(_ResistanceEnchantment):  # grants resistance to pure damage
    tier = 3
    _resist_type, _resist_amount = "pure", 0.35
    _announce_template = (
        "There's a {} here, tempered to guard against absolute force."
    )

    def __init__(self, item):
        super().__init__(item, name="Purifying", group="Prefix", value=1.5)


class Needleproof(_ResistanceEnchantment):  # grants resistance to piercing attacks
    tier = 2
    _resist_type, _resist_amount = "piercing", 0.3
    _announce_template = (
        "There's a {} here, its fibers woven to shrug off arrows and needles."
    )

    def __init__(self, item):
        super().__init__(item, name="Needleproof", group="Prefix", value=1.2)


class Edgebound(_ResistanceEnchantment):  # reduces slashing damage
    tier = 2
    _resist_type, _resist_amount = "slashing", 0.3
    _announce_template = (
        "There's a {} here, its plates deflect blade and saber alike."
    )

    def __init__(self, item):
        super().__init__(item, name="Edgebound", group="Prefix", value=1.25)


class Bulwark(_ResistanceEnchantment):  # toughened against crushing impacts
    tier = 3
    _resist_type, _resist_amount = "crushing", 0.35
    _announce_template = (
        "There's a {} here, bulked and braced to take heavy blows."
    )

    def __init__(self, item):
        super().__init__(item, name="Bulwark", group="Prefix", value=1.35)
