"""Debug mixin for Player — cheat commands and story-variable inspection."""

import traceback

from neotermcolor import cprint


class PlayerDebugMixin:
    """Debug and testing commands for the Player (not for production use)."""

    def supersaiyan(self):
        """Makes player super strong! Debug only."""
        self.strength_base = 1000
        self.strength = 1000
        self.finesse_base = 1000
        self.finesse = 1000
        self.speed_base = 1000
        self.speed = 1000
        self.maxhp_base = 10000
        self.maxhp = 10000
        self.hp = 10000
        self.maxfatigue_base = 10000
        self.maxfatigue = 10000
        self.fatigue = 10000

    def testevent(self, phrase=""):
        """Spawn a story event in the current tile."""
        params = phrase.split(" ")
        repeat = False
        if len(params) > 1:
            repeat = params[1]
        self.current_room.spawn_event(
            params[0], self, self.current_room, repeat=repeat, params=[]
        )  # will go fubar
        # if the name of the event is wrong or if other parameters are present in phrase

    def spawnobject(self, phrase=""):
        """
        Spawn an object (npc, item, room object, event) on the current tile.

        :param phrase: Pattern is "spawn obj_type obj params." Note the special instruction 'params=' refers to
        special params passed to room objects.
        :return: Nothing returned (action by player)
        """
        params = phrase.split(" ")
        obj_type = params[0].lower()
        obj = params[1].lower().title()
        if "_" in obj:
            obj = obj.replace("_", "")
        hidden = False
        hfactor = 0
        delay = -1
        count = 1
        repeat = False
        myparams = None
        if len(params) > 1:
            for item in params:
                if item == "hidden":
                    hidden = True
                elif "hfactor=" in item:
                    hfactor = int(item[8:])
                elif "delay=" in item:
                    delay = int(item[6:])
                elif "count=" in item:
                    count = int(item[6:])
                elif "repeat" in item:
                    repeat = True
                elif "params=" in item:
                    myparams = item[7:].split(",")

        try:
            for i in range(count):
                if obj_type == "npc":
                    self.current_room.spawn_npc(
                        obj, hidden=hidden, hfactor=hfactor, delay=delay
                    )
                elif obj_type == "item":
                    self.current_room.spawn_item(obj, hidden=hidden, hfactor=hfactor)
                elif obj_type == "event":
                    self.current_room.spawn_event(
                        obj,
                        self,
                        self.current_room,
                        repeat=repeat,
                        params=myparams,
                    )
                elif obj_type == "object":
                    self.current_room.spawn_object(
                        obj,
                        self,
                        self.current_room,
                        myparams,
                        hidden=hidden,
                        hfactor=0,
                    )
        except SyntaxError:
            cprint("Oops, something went wrong. \n\n" + traceback.format_exc())

    def print_story_vars(self):
        """Print all story variables (debug)."""
        print(self.universe.story)

    def alter(self, phrase=""):
        """Set a story variable by key/value pair (debug)."""
        params = phrase.split(" ")
        if len(params) < 2:
            print("### ERR IN SETTING VAR; BAD ARGUMENTS: " + phrase + " ###")
            return
        key, value = params[0], params[1]
        if key not in self.universe.story:
            print("### ERR IN SETTING VAR; NO ENTRY: " + key + " " + value + " ###")
            return
        self.universe.story[key] = value
        print("### SUCCESS: " + key + " changed to " + value + " ###")
