import random
import time
from neotermcolor import colored, cprint
import functions

item_types = {
    'weapons': {
        'subtypes': [
            "Dagger",
            "Sword",
            "Axe",
            "Pick",
            "Scythe",
            "Spear",
            "Halberd",
            "Bludgeon",
            "Hammer",
            "Bow",
            "Arrow",  # distinct from Bow because Bow is considered a blunt attack at close range
            "Crossbow",
            "Polearm",
            "Stars",
            "Staff",
            "Ethereal"
        ],
        'base_damage_types': {  # not to be confused with subtypes or archetypes, base damage is what a
            # standard attack evaluates as for a weapon or skill,
            # which can be combined with other base types or elemental types of damage
            "piercing": ["Dagger", "Pick", "Spear", "Arrow"],
            "slashing": ["Sword", "Axe", "Scythe", "Halberd", "Stars"],
            "crushing": ["Bludgeon", "Hammer", "Bow", "Crossbow", "Polearm", "Staff"],
            "spiritual": ["Ethereal"],
            "pure": ["Pure"]
        },
        'archetypes': {
            "Blade": ["Dagger", "Sword", "Axe", "Pick", "Scythe", "Spear", "Halberd"],
            "Blunt": ["Bludgeon", "Hammer", "Polearm", "Staff"],
            "Archery": ["Bow", "Crossbow"],
            "Ranged": ["Bow", "Crossbow", "Stars"],
            "Melee": ["Dagger", "Sword", "Axe", "Pick", "Scythe", "Spear", "Halberd", "Bludgeon", "Hammer", "Polearm",
                      "Staff"],
            "Twohand": ["Scythe", "Bow", "Crossbow", "Polearm"]
        }
    }
}


def get_all_subtypes():
    collection = []
    for group in item_types.keys():
        for subtype in item_types[group]:
            collection.append(subtype)
        item_types[group]['archetypes']['All'] = collection


def get_base_damage_type(item):
    damagetype = "pure"  # default
    for basetype, weapontypes in item_types['weapons']['base_damage_types'].items():
        if item.subtype in weapontypes:
            damagetype = basetype
    return damagetype


class Item:
    """The base class for all items"""

    def __init__(self, name, description, value, maintype, subtype, discovery_message, hidden=False, hide_factor=0,
                 skills=None, merchandise=False):
        self.name = name
        self.description = description
        self.value = value
        self.type = maintype
        self.subtype = subtype
        self.hidden = hidden
        self.hide_factor = hide_factor
        self._merchandise = merchandise
        self.discovery_message = discovery_message
        # self.level = level  # used for categorizing items in loot tables
        self.announce = "There's a {} here.".format(self.name)
        self.interactions = ["drop"]  # things to do with the item from the inventory menu
        self.skills = skills  # skills that can be learned from using the item (acquiring exp);
        # should be a dictionary with "moves" objects and the exp needed
        self.owner = None  # used to tie an item to an owner for special interactions
        self.equip_states = []  # items can cause states to be applied to the player when the item is equipped;
        # enchantments can add to this as well
        self.add_resistance = {}
        self.add_status_resistance = {}
        self.gives_exp = False  # checked before opening an exp category for this item
        if hasattr(self, "isequipped"):
            if getattr(self, "isequipped"):  # if the item starts equipped, add the unequip interaction, else visa versa
                self.interactions.append("unequip")
            else:
                self.interactions.append("equip")

    @property
    def merchandise(self):
        return self._merchandise

    @merchandise.setter
    def merchandise(self, value):
        self._merchandise = value

    def __str__(self):
        return "{}\n=====\n{}\nValue: {}\n".format(self.name, self.description, self.value)

    def on_equip(self, player):
        if len(self.equip_states) > 0:
            for state in self.equip_states:
                player.apply_state(state)
        '''
        Actions performed when the item is equipped
        Clobber with child objects
        :return: 
        '''
        pass

    def on_unequip(self, player):
        """
        Actions performed when the item is unequipped
        Clobber with child objects
        :return:
        """
        pass

    def drop(self, player):
        if hasattr(self, "count"):
            if getattr(self, "count") > 1:
                while True:
                    drop_count = input("How many would you like to drop? (Carrying {}) ".format(getattr(self, "count")))
                    if functions.is_input_integer(drop_count):
                        if 0 <= int(drop_count) <= getattr(self, "count"):
                            if int(drop_count) > 0:
                                cprint("Jean dropped {} x {}.".format(self.name, drop_count), "cyan")
                                for i in range(int(drop_count)):
                                    self.count -= 1
                                    itemtype = self.__class__.__name__
                                    player.current_room.spawn_item(item_type=itemtype)
                                player.current_room.stack_duplicate_items()
                            else:
                                print("Jean changed his mind.")
                            break
                        else:
                            cprint("Invalid amount!", "red")
                    else:
                        cprint("Invalid amount!", "red")
            else:
                cprint("Jean dropped {}.".format(self.name), "cyan")
                player.current_room.items_here.append(self)
                player.inventory.remove(self)
        else:
            cprint("Jean dropped {}.".format(self.name), "cyan")
            player.current_room.items_here.append(self)
            player.inventory.remove(self)
            if hasattr(self, "isequipped"):
                if getattr(self, "isequipped"):
                    self.isequipped = False  # noqa; attribute existence is checked above!
                    self.on_unequip(player)
                    self.interactions.remove("unequip")
                    self.interactions.append("equip")
                    if issubclass(self.__class__, Weapon):  # if the player is now unarmed, "equip" fists
                        player.eq_weapon = player.fists
        functions.refresh_stat_bonuses(player)
        player.refresh_protection_rating()

    def equip(self, player):
        player.equip_item(phrase="{}".format(self.name))

    def unequip(self, player):
        if hasattr(self, "isequipped"):
            self.isequipped = False  # noqa
            if issubclass(self.__class__, Weapon):  # if the player is now unarmed, "equip" fists
                player.eq_weapon = player.fists
            cprint("Jean put {} back into his bag.".format(self.name), "cyan")
            self.on_unequip(player)
            self.interactions.remove("unequip")
            self.interactions.append("equip")
            functions.refresh_stat_bonuses(player)
            player.refresh_protection_rating()


class Gold(Item):
    def __init__(self, amt=1):
        self.amt = functions.randomize_amount(amt)
        self.maintype = "Gold"
        super().__init__(name="Gold", description="A small pouch containing {} gold pieces.".format(str(self.amt)),
                         value=self.amt, maintype="Currency", subtype="Gold",
                         discovery_message="a small pouch of gold.")
        self.announce = "There's a small pouch of gold on the ground."
        self.interactions = []


class Weapon(Item):

    def __init__(self, name, description, value, damage, isequipped, str_req,
                 fin_req, str_mod, fin_mod, weight, maintype, subtype, wpnrange=(0, 5),
                 discovery_message='a kind of weapon.', twohand=False, skills=None, merchandise=False):
        self.damage = damage
        self.str_req = str_req
        self.fin_req = fin_req
        self.str_mod = str_mod
        self.fin_mod = fin_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        self.wpnrange = wpnrange  # tuple containing the min and max range for the weapon
        super().__init__(name, description, value, maintype, subtype, discovery_message, skills=skills, merchandise=merchandise)
        self.announce = "There's a {} here.".format(self.name)
        self.twohand = twohand
        self.gives_exp = True

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}\nRange: {}".format(self.name,
                                                                                                   self.description,
                                                                                                   self.value,
                                                                                                   self.damage,
                                                                                                   self.weight,
                                                                                                   self.wpnrange)
        else:
            return "{}\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}\nRange: {}".format(self.name, self.description,
                                                                                        self.value, self.damage,
                                                                                        self.weight, self.wpnrange)


class Armor(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, maintype, subtype,
                 discovery_message='a piece of armor.', merchandise=False):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise)  # announce="{} can be seen on the ground.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Boots(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, maintype, subtype,
                 discovery_message='a pair of footgear.', merchandise=False):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise)  # announce="A set of {} is laying here.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Helm(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, maintype, subtype,
                 discovery_message='a kind of head covering.', merchandise=False):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise)  # announce="A {} can be seen on the ground.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Gloves(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, maintype, subtype,
                 discovery_message='a pair of gloves.', merchandise=False):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise)  # announce="There is a pair of {} here.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Accessory(Item):
    def __init__(self, name, description, value, protection, isequipped, str_mod, fin_mod, weight, maintype, subtype,
                 discovery_message='a small trinket.', merchandise=False):
        self.protection = protection
        self.str_mod = str_mod
        self.fin_mod = fin_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        # self.level = level
        super().__init__(name, description, value, maintype, subtype, discovery_message, merchandise=merchandise)

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Consumable(Item):

    def __init__(self, name, description, value, weight, maintype, subtype,
                 discovery_message='a useful item.', count=1, merchandise=False):
        self.weight = weight
        self.maintype = maintype
        self.subtype = subtype
        self.count = count
        self.interactions = ["use", "drop"]
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise)  # announce="You notice a {} sitting here.".format(self.name))

    def stack_grammar(self):
        """Checks the stack count for the item and changes the verbiage accordingly"""
        pass

    def __str__(self):
        return "{}\n=====\n{}\n" \
               "Count: {}\n" \
               "Value: {} gold each, {} gold total\n" \
               "Weight: {} lbs each, {} lbs total".format(self.name, self.description, self.count, self.value,
                                                          self.value * self.count, self.weight,
                                                          self.weight * self.count)


class Special(Item):
    def __init__(self, name, description, value, weight, maintype, subtype, discovery_message='a strange object.', merchandise=False):
        self.weight = weight
        self.maintype = maintype
        self.subtype = subtype
        self.count = 1
        self.interactions = ["drop"]
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise)  # announce="You notice a {} sitting here.".format(self.name))

    def __str__(self):
        return "{}\n=====\n{}\nValue: {}\nWeight: {}".format(
            self.name, self.description, self.value, self.weight)


class Key(Special):
    def __init__(self, lock=None, merchandise=False):
        """
        Keys just sort of sit in inventory. They are "used" when the player uses 'unlock' on their paired lock
        :param lock: # Any object that has an 'unlock' method
        """

        super().__init__(name="Key",
                         description="A small, dull, metal key.",
                         value=0, weight=0, maintype="Special", subtype="Key", merchandise=merchandise)

        self.lock = lock  # Any object that has an 'unlock' method
        self.interactions = ["drop"]


class Crystals(Special):
    def __init__(self, merchandise=False):
        """
        Crystals are commodity drops from certain creatures like Rock Rumblers.
        They can also be found growing naturally in some caves and mountain areas.
        They can be sold to merchants. Gollem merchants will pay an increased rate for them since
        they are a source of food.
        """
        super().__init__(name="Crystals",
                         description="A beautiful collection of scintillating purple and aquamarine crystals. "
                                     "Interesting baubles to most, but a valuable"
                                     " food source to Rock Rumblers and their gentler cousins, the Grondites.",
                         value=10, weight=0.1, maintype="Special", subtype="Commodity", merchandise=merchandise)


class Fists(Weapon):  # equipped automatically when Jean has no other weapon equipped
    def __init__(self, merchandise=False):
        super().__init__(name="fists",
                         description="",
                         isequipped=True, value=0,
                         damage=1, str_req=1, fin_req=1, str_mod=1, fin_mod=1, weight=0.0,
                         maintype="Weapon", subtype="Unarmed", merchandise=merchandise)
        self.interactions = []


class Rock(Weapon):
    def __init__(self, merchandise=False):
        super().__init__(name="Rock",
                         description="A fist-sized rock, suitable for bludgeoning.",
                         isequipped=False, value=0,
                         damage=1, str_req=1, fin_req=1, str_mod=3.00, fin_mod=0.50, weight=2.0,
                         maintype="Weapon", subtype="Bludgeon", merchandise=merchandise)


class RustedIronMace(Weapon):
    level = 0
    def __init__(self, merchandise=False):
        super().__init__(name="Rusted Iron Mace",
                         description="A small mace with some rust around the spikes. Heavy and slow, "
                                     "but packs a decent punch.",
                         isequipped=False, value=10,
                         damage=15, str_req=10, fin_req=5, str_mod=2.25, fin_mod=0.5, weight=5.0, maintype="Weapon",
                         subtype="Bludgeon", merchandise=merchandise)


class Mace(Weapon):
    level = 1
    def __init__(self, merchandise=False):
        super().__init__(name="Mace",
                         description="A small mace. Heavy and slow, but packs a decent punch.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=5, str_mod=2, fin_mod=0.5, weight=5.0, maintype="Weapon",
                         subtype="Bludgeon", merchandise=merchandise)


class RustedDagger(Weapon):
    level = 0
    def __init__(self, merchandise=False):
        super().__init__(name="Rusted Dagger",
                         description="A small dagger with some rust. Somewhat more dangerous than a rock.",
                         isequipped=False, value=10,
                         damage=10, str_req=1, fin_req=12, str_mod=0.25, fin_mod=3, weight=1, maintype="Weapon",
                         subtype="Dagger", wpnrange=(0, 3), merchandise=merchandise)


class Dagger(Weapon):
    level = 1
    def __init__(self, merchandise=False):
        super().__init__(name="Dagger",
                         description="A rogue's best friend.",
                         isequipped=False, value=100,
                         damage=12, str_req=1, fin_req=12, str_mod=0.25, fin_mod=3, weight=1, maintype="Weapon",
                         subtype="Dagger", wpnrange=(0, 3), merchandise=merchandise)


class Baselard(Weapon):
    level = 1
    def __init__(self, merchandise=False):
        super().__init__(name="Baselard",
                         description="A small, sharp dagger with an 'H'-shaped hilt.",
                         isequipped=False, value=100,
                         damage=18, str_req=1, fin_req=12, str_mod=0.2, fin_mod=2.8, weight=1.2, maintype="Weapon",
                         subtype="Dagger", wpnrange=(0, 3), merchandise=merchandise)


class Shortsword(Weapon):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Shortsword",
                         description="A double-edged shortsword. A reliable companion in any fight.",
                         isequipped=False, value=100,
                         damage=25, str_req=5, fin_req=10, str_mod=0.75, fin_mod=1.25, weight=2, maintype="Weapon",
                         subtype="Sword", wpnrange=(0, 4), merchandise=merchandise)


class Epee(Weapon):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Epee",
                         description="A short dueling sword. Frequently used ceremonially, "
                                     "it is nonetheless effective in combat if wielded properly.\n"
                                     " While the long, thin blade does have a cutting edge, "
                                     "it is most effective with thrusting attacks or to parry an opponent.",
                         isequipped=False, value=100,
                         damage=25, str_req=5, fin_req=20, str_mod=0.5, fin_mod=2, weight=3, maintype="Weapon",
                         subtype="Sword", wpnrange=(0, 5), merchandise=merchandise)


class Battleaxe(Weapon):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Battleaxe",
                         description="A crescent blade affixed to a reinforced wooden haft. "
                                     "It is light and easy to swing.",
                         isequipped=False, value=100,
                         damage=25, str_req=5, fin_req=5, str_mod=1, fin_mod=0.5, weight=2, maintype="Weapon",
                         subtype="Axe", wpnrange=(0, 5), merchandise=merchandise)


class Pickaxe(Weapon):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Pickaxe",
                         description="A hardy weapon that can also be used to mine for rare metals, "
                                     "if the user is so-inclined. \n"
                                     "Difficult to wield at very close range.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=1, str_mod=2.5, fin_mod=0.1, weight=3, maintype="Weapon",
                         subtype="Pick", wpnrange=(1, 5), merchandise=merchandise)


class Scythe(Weapon):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Scythe",
                         description="An unusual weapon that, despite its intimidating appearance, "
                                     "is particularly difficult to wield. Requires two hands.",
                         isequipped=False, value=100,
                         damage=5, str_req=1, fin_req=1, str_mod=2, fin_mod=2, weight=7, maintype="Weapon",
                         subtype="Scythe", wpnrange=(1, 5), twohand=True, merchandise=merchandise)


class Spear(Weapon):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Spear",
                         description="A weapon of simple design and great effectiveness. \n"
                                     "Has a longer reach than most melee weapons but is not great at close range.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=1, str_mod=2, fin_mod=0.5, weight=3, maintype="Weapon",
                         subtype="Spear", wpnrange=(3, 8), merchandise=merchandise)


class Halberd(Weapon):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Halberd",
                         description="Essentially an axe mounted on top of a large pole. \n"
                                     "Has a longer reach than most melee weapons but is not great at close range.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=1, str_mod=1.75, fin_mod=1, weight=4, maintype="Weapon",
                         subtype="Spear", wpnrange=(3, 8), merchandise=merchandise)


class Hammer(Weapon):
    level = 0

    def __init__(self, merchandise=False):
        super().__init__(name="Hammer",
                         description="Great for smashing more heavily-armored foes.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=1, str_mod=2.5, fin_mod=0.1, weight=3, maintype="Weapon",
                         subtype="Bludgeon", merchandise=merchandise)


class Shortbow(Weapon):
    level = 0

    def __init__(self, merchandise=False):
        super().__init__(name="Shortbow",
                         description="A reliable missile weapon. Useful as a weak bludgeon at close range.\n"
                                     "Requires two hands.",
                         isequipped=False, value=50,
                         damage=8, str_req=5, fin_req=5, str_mod=1, fin_mod=1, weight=1.5, maintype="Weapon",
                         subtype="Bow", merchandise=merchandise)
        self.range_base = 20  # this will affect the accuracy and power of the shot;
        # range is the distance when the effect begins
        self.range_decay = 0.05  # the rate of decay for accuracy and damage after base range is reached


class Longbow(Weapon):
    level = 0

    def __init__(self, merchandise=False):
        super().__init__(name="Longbow",
                         description="Specialized bow for shooting long distances. Useful as a weak bludgeon at "
                                     "close range.\n"
                                     "Requires two hands.",
                         isequipped=False, value=100,
                         damage=8, str_req=5, fin_req=5, str_mod=1, fin_mod=1, weight=2, maintype="Weapon",
                         subtype="Bow", merchandise=merchandise)
        self.range_base = 25
        self.range_decay = 0.04


class Crossbow(Weapon):
    level = 0

    def __init__(self, merchandise=False):
        super().__init__(name="Crossbow",
                         description="Heavier than a standard bow but able to fire more rapidly. "
                                     "It fires bolts instead of arrows.\n"
                                     "Requires two hands.",
                         isequipped=False, value=100,
                         damage=20, str_req=5, fin_req=5, str_mod=1.5, fin_mod=1, weight=4, maintype="Weapon",
                         subtype="Crossbow", merchandise=merchandise)
        self.range_base = 15
        self.range_decay = 0.06


class Pole(Weapon):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Pole",
                         description="A large pole, great for delivering blows from a distance. \n"
                                     "Has a longer reach than most melee weapons but is not great at close range.",
                         isequipped=False, value=100,
                         damage=25, str_req=5, fin_req=5, str_mod=1.25, fin_mod=1.25, weight=2, maintype="Weapon",
                         subtype="Polearm", wpnrange=(2, 7), merchandise=merchandise)


class TatteredCloth(Armor):
    level = 0

    def __init__(self, merchandise=False):
        super().__init__(name="Tattered Cloth",
                         description="Shamefully tattered cloth wrappings. \n"
                                     "Lightweight, but offering little in protection.",
                         isequipped=False, value=0,
                         protection=1, str_req=1, str_mod=0.1, weight=0.5, maintype="Armor", subtype="Light Armor", merchandise=merchandise)
        # minimum protection of 2


class ClothHood(Helm):
    level = 0

    def __init__(self, merchandise=False):
        super().__init__(name="Cloth Hood",
                         description="Stained cloth hood. "
                                     "Enough to conceal your face, but that's about it.",
                         isequipped=False, value=0,
                         protection=0, str_req=1, str_mod=0.1, weight=0.5, maintype="Helm", subtype="Light Helm", merchandise=merchandise)
        self.add_fin = 1
        # minimum protection of 1


class DullMedallion(Accessory):
    def __init__(self, merchandise=False):
        super().__init__(name="Dull Medallion",
                         description="A rather unremarkable medallion. \n"
                                     "It's face is dull, and seems to swallow any light unlucky enough to "
                                     "land upon it. \n"
                                     "It may have been a family heirloom or a memento of a lost love.",
                         isequipped=False, value=25,
                         protection=0, str_mod=0, fin_mod=0, weight=0.5, maintype="Accessory", subtype="Necklace", merchandise=merchandise)

    def on_equip(self, player):
        cprint("Jean feels a slight chill as the medallion's chain settles on his neck.", "green")
        player.combat_idle_msg.append("Jean feels the soft caress of a stranger's hand on his cheek.")
        player.combat_idle_msg.append("A faint whisper of unknown origin passes quickly through Jean's mind.")
        player.combat_idle_msg.append("For an instant, Jean thought he saw the face of an unknown woman.")
        player.combat_idle_msg.append("A sharp feeling of grief suddenly grips Jean's chest.")
        player.combat_idle_msg.append("Jean suddenly imagined his wife coughing up blood.")
        player.combat_idle_msg.append("A sense of urgency and desperation suddenly fills Jean.")
        player.combat_idle_msg.append("The words, 'Cherub Root,' flash across Jean's mind.")

    def on_unequip(self, player):
        cprint("Removing the medallion gives Jean a strange sense of relief, but also inexplicable sadness.", "green")
        player.combat_idle_msg.remove("Jean feels the soft caress of a stranger's hand on his cheek.")
        player.combat_idle_msg.remove("A faint whisper of unknown origin passes quickly through Jean's mind.")
        player.combat_idle_msg.remove("For an instant, Jean thought he saw the face of an unknown woman.")
        player.combat_idle_msg.remove("A sharp feeling of grief suddenly grips Jean's chest.")
        player.combat_idle_msg.remove("Jean suddenly imagined his wife coughing up blood.")
        player.combat_idle_msg.remove("A sense of urgency and desperation suddenly fills Jean.")
        player.combat_idle_msg.remove("The words, 'Cherub Root,' flash across Jean's mind.")


class GoldRing(Accessory):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Gold Ring",
                         description="A shiny gold ring. \n"
                                     "Typically a sign of marital vows, though it may also be worn to exhibit wealth.",
                         isequipped=False, value=200,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Ring", merchandise=merchandise)


class JeanWeddingBand(Accessory):
    level = 99
    add_faith = 1
    add_endurance = 1
    add_charisma = -1

    def __init__(self, merchandise=False):
        super().__init__(name="Wedding Band",
                         description="A shiny gold ring with some intricate patterns carved into it. \n"
                                     "The faded inscription on the inner wall of the ring reads, 'AMELIA.' \n"
                                     "This is an item of special interest to Jean. "
                                     "Some things are too difficult to let go.",
                         isequipped=True, value=900,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Ring", merchandise=merchandise)
        self.interactions.remove("drop")
        # self.add_resistance["fire"] = -0.5
        # self.add_status_resistance["poison"] = -0.75

    def on_equip(self, player):
        if len(self.equip_states) > 0:
            for state in self.equip_states:
                player.apply_state(state)
        print(
            "As he slides on the band, Jean's face appears placid. "
            "His heart, however, is filled with sadness, and a coldness grips his stomach.")

    def on_unequip(self, player):
        print("Jean's frown twitches slightly as his finger is released from the weight of the band. "
              "He glances briefly at the faded inscription on the ring's inner wall "
              "before stuffing the small baubel into his bag.")


class SilverRing(Accessory):
    level = 0

    def __init__(self, merchandise=False):
        super().__init__(name="Silver Ring",
                         description="A shiny silver ring. \n"
                                     "A small bauble favored by people of typically lower class.",
                         isequipped=False, value=50,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Ring", merchandise=merchandise)


class GoldChain(Accessory):
    level = 2

    def __init__(self, merchandise=False):
        super().__init__(name="Gold Chain",
                         description="A shiny gold chain. \n"
                                     "Worn to impress. An excellent gift for a lady.",
                         isequipped=False, value=300,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Necklace", merchandise=merchandise)


class SilverChain(Accessory):
    level = 1

    def __init__(self, merchandise=False):
        super().__init__(name="Silver Chain",
                         description="A shiny silver chain. \n"
                                     "An excellent gift for a lady who has simple tastes.",
                         isequipped=False, value=100,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Necklace", merchandise=merchandise)


class GoldBracelet(Accessory):
    level = 2

    def __init__(self, merchandise=False):
        super().__init__(name="Gold Bracelet",
                         description="A shiny gold bracelet. \n"
                                     "Everyone knows that you need to accessorize in order to make an impression.",
                         isequipped=False, value=300,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Bracelet", merchandise=merchandise)


class SilverBracelet(Accessory):
    level = 0

    def __init__(self, merchandise=False):
        super().__init__(name="Silver Bracelet",
                         description="A shiny silver bracelet. \n"
                                     "More of an eccentricity than anything else.",
                         isequipped=False, value=100,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Bracelet", merchandise=merchandise)


class Restorative(Consumable):
    def __init__(self, count=1, merchandise=False):
        super().__init__(name="Restorative",
                         description="A strange pink fluid of questionable chemistry.\n"
                                     "Drinking it seems to cause your wounds to immediately mend "
                                     "themselves.",
                         value=100, weight=0.25, maintype="Consumable", subtype="Potion", count=count, merchandise=merchandise)
        self.power = 60
        self.count = count  # this will allow stacking of homogeneous items. At each game loop,
        # the game searches the inventory for other copies and increases that count by self.count,
        # then removes this object
        self.interactions = ["use", "drink", "drop"]
        self.announce = "Jean notices a small glass vial on the ground with an odd pink fluid inside and a label " \
                        "reading, 'Restorative.'"

    def stack_grammar(self):
        if self.count > 1:
            self.description = "A box filled with vials of a strange pink fluid.\n" \
                               "Drinking one would seem to cause your wounds to immediately mend themselves.\n" \
                               "There appear to be {} vials in the box.\n".format(self.count)
            self.announce = "There is a box of small glass vials here."
        else:
            self.description = "A strange pink fluid of questionable chemistry.\n" \
                               "Drinking it seems to cause your wounds to immediately mend " \
                               "themselves."
            self.announce = "Jean notices a small glass vial on the ground with an odd pink fluid inside and a label " \
                            "reading, 'Restorative.'"

    def drink(self, player):  # alias for "use"
        self.use(player)

    def use(self, player):
        if player.hp < player.maxhp:
            print(
                "Jean quaffs down the Restorative. The liquid burns slightly in his throat for a moment, before the \n"
                "sensation is replaced with a period of numbness. He feels his limbs getting a bit lighter, his \n"
                "muscles relaxing, and the myriad of scratches and cuts closing up.\n")
            amount = (self.power * random.uniform(0.8, 1.2))
            amount = int(amount)
            missing_hp = player.maxhp - player.hp
            if amount > missing_hp:
                amount = missing_hp
            player.hp += amount
            time.sleep(2)
            cprint("Jean recovered {} HP!".format(amount), "green")
            self.count -= 1
            self.stack_grammar()
            if self.count <= 0:
                player.inventory.remove(self)
        else:
            print("Jean is already at full health. He places the Restorative back into his bag.")


class Draught(Consumable):
    def __init__(self, count=1, merchandise=False):
        super().__init__(name="Draught",
                         description="A green fluid giving off a warm, pleasant glow.\n"
                                     "Invigorating for any tired adventurer.",
                         value=75, weight=0.25, maintype="Consumable", subtype="Potion", count=count, merchandise=merchandise)
        self.power = 100
        self.count = count
        self.interactions = ["use", "drink", "drop"]
        self.announce = ("Jean notices a small glass bottle of glowing green fluid on the ground. "
                         "Its label reads, simply, 'Draught.'")

    def stack_grammar(self):
        if self.count > 1:
            self.description = "A box filled with bottles of a green fluid giving off a warm, pleasant glow.\n" \
                               "Invigorating for any tired adventurer.\n" \
                               "There appear to be {} bottles in the box.\n".format(self.count)
            self.announce = "There is a box of small glass bottles here."
        else:
            self.description = "A green fluid giving off a warm, pleasant glow.\n" \
                               "Invigorating for any tired adventurer."
            self.announce = ("Jean notices a small glass bottle of glowing green fluid on the ground. "
                             "Its label reads, simply, 'Draught.'")

    def drink(self, player):  # alias for "use"
        self.use(player)

    def use(self, player):
        if player.hp < player.maxhp:
            print("Jean gulps down the {}. It's surprisingly sweet and warm. The burden of fatigue seems \n"
                  "to have lifted off of his shoulders for the time being.".format(self.name))
            amount = (self.power * random.uniform(0.8, 1.2))
            amount = int(amount)
            missing_fatigue = player.maxfatigue - player.fatigue
            if amount > missing_fatigue:
                amount = missing_fatigue
            player.fatigue += amount
            time.sleep(2)
            cprint("Jean recovered {} fatigue!".format(amount), "green")
            self.count -= 1
            self.stack_grammar()
            if self.count <= 0:
                player.inventory.remove(self)
        else:
            print("Jean is already fully rested. He places the {} back into his bag.".format(self.name))


class Antidote(Consumable):
    def __init__(self, count=1, merchandise=False):
        super().__init__(name="Antidote",
                         description="A murky green fluid of questionable chemistry.\n"
                                     "Drinking it restores a small amount of health and \n"
                                     "neutralizes harmful toxins in the bloodstream.",
                         value=175, weight=0.25, maintype="Consumable", subtype="Potion", count=count, merchandise=merchandise)
        self.power = 15
        self.count = count  # this will allow stacking of homogeneous items. At each game loop,
        # the game searches the inventory for other copies and increases that count by self.count,
        # then removes this object
        self.interactions = ["use", "drink", "drop"]
        self.announce = "Jean notices a small glass bottle on the ground with a murky green fluid inside and a label " \
                        "reading, 'Antidote.'"

    def stack_grammar(self):
        if self.count > 1:
            self.description = "A box filled with bottles of a murky green fluid.\n" \
                               "Drinking one restores a small amount of health and \n" \
                               "neutralizes harmful toxins in the bloodstream. \n" \
                               "There appear to be {} vials in the box.\n".format(self.count)
            self.announce = "There is a box of small glass bottles here."
        else:
            self.description = "A murky green fluid of questionable chemistry.\n" \
                               "Drinking it restores a small amount of health and \n" \
                               "neutralizes harmful toxins in the bloodstream."
            self.announce = ("Jean notices a small glass bottle on the ground with a murky green "
                             "fluid inside and a label reading, 'Antidote.'")

    def drink(self, player):  # alias for "use"
        self.use(player)

    def use(self, player):
        poisons = []
        for state in player.states:
            if hasattr(state, "statustype"):
                if state.statustype == "poison":
                    poisons.append(state)

        if poisons:
            print("Jean sips gingerly at the Antidote. The liquid feels very cool as it slides thickly down \n"
                  "his throat. He shudders uncontrollably for a moment as the medicine flows into his \n"
                  "bloodstream, doing its work on whatever toxic agent made its home there.\n")
            amount = (self.power * random.uniform(0.8, 1.2))
            amount = int(amount)
            missing_hp = player.maxhp - player.hp
            if missing_hp > 0:
                if amount > missing_hp:
                    amount = missing_hp
                player.hp += amount
                time.sleep(2)
                cprint("Jean recovered {} HP!".format(amount), "green")
            for poison in poisons:
                poison.on_removal(poison.target)
                player.states.remove(poison)
            self.count -= 1
            self.stack_grammar()
            if self.count <= 0:
                player.inventory.remove(self)
            return
        else:
            print("Jean is not beset by poison. He places the Antidote back into his bag.")


class Arrow(Consumable):  # master class for arrows. Actual arrows are subclasses (like WoodenArrow, IronArrow, etc.)
    def __init__(self, name, description, value, weight, power, range_base_modifier, range_decay_modifier, sturdiness,
                 helptext, effects, count=1, merchandise=False):
        super().__init__(name=name, description=description, value=value, weight=weight, maintype="Consumable",
                         subtype="Arrow", count=count, merchandise=merchandise)
        self.power = power
        self.count = count  # this will allow stacking of homogeneous items. At each game loop,
        # the game searches the inventory for other copies and increases that count by self.count,
        # then removes this object
        self.interactions = ["drop", "prefer"]
        self.announce = "Jean notices an arrow on the ground."
        self.range_base_modifier = range_base_modifier  # multiplies the bow's base range by this amount
        self.range_decay_modifier = range_decay_modifier  # multiplies the bow's base decay by this amount
        self.sturdiness = sturdiness  # frequency that an arrow fired at an enemy will survive to be picked up again
        self.helptext = helptext  # appears next to the arrow when the player is
        # choosing after using the Shoot Arrow move
        self.effects = effects

    def stack_grammar(self):
        if self.count > 1:
            self.description = "A quiver of {}s.\n" \
                               "There appear to be {} arrows in the quiver.\n".format(self.name.lower(), self.count)
            self.announce = "There is a quiver of arrows here."
        else:
            self.description = "A standard arrow, to be fired with a bow."
            self.announce = "Jean notices an arrow on the ground."

    def prefer(self, player):
        functions.add_preference(player, "arrow", self.name)


class WoodenArrow(Arrow):
    def __init__(self, count=1, merchandise=False):
        super().__init__(name="Wooden Arrow",
                         description="A useful device composed of a sharp tip, a shaft of sorts, and fletching. \n"
                                     "This one is made of wood. Wooden arrows are lightweight, "
                                     "so they generally improve accuracy at the cost of impact force. "
                                     "\nThey tend to break frequently.",
                         value=1, weight=0.05, power=20, range_base_modifier=1.2, range_decay_modifier=0.8,
                         sturdiness=0.4,
                         helptext=colored("+range, -decay, ", "green") + colored("-damage, -sturdiness", "red"),
                         effects=None, count=count, merchandise=merchandise)


class IronArrow(Arrow):
    def __init__(self, count=1, merchandise=False):
        super().__init__(name="Iron Arrow", description="A useful device composed of a sharp tip, "
                                                        "a shaft of sorts, and fletching. \
        This one is made of iron. Iron arrows are heavy and can be devastating up close. "
                                                        "They suffer, however, when it comes to range and "
                                                        "accuracy over long \
        distances. \nLike all metal arrows, they are considerably sturdier than other types of arrows.",
                         value=5, weight=0.25, power=30, range_base_modifier=0.7, range_decay_modifier=1.4,
                         sturdiness=0.6,
                         helptext=colored("+damage, +sturdiness, ", "green") + colored("-range, ++decay", "red"),
                         effects=None, count=count, merchandise=merchandise)


class GlassArrow(Arrow):
    def __init__(self, count=1, merchandise=False):
        super().__init__(name="Glass Arrow", description="A useful device composed of a sharp tip, "
                                                         "a shaft of sorts, and fletching. \
        This one is made of glass. It is of moderate weight and extremely sharp. \nAs you might expect, "
                                                         "arrows like this rarely survive the first shot.",
                         value=10, weight=0.1, power=40, range_base_modifier=1.1, range_decay_modifier=1,
                         sturdiness=0.1,
                         helptext=colored("+range, +damage, ", "green") + colored("~decay, ", "yellow") + colored(
                             "---sturdiness", "red"), effects=None, count=count, merchandise=merchandise)


class FlareArrow(Arrow):
    def __init__(self, count=1, merchandise=False):
        super().__init__(name="Flare Arrow", description="A useful device composed of a sharp tip, a shaft of sorts, "
                                                         "and fletching. \
        This one is made of wood and bursts into flames upon impact."
                                                         "\nObviously, don't expect to get it back after firing.",
                         value=10, weight=0.05, power=25, range_base_modifier=1.2, range_decay_modifier=0.8,
                         sturdiness=0.0,
                         helptext=colored("+range, +damage, -decay, ", "green") + colored("----sturdiness", "red"),
                         effects=None, count=count, merchandise=merchandise)
        # todo add fire effect on impact
