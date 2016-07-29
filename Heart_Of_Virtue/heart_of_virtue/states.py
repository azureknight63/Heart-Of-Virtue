"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""
from termcolor import colored, cprint
import random

class State: #master class for all states
    '''
    If beats_max is 0 (default), the state will not expire after n beats.

    '''
    def __init__(self, name, target,
                 source=None, apply_announce="", description="", beats_max=0, steps_max=0, combat=True, world=False):
        self.name = name
        self.description = description  # todo finish this
        self.beats_max = beats_max  # combat beats
        self.beats_left = self.beats_max
        self.steps_max = steps_max  # world steps
        self.steps_left = self.steps_max
        self.apply_announce = apply_announce

        self.target = target  # can be the same as the user in abilities with no targets
        self.source = source
        self.combat = combat
        self.world = world

    def effect(self, target):
        """
        to be overwritten by a state - this is the effect that occurs on a beat in combat or a step in the world
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def process(self, target):
        if self.combat and target.in_combat:
            self.effect(target)
            if self.beats_max != 0:
                self.beats_left -= 1
                if self.beats_left == 0:
                    target.states.remove(self)
        elif self.world and not target.in_combat:
            self.effect(target)
            if self.steps_max != 0:
                self.steps_left -= 1
                if self.steps_left == 0:
                    target.states.remove(self)