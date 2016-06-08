import random
import items, world

class Player():
    def __init__(self):
        self.inventory = [items.Gold(15), items.Rock(), items.TatteredCloth(), items.ClothHood()]
        self.hp = 100
        self.strength = 10 #attack damage with strength-based weapons, parry rating, armor efficacy, influence ability
        self.finesse = 10 #attack damage with finesse-based weapons, parry and dodge rating
        self.speed = 10 #dodge rating, combat action frequency, combat cooldown
        self.endurance = 10 #combat cooldown, fatigue rate
        self.charisma = 10 #influence ability, yielding in combat
        self.intelligence = 10 #sacred arts, influence ability, parry and dodge rating
        self.faith = 10 #sacred arts, influence ability, dodge rating
        self.eq_weapon = None
        self.location_x, self.location_y = world.starting_position
        self.victory = False

    def is_alive(self):
        return self.hp > 0

    def print_inventory(self):
        num_gold = 0
        num_consumables = 0
        num_weapon = 0
        num_armor = 0
        num_boots = 0
        num_helm = 0
        num_gloves = 0
        for item in self.inventory:
            #TODO: Count all of the items of a specific type in inventory, then offer the player a choice of what type to view
        for item in self.inventory:
            print(item, '\n')

    def equip_item(self, e_item):
        if e_item.isequipped == True:
            print("{} is already equipped.".format(e_item.name))
            return
        else:
            item_class = e_item.__name__
            for item in self.inventory:
                if isinstance(item, item_class) and item.isequipped == True:
                    item.isequipped = False
                    print("You removed {}.".format(item.name))
            e_item.isequipped = True
            print("You equipped {}!".format(e_item.name))

    def move(self, dx, dy):
        self.location_x += dx
        self.location_y += dy
        print(world.tile_exists(self.location_x, self.location_y).intro_text())

    def move_north(self):
        self.move(dx=0, dy=-1)

    def move_south(self):
        self.move(dx=0, dy=1)

    def move_east(self):
        self.move(dx=1, dy=0)

    def move_west(self):
        self.move(dx=-1, dy=0)

    def attack(self, enemy):
        best_weapon = None
        max_dmg = 0
        for i in self.inventory:
            if isinstance(i, items.Weapon):
                if i.damage > max_dmg:
                    max_dmg = i.damage
                    best_weapon = i

        print("You use {} against {}!".format(best_weapon.name, enemy.name))
        enemy.hp -= best_weapon.damage
        if not enemy.is_alive():
            print("You killed {}!".format(enemy.name))
        else:
            print("{} HP is {}.".format(enemy.name, enemy.hp))

    def do_action(self, action, **kwargs):
        action_method = getattr(self, action.method.__name__)
        if action_method:
            action_method(**kwargs)

    def flee(self, tile):
        """Moves the player randomly to an adjacent tile"""
        available_moves = tile.adjacent_moves()
        r = random.randint(0, len(available_moves) - 1)
        self.do_action(available_moves[r])
