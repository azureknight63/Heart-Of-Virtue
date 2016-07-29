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
                 source=None, apply_announce="", description="", beats_max=0):
        self.name = name
        self.description = description  # todo finish this
        self.beats_max = beats_max
        self.beats_left = self.beats_max
        self.apply_announce = apply_announce

        self.target = target  # can be the same as the user in abilities with no targets
        self.source = source


    def process_stage(self, user):
        if user.current_move == self:
            if self.current_stage == 0:
                self.prep(user)
            elif self.current_stage == 1:
                self.execute(user)
            elif self.current_stage == 2:
                self.recoil(user)
            elif self.current_stage == 3:
                self.cooldown(user)  # the cooldown stage will typically never be rewritten,
                # so this will usually just pass

    def cast(self, user): # this is what happens when the ability is first chosen by the player
        self.current_stage = 0 # initialize prep stage
        if self.stage_announce[1] != "":
            print(self.stage_announce[0])  # Print the prep announce message for the move
        self.beats_left = self.stage_beat[0]

    def advance(self, user):
        if user.current_move == self or self.current_stage == 3: # only advance the move if it's the player's
            # current move or if it's in cooldown
            if self.beats_left > 0:
                self.beats_left -= 1
            else:
                while self.beats_left == 0: # this loop will advance stages until the current stage has a beat count,
                    # effectively skipping unused stages
                    self.process_stage(user)
                    self.current_stage += 1  # switch to next stage
                    if self.current_stage == 3: # when the move enters cooldown, detach it from the player so he can
                        # do something else.
                        user.current_move = None
                        self.initialized = False
                    if self.current_stage > 3: # if the move is coming out of cooldown, switch back to the prep stage
                        # and break the while loop
                        self.current_stage = 0
                        self.beats_left = self.stage_beat[self.current_stage]
                        break
                    self.beats_left = self.stage_beat[self.current_stage] # set beats remaining for current stage

    def prep(self, user): #what happens during these stages. Each move will overwrite prep/execute/recoil/cooldown
        # depending on whether something is supposed to happen at that stage
        # print("######{}: I'm in the prep stage now".format(self.name)) #debug message
        pass

    def execute(self, user):
        # print("######{}: I'm in the execute stage now".format(self.name)) #debug message
        if self.beats_left == self.stage_beat[0] and self.stage_announce[1] != "":
            print(self.stage_announce[1])

    def recoil(self, user):
        # print("######{}: I'm in the recoil stage now".format(self.name)) #debug message
        if self.beats_left == self.stage_beat[0] and self.stage_announce[2] != "":
            print(self.stage_announce[2])

    def cooldown(self, user):
        # print("######{}: I'm in the cooldown stage now".format(self.name)) #debug message
        pass

