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

    '''
    def __init__(self, name, player, repeat=False, parallel=False):
        self.name = name
        self.player = player
        self.repeat = repeat
        self.parallel = parallel
        self.has_run = False

    def pass_conditions_to_process(self):
        if self.repeat:
            self.call_process()
        else:
            if not self.has_run:
                self.call_process()
                self.has_run = True

    def call_process(self):
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

#todo left off here; not sure auto is needed

class Auto(Event):  # Event subclass that automatically runs
    def __init__(self, name, player, repeat=False, parallel=False):  # Set repeat to True to automatically repeat
        # for each game loop; setting parallel to True opens a new thread
        super().__init__(name=name, player=player)
        self.repeat = repeat
        self.parallel = parallel
        self.has_run = False

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        """
        to be overwritten by an event subclass
        """
        pass

class Parrying(State):
    def __init__(self, target):  # parries the next attack, giving the aggressor a large recoil duration
        super().__init__(name="Parrying", target=target, beats_max=5,hidden=True)