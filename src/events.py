"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""
from termcolor import colored, cprint
import threading
import random
import time
import objects, functions

class EventThread(threading.Thread):
    def __init__(self, event):
        threading.Thread.__init__(self)
        self.event = event

    def run(self):
        self.event.process()


class Event: #master class for all events
    '''
    Events are added to tiles much like NPCs and items. These are evaluated each game loop to see if the conditions
    of the event are met. If so, execute the 'process' function, else pass.
    Set repeat to True to automatically repeat for each game loop; setting parallel to True opens a new thread
    params is a list of additional parameters, None if omitted.

    '''
    def __init__(self, name, player, tile, repeat, parallel, params):
        self.name = name
        self.player = player
        self.tile = tile
        self.repeat = repeat
        self.parallel = parallel
        self.thread = None
        self.has_run = False
        self.params = params

    def pass_conditions_to_process(self):
        if self.repeat:
            self.call_process()
        else:
            self.call_process()
            self.tile.events_here.remove(self)  # if this is a one-time event, kill it after it executes

    def call_process(self):  # allows switching between parallel and standard processing
        if self.parallel:  #todo figure out why parallel isn't working
            self.thread = EventThread(self)
            self.thread.run()
        else:
            self.process()

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        """
        to be overwritten by an event subclass
        """
        pass


class GoldFromHeaven(Event):  # Gives the player a certain amount of gold... for testing? Or just fun.
    def __init__(self, player, tile, repeat, parallel, name='Gold From Heaven'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel, params=None)

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        print("Oddly enough, a pouch of gold materializes in front of you.")
        self.tile.spawn_item('Gold', amt=77)


class Block(Event):  # blocks exit in tile, blocks all if none are declared
    def __init__(self, player, tile, params, repeat, parallel, name='Block'):
        super().__init__(name=name, player=player, tile=tile, params=params, repeat=repeat, parallel=parallel)
        self.directions = []
        if not params:
            self.directions = ['north', 'south', 'east', 'west']
        else:
            self.directions = params

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        for direction in self.directions:
            if direction == 'east' and 'east' not in self.tile.block_exit:
                self.tile.block_exit.append('east')
            if direction == 'west' and 'west' not in self.tile.block_exit:
                self.tile.block_exit.append('west')
            if direction == 'north' and 'north' not in self.tile.block_exit:
                self.tile.block_exit.append('north')
            if direction == 'south' and 'south' not in self.tile.block_exit:
                self.tile.block_exit.append('south')


# class Unblock(Event):  # unblocks exit in tile, unblocks all if none are declared
#     def __init__(self, player, tile, repeat, parallel, params, name='Unblock'):
#         super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel, params=params)
#         self.directions = []
#         if not params:
#             self.directions = ['north', 'south', 'east', 'west']
#         else:
#             self.directions = params
#
#     def check_conditions(self):
#         if True:
#             self.pass_conditions_to_process()
#
#     def process(self):
#         for direction in self.directions:
#             if direction == 'east' and 'east' in self.tile.block_exit:
#                 self.tile.block_exit.remove('east')
#             if direction == 'west' and 'west' in self.tile.block_exit:
#                 self.tile.block_exit.remove('west')
#             if direction == 'north' and 'north' in self.tile.block_exit:
#                 self.tile.block_exit.remove('north')
#             if direction == 'south' and 'south' in self.tile.block_exit:
#                 self.tile.block_exit.remove('south')

class CombatEvent(Event):  # Occurs when Jean beats the first rumbler after opening the chest
    def __init__(self, player, tile, params, name, repeat=False, parallel=False):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel, params=params)

    def check_combat_conditions(self, beat):
        """ conditions can pull from data passed into the function as parameters.
        Most relevant data can be accessed through the player, player.tile, etc.
        """
        if True:  # change to any arbitrary code to fit the situation
            self.pass_conditions_to_process()

    def pass_conditions_to_process(self):
        if self.repeat:
            self.call_process()
        else:
            self.call_process()
            self.player.combat_events.remove(self)  # if this is a one-time event, kill it after it executes

    def process(self):
        pass


class Ch01_PostRumbler(CombatEvent):
    def __init__(self, player, tile, params, repeat=False, parallel=False, name='Ch01_PostRumbler'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel, params=params)

    def check_combat_conditions(self, beat):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self):
        cprint("\nThe ground quivers slightly as more rock creatures appear.\n")
        time.sleep(0.5)
        for x in range(0,2):
            npc = getattr(__import__('npc'), "RockRumbler")()
            self.player.current_room.npcs_here.append(npc)
            self.player.combat_list.append(npc)
        self.player.combat_events.append(
            getattr(__import__('events'), "Ch01_PostRumbler2")(player=self.player, tile=self.tile, params=False,
                                                              repeat=False, parallel=False))

class Ch01_PostRumbler2(CombatEvent):
    def __init__(self, player, tile, params, repeat=False, parallel=False, name='Ch01_PostRumbler2'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel, params=params)

    def check_combat_conditions(self, beat):
        if self.player.get_hp_pcnt() < 0.3:
            self.pass_conditions_to_process()

    def process(self):
        cprint("\nSuddenly, a loud 'crack' thunders through the chamber. A nearby wall splits open and a massive figure "
               "leaps out, smashing its huge fist down on top of one of the rock creatures.")
        self.player.combat_list[0].hp = 0  # instagib one of the rock creatures
        print(colored( self.player.combat_list[0].name, "magenta") + " exploded into fragments of light!")
        self.player.current_room.npcs_here.remove(self.player.combat_list[0])
        self.player.combat_list.remove(self.player.combat_list[0])
        time.sleep(0.5)
        cprint("The massive figure somewhat resembles a man, except he is covered head-to-toe in armor not much different from the chamber walls.")
        cprint("Two more rock creatures advance on him, snapping their heavy jaws.")
        cprint("Without saying a word, he hands a strange vial to Jean and gesticulates with large, clumsy hands, then turns to face the creatures.")
        time.sleep(4)
        cprint("\nSensing the urgency of his situation, Jean quaffs the strange liquid.")
        cprint("It burns in his throat, but he can feel strength quickly returning to his limbs.")
        cprint("Jean would like to thank the strange rock-man, but he's not out of danger just yet.")
        self.player.hp = self.player.maxhp
        self.player.fatigue = self.player.maxfatigue
        self.player.heat += 0.75
        self.player.combat_events.append(
            getattr(__import__('events'), "Ch01_PostRumbler3")(player=self.player, tile=self.tile, params=False,
                                                               repeat=False, parallel=False))

class Ch01_PostRumbler3(CombatEvent):
    def __init__(self, player, tile, params, repeat=False, parallel=False, name='Ch01_PostRumbler2'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel, params=params)

    def check_combat_conditions(self, beat):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self):
        time.sleep(1)
        cprint("\nWiping sweat from his brow, Jean looks up to see the rock-man surrounded by the beasts, "
               "\nswinging wildly with a large stone column it had picked up from the floor."
               "\nWhile he wouldn't feel right abandoning the rock-man to an ill fate, now"
               "\nis the perfect time to make a break for the hole that was opened in the"
               "\nchamber wall. There isn't enough time to consider alternatives.")
        time.sleep(12)
        cprint("\nWhich should Jean choose?"
               "\nA: I'm not some filthy coward! (Help rock-man)"
               "\nB: It can't be helped. I must survive! (Make a break for it)"
               "\nC: I need more time to think! (Consider alternatives)\n", 'cyan', attrs=['bold'])
        choices = ["a","b","c"]
        while True:
            choice_input = input('Choice: ')
            choice_input = choice_input.lower()
            if choice_input in choices:
                break
            else:
                cprint("You must choose one of the following: " + str(choices))
        time.sleep(3)
        #  a is the correct choice, so evaluate that last
        if choice_input == "b" or choice_input == "c":
            if choice_input == "b":
                cprint("Jean swallows hard and begins sprinting toward the hole in the chamber wall.")
            elif choice_input == "c":
                cprint("Unsure of what to do, Jean stands frozen, glancing between the rock-man and his"
                       "\navenue of escape.")
            time.sleep(4)
            cprint("Rock-man manages to smash one of the beasts beneath his large column-turned-bludgeon,"
                   "\nhowever one of the other beasts jumps on his back at that moment, knocking him "
                   "\nquickly to the ground. The other beasts pile on and begin slashing and biting"
                   "\nmercilessly.")
            time.sleep(8)
            cprint("Just before Jean can make his escape, a beast jumps and slides between Jean and"
                   "\nhis salvation, kicking up loose dirt and pebbles. Jean quickly dodges to the side"
                   "\nand tries to circle back to the entrance from which he came."
                   "\nJumping around the snapping jaws and swinging tails of the other beasts,"
                   "\nHe manages to make it back to the long bridge connecting the two spires.")
            time.sleep(12)
            cprint("He can hear the beasts behind him, but they seemed to have stopped at"
                   "\nthe threshold separating the chamber entrance and the outside,"
                   "\nas if they are afraid of the daylight.")
            time.sleep(10)
            cprint("Jean straightens up and begins to catch his breath. Just as he breathes"
                   "\na sigh of relief, a piercing screech rings through his ears,"
                   "\na great cold wind blows over him, and two sharp claws dig"
                   "\nruthlessly into his shoulders, picking him up off of the"
                   "\nbridge.")
            time.sleep(8)
            cprint("He looks up at the horrible monster that grabbed him and"
                   "\nis terrified at the ugly abomination. Rows upon rows"
                   "\nof jagged teeth, three sunken black eyes staring"
                   "\nhungrily at him, a froth of saliva spilling out of"
                   "\nits disgusting maw.")
            time.sleep(8)
            cprint("Jean gasps and gropes uselessly at the sharp claws"
                   "\nstill digging painfully into his flesh. He swings"
                   "\nhis mace and lands a blow on the twisted, scaly"
                   "\ncalf of the abominable demon.")
            time.sleep(8)
            cprint("The monster lets out a loud screech, and swooping"
                   "\nquickly, smashes Jean's body against the wall of rock.")
            time.sleep(3)
            cprint("Jean suffers " + str(random.randint(30,90)) + " damage!", "red")
            time.sleep(3)
            cprint("Jean screams in pain, his mace arm swinging uselessly by"
                   "\nhis side, broken.")
            time.sleep(5)
            cprint("Again, the monster smashes Jean against the wall,"
                   "\nrepeatedly and without hesitation or mercy,"
                   "\nbefore slamming him hard into the ground.")
            time.sleep(1)
            cprint("Jean suffers " + str(random.randint(30,90)) + " damage!", "red")
            time.sleep(1)
            cprint("Jean suffers " + str(random.randint(10,60)) + " damage!", "red")
            time.sleep(1)
            cprint("Jean suffers " + str(random.randint(30,90)) + " damage!", "red")
            time.sleep(1)
            cprint("Jean suffers " + str(random.randint(85,155)) + " damage!", "red")
            self.player.hp = 0
            time.sleep(3)
            #  deth
        else:
            cprint("Jean grits his teeth, then begins running toward one of the beasts"
                   "\nsurrounding the rock man. He shouts loudly, and plants his mace"
                   "\nsquarely between the ferocious snapper's eyes. The beast explodes"
                   "\ninto brilliant fragments of light.")
            time.sleep(8)
            cprint("The other creatures turn toward Jean in alarm. Rock-man takes this"
                   "\nopportunity to smash one of them into the wall with a great swing"
                   "\nfrom his large column.")
            time.sleep(8)
            cprint("Rock-man glances over at Jean and with another gesticulation,"
                   "\nnods his head in respect. Both prepare themselves for the "
                   "\ndifficult fight that remains.")
            time.sleep(8)

            #  OK, so at this point you need to add the "friendly NPC" feature to the combat.
            #  Don't forget that the enemies need to be able to target friendly NPCs as well!
            #  For some reason Gorran is attacking himself and Jean xD plz fix

            npc = getattr(__import__('npc'), "Gorran")()
            self.player.current_room.npcs_here.append(npc)
            self.player.combat_list_allies.append(npc)

            for x in range(0, 3):
                npc = getattr(__import__('npc'), "RockRumbler")()
                self.player.current_room.npcs_here.append(npc)
                self.player.combat_list.append(npc)


class Story(Event):  # Executes the story event with the given ID, where params=ID
    def __init__(self, player, tile, repeat, parallel, params, name='Story'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel, params=params)
        self.disable = {}  # key is the story ID, value is whether it's disabled (ex 0:False)
        for id in params:
            self.disable[id] = False

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        for param in self.params:
            if param == 'start_open_wall':
                if not self.disable[param]:
                    wall_switch = None
                    for object in self.tile.objects_here:
                        if object.name == 'Wall Depression':
                            wall_switch = object
                    # if wall_switch.position == True:
                    cprint("A loud rumbling fills the chamber as the wall slowly opens up, revealing an exit to the"
                          " east.", 'yellow')
                    self.tile.block_exit.remove('east')
                    self.disable[param] = True # disables this event
                    self.tile.description = """
        Now that an exit in the east wall has been revealed, the room has been filled with warmth and light. A bright
        blue sky is visible through the hole in the rock. The faint sound of birds chirping and water flowing can be
        heard.
        """
                    for object in self.tile.objects_here:
                        if isinstance(object, objects.Tile_Description):
                            self.tile.objects_here.remove(object)
                            break
                    for object in self.tile.objects_here:
                        if object == wall_switch:
                            self.tile.objects_here.remove(object)
                            break
                    time.sleep(0.5)
            elif param == 'start_open_bridgewall':
                if not self.disable[param]:
                    wall_switch = None
                    for object in self.tile.objects_here:
                        if object.name == 'Wall Depression':
                            wall_switch = object
                    # if wall_switch.position == True:
                    cprint("The rock face splits open with a loud rumble as a dark and somewhat foreboding doorway appears.", 'yellow')
                    self.tile.block_exit.remove('east')
                    self.disable[param] = True
                    self.tile.description = """
                The rock ledge continues to the east and terminates as it reaches the wall. From this vantage point,
                large mountains can be seen to the northwest, covered in white clouds at their crowns.

                A dark gaping hole in the shape of a doorway is cut out of the eastern rock face.
                """
                    for object in self.tile.objects_here:
                        if isinstance(object, objects.Tile_Description):
                            self.tile.objects_here.remove(object)
                            break
                    for object in self.tile.objects_here:
                        if object == wall_switch:
                            self.tile.objects_here.remove(object)
                            break
                    time.sleep(0.5)

            elif param == 'start_chest_rumbler_battle':
                if not self.disable[param]:
                    time.sleep(2)
                    cprint("Apparently, there is also a rusty iron mace in the chest. Jean takes it and swings it around gently, testing its balance.")
                    time.sleep(3)
                    mace = getattr(__import__('items'), 'RustedIronMace')()
                    self.player.inventory.append(mace)
                    mace.isequipped = True
                    self.player.eq_weapon = mace
                    self.player.refresh_moves()
                    cprint("Suddenly, Jean hears a loud rumbling noise and the sound of scraping rocks.", 'yellow')
                    self.disable[param] = True
                    self.tile.spawn_npc("RockRumbler")
                    cprint("A rock-like creature appears and advances toward Jean!")
                    time.sleep(0.5)
                    self.player.combat_events.append(getattr(__import__('events'), "Ch01_PostRumbler")(player=self.player, tile=self.tile, params=False, repeat=False, parallel=False))

            else:
                temp = '!!!param error: params='
                for p in self.params:
                    temp += p
                    temp += ', '
                print(temp)