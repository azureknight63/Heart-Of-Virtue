"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""
from termcolor import colored, cprint
import threading
import random

class Event: #master class for all events
    '''
    Events are added to tiles much like NPCs and items. These are evaluated each game loop to see if the conditions
    of the event are met. If so, execute the 'process' function, else pass.
    Set repeat to True to automatically repeat for each game loop; setting parallel to True opens a new thread

    '''
    def __init__(self, name, player, tile, repeat=False, parallel=False):
        self.name = name
        self.player = player
        self.tile = tile
        self.repeat = repeat
        self.parallel = parallel
        self.has_run = False

    def pass_conditions_to_process(self):
        if self.repeat:
            self.call_process()
        else:
            self.call_process()
            self.tile.events_here.remove(self)  # if this is a one-time event, kill it after it executes

    def call_process(self):  # allows switching between parallel and standard processing
        if self.parallel:
            threading._start_new_thread(self.process(), self)
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


class Gold_from_heaven(Event):  # Gives the player a random amount of gold... for testing? Or just fun.
    def __init__(self, player, tile, name='Gold From Heaven', repeat=False, parallel=False):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, parallel=parallel)

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        print("Oddly enough, a pouch of gold materializes in front of you.")
        self.tile.spawn_item('Gold', amt=77)