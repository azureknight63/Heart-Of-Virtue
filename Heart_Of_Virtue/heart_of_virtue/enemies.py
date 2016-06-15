import random
import genericng

class Enemy:
    def __init__(self, name, description,
                 hp, damage, armor, speed, finesse, resistance, awareness, aggro,
                 idle_message = ' is shuffling about.', alert_message = 'glares sharply at you!'):
        self.name = name
        self.description = description
        self.idle_message = idle_message
        self.alert_message = alert_message
        self.hp = hp
        self.damage = damage
        self.armor = armor
        self.speed = speed
        self.finesse = finesse
        self.resistance = resistance
        self.awareness = awareness
        self.aggro = aggro

    def is_alive(self):
        return self.hp > 0

class RockRumbler(Enemy):
    def __init__(self):
        description = "A burly creature covered in a rock-like carapace somewhat resembling a stout crocodile." \
                           "Highly resistant to most weapons. You'd probably be better off avoiding combat with this" \
                           "one."
        super().__init__(name="Rock Rumbler " + genericng.generate(2,4), description=description, hp=30,
                         damage=3, armor=30, speed=10, finesse=10,
                         resistance=0, awareness=12, aggro=True)

