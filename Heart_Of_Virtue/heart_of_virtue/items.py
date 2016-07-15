import random

class Item():
    """The base class for all items"""
    def __init__(self, name, description, value, type, subtype):
        self.name = name
        self.description = description
        self.value = value
        self.type = type #is it currency, a weapon, key item? This should be a string since it will be printed to the player at times
        self.subtype = subtype #is it gold, a dagger, a door key? This should be a string since it will be printed to the player at times

    def __str__(self):
        return "{}\n=====\n{}\nValue: {}\n".format(self.name, self.description, self.value)

class Gold(Item):
    def __init__(self, amt):
        self.amt = amt
        super().__init__(name="Gold", description="A small pouch containing {} gold pieces.".format(str(self.amt)),
                         value=self.amt, type="Currency", subtype="Gold")
        self.announce = "There's a small pouch of gold on the ground."

class Weapon(Item):
    def __init__(self, name, description, value, damage, isequipped, str_req,
                 fin_req, str_mod, fin_mod, weight, type, subtype):
        self.damage = damage
        self.str_req = str_req
        self.fin_req = fin_req
        self.str_mod = str_mod
        self.fin_mod = fin_mod
        self.weight = weight
        self.isequipped = isequipped
        self.type = type
        self.subtype = subtype
        super().__init__(name, description, value, type, subtype)
        self.announce = "There's a {} here.".format(self.name)

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}".format(self.name, self.description,
                                                                            self.value, self.damage, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}".format(self.name, self.description,
                                                                 self.value, self.damage, self.weight)

class Armor(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, type, subtype):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.type = type
        self.subtype = subtype
        super().__init__(name, description, value, type, subtype) #announce="{} can be seen on the ground.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)

class Boots(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, type, subtype):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.type = type
        self.subtype = subtype
        super().__init__(name, description, value, type, subtype) #announce="A set of {} is laying here.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)

class Helm(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, type, subtype):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.type = type
        self.subtype = subtype
        super().__init__(name, description, value, type, subtype) # announce="A {} can be seen on the ground.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)

class Gloves(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight, type, subtype):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.type = type
        self.subtype = subtype
        super().__init__(name, description, value, type, subtype) # announce="There is a pair of {} here.".format(self.name))

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)

class Consumable(Item):
    def __init__(self, name, description, value, weight, type, subtype):
        self.weight = weight
        self.type = type
        self.subtype = subtype
        super().__init__(name, description, value, type, subtype) # announce="You notice a {} sitting here.".format(self.name))

    def __str__(self):
         return "{}\n=====\n{}\nValue: {}\nWeight: {}".format(
            self.name, self.description, self.value, self.weight)

class Special(Item):
    def __init__(self, name, description, value, weight, type, subtype):
        self.weight = weight
        self.type = type
        self.subtype = subtype
        super().__init__(name, description, value, type, subtype) # announce="You notice a {} sitting here.".format(self.name))

    def __str__(self):
         return "{}\n=====\n{}\nValue: {}\nWeight: {}".format(
            self.name, self.description, self.value, self.weight)

class Rock(Weapon):
    def __init__(self):
        super().__init__(name="Rock",
                         description="A fist-sized rock, suitable for bludgeoning.",
                         isequipped=False, value=0,
                         damage=1, str_req=1, fin_req=1, str_mod=2.00, fin_mod=0.50, weight=2.0,
                         type="Weapon", subtype="Bludgeon")
        #minimum damage of 26

class RustedDagger(Weapon):
    def __init__(self):
        super().__init__(name="Rusted Dagger",
                         description="A small dagger with some rust. Somewhat more dangerous than a rock.",
                         isequipped=False, value=10,
                         damage=10, str_req=1, fin_req=12, str_mod=0.5, fin_mod=2, weight= 1.5, type="Weapon",
                         subtype="Dagger")
        #minimum damage of 37

class TatteredCloth(Armor):
    def __init__(self):
        super().__init__(name="Tattered Cloth",
                         description="Shamefully tattered cloth wrappings. "
                                     "Lightweight, but offering little in protection.",
                         isequipped=False, value=0,
                         protection=1, str_req=1, str_mod=0.1, weight= 0.5, type="Armor", subtype="Light Armor")
        #minimum protection of 2

class ClothHood(Helm):
    def __init__(self):
        super().__init__(name="Cloth Hood",
                         description="Stained cloth hood. "
                                     "Enough to conceal your face, but that's about it.",
                         isequipped=False, value=0,
                         protection=0, str_req=1, str_mod=0.1, weight= 0.5, type="Helm", subtype="Light Helm")
        self.add_fin = 1
        #minimum protection of 1

class Restorative(Consumable):
    def __init__(self):
        super().__init__(name="Restorative",
                         description="A strange pink fluid of questionable chemistry.\n"
                                     "Drinking it seems to cause your wounds to immediately mend "
                                     "themselves",
                         value=100, weight=0.25, type="Consumable", subtype="Potion")
        self.power = 60
        self.count = 1  # this will allow stacking of homogeneous items. When the player acquires this in inventory,
                        # the game searches the inventory for other copies and increases that count by self.count,
                        # then removes this object todo: implement item stacking on item pickup
        self.announce = "You notice a small glass bottle on the ground with an odd pink fluid inside and a label " \
                        "reading, 'Restorative.'"

    def use(self, player):
        if player.hp < player.maxhp:
            print("You quaff down the restorative. The liquid burns slightly in your throat for a moment, before the "
                  "sensation is replaced with a period of numbness. You feel your limbs getting a bit lighter, your "
                  "muscles relaxing, and the myriad of scratches and cuts closing up.")
            player.hp += (self.power * random.uniform(0.8, 1.2))
            if player.hp > player.maxhp:
                player.hp = player.maxhp
            self.count -= 1
            if self.count <= 0:
                player.inventory.remove(self)
        else:
            print("You are already at full health. You place the Restorative back in your bag.")
