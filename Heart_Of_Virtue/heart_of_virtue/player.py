import random
from switch import switch
import items, functions, world

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
        num_consumable = 0
        num_weapon = 0
        num_armor = 0
        num_boots = 0
        num_helm = 0
        num_gloves = 0
        while True:
            for item in self.inventory: #get the counts of each item in each category
                if isinstance(item, items.Gold):
                    num_gold = item.amt
                else:
                    if issubclass(item.__class__, items.Consumable):
                        num_consumable += 1
                    if issubclass(item.__class__, items.Weapon):
                        num_weapon += 1
                    if issubclass(item.__class__, items.Armor):
                        num_armor += 1
                    if issubclass(item.__class__, items.Boots):
                        num_boots += 1
                    if issubclass(item.__class__, items.Helm):
                        num_helm += 1
                    if issubclass(item.__class__, items.Gloves):
                        num_gloves += 1
                    else:
                        pass
            print("=====\nInventory\n=====\nGold: {}\nSelect a category to view:\n\n(c) Consumables: {}\n"
                  "(w) Weapons: {}\n(a) Armor: {}\n(b) Boots: {}\n(h) Helms: {}\n(g) Gloves: {}\n(x) Cancel\n"
                  .format(num_gold,num_consumable,num_weapon,num_armor,num_boots,num_helm,num_gloves))

            inventory_selection = input('Selection: ')
            for case in switch(inventory_selection):
                if case('c', 'Consumables', 'consumables'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Consumable):
                            print(item, '\n')
                    break
                if case('w', 'Weapons', 'weapons'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Weapon):
                            print(item, '\n')
                    break
                if case('a', 'Armor', 'armor'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Armor):
                            print(item, '\n')
                    break
                if case('b', 'Boots', 'boots'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Boots):
                            print(item, '\n')
                    break
                if case('h', 'Helms', 'helms'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Helm):
                            print(item, '\n')
                    break
                if case('g', 'Gloves', 'gloves'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Gloves):
                            print(item, '\n')
                    break
                if case():
                    break
            num_gold = num_consumable = num_weapon = num_armor = num_boots = num_helm = num_gloves = 0
            if inventory_selection == 'x':
                break
        # for item in self.inventory:
        #     print(item, '\n')

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

    def look(self):
        tile = world.tile_exists(self.location_x, self.location_y)
        print(tile.intro_text())
        functions.check_for_enemies(tile)
        functions.check_for_items(tile)

    def commands(self):
        print("l: Look around\n"
              "v: View details on a person, creature, or object\n"
              "i: Inspect your inventory\n"
              "q: Equip or unequip an item from your inventory\n"
              "u: Use an item from your inventory\n"
              "z: Enter a custom command (ex. 'pull switch', 'press button', 'cut rope', etc.\n")