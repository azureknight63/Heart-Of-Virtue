import random
import time
import math
import traceback

from switch import switch

import items
import functions
import moves
import combat
import skilltree

from neotermcolor import colored, cprint
from universe import tile_exists as tile_exists


def generate_output_grid(data, rows=0, cols=0, border="*", data_color="green",
                         data_attr=None, border_color="magenta", border_attr=None):
    """
    Generates a grid from the provided list

    :param data: A list of strings
    :param rows: Number of rows. Will set automatically if left at zero
    :param cols: Number of columns. Will set automatically if left at zero
    :param border: This string pattern will form the border between rows and columns
    :param data_color: The _color and _attr options mirror neotermcolor.colored()
    :param data_attr: Attribues to apply to the data such as normal, bold, dark, underline, blink, reverse, concealed
    :param border_color: Color for the grid border
    :param border_attr: Attributes to apply to the border
    :return: A string formatted in a grid shape
    """
    rows_var = rows
    cols_var = cols
    output = ""
    if rows_var <= 0:  # I don't know how many rows I want, so let's try to find it automatically
        if cols_var > 0:  # I do know how many columns I want, so we can calculate the rows based on that
            rows_var = math.ceil(len(data) / cols_var)
        else:  # I want to figure out the grid arrangement automatically!
            # This will make the grid as "square" as possible
            rows_var = cols_var = math.ceil(math.sqrt(len(data)))
            if (rows_var * cols_var) > (len(data) + cols_var):
                rows_var -= 1
    row_width_compatibility_verified = False  # we will need to make sure the width of the row
    # will fit in the stout display
    cell_max_length = 1
    row_length = 1
    data_raw = data[:]
    for item in data_raw:  # this will iterate over all of the strings in the data list to find the length of
        # the longest one; necessary for padding cells
        item = functions.escape_ansi(item)
        if len(item) > cell_max_length:
            cell_max_length = len(item)

    while not row_width_compatibility_verified:  # this is to make sure the rows don't get too long to display.
        # It will override any row/column parameters
        row_length = ((cell_max_length + len(border) + 2) * cols_var) + len(border)
        if row_length <= 300:
            row_width_compatibility_verified = True
        else:
            cols_var -= 1
            rows_var += 1
        if rows_var == 0:  # this will only happen if the data list contains a really long string over
            # the defined limit.
            rows_var = 1  # In which case, just show all on one line.
            row_width_compatibility_verified = True
            cols_var = len(data)

    data_index = 0
    for row in range(rows_var):
        row_output = (colored(border * (math.ceil(row_length / len(border))), color=border_color, attrs=border_attr) +
                      "\n")  # insert the row border on top
        for col in range(cols_var):
            try:
                cell_value = data[data_index]
            except IndexError:  # we've reached the end of our data list
                continue
            while len(functions.escape_ansi(cell_value)) < cell_max_length:  # this will pad our cell to the right
                cell_value += " "
            cell_value = colored(cell_value, color=data_color, attrs=data_attr)
            row_output += colored(border, color=border_color, attrs=border_attr) + " " + cell_value + " "
            data_index += 1
        row_output += colored(border, color=border_color, attrs=border_attr)
        output += row_output + "\n"
    output += colored(border * (math.ceil(row_length / len(border))), color=border_color, attrs=border_attr)
    # ^^^ final row border at the bottom
    return output


class Player:
    def __init__(self):
        self.inventory = [items.Gold(15), items.TatteredCloth(), items.ClothHood(), items.JeanWeddingBand()]
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
        # A note about resistances: 1.0 means "no effect." 0.5 means "damage/chance reduced by half."
        # 2.0 means "double damage/chance."
        # Negative values mean the damage is absorbed (heals instead of damages.) Status resistances cannot be negative.
        self.resistance = {
            "fire": 1.0,
            "ice": 1.0,
            "shock": 1.0,
            "earth": 1.0,
            "light": 1.0,
            "dark": 1.0,
            "piercing": 1.0,
            "slashing": 1.0,
            "crushing": 1.0,
            "spiritual": 1.0,
            "pure": 1.0
        }
        self.resistance_base = {
            "fire": 1.0,
            "ice": 1.0,
            "shock": 1.0,
            "earth": 1.0,
            "light": 1.0,
            "dark": 1.0,
            "piercing": 1.0,
            "slashing": 1.0,
            "crushing": 1.0,
            "spiritual": 1.0,
            "pure": 1.0
        }
        self.status_resistance = {
            "generic": 1.0,  # Default status type for all states
            "stun": 1.0,  # Unable to move; typically short duration
            "poison": 1.0,  # Drains Health every combat turn/game tick; persists
            "enflamed": 1.0,  # Fire damage over time
            "sloth": 1.0,  # Drains Fatigue every combat turn
            "apathy": 1.0,  # Drains HEAT every combat turn
            "blind": 1.0,  # Miss physical attacks more frequently; persists
            "incoherence": 1.0,  # Miracles fail more frequently; persists
            "mute": 1.0,  # Cannot use Miracles; persists
            "enraged": 1.0,  # Double physical damage given and taken
            "enchanted": 1.0,  # Double magical damage given and taken
            "ethereal": 1.0,  # Immune to physical damage but take 3x magical damage; persists
            "berserk": 1.0,  # Auto attack, 1.5x physical damage
            "slow": 1.0,  # All move times are doubled
            "sleep": 1.0,  # Unable to move; removed upon physical damage
            "confusion": 1.0,  # Uses random moves on random targets; removed upon physical damage
            "cursed": 1.0,  # Makes luck 1, chance of using a random move with a random target; persists
            "stop": 1.0,  # Unable to move; not removed with damage
            "stone": 1.0,  # Unable to move; immune to damage; permanent death if allowed to persist after battle
            "frozen": 1.0,  # Unable to move; removed with Fire magic;
            # permanent death if allowed to persist after battle
            "doom": 1.0,  # Death after n turns/ticks; persists; lifted with purification magic ONLY
            "death": 1.0
        }
        self.status_resistance_base = {
            "generic": 1.0,
            "stun": 1.0,
            "poison": 1.0,
            "enflamed": 1.0,
            "sloth": 1.0,
            "apathy": 1.0,
            "blind": 1.0,
            "incoherence": 1.0,
            "mute": 1.0,
            "enraged": 1.0,
            "enchanted": 1.0,
            "ethereal": 1.0,
            "berserk": 1.0,
            "slow": 1.0,
            "sleep": 1.0,
            "confusion": 1.0,
            "cursed": 1.0,
            "stop": 1.0,
            "stone": 1.0,
            "frozen": 1.0,
            "doom": 1.0,
            "death": 1.0
        }
        self.weight_tolerance = 20.00
        self.weight_tolerance_base = 20.00
        self.weight_current = 0.00
        self.fists = items.Fists()
        self.eq_weapon = self.fists
        self.combat_exp = {"Basic": 0, "Unarmed": 0}  # place to pool all exp gained from a
        # single combat before distribution
        self.exp = 0  # exp to be gained from doing stuff rather than killing things
        self.skill_exp = {"Basic": 0, "Unarmed": 0}  # pools exp gained in combat or otherwise to be
        # spent on learning skills
        self.skilltree = skilltree.Skilltree(self)
        for subtype in self.skilltree.subtypes.keys():  # initialize an exp pool for each skill subtype
            self.skill_exp[subtype] = 0
        self.level = 1
        self.exp_to_level = 100
        self.location_x, self.location_y = (0, 0)
        self.current_room = None
        self.victory = False
        self.known_moves = [  # this should contain ALL known moves, regardless of whether they are
            # viable (moves will check their own conditions)
            moves.Check(self), moves.Wait(self), moves.Rest(self),
            moves.UseItem(self), moves.Advance(self), moves.Withdraw(self), moves.Attack(self), moves.ShootBow(self)
        ]
        self.current_move = None
        self.heat = 1.0
        self.protection = 0
        self.states = []
        self.in_combat = False
        self.combat_events = []  # list of pending events in combat. If non-empty, combat will be paused
        # while an event happens
        self.combat_list = []  # populated by enemies currently being encountered. Should be empty outside of combat
        self.combat_list_allies = [self]  # friendly NPCs in combat that either help the player or just stand
        # there looking pretty
        self.combat_proximity = {}  # dict for unit proximity: {unit: distance}; Range for most melee weapons is 5,
        # ranged is 20. Distance is in feet (for reference)
        self.default_proximity = 50
        self.savestat = None
        self.saveuniv = None
        self.universe = None
        self.map = None
        self.main_menu = False  # escape switch to get to the main menu; setting to True jumps out of the play loop
        self.time_elapsed = 0  # total seconds of gameplay
        self.pronouns = {
            "personal": "he", "possessive": "his", "reflexive": "himself", "intensive": "himself"
        }
        self.preferences = {
            "arrow": "Wooden Arrow"
        }  # player defined preferences will live here; for example, "arrow" = "Wooden Arrow"
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

        self.prayer_msg = [
            "A warm sense of peace fills Jean's heart.",
            'Jean frowns impatiently.',
            'Jean shudders slightly.',
            "Jean sees his wife's face for a brief moment and lets out a barely audible sigh. \n" +
            "The memory of her auburn braids swinging as she walked remains like a retinal burn. \n" +
            "Her other features are painfully mercurial and induce a burning sense of guilt.",
            'Jean grits his teeth and focuses hard on praying for his wife and daughter.',
            'Jean anxiously shifts his weight back and forth.',
            "Jean can still remember the look on the courier's face on that fateful day. "
            "He can still see the clothes he was wearing. \n" +
            "He can still smell the warm spring air. \nHe will never forget that day or the pain and anger "
            "that came with it.",
            'In spite of himself, Jean wonders just what, exactly, this is supposed to accomplish.',
            'Jean makes the sign of the cross.',
            """Jean prays quietly, 
            
Je vous salue, Marie, pleine de grâce, Le Seigneur est avec vous.
Vous êtes bénie entre toutes les femmes, et Jésus, le fruit de vos entrailles, est béni.
Sainte Marie, Mère de Dieu, priez pour nous, pauvres pécheurs,
maintenant et à l'heure de notre mort. Amen.""",
            'Jean becomes conscious of his own heart beating loudly.',
            'His little girl is laughing and running through a field of grass. '
            'Jean remembers how they would play together. \n'
            'She would tease him, calling him "Gros Glouton." He would call her "Paresseux Passereau."',
            'Jean feels the silence around him to be very heavy.',
            "An intense groaning makes its way through Jean's stomache.",
            "The smell of fresh, sweet lillies dances in Jean's memory. \nThey were Regina's favorite.",
        ]

    def cycle_states(self):
        """
        Loop through all of the states on the player and process the effects of each one
        """
        for state in self.states:
            state.process(self)

    def apply_state(self, state):
        player_has_state = False
        for player_state in self.states:
            if player_state.name == state.name:
                player_has_state = True
                if player_state.compounding:
                    player_state.compound(self)
                else:
                    self.states.remove(player_state)  # state is non-compounding; remove the existing state and
                    # replace with the new one (refreshes the state)
                    self.states.append(state)
                break
        if not player_has_state:
            self.states.append(state)

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
            chance = random.randint(0, 1000)
            if chance > 995:
                message = random.randint(0, len(self.combat_idle_msg) - 1)
                print(self.combat_idle_msg[message])
        else:
            chance = random.randint(0, 1000)  # combat hurt (injured)
            if chance > 950:
                message = random.randint(0, len(self.combat_hurt_msg) - 1)
                print(self.combat_hurt_msg[message])

    def gain_exp(self, amt, exp_type="Basic"):
        """
        Give the player amt exp, then check to see if he gained a level and act accordingly
        Also adds exp to the designated skill tree subtype. All abilities under that subtype gain the exp and are
        learned if possible.
        EXP is always added to the "Basic" subtype regardless of the subtype declared.
        """

        # self.skill_exp["Basic"] += amt
        # if exp_type != "Basic":

        if exp_type not in self.skill_exp:
            self.skill_exp[exp_type] = 0
        self.skill_exp[exp_type] += amt

        # Check through the players skill tree and announce if any skills may be learned
        announce = False
        for category, d in self.skilltree.subtypes.items():
            if category == exp_type:
                for skill, req in d.items():
                    if self.skill_exp[exp_type] >= req:
                        skill_is_already_learned = False
                        for known_skill in self.known_moves:
                            if skill.name == known_skill.name:
                                skill_is_already_learned = True
                                break
                        if not skill_is_already_learned:
                            announce = True
                    else:
                        continue
                if announce:
                    cprint(f"Jean may spend some of his earned exp to learn a new {exp_type} skill. "
                           f"Type SKILL to open the skill menu for details.", "magenta")
                break

        # remove = []
        # for k, v in self.skilltree.subtypes.items():
        #     if k == exp_type or k == "Basic":
        #         for skill, values in v.items():
        #             values[1] += amt
        #             if values[1] >= values[0]:
        #                 self.learn_skill(skill)
        #                 remove.append(skill)
        # for ability in remove:
        #     for k,v in self.skilltree.subtypes.items():
        #         if ability in v:
        #             v.pop(ability)
        #             break

        if self.level < 100:
            self.exp += amt
        while self.exp >= self.exp_to_level:
            self.level_up()

    def learn_skill(self, skill):
        success = True
        for move in self.known_moves:
            if move.name == skill.name:
                success = False
                break
        if success:
            cprint("Jean learned {}!".format(skill.name), "magenta")
            self.known_moves.append(skill)
        return skill
        # if not success, Jean already knows the skill so no need to do anything!

    def get_hp_pcnt(self):  # returns the player's remaining HP as a decimal
        curr = float(self.hp)
        maxhp = float(self.maxhp)
        return curr / maxhp

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
        self.current_room.spawn_event(params[0], self, self.current_room, repeat=repeat, params=[])  # will go fubar
        # if the name of the event is wrong or if other parameters are present in phrase

    def spawnobject(self, phrase=''):  # spawns an object (npc, item, room object, event) on the current tile
        """
        :param phrase: Pattern is "spawn obj_type obj params." Note the special instruction 'params=' refers to
        special params passed to room objects.
        :return: Nothing returned (action by player)
        """
        params = phrase.split(" ")
        obj_type = params[0].lower()
        obj = params[1].lower().title()
        if "_" in obj:
            obj = obj.replace("_", "")
        hidden = False
        hfactor = 0
        delay = -1
        count = 1
        repeat = False
        myparams = None
        if len(params) > 1:
            for item in params:
                if item == 'hidden':
                    hidden = True
                elif 'hfactor=' in item:
                    hfactor = int(item[8:])
                elif 'delay=' in item:
                    delay = int(item[6:])
                elif 'count=' in item:
                    count = int(item[6:])
                elif 'repeat' in item:
                    repeat = True
                elif 'params=' in item:
                    myparams = item[7:].split(",")

        try:
            for i in range(count):
                if obj_type == "npc":
                    self.current_room.spawn_npc(obj, hidden=hidden, hfactor=hfactor, delay=delay)
                elif obj_type == "item":
                    self.current_room.spawn_item(obj, hidden=hidden, hfactor=hfactor)
                elif obj_type == "event":
                    self.current_room.spawn_event(obj, self, self.current_room, repeat=repeat, params=myparams)
                elif obj_type == "object":
                    self.current_room.spawn_object(obj, self, self.current_room, myparams, hidden=hidden, hfactor=0)
        except SyntaxError:
            cprint("Oops, something went wrong. \n\n" + traceback.format_exc())

    def vars(self):  # print all variables
        print(self.universe.story)

    def alter(self, phrase=''):
        params = phrase.split(" ")
        self.universe.story[params[0]] = params[1]
        if self.universe.story[params[0]]:
            try:
                self.universe.story[params[0]] = params[1]
                print("### SUCCESS: " + params[0] + " changed to " + params[1] + " ###")
            except SyntaxError:
                print("### ERR IN SETTING VAR; BAD ARGUMENTS: " + params[0] + " " + params[1] + " ###")
        else:
            print("### ERR IN SETTING VAR; NO ENTRY: " + params[0] + " " + params[1] + " ###")

    def teleport(self, phrase=''):
        params = phrase.split(" ")
        for area in self.universe.maps:
            if area['name'] == params[0]:
                tele_to = area
                tile = tile_exists(tele_to, int(params[1]), int(params[2]))
                if tile:
                    self.map = tele_to
                    self.universe.game_tick += 1
                    self.location_x = int(params[1])
                    self.location_y = int(params[2])
                    print(tile_exists(self.map, self.location_x, self.location_y).intro_text())
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

        attributes = [
            ("strength_base", colored("Strength", "magenta"), 1),
            ("finesse_base", colored("Finesse", "magenta"), 2),
            ("speed_base", colored("Speed", "magenta"), 3),
            ("endurance_base", colored("Endurance", "magenta"), 4),
            ("charisma_base", colored("Charisma", "magenta"), 5),
            ("intelligence_base", colored("Intelligence", "magenta"), 6)
        ]

        for attr, attr_name, i in attributes:
            bonus = random.randint(0, 2)
            if bonus != 0:
                current_value = getattr(self, attr)
                setattr(self, attr, current_value + bonus)
                print(f"{attr_name} went up by {colored(str(bonus), 'yellow')}.")
                time.sleep(2)

        points = random.randint(6, 9)

        while points > 0:
            print(f'You have {colored(str(points), "yellow")} additional attribute points to distribute. '
                  f'Please select an attribute to increase:\n')
            for attr, attr_name, i in attributes:
                print(f'({i}) {attr_name} - {getattr(self, attr)}')

            selection = input("Selection: ")
            if not selection.isdigit() or (1 > int(selection) > 6):
                cprint("Invalid selection. You must enter a choice between 1 and 6.", "red")
                continue

            selection = int(selection)
            set_attr = ""
            set_attr_name = ""
            for attr, attr_name, i in attributes:
                if selection == i:
                    set_attr, set_attr_name = attr, attr_name
                    break

            amt = input(f"How many points would you like to allocate? ({points} available, 0 to cancel) ")
            if not amt.isdigit() or not (0 <= int(amt) <= points):
                cprint(f"Invalid selection. You must enter an amount between 0 and {points}.", "red")
                continue

            amt = int(amt)
            if amt > 0:
                setattr(self, set_attr, getattr(self, set_attr) + amt)
                points -= amt
                cprint(f"{set_attr_name} increased by {amt}!", "green")

    def change_heat(self, mult=1, add=0):  # enforces boundaries with min and max heat levels
        self.heat *= mult
        self.heat += add
        self.heat = int((self.heat * 100) + 0.5) / 100.0  # enforce 2 decimals
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
        remove_these = []  # since you can't mutate a dict while iterating over it, delegate this iteration to a
        # list and THEN remove the enemy
        for enemy in self.combat_proximity:
            if not enemy.is_alive():
                remove_these.append(enemy)
        for enemy in remove_these:
            del self.combat_proximity[enemy]

    def death(self):
        for i in range(random.randint(2, 5)):
            message = random.randint(0, len(self.combat_hurt_msg) - 1)
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

    def skillmenu(self):
        """
        Opens the skill menu for the player so he may inspect or learn skills
        :return:
        """  # todo various issues with this menu; needs colorization as well. Could benefit from gridding.
        # Learning a skill does not update the preceding menu.
        menu = []  # each entry is a tuple; the first element of the tuple is the subcat name,
        # the second is "0: Subtype (*****0 exp); 0 skills"
        for item, exp in self.skill_exp.items():
            skillcount = len(self.skilltree.subtypes[item])  # number of skills in the subcategory
            menu.append((item, f"{item} ({exp:>6,} exp); {skillcount} skills"))
        finished = False
        while not finished:
            cprint("*** SKILL MENU ***\n\nSelect a category to view or learn skills.\n\n", "cyan")
            for i, v in enumerate(menu):
                cprint("{}: {}".format(i, v[1]), "cyan")
            cprint("x: Exit menu", "cyan")
            selection = None
            while not selection:
                response = input(colored('Selection: ', "cyan"))
                if functions.is_input_integer(response):
                    if (len(menu) > int(response)) and (int(response) >= 0):  # handles index errors
                        selection = response
                elif response.lower() == "x":
                    selection = response.lower()
                else:
                    selection = "x"
            if selection != "x":
                # Display all available skills, including those learned already
                skills_to_display = []  # list of tuples; (skill_object, requirement, display_text, is_learned)
                subcat = menu[int(selection)][0]
                for skill, req in self.skilltree.subtypes[subcat].items():
                    known = False
                    for known_skill in self.known_moves:
                        if skill.name == known_skill.name:
                            known = True
                            break
                    if known:
                        skills_to_display.append((skill, req, "{} (LEARNED)".format(skill.name), True))
                    else:
                        skills_to_display.append((skill, req, "{} ({})".format(skill.name, req), False))
                inner_selection_finished = False
                while not inner_selection_finished:
                    for i, v in enumerate(skills_to_display):
                        cprint("{}: {}".format(i, v[2]), "cyan")
                    cprint("k: Return to skill menu", "cyan")
                    cprint("x: Exit menu", "cyan")
                    inner_selection = None
                    while not inner_selection:
                        response = input(colored('Selection: ', "cyan"))
                        if functions.is_input_integer(response):
                            if len(skills_to_display) > int(response):
                                inner_selection = response
                        elif response.lower() in ['k', 'x']:
                            inner_selection = response.lower()
                        else:
                            cprint("Invalid response! Please try again.", "red")
                    if inner_selection == "k":  # The player wishes to exit the inner menu and return to
                        # the main skill menu
                        inner_selection_finished = True
                    if inner_selection == "x":  # The player wishes to exit the menu entirely
                        inner_selection_finished = True
                        finished = True
                    elif functions.is_input_integer(inner_selection):
                        # The player has chosen a skill to investigate. Show details and provide a small menu of
                        # actions to perform
                        skill_menu_choice = skills_to_display[int(inner_selection)]
                        skill_object = skill_menu_choice[0]
                        info = """
    === SKILL INFORMATION ===
    {}
    -------------------------
    {}
    -------------------------""".format(skill_object.name, skill_object.description)
                        cprint(info, "cyan")
                        cprint("Available {} experience: {}\n".format(subcat, self.skill_exp[subcat]))
                        if not skill_menu_choice[3]:
                            if self.skill_exp[subcat] >= skill_menu_choice[1]:
                                cprint("Cost: {}\n\nTo learn this skill, enter 'LEARN'.\n"
                                       "Enter anything else to return to the skill menu.".format(skill_menu_choice[1]),
                                       "cyan")
                                response = input(colored('Selection: ', "cyan"))
                                if response.lower() == "learn":
                                    self.learn_skill(skill_object)
                                    self.skill_exp[subcat] -= skill_menu_choice[1]
                                    functions.await_input()
                            else:
                                cprint("Cost: {}".format(skill_menu_choice[1]), "red")
                                functions.await_input()
                        else:
                            cprint("Jean knows this skill.", "cyan")
                            functions.await_input()
            else:
                finished = True

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
                "(w) Weapons: {}\n(a) Armor: {}\n(b) Boots: {}\n(h) Helms: {}\n(g) Gloves: {}\n(y) Accessories: "
                "{}\n(s) Special: {}\n(x) Cancel\n"
                .format(num_gold, num_consumable, num_weapon, num_armor, num_boots, num_helm, num_gloves,
                        num_accessories, num_special), "cyan")

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
                    item_preference_value = ""
                    for prefitem in self.preferences.values():
                        if prefitem == item.name:
                            item_preference_value = colored("(P)", "magenta")
                    if hasattr(item, 'isequipped'):
                        if item.isequipped:
                            print(i, ': ', item.name, colored('(Equipped)', 'green'), ' ', item_preference_value, '\n')
                        else:
                            print(i, ': ', item.name, ' ', item_preference_value, '\n')
                    else:
                        if hasattr(item, 'count'):
                            print(i, ': ', item.name, ' (', item.count, ')', ' ', item_preference_value, '\n')
                        else:
                            print(i, ': ', item.name, ' ', item_preference_value, '\n')
                inventory_selection = input(colored('View which? ', "cyan"))
                if not functions.is_input_integer(inventory_selection):
                    num_gold = num_consumable = num_weapon = num_armor = num_boots = num_helm = num_gloves = \
                        num_accessories = num_special = 0
                    continue
                for i, item in enumerate(choices):
                    if i == int(inventory_selection):
                        print(item, '\n')
                        if item.subtype == "Arrow":
                            if self.preferences["arrow"] == item.name:
                                print('\nThis is your preferred arrow type. You will choose this when shooting '
                                      'your bow as long as you have enough.\n'
                                      'If you select "prefer" again, you will remove this preference.'
                                      ' Having no arrow preference will force you to'
                                      ' choose the arrow you want each time you shoot.\n')
                        if item.interactions:
                            self.inventory_item_sub_menu(item)
                        else:
                            functions.await_input()
            num_gold = num_consumable = num_weapon = num_armor = num_boots = num_helm = num_gloves = \
                num_accessories = num_special = 0
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

    def print_status(self):
        functions.refresh_stat_bonuses(self)
        self.fatigue = self.maxfatigue
        self.refresh_protection_rating()
        cprint("=====\nStatus\n=====\n"
               "{}".format(self.name_long), "cyan")
        output_grid_data = [
            "Health: {} / {} ({})".format(self.hp, self.maxhp, self.maxhp_base),
            "Fatigue: {} ({})".format(self.fatigue, self.maxfatigue_base),
            "Weight Tolerance: {} / {} ({})".format(self.weight_current, self.weight_tolerance,
                                                    self.weight_tolerance_base),
            "Level: {} // Exp to next: {}".format(self.level, self.exp_to_level)
        ]
        print(generate_output_grid(output_grid_data, border="+++", border_color="red", border_attr=["dark"]))

        state_list = ""
        if len(self.states) > 0:
            for state in self.states:
                state_list += colored("{}".format(state.name), "white") + colored(" ({}) ".
                                                                                  format(state.steps_left),
                                                                                  "red")  # todo test this display
        else:
            state_list = "None"
        cprint("States: {}".format(state_list), "cyan")

        output_grid_data = []
        if self.protection < 0:
            output_grid_data.append("Protection: " + colored("{}".format(self.protection), "red"))
        elif self.protection > 0:
            output_grid_data.append("Protection: " + colored("{}".format(self.protection), "green"))
        else:
            output_grid_data.append("Protection: " + colored("{}".format(self.protection), "white"))

        charstats = [
            "strength", "finesse", "speed", "endurance", "charisma", "intelligence", "faith"
        ]
        for attribute in charstats:
            color = "white"
            if getattr(self, attribute) < getattr(self, attribute + "_base"):
                color = "red"
            elif getattr(self, attribute) > getattr(self, attribute + "_base"):
                color = "green"
            output_grid_data.append("{}: ".format(attribute.title()) +
                                    colored("{} ".format(getattr(self, attribute)), color) +
                                    colored("({})".format(getattr(self, attribute + "_base")), "white",
                                            attrs=["bold", "dark"])
                                    )
        print(generate_output_grid(output_grid_data, cols=2, data_color="white", data_attr=["bold", "dark"],
                                   border="=*="))

        cprint("Vulnerabilities:", "cyan")
        output_grid_data = []
        for n, v in self.resistance.items():
            resistance_value = v * 100
            n += ": "
            while len(n) < 11:
                n += " "  # this will pad the space between the resistance title and value
            if resistance_value == 100:
                output_grid_data.append(n.title() + "{}".format(colored(str(resistance_value) + "%", color="white",
                                                                        attrs=["bold"])))
            elif 0 <= resistance_value < 100:  # damage reduced
                output_grid_data.append(n.title() + "{}".format(colored(str(resistance_value) + "%", color="blue",
                                                                        attrs=["bold", "dark"])))
            elif resistance_value > 100:  # damage increased
                output_grid_data.append(n.title() + "{}".format(colored(str(resistance_value) + "%", color="red",
                                                                        attrs=["bold"])))
            else:  # damage absorbed
                output_grid_data.append(n.title() + "{}".format(colored(str(resistance_value) + "%", color="green",
                                                                        attrs=["bold"])))
        if len(output_grid_data) == 0:
            print("None")
        else:
            print(generate_output_grid(output_grid_data, border="-", border_color="yellow", border_attr=["bold"]))

        cprint("Susceptibilities:", "cyan")
        output_grid_data = []
        for n, v in self.status_resistance.items():
            resistance_value = v * 100
            n += ": "
            while len(n) < 11:
                n += " "  # this will pad the space between the resistance title and value
            if resistance_value == 100:
                output_grid_data.append(n.title() + "{}".format(colored(str(resistance_value) + "%", color="white",
                                                                        attrs=["bold"])))
            elif 0 <= resistance_value < 100:  # chance reduced
                output_grid_data.append(n.title() + "{}".format(colored(str(resistance_value) + "%", color="blue",
                                                                        attrs=["bold", "dark"])))
            else:  # chance increased
                output_grid_data.append(n.title() + "{}".format(colored(str(resistance_value) + "%", color="red",
                                                                        attrs=["bold"])))
        if len(output_grid_data) == 0:
            print("None")
        else:
            print(generate_output_grid(output_grid_data, border="~", border_color="blue", border_attr=["bold"]))

        functions.await_input()

    def equip_item(self, phrase=''):

        def confirm(thing):
            check = input(colored("Equip {}? (y/n)".format(thing.name), "cyan"))
            if check.lower() == ('y' or 'yes'):
                return True
            else:
                return False

        target_item = None
        candidates = []
        if phrase != '':  # equip the indicated item, if possible
            lower_phrase = phrase.lower()
            for item in self.inventory:
                if hasattr(item, "isequipped"):
                    search_item = item.name.lower() + ' ' + item.announce.lower()
                    if lower_phrase in search_item:
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
                if target_item not in self.inventory:  # if the player equips an item from the ground or via an event,
                    # add to inventory
                    self.inventory.append(target_item)
                if target_item.isequipped:
                    print("{} is already equipped.".format(target_item.name))
                    answer = input(colored("Would you like to remove it? (y/n) ", "cyan"))
                    if answer == 'y':
                        target_item.isequipped = False
                        if issubclass(target_item.__class__, items.Weapon):  # if the player is now unarmed,
                            # "equip" fists
                            self.eq_weapon = self.fists
                        cprint("Jean put {} back into his bag.".format(target_item.name), "cyan")
                        target_item.on_unequip(self)
                        target_item.interactions.remove("unequip")
                        target_item.interactions.append("equip")
                else:
                    count_subtypes = 0
                    for olditem in self.inventory:
                        replace_old = False
                        if target_item.maintype == olditem.maintype and olditem.isequipped:
                            if target_item.maintype == "Accessory":
                                if target_item.subtype == olditem.subtype:
                                    if (target_item.subtype == "Ring" or target_item.subtype == "Bracelet" or
                                            target_item.subtype == "Earring"):
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
                            olditem.interactions.remove("unequip")
                            olditem.interactions.append("equip")
                    target_item.isequipped = True
                    cprint("Jean equipped {}!".format(target_item.name), "cyan")
                    target_item.on_equip(self)
                    target_item.interactions.remove("equip")
                    target_item.interactions.append("unequip")
                    if issubclass(target_item.__class__, items.Weapon):
                        self.eq_weapon = target_item
                    if hasattr(target_item, "subtype") and target_item.gives_exp:
                        if target_item.subtype not in self.combat_exp:
                            self.combat_exp[target_item.subtype] = 0  # if the player hasn't equipped this
                            # before and it has a subtype, open an exp category
                            self.skill_exp[target_item.subtype] = 0
                    functions.refresh_stat_bonuses(self)
                    self.refresh_protection_rating()

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
            cprint(f"=====\nChange Equipment\n=====\nSelect a category to view:\n\n"
                   f"(w) Weapons: {num_weapon}\n(a) Armor: {num_armor}\n(b) Boots: {num_boots}\n(h) Helms: {num_helm}"
                   f"\n(g) Gloves: {num_gloves}\n(y) Accessories: {num_accessories}\n(x) Cancel\n",
                   "cyan")

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
                cprint(f"=====\nUse Item\n=====\nSelect a category to view:\n\n"
                       f"(c) Consumables: {num_consumables}\n(s) Special: {num_special}\n(x) Cancel\n", "cyan")
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
                        item_preference_value = ""
                        for prefitem in self.preferences.values():
                            if prefitem == item.name:
                                item_preference_value = colored("(P)", "magenta")
                        if hasattr(item, 'isequipped'):
                            if item.isequipped:
                                print(i, ': ', item.name, colored('(Equipped)', 'green'), ' ',
                                      item_preference_value, '\n')
                            else:
                                print(i, ': ', item.name, ' ', item_preference_value, '\n')
                        else:
                            if hasattr(item, 'count'):
                                print(i, ': ', item.name, ' (', item.count, ')', ' ', item_preference_value, '\n')
                            else:
                                print(i, ': ', item.name, ' ', item_preference_value, '\n')
                    inventory_selection = input(colored('Use which? ', "cyan"))
                    if not functions.is_input_integer(inventory_selection):
                        num_consumables = num_special = 0
                        continue
                    for i, item in enumerate(choices):
                        if i == int(inventory_selection):
                            if "use" in item.interactions and hasattr(item, "use"):
                                print("Jean used {}!".format(item.name))
                                item.use(self)
                            elif "prefer" in item.interactions and hasattr(item, "prefer"):
                                item.prefer(self)
                            else:
                                for interaction in item.interactions:  # this will search through the item's available
                                    # interactions and attempt to execute
                                    if interaction != "drop" and hasattr(item, "exec"):  # this will only occur if I
                                        # forgot to handle the interaction above (see "use" and "prefer")
                                        item.exec(interaction + "(self)")
                                        break
                                    else:
                                        continue  # no available interactions; dump back to menu.
                                        # Theoretically, this should never happen.
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
                    if lower_phrase in search_item and hasattr(item, "use"):
                        confirm = input(colored("Use {}? (y/n)".format(item.name), "cyan"))
                        acceptable_confirm_phrases = ['y', 'Y', 'yes', 'Yes', 'YES']
                        if confirm in acceptable_confirm_phrases:
                            item.use(self)
                            break

    def move(self, dx, dy):
        self.universe.game_tick += 1
        self.location_x += dx
        self.location_y += dy
        print(tile_exists(self.map, self.location_x, self.location_y).intro_text())
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

    def move_northeast(self):
        self.move(dx=1, dy=-1)

    def move_northwest(self):
        self.move(dx=-1, dy=-1)

    def move_southeast(self):
        self.move(dx=1, dy=1)

    def move_southwest(self):
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

    def search(self):
        print("Jean searches around the area...")
        search_ability = int(((self.finesse * 2) + (self.intelligence * 3) + self.faith) * random.uniform(0.5, 1.5))
        time.sleep(5)
        something_found = False
        for hidden in self.current_room.npcs_here:
            if hidden.hidden:
                if search_ability > hidden.hide_factor:
                    print("Jean uncovered " + hidden.discovery_message)
                    something_found = True
                    hidden.hidden = False
        for hidden in self.current_room.items_here:
            if hidden.hidden:
                if search_ability > hidden.hide_factor:
                    print("Jean found " + hidden.discovery_message)
                    something_found = True
                    hidden.hidden = False
        for hidden in self.current_room.objects_here:
            if hidden.hidden:
                if search_ability > hidden.hide_factor:
                    print("Jean found " + hidden.discovery_message)
                    something_found = True
                    hidden.hidden = False
        if not something_found:
            print("...but he couldn't find anything of interest.")

    def menu(self):
        functions.autosave(self)
        self.main_menu = True

    def save(self):
        functions.save_select(self)

    def stack_inv_items(self):
        for master_item in self.inventory:  # traverse the inventory for stackable items, then stack them
            if hasattr(master_item, "count"):
                remove_duplicates = []
                for duplicate_item in self.inventory:
                    if duplicate_item != master_item and master_item.__class__ == duplicate_item.__class__\
                            and hasattr(duplicate_item, "count"):
                        master_item.count += duplicate_item.count
                        remove_duplicates.append(duplicate_item)
                if hasattr(master_item, "stack_grammar"):
                    master_item.stack_grammar()
                for duplicate in remove_duplicates:
                    self.inventory.remove(duplicate)

    def commands(self):
        possible_actions = self.current_room.available_actions()
        for action in possible_actions:
            cprint('{}:{}{}'.format(action.name, (' ' * (20 - (len(action.name) + 2))), action.hotkey), "blue")
        functions.await_input()

    def show_bars(self, hp=True, fp=True):  # show HP and Fatigue bars
        if hp:
            hp_pcnt = float(self.hp) / float(self.maxhp)
            hp_pcnt = int(hp_pcnt * 10)
            hp_string = colored("HP: ", "red") + "["
            for bar in range(0, hp_pcnt):
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
            for bar in range(0, fat_pcnt):
                fat_string += colored("█", "green")
            for blank in range(fat_pcnt + 1, 10):
                fat_string += " "
            fat_string += "]"
        else:
            fat_string = ''

        print(hp_string + fat_string)

    def refresh_moves(self):
        available_moves = []
        for move in self.known_moves:
            if move.viable():
                available_moves.append(move)
        return available_moves

    def refresh_protection_rating(self):
        self.protection = (self.endurance / 10)  # base level of protection from player stats
        for item in self.inventory:
            if hasattr(item, "isequipped"):
                if item.isequipped and hasattr(item, "protection"):  # check the protection level of all
                    # equipped items and add to base
                    add_prot = item.protection
                    if hasattr(item, "str_mod"):
                        add_prot += item.str_mod * self.strength
                    if hasattr(item, "fin_mod"):
                        add_prot += item.fin_mod * self.finesse
                    self.protection += add_prot

    def attack(self, phrase=''):  # todo add ability to strike with a ranged weapon like a bow
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
            self.combat_exp["Basic"] += 10
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

        check_other_aggro_enemies = functions.check_for_combat(self)  # run an aggro check;
        # will add additional enemies to the fray if they spot the player
        if target in check_other_aggro_enemies:
            check_other_aggro_enemies.remove(target)
        self.combat_list = self.combat_list + check_other_aggro_enemies

        if target.is_alive() or check_other_aggro_enemies:
            print(colored("Jean readies himself for battle!", "red"))
        combat.combat(self)

    def refresh_weight(self):
        self.weight_current = 0.00
        for item in self.inventory:
            if hasattr(item, 'weight'):
                addweight = item.weight
                if hasattr(item, 'count'):
                    addweight *= item.count
                self.weight_current += addweight
        self.weight_current = round(self.weight_current, 2)

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
                            item.owner = self
                    else:
                        self.inventory.append(item)
                        print('Jean takes {}.'.format(item.name))
                        self.current_room.items_here.remove(item)
                        item.owner = self

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

    def view_map(self):
        """First draw a map of known tiles by iterating over self.map and checking self.map.last_entered to see if the
        player has discovered that tile. If so, place a square at those coordinates."""
        # determine boundaries
        max_x = 0
        max_y = 0
        for key in self.map:
            if key != 'name' and tile_exists(self.map, key[0], key[1]):
                if tile_exists(self.map, key[0], key[1]).discovered:
                    test_x = int(key[0])
                    test_y = int(key[1])
                    if test_x > max_x:
                        max_x = test_x
                    if test_y > max_y:
                        max_y = test_y
        # iterate over the map and begin drawing
        map_lines = []
        for y in range(max_y + 2):
            line = ''
            for x in range(max_x + 2):
                if tile_exists(self.map, x, y):
                    if self.map[(x, y)] == self.current_room:
                        line += 'X'
                    else:
                        if self.map[x, y].last_entered > 0:
                            line += self.map[(x, y)].symbol
                        elif self.map[x, y].discovered:
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
        party_size = len(self.combat_list_allies) - 1
        for friend in self.combat_list_allies:
            if friend.current_room != self.current_room:
                friend.current_room.npcs_here.remove(friend)
                friend.current_room = self.current_room
                friend.current_room.npcs_here.append(friend)
        if party_size == 1:
            print(colored(self.combat_list_allies[1].name, "cyan") + colored(" follows Jean.", "green"))
        elif party_size == 2:
            print(colored(self.combat_list_allies[1].name, "cyan") + colored(" and ", "green") +
                  colored(self.combat_list_allies[2].name, "cyan")
                  + colored("follow Jean.", "green"))
        elif party_size >= 3:
            output = ""
            for friend in range(party_size - 1):
                output += (colored(self.combat_list_allies[friend + 1].name, "cyan") +
                           colored(", ", "green"))
            output += colored(", and ", "green") + colored(
                self.combat_list_allies[party_size].name, "cyan") + colored(" follow Jean.", "green")
            print(output)
