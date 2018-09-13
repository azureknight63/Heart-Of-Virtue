import random, time
from termcolor import colored, cprint
import functions

class Item():
    """The base class for all items"""
    def __init__(self, name, description, value, maintype, subtype, discovery_message, hidden=False, hide_factor=0):
        self.name = name
        self.description = description
        self.value = value
        self.type = maintype
        self.subtype = subtype
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        #self.level = level  # used for categorizing items in loot tables
        self.announce = "There's a {} here.".format(self.name)
        self.interactions = []  # things to do with the item from the inventory menu - player must be passed as a parameter

    def __str__(self):
        return "{}\n=====\n{}\nValue: {}\n".format(self.name, self.description, self.value)
    
    def on_equip(self, player):
        '''
        Actions performed when the item is equipped
        Clobber with child objects
        :return: 
        '''
        pass
    
    def on_unequip(self, player):
        '''
        Actions performed when the item is unequipped
        Clobber with child objects
        :return: 
        '''
        pass


class Gold(Item):
    def __init__(self, amt=1):
        self.amt = functions.randomize_amount(amt)
        self.maintype = "Gold"
        super().__init__(name="Gold", description="A small pouch containing {} gold pieces.".format(str(self.amt)),
                         value=self.amt, maintype="Currency", subtype="Gold", discovery_message="a small pouch of gold.")
        self.announce = "There's a small pouch of gold on the ground."


class Weapon(Item):
    subtypes = [
        "Dagger",
        "Sword",
        "Battleaxe",
        "Pick",
        "Scythe",
        "Spear",
        "Halberd",
        "Bludgeon",
        "Hammer",
        "Bow",
        "Crossbow",
        "Polearm",
        "Stars",
        "Staff",
        "Ethereal"
    ]
    archetypes = {  # groups of similar subtypes; useful for checking requirements
        "All": subtypes,
        "Blade": ["Dagger", "Sword", "Battleaxe", "Pick", "Scythe", "Spear", "Halberd"],
        "Blunt": ["Bludgeon", "Hammer", "Polearm", "Staff"],
        "Archery": ["Bow", "Crossbow"],
        "Ranged": ["Bow", "Crossbow", "Stars"],
        "Melee": ["Dagger", "Sword", "Battleaxe", "Pick", "Scythe", "Spear", "Halberd", "Bludgeon", "Hammer", "Polearm", "Staff"]
    }

    def __init__(self, name, description, value, damage, isequipped, str_req,
                 fin_req, str_mod, fin_mod, weight, maintype, subtype, wpnrange=(0,5), discovery_message='a kind of weapon.'):
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
        super().__init__(name, description, value, maintype, subtype, discovery_message)
        self.announce = "There's a {} here.".format(self.name)

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}\nRange: {}".format(self.name,
                                                                            self.description, self.value, self.damage,
                                                                            self.weight, self.wpnrange)
        else:
            return "{}\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}\nRange: {}".format(self.name, self.description,
                                                                 self.value, self.damage, self.weight, self.wpnrange)


class Armor(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, maintype, subtype,
                 discovery_message='a piece of armor.'):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype, discovery_message) #announce="{} can be seen on the ground.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Boots(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, maintype, subtype,
                 discovery_message='a pair of footgear.'):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype, discovery_message) #announce="A set of {} is laying here.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Helm(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, maintype, subtype,
                 discovery_message='a kind of head covering.'):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype, discovery_message) # announce="A {} can be seen on the ground.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Gloves(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, maintype, subtype,
                 discovery_message='a pair of gloves.'):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype, discovery_message) # announce="There is a pair of {} here.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Accessory(Item):
    def __init__(self, name, description, value, protection, isequipped, str_mod, fin_mod, weight, maintype, subtype,
                 discovery_message='a small trinket.'):
        self.protection = protection
        self.str_mod = str_mod
        self.fin_mod = fin_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        #self.level = level
        super().__init__(name, description, value, maintype, subtype, discovery_message)

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Consumable(Item):

    def __init__(self, name, description, value, weight, maintype, subtype, discovery_message='a useful item.'):
        self.weight = weight
        self.maintype = maintype
        self.subtype = subtype
        self.count = 1
        self.interactions = ["use", "drop"]
        super().__init__(name, description, value, maintype, subtype, discovery_message)  # announce="You notice a {} sitting here.".format(self.name))

    def stack_grammar(self):
        '''Checks the stack count for the item and changes the verbiage accordingly'''
        pass

    def __str__(self):
         return "{}\n=====\n{}\n" \
                "Count: {}\n" \
                "Value: {} gold each, {} gold total\n" \
                "Weight: {} lbs each, {} lbs total".format(self.name, self.description, self.count, self.value,
                                                           self.value * self.count, self.weight, self.weight * self.count)

    def drop(self, player):
        if self.count > 1:
            while True:
                drop_count = input("How many would you like to drop? ")
                if functions.is_input_integer(drop_count):
                    if 0 <= int(drop_count) <= self.count:
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


class Special(Item):
    def __init__(self, name, description, value, weight, maintype, subtype, discovery_message='a strange object.'):
        self.weight = weight
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype, discovery_message) # announce="You notice a {} sitting here.".format(self.name))

    def __str__(self):
         return "{}\n=====\n{}\nValue: {}\nWeight: {}".format(
            self.name, self.description, self.value, self.weight)


class Key(Special):
    def __init__(self, lock=None):
        '''
        Keys just sort of sit in inventory. They are "used" when the player uses 'unlock' on their paired lock
        :param lock: # Any object that has an 'unlock' method
        '''

        super().__init__(name="Key",
                         description="A small, dull, metal key.",
                         value=0, weight=0, maintype="Special", subtype="Key")

        self.lock = lock  # Any object that has an 'unlock' method


class Fists(Weapon):  # equipped automatically when Jean has no other weapon equipped
    def __init__(self):
        super().__init__(name="fists",
                         description="",
                         isequipped=True, value=0,
                         damage=1, str_req=1, fin_req=1, str_mod=1, fin_mod=1, weight=0.0,
                         maintype="Weapon", subtype="Bludgeon")


class Rock(Weapon):
    def __init__(self):
        super().__init__(name="Rock",
                         description="A fist-sized rock, suitable for bludgeoning.",
                         isequipped=False, value=0,
                         damage=1, str_req=1, fin_req=1, str_mod=2.00, fin_mod=0.50, weight=2.0,
                         maintype="Weapon", subtype="Bludgeon")
        #minimum damage of 26


class RustedDagger(Weapon):
    level = 0
    def __init__(self):
        super().__init__(name="Rusted Dagger",
                         description="A small dagger with some rust. Somewhat more dangerous than a rock.",
                         isequipped=False, value=10,
                         damage=10, str_req=1, fin_req=12, str_mod=0.5, fin_mod=2, weight=1.5, maintype="Weapon",
                         subtype="Dagger", wpnrange=(1,3))
        #minimum damage of 37


class RustedIronMace(Weapon):
    level = 0
    def __init__(self):
        super().__init__(name="Rusted Iron Mace",
                         description="A small mace with some rust around the spikes. Heavy and slow, but packs a decent punch.",
                         isequipped=False, value=10,
                         damage=25, str_req=10, fin_req=5, str_mod=2, fin_mod=0.5, weight=3.0, maintype="Weapon",
                         subtype="Bludgeon")
        #minimum damage of 40

class TatteredCloth(Armor):
    level = 0
    def __init__(self):
        super().__init__(name="Tattered Cloth",
                         description="Shamefully tattered cloth wrappings. \n"
                                     "Lightweight, but offering little in protection.",
                         isequipped=False, value=0,
                         protection=1, str_req=1, str_mod=0.1, weight=0.5, maintype="Armor", subtype="Light Armor")
        #minimum protection of 2


class ClothHood(Helm):
    level = 0
    def __init__(self):
        super().__init__(name="Cloth Hood",
                         description="Stained cloth hood. "
                                     "Enough to conceal your face, but that's about it.",
                         isequipped=False, value=0,
                         protection=0, str_req=1, str_mod=0.1, weight=0.5, maintype="Helm", subtype="Light Helm")
        self.add_fin = 1
        #minimum protection of 1


class DullMedallion(Accessory):
    def __init__(self):
        super().__init__(name="Dull Medallion",
                         description="A rather unremarkable medallion. \n"
                                     "It's face is dull, and seems to swallow any light unlucky enough to land upon it. \n"
                                     "It may have been a family heirloom or a memento of a lost love.",
                         isequipped=False, value=10,
                         protection=0, str_mod=0, fin_mod=0, weight=0.5, maintype="Accessory", subtype="Necklace")
        
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
    def __init__(self):
        super().__init__(name="Gold Ring",
                         description="A shiny gold ring. \n"
                                     "Typically a sign of marital vows, though it may also be worn to exhibit wealth.",
                         isequipped=False, value=200,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Ring")


class SilverRing(Accessory):
    level = 0
    def __init__(self):
        super().__init__(name="Silver Ring",
                         description="A shiny silver ring. \n"
                                     "A small bauble favored by people of typically lower class.",
                         isequipped=False, value=50,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Ring")


class GoldChain(Accessory):
    level = 2
    def __init__(self):
        super().__init__(name="Gold Chain",
                         description="A shiny gold chain. \n"
                                     "Worn to impress. An excellent gift for a lady.",
                         isequipped=False, value=300,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Necklace")


class SilverChain(Accessory):
    level = 1
    def __init__(self):
        super().__init__(name="Silver Chain",
                         description="A shiny silver chain. \n"
                                     "An excellent gift for a lady who has simple tastes.",
                         isequipped=False, value=100,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Necklace")


class GoldBracelet(Accessory):
    level = 2
    def __init__(self):
        super().__init__(name="Gold Bracelet",
                         description="A shiny gold bracelet. \n"
                                     "Everyone knows that you need to accessorize in order to make an impression.",
                         isequipped=False, value=300,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Bracelet")


class SilverBracelet(Accessory):
    level = 0
    def __init__(self):
        super().__init__(name="Silver Bracelet",
                         description="A shiny silver bracelet. \n"
                                     "More of an eccentricity than anything else.",
                         isequipped=False, value=100,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Bracelet")


class Restorative(Consumable):
    def __init__(self):
        super().__init__(name="Restorative",
                         description="A strange pink fluid of questionable chemistry.\n"
                                     "Drinking it seems to cause your wounds to immediately mend "
                                     "themselves.",
                         value=100, weight=0.25, maintype="Consumable", subtype="Potion")
        self.power = 60
        self.count = 1  # this will allow stacking of homogeneous items. At each game loop,
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
            print("Jean quaffs down the Restorative. The liquid burns slightly in his throat for a moment, before the \n"
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
    def __init__(self):
        super().__init__(name="Draught",
                         description="A green fluid giving off a warm, pleasant glow.\n"
                                     "Invigorating for any tired adventurer.",
                         value=75, weight=0.25, maintype="Consumable", subtype="Potion")
        self.power = 100
        self.count = 1
        self.interactions = ["use", "drink", "drop"]
        self.announce = "Jean notices a small glass bottle of glowing green fluid on the ground. Its label reads, simply, 'Draught.'"

    def stack_grammar(self):
        if self.count > 1:
            self.description = "A box filled with bottles of a green fluid giving off a warm, pleasant glow.\n" \
                               "Invigorating for any tired adventurer.\n" \
                               "There appear to be {} bottles in the box.\n".format(self.count)
            self.announce = "There is a box of small glass bottles here."
        else:
            self.description = "A green fluid giving off a warm, pleasant glow.\n" \
                                     "Invigorating for any tired adventurer."
            self.announce = "Jean notices a small glass bottle of glowing green fluid on the ground. Its label reads, simply, 'Draught.'"

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
