"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""
from termcolor import colored, cprint
import threading
import random
import time
import objects

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
    def __init__(self, player, tile, repeat, parallel, params, name='Block'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel, params=params)
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
                    cprint("A rock-like creature appears and advances toward Jean!")
                    time.sleep(0.5)
                    self.tile.spawn_npc("RockRumbler")
                    self.tile.spawn_event("Story", player=self.player, tile=self.tile, params="start_post_rumbler_battle") #TODO figure out a way to interrupt battles with events

            elif param == 'start_post_rumbler_battle':
                if not self.disable[param]:
                    cprint("The ground quivers slightly as another.", 'yellow')
                    self.disable[param] = True
                    cprint("A rock-like creature appears and advances toward Jean!")
                    time.sleep(0.5)
                    self.tile.spawn_npc("RockRumbler")

            else:
                temp = '!!!param error: params='
                for p in self.params:
                    temp += p
                    temp += ', '
                print(temp)