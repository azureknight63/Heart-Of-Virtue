import random, time, decimal
from switch import switch
import items, functions, universe, moves, actions, combat
from termcolor import colored, cprint

class Player():
    def __init__(self):
        self.inventory = [items.Gold(15), items.TatteredCloth(), items.ClothHood()]
        self.name = "Jean"
        self.name_long = "Jean Claire"
        self.hp = 100
        self.maxhp = 100
        self.maxhp_base = 100
        self.fatigue = 150  # cannot perform moves without enough of this stuff
        self.maxfatigue = 150
        self.maxfatigue_base = 150
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
        self.resistance = {
            "fire": 0.0,
            "ice": 0.0,
            "shock": 0.0,
            "earth": 0.0,
            "light": 0.0,
            "dark": 0.0
        }
        self.resistance_base = {
            "fire": 0.0,
            "ice": 0.0,
            "shock": 0.0,
            "earth": 0.0,
            "light": 0.0,
            "dark": 0.0
        }
        self.weight_tolerance = decimal.Decimal(20)
        self.weight_tolerance_base = decimal.Decimal(20)
        self.weight_current = decimal.Decimal(0)
        self.fists = items.Fists()
        self.eq_weapon = self.fists
        self.combat_exp = 0  # place to pool all exp gained from a single combat before distribution
        self.exp = 0  # exp to be gained from doing stuff rather than killing things
        self.level = 1
        self.exp_to_level = 100
        self.location_x, self.location_y = (0, 0)
        self.current_room = None
        self.victory = False
        self.known_moves = [  # this should contain ALL known moves, regardless of whether they are unlocked (moves will check their own conditions)
            moves.Check(self), moves.Wait(self), moves.Rest(self),
            moves.Use_Item(self), moves.Advance(self), moves.Withdraw(self), moves.Dodge(self), moves.Attack(self)
        ]
        self.current_move = None
        self.heat = 1.0
        self.protection = 0
        self.states = []
        self.in_combat = False
        self.combat_events = []  # list of pending events in combat. If non-empty, combat will be paused while an event happens
        self.combat_list = []  # populated by enemies currently being encountered. Should be empty outside of combat
        self.combat_list_allies = [self]  # friendly NPCs in combat that either help the player or just stand there looking pretty
        self.combat_proximity = {}  # dict for unit proximity: {unit: distance}; Range for most melee weapons is 5, ranged is 20. Distance is in feet (for reference)
        self.default_proximity = 50
        self.savestat = None
        self.saveuniv = None
        self.universe = None
        self.map = None
        self.main_menu = False  # escape switch to get to the main menu; setting to True jumps out of the play loop
        self.time_elapsed = 0  # total seconds of gameplay
        self.combat_idle_msg = [
            'Jean breathes heavily. ',
            'Jean swallows forcefully. ',
            'Jean sniffs.',
            'Jean licks his lips in anticipation. ',
            'Jean grimaces for a moment.',
            'Jean anxiously shifts his weight back and forth. ',
            'Jean stomps his foot impatiently. ',
            'Jean carefully considers his enemy. ',
            'Jean spits on the ground. ',
            "A bead of sweat runs down Jean's brow. ",
            'Jean becomes conscious of his own heart beating loudly. ',
            'In a flash, Jean remembers the face of his dear, sweet Amelia smiling at him. ',
            'With a smug grin, Jean wonders how he got himself into this mess. ',
            "Sweat drips into Jean's eye, causing him to blink rapidly. ",
            'Jean misses the sound of his daughter laughing happily. ',
            'Jean recalls the sensation of consuming the Eucharist and wonders when - if - that might happen again. ',
            'Jean mutters a quick prayer under his breath. ',
            'Jean briefly recalls his mother folding laundry and humming softly to herself. ',
            ]

        self.combat_hurt_msg = [
            'Jean tastes blood in his mouth and spits it out. ',
            'Jean winces in pain. ',
            'Jean grimaces. ',
            "There's a loud ringing in Jean's ears. ",
            'Jean staggers for a moment. ',
            "Jean's body shudders from the abuse it's received. ",
            'Jean coughs spasmodically. ',
            'Jean falls painfully to one knee, then quickly regains his footing. ',
            'Jean fumbles a bit before planting his feet. ',
            'Jean suddenly becomes aware that he is losing a lot of blood. ',
            '''Jean's face suddenly becomes pale as he realizes this could be his last battle. ''',
            "A throbbing headache sears into Jean's consciousness. ",
            "Jean's vision becomes cloudy and unfocused for a moment. ",
            'Jean vomits blood and bile onto the ground. ',
            '''Jean whispers quietly, "Amelia... Regina..." ''',
            '''Jean shouts loudly, "No, not here! I have to find them!"''',
            '''A ragged wheezing escapes Jean's throat. ''',
            '''A searing pain lances Jean's side. ''',
            '''A sense of panic wells up inside of Jean. ''',
            '''For a brief moment, a wave of fear washes over Jean. '''
        ]

    def cycle_states(self):
        for state in self.states:
            state.process(self)

    def stack_gold(self):
        gold_objects = []
        for item in self.inventory:  # get the counts of each item in each category
            if isinstance(item, items.Gold):
                gold_objects.append(item)
        if len(gold_objects) > 0:
            amt = 0
            for obj in gold_objects:
                amt += obj.amt
            remove_existing_gold_objects = []
            for item in self.inventory:  # get the counts of each item in each category
                if isinstance(item, items.Gold):
                    remove_existing_gold_objects.append(item)
            for item in remove_existing_gold_objects:
                self.inventory.remove(item)
            gold_objects[0].amt = amt
            self.inventory.append(gold_objects[0])


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
        if self.level < 100:
            self.exp += amt
        while self.exp >= self.exp_to_level:
            self.level_up()

    def get_hp_pcnt(self):  # returns the player's remaining HP as a decimal
        curr = float(self.hp)
        maxhp = float(self.maxhp)
        return curr/maxhp

    def supersaiyan(self):  # makes player super strong! Debug only
        self.strength_base = 1000
        self.strength = 1000
        self.finesse_base = 1000
        self.finesse = 1000
        self.speed_base = 1000
        self.speed = 1000
        self.maxhp_base = 10000
        self.maxhp = 10000
        self.hp = 10000
        self.maxfatigue_base = 10000
        self.maxfatigue = 10000
        self.fatigue = 10000

    def testevent(self, phrase=''):  # spawns a story event in the current tile
        params = phrase.split(" ")
        repeat = False
        if len(params) > 1:
            repeat = params[1]
        self.current_room.spawn_event(params[0], self, self.current_room, repeat=repeat, params=[])  # will go fubar if the name of the event is wrong or
        #  if other parameters are present in phrase

    def spawnnpc(self, phrase=''):  # spawns an npc on the current tile
        params = phrase.split(" ")
        npc = params[0].title()
        if npc == "Rockrumbler":
            npc = "RockRumbler"
        hidden=False
        hfactor=0
        delay=-1
        count=1
        if len(params) > 1:
            for item in params:
                if item == 'hidden':
                    hidden=True
                elif 'hfactor=' in item:
                    hfactor=int(item[8:])
                elif 'delay=' in item:
                    delay = int(item[6:])
                elif 'count=' in item:
                    count = int(item[6:])
        for i in range(count):
            self.current_room.spawn_npc(npc, hidden=hidden, hfactor=hfactor, delay=delay)

    def vars(self):  # print all variables
        print(self.universe.story)

    def alter(self, phrase=''):
        params = phrase.split(" ")
        self.universe.story[params[0]] = params[1]
        if self.universe.story[params[0]]:
            try:
                self.universe.story[params[0]] = params[1]
                print("### SUCCESS: " + params[0] + " changed to " + params[1] + " ###")
            except:
                print("### ERR IN SETTING VAR; BAD ARGUMENTS: " + params[0] + " " + params[1] + " ###")
        else:
            print("### ERR IN SETTING VAR; NO ENTRY: " + params[0] + " " + params[1] + " ###")

    def teleport(self, phrase=''):
        params = phrase.split(" ")
        for area in self.universe.maps:
            if area['name'] == params[0]:
                tele_to = area
                tile = self.universe.tile_exists(tele_to, int(params[1]), int(params[2]))
                if tile:
                    self.map = tele_to
                    self.universe.game_tick += 1
                    self.location_x = int(params[1])
                    self.location_y = int(params[2])
                    print(self.universe.tile_exists(self.map, self.location_x, self.location_y).intro_text())
                    return
                else:
                    print("### INVALID TELEPORT LOCATION: " + phrase + " ###")
                    return
        print("### INVALID TELEPORT LOCATION: " + phrase + " ###")

    def level_up(self):
        cprint(r"""
                         .'  '.____.' '.           ..
        '''';;;,~~~,,~~''   /  *    ,\  ''~~,,,..''  '.,_
                           / ,    *   \
                          /*    * .  * \
                         /  . *     ,   \
                        / *     ,  *   , \
                       /  .  *       *  . \
        """, "yellow")
        cprint("Jean has reached a new level!", "cyan")
        self.level += 1
        print(colored("He is now level {}".format(self.level)))
        self.exp -= self.exp_to_level
        self.exp_to_level = self.level * (150 - self.intelligence)
        cprint("{} exp needed for the next level.".format(self.exp_to_level - self.exp), "yellow")

        bonus = random.randint(0,2)
        if bonus != 0:
            self.strength_base += bonus
            cprint("Strength went up by {}".format(bonus))
        bonus = random.randint(0,2)
        if bonus != 0:
            self.finesse_base += bonus
            cprint("Finesse went up by {}".format(bonus))
        bonus = random.randint(0, 2)
        if bonus != 0:
            self.speed_base += bonus
            cprint("Speed went up by {}".format(bonus))
        bonus = random.randint(0,2)
        if bonus != 0:
            self.endurance_base += bonus
            cprint("Endurance went up by {}".format(bonus))
        bonus = random.randint(0,2)
        if bonus != 0:
            self.charisma_base += bonus
            cprint("Charisma went up by {}".format(bonus))
        bonus = random.randint(0,2)
        if bonus != 0:
            self.intelligence_base += bonus
            cprint("Intelligence went up by {}".format(bonus))

        points = random.randint(5,10)

        while points > 0:
            selection = ''
            while selection == '':
                print('You have {} attribute points to distribute. Please select an attribute to increase.\n\n'
                      '(1) Strength     - {}\n'
                      '(2) Finesse      - {}\n'
                      '(3) Speed        - {}\n'
                      '(4) Endurance    - {}\n'
                      '(5) Charisma     - {}\n'
                      '(6) Intelligence - {}\n\n'.format(points, self.strength_base, self.finesse_base, self.speed_base,
                                                       self.endurance_base, self.charisma_base, self.intelligence_base))
                selection = input("Selection: ")
                if functions.is_input_integer(selection):
                    if int(selection) < 1 or int(selection) > 6:
                        cprint("Invalid selection. You must enter a choice between 1 and 6.", "red")
                        selection = ''
                else:
                    cprint("Invalid selection. You must enter a choice between 1 and 6.", "red")
                    selection = ''
            selection = int(selection)

            amt = ''
            while amt == '':
                amt = input("How many points would you like to allocate? ({} available, 0 to cancel)".format(points))
                if functions.is_input_integer(amt):
                    if int(amt) < 0 or int(amt) > points:
                        cprint("Invalid selection. You must enter an amount between 0 and {}.".format(points), "red")
                        amt = ''
                else:
                    cprint("Invalid selection. You must enter an amount between 0 and {}.".format(points), "red")
                    amt = ''
            amt = int(amt)

            if amt > 0:
                if selection == 1:
                    self.strength_base += amt
                    points -= amt
                    cprint("Strength increased by {}!".format(amt), "green")
                if selection == 2:
                    self.finesse_base += amt
                    points -= amt
                    cprint("Finesse increased by {}!".format(amt), "green")
                if selection == 3:
                    self.speed_base += amt
                    points -= amt
                    cprint("Speed increased by {}!".format(amt), "green")
                if selection == 4:
                    self.endurance_base += amt
                    points -= amt
                    cprint("Endurance increased by {}!".format(amt), "green")
                if selection == 5:
                    self.charisma_base += amt
                    points -= amt
                    cprint("Charisma increased by {}!".format(amt), "green")
                if selection == 6:
                    self.intelligence_base += amt
                    points -= amt
                    cprint("Intelligence increased by {}!".format(amt), "green")

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

    def refresh_enemy_list_and_prox(self):
        for enemy in self.combat_list:
            if not enemy.is_alive():
                self.combat_list.remove(enemy)
        remove_these = []  # since you can't mutate a dict while iterating over it, delegate this iteration to a list and THEN remove the enemy
        for enemy in self.combat_proximity:
            if not enemy.is_alive():
                remove_these.append(enemy)
        for enemy in remove_these:
            del self.combat_proximity[enemy]

    def death(self):
        for i in range(random.randint(2,5)):
            message = random.randint(0, len(self.combat_hurt_msg)-1)
            print(self.combat_hurt_msg[message])
            time.sleep(0.5)

        cprint('Jean groans weakly, then goes completely limp.', "red")
        time.sleep(4)

        cprint("""Jean's eyes seem to focus on something distant. A rush of memories enters his mind.""", "red")
        time.sleep(5)

        cprint("""Jean gasps as the unbearable pain wracks his body. As his sight begins to dim,
he lets out a barely audible whisper:""", "red")
        time.sleep(5)

        cprint('''"...Amelia... ...Regina... ...I'm sorry..."''', "red")
        time.sleep(5)

        cprint("Darkness finally envelopes Jean. His struggle is over now. It's time to rest.\n\n", "red")
        time.sleep(8)

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
                 "OOOO"       "YOoOOOOOOOOOOOOO"`  .   '"OOOOOOOOOOOOoOY"     "OOO"
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
        time.sleep(5)
        functions.await_input()

    def print_inventory(self):
        num_gold = 0
        num_consumable = 0
        num_weapon = 0
        num_armor = 0
        num_boots = 0
        num_helm = 0
        num_gloves = 0
        num_accessories = 0
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
                    if issubclass(item.__class__, items.Accessory):
                        num_accessories += 1
                    if issubclass(item.__class__, items.Special):
                        num_special += 1
                    else:
                        pass
            self.refresh_weight()
            cprint("=====\nInventory\n=====\n"
                      "Weight: {} / {}".format(self.weight_current, self.weight_tolerance), "cyan")
            cprint(
                      "Gold: {}\n\nSelect a category to view:\n\n(c) Consumables: {}\n"
                      "(w) Weapons: {}\n(a) Armor: {}\n(b) Boots: {}\n(h) Helms: {}\n(g) Gloves: {}\n(y) Accessories: {}\n(s) Special: {}\n"
                      "(x) Cancel\n"
                      .format(num_gold, num_consumable, num_weapon, num_armor, num_boots, num_helm, num_gloves, num_accessories, num_special), "cyan")

            choices = []
            inventory_selection = input(colored('Selection: ', "cyan"))
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
                if case('y', 'Accessories', 'accessories'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Accessory):
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
                inventory_selection = input(colored('View which? ', "cyan"))
                if not functions.is_input_integer(inventory_selection):
                    num_gold = num_consumable = num_weapon = num_armor = num_boots = num_helm = num_gloves = num_accessories = num_special = 0
                    continue
                for i, item in enumerate(choices):
                    if i == int(inventory_selection):
                        print(item, '\n')
                        if item.interactions:
                            self.inventory_item_sub_menu(item)
                        else:
                            functions.await_input()
            num_gold = num_consumable = num_weapon = num_armor = num_boots = num_helm = num_gloves = num_accessories = num_special = 0
            if inventory_selection == 'x':
                break

    def inventory_item_sub_menu(self, item):
        cprint("What would you like to do with this item?\n", "cyan")
        for i, action in enumerate(item.interactions):
            print("{}: {}".format(i, action.title()))
        print("(x): Nothing, nevermind.\n")
        selection = input(colored("Selection: ", "cyan"))
        if functions.is_input_integer(selection):
            selection = int(selection)
            if hasattr(item, item.interactions[selection]):
                method = getattr(item, item.interactions[selection])
                method(self)

    def equip_item(self, phrase=''):

        def confirm(thing):
            check = input(colored("Equip {}? (y/n)".format(thing.name), "cyan"))
            if check.lower() == ('y' or 'yes'):
                return True
            else:
                return False

        target_item = None
        candidates = []
        if phrase is not '':  # equip the indicated item, if possible
            lower_phrase = phrase.lower()
            for item in self.inventory:
                if hasattr(item, "isequipped"):
                    search_item = item.name.lower() + ' ' + item.announce.lower()
                    if (lower_phrase in search_item):
                        candidates.append(item)
            if target_item is None:
                for i, item in enumerate(self.current_room.items_here):
                    if hasattr(item, "isequipped"):
                        search_item = item.name.lower() + ' ' + item.announce.lower()
                        if lower_phrase in search_item:
                            candidates.append(self.current_room.items_here.pop(i))
        else:  # open the menu
            target_item = self.equip_item_menu()

        if len(candidates) == 1:
            target_item = candidates[0]
        else:
            for candidate in candidates:
                if confirm(candidate):
                    target_item = candidate
        if target_item is not None:
            if hasattr(target_item, "isequipped"):
                if target_item not in self.inventory:  # if the player equips an item from the ground or via an event, add to inventory
                    self.inventory.append(target_item)
                if target_item.isequipped:
                    print("{} is already equipped.".format(target_item.name))
                    answer = input(colored("Would you like to remove it? (y/n) ","cyan"))
                    if answer == 'y':
                        target_item.isequipped = False
                        if issubclass(target_item.__class__, items.Weapon):  # if the player is now unarmed, "equip" fists
                            self.eq_weapon = self.fists
                        cprint("Jean put {} back into his bag.".format(target_item.name),"cyan")
                        target_item.on_unequip(self)
                else:
                    count_subtypes = 0
                    for olditem in self.inventory:
                        replace_old = False
                        if target_item.maintype == olditem.maintype and olditem.isequipped:
                            if target_item.maintype == "Accessory":
                                if target_item.subtype == olditem.subtype:
                                    if target_item.subtype == "Ring" or target_item.subtype == "Bracelet" or target_item.subtype == "Earring":
                                        count_subtypes += 1
                                        if count_subtypes > 1:
                                            replace_old = True
                                    else:
                                        replace_old = True
                            else:
                                replace_old = True
                        if replace_old:
                            olditem.isequipped = False
                            cprint("Jean put {} back into his bag.".format(olditem.name), "cyan")
                            olditem.on_unequip(self)
                    target_item.isequipped = True
                    cprint("Jean equipped {}!".format(target_item.name), "cyan")
                    target_item.on_equip(self)
                    if issubclass(target_item.__class__, items.Weapon):
                        self.eq_weapon = target_item

    def equip_item_menu(self):
        num_weapon = 0
        num_armor = 0
        num_boots = 0
        num_helm = 0
        num_gloves = 0
        num_accessories = 0
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
                if issubclass(item.__class__, items.Accessory):
                    num_accessories += 1
                else:
                    pass
            cprint("=====\nChange Equipment\n=====\nSelect a category to view:\n\n"
                  "(w) Weapons: {}\n(a) Armor: {}\n(b) Boots: {}\n(h) Helms: {}\n(g) Gloves: {}\n(y) Accessories: {}\n(x) Cancel\n"
                  .format(num_weapon, num_armor, num_boots, num_helm, num_gloves, num_accessories), "cyan")

            choices = []
            inventory_selection = input(colored('Selection: ', "cyan"))
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
                if case('y', 'Accessories', 'accessories'):
                    for item in self.inventory:
                        if issubclass(item.__class__, items.Accessory):
                            choices.append(item)
                    break
                if case():
                    num_weapon = num_armor = num_boots = num_helm = num_gloves = num_accessories = 0
                    break
            if len(choices) > 0:
                for i, item in enumerate(choices):
                    if item.isequipped:
                        print(i, ': ', item.name, colored('(Equipped)', 'green'), '\n')
                    else:
                        print(i, ': ', item.name, '\n')
                inventory_selection = input(colored('Equip which? ', "cyan"))
                if not functions.is_input_integer(inventory_selection):
                    num_weapon = num_armor = num_boots = num_helm = num_gloves = num_accessories = 0
                    continue
                for i, item in enumerate(choices):
                    if i == int(inventory_selection):
                        return item
                    num_weapon = num_armor = num_boots = num_helm = num_gloves = num_accessories = 0
                    continue
            else:
                return None

    def use_item(self, phrase=''):
        if phrase == '':
            num_consumables = 0
            num_special = 0
            exit_loop = False
            while exit_loop is False:
                for item in self.inventory:  # get the counts of each item in each category
                    if issubclass(item.__class__, items.Consumable):
                        num_consumables += 1
                    if issubclass(item.__class__, items.Special):
                        num_special += 1
                    else:
                        pass
                cprint("=====\nUse Item\n=====\nSelect a category to view:\n\n"
                    "(c) Consumables: {}\n(s) Special: {}\n(x) Cancel\n"
                    .format(num_consumables, num_special), "cyan")
                choices = []
                inventory_selection = input(colored('Selection: ', "cyan"))
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
                    inventory_selection = input(colored('Use which? ', "cyan"))
                    if not functions.is_input_integer(inventory_selection):
                        num_consumables = num_special = 0
                        continue
                    for i, item in enumerate(choices):
                        if i == int(inventory_selection):
                            print("Jean used {}!".format(item.name))
                            item.use(self)
                            if self.in_combat:
                                exit_loop = True
                            break

                num_consumables = num_special = 0
                if inventory_selection == 'x':
                    exit_loop = True

        else:
            lower_phrase = phrase.lower()
            for i, item in enumerate(self.inventory):
                if issubclass(item.__class__, items.Consumable) or issubclass(item.__class__, items.Special):
                    search_item = item.name.lower() + ' ' + item.announce.lower()
                    if lower_phrase in search_item:
                        confirm = input(colored("Use {}? (y/n)".format(item.name), "cyan"))
                        if confirm == 'y' or 'Y' or 'yes' or 'Yes' or 'YES':
                            item.use(self)
                            break

    def move(self, dx, dy):
        self.universe.game_tick += 1
        self.location_x += dx
        self.location_y += dy
        print(self.universe.tile_exists(self.map, self.location_x, self.location_y).intro_text())
        # if self.game_tick - world.tile_exists(self.location_x, self.location_y).last_entered >= world.tile_exists(
        #         self.location_x, self.location_y).respawn_rate:
        #     pass

    def move_north(self, phrase=''):
        self.move(dx=0, dy=-1)

    def move_south(self, phrase=''):
        self.move(dx=0, dy=1)

    def move_east(self, phrase=''):
        self.move(dx=1, dy=0)

    def move_west(self, phrase=''):
        self.move(dx=-1, dy=0)

    def move_northeast(self, phrase=''):
        self.move(dx=1, dy=-1)

    def move_northwest(self, phrase=''):
        self.move(dx=-1, dy=-1)

    def move_southeast(self, phrase=''):
        self.move(dx=1, dy=1)

    def move_southwest(self, phrase=''):
        self.move(dx=-1, dy=1)

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

    def look(self, target=None):
        if target is not None:
            self.view(target)
        else:
            print(self.current_room.intro_text())

    def view(self, phrase=''):
        # print(phrase)
        if phrase == '':
            stuff_here = {}
            for i, thing in enumerate(self.current_room.npcs_here + self.current_room.items_here +
                                              self.current_room.objects_here):
                if not thing.hidden and thing.name != 'null':
                    stuff_here[str(i)] = thing
            if len(stuff_here) > 0:
                print("What would you like to view?\n\n")
                for k, v in stuff_here.items():
                    print(k, ": ", v.name)
                choice = input("Selection: ")
                if choice in stuff_here:
                    print(stuff_here[choice].description)
                    functions.await_input()
                else:
                    print("Invalid selection.")
            else:
                print("Jean doesn't see anything remarkable here to look at.\n")
        else:
            lower_phrase = phrase.lower()
            for i, thing in enumerate(self.current_room.npcs_here + self.current_room.items_here +
                                              self.current_room.objects_here):
                if not thing.hidden and thing.name != 'null':
                    announce = ""
                    idle = ""
                    if hasattr(thing, "announce"):
                        announce = thing.announce
                    if hasattr(thing, "idle_message"):
                        idle = thing.idle_message
                    search_item = thing.name.lower() + ' ' + announce.lower() + ' ' + idle.lower()
                    if lower_phrase in search_item:
                        print(thing.description)
                        functions.await_input()
                        break

    def search(self, phrase=''):
        print("Jean searches around the area...")
        search_ability = int(((self.finesse * 2) + (self.intelligence * 3) + self.faith) * random.uniform(0.5, 1.5))
        time.sleep(5)
        something_found = False
        for hidden in self.current_room.npcs_here:
            if hidden.hidden == True:
                if search_ability > hidden.hide_factor:
                    print("Jean uncovered " + hidden.discovery_message)
                    something_found = True
                    hidden.hidden = False
        for hidden in self.current_room.items_here:
            if hidden.hidden == True:
                if search_ability > hidden.hide_factor:
                    print("Jean found " + hidden.discovery_message)
                    something_found = True
                    hidden.hidden = False
        for hidden in self.current_room.objects_here:
            if hidden.hidden == True:
                if search_ability > hidden.hide_factor:
                    print("Jean found " + hidden.discovery_message)
                    something_found = True
                    hidden.hidden = False
        if not something_found:
            print("...but he couldn't find anything of interest.")

    def menu(self, phrase=''):
        functions.autosave(self)
        self.main_menu = True

    def save(self, phrase=''):
        functions.save_select(self)

    def stack_inv_items(self):
        for master_item in self.inventory:  # traverse the inventory for stackable items, then stack them
            if hasattr(master_item, "count"):
                remove_duplicates = []
                for duplicate_item in self.inventory:
                    if duplicate_item != master_item and master_item.__class__ == duplicate_item.__class__:
                        master_item.count += duplicate_item.count
                        remove_duplicates.append(duplicate_item)
                if hasattr(master_item, "stack_grammar"):
                    master_item.stack_grammar()
                for duplicate in remove_duplicates:
                    self.inventory.remove(duplicate)

    def commands(self, phrase=''):
        possible_actions = self.current_room.available_actions()
        for action in possible_actions:
            cprint('{}:{}{}'.format(action.name, (' ' * (20 - (len(action.name) + 2))), action.hotkey), "blue")
        functions.await_input()

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
        available_moves = self.known_moves[:]
        for move in available_moves:
            if not move.viable():
                available_moves.remove(move)
        return available_moves

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

    def attack(self, phrase=''):
        target = None

        def strike():
            print(colored("Jean strikes with his " + self.eq_weapon.name + "!", "green"))
            power = self.eq_weapon.damage + \
                    (self.strength * self.eq_weapon.str_mod) + \
                    (self.finesse * self.eq_weapon.fin_mod)
            hit_chance = (98 - target.finesse) + self.finesse
            if hit_chance < 5:  # Minimum value for hit chance
                hit_chance = 5
            roll = random.randint(0, 100)
            damage = (power - target.protection) * random.uniform(0.8, 1.2)
            if damage <= 0:
                damage = 0
            glance = False
            if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
                damage /= 2
                glance = True
            damage = int(damage)
            self.combat_exp += 10
            if hit_chance >= roll:  # a hit!
                if glance:
                    print(colored(self.name, "cyan") + colored(" just barely hit ", "yellow") +
                          colored(target.name, "magenta") + colored(" for ", "yellow") +
                          colored(damage, "red") + colored(" damage!", "yellow"))
                else:
                    print(colored(self.name, "cyan") + colored(" struck ", "yellow") +
                          colored(target.name, "magenta") + colored(" for ", "yellow") +
                          colored(damage, "red") + colored(" damage!", "yellow"))
                target.hp -= damage
            else:
                print(colored("Jean", "cyan") + "'s attack just missed!")

        if phrase == '':
            targets_here = {}
            for i, possible_target in enumerate(self.current_room.npcs_here):
                if not possible_target.hidden and possible_target.name != 'null':
                    targets_here[str(i)] = possible_target
            if len(targets_here) > 0:
                print("Which target would you like to attack?\n\n")
                for k, v in targets_here.items():
                    print(k, ": ", v.name)
                choice = input("Selection: ")
                if choice in targets_here:
                    target = targets_here[choice]
                    strike()
                else:
                    print("Invalid selection.")
                    return
            else:
                print("There's nothing here for Jean to attack.\n")
                return
        else:
            lower_phrase = phrase.lower()
            success = False
            for i, potential_target in enumerate(self.current_room.npcs_here):
                if not potential_target.hidden and potential_target.name != 'null':
                    announce = ""
                    idle = ""
                    if hasattr(potential_target, "announce"):
                        announce = potential_target.announce
                    if hasattr(potential_target, "idle_message"):
                        idle = potential_target.idle_message
                    search_item = potential_target.name.lower() + ' ' + announce.lower() + ' ' + idle.lower()
                    if lower_phrase in search_item:
                        target = potential_target
                        strike()
                        success = True
                        break
            if not success:
                print("That's not a valid target for Jean to attack.\n")
                return

        # The following is not accessible if the strike was never attempted (no valid target, invalid selection, etc.)
        # Engage the target in combat!
        if target.is_alive():
            print(target.name + " " + target.alert_message)

        target.in_combat = True
        self.combat_list = [target]

        check_other_aggro_enemies = functions.check_for_combat(self)  # run an aggro check; will add additional enemies to the fray if they spot the player
        if target in check_other_aggro_enemies:
            check_other_aggro_enemies.remove(target)
        self.combat_list = self.combat_list + check_other_aggro_enemies

        if target.is_alive() or check_other_aggro_enemies:
            print(colored("Jean readies himself for battle!", "red"))
        combat.combat(self)

    def refresh_weight(self):
        self.weight_current = decimal.Decimal(0)
        for item in self.inventory:
            if hasattr(item, 'weight'):
                addweight = decimal.Decimal(item.weight)
                if hasattr(item, 'count'):
                    addweight *= item.count
                self.weight_current += addweight
        self.weight_current = decimal.Decimal(self.weight_current)

    def take(self, phrase=''):
        if phrase == '':  # player entered general take command with no args. Show a list of items that can be taken.
            if len(self.current_room.items_here) > 0:
                print("What are you trying to take?")
                for i, item in enumerate(self.current_room.items_here):
                    print('{}: {}\n'.format(i, item.name))
                selection = input('Selection: ')
                if not functions.is_input_integer(selection):
                    cprint("Jean isn't sure exactly what he's trying to do.", 'red')
                else:
                    item = self.current_room.items_here[int(selection)]
                    if hasattr(item, "weight"):
                        checkweight = item.weight
                        weightcap = self.weight_tolerance - self.weight_current
                        if hasattr(item, "count"):
                            checkweight *= item.weight
                        if checkweight <= weightcap:
                            self.inventory.append(item)
                            print('Jean takes {}.'.format(item.name))
                            self.current_room.items_here.remove(item)
                    else:
                        self.inventory.append(item)
                        print('Jean takes {}.'.format(item.name))
                        self.current_room.items_here.remove(item)


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

    def view_map(self, phrase=''):
        '''First draw a map if known tiles by iterating over self.map and checking self.map.last_entered to see if the
        player has discovered that tile. If so, place a square at those coordinates.'''
        # determine boundaries
        max_x = 0
        max_y = 0
        for key in self.map:
            if key != 'name' and self.universe.tile_exists(self.map, key[0], key[1]):
                if self.universe.tile_exists(self.map, key[0], key[1]).discovered:
                    test_x = int(key[0])
                    test_y = int(key[1])
                    if test_x > max_x:
                        max_x = test_x
                    if test_y > max_y:
                        max_y = test_y
        #iterate over the map and begin drawing
        map_lines = []
        for y in range(max_y + 2):
            line = ''
            for x in range(max_x + 2):
                if self.universe.tile_exists(self.map, x, y):
                    if self.map[(x,y)] == self.current_room:
                        line += 'X'
                    else:
                        if self.map[x,y].last_entered > 0:
                            line += self.map[(x,y)].symbol
                        elif self.map[x,y].discovered:
                            line += '?'
                        else:
                            line += "'"
                else:
                    line += "'"
            map_lines.append(line)
        for i in map_lines:
            print(i)
        functions.await_input()

    def recall_friends(self):
        party_size = len(self.combat_list_allies)-1
        for friend in self.combat_list_allies:
            if friend.current_room != self.current_room:
                friend.current_room.npcs_here.remove(friend)
                friend.current_room = self.current_room
                friend.current_room.npcs_here.append(friend)
        if party_size == 1:
            print(colored(self.combat_list_allies[1].name, "cyan") + colored(" follows Jean.", "green"))
        elif party_size == 2:
            print(colored(self.combat_list_allies[1].name, "cyan") + colored(" and ", "green") + colored(self.combat_list_allies[2].name, "cyan")
                  + colored("follow Jean.", "green"))
        elif party_size >= 3:
            output = ""
            for friend in range(party_size-1):
                output += colored(self.combat_list_allies[friend+1].name, "cyan") + colored(", ", "green")
            output += colored(", and ", "green") + colored(self.combat_list_allies[party_size].name, "cyan") + colored(" follow Jean.", "green")
            print(output)