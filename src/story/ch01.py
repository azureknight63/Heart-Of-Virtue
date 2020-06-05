"""
Chapter 01 events
"""
from termcolor import colored, cprint
import threading
import random
import time, inspect
import objects, functions
from ..events import *


class Ch01StartOpenWall(Event):
    '''
    The first event. Opens the wall in the starting room when the player 'presses' the wall depression
    '''
    def __init__(self, player, tile, params, repeat=True, name='Ch01_Start_Open_Wall'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        for room_object in self.tile.objects_here:
            if room_object.name == 'Wall Depression':
                if room_object.position:
                    self.pass_conditions_to_process()

    def process(self):
        wall_switch = self.tile.objects_here[0]
        for room_object in self.tile.objects_here:
            if room_object.name == 'Wall Depression':
                wall_switch = room_object
        cprint("A loud rumbling fills the chamber as the wall slowly opens up, revealing an exit to the"
              " east.", 'yellow')
        self.tile.block_exit.remove('east')
        self.tile.description = """
Now that an exit in the east wall has been revealed, the room has been filled with warmth and light. A bright
blue sky is visible through the hole in the rock. The faint sound of birds chirping and water flowing can be
heard.
"""
        for room_object in self.tile.objects_here:
            if isinstance(room_object, objects.Tile_Description):
                self.tile.objects_here.remove(room_object)
                break
        for room_object in self.tile.objects_here:
            if room_object == wall_switch:
                self.tile.objects_here.remove(room_object)
                break
        time.sleep(0.5)


class Ch01BridgeWall(Event):
    '''
    Opens the wall on the bridge in the starting area
    '''
    def __init__(self, player, tile, params, repeat=True, name='Ch01_Bridge_Wall'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        for room_object in self.tile.objects_here:
            if room_object.name == 'Wall Depression':
                if room_object.position:
                    self.pass_conditions_to_process()

    def process(self):
        wall_switch = self.tile.objects_here[0]
        for room_object in self.tile.objects_here:
            if room_object.name == 'Wall Depression':
                wall_switch = room_object
        cprint("The rock face splits open with a loud rumble as a dark and somewhat foreboding doorway appears.",
               'yellow')
        self.tile.block_exit.remove('east')
        self.tile.description = """
                        The rock ledge continues to the east and terminates as it reaches the wall. From this vantage point,
                        large mountains can be seen to the northwest, covered in white clouds at their crowns.

                        A dark gaping hole in the shape of a doorway is cut out of the eastern rock face.
                        """
        for room_object in self.tile.objects_here:
            if isinstance(room_object, objects.Tile_Description):
                self.tile.objects_here.remove(room_object)
                break
        for room_object in self.tile.objects_here:
            if room_object == wall_switch:
                self.tile.objects_here.remove(room_object)
                break
        time.sleep(0.5)


class Ch01ChestRumblerBattle(Event):
    '''
    Initiates the battle with rock rumblers when the chest at (7,1) is looted
    '''
    def __init__(self, player, tile, params, repeat=True, name='Ch01_Chest_Rumbler_Battle'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        for thing in self.params:
            if hasattr(thing, "name"):
                if thing.name == "Wooden Chest":
                    if len(thing.contents) == 0:  # if the chest is empty, continue
                        self.pass_conditions_to_process()
                        break

    def process(self):
        time.sleep(2)
        cprint(
            "Apparently, there is also a rusty iron mace in the chest. Jean takes it and swings it around gently, testing its balance.")
        time.sleep(3)
        mace = getattr(__import__('items'), 'RustedIronMace')()
        self.player.inventory.append(mace)
        self.player.equip_item(mace.name)
        #mace.isequipped = True
        #self.player.eq_weapon = mace
        cprint("Suddenly, Jean hears a loud rumbling noise and the sound of scraping rocks.", 'yellow')
        self.tile.spawn_npc("RockRumbler")
        cprint("A rock-like creature appears and advances toward Jean!")
        time.sleep(0.5)
        self.player.combat_events.append(Ch01PostRumbler(player=self.player, tile=self.tile, params=False,
                                                              repeat=False))
        self.tile.events_here.remove(self)


class Ch01PostRumbler(Event): # Occurs when Jean beats the first rumbler after opening the chest
    def __init__(self, player, tile, params, repeat=False, name='Ch01_PostRumbler'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_combat_conditions(self, beat):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self):
        cprint("\nThe ground quivers slightly as more rock creatures appear.\n")
        time.sleep(0.5)
        for x in range(0,2):
            npc = self.tile.spawn_npc("RockRumbler")
            npc.combat_engage(self.player)
        self.player.combat_events.append(Ch01PostRumblerRep(player=self.player, tile=self.tile, params=False,
                                                              repeat=True))
        self.player.combat_events.append(Ch01PostRumbler2(player=self.player, tile=self.tile, params=False,
                                                              repeat=False))


class Ch01PostRumblerRep(Event):
    def __init__(self, player, tile, params, repeat=True, name='Ch01_PostRumbler_Rep'):  # This event is to continue repeating until the player's health is low
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)
        self.iteration = 2

    def check_combat_conditions(self, beat):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self):
        cprint("\nThe ground quivers slightly as even more rock creatures appear.\n")
        time.sleep(0.5)
        for x in range(0,self.iteration):
            npc = self.tile.spawn_npc("RockRumbler")
            npc.combat_engage(self.player)
            self.iteration += 1


class Ch01PostRumbler2(Event):
    def __init__(self, player, tile, params, repeat=False, name='Ch01_PostRumbler2'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_combat_conditions(self, beat):
        if self.player.get_hp_pcnt() < 0.3:
            self.pass_conditions_to_process()

    def process(self):
        for event in self.player.combat_events:
            if event.name == 'Ch01_PostRumbler_Rep':
                self.player.combat_events.remove(event)  # Remove the repeating event
        cprint("\nSuddenly, a loud 'crack' thunders through the chamber. A nearby wall splits open and a massive figure "
               "leaps out, smashing its huge fist down on top of one of the rock creatures.")
        time.sleep(2)
        self.player.combat_list[0].hp = 0  # instagib one of the rock creatures
        print(colored( self.player.combat_list[0].name, "magenta") + " exploded into fragments of light!")
        self.player.current_room.npcs_here.remove(self.player.combat_list[0])
        self.player.combat_list.remove(self.player.combat_list[0])
        self.player.refresh_enemy_list_and_prox()
        time.sleep(3)
        cprint("The massive figure somewhat resembles a man, except he is covered head-to-toe in armor not much different from the chamber walls.")
        time.sleep(3)
        cprint("Two more rock creatures advance on him, snapping their heavy jaws.")
        time.sleep(3)
        cprint("Without saying a word, he hands a strange vial to Jean and gesticulates with large, clumsy hands, then turns to face the creatures.")
        time.sleep(4)
        cprint("\nSensing the urgency of his situation, Jean quaffs the strange liquid.")
        time.sleep(3)
        cprint("It burns in his throat, but he can feel strength quickly returning to his limbs.")
        time.sleep(3)
        cprint("Jean would like to thank the strange rock-man, but he's not out of danger just yet.")
        if len(self.player.combat_list) == 0:
            npc = self.tile.spawn_npc("RockRumbler")
            npc.combat_engage(self.player)
        self.player.hp = self.player.maxhp
        self.player.fatigue = self.player.maxfatigue
        self.player.heat += 0.75
        self.player.combat_events.append(Ch01PostRumbler3(player=self.player, tile=self.tile, params=False,
                                                               repeat=False))


class Ch01PostRumbler3(Event):
    def __init__(self, player, tile, params, repeat=False, name='Ch01_PostRumbler2'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

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
                   "\nleg of the abominable demon.")
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
            time.sleep(2)
            cprint("Jean suffers " + str(random.randint(85,155)) + " damage!", "red")
            self.player.hp = 0
            time.sleep(5)
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

            npc = self.tile.spawn_npc("Gorran", delay=0)
            self.player.combat_list_allies.append(npc)
            npc.in_combat = True

            for x in range(0, 5):
                npc = self.tile.spawn_npc("RockRumbler", delay=random.randint(0,14))
                npc.combat_engage(self.player)

            self.tile.events_here.append(AfterTheRumblerFight(self.player, self.tile, None))


class AfterTheRumblerFight(Event):
    '''
    After the fight, Gorran tells Jean that they will talk, but not here. Too dangerous. Gorran then waits for Jean to speak to him again.
    '''
    def __init__(self, player, tile, params, repeat=False, name='AfterTheRumblerFight'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        if not self.player.in_combat:
            self.pass_conditions_to_process()

    def process(self):
        time.sleep(5)
        print("The Rock-Man lowers his club to the ground and turns toward Jean.")
        time.sleep(3)
        self.dialogue("Jean", "I suppose I should thank you for saving my skin. What is your name?", "cyan")
        print("The Rock-Man stands immobile for a long moment, then slowly gestures toward himself. He begins to speak in low, rumbling tones.")
        self.dialogue("Rock-Man", "Mmmmm... Go-rra-nnnnnn...", "green")
        self.dialogue("Jean", "Go... rran? Well, thank you, Gorran. But what were those things? I've never seen their like in my life!", "cyan")
        print("Gorran lets out a deep, low rumble, then gestures toward the wall from which he apparently came.")
        self.dialogue("Rock-Man", "Time... short. Not... safe... to linger. Speak... to Gorran again... when ready.", "green")
        for npc in self.tile.npcs_here:
            if npc.name == "Rock-Man":
                npc.name = "Gorran"
                if npc in self.player.combat_list_allies:
                    self.player.combat_list_allies.remove(npc)


class AfterGorranIntro(Event):
    '''
    When Jean talks to Gorran again (for the first time?) Gorran leads Jean through an
    opening in the rock to the Verdette Caverns, heading for the Grondite town.
    '''
    def __init__(self, player, tile, params, repeat=False, name='AfterGorranIntro'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        self.pass_conditions_to_process()

    def process(self):
        time.sleep(1)
        print("Gorran gestures toward the opening in the wall. The two walk over. Jean can see that the opening is much too small for him to\n"
              "pass through. Gorran waves an arm toward it and, miraculously, the opening widens with a loud rumble. Gorran walks through and\n"
              "Jean, with trepidation, follows.")
        functions.await_input()
        for gorran in self.tile.npcs_here:
            if gorran.name == "Gorran":
                self.player.combat_list_allies.append(gorran)
        self.player.teleport("verdette_caverns 2 1")
