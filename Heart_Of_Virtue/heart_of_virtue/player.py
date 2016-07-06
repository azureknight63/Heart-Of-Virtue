import random
from switch import switch
import items, functions, world, moves
from termcolor import colored

class Player():
    def __init__(self):
        self.inventory = [items.Gold(15), items.Rock(), items.TatteredCloth(), items.ClothHood()]
        self.hp = 100
        self.maxhp = 100
        self.fatigue = 100 #cannot perform moves without enough of this stuff
        self.maxfatigue = 100
        self.strength = 10 #attack damage with strength-based weapons, parry rating, armor efficacy, influence ability
        self.finesse = 10 #attack damage with finesse-based weapons, parry and dodge rating
        self.speed = 10 #dodge rating, combat action frequency, combat cooldown
        self.endurance = 10 #combat cooldown, fatigue rate
        self.charisma = 10 #influence ability, yielding in combat
        self.intelligence = 10 #sacred arts, influence ability, parry and dodge rating
        self.faith = 10 #sacred arts, influence ability, dodge rating
        self.eq_weapon = None
        self.exp = 0 #exp to be gained from doing stuff rather than killing things TODO: add in exp gains to certain actions
        self.level = 0
        self.location_x, self.location_y = world.starting_position
        self.current_room = world.starting_position
        self.victory = False
        self.known_moves = [moves.Rest(self)]
        self.current_move = None
        self.game_tick = 0
        self.heat = 1.0

        self.combat_idle_msg = [
            'You breathe heavily.',
            'You anxiously shift your weight back and forth.',
            'You stomp your foot impatiently.',
            'You carefully consider your enemy.',
            'You spit on the ground.',
            'A bead of sweat runs down your brow.',
            'You become conscious of your own heart beating loudly.',
            'In a flash, you remember the face of your dear, sweet Amelia smiling at you.',
            'With a smug grin, you wonder how you got yourself into this mess.',
            'Sweat drips into your eye, causing you to blink rapidly.',
            'You miss the sound of your daughter laughing happily.',
            'You recall the sensation of consuming the Eucharist and wonder when - if - that might happen again.',
            'You mutter a quick prayer under your breath.',
            ]

    def combat_idle(self):
        chance = random.randint(0,100)
        if chance > 96:
            message = random.randint(0,len(self.combat_idle_msg))
            print(self.combat_idle_msg[message])

    def gain_exp(self, amt):
        """
        Give the player amt exp, then check to see if he gained a level and act accordingly
        """

    def change_heat(self, mult=1, add=0): #enforces boundaries with min and max heat levels
        self.heat *= mult
        self.heat += add
        self.heat = int((self.heat * 100)+ 0.5) / 100.0 # enforce 2 decimals
        if self.heat > 10:
            self.heat = 10
        if self.heat < 0.5:
            self.heat = 0.5


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

    def equip_item(self):
        num_weapon = 0
        num_armor = 0
        num_boots = 0
        num_helm = 0
        num_gloves = 0
        while True:
            for item in self.inventory:  # get the counts of each item in each category
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
            print("=====\nInventory\n=====\nSelect a category to view:\n\n"
                  "(w) Weapons: {}\n(a) Armor: {}\n(b) Boots: {}\n(h) Helms: {}\n(g) Gloves: {}\n(x) Cancel\n"
                  .format(num_weapon, num_armor, num_boots, num_helm, num_gloves))

            choices = []
            inventory_selection = input('Selection: ')
            for case in switch(inventory_selection):
                if case('w', 'Weapons', 'weapons'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Weapon):
                            choices.append(item)
                    break
                if case('a', 'Armor', 'armor'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Armor):
                            choices.append(item)
                    break
                if case('b', 'Boots', 'boots'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Boots):
                            choices.append(item)
                    break
                if case('h', 'Helms', 'helms'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Helm):
                            choices.append(item)
                    break
                if case('g', 'Gloves', 'gloves'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Gloves):
                            choices.append(item)
                    break
                if case():
                    break
            if len(choices) > 0:
                for i, item in enumerate(choices):
                    if item.isequipped:
                        print(i, ': ', item.name, colored('(Equipped)', 'green'), '\n')
                    else:
                        print(i, ': ', item.name, '\n')
                inventory_selection = input('Equip which? ')
                if not functions.is_input_integer(inventory_selection):
                    num_weapon = num_armor = num_boots = num_helm = num_gloves = 0
                    continue
                for i, item in enumerate(choices):
                    if i == int(inventory_selection):
                        e_item = item
                        if e_item.isequipped == True:
                            print("{} is already equipped.".format(e_item.name))
                            answer = input("Would you like to remove it? (y/n) ")
                            if answer == 'y':
                                e_item.isequipped = False
                                print("You put {} back into your bag.".format(e_item.name))
                        else:
                            for item in self.inventory:
                                if e_item.type == item.type and item.isequipped == True:
                                    item.isequipped = False
                                    print("You put {} back into your bag.".format(item.name))
                            e_item.isequipped = True
                            print("You equipped {}!".format(e_item.name))
                        break

            num_weapon = num_armor = num_boots = num_helm = num_gloves = 0
            if inventory_selection == 'x':
                break

    def move(self, dx, dy):
        self.game_tick += 1
        self.location_x += dx
        self.location_y += dy
        print(world.tile_exists(self.location_x, self.location_y).intro_text())
        if self.game_tick - world.tile_exists(self.location_x, self.location_y).last_entered >= world.tile_exists(
                self.location_x, self.location_y).respawn_rate:
            pass #todo: enable enemy and item respawn

    def move_north(self):
        self.move(dx=0, dy=-1)

    def move_south(self):
        self.move(dx=0, dy=1)

    def move_east(self):
        self.move(dx=1, dy=0)

    def move_west(self):
        self.move(dx=-1, dy=0)

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

    def view(self):
        stuff_here = {}
        for i, thing in enumerate(self.current_room.enemies_here + self.current_room.items_here):
            stuff_here[str(i+1)] = thing # The +1 is to make the list player-friendly
        if len(stuff_here) > 0:
            print("What would you like to view?\n\n")
            for k, v in stuff_here.items():
                print(k, ": ", v.name)
            choice = input("Selection: ")
            if choice in stuff_here:
                print(stuff_here[choice])
            else:
                print("Invalid selection.")
        else:
            print("You don't see anything remarkable here to look at.\n")

    def commands(self):
        print(colored("l: Look around\n"
              "v: View details on a person, creature, or object\n"
              "i: Inspect your inventory\n"
              "q: Equip or unequip an item from your inventory\n"
              "u: Use an item from your inventory\n" #TODO: implement this
              , "blue")) #TODO: Figure out how player can type arbitrary command like 'pull rope' 'push button' etc.

    def show_bars(self): #show HP and Fatigue bars
        hp_pcnt = float(self.hp) / float(self.maxhp)
        hp_pcnt = int(hp_pcnt * 10)
        hp_string = colored("HP: ", "red") + "["
        for bar in range(0,hp_pcnt):
            hp_string += colored("█", "red")
        for blank in range(hp_pcnt + 1, 10):
            hp_string += " "
        hp_string += "]   "

        fat_pcnt = float(self.fatigue) / float(self.maxfatigue)
        fat_pcnt = int(fat_pcnt * 10)
        fat_string = colored("FAT: ", "green") + "["
        for bar in range(0,fat_pcnt):
            fat_string += colored("█", "green")
        for blank in range(fat_pcnt + 1, 10):
            fat_string += " "
        fat_string += "]"
        print(hp_string + fat_string)

    def refresh_moves(self):
        self.known_moves = [moves.Rest(self)]
        if not self.eq_weapon == None:
            self.known_moves.append(moves.Attack(self))
        #todo: if certain criteria are met, add additional moves