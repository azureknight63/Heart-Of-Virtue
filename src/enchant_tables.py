'''
All of the loot tables for NPCs can be found here. These are called from the npc module.
'''

import random, decimal
import items


class Enchantment:
    def __init__(self, item, name, rarity, group, value):
        self.item = item  # item to be modified by the enchantment
        self.name = name  # will be added to the item's base name as either a prefix or suffix, depending on group
        self.rarity = rarity  # likelihood of this enchantment being selected
        self.group = group  # prefix or suffix
        self.value = value  # multiplier against the item's base value; 1.5 = 50% increase in gold value

    def modify(self):
        '''
        The modifications that take place against the item. Varies per enchantment
        :return:
        '''
        pass

    def requirements(self):
        '''
        Requirements that must be met for the enchantment to be selected
        :return: True or False
        '''
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
        self.item.value *= mod
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_subtypes = items.item_types['weapons']['archetypes']["Blade"]
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
        allowed_subtypes = items.item_types['weapons']['archetypes']["Blunt"]
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
        self.item.value *= mod
        self.item.value = int(self.item.value)
        self.item.name = self.name + " " + self.item.name
        self.item.announce = "There's a {} here.".format(self.item.name)

    def requirements(self):
        allowed_subtypes = items.item_types['weapons']['archetypes']["Ranged"]
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
        allowed_subtypes = items.item_types['weapons']['archetypes']["Ranged"]
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
        super().__init__(item, name="Reinforced", rarity=0, group="Prefix", value=1)

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


class OfRelief(Enchantment):  # Increase weight tolerance by 2-5 lbs
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

# todo: add more enchantments!