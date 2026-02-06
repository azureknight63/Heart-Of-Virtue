"""
Chapter 01 events
"""

from neotermcolor import cprint, colored
import time
import random

from events import Event, dialogue
import objects as objects
from functions import print_slow, await_input
from story.effects import MemoryFlash


class Ch01_Memory_Amelia(MemoryFlash):
    """
    The first memory flash - triggered after defeating the first Rock Rumbler.
    Jean's mind drifts to a moment with Amelia, hinting at loss and love.
    """
    def __init__(self, player, tile, params=None, repeat=False, name='Ch01_Memory_Amelia'):
        # Define the memory fragments with timing
        memory_lines = [
            ("The smell of old parchment and candle wax.", 2),
            ("", 1),  # Blank line for pacing
            ("A woman's voice, soft and warm, reading aloud by firelight.", 2.5),
            ("", 1),
            ('"Jean, you always were too stubborn for your own good."', 2),
            ("", 0.5),
            ("Laughter— her laughter— like wind chimes in a summer breeze.", 2.5),
            ("", 1),
            ("A hand reaching out, fingers intertwining with his own.", 2),
            ("The weight of a gold ring, cool against his skin.", 2),
            ("", 1),
            ('"Promise me it\'ll be fine. Promise me."', 2),
            ('"You worry too much, dear."', 2.5),
            ("", 1.5),
            ("A tender kiss...", 2),
            ("A warm smile...", 1.5),
            ("", 1),
            ("...but some...", 1.5),
            ("...some promises...", 1.5),
            ("...promises...", 2),
        ]
        
        # Jean's reaction after the memory
        aftermath = [
            "Jean gasps, stumbling backward. His chest feels tight,",
            "his breath coming in short, sharp bursts.",
            "",
            "Who was that? Regina? The name echoes in his mind,",
            "familiar yet distant, like a half-remembered dream.",
            "",
            "He shakes his head, trying to clear the fog.",
            "There's no time to dwell on these strange visions.",
            "Not here. Not now.",
        ]
        
        super().__init__(
            player=player,
            tile=tile,
            memory_lines=memory_lines,
            aftermath_text=aftermath,
            repeat=repeat,
            name=name
        )


class Ch01StartOpenWall(Event):
    """
    The first event. Opens the wall in the starting room when the player 'presses' the wall depression
    """

    def __init__(self, player, tile, params=None, repeat=True, name='Ch01_Start_Open_Wall'):
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
        for room_object in self.tile.objects_here:
            if isinstance(room_object, objects.TileDescription):
                room_object.description = """
Now that an exit in the east wall has been revealed, the room has been filled with warmth and light. A bright
blue sky is visible through the hole in the rock. The faint sound of birds chirping and water flowing can be
heard. """
                break
        for room_object in self.tile.objects_here:
            if room_object == wall_switch:
                self.tile.objects_here.remove(room_object)
                break
        time.sleep(0.5)


class Ch01BridgeWall(Event):
    """
    Opens the wall on the bridge in the starting area
    """

    def __init__(self, player, tile, params=None, repeat=True, name='Ch01_Bridge_Wall'):
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
            if isinstance(room_object, objects.TileDescription):
                self.tile.objects_here.remove(room_object)
                break
        for room_object in self.tile.objects_here:
            if room_object == wall_switch:
                self.tile.objects_here.remove(room_object)
                break
        time.sleep(0.5)


class Ch01ChestRumblerBattle(Event):
    """
    Initiates the battle with rock rumblers when the chest at (7,1) is looted
    """

    def __init__(self, player, tile, params=None, repeat=True, name='Ch01_Chest_Rumbler_Battle'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)
        self.triggered = False  # Track if we've already started the narrative

    def check_conditions(self):
        # Only check if we haven't triggered yet
        if self.triggered:
            return
            
        for thing in self.tile.objects_here:
            if hasattr(thing, "name"):
                if thing.name == "Wooden Chest":
                    if len(thing.inventory) == 0:  # if the chest is empty, continue
                        self.triggered = True  # Mark as triggered before processing
                        self.pass_conditions_to_process()
                        break

    def process(self, user_input=None):
        if user_input is None:
            cprint(
                "Apparently, there is also a rusty iron mace in the chest. "
                "Jean takes it and swings it around gently, testing its balance.")
            import items
            mace = items.RustedIronMace()
            self.player.inventory.append(mace)
            self.player.equip_item(mace.name)
            cprint("Suddenly, Jean hears a loud rumbling noise and the sound of scraping rocks.", 'yellow')
            
            # Signal to the API that we need a narrative pause
            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = "What's that noise!?"
            self.description = "Jean hears a loud rumbling noise and the sound of scraping rocks."
            self.input_options = [{"value": "continue", "label": "Continue"}]
            return

        # Second part of the trigger after user acknowledgment
        cprint("A rock-like creature appears and advances toward Jean!")
        self.tile.spawn_npc("RockRumbler")
        time.sleep(0.5)
        self.player.combat_events.append(Ch01PostRumbler(player=self.player, tile=self.tile, params=False,
                                                         repeat=False))
        self.completed = True
        self.needs_input = False
        if self in self.tile.events_here:
            self.tile.events_here.remove(self)


class Ch01PostRumbler(Event):  # Occurs when Jean beats the first rumbler after opening the chest
    def __init__(self, player, tile, params=None, repeat=False, name='Ch01_PostRumbler'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params, combat_effect=True)

    def check_combat_conditions(self):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        # Track which stage we're in using a stage attribute
        if not hasattr(self, '_stage'):
            self._stage = 1
            
        if self._stage == 1:
            # Stage 1: Trigger the memory flash
            memory = Ch01_Memory_Amelia(player=self.player, tile=self.tile)
            memory.process()
            
            # Sync state from memory to this event to pause processing
            self.needs_input = True
            self.input_type = getattr(memory, "input_type", "choice")
            self.input_prompt = getattr(memory, "input_prompt", "The memory fades...")
            self.input_options = getattr(memory, "input_options", [{"value": "continue", "label": "Continue"}])
            self.description = getattr(memory, "description", "")
            self._stage = 2
            return

        elif self._stage == 2:
            # Stage 2: Spawn enemies and show announcement dialog
            # Ensure we use the current tile instance to avoid stale refs
            target_tile = self.tile
            if hasattr(self.player, 'current_room'):
                target_tile = self.player.current_room

            # Spawn new enemies
            new_enemies = []
            for x in range(0, 2):
                npc = target_tile.spawn_npc("RockRumbler")
                new_enemies.append(npc)
            
            cprint("\nLow rumbles vibrate through the stone floor as more creatures emerge!", "yellow")
                
            # Add them to combat and reinitialize positions for all combatants
            from functions import add_enemies_to_combat
            add_enemies_to_combat(self.player, new_enemies)
                
            # Set up event dialog to announce the new enemies
            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = "The ground quivers slightly as more rock creatures appear!"
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self.description = f"{len(new_enemies)} Rock Rumblers emerge from the shadows!"
            
            # Add follow-up events
            self.player.combat_events.append(Ch01PostRumblerRep(player=self.player, tile=target_tile, params=False,
                                                                repeat=True))
            self.player.combat_events.append(Ch01PostRumbler2(player=self.player, tile=target_tile, params=False,
                                                              repeat=False))
            
            self._stage = 3
            return
            
        elif self._stage == 3:
            # Stage 3: User acknowledged the announcement, complete the event
            self.completed = True
            self.needs_input = False
            
            # Clean up this event manually since staged events might persist in lists
            if self in self.player.combat_events:
                 self.player.combat_events.remove(self)


class Ch01PostRumblerRep(Event):
    def __init__(self, player, tile, params=None, repeat=True,
                 name='Ch01_PostRumbler_Rep'):  # This event is to continue repeating until the player's health is low
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params, combat_effect=True)
        self.iteration = 2

    def check_combat_conditions(self):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        # Track which stage we're in using a stage attribute
        if not hasattr(self, '_announcement_stage'):
            self._announcement_stage = 1
            
        if self._announcement_stage == 1:
            # Stage 1: Spawn enemies and show announcement dialog
            # Ensure we use the current tile instance to avoid stale refs
            target_tile = self.tile
            if hasattr(self.player, 'current_room'):
                target_tile = self.player.current_room

            # Spawn new enemies
            new_enemies = []
            for x in range(0, self.iteration):
                npc = target_tile.spawn_npc("RockRumbler")
                new_enemies.append(npc)
            
            # Add them to combat and reinitialize positions
            from functions import add_enemies_to_combat
            add_enemies_to_combat(self.player, new_enemies, f"The ground shudders violently as {len(new_enemies)} more rock creatures rise!")
            
            # Set up event dialog to announce the new enemies
            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = f"The ground quivers as {len(new_enemies)} more rock creatures emerge!"
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self.description = f"{len(new_enemies)} additional Rock Rumblers join the fray!"
            
            self.iteration += 1
            self._announcement_stage = 2
            return
            
        elif self._announcement_stage == 2:
            # Stage 2: User acknowledged the announcement, reset for next trigger
            self.needs_input = False
            self._announcement_stage = 1  # Reset for next time this repeating event triggers
    

class Ch01PostRumbler2(Event):
    def __init__(self, player, tile, params=None, repeat=False, name='Ch01_PostRumbler2'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params, combat_effect=True)

    def check_combat_conditions(self):
        if self.player.get_hp_pcnt() < 0.3:
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        # Ensure we use the current tile instance to avoid stale refs
        target_tile = self.tile
        if hasattr(self.player, 'current_room'):
            target_tile = self.player.current_room

        for event in list(self.player.combat_events):
            if event.name == 'Ch01_PostRumbler_Rep':
                self.player.combat_events.remove(event)  # Remove the repeating event
        
        cprint(
            "\nSuddenly, a loud 'crack' thunders through the chamber. A nearby wall splits open and a massive figure "
            "leaps out, smashing its huge fist down on top of one of the rock creatures.", "yellow")
        
        if self.player.combat_list:
            enemy = self.player.combat_list[0]
            enemy.hp = 0  # instagib one of the rock creatures
            print(colored(enemy.name, "magenta") + " exploded into fragments of light!")
            if enemy in target_tile.npcs_here:
                target_tile.npcs_here.remove(enemy)
            if enemy in self.player.combat_list:
                self.player.combat_list.remove(enemy)
            self.player.refresh_enemy_list_and_prox()

        cprint("The massive figure somewhat resembles a man, except he is covered head-to-toe in armor not much "
               "different from the chamber walls. There is a star-shaped patch of moss on its left shoulder.", "cyan")
        cprint("Two more rock creatures advance on him, snapping their heavy jaws.", "cyan")
        cprint("Without saying a word, he hands a strange vial to Jean and gesticulates with large, clumsy hands, "
               "then turns to face the creatures. A loud rumble billows out from the figure, vibrating Jean's chest.", "cyan")
        cprint("\nSensing the urgency of his situation, Jean quaffs the strange liquid.", "yellow")
        cprint("It burns in his throat, but he can feel strength quickly returning to his limbs.", "cyan")
        cprint("Jean would like to thank the strange rock-man, but he's not out of danger just yet.", "cyan")
        
        if len(self.player.combat_list) == 0:
            npc = target_tile.spawn_npc("RockRumbler")
            npc.combat_engage(self.player)
            
        self.player.hp = self.player.maxhp
        self.player.fatigue = self.player.maxfatigue
        self.player.heat += 0.75
        self.player.combat_events.append(Ch01PostRumbler3(player=self.player, tile=self.tile, params=False,
                                                          repeat=False))


class Ch01PostRumbler3(Event):
    def __init__(self, player, tile, params=None, repeat=False, name='Ch01_PostRumbler3'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params, combat_effect=True)
        self.needs_input = True
        self.input_type = "choice"
        self.input_prompt = "Which should Jean choose?"
        self.description = "Jean would like to thank the strange rock-man, but he's not out of danger just yet."
        self.input_options = [
            {"value": "a", "label": "I'm not some filthy coward! (Help rock-man)"},
            {"value": "b", "label": "It can't be helped. I must survive! (Make a break for it)"},
            {"value": "c", "label": "I need more time to think! (Consider alternatives)"}
        ]

    def check_combat_conditions(self):
        # This event is added manually, so it runs when it's the player's turn or start of beat
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        if not user_input:
            cprint("\nWiping sweat from his brow, Jean looks up to see the rock-man surrounded by the beasts, "
                   "\nswinging wildly with a large stone column it had picked up from the floor."
                   "\nWhile he wouldn't feel right abandoning the rock-man to an ill fate, now"
                   "\nis the perfect time to make a break for the hole that was opened in the"
                   "\nchamber wall. There isn't enough time to consider alternatives.")
            return

        self.needs_input = False
        self.completed = True

        choice_input = user_input.lower()
        
        #  a is the correct choice, so evaluate that last
        if choice_input == "b" or choice_input == "c":
            if choice_input == "b":
                cprint("Jean swallows hard and begins sprinting toward the hole in the chamber wall.")
            elif choice_input == "c":
                cprint("Unsure of what to do, Jean stands frozen, glancing between the rock-man and his"
                       "\navenue of escape.")
            time.sleep(1)
            cprint("Rock-man manages to smash one of the beasts beneath his large column-turned-bludgeon,"
                   "\nhowever one of the other beasts jumps on his back at that moment, knocking him "
                   "\nquickly to the ground. The other beasts pile on and begin slashing and biting"
                   "\nmercilessly.")
            time.sleep(1)
            cprint("Just before Jean can make his escape, a beast jumps and slides between Jean and"
                   "\nhis salvation, kicking up loose dirt and pebbles. Jean quickly dodges to the side"
                   "\nand tries to circle back to the entrance from which he came."
                   "\nJumping around the snapping jaws and swinging tails of the other beasts,"
                   "\nHe manages to make it back to the long bridge connecting the two spires.")
            time.sleep(1)
            cprint("He can hear the beasts behind him, but they seemed to have stopped at"
                   "\nthe threshold separating the chamber entrance and the outside,"
                   "\nas if they are afraid of the daylight.")
            time.sleep(1)
            cprint("Jean straightens up and begins to catch his breath. Just as he breathes"
                   "\na sigh of relief, a piercing screech rings through his ears,"
                   "\na great cold wind blows over him, and two sharp claws dig"
                   "\nruthlessly into his shoulders, picking him up off of the"
                   "\nbridge.")
            time.sleep(1)
            cprint("He looks up at the horrible monster that grabbed him and"
                   "\nis terrified at the ugly abomination. Rows upon rows"
                   "\nof jagged teeth, three sunken black eyes staring"
                   "\nhungrily at him, a froth of saliva spilling out of"
                   "\nits disgusting maw.")
            time.sleep(1)
            cprint("Jean gasps and gropes uselessly at the sharp claws"
                   "\nstill digging painfully into his flesh. He swings"
                   "\nhis mace and lands a blow on the twisted, scaly"
                   "\nleg of the abominable demon.")
            time.sleep(1)
            cprint("The monster lets out a loud screech, and swooping"
                   "\nquickly, smashes Jean's body against the wall of rock.")
            cprint("Jean suffers " + str(random.randint(30, 90)) + " damage!", "red")
            cprint("Jean screams in pain, his mace arm swinging uselessly by"
                   "\nhis side, broken.")
            cprint("Again, the monster smashes Jean against the wall,"
                   "\nrepeatedly and without hesitation or mercy,"
                   "\nbears it slams him hard into the ground.")
            cprint("Jean suffers " + str(random.randint(30, 90)) + " damage!", "red")
            cprint("Jean suffers " + str(random.randint(10, 60)) + " damage!", "red")
            cprint("Jean suffers " + str(random.randint(30, 90)) + " damage!", "red")
            cprint("Jean suffers " + str(random.randint(85, 155)) + " damage!", "red")
            self.player.hp = 0
            #  deth
        else:
            cprint("Jean grits his teeth, then begins running toward one of the beasts"
                   "\nsurrounding the rock man. He shouts loudly, and plants his mace"
                   "\nsquarely between the ferocious snapper's eyes. The beast explodes"
                   "\ninto brilliant fragments of light.")
            time.sleep(1)
            cprint("The other creatures turn toward Jean in alarm. Rock-man takes this"
                   "\nopportunity to smash one of them into the wall with a great swing"
                   "\nfrom his large column.")
            time.sleep(1)
            cprint("Rock-man glances over at Jean and with another gesticulation,"
                   "\nnods his head in respect. Both prepare themselves for the "
                   "\ndifficult fight that remains.")
            time.sleep(1)

            gorran = self.tile.spawn_npc("Gorran", delay=0)
            self.player.combat_list_allies.append(gorran)
            gorran.in_combat = True
            gorran.reset_combat_moves()

            for x in range(0, 5):
                rumbler = self.tile.spawn_npc("RockRumbler", delay=random.randint(0, 5))
                rumbler.combat_engage(self.player)

            self.tile.events_here.append(AfterTheRumblerFight(self.player, self.tile, None))


class AfterTheRumblerFight(Event):
    """
    After the fight, Gorran tells Jean that they will talk, but not here. Too dangerous. Gorran then waits for Jean to
    speak to him again.
    """

    def __init__(self, player, tile, params=None, repeat=False, name='AfterTheRumblerFight'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        if not self.player.in_combat:
            self.pass_conditions_to_process()

    def process(self):
        time.sleep(5)
        print("The Rock-Man lowers his club to the ground and turns toward Jean.")
        time.sleep(3)
        dialogue("Jean", "I suppose I should thank you for saving my skin. What is your name?", "cyan")
        print("The Rock-Man stands immobile for a long moment, then slowly gestures toward himself. "
              "He begins to speak in low, rumbling tones, little of which Jean can understand.")
        time.sleep(3)
        print("Seeming to sense Jean's incomprehension, the Rock-Man places his open palm on his chest before emitting what could " \
        "best be described as an avalanche falling in love with an earthquake.")
        time.sleep(4)
        dialogue("Rock-Man", "Mmmmm... Go-rra-nnnnnn...", "green")
        dialogue("Jean", "Go... rran? Well, thank you, Gorran. But what were those things? "
                         "I've never seen their like in my life!", "cyan")
        print("Gorran lets out a deep, low rumble, then gestures toward the wall from which he apparently came.")
        time.sleep(3)
        print("Gorran points at himself, then at Jean, and finally gestures toward the recently opened passage.")
        print("He makes a series of rumbling sounds and waves his hands, clearly inviting Jean to approach him again.")
        print("It seems Gorran wants to communicate further, but words are not his way. Perhaps Jean should try speaking to him once more.")

        for npc_here in self.tile.npcs_here:
            if npc_here.name == "Rock-Man":
                npc_here.name = "Gorran"
                if npc_here in self.player.combat_list_allies:
                    self.player.combat_list_allies.remove(npc_here)


class AfterGorranIntro(Event):
    """
    When Jean talks to Gorran again, Gorran leads Jean through an
    opening in the rock to the Verdette Caverns, heading for Grondia.
    """

    def __init__(self, player, tile, params=None, repeat=False, name='AfterGorranIntro'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        self.pass_conditions_to_process()

    def process(self):
        time.sleep(1)
        print("Gorran gestures toward the opening in the wall. The two walk over. Jean can see that the opening is "
              "much too small for him to\npass through. Gorran waves an arm toward it and, miraculously, "
              "the opening widens with a loud rumble. Gorran walks through and\n"
              "Jean, with trepidation, follows.")
        await_input()
        for gorran in self.tile.npcs_here:
            if gorran.name == "Gorran":
                self.player.combat_list_allies.append(gorran)
                gorran.friend = True
                # Reset moves if joining mid-combat
                if self.player.in_combat:
                    gorran.reset_combat_moves()
        self.player.teleport("verdette-caverns", (2, 1))
