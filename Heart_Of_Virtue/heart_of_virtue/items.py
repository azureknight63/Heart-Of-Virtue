class Item():
    """The base class for all items"""
    def __init__(self, name, description, value):
        self.name = name
        self.description = description
        self.value = value

    def __str__(self):
        return "{}\n=====\n{}\nValue: {}\n".format(self.name, self.description, self.value)

class Gold(Item):
    def __init__(self, amt):
        self.amt = amt
        super().__init__(name="Gold", description="A small pouch containing {} gold pieces.".format(str(self.amt)),
                         value=self.amt)

class Weapon(Item):
    def __init__(self, name, description, value, damage, isequipped, str_req, fin_req, str_mod, fin_mod, weight):
        self.damage = damage
        self.str_req = str_req
        self.fin_req = fin_req
        self.str_mod = str_mod
        self.fin_mod = fin_mod
        self.weight = weight
        self.isequipped = isequipped
        super().__init__(name, description, value)

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}".format(self.name, self.description,
                                                                            self.value, self.damage, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}".format(self.name, self.description,
                                                                 self.value, self.damage, self.weight)

class Armor(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        super().__init__(name, description, value)

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)

class Boots(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        super().__init__(name, description, value)

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)

class Helm(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        super().__init__(name, description, value)

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)

class Gloves(Item):
    def __init__(self, name, description, value, protection, isequipped, str_req, str_mod, weight):
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        super().__init__(name, description, value)

    def __str__(self):
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)

class Consumable(Item):
    def __init__(self, name, description, value, weight):
        self.weight = weight
        super().__init__(name, description, value)

    def __str__(self):
         return "{}\n=====\n{}\nValue: {}\nWeight: {}".format(
            self.name, self.description, self.value, self.weight)

class Rock(Weapon):
    def __init__(self):
        super().__init__(name="Rock",
                         description="A fist-sized rock, suitable for bludgeoning.",
                         isequipped=False, value=0,
                         damage=1, str_req=1, fin_req=1, str_mod=2.00, fin_mod=0.50, weight=2.0)
        #minimum damage of 26

class RustedDagger(Weapon):
    def __init__(self):
        super().__init__(name="Rusted Dagger",
                         description="A small dagger with some rust. Somewhat more dangerous than a rock.",
                         isequipped=False, value=10,
                         damage=10, str_req=1, fin_req=12, str_mod=0.5, fin_mod=2, weight= 1.5)
        #minimum damage of 37

class TatteredCloth(Armor):
    def __init__(self):
        super().__init__(name="Tattered Cloth",
                         description="Shamefully tattered cloth wrappings. "
                                     "Lightweight, but offering little in protection.",
                         isequipped=False, value=0,
                         protection=1, str_req=1, str_mod=0.1, weight= 0.5)
        #minimum protection of 2

class ClothHood(Helm):
    def __init__(self):
        super().__init__(name="Cloth Hood",
                         description="Stained cloth hood. "
                                     "Enough to conceal your face, but that's about it.",
                         isequipped=False, value=0,
                         protection=0, str_req=1, str_mod=0.1, weight= 0.5)
        self.add_fin = 1
        #minimum protection of 1