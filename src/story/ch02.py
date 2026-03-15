"""
Chapter 02 events
"""
from src.events import Event, dialogue
from src.functions import print_slow, await_input
import time
from src import items
from src.story.effects import MemoryFlash


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
        print("Gorran turns back around to face Jean and rumbles in what has to be something like relief mixed with fatigue.")
        await_input()
        # Spawn a passageway to Grondia at coordinates (1, 3)
        self.tile.spawn_object("Passageway", self.player, self.tile, 
                              teleport_map="grondia", teleport_tile=(1, 3))
        print("Gorran ducked low, disappearing beneath a curving shelf of grey rock. Looking closely, "
              "Jean could see a conspicuous divot along the bottom of the shelf, near where his mighty "
              "friend's massive head had passed just moments ago. Scratches covered the divot, marking "
              "this route as one frequently traveled by the strange rock-like man or perhaps his companions, "
              "if he has any.")
        time.sleep(4)
        print("Immediately on passing under the shelf, Jean's greying whiskers were blasted by a cool "
              "breeze. He turned his head slightly, reading the flow — east to west, coming up from somewhere "
              "deeper in. It had the dank smell of the cavern to which Jean was just "
              "starting to grow accustomed, but also, something more. Or, rather, a lot of things more. "
              "There was a mixture of scents; some familiar, and some entirely alien. "
              "The moist wetness told of a fresh water source nearby. The dust betrayed the movement "
              "of something large, or perhaps many things. There was also - yes, Jean was sure of "
              "it - the smells of leather and iron.")
        await_input()
        self.player.teleport("grondia", (3,1))


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
            await_input()
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
            await_input()
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
            await_input()
            print("As they walk through the Citadel, Jean is struck by the sheer scale of the place. \n"
                  "The halls are vast and echo with the sound of their footsteps. "
                  "The walls are adorned with intricate carvings and murals, \ndepicting scenes from Grondia's history "
                  "much like the ones on the walls outside. \n"
                  "Jean's first thought is not of the carvings. It is of the air — steady, slow-moving, \n"
                  "cool at his feet and perceptibly warmer at his shoulders. Convection, working the way \n"
                  "it's supposed to, on a scale he has never encountered. He wants to find where it rises. \n"
                  "Then Gorran makes a sound and Jean remembers to look at the walls.")
            time.sleep(4)
            print("Gorran leads Jean to a large chamber at the heart of the Citadel where a group of Grondite elders \n"
                  "are gathered. They are seated on stone thrones, their faces lined with age and wisdom. \n"
                  "Gorran speaks to them in their language, and they regard Jean with a mixture of curiosity and respect. \n"
                  "One of the elders stands and approaches Jean. Much to Jean's surprise, the elder extends a \n"
                  "burly, unyielding hand in greeting. Taking it, Jean has the sensation of grasping a \n"
                  "piece of the mountain itself. The elder's grip is firm, but not painful, \n"
                  "and Jean feels a sense of connection to this ancient being.")
            await_input()
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
            await_input()
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
            dialogue("Jean", "I am Jean. Jean Claire.", "cyan")
            time.sleep(1)
            print("He stops there. Votha Krr waits, unhurried as erosion.")
            time.sleep(2)
            dialogue("Jean", "As for the rest — I can fight. I'm good with my hands. "
                    "I can figure out what's broken and fix it. "
                    "That's... that's what I do.", "cyan")
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
            print("Jean is quiet for a moment. Something is broken and someone needs it fixed.")
            time.sleep(1)
            dialogue("Jean", "Alright. I'll take a look at it.", "cyan")
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
        await_input()

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


class AfterDefeatingKingSlime(Event):
    """
    Fires once KingSlime is absent from the arena tile.
    Cleanses the pool description, spawns MineralFragment, then triggers the
    memory flash when Jean picks it up. Gorran teleports to the arena afterward.
    """
    def __init__(self, player, tile, params=None, repeat=False, name='AfterDefeatingKingSlime'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        king_still_alive = any(
            n.__class__.__name__ == "KingSlime"
            for n in self.tile.npcs_here
        )
        if not king_still_alive:
            self.pass_conditions_to_process()

    def process(self):
        time.sleep(1)
        print_slow(
            "The churning stills. A deep, resonant silence settles over the cavern.",
            delay=0.04
        )
        time.sleep(1)
        print_slow(
            "Then — gradually — the green recedes. Ripple by ripple, the corruption dissolves "
            "outward from the center, the thick slime thinning and clearing until clean, "
            "luminescent blue water fills the chamber.",
            delay=0.03
        )
        time.sleep(1.5)
        print_slow(
            "The central stone island is exactly what it always was. "
            "The light here is steady and quiet, blue-white, older than the corruption that hid it.",
            delay=0.03
        )
        time.sleep(1)
        print_slow(
            "On the island, something catches the light. "
            "Impossibly sharp. Impossibly beautiful.",
            delay=0.04
        )
        time.sleep(0.5)

        # Update the arena tile description to reflect the cleansed state
        self.tile.spawn_object(
            "TileDescription", self.player, self.tile,
            description=(
                "The circular cavern is still. The pool that filled it — wall to wall with "
                "pulsating corruption — is gone. Clean, luminescent blue water rests in its place, "
                "glowing faintly from below. The single stone island at the centre is bare and quiet. "
                "The arena smells of minerals and cold water."
            )
        )

        # Spawn the MineralFragment on this tile
        self.tile.spawn_item("MineralFragment")

        # Set the story flag so AfterKingSlimeReturn can fire later
        self.player.universe.story["king_slime_defeated"] = "1"

        # Teleport Gorran from the atrium (2,1) to the arena (2,6)
        current_map = self.player.universe.current_map
        atrium_coords = (2, 1)
        if atrium_coords in current_map.tiles:
            atrium_tile = current_map.tiles[atrium_coords]
            for npc in list(atrium_tile.npcs_here):
                if npc.__class__.__name__ == "Gorran":
                    atrium_tile.npcs_here.remove(npc)
                    npc.tile = self.tile
                    self.tile.npcs_here.append(npc)
                    break

        self.tile.remove_event(self.name)


class Ch02KingSlimeMemoryFlash(MemoryFlash):
    """
    Memory flash triggered when Jean picks up the MineralFragment after
    defeating King Slime. The razor edge cuts Jean's finger; the sharp pain
    unlocks a violent, fragmented memory of the explosion.
    Called from the MineralFragment item's on_pickup hook via the story system.
    """
    def __init__(self, player, tile, params=None, repeat=False, name='Ch02KingSlimeMemoryFlash'):
        memory_lines = [
            ("The edge catches Jean's finger.", 1.5),
            ("", 0.5),
            ("Pain — sudden, immediate, real.", 1.5),
            ("", 0.5),
            ("Then —", 1.0),
            ("", 0.3),
            ("BOOM.", 2.0),
            ("", 0.5),
            ("A sound that is not a sound. A pressure that moves through bone.", 2.0),
            ("", 0.5),
            ("Screams. Human screams, many of them, very close.", 2.0),
            ("A blinding flash of white — then nothing.", 1.5),
            ("Then swirling debris. Dust and fire and cold air rushing in.", 2.0),
            ("", 0.5),
            ("Being thrown. The sensation of the ground disappearing.", 1.5),
            ("", 0.5),
            ("And where something warm should have been, in Jean's arms —", 2.0),
            ("emptiness.", 3.0),
        ]
        aftermath = [
            "Silence.",
            "",
            "Jean is standing on the stone island. The water around it is blue.",
            "The fragment is in their hand, still sharp, still bright.",
            "",
            "The bleeding finger is real. Everything else is gone.",
        ]
        super().__init__(
            player=player,
            tile=tile,
            memory_lines=memory_lines,
            aftermath_text=aftermath,
            repeat=repeat,
            name=name
        )

    def check_conditions(self):
        # This event is triggered manually from MineralFragment pickup — never fires on its own
        pass


class AfterKingSlimeReturn(Event):
    """
    Fires once when Jean re-enters any Grondia tile after king_slime_defeated is set.
    Votha Krr eats the mineral fragment and sends Jean toward the Echoing Caves.
    """
    def __init__(self, player, tile, params=None, repeat=False, name='AfterKingSlimeReturn'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        story = getattr(self.player.universe, 'story', {})
        if story.get("king_slime_defeated") == "1" and not story.get("votha_krr_response_given"):
            self.pass_conditions_to_process()

    def process(self):
        # Check if Jean actually has the MineralFragment
        has_fragment = any(
            i.__class__.__name__ == "MineralFragment"
            for i in self.player.inventory
        )
        if not has_fragment:
            return

        time.sleep(1)
        print_slow(
            "Votha Krr rises from his throne as Jean enters. His deep-set eyes take in the "
            "bleeding finger, the fragment in Jean's hand, and Jean's expression — all at once.",
            delay=0.03
        )
        time.sleep(1.5)

        dialogue("Votha Krr",
                 "The pools are clean, little one. You have done well.",
                 "green")
        time.sleep(0.5)

        print_slow(
            "Before Jean can respond, the Elder leans forward and, with a deliberate precision "
            "that borders on ceremony, plucks the mineral fragment from Jean's hand. "
            "He regards it for a single moment — then places it in his mouth.",
            delay=0.03
        )
        time.sleep(1)
        print_slow(
            "A soft, contented rumble escapes him. The fragment is gone.",
            delay=0.04
        )

        # Remove the MineralFragment from inventory
        for item in list(self.player.inventory):
            if item.__class__.__name__ == "MineralFragment":
                self.player.inventory.remove(item)
                break

        time.sleep(1.5)
        dialogue("Votha Krr",
                 "The corruption is gone. But I sense... a great disturbance within you. "
                 "A sorrow that is not of this stone. "
                 "The world outside these stones holds many shards. "
                 "Some bring strength, some bring pain. "
                 "Sometimes, the deepest truths are found in the broken places.",
                 "green")
        time.sleep(1)
        dialogue("Votha Krr",
                 "To mend what is broken, one must first understand the cracks. "
                 "Go now. Seek the Echoing Caves to the west, beyond the river. "
                 "There, the earth sings the songs of lost things. "
                 "Perhaps you will find a different kind of strength there... "
                 "or, at the very least, a clearer path.",
                 "green")
        time.sleep(0.5)
        await_input()

        self.player.universe.story["votha_krr_response_given"] = "1"
        self.tile.remove_event(self.name)
