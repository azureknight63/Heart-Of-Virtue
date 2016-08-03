import random, time
from switch import switch
import items, functions, world, moves
from termcolor import colored, cprint

class Player():
    def __init__(self):
        self.inventory = [items.Gold(15), items.Rock(), items.TatteredCloth(), items.ClothHood()]
        self.name = "Jean"
        self.name_long = "Jean Claire"
        self.hp = 100
        self.maxhp = 100
        self.maxhp_base = 100
        self.fatigue = 100  # cannot perform moves without enough of this stuff
        self.maxfatigue = 100
        self.maxfatigue_base = 100
        self.strength = 10  # attack damage with strength-based weapons, parry rating, armor efficacy, influence ability
        self.strength_base = 10
        self.finesse = 10  # attack damage with finesse-based weapons, parry and dodge rating
        self.finesse_base = 10
        self.speed = 10  # dodge rating, combat action frequency, combat cooldown
        self.speed_base = 10
        self.endurance = 10  # combat cooldown, fatigue rate
        self.endurance_base = 10
        self.charisma = 10  # influence ability, yielding in combat
        self.charisma_base = 10
        self.intelligence = 10  # sacred arts, influence ability, parry and dodge rating
        self.intelligence_base = 10
        self.faith = 10  # sacred arts, influence ability, dodge rating
        self.faith_base = 10
        self.resistance = [0,0,0,0,0,0]  # [fire, ice, shock, earth, light, dark]
        self.resistance_base = [0,0,0,0,0,0]
        self.eq_weapon = None
        self.exp = 0  # exp to be gained from doing stuff rather than killing things TODO: add in exp gains to certain actions
        self.level = 1
        self.location_x, self.location_y = world.starting_position
        self.current_room = world.starting_position
        self.victory = False
        self.known_moves = [moves.Rest(self), moves.Use_Item(self)]
        self.current_move = None
        self.game_tick = 0
        self.heat = 1.0
        self.protection = 0
        self.states = []
        self.in_combat = False

        self.combat_idle_msg = [
            'Jean breathes heavily.',
            'Jean anxiously shifts his weight back and forth.',
            'Jean stomps his foot impatiently.',
            'Jean carefully considers his enemy.',
            'Jean spits on the ground.',
            "A bead of sweat runs down Jean's brow.",
            'Jean becomes conscious of his own heart beating loudly.',
            'In a flash, Jean remembers the face of his dear, sweet Amelia smiling at him.',
            'With a smug grin, Jean wonders how he got himself into this mess.',
            "Sweat drips into Jean's eye, causing him to blink rapidly.",
            'Jean misses the sound of his daughter laughing happily.',
            'Jean recalls the sensation of consuming the Eucharist and wonders when - if - that might happen again.',
            'Jean mutters a quick prayer under his breath.',
            'Jean briefly recalls his mother folding laundry and humming softly to herself.',
            ]

        self.combat_hurt_msg = [
            'Jean tastes blood in his mouth and spits it out.',
            'Jean winces in pain.',
            'Jean grimaces.',
            "There's a loud ringing in Jean's ears.",
            'Jean staggers for a moment.',
            "Jean's body shudders from the abuse it's received.",
            'Jean coughs spasmodically.',
            "A throbbing headache sears into Jean's consciousness."
            "Jean's vision becomes cloudy and unfocused for a moment.",
            'Jean vomits blood and bile onto the ground.',
            '''Jean whispers quietly, "Amelia... Regina...''',
            '''A ragged wheezing escapes Jean's throat.''',
            '''A searing pain lances Jean's side.'''
            '''A sense of panic wells up inside of Jean.'''
            '''For a brief moment, a wave of fear washes over Jean.'''
        ]

    def cycle_states(self):
        for state in self.states:
            state.process(self)

    def combat_idle(self):
        if (self.hp * 100) / self.maxhp > 20:  # combat idle (healthy)
            chance = random.randint(0,1000)
            if chance > 995:
                message = random.randint(0, len(self.combat_idle_msg)-1)
                print(self.combat_idle_msg[message])
        else:
            chance = random.randint(0, 1000)  # combat hurt (injured)
            if chance > 950:
                message = random.randint(0, len(self.combat_hurt_msg)-1)
                print(self.combat_hurt_msg[message])

    def gain_exp(self, amt):
        """
        Give the player amt exp, then check to see if he gained a level and act accordingly
        """
        if self.level > 100:
            self.exp += amt  #todo: finish this

    def change_heat(self, mult=1, add=0):  # enforces boundaries with min and max heat levels
        self.heat *= mult
        self.heat += add
        self.heat = int((self.heat * 100)+ 0.5) / 100.0  # enforce 2 decimals
        if self.heat > 10:
            self.heat = 10
        if self.heat < 0.5:
            self.heat = 0.5

    def is_alive(self):
        return self.hp > 0

    def death(self):
        for i in range(random.randint(2,5)):
            message = random.randint(0, len(self.combat_hurt_msg)-1)
            print(self.combat_hurt_msg[message])
            time.sleep(0.5)

        cprint('Jean wavers, then collapses heavily on the ground.', "red")
        time.sleep(2)

        cprint("""Jean's eyes seem to focus on something distant. A rush of memories enters his mind.""", "red")
        time.sleep(3)

        cprint("""Jean gasps as the unbearable pain wracks his body. As his sight begins to dim,
        he lets out a barely audible whisper:""", "red")
        time.sleep(3)

        cprint('''"...Amelia... ...Regina... ...I'm sorry..."''', "red")
        time.sleep(3)

        cprint("Darkness finally envelopes Jean. His struggle is over now. It's time to rest.\n\n", "red")
        time.sleep(5)

        cprint('''
                   .o oOOOOOOOo                                            OOOo
                    Ob.OOOOOOOo  OOOo.      oOOo.                      .adOOOOOOO
                    OboO"""""""""""".OOo. .oOOOOOo.    OOOo.oOOOOOo.."""""""""'OO
                    OOP.oOOOOOOOOOOO "POOOOOOOOOOOo.   `"OOOOOOOOOP,OOOOOOOOOOOB'
                    `O'OOOO'     `OOOOo"OOOOOOOOOOO` .adOOOOOOOOO"oOOO'    `OOOOo
                    .OOOO'            `OOOOOOOOOOOOOOOOOOOOOOOOOO'            `OO
                    OOOOO                 '"OOOOOOOOOOOOOOOO"`                oOO
                   oOOOOOba.                .adOOOOOOOOOOba               .adOOOOo.
                  oOOOOOOOOOOOOOba.    .adOOOOOOOOOO@^OOOOOOOba.     .adOOOOOOOOOOOO
                 OOOOOOOOOOOOOOOOO.OOOOOOOOOOOOOO"`  '"OOOOOOOOOOOOO.OOOOOOOOOOOOOO
                 "OOOO"       "YOoOOOOMOIONODOO"`  .   '"OOROAOPOEOOOoOY"     "OOO"
                    Y           'OOOOOOOOOOOOOO: .oOOo. :OOOOOOOOOOO?'         :`
                    :            .oO%OOOOOOOOOOo.OOOOOO.oOOOOOOOOOOOO?         .
                    .            oOOP"%OOOOOOOOoOOOOOOO?oOOOOO?OOOO"OOo
                                 '%o  OOOO"%OOOO%"%OOOOO"OOOOOO"OOO':
                                      `$"  `OOOO' `O"Y ' `OOOO'  o             .
                    .                  .     OP"          : o     .
                                              :
                                              .
               ''', "red")
        time.sleep(0.5)
        print('\n\n')
        cprint('Jean has died!', "red")

    def print_inventory(self):
        num_gold = 0
        num_consumable = 0
        num_weapon = 0
        num_armor = 0
        num_boots = 0
        num_helm = 0
        num_gloves = 0
        num_special = 0
        while True:
            for item in self.inventory:  # get the counts of each item in each category
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
                    if issubclass(item.__class__, items.Special):
                        num_special += 1
                    else:
                        pass
            print("=====\nInventory\n=====\nGold: {}\nSelect a category to view:\n\n(c) Consumables: {}\n"
                  "(w) Weapons: {}\n(a) Armor: {}\n(b) Boots: {}\n(h) Helms: {}\n(g) Gloves: {}\n(s) Special: {}\n"
                  "(x) Cancel\n"
                  .format(num_gold,num_consumable,num_weapon,num_armor,num_boots,num_helm,num_gloves, num_special))

            choices = []
            inventory_selection = input('Selection: ')
            for case in switch(inventory_selection):
                if case('c', 'Consumables', 'consumables'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Consumable):
                            choices.append(item)
                    break
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
                if case('s', 'Special', 'special'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Special):
                            choices.append(item)
                    break
                if case():
                    break

            if len(choices) > 0:
                for i, item in enumerate(choices):
                    if hasattr(item, 'isequipped'):
                        if item.isequipped:
                            print(i, ': ', item.name, colored('(Equipped)', 'green'), '\n')
                        else:
                            print(i, ': ', item.name, '\n')
                    else:
                        if hasattr(item, 'count'):
                            print(i, ': ', item.name, ' (', item.count, ')\n')
                        else:
                            print(i, ': ', item.name, '\n')
                inventory_selection = input('View which? ')
                if not functions.is_input_integer(inventory_selection):
                    num_weapon = num_armor = num_boots = num_helm = num_gloves = num_special = 0
                    continue
                for i, item in enumerate(choices):
                    if i == int(inventory_selection):
                        print(item, '\n')

            num_gold = num_consumable = num_weapon = num_armor = num_boots = num_helm = num_gloves = num_special = 0
            if inventory_selection == 'x':
                break

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
            print("=====\nChange Equipment\n=====\nSelect a category to view:\n\n"
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
                                print("Jean puts {} back into his bag.".format(e_item.name))
                        else:
                            for item in self.inventory:
                                if e_item.type == item.type and item.isequipped == True:
                                    item.isequipped = False
                                    print("Jean puts {} back into his bag.".format(item.name))
                            e_item.isequipped = True
                            print("Jean equipped {}!".format(e_item.name))
                        break

            num_weapon = num_armor = num_boots = num_helm = num_gloves = 0
            if inventory_selection == 'x':
                break

    def use_item(self, phrase=''):
        if phrase == '':
            num_consumables = 0
            num_special = 0
            exit = False
            while exit == False:
                for item in self.inventory:  # get the counts of each item in each category
                    if issubclass(item.__class__, items.Consumable):
                        num_consumables += 1
                    if issubclass(item.__class__, items.Special):
                        num_special += 1
                    else:
                        pass
                print("=====\nUse Item\n=====\nSelect a category to view:\n\n"
                      "(c) Consumables: {}\n(s) Special: {}\n(x) Cancel\n"
                      .format(num_consumables, num_special))
                choices = []
                inventory_selection = input('Selection: ')
                for case in switch(inventory_selection):
                    if case('c', 'Consumables', 'consumables'):
                        for item in self.inventory:
                            if issubclass(item.__class__, items.Consumable):
                                choices.append(item)
                        break
                    if case('s', 'Special', 'special'):
                        for item in self.inventory:
                            if issubclass(item.__class__, items.Special):
                                choices.append(item)
                        break
                    if case():
                        break
                if len(choices) > 0:
                    for i, item in enumerate(choices):
                        if hasattr(item, 'isequipped'):
                            if item.isequipped:
                                print(i, ': ', item.name, colored('(Equipped)', 'green'), '\n')
                        else:
                            if hasattr(item, 'count'):
                                print(i, ': ', item.name, ' (', item.count, ')\n')
                            else:
                                print(i, ': ', item.name, '\n')
                    inventory_selection = input('Use which? ')
                    if not functions.is_input_integer(inventory_selection):
                        num_consumables = num_special = 0
                        continue
                    for i, item in enumerate(choices):
                        if i == int(inventory_selection):
                            print("Jean used {}!".format(item.name))
                            item.use(self)
                            if self.in_combat == True:
                                exit = True
                            break

                num_consumables = num_special = 0
                if inventory_selection == 'x':
                    exit = True

        else:
            lower_phrase = phrase.lower()
            for i, item in enumerate(self.inventory):
                if issubclass(item.__class__, items.Consumable) or issubclass(item.__class__, items.Special):
                    search_item = item.name.lower() + ' ' + item.announce.lower()
                    if lower_phrase in search_item:
                        confirm = input("Use {}? (y/n)".format(item.name))
                        if confirm == 'y' or 'Y' or 'yes' or 'Yes' or 'YES':
                            item.use(self)
                            break

    def move(self, dx, dy):
        self.game_tick += 1
        self.location_x += dx
        self.location_y += dy
        print(world.tile_exists(self.location_x, self.location_y).intro_text())
        # if self.game_tick - world.tile_exists(self.location_x, self.location_y).last_entered >= world.tile_exists(
        #         self.location_x, self.location_y).respawn_rate:
        #     pass

    def move_north(self):
        self.move(dx=0, dy=-1)

    def move_south(self):
        self.move(dx=0, dy=1)

    def move_east(self):
        self.move(dx=1, dy=0)

    def move_west(self):
        self.move(dx=-1, dy=0)

    def do_action(self, action, phrase=''):
        action_method = getattr(self, action.method.__name__)
        if phrase == '':
            if action_method:
                action_method()
        else:
            if action_method:
                action_method(phrase)

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
        for i, thing in enumerate(self.current_room.npcs_here + self.current_room.items_here):
            stuff_here[str(i+1)] = thing  # The +1 is to make the list player-friendly
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
            print("Jean doesn't see anything remarkable here to look at.\n")

    def take(self, phrase=''):
        if phrase == '':  # player entered general take command with no args. Show a list of items that can be taken.
            if len(self.current_room.items_here) > 0:
                print("What are you trying to take?")
                for i, item in enumerate(self.current_room.items_here):
                    print('{}: {}\n'.format(i,item.name))
                selection = input('Selection: ')
                if not functions.is_input_integer(selection):
                    cprint("JEan isn't sure exactly what he's trying to do.", 'red')
                else:
                    self.inventory.append(self.current_room.items_here[int(selection)])
                    print('Jean takes {}.'.format(self.current_room.items_here[int(selection)].name))
                    self.current_room.items_here.pop(int(selection))
            else:
                cprint("There doesn't seem to be anything here for Jean to take.", 'red')
        else:
            if phrase == 'all':
                for item in self.current_room.items_here:
                    self.inventory.append(item)
                    print('Jean takes {}.'.format(item.name))
                self.current_room.items_here = []
            else:
                lower_phrase = phrase.lower()
                for i, item in enumerate(self.current_room.items_here):
                    search_item = item.name.lower() + ' ' + item.announce.lower()
                    if lower_phrase in search_item:
                        self.inventory.append(item)
                        print('Jean takes {}.'.format(item.name))
                        self.current_room.items_here.pop(i)
                        break

    def stack_inv_items(self):
        for master_item in self.inventory:  # traverse the inventory for stackable items, then stack them
            if hasattr(master_item, "count"):
                for duplicate_item in self.inventory:
                    if duplicate_item != master_item and master_item.__class__ == duplicate_item.__class__:
                        master_item.count += 1
                        self.inventory.remove(duplicate_item)

    def commands(self):
        print(colored("l: Look around\n"
              "v: View details on a person, creature, or object\n"
              "i: Inspect your inventory\n"
              "q: Equip or unequip an item from your inventory\n"
              "use <item>: Use an item from your inventory\n"
              "take <item>: Pick up an item - accepts partial names (ex. 'take rest' to pick up a Restorative.)"
                      "Entering 'take' by itself will show a list of items in the room."
              , "blue")) #TODO: Figure out how player can type arbitrary command like 'pull rope' 'push button' etc.

    def show_bars(self, hp=True, fp=True):  # show HP and Fatigue bars
        if hp:
            hp_pcnt = float(self.hp) / float(self.maxhp)
            hp_pcnt = int(hp_pcnt * 10)
            hp_string = colored("HP: ", "red") + "["
            for bar in range(0,hp_pcnt):
                hp_string += colored("█", "red")
            for blank in range(hp_pcnt + 1, 10):
                hp_string += " "
            hp_string += "]   "
        else:
            hp_string = ''

        if fp:
            fat_pcnt = float(self.fatigue) / float(self.maxfatigue)
            fat_pcnt = int(fat_pcnt * 10)
            fat_string = colored("FP: ", "green") + "["
            for bar in range(0,fat_pcnt):
                fat_string += colored("█", "green")
            for blank in range(fat_pcnt + 1, 10):
                fat_string += " "
            fat_string += "]"
        else:
            fat_string = ''

        print(hp_string + fat_string)

    def refresh_moves(self):
        self.known_moves = [moves.Wait(self), moves.Rest(self), moves.Use_Item(self), moves.Dodge(self)]
        if not self.eq_weapon == None:
            self.known_moves.append(moves.Attack(self))

    def refresh_protection_rating(self):
        self.protection = (self.endurance / 10)  # base level of protection from player stats
        for item in self.inventory:
            if hasattr(item, "isequipped"):
                if item.isequipped == True:  # check the protection level of all equipped items and add to base
                    add_prot = item.protection
                    if hasattr(item, "str_mod"):
                        add_prot += item.str_mod * self.strength
                    if hasattr(item, "fin_mod"):
                        add_prot += item.fin_mod * self.finesse
                    self.protection += add_prot

    def refresh_stat_bonuses(self):  # searches all items and states for stat bonuses, then applies them
        functions.reset_stats(self)
        bonuses = ["add_str", "add_fin", "add_maxhp", "add_maxfatigue", "add_speed", "add_endurance", "add_charisma",
                   "add_intelligence", "add_faith", "add_resistance"]
        adder_group = []
        for item in self.inventory:
            if hasattr(item, "is_equipped"):
                if item.is_equipped:
                    for bonus in bonuses:
                        if hasattr(item, bonus):
                            adder_group.append(item)
                            break
        for state in self.states:
            for bonus in bonuses:
                if hasattr(state, bonus):
                    adder_group.append(state)
                    break
        for adder in adder_group:
            if hasattr(adder, bonuses[0]):
                self.strength += adder.add_str
            if hasattr(adder, bonuses[1]):
                self.finesse += adder.add_fin
            if hasattr(adder, bonuses[2]):
                self.maxhp += adder.add_maxhp
            if hasattr(adder, bonuses[3]):
                self.maxfatigue += adder.add_maxfatigue
            if hasattr(adder, bonuses[4]):
                self.speed += adder.add_speed
            if hasattr(adder, bonuses[5]):
                self.endurance += adder.add_endurance
            if hasattr(adder, bonuses[6]):
                self.charisma += adder.add_charisma
            if hasattr(adder, bonuses[7]):
                self.intelligence += adder.add_intelligence
            if hasattr(adder, bonuses[8]):
                self.faith += adder.add_faith
            if hasattr(adder, bonuses[9]):
                for i, v in enumerate(self.resistance):
                    self.resistance[i] += adder.add_resistance[i]


