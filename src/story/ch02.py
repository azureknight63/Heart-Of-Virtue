"""
Chapter 02 events
"""
from src.events import *
import time


class AfterDefeatingLurker(Event):
    """
    Jean defeats the Lurker. Gorram opens another passageway
    """
    def __init__(self, player, tile, params=None, repeat=False, name='AfterGorranIntro'):
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
              "he strides over to the far wall. Sliding two hands into a small crack in the wall, "
              "he braces himself.\n\n"
              "With a low rumble, he begins spreading the wall apart, gradually revealing a passage not unlike the "
              "last that he opened in the same manner.")
        time.sleep(2)
        print("Gorran turns back around to face Jean.")
        dialogue("Gorran", "Gr-rrondia-a-a... this way...", "green")
        functions.await_input()
        self.tile.spawn_object("Passageway", self.player, self.tile, params="t.grondia 1 3")
        print("Gorran ducked low, disappearing beneath a curving shelf of grey rock. Looking closely, "
              "Jean could see a conspicuous divot along the bottom of the shelf, near where his mighty "
              "friend's massive head had passed just moments ago. Scratches covered the divot, marking "
              "this route as one frequently traveled by the strange rock-like man or perhaps his companions, "
              "if he has any.")
        time.sleep(4)
        print("Immediately on passing under the shelf, Jean's greying whiskers were blasted by a cool "
              "breeze of unknown origin. It had the dank smell of the cavern to which Jean was just "
              "starting to grow accustomed, but also, something more. Or, rather, a lot of things more. "
              "There was a mixture of scents; some familiar, and some entirely alien. "
              "The moist wetness told of a fresh water source nearby. The dust betrayed the movement "
              "of something large, or perhaps many things. There was also - yes, Jean was sure of "
              "it - the smells of leather and iron.")
        functions.await_input()
        self.player.teleport("grondia 3 1")
