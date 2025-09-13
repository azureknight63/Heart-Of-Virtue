"""
All the loot tables for NPCs can be found here. These are called from the npc module.
"""

import random, decimal
from src.items import item_types
from src.states import Poisoned, PhoenixRevive


class Enchantment:
    def __init__(self, item, name, rarity, group, value):
        self.item = item  # item to be modified by the enchantment
        self.name = name  # will be added to the item's base name as either a prefix or suffix, depending on group
        self.rarity = rarity  # likelihood of this enchantment being selected
        self.group = group  # prefix or suffix
        self.value = value  # multiplier against the item's base value; 1.5 = 50% increase in gold value
        self.equip_states = []  # enchantments can cause states to be applied to the player when the item is equipped

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


### PREFIXES ###


class Sharp(Enchantment):
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="Sharp", rarity=0, group="Prefix", value=1)

    def modify(self):
        mod = random.uniform(1.05, 1.15)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        # scale value based on the extra damage in a manner consistent with Flaming
        value_mod = ((mod - 1) / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_subtypes = item_types['weapons']['archetypes']["Blade"]
        if self.item.subtype in allowed_subtypes:
            return True
        else:
            return False


class Weighted(Enchantment):
    tier = 1
    def __init__(self, item):
        super().__init__(item, name="Weighted", rarity=0, group="Prefix", value=1)

    def modify(self):
        mod = random.uniform(0.05, 0.15)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        self.item.value *= 1 + mod
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_subtypes = item_types['weapons']['archetypes']["Blunt"]
        if self.item.subtype in allowed_subtypes:
            return True
        else:
            return False


class Balanced(Enchantment):
    tier = 1
    def __init__(self, item):
        super().__init__(item, name="Balanced", rarity=0, group="Prefix", value=1)

    def modify(self):
        mod = random.uniform(1.05, 1.15)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        # scale value based on the extra damage in a manner consistent with Flaming
        value_mod = ((mod - 1) / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_subtypes = item_types['weapons']['archetypes']["Ranged"]
        if self.item.subtype in allowed_subtypes:
            return True
        else:
            return False


class Hollow(Enchantment):  # reduced weight and damage
    tier = 1
    def __init__(self, item):
        super().__init__(item, name="Hollow", rarity=0, group="Prefix", value=1.1)

    def modify(self):
        self.item.weight *= 0.5
        self.item.damage *= 0.8
        self.item.value *= self.value
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_subtypes = item_types['weapons']['archetypes']["Ranged"]
        if self.item.subtype in allowed_subtypes:
            return True
        else:
            return False


class Polished(Enchantment):  # it's shiny! 10% increase in gold value
    tier = 1
    def __init__(self, item):
        super().__init__(item, name="Polished", rarity=0, group="Prefix", value=1.1)

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
        super().__init__(item, name="Encrusted", rarity=0, group="Prefix", value=1.3)

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
        super().__init__(item, name="Dirty", rarity=0, group="Prefix", value=0.9)

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
        super().__init__(item, name="Studded", rarity=0, group="Prefix", value=1)

    def modify(self):
        mod = random.randint(1, 3)
        self.item.protection += mod
        self.item.value += (mod * 21)
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = [
            "Armor",
            "Helm",
            "Gloves",
            "Boots"
                            ]
        if self.item.maintype in allowed_maintypes:
            return True
        else:
            return False


class Reinforced(Enchantment):  # improves protection rating of armor by 3-5
    tier = 2
    def __init__(self, item):
        super().__init__(item, name="Reinforced", rarity=0, group="Prefix", value=1)

    def modify(self):
        mod = random.randint(3, 5)
        self.item.protection += mod
        self.item.value += (mod * 21)
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = [
            "Armor",
            "Helm",
            "Gloves",
            "Boots"
                            ]
        if self.item.maintype in allowed_maintypes:
            return True
        else:
            return False


class Plated(Enchantment):  # improves protection rating of armor by 5-10
    tier = 3
    def __init__(self, item):
        super().__init__(item, name="Plated", rarity=0, group="Prefix", value=1)

    def modify(self):
        mod = random.randint(5, 10)
        self.item.protection += mod
        self.item.value += (mod * 21)
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = [
            "Armor",
            "Helm",
            "Gloves",
            "Boots"
                            ]
        if self.item.maintype in allowed_maintypes:
            return True
        else:
            return False


class Poisonous(Enchantment):  # inflicts Poison state when equipped; non-permanent. Also adds resistance to poison.
    tier = 2
    def __init__(self, item):
        super().__init__(item, name="Poisonous", rarity=0, group="Prefix", value=1)
        self.equip_states = [Poisoned(None)]

    def modify(self):
        if hasattr(self.item, "add_resistance"):
            if hasattr(self.item.add_resistance, "poison"):
                self.item.add_resistance.poison += 0.4
        else:
            self.item.add_resistance.poison = 0.4
        self.item.value *= 1.3
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = [
            "Armor",
            "Helm",
            "Gloves",
            "Boots",
            "Accessory"
                            ]
        if self.item.maintype in allowed_maintypes:
            return True
        else:
            return False


class Dousing(Enchantment):  # grants resistance to fire when equipped
    tier = 2
    def __init__(self, item):
        super().__init__(item, name="Dousing", rarity=0, group="Prefix", value=1.25)

    def modify(self):
        # add or increase fire resistance on the item
        if hasattr(self.item, "add_resistance"):
            if hasattr(self.item.add_resistance, "fire"):
                self.item.add_resistance.fire += 0.3
            else:
                self.item.add_resistance.fire = 0.3
        else:
            # follow existing project pattern: attach attribute directly
            self.item.add_resistance.fire = 0.3
        # increase value modestly for the protection
        self.item.value *= 1.25
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, treated against flame.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = [
            "Armor",
            "Helm",
            "Gloves",
            "Boots",
            "Accessory"
        ]
        return self.item.maintype in allowed_maintypes


class Flaming(Enchantment):
    tier = 2
    def __init__(self, item):
        super().__init__(item, name="Flaming", rarity=0, group="Prefix", value=1.3)

    def modify(self):
        # modest elemental damage boost
        mod = random.uniform(1.12, 1.28)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        # force weapon to do fire damage as its base damage type
        self.item.base_damage_type = "fire"
        value_mod = ((mod - 1) / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, crackling with heat.".format(self.item.name)

    def requirements(self):
        return getattr(self.item, 'maintype', None) == "Weapon"


class Icy(Enchantment):
    tier = 2
    def __init__(self, item):
        super().__init__(item, name="Icy", rarity=0, group="Prefix", value=1.25)

    def modify(self):
        mod = random.uniform(1.12, 1.28)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        self.item.base_damage_type = "ice"
        # scale value based on damage bonus (fractional mod)
        value_mod = (mod - 1 / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, rimed in frost.".format(self.item.name)

    def requirements(self):
        return getattr(self.item, 'maintype', None) == "Weapon"


class Shocking(Enchantment):
    tier = 2
    def __init__(self, item):
        super().__init__(item, name="Shocking", rarity=0, group="Prefix", value=1.35)

    def modify(self):
        mod = random.uniform(1.10, 1.25)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        self.item.base_damage_type = "shock"
        # scale value based on damage bonus (fractional mod)
        value_mod = (mod - 1 / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, humming with electricity.".format(self.item.name)

    def requirements(self):
        return getattr(self.item, 'maintype', None) == "Weapon"


class Earthen(Enchantment):
    tier = 2
    def __init__(self, item):
        super().__init__(item, name="Earthen", rarity=0, group="Prefix", value=1.2)

    def modify(self):
        mod = random.uniform(1.08, 1.22)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        self.item.base_damage_type = "earth"
        # scale value based on damage bonus (fractional mod)
        value_mod = (mod - 1 / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, bound with the weight of the earth.".format(self.item.name)

    def requirements(self):
        return getattr(self.item, 'maintype', None) == "Weapon"


class Radiant(Enchantment):
    tier = 3
    def __init__(self, item):
        super().__init__(item, name="Radiant", rarity=0, group="Prefix", value=1.5)

    def modify(self):
        mod = random.uniform(1.15, 1.30)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        self.item.base_damage_type = "light"
        # scale value based on damage bonus (fractional mod)
        value_mod = (mod - 1 / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, glowing with a pure light.".format(self.item.name)

    def requirements(self):
        return getattr(self.item, 'maintype', None) == "Weapon"


class Umbral(Enchantment):
    tier = 3
    def __init__(self, item):
        super().__init__(item, name="Umbral", rarity=0, group="Prefix", value=1.5)

    def modify(self):
        mod = random.uniform(1.15, 1.30)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        self.item.base_damage_type = "dark"
        # scale value based on damage bonus (fractional mod)
        value_mod = (mod - 1 / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, cloaked in shadow.".format(self.item.name)

    def requirements(self):
        return getattr(self.item, 'maintype', None) == "Weapon"


class Spiritual(Enchantment):
    tier = 3
    def __init__(self, item):
        super().__init__(item, name="Spiritual", rarity=0, group="Prefix", value=1.4)

    def modify(self):
        mod = random.uniform(1.10, 1.25)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        self.item.base_damage_type = "spiritual"
        # scale value based on damage bonus (fractional mod)
        value_mod = (mod - 1 / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, suffused with otherworldly power.".format(self.item.name)

    def requirements(self):
        return getattr(self.item, 'maintype', None) == "Weapon"


class Pure(Enchantment):
    tier = 3
    def __init__(self, item):
        super().__init__(item, name="Pure", rarity=0, group="Prefix", value=1.4)

    def modify(self):
        # 'Pure' enchanment makes attacks ignore some resistances by converting to pure damage
        mod = random.uniform(1.15, 1.30)
        amount = self.item.damage * mod
        if amount < 1:
            amount = 1
        self.item.damage += amount
        self.item.base_damage_type = "pure"
        # scale value based on damage bonus (fractional mod)
        value_mod = (mod - 1 / 2) + self.value
        self.item.value = int(self.item.value * value_mod)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, its edge humming with uncompromising force.".format(self.item.name)

    def requirements(self):
        return getattr(self.item, 'maintype', None) == "Weapon"

### SUFFIXES ###


class OfHealth(Enchantment):  # it's healthy! Increase maxhp by 10-30
    tier = 1
    def __init__(self, item):
        super().__init__(item, name="of Health", rarity=0, group="Suffix", value=1)

    def modify(self):
        mod = random.randint(10, 30)
        if hasattr(self.item, "add_maxhp"):
            self.item.add_maxhp += mod
        else:
            self.item.add_maxhp = mod
        self.item.value += mod * 2
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class OfVigor(Enchantment):  # it's strong! Increase strength by 1-3
    tier = 1
    def __init__(self, item):
        super().__init__(item, name="of Vigor", rarity=0, group="Suffix", value=1)

    def modify(self):
        mod = random.randint(1, 3)
        if hasattr(self.item, "add_str"):
            self.item.add_str += mod
        else:
            self.item.add_str = mod
        self.item.value += mod * 20
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class OfPerseverance(Enchantment):  # Increase max fatigue by 10-30
    tier = 1
    def __init__(self, item):
        super().__init__(item, name="of Perseverance", rarity=0, group="Suffix", value=1)

    def modify(self):
        mod = random.randint(10, 30)
        if hasattr(self.item, "add_maxfatigue"):
            self.item.add_maxfatigue += mod
        else:
            self.item.add_maxfatigue = mod
        self.item.value += mod * 2
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class OfTempo(Enchantment):  # it's fast! Increase speed by 1-3
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="of Tempo", rarity=0, group="Suffix", value=1)

    def modify(self):
        mod = random.randint(1, 3)
        if hasattr(self.item, "add_speed"):
            self.item.add_speed += mod
        else:
            self.item.add_speed = mod
        self.item.value += mod * 20
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class OfGrit(Enchantment):  # Increase endurance by 1-3
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="of Grit", rarity=0, group="Suffix", value=1)

    def modify(self):
        mod = random.randint(1, 3)
        if hasattr(self.item, "add_endurance"):
            self.item.add_endurance += mod
        else:
            self.item.add_endurance = mod
        self.item.value += mod * 20
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class OfCharms(Enchantment):  # Increase charisma by 1-3
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="of Charms", rarity=0, group="Suffix", value=1)

    def modify(self):
        mod = random.randint(1, 3)
        if hasattr(self.item, "add_charisma"):
            self.item.add_charisma += mod
        else:
            self.item.add_charisma = mod
        self.item.value += mod * 20
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class OfInsight(Enchantment):  # Increase intelligence by 1-3
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="of Insight", rarity=0, group="Suffix", value=1)

    def modify(self):
        mod = random.randint(1, 3)
        if hasattr(self.item, "add_intelligence"):
            self.item.add_intelligence += mod
        else:
            self.item.add_intelligence = mod
        self.item.value += mod * 20
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class OfSupplication(Enchantment):  # Increase faith by 1-3
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="of Supplication", rarity=0, group="Suffix", value=1)

    def modify(self):
        mod = random.randint(1, 3)
        if hasattr(self.item, "add_faith"):
            self.item.add_faith += mod
        else:
            self.item.add_faith = mod
        self.item.value += mod * 20
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True


class OfRelief(Enchantment):  # Increase weight tolerance slightly
    tier = 1

    def __init__(self, item):
        super().__init__(item, name="of Relief", rarity=0, group="Suffix", value=1)

    def modify(self):
        mod = random.randint(3, 7)
        if hasattr(self.item, "add_weight_tolerance"):
            self.item.add_weight_tolerance += decimal.Decimal(mod)
        else:
            self.item.add_weight_tolerance = decimal.Decimal(mod)
        self.item.value += mod * 5
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        return True

class OfThePhoenix(Enchantment):  # Grants a chance to revive on death once per combat
    tier = 3

    def __init__(self, item):
        super().__init__(item, name="of the Phoenix", rarity=0, group="Suffix", value=2)
        self.equip_states = [PhoenixRevive(None)]

    def modify(self):
        self.item.value *= self.value
        self.item.value = int(self.item.value)
        self.item.name = self.item.name + " " + self.name
        self.item.announce = "There's a {} here, radiating warmth.".format(self.item.name)

    def requirements(self):
        # Can be applied to armor or accessories
        allowed_maintypes = [
            "Armor",
            "Helm",
            "Gloves",
            "Boots",
            "Accessory"
        ]
        return self.item.maintype in allowed_maintypes


class Purifying(Enchantment):  # grants resistance to pure damage
    tier = 3
    def __init__(self, item):
        super().__init__(item, name="Purifying", rarity=0, group="Prefix", value=1.5)

    def modify(self):
        if hasattr(self.item, "add_resistance"):
            if hasattr(self.item.add_resistance, "pure"):
                self.item.add_resistance.pure += 0.35
            else:
                self.item.add_resistance.pure = 0.35
        else:
            self.item.add_resistance.pure = 0.35
        self.item.value *= 1.5
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, tempered to guard against absolute force.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = ["Armor","Helm","Gloves","Boots","Accessory"]
        return self.item.maintype in allowed_maintypes


class Needleproof(Enchantment):  # grants resistance to piercing attacks
    tier = 2
    def __init__(self, item):
        super().__init__(item, name="Needleproof", rarity=0, group="Prefix", value=1.2)

    def modify(self):
        if hasattr(self.item, "add_resistance"):
            if hasattr(self.item.add_resistance, "piercing"):
                self.item.add_resistance.piercing += 0.3
            else:
                self.item.add_resistance.piercing = 0.3
        else:
            self.item.add_resistance.piercing = 0.3
        self.item.value *= 1.2
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, its fibers woven to shrug off arrows and needles.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = ["Armor","Helm","Gloves","Boots","Accessory"]
        return self.item.maintype in allowed_maintypes


class Edgebound(Enchantment):  # reduces slashing damage
    tier = 2
    def __init__(self, item):
        super().__init__(item, name="Edgebound", rarity=0, group="Prefix", value=1.25)

    def modify(self):
        if hasattr(self.item, "add_resistance"):
            if hasattr(self.item.add_resistance, "slashing"):
                self.item.add_resistance.slashing += 0.3
            else:
                self.item.add_resistance.slashing = 0.3
        else:
            self.item.add_resistance.slashing = 0.3
        self.item.value *= 1.25
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, its plates deflect blade and saber alike.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = ["Armor","Helm","Gloves","Boots","Accessory"]
        return self.item.maintype in allowed_maintypes


class Bulwark(Enchantment):  # toughened against crushing impacts
    tier = 3
    def __init__(self, item):
        super().__init__(item, name="Bulwark", rarity=0, group="Prefix", value=1.35)

    def modify(self):
        if hasattr(self.item, "add_resistance"):
            if hasattr(self.item.add_resistance, "crushing"):
                self.item.add_resistance.crushing += 0.35
            else:
                self.item.add_resistance.crushing = 0.35
        else:
            self.item.add_resistance.crushing = 0.35
        self.item.value *= 1.35
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here, bulked and braced to take heavy blows.".format(self.item.name)

    def requirements(self):
        allowed_maintypes = ["Armor","Helm","Gloves","Boots","Accessory"]
        return self.item.maintype in allowed_maintypes
