"""
Chapter 02 events
"""

from src.events import Event, dialogue
from src.functions import print_slow, await_input
from neotermcolor import colored
import time
from src import items
from src.story.effects import MemoryFlash


class AfterDefeatingLurker(Event):
    """
    Jean defeats the Lurker. Gorram opens another passageway
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="AfterGorranIntro"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        conditions_pass = True
        for npc in self.tile.npcs_here:
            if (
                npc.__class__.__name__ == "Lurker"
            ):  # If there's a Lurker here, the event cannot fire
                conditions_pass = False
        if conditions_pass:
            self.pass_conditions_to_process()

    def process(self):
        # Beta end: story continuation to Grondia is disabled for beta testing.
        # The player can continue exploring Verdette Caverns freely.
        pass


class Ch02GuideToCitadel(
    Event
):  # When first in Grondia, Gorran guides Jean to the Citadel
    def __init__(self, player, tile, params, repeat=False, name="Ch02_GuideToCitadel"):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_combat_conditions(self):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            print(
                "Gorran turns. His great head swings toward the passage that leads into the city.\n"
                "He makes a sound — short, low, the kind that doesn't require translation — and moves.\n"
                "Not wanting to disappoint his new friend, Jean follows him through the passageway.\n\n"
            )
            time.sleep(0.5)
            # Describe the surroundings as they walk. Include descriptions of the Arcology through which they pass.
            # There will be several Grondites milling about with their daily concerns.
            # Gorran can only communicate in grunts and gestures, so Jean must rely on his own observations.
            print(
                "The passageway opens into a large cavern, the walls of which are covered in strange, glowing \n"
                "symbols. The air is thick with the smell of damp earth and moss. \n"
                "Gorran leads Jean through the cavern, "
                "pointing out various features of the Grondite settlement as they go."
            )
            time.sleep(2)
            print(
                "From the ceiling at various intervals hang clusters of red crystals, casting a steady glow on the \n"
                "streets below. Gorran stops in front of a large, stone archway. \n"
                "The archway is covered in the same glowing symbols as the walls of the cavern. \n"
                "Gorran gestures for Jean to follow him through the archway."
            )
            await_input()
            print(
                "As Jean steps through the archway, he is struck by the sheer size of the cavern beyond. \n"
                "The ceiling is so high that it is lost in darkness, \nand the walls are so far away that "
                "they seem to be a part of the very rock itself. "
                "The floor is covered in a thick layer of moss, \nand the air is filled with the sound of dripping water "
                "and the heavy bustle of the city's stony inhabitants."
            )
            time.sleep(2)
            print(
                "After walking at length, Gorran stops in front of a large, stone building. "
            )
            print(
                "The Citadel rises before them, an immense structure carved directly from the cavern's living stone. \n"
                "Its walls are etched with intricate, ancient depictions of Grondia's history. \n"
                "Massive pillars support the vaulted entrance, and the air hums with a quiet energy. \n"
                "Jean feels a sense of both wonder and trepidation as he gazes up at the fortress, \n"
                "realizing that this place has stood for countless generations, \n"
                "guarding secrets as old as the earth itself."
            )
            await_input()
            print(
                "Gorran turns to Jean, his expression serious. He gestures towards the Citadel, \n"
                "indicating that this is where they must go next. \n"
                "Jean nods, understanding that this is a place of great importance to the Grondites, \n"
                "and perhaps to his own journey as well."
            )
            time.sleep(4)
            print(
                "Gorran leads Jean into the Citadel, where they are greeted by a group of Grondites. \n"
                "They are dressed in simple, yet sturdy clothing, and they regard Jean with curiosity. \n"
                "Gorran addresses the Grondites in their peculiar language of grunts and groans, \n"
                "apparently explaining that he is a friend and ally - or, at the very least, not an enemy."
            )
            time.sleep(4)
            print(
                "The Grondites nod in understanding, and one of them steps forward to address Jean. \n"
                "He speaks in a deep, rumbling voice, gesturing towards the interior of the Citadel. \n"
                "Gorran nods his great head and sets off into the depths of the Citadel, \n"
                "motioning for Jean to follow. "
            )
            await_input()
            print(
                "As they walk through the Citadel, Jean is struck by the sheer scale of the place. \n"
                "The halls are vast and echo with the sound of their footsteps. "
                "The walls are adorned with intricate carvings and murals, \ndepicting scenes from Grondia's history "
                "much like the ones on the walls outside. \n"
                "Jean's first thought is not of the carvings. It is of the air — steady, slow-moving, \n"
                "cool at his feet and perceptibly warmer at his shoulders. Convection, working the way \n"
                "it's supposed to, on a scale he has never encountered. He wants to find where it rises. \n"
                "Then Gorran makes a sound and Jean remembers to look at the walls."
            )
            time.sleep(4)
            print(
                "Gorran leads Jean to a large chamber at the heart of the Citadel where a group of Grondite elders \n"
                "are gathered. They are seated on stone thrones, their faces lined with age and wisdom. \n"
                "Gorran speaks to them in their language, and they regard Jean with a mixture of curiosity and respect. \n"
                "One of the elders stands and approaches Jean. Much to Jean's surprise, the elder extends a \n"
                "burly, unyielding hand in greeting. Taking it, Jean has the sensation of grasping a \n"
                "piece of the mountain itself. The elder's grip is firm, but not painful, \n"
                "and Jean feels a sense of connection to this ancient being."
            )
            await_input()
            print(
                "Even more astonishingly, the elder speaks in a deep, rumbling voice, which Jean is able to understand."
            )
            time.sleep(1)
            dialogue(
                "Elder",
                "You are a friend of Gorran. You are welcome here.",
                "green",
            )
            time.sleep(1)
            print(
                "Jean nods, grateful for the warm welcome. He can feel the weight of the elder's gaze upon him, \n"
                "and he knows that he is in the presence of someone who has seen much in their long life. \n"
                "The elder gestures for Jean to sit on a nearby stool, also made from stone. Jean does so, \n"
                "feeling awkward and out of place on the hard, cold seat."
            )
            time.sleep(5)
            print(
                "Gorran comes over and stands beside Jean, his massive frame casting a shadow over the elder.\n"
                "The elder looks up at Gorran and speaks in a low, rumbling voice. \n"
                "Gorran rumbles briefly in reply, then turns and strides out of the chamber.\n"
                "The elder turns back to Jean, his expression serious."
            )
            time.sleep(5)
            print(
                "Now having gotten a chance to look at the elder, Jean can see that he is a bit smaller in form \n"
                "than Gorran, though still quite large by human standards. Rather than the craggy, harsh exterior \n"
                "of other Golemites, this elder has a smooth, almost polished appearance. It's clear that many \n"
                "years of erosion have worn away the rough edges of his form, much like stones in a riverbed. \n"
                "His eyes are deep-set and wise, and they seem to hold a depth of knowledge that speaks of \n"
                "centuries of experience. He opens his mouth to speak."
            )
            await_input()
            dialogue(
                "Elder",
                "Welcome, little one. I am Elder Votha Krr. Within this city, I serve "
                "on its council of leaders — though some among us are more foolish than "
                "others in how much weight they give that title.",
                "green",
            )
            time.sleep(2)
            print(
                "With that, a rolling rumble of laughter erupts from the elder's mouth like the aftershocks of an "
                "earthquake. "
            )
            time.sleep(2)
            dialogue(
                "Votha Krr",
                "Ah, but let's not waste time talking about me. Tell me who you are and, "
                "especially, why you are here. Or, perhaps more especially, where you are going.",
                "green",
            )
            time.sleep(2)
            print(
                "Jean pauses for a long moment, unsure of how to answer. If he's honest with himself, he doesn't \n"
                "really know how to answer any of those questions. He furrows his brow, troubled by this sudden \n"
                "consternation. He takes a deep breath, trying to gather his thoughts."
            )
            time.sleep(3)
            dialogue("Jean", "I am Jean. Jean Claire.", "cyan")
            time.sleep(1)
            print("He stops there. Votha Krr waits, unhurried as erosion.")
            time.sleep(2)
            dialogue(
                "Jean",
                "As for the rest — I can fight. I'm good with my hands. "
                "I can figure out what's broken and fix it. "
                "That's... that's what I do.",
                "cyan",
            )
            time.sleep(2)
            print(
                "Votha Krr does not nod. He regards Jean with those deep-set eyes — "
                "patient, unhurried, the way a canyon regards a river."
            )
            time.sleep(3)
            dialogue(
                "Votha Krr",
                "You know who you are in your hands. That is not a small thing. "
                "Many who arrive in this world know far less.",
                "green",
            )
            time.sleep(1)
            print("He tilts his great head, just slightly.")
            time.sleep(1)
            dialogue(
                "Votha Krr",
                "But I notice you did not answer where you are going.",
                "green",
            )
            time.sleep(2)
            print("Jean opens his mouth. Closes it. The chamber is very quiet.")
            time.sleep(2)
            dialogue("Jean", "No. I didn't.", "cyan")
            time.sleep(2)
            print(
                "Something passes across Votha Krr's expression — not pity, not recognition. "
                "Something older than both."
            )
            time.sleep(2)
            dialogue(
                "Votha Krr",
                "Then perhaps that is a question for the road.",
                "green",
            )
            time.sleep(2)
            print(
                "He settles back in his throne, the stone of him indistinguishable from the stone beneath him."
            )
            time.sleep(1)
            dialogue(
                "Votha Krr",
                "Since you are a man who knows what to do with his hands — "
                "and since you find yourself without a direction — allow me to offer you one. "
                "Our sacred Grondelith Mineral Pools to the southwest have been infested by slimes. "
                "They consume the minerals our people depend on, and their corruption is lethal to our kind. "
                "We cannot clear them ourselves.",
                "green",
            )
            time.sleep(1.5)
            print("He watches Jean's face. Jean isn't showing much.")
            time.sleep(1)
            print(colored("[a]", "magenta") + ' "Tell me more."')
            print(colored("[b]", "magenta") + ' "I\'ll take a look at it."')
            _quest_choice = ""
            while _quest_choice not in ["a", "b"]:
                _quest_choice = input("Choice: ").strip().lower()

            if _quest_choice == "a":
                time.sleep(1)
                print("Votha Krr's expression darkens, and he continues.")
                time.sleep(1)
                dialogue(
                    "Votha Krr",
                    "The pools have become infested by a colony of slimes. "
                    "These slimes are not only consuming the minerals, but are also corrupting the pools "
                    "themselves, rendering them toxic to our people. We have tried to eradicate the slimes "
                    "ourselves, but the corruption infects our kind like a disease — it is much too "
                    "dangerous for me to send my people. I fear that if we do not act soon, the pools "
                    "will be lost to us and our people will begin to starve.",
                    "green",
                )
                time.sleep(2)
                dialogue(
                    "Jean",
                    "And you think me, being a creature of flesh, would not be affected by "
                    "the corruption?",
                    "cyan",
                )
                time.sleep(1)
                dialogue(
                    "Votha Krr",
                    "Ah, well, your kind is not immune to the corruption, "
                    "but it does not affect you in the same way it does us. You see, our bodies are made of "
                    "the very minerals that the slimes consume, and so we are much more vulnerable to their "
                    "corruption. However, your flesh is not stone and mineral, so while you may be "
                    "harmed if you are not careful, you would not turn to dust and crumble "
                    "as we surely would.",
                    "green",
                )
                dialogue(
                    "Jean",
                    'Wait, "my kind?" There are others here like me?',
                    "cyan",
                )
                dialogue(
                    "Votha Krr",
                    "Oh yes, indeed! We have traded, formed treaties, and even in times of war, "
                    "allied with fleshlings like yourself. I believe you call yourselves... ahhhh... humans.",
                    "green",
                )
                time.sleep(1)
                print(
                    "The last word rumbled from Votha like a landslide, reverberating into Jean's chest."
                )
                time.sleep(2)
                print(
                    "Jean is quiet, but his mind is already moving — tracing the shape of the problem. "
                    "An infestation with a center. Corrupted channels. A source."
                )
                time.sleep(2)
                dialogue(
                    "Jean",
                    "Is it centralized? Or spread through the whole system?",
                    "cyan",
                )
                time.sleep(1)
                dialogue(
                    "Votha Krr",
                    "There is a heart to it. One great slime at the center of the corruption — "
                    "the others follow where it leads. Remove the heart, and the rest will dissipate.",
                    "green",
                )
                time.sleep(1)
                print(
                    "Jean nods slowly. He's had that kind of job before. Somewhere, in some life, he's gone "
                    "after the source and let the symptoms take care of themselves."
                )
                time.sleep(1)
                print("He doesn't ask himself why he's so sure of that.")
                time.sleep(2)
                dialogue("Jean", "Alright. I'll take a look at it.", "cyan")
                time.sleep(1)
                dialogue(
                    "Votha Krr",
                    "Thank you, Jean. The pools are to the southwest. "
                    "Take these supplies — the corruption will harm you if you are not careful.",
                    "green",
                )
                time.sleep(1)
            else:
                dialogue("Jean", "I'll take a look at it.", "cyan")
                time.sleep(1)
                dialogue(
                    "Votha Krr",
                    "Thank you, Jean. The pools are southwest of the city. "
                    "The corruption will not destroy your kind as it does ours, "
                    "but it will hurt you if you are careless. Take these supplies.",
                    "green",
                )
                time.sleep(1)
        if not self.player.skip_dialog:
            print(
                "Votha Krr waves a hand, and a Grondite attendant steps forward, carrying a small bundle of supplies. "
            )
            print("The attendant hands the bundle to Jean, who takes it gratefully.")
        # Add 5 Antidotes and 2 Restoratives to the player's inventory
        loot = [items.Antidote(5), items.Restorative(2)]
        self.player.add_items_to_inventory(loot)
        if not self.player.skip_dialog:
            await_input()

        if not self.player.skip_dialog:
            print(
                "With that, Votha Krr slowly got to his feet, his massive form towering over Jean.\n"
            )
            dialogue(
                "Votha Krr",
                "May the earth guide your steps, Jean. "
                "You are a guest of our city. The merchants of the Eastern Gate "
                "will have what you need for the road. "
                "Return to me when you have dealt with the slimes.",
                "green",
            )
            time.sleep(1)
            print(
                "He pauses. Those deep-set eyes hold Jean's for a moment longer than necessary."
            )
            time.sleep(1)
            dialogue(
                "Votha Krr",
                "And when you return — perhaps we will speak again "
                "of where you are going.",
                "green",
            )
            time.sleep(1)
            print(
                "He says it the same way he said it the first time. Like a door left open."
            )

        # At the end of the sequence, don't forget to teleport to the Citadel tile.

        #  Remove this event from the tile
        self.tile.remove_event(self.name)


class Ch02ArenaEntrance(Event):
    """
    Fires once when Jean first arrives at the King Slime arena — before combat
    begins. Narrates the isolation (Gorran couldn't follow), the shape of the
    corrupted pools, and the King Slime with something embedded inside it.

    Attach to the same arena tile as AfterDefeatingKingSlime.
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="Ch02ArenaEntrance"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(self.player.universe, "story", {})
        if story.get("arena_entered"):
            self.tile.remove_event(self.name)
            return
        king_slime_present = any(
            n.__class__.__name__ == "KingSlime" for n in self.tile.npcs_here
        )
        if king_slime_present:
            self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            print_slow(
                "The corridor narrows and the smell changes — thick with something sweet and wrong, "
                "like rot and copper together.",
                delay=0.03,
            )
            time.sleep(1)
            print_slow(
                "Jean came this way alone. The passageway behind him is empty. "
                "Gorran's footsteps stopped at the last junction — the air grew too heavy, "
                "the corruption too dense for stone to tolerate, and Gorran knew it "
                "before Jean did. He made one sound, low and short, and did not follow.",
                delay=0.03,
            )
            time.sleep(1.5)
            await_input()
            print_slow(
                "The arena opens before him. A circular cavern, pools filling it wall to wall — "
                "churning, pulsating green that moves with its own slow intention. "
                "The smell is overwhelming. The light casts no shadows.",
                delay=0.03,
            )
            time.sleep(1)
            print_slow(
                "At the far end, something large rises from the center of the pools. "
                "It has no face, no shape that lends itself to naming — only mass, and a slow "
                "purposeful movement. Within that mass, something that does not belong: "
                "a glint, sharp and pale, glimpsed through the churning surface. "
                "Consumed. Held. Not yet dissolved.",
                delay=0.03,
            )
            time.sleep(1.5)
            print_slow(
                "Jean has cleared drains before. Found the blockage. Removed what had lodged "
                "where it shouldn't be. This is the same job.",
                delay=0.04,
            )
            time.sleep(1)
            print_slow("He tells himself that.", delay=0.05)
            time.sleep(1)
            await_input()
        self.player.universe.story["arena_entered"] = "1"
        self.tile.remove_event(self.name)


class AfterDefeatingKingSlime(Event):
    """
    Fires once KingSlime is absent from the arena tile.
    Cleanses the pool description, spawns MineralFragment, then triggers the
    memory flash when Jean picks it up. Gorran teleports to the arena afterward.
    """

    def __init__(
        self,
        player,
        tile,
        params=None,
        repeat=False,
        name="AfterDefeatingKingSlime",
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        king_still_alive = any(
            n.__class__.__name__ == "KingSlime" for n in self.tile.npcs_here
        )
        if not king_still_alive:
            self.pass_conditions_to_process()

    def process(self):
        time.sleep(1)
        print_slow(
            "The churning stills. A deep, resonant silence settles over the cavern.",
            delay=0.04,
        )
        time.sleep(1)
        print_slow(
            "Then — gradually — the green recedes. Ripple by ripple, the corruption dissolves "
            "outward from the center, the thick slime thinning and clearing until clean, "
            "luminescent blue water fills the chamber.",
            delay=0.03,
        )
        time.sleep(1.5)
        print_slow(
            "The central stone island is exactly what it always was. "
            "The light here is steady and quiet, blue-white, older than the corruption that hid it.",
            delay=0.03,
        )
        time.sleep(1)
        print_slow(
            "On the island, something catches the light. "
            "Impossibly sharp. Impossibly beautiful.",
            delay=0.04,
        )
        time.sleep(1.5)
        print_slow(
            "Jean stands in the clearing water. It's cold — rising back toward its natural level, "
            "lapping at his boots. The fight is over. There is nothing left in the room that needs him.",
            delay=0.03,
        )
        time.sleep(1)
        print_slow(
            "He doesn't know what to do with his hands when they aren't needed.",
            delay=0.04,
        )
        time.sleep(2)

        # Update the arena tile description to reflect the cleansed state
        self.tile.spawn_object(
            "TileDescription",
            self.player,
            self.tile,
            description=(
                "The circular cavern is still. The pool that filled it — wall to wall with "
                "pulsating corruption — is gone. Clean, luminescent blue water rests in its place, "
                "glowing faintly from below. The single stone island at the centre is bare and quiet. "
                "The arena smells of minerals and cold water."
            ),
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

        # Narrate Gorran's arrival and his reaction to the cleansed pools
        time.sleep(1)
        print_slow(
            "Then — footsteps. Heavy, deliberate, from the corridor entrance.",
            delay=0.04,
        )
        time.sleep(0.5)
        print_slow("Gorran rounds the archway and stops.", delay=0.05)
        time.sleep(1)
        print_slow(
            "He looks at the pools. Clean, blue, still. His great head moves slowly across the chamber, "
            "taking in what it was and what it is now.",
            delay=0.03,
        )
        time.sleep(1.5)
        print_slow(
            "He makes no sound. He just stands there in the entrance to the arena, "
            "looking at the water the way someone looks at something they thought was gone.",
            delay=0.03,
        )
        time.sleep(1)
        print_slow(
            "Then, slowly, he walks to the edge of the nearest pool and lowers himself to one knee. "
            "He extends one wide hand over the surface. Doesn't touch it. Just holds his palm there, "
            "feeling the cold rise off it.",
            delay=0.03,
        )
        time.sleep(2)
        print_slow(
            "A sound from him — low and long, held in the chest. Not quite a word. "
            "He stays like that for a moment, hand over the water. Then he straightens.",
            delay=0.04,
        )
        time.sleep(1)

        #TODO: All of the map tiles referencing active corruption or "rumbling" (in reference to the now-defeated King Slime) need to get revised descriptions to match the present state of affairs.

        self.tile.remove_event(self.name)


class Ch02FragmentReminder(Event):
    """
    Fires via evaluate_for_map_entry() whenever the player has left the
    arena tile without picking up the MineralFragment.

    Gorran rumbles and gestures at the fragment; Jean is guided back.
    Repeats until the fragment is collected or Votha Krr has been visited.

    Attach to the arena tile alongside Ch02ArenaEntrance and
    AfterDefeatingKingSlime.
    """

    def __init__(
        self,
        player,
        tile,
        params=None,
        repeat=True,
        name="Ch02FragmentReminder",
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def evaluate_for_map_entry(self, player):
        story = getattr(player.universe, "story", {})

        # Done once Votha has received the fragment
        if story.get("votha_krr_response_given"):
            self.tile.remove_event(self.name)
            return

        # Only active after the King Slime is defeated
        if story.get("king_slime_defeated") != "1":
            return

        # If Jean already has the fragment, nothing to remind
        if any(i.__class__.__name__ == "MineralFragment" for i in player.inventory):
            return

        # If the fragment is gone from the tile too, nothing to do
        if not any(
            i.__class__.__name__ == "MineralFragment" for i in self.tile.items_here
        ):
            return

        # Only fire when Jean has LEFT the arena
        if player.current_room is self.tile:
            return

        # Rate-limit: at most once every 3 ticks so it doesn't spam corridors
        last_tick = int(story.get("fragment_reminder_tick", -999))
        if player.universe.game_tick - last_tick < 3:
            return

        story["fragment_reminder_tick"] = str(player.universe.game_tick)
        self._remind(player)

    def _remind(self, player):
        if not player.skip_dialog:
            print_slow("A rumble from behind — low, insistent.", delay=0.04)
            time.sleep(1)
            print_slow(
                "Gorran stands at the entrance to the corridor, one hand braced against the arch. "
                "He is looking at the island.",
                delay=0.03,
            )
            time.sleep(1)
            print_slow("Jean follows his gaze.", delay=0.05)
            time.sleep(1)
            print_slow(
                "The fragment is still there. He walked out without it.",
                delay=0.03,
            )
            time.sleep(1.5)

        # Teleport player back to the arena tile
        arena_coords = next(
            (
                coord
                for coord, t in player.map.items()
                if isinstance(coord, tuple) and t is self.tile
            ),
            None,
        )
        map_name = player.map.get("name", "grondia")
        if arena_coords:
            player.teleport(map_name, arena_coords)


class Ch02KingSlimeMemoryFlash(MemoryFlash):
    """
    Memory flash triggered when Jean picks up the MineralFragment after
    defeating King Slime. The razor edge cuts Jean's finger; the sharp pain
    unlocks a violent, fragmented memory of the explosion.
    Called from the MineralFragment item's on_pickup hook via the story system.
    """

    def __init__(
        self,
        player,
        tile,
        params=None,
        repeat=False,
        name="Ch02KingSlimeMemoryFlash",
    ):
        memory_lines = [
            ("The edge catches Jean's finger.", 1.5),
            ("", 0.5),
            ("Pain — sudden, immediate, real.", 1.5),
            ("", 0.5),
            ("Then —", 1.0),
            ("", 0.3),
            ("BOOM.", 2.0),
            ("", 0.5),
            (
                "A sound that is not a sound. A pressure that moves through bone.",
                2.0,
            ),
            ("", 0.5),
            ("Screams. Human screams, many of them, very close.", 2.0),
            ("A blinding flash of white — then nothing.", 1.5),
            (
                "Then swirling debris. Dust and fire and cold air rushing in.",
                2.0,
            ),
            ("", 0.5),
            ("Being thrown. The sensation of the ground disappearing.", 1.5),
            ("", 0.5),
            (
                "And where something warm should have been, in Jean's arms —",
                2.0,
            ),
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
            name=name,
        )

    def check_conditions(self):
        # This event is triggered manually from MineralFragment pickup — never fires on its own
        pass


class AfterKingSlimeReturn(Event):
    """
    Fires once when Jean re-enters any Grondia tile after king_slime_defeated is set.
    Votha Krr eats the mineral fragment and sends Jean toward the Echoing Caves.
    """

    def __init__(
        self,
        player,
        tile,
        params=None,
        repeat=False,
        name="AfterKingSlimeReturn",
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(self.player.universe, "story", {})
        if story.get("king_slime_defeated") == "1" and not story.get(
            "votha_krr_response_given"
        ):
            self.pass_conditions_to_process()

    def process(self):
        # Check if Jean actually has the MineralFragment
        has_fragment = any(
            i.__class__.__name__ == "MineralFragment" for i in self.player.inventory
        )
        if not has_fragment:
            return

        time.sleep(1)
        print_slow(
            "Votha Krr rises from his throne as Jean enters. His deep-set eyes take in the "
            "bleeding finger, the fragment in Jean's hand, and Jean's expression — all at once.",
            delay=0.03,
        )
        time.sleep(1.5)

        dialogue(
            "Votha Krr",
            "The pools are clean, little one. You have done well.",
            "green",
        )
        time.sleep(1)
        print_slow(
            "Jean still holds the mineral fragment. The cut on his finger has stopped bleeding "
            "but hasn't stopped hurting.",
            delay=0.03,
        )
        time.sleep(1)
        print(colored("[a]", "magenta") + " Hand it over.")
        print(colored("[b]", "magenta") + ' "What is this thing, exactly?"')
        print(
            colored("[c]", "magenta")
            + " [Set it on the edge of the throne without a word.]"
        )
        _frag_choice = ""
        while _frag_choice not in ["a", "b", "c"]:
            _frag_choice = input("Choice: ").strip().lower()
        if _frag_choice == "a":
            print_slow("Jean holds it out. Votha takes it from his hand.", delay=0.03)
        elif _frag_choice == "b":
            dialogue("Jean", "What is this thing, exactly?", "cyan")
            time.sleep(0.5)
            dialogue(
                "Votha Krr",
                "A memory, made stone. The mineral pools do not merely hold water — "
                "they record what passes through them. Light, creature, time. "
                "This fragment carries something very old. "
                "It is right that it returns to stone.",
                "green",
            )
            time.sleep(1)
            print_slow("He takes the fragment from Jean's hand.", delay=0.03)
        else:
            print_slow(
                "Jean sets the fragment on the armrest of the throne without looking at Votha. "
                "The Elder watches him do it. Waits. "
                "Then reaches out and picks it up, slowly, as though giving Jean time to reconsider.",
                delay=0.03,
            )
        time.sleep(1)
        print_slow(
            "Votha regards the fragment for a single moment — then places it in his mouth.",
            delay=0.03,
        )
        time.sleep(1)
        print_slow(
            "A soft, contented rumble escapes him. The fragment is gone.",
            delay=0.04,
        )

        # Remove the MineralFragment from inventory
        for item in list(self.player.inventory):
            if item.__class__.__name__ == "MineralFragment":
                self.player.inventory.remove(item)
                break

        time.sleep(1.5)
        dialogue(
            "Votha Krr",
            "The pools are clean. You have done what we could not do alone, little one.",
            "green",
        )
        time.sleep(1)
        print_slow(
            "He studies Jean's face. Then — the bleeding finger. "
            "He regards it for a moment without comment.",
            delay=0.03,
        )
        time.sleep(1.5)
        dialogue(
            "Votha Krr",
            "You came back.",
            "green",
        )
        time.sleep(1)
        print_slow(
            "He says it simply. As an observation, not a compliment.", delay=0.03
        )
        time.sleep(1.5)
        dialogue(
            "Votha Krr",
            "To mend what is broken, one must first understand the cracks. "
            "Go now. Seek the Echoing Caves to the west, beyond the river. "
            "There, the earth sings the songs of lost things. "
            "Perhaps you will find a different kind of strength there — "
            "or, at the very least, a clearer path.",
            "green",
        )
        time.sleep(1)
        print_slow(
            "He does not elaborate. When Jean opens his mouth, Votha Krr's only answer "
            "is to press two fingers briefly to his own chest — over the place a human "
            "would call the heart — and then withdraw.",
            delay=0.03,
        )
        time.sleep(1.5)
        time.sleep(0.5)
        await_input()

        self.player.universe.story["votha_krr_response_given"] = "1"
        self.tile.remove_event(self.name)
