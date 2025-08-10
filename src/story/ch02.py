"""
Chapter 02 events
"""
from src.events import *
import time
from src import items


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
        if not self.player.skip_dialog:
            print("Gorran looks at Jean, his eyes wide with excitement. He gestures for Jean to follow him.\n"
                  "Not wanting to disappoint his new friend, Jean follows him through the passageway.\n\n")
            time.sleep(0.5)
            # Describe the surroundings as they walk. Include descriptions of the Arcology through which they pass.
            # There will be several Grondites milling about with their daily concerns.
            # Gorran can only communicate in grunts and gestures, so Jean must rely on his own observations.
            print("The passageway opens into a large cavern, the walls of which are covered in strange, glowing \n"
                  "symbols. The air is thick with the smell of damp earth and moss. \n"
                  "Gorran leads Jean through the cavern, "
                  "pointing out various features of the Grondite settlement as they go.")
            time.sleep(2)
            print("From the ceiling at various intervals hang clusters of red crystals, casting a steady glow on the \n"
                  "streets below. Gorran stops in front of a large, stone archway. \n"
                  "The archway is covered in the same glowing symbols as the walls of the cavern. \n"
                  "Gorran gestures for Jean to follow him through the archway.")
            functions.await_input()
            print("As Jean steps through the archway, he is struck by the sheer size of the cavern beyond. \n"
                  "The ceiling is so high that it is lost in darkness, \nand the walls are so far away that "
                  "they seem to be a part of the very rock itself. "
                  "The floor is covered in a thick layer of moss, \nand the air is filled with the sound of dripping water "
                  "and the heavy bustle of the city's stony inhabitants.")
            time.sleep(2)
            print("After walking at length, Gorran stops in front of a large, stone building. ")
            print("The Citadel rises before them, an immense structure carved directly from the cavern's living stone. \n"
                  "Its walls are etched with intricate, ancient depictions of Grondia's history. \n"
                  "Massive pillars support the vaulted entrance, and the air hums with a quiet energy. \n"
                  "Jean feels a sense of both wonder and trepidation as he gazes up at the fortress, \n"
                  "realizing that this place has stood for countless generations, \n"
                  "guarding secrets as old as the earth itself.")
            functions.await_input()
            print("Gorran turns to Jean, his expression serious. He gestures towards the Citadel, \n"
                  "indicating that this is where they must go next. \n"
                  "Jean nods, understanding that this is a place of great importance to the Grondites, \n"
                  "and perhaps to his own journey as well.")
            time.sleep(4)
            print("Gorran leads Jean into the Citadel, where they are greeted by a group of Grondites. \n"
                  "They are dressed in simple, yet sturdy clothing, and they regard Jean with curiosity. \n"
                  "Gorran addresses the Grondites in their peculiar language of grunts and groans, \n"
                  "apparently explaining that he is a friend and ally - or, at the very least, not an enemy.")
            time.sleep(4)
            print("The Grondites nod in understanding, and one of them steps forward to address Jean. \n"
                  "He speaks in a deep, rumbling voice, gesturing towards the interior of the Citadel. \n"
                  "Gorran nods his great head and sets off into the depths of the Citadel, \n"
                  "motioning for Jean to follow. ")
            functions.await_input()
            print("As they walk through the Citadel, Jean is struck by the sheer scale of the place. \n"
                  "The halls are vast and echo with the sound of their footsteps. "
                  "The walls are adorned with intricate carvings and murals, \ndepicting scenes from Grondia's history "
                  "much like the ones on the walls outside. \n"
                  "Jean feels a sense of awe and reverence for this place, realizing that it is a testament to the \n"
                  "Grondites' strength and resilience.")
            time.sleep(4)
            print("Gorran leads Jean to a large chamber at the heart of the Citadel where a group of Grondite elders \n"
                  "are gathered. They are seated on stone thrones, their faces lined with age and wisdom. \n"
                  "Gorran speaks to them in their language, and they regard Jean with a mixture of curiosity and respect. \n"
                  "One of the elders stands and approaches Jean. Much to Jean's surprise, the elder extends a \n"
                  "burly, unyielding hand in greeting. Taking it, Jean has the sensation of grasping a \n"
                  "piece of the mountain itself. The elder's grip is firm, but not painful, \n"
                  "and Jean feels a sense of connection to this ancient being.")
            functions.await_input()
            print("Even more astonishingly, the elder speaks in a deep, rumbling voice, which Jean is able to understand.")
            time.sleep(1)
            dialogue("Elder", "You are a friend of Gorran. You are welcome here.", "green")
            time.sleep(1)
            print("Jean nods, grateful for the warm welcome. He can feel the weight of the elder's gaze upon him, \n"
                  "and he knows that he is in the presence of someone who has seen much in their long life. \n"
                  "The elder gestures for Jean to sit on a nearby stool, also made from stone. Jean does so, \n"
                  "feeling awkward and out of place on the hard, cold seat.")
            time.sleep(5)
            print("Gorran comes over and stands beside Jean, his massive frame casting a shadow over the elder.\n"
                  "The elder looks up at Gorran and speaks in a low, rumbling voice. \n"
                  "Gorran rumbles briefly in reply, then turns and strides out of the chamber.\n"
                  "The elder turns back to Jean, his expression serious.")
            time.sleep(5)
            print("Now having gotten a chance to look at the elder, Jean can see that he is a bit smaller in form \n"
                  "than Gorran, though still quite large by human standards. Rather than the craggy, harsh exterior \n"
                  "of other Golemites, this elder has a smooth, almost polished appearance. It's clear that many \n"
                  "years of erosion have worn away the rough edges of his form, much like stones in a riverbed. \n"
                  "His eyes are deep-set and wise, and they seem to hold a depth of knowledge that speaks of \n"
                  "centuries of experience. He opens his mouth to speak.")
            functions.await_input()
            dialogue("Elder", "Welcome, little one. I am Elder Votha Krr. Among the inhabitants "
                  "of this great city, I am among its council of leaders. "
                  "Some may even foolishly look to me for guidance from time to time.", "green")
            time.sleep(2)
            print("With that, a rolling rumble of laughter erupts from the elder's mouth like the aftershocks of an "
                  "earthquake. ")
            time.sleep(2)
            dialogue("Votha Krr", "Ah, but let's not waste time talking about me. Tell me who you are and, "
                  "especially, why you are here. Or, perhaps more especially, where you are going.",
                     "green")
            time.sleep(2)
            print("Jean pauses for a long moment, unsure of how to answer. If he's honest with himself, he doesn't \n"
                  "really know how to answer any of those questions. He furrows his brow, troubled by this sudden \n"
                  "consternation. He takes a deep breath, trying to gather his thoughts.")
            time.sleep(3)
            dialogue("Jean", "I am Jean. Jean... Claire. I'm on a journey - I think. But I'm "
                    "not sure where I'm going or why. I just know that I need to keep moving forward, "
                    "to find something... or someone.", "cyan")
            time.sleep(2)
            print("Elder Votha Krr nods slowly, his expression thoughtful.")
            time.sleep(1)
            dialogue("Votha Krr", "In that case, perhaps you can help us with something while you "
                     "work out your own path. I hope that is not too forward of me to ask. We are, you see, "
                     "in dire need of assistance. Our people rely on the sustenance provided by the unique "
                     "mineral formations found in the sacred Grondelith Mineral Pools to the southwest.", "green")
            time.sleep(2)
            print("Votha Krr's expression darkens, and he continues.")
            time.sleep(1)
            dialogue("Votha Krr", "However, the pools have become infested by a colony of slimes. "
                     "These slimes are not only consuming the minerals, but are also corrupting the pools themselves, "
                     "rendering them toxic to our people. We have tried to eradicate the slimes ourselves, "
                     "but unfortunately, the corruption infects our kind like a disease, and so it is much "
                     "too dangerous for me to send my people to deal with them. I have been worrying about "
                     "this for some time now, and I fear that if we do not act soon, the pools will be lost to us "
                     "and our people will begin to starve.", "green")
            time.sleep(2)
            dialogue("Jean", "And you think me, being a creature of flesh, would not be affected by "
                             "the corruption? ","cyan")
            time.sleep(1)
            dialogue("Votha Krr", "Ah, well, your kind is not immune to the corruption, "
                     "but it does not affect you in the same way it does us. You see, our bodies are made of "
                     "the very minerals that the slimes consume, and so we are much more vulnerable to their "
                     "corruption. However, your flesh is not stone and mineral, so while you may be "
                     "harmed if you are not careful, you would not turn to dust and crumble "
                     "as we surely would.", "green")
            dialogue("Jean", "Wait, \"my kind?\" There are others here like me?", "cyan")
            dialogue("Votha Krr", "Oh yes, indeed! We have traded, formed treaties, and even in times of war, "
                    "allied with fleshlings like yourself. I believe you call yourselves... ahhhh... humans.",
                     "green")
            time.sleep(1)
            print("The last word rumbled from Votha like a landslide, reverberating into Jean's chest. ")
            time.sleep(1)
            dialogue("Jean", "Alright, I'll help you if I can. I'm not sure what else to do, anyway.",
                     "cyan")
            time.sleep(1)
            dialogue("Votha Krr", "Thank you, Jean. I will be forever grateful for your assistance. "
                     "The Grondelith Mineral Pools are located to the southwest of here. Take these supplies; I "
                     "think you will find them useful.", "green")
            time.sleep(1)
        print("Votha Krr waves a hand, and a Grondite attendant steps forward, carrying a small bundle of supplies. ")
        # Add 5 Antidotes and 2 Restoratives to the player's inventory
        print("The attendant hands the bundle to Jean, who takes it gratefully.")
        loot = [
            items.Antidote(5),
            items.Restorative(2)
        ]
        self.player.add_items_to_inventory(loot)
        functions.await_input()

        if not self.player.skip_dialog:
            print("With that, Votha Krr slowly got to his feet, his massive form towering over Jean. \n")
            dialogue("Votha Krr", "May the earth guide your steps, Jean. "
                     "You are a guest of our city. You may find the merchants of the Eastern Gate "
                     "to be of great help. As for me, I must return to my duties. "
                     "Return to me when you have dealt with the slimes, and perhaps we can discover "
                     "the trajectory of your future."
                     "green")



        # At the end of the sequence, don't forget to teleport to the Citadel tile.


        #  Remove this event from the tile
        self.tile.remove_event(self.name)
