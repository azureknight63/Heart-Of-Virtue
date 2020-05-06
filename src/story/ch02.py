"""
Chapter 02 events
"""
from termcolor import colored, cprint
import threading
import random
import time, inspect
import objects, functions
from ..events import *


class AfterDefeatingLurker(Event):
    '''
    Jean defeats the Lurker. Gorram opens another passageway
    '''
    def __init__(self, player, tile, params, repeat=False, name='AfterGorranIntro'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        conditions_pass = True
        for npc in self.tile.npcs_here:
            if npc.__class__.__name__ == "Lurker":  # If there's a Lurker here, the event cannot fire
                conditions_pass = False
        if conditions_pass:
            self.pass_conditions_to_process()

    def process(self):
        time.sleep(2)
        print("Gorran breathes deeply and seems to collect himself for a moment. Then, with a glance at Jean, "
              "he strides over to the far wall. Sliding two hands into a small crack in the wall, he braces himself.\n\n"
              "With a low rumble, he begins spreading the wall apart, gradually revealing a passage not unlike the "
              "last that he opened in the same manner.")
        time.sleep(2)
        print("Gorran turns back around to face Jean.")
        self.dialogue("Gorran", "Gr-rrondia-a-a... this way...", "green")
        functions.await_input()
        #self.tile.spawn_object("Passageway", self.player, self.tile, params="t.mapname x-coord y-coord") #todo build Grondia first
