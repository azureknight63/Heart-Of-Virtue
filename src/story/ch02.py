"""
Chapter 02 events
"""
from src.events import *
import time


class AfterDefeatingLurker(Event):
    """
    Jean defeats the Lurker. Gorram opens another passageway
    """
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


class Ch02GuideToCitadel(Event):  # When first in Grondia, Gorran guides Jean to the Citadel
    def __init__(self, player, tile, params, repeat=False, name='Ch02_GuideToCitadel'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_combat_conditions(self):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self):
        print("Gorran looks at Jean, his eyes wide with excitement. He gestures for Jean to follow him."
              "Not wanting to disappoint his new friend, Jean follows him through the passageway.")
        time.sleep(0.5)
        # Describe the surroundings as they walk. Include descriptions of the Arcology through which they pass.
        # There will be several Grondites milling about with their daily concerns.
        # Gorran can only communicate in grunts and gestures, so Jean must rely on his own observations.
        print("The passageway opens into a large cavern, the walls of which are covered in strange, glowing "
              "symbols. The air is thick with the smell of damp earth and moss. Gorran leads Jean through the cavern, "
              "pointing out various features of the Grondite settlement as they go.")
        time.sleep(2)
        print("From the ceiling at various intervals hang clusters of red crystals, casting a steady glow on the"
              "streets below. Gorran stops in front of a large, stone archway. "
              "The archway is covered in the same glowing symbols "
              "as the walls of the cavern. Gorran gestures for Jean to follow him through the archway.")
        functions.await_input()
        print("As Jean steps through the archway, he is struck by the sheer size of the cavern beyond. "
              "The ceiling is so high that it is lost in darkness, and the walls are so far away that "
              "they seem to be a part of the very rock itself. "
              "The floor is covered in a thick layer of moss, and the air is filled with the sound of dripping water"
              "and the heavy bustle of the city's stony inhabitants.")
        time.sleep(2)
        print("After walking at length, Gorran stops in front of a large, stone building. ")
        print("The Citadel rises before them, an immense structure carved directly from the cavern's living stone. "
              "Its walls are etched with intricate, ancient depictions of Grondia's history. "
              "Massive pillars support the vaulted entrance, and the air hums with a quiet energy. "
              "Jean feels a sense of both wonder and trepidation as he gazes up at the fortress, "
              "realizing that this place has stood for countless generations, "
              "guarding secrets as old as the earth itself.")
        functions.await_input()
        print("Gorran turns to Jean, his expression serious. He gestures towards the Citadel, "
              "indicating that this is where they must go next. "
              "Jean nods, understanding that this is a place of great importance to the Grondites, "
              "and perhaps to his own journey as well.")
        time.sleep(2)
        print("Gorran leads Jean into the Citadel, where they are greeted by a group of Grondites. "
              "They are dressed in simple, yet sturdy clothing, and they regard Jean with curiosity. "
              "Gorran addresses the Grondites in their peculiar language of grunts and groans, "
              "apparently explaining that he is a friend and ally - or, at the very least, not an enemy.")
        time.sleep(2)
        print("The Grondites nod in understanding, and one of them steps forward to address Jean. "
              "He speaks in a deep, rumbling voice, gesturing towards the interior of the Citadel. "
              "Gorran nods his great head and sets off into the depths of the Citadel, "
              "motioning for Jean to follow. ")
        functions.await_input()
        print("As they walk through the Citadel, Jean is struck by the sheer scale of the place. "
              "The halls are vast and echo with the sound of their footsteps. "
              "The walls are adorned with intricate carvings and murals, depicting scenes from Grondia's history "
              "much like the ones on the walls outside. "
              "Jean feels a sense of awe and reverence for this place, realizing that it is a testament to the "
              "Grondites' strength and resilience.")
        time.sleep(2)
        print("Gorran leads Jean to a large chamber at the heart of the Citadel where a group of Grondite elders "
              "are gathered. They are seated on stone thrones, their faces lined with age and wisdom. "
              "Gorran speaks to them in their language, and they regard Jean with a mixture of curiosity and respect. "
              "One of the elders stands and approaches Jean. Much to Jean's surprise, the elder extends a "
              "burly, unyielding hand in greeting. Taking it, Jean has the sensation of grasping a "
              "piece of the mountain itself. The elder's grip is firm, but not painful, "
              "and Jean feels a sense of connection to this ancient being.")
        functions.await_input()
        print("Even more astonishingly, the elder speaks in a deep, rumbling voice, which Jean is able to understand.")
        time.sleep(1)
        dialogue("Elder", "You are a friend of Gorran. You are welcome here.", "green")
        time.sleep(1)
        print("Jean nods, grateful for the warm welcome. He can feel the weight of the elder's gaze upon him, "
              "and he knows that he is in the presence of someone who has seen much in their long life. "
              "The elder gestures for Jean to sit on a nearby stool, also made from stone. Jean does so, "
              "feeling awkward and out of place on the hard, cold seat.")
        time.sleep(2)
        print("Gorran comes over and stands beside Jean, his massive frame casting a shadow over the elder."
              "The elder looks up at Gorran and speaks in a low, rumbling voice. "
              "Gorran rumbles briefly in reply, then turns and strides out of the chamber."
              "The elder turns back to Jean, his expression serious.")
        time.sleep(2)


        #  Remove this event from the tile
        self.tile.remove_event(self.name)
