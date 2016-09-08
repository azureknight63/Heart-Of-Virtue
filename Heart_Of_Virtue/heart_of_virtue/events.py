"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""
from termcolor import colored, cprint
import threading
import random

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
    def __init__(self, name, player, tile, repeat=False, parallel=False, params=None):
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
        if self.parallel:
            self.thread = EventThread(self)
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
    def __init__(self, player, tile, name='Gold From Heaven', repeat=False, parallel=False):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel)

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        print("Oddly enough, a pouch of gold materializes in front of you.")
        self.tile.spawn_item('Gold', amt=77)


class Block(Event):  # blocks exit in tile, blocks all if none are declared
    def __init__(self, player, tile, name='Block', repeat=False, parallel=False, params=None):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel, params=params)
        if not params:
            self.directions = ['north', 'south', 'east', 'west']
        else:
            self.directions = params
        print(tile, '@ [', tile.x, tile.y, '] blocking ', self.directions)  # todo left off here... not sure why east isn't being blocked on tile 3,2

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
#     def __init__(self, player, tile, name='Unblock', params=None, repeat=False, parallel=False):
#         super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel)
#         self.directions = params
#         if self.directions == None:
#             self.directions = ['north', 'south', 'east', 'west']
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