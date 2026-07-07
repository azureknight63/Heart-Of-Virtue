"""
Chapter 02 events
"""

from src.events import Event
from src.functions import print_slow, await_input
import time
from src import items
from src.story.effects import MemoryFlash
from src.narration import (
    narrate,
    say,
    begin_conversation,
    end_conversation,
    enter_op,
    exit_op,
)

# Recurring conversation casts, to avoid retyping the same tuple at every stage.
_JEAN_SOLO = [("Jean", "left", "neutral")]
_JEAN_GORRAN_ALLY = [("Jean", "left", "neutral"), ("Gorran", None, "neutral")]
_JEAN_VOTHA_KRR = [("Jean", "left", "neutral"), ("Votha Krr", None, "neutral")]


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


class BetaTesterBriefing(Event):
    """
    One-shot briefing that fires the first time Jean enters Grondia (tile 1,2).
    Presents a story-so-far recap and beta tester instructions, including a
    prompt to use the Feedback button for credited feedback.
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="BetaTesterBriefing"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        self.pass_conditions_to_process()

    def process(self, user_input=None):
        if not hasattr(self, "_stage"):
            self._stage = 1

        if self._stage == 1:
            self.needs_input = True
            self.input_type = "choice"
            self.description = (
                "[ HEART OF VIRTUE — BETA ]\n\n"
                "Jean Claire woke in the dark with no memory of how he arrived. "
                "In the caves above Grondia he found Gorran — a Golemite, stone-skinned and quiet — "
                "who chose to fight beside him without explanation. "
                "Together they pressed deeper through the Verdette Caverns, following the drift of air, "
                "until Jean faced and defeated the Lurker: a creature of shadow and venom that kills from concealment. "
                "Now Gorran has led him here, to the threshold of Grondia — the living city of the Grondites, "
                "Gorran’s people — and whatever waits inside."
            )
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 2
            return

        elif self._stage == 2:
            self.needs_input = True
            self.input_type = "choice"
            self.description = (
                "── BETA TESTER NOTICE ──\n\n"
                "Welcome to the Grondia arc beta. Your task is to play through the sequence below and "
                "note anything that feels broken, inconsistent, or unclear:\n\n"
                "1. Explore Grondia and speak with its inhabitants.\n\n"
                "2. Reach the Grondelith Mineral Pools and defeat the King Slime.\n\n"
                "3. Return to the Citadel and speak with Votha Krr.\n\n"
                "4. Exit Grondia and head east to the river.\n\n"
                "5. Find Mara at the river camp and attempt to cross.\n\n"
                "Use the Feedback button (left panel) to record anything worth reporting.\n"
                "If you send feedback with your name or contact, you will be listed in the game credits.\n"
                "Anonymous feedback is still valuable — you just won’t be credited.\n\n"
                "Thank you for playing."
            )
            self.input_prompt = ""
            self.input_options = [{"value": "begin", "label": "Begin"}]
            self._stage = 3
            return

        elif self._stage == 3:
            self.needs_input = False
            self.completed = True
            if self.tile is not None and self in self.tile.events_here:
                self.tile.events_here.remove(self)


class Ch02GuideToCitadel(
    Event
):  # When first in Grondia, Gorran guides Jean to the Citadel
    def __init__(self, player, tile, params, repeat=False, name="Ch02_GuideToCitadel"):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        if not hasattr(self, "_stage"):
            self._stage = 1

        # Terminal mode is not supported for this staged event.
        # Terminal play is planned for deprecation; skip_dialog fast-path handles automation.
        if self.player.skip_dialog:
            loot = [items.Antidote(5), items.Restorative(2)]
            self.player.add_items_to_inventory(loot)
            self.player.teleport("grondia", (10, 5))
            self.needs_input = False
            self.completed = True
            self.tile.remove_event(self.name)
            return

        # Stage 1 — The approach: following Gorran through the settlement to the archway
        if self._stage == 1:
            self.needs_input = True
            self.input_type = "choice"
            self.description = (
                "Gorran turned. His great head swung toward the passage that led into the city. "
                "He made a sound — short, low, the kind that doesn't require translation — and moved. "
                "Not wanting to disappoint his new friend, Jean followed him through the passageway.\n\n"
                "The passageway opened into a large cavern, the walls of which were covered in strange, glowing "
                "symbols. The air was thick with the smell of damp earth and moss. "
                "Gorran led Jean through the cavern, pointing out various features of the Grondite settlement "
                "as they went.\n\n"
                "From the ceiling at various intervals hung clusters of red crystals, casting a steady glow on the "
                "streets below. Gorran stopped in front of a large stone archway, its surface etched with the same "
                "glowing symbols as the cavern walls. He gestured for Jean to follow."
            )
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 2
            return

        # Stage 2 — Through the archway and first sight of the Citadel
        if self._stage == 2:
            self.needs_input = True
            self.input_type = "choice"
            self.description = (
                "Jean stepped through. The cavern beyond was vast — the ceiling lost in darkness, "
                "the walls so far away they seemed part of the rock itself. "
                "The floor was covered in a thick layer of moss, and the air was filled with the sound of dripping "
                "water and the heavy bustle of the city's stony inhabitants.\n\n"
                "After walking at length, Gorran stopped in front of a large, stone building.\n\n"
                "The Citadel rose before them, an immense structure carved directly from the cavern's living stone. "
                "Its walls were etched with intricate, ancient depictions of Grondia's history. "
                "Massive pillars supported the vaulted entrance, and the air hummed with a quiet energy. "
                "Jean felt a sense of both wonder and trepidation as he gazed up at the fortress, "
                "realizing that this place had stood for countless generations, "
                "guarding secrets as old as the earth itself."
            )
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 3
            return

        # Stage 3 — Entering the Citadel: Grondites, the halls, convection
        if self._stage == 3:
            self.needs_input = True
            self.input_type = "choice"
            begin_conversation(_JEAN_GORRAN_ALLY)
            narrate(
                "Gorran turned to Jean, his expression serious. He gestured toward the Citadel, "
                "indicating that this was where they needed to go. Jean nodded, understanding "
                "this was a place of great importance to the Grondites, and perhaps to his own "
                "journey as well."
            )
            narrate(
                "Gorran led Jean into the Citadel, where they were greeted by a group of "
                "Grondites. They were dressed in simple, yet sturdy clothing, and they regarded "
                "Jean with curiosity. Gorran addressed the Grondites in their peculiar language "
                "of grunts and groans, apparently explaining that he was a friend and ally — or, "
                "at the very least, not an enemy."
            )
            narrate(
                "The Grondites nodded in understanding, and one of them stepped forward to "
                "address Jean. He spoke in a deep, rumbling voice, gesturing toward the interior "
                "of the Citadel. Gorran nodded his great head and set off into the depths of the "
                "Citadel, motioning for Jean to follow."
            )
            narrate(
                "As they walked through the Citadel, Jean was struck by the sheer scale of the "
                "place. The halls were vast and echoed with the sound of their footsteps. The "
                "walls were adorned with intricate carvings and murals, depicting scenes from "
                "Grondia's history much like the ones on the walls outside."
            )
            say(
                "Jean's first thought was not of the carvings. It was the air — steady, "
                "slow-moving, cool at his feet and perceptibly warmer at his shoulders. "
                "Convection, working the way it's supposed to, on a scale he had never "
                "encountered. He wanted to find where it rose.",
                "Jean",
                "neutral",
                thought=True,
            )
            narrate("Then Gorran made a sound and Jean remembered to look at the walls.")
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 4
            return

        # Stage 4 — The elders' chamber: handshake, first words, Gorran exits, Votha's introduction
        if self._stage == 4:
            self.needs_input = True
            self.input_type = "choice"
            begin_conversation(_JEAN_GORRAN_ALLY)
            narrate(
                "Gorran led Jean to a large chamber at the heart of the Citadel where a group of "
                "Grondite elders were gathered. They were seated on stone thrones, their faces "
                "lined with age and wisdom. Gorran spoke to them in their language, and they "
                "regarded Jean with a mixture of curiosity and respect."
            )
            narrate(
                "One of the elders stood and approached Jean. Much to Jean's surprise, the elder "
                "extended a burly, unyielding hand in greeting. Taking it, Jean had the sensation "
                "of grasping a piece of the mountain itself. The elder's grip was firm, but not "
                "painful, and Jean felt a sense of connection to this ancient being."
            )
            narrate(
                "Even more astonishingly, the elder spoke in a deep, rumbling voice, which Jean "
                "was able to understand."
            )
            # Speaker id is "Elder" (unnamed) until he introduces himself below —
            # matches the reveal already preserved in the legacy description text
            # ("Elder: ..." then "Votha Krr: ..."). The identity swaps to
            # "Votha Krr" on his self-introduction beat.
            say(
                "You are a friend of Gorran. You are welcome here.",
                "Elder",
                "neutral",
                enter=enter_op("Elder", side=None),
            )
            narrate(
                "Jean nodded, grateful for the warm welcome. He could feel the weight of the "
                "elder's gaze upon him, and he knew he was in the presence of someone who had "
                "seen much in their long life. The elder gestured for Jean to sit on a nearby "
                "stool, also made from stone. Jean did so, feeling awkward and out of place on "
                "the hard, cold seat."
            )
            narrate(
                "Gorran came over and stood beside Jean, his massive frame casting a shadow over "
                "the elder. The elder looked up at Gorran and spoke in a low, rumbling voice. "
                "Gorran rumbled briefly in reply, then turned and strode out of the chamber.",
                exit=[exit_op("Gorran", span=2)],
            )
            narrate("The elder turned back to Jean, his expression serious.")
            narrate(
                "Now having gotten a chance to look at the elder, Jean could see he was a bit "
                "smaller in form than Gorran, though still quite large by human standards. "
                "Rather than the craggy, harsh exterior of other Golemites, this elder had a "
                "smooth, almost polished appearance. Many years of erosion had worn away the "
                "rough edges of his form, much like stones in a riverbed. His eyes were deep-set "
                "and wise, and they seemed to hold a depth of knowledge that spoke of centuries "
                "of experience. He opened his mouth to speak."
            )
            say(
                "Welcome, little one. I am Elder Votha Krr. Within this city, I serve on its "
                "council of leaders — though some among us are more foolish than others in how "
                "much weight they give that title.",
                "Votha Krr",
                "neutral",
                enter=enter_op("Votha Krr", side=None, transition="instant"),
                leave=exit_op("Elder", transition="instant"),
            )
            narrate(
                "With that, a rolling rumble of laughter erupted from the elder's mouth like the "
                "aftershocks of an earthquake.",
                reactions={"Votha Krr": "happy"},
            )
            say(
                "Ah, but let's not waste time talking about me. Tell me who you are and, "
                "especially, why you are here. Or, perhaps more especially, where you are going.",
                "Votha Krr",
                "neutral",
            )
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 5
            return

        # Stage 5 — Jean introduces himself; Votha offers the quest
        if self._stage == 5:
            self.needs_input = True
            self.input_type = "choice"
            begin_conversation(_JEAN_VOTHA_KRR)
            narrate(
                "Jean paused. He wasn't sure how to answer — not any of those questions. He took "
                "a deep breath, trying to gather his thoughts."
            )
            say("I am Jean. Jean Claire.", "Jean", "neutral")
            narrate("He stopped there. Votha Krr waited, unhurried as erosion.")
            say(
                "As for the rest — I can fight. I'm good with my hands. I can figure out what's "
                "broken and fix it. That's... that's what I do.",
                "Jean",
                "neutral",
            )
            narrate(
                "Votha Krr did not nod. He regarded Jean with those deep-set eyes — patient, "
                "unhurried, the way a canyon regards a river."
            )
            say(
                "You know who you are in your hands. That is not a small thing. Many who arrive "
                "in this world know far less.",
                "Votha Krr",
                "neutral",
            )
            narrate("He tilted his great head, just slightly.")
            say("But I notice you did not answer where you are going.", "Votha Krr", "skeptical")
            narrate("Jean opened his mouth. Closed it. The chamber was very quiet.")
            say("No. I didn't.", "Jean", "neutral")
            narrate(
                "Something passed across Votha Krr's expression — not pity, not recognition. "
                "Something older than both."
            )
            say("Then perhaps that is a question for the road.", "Votha Krr", "neutral")
            narrate(
                "He settled back in his throne, the stone of him indistinguishable from the "
                "stone beneath him."
            )
            say(
                "Since you are a man who knows what to do with his hands — and since you find "
                "yourself without a direction — allow me to offer you one. Our sacred Grondelith "
                "Mineral Pools to the southwest have been infested by slimes. They consume the "
                "minerals our people depend on, and their corruption is lethal to our kind. We "
                "cannot clear them ourselves.",
                "Votha Krr",
                "neutral",
            )
            narrate("He watched Jean's face. Jean wasn't showing much.")
            self.input_prompt = ""
            self.input_options = [
                {"value": "a", "label": '"Tell me more."'},
                {"value": "b", "label": '"I\'ll take a look at it."'},
            ]
            self._stage = 6
            return

        # Stage 6 — Handle the quest choice; show the appropriate response
        if self._stage == 6:
            _choice = str(user_input or "a").strip().lower()
            _choice_map = {"0": "a", "1": "b"}
            _choice = _choice_map.get(_choice, _choice)
            if _choice not in ("a", "b"):
                _choice = "a"
            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]

            begin_conversation(_JEAN_VOTHA_KRR)
            if _choice == "a":
                narrate(
                    "Votha Krr was quiet a moment. When he spoke again, his voice was the same — "
                    "unhurried, without urgency, as if what he described had already been decided."
                )
                say(
                    "The Grondelith Pools to the southwest. Slimes have found them. They consume "
                    "the minerals our people require. The corruption is lethal to our kind — we "
                    "cannot clear them ourselves.",
                    "Votha Krr",
                    "neutral",
                )
                narrate("He watched Jean's face. Jean wasn't showing much.")
                say("It would not kill you the same way.", "Votha Krr", "neutral")
                say("Is it centralized? Or spread through the whole system?", "Jean", "neutral")
                say(
                    "There is a heart to it. One great slime at the center. Remove it, and the "
                    "rest will follow.",
                    "Votha Krr",
                    "neutral",
                )
                say("Wait — 'your kind.' There are others here like me?", "Jean", "surprised")
                say(
                    "We have known your kind before. Traded with them. Fought alongside them.",
                    "Votha Krr",
                    "neutral",
                )
                narrate("He paused, searching for the word with the patience of stone finding water.")
                say("Humans.", "Votha Krr", "neutral")
                narrate("The word rumbled from him like a landslide, reverberating into Jean's chest.")
                say(
                    "Jean was quiet, but his mind was already moving — tracing the shape of the "
                    "problem. An infestation with a center. Corrupted channels. A source. He'd had "
                    "that kind of job before. Somewhere, in some life. He didn't ask himself why "
                    "he was so sure of that.",
                    "Jean",
                    "neutral",
                    thought=True,
                )
                say("Alright. I'll take a look at it.", "Jean", "neutral")
                say(
                    "Thank you, Jean. The pools are to the southwest. Take these supplies — the "
                    "corruption will harm you if you are not careful.",
                    "Votha Krr",
                    "happy",
                )
            else:
                say("I'll take a look at it.", "Jean", "neutral")
                say(
                    "Thank you, Jean. The pools are southwest of the city. The corruption will "
                    "not destroy your kind as it does ours, but it will hurt you if you are "
                    "careless. Take these supplies.",
                    "Votha Krr",
                    "happy",
                )
            self._stage = 7
            return

        # Stage 7 — Give loot; Votha's farewell
        if self._stage == 7:
            loot = [items.Antidote(5), items.Restorative(2)]
            self.player.add_items_to_inventory(loot)

            self.needs_input = True
            self.input_type = "choice"
            begin_conversation(_JEAN_VOTHA_KRR)
            narrate(
                "Votha Krr waved a hand, and a Grondite attendant stepped forward, carrying a "
                "small bundle of supplies. The attendant handed the bundle to Jean, who took it "
                "gratefully."
            )
            narrate("[Received: 5 Antidotes, 2 Restoratives]")
            narrate("With that, Votha Krr slowly got to his feet, his massive form towering over Jean.")
            say(
                "May the earth guide your steps, Jean. You are a guest of our city. The "
                "merchants of the Eastern Gate will have what you need for the road. Return to "
                "me when you have dealt with the slimes.",
                "Votha Krr",
                "neutral",
            )
            narrate("He paused. Those deep-set eyes held Jean's for a moment longer than necessary.")
            say(
                "And when you return — perhaps we will speak again of where you are going.",
                "Votha Krr",
                "neutral",
            )
            narrate("He said it the same way he'd said it the first time. Like a door left open.")
            self.input_prompt = ""
            self.input_options = [{"value": "done", "label": "Continue"}]
            self._stage = 8
            return

        # Stage 8 — Cleanup
        if self._stage == 8:
            self.player.teleport("grondia", (10, 5))
            self.needs_input = False
            self.completed = True
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
        if self.player.universe.story.get("king_slime_defeated"):
            return
        time.sleep(1)
        begin_conversation(_JEAN_SOLO)
        print_slow("The churning stilled. A deep, resonant silence settled over the cavern.")
        time.sleep(1)
        print_slow(
            "Then — gradually — the green receded. Ripple by ripple, the corruption dissolved "
            "outward from the center, the thick slime thinning and clearing until clean, "
            "luminescent blue water filled the chamber."
        )
        time.sleep(1.5)
        print_slow(
            "The central stone island was exactly what it always had been. "
            "The light was steady and quiet, blue-white, older than the corruption that had hidden it."
        )
        time.sleep(1)
        print_slow(
            "On the island, something caught the light. "
            "Impossibly sharp. Impossibly beautiful."
        )
        time.sleep(1.5)
        print_slow(
            "Jean stood in the clearing water. It was cold — rising back toward its natural level, "
            "lapping at his boots. The fight was over. There was nothing left in the room that needed him."
        )
        time.sleep(1)
        say(
            "He didn't know what to do with his hands when they weren't needed.",
            "Jean",
            "neutral",
            thought=True,
        )
        # Close the stage here — the rest of this event (pool cleansing, Gorran's
        # arrival) is unstaged narration; Gorran isn't cast/entered as a portrait,
        # so leaving the conversation open would strand Jean's portrait on-screen
        # through an unrelated passage.
        end_conversation()
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

        # Queue the memory flash so it fires once Jean picks up the fragment
        self.tile.events_here.append(Ch02KingSlimeMemoryFlash(
            player=self.player, tile=self.tile, repeat=False
        ))

        # Set the story flag so AfterKingSlimeReturn can fire later
        self.player.universe.story["king_slime_defeated"] = "1"

        # Teleport Gorran to the arena. He lives as an ally NPC; find him wherever
        # he currently is (atrium fallback, then combat_list_allies).
        # player.map is a dict keyed by (x, y) tuples, not an object with .tiles.
        current_map = self.player.map
        gorran = None
        atrium_coords = (2, 1)
        if atrium_coords in current_map:
            atrium_tile = current_map[atrium_coords]
            for npc in list(atrium_tile.npcs_here):
                if npc.__class__.__name__ == "Gorran":
                    atrium_tile.npcs_here.remove(npc)
                    npc.tile = self.tile
                    self.tile.npcs_here.append(npc)
                    gorran = npc
                    break

        if gorran is None:
            for ally in list(getattr(self.player, "combat_list_allies", [])):
                if ally.__class__.__name__ == "Gorran":
                    gorran = ally
                    break
            if gorran is not None:
                old_tile = getattr(gorran, "tile", None)
                if old_tile and gorran in getattr(old_tile, "npcs_here", []):
                    old_tile.npcs_here.remove(gorran)
                gorran.tile = self.tile
                self.tile.npcs_here.append(gorran)

        # Narrate Gorran's arrival and his reaction to the cleansed pools
        time.sleep(1)
        print_slow("Then — footsteps. Heavy, deliberate, from the corridor entrance.")
        time.sleep(0.5)
        print_slow("Gorran rounded the archway and stopped.")
        time.sleep(1)
        print_slow(
            "He looked at the pools. Clean, blue, still. His great head moved slowly across the chamber, "
            "taking in what it had been and what it was now."
        )
        time.sleep(1.5)
        print_slow(
            "He made no sound. He just stood there in the entrance to the arena, "
            "looking at the water the way someone looks at something they thought was gone."
        )
        time.sleep(1)
        print_slow(
            "Then, slowly, he walked to the edge of the nearest pool and lowered himself to one knee. "
            "He extended one wide hand over the surface. Didn't touch it. Just held his palm there, "
            "feeling the cold rise off it."
        )
        time.sleep(2)
        print_slow(
            "A sound from him — low and long, held in the chest. Not quite a word. "
            "He stayed like that for a moment, hand over the water. Then he straightened."
        )
        time.sleep(1)

        self._cleanse_pool_tiles(self.player)

        self.tile.remove_event(self.name)

    def _cleanse_pool_tiles(self, player, current_map=None):
        """Update corrupted channel tile descriptions to reflect the post-cleansing state.

        Physical damage (acid pitting, dissolved floors, staining) persists as geological
        evidence. Active slime, living corruption, and all rumbling references are gone.
        """
        # Use universe.maps lookup so the correct map is found even if player.map
        # is pointing elsewhere (e.g., after a flee from a random encounter).
        current_map = next(
            (m for m in player.universe.maps if m.get("name") == "grondelith-mineral-pools"),
            current_map,  # fall back to the passed-in map if not found
        )
        cleansed = {
            (2, 2): (
                "The colour has returned. Where the channels ran green, they run clear now — "
                "milky-blue, lit from below, moving with quiet purpose. The walls carry the "
                "memory of what was here: a dark tide line, scored stone, old acid pitting. "
                "The air is cold and mineral-clean. The crevice on the west wall is visible "
                "now, no longer obscured — a thin gap breathing the same clean air as the "
                "rest of the passage."
            ),
            (3, 2): (
                "The walkway holds. The channel below is clear — mineral water moving slowly "
                "east, washing over stone that shows where the slime ate in: pitting, softened "
                "edges, the marks of something that fed here for a long time. To the east, the "
                "sealed chamber is silent now. Whatever was feeding there is gone."
            ),
            (4, 2): (
                "The pocket has drained. Walls that were sheeted in thick slime are bare — "
                "acid-scored and stained, but bare. A stone shelf juts from the east wall, "
                "its surface worn smooth. Whatever this room was before the infestation, it "
                "is only an empty chamber now: still, cold, smelling of mineral water and "
                "old stone."
            ),
            (2, 3): (
                "The walkway is intact. Below it, the pool is clear — deep blue, faintly "
                "luminous, the same light as the atrium above. The acid pitting on the walls "
                "hasn't changed; the dissolution is old work, stone already spent. Above: "
                "silence. Whatever was nesting in the ceiling has gone. The rumbling from "
                "the south is gone too. It is quiet here in a way it wasn't before."
            ),
            (3, 3): (
                "The wider cavern is still. The dissolution is visible — the walls stripped "
                "back to raw mineral where the slime ate through centuries of accumulated "
                "stone — but the slime itself is gone. The chamber is deep and cold and very "
                "quiet. The far wall is bare."
            ),
            (4, 3): (
                "The low chamber is unchanged by the cleansing — the ceiling is still "
                "collapsed, the rubble still fills half the floor. The old slime residue has "
                "dried to a thin dark crust on the stone: harmless, inert, the ghost of a "
                "longer infestation. The collapsed section exposes raw mineral beneath, "
                "unchanged. It is quiet here. It was quiet here before too."
            ),
            (2, 4): (
                "The passage is as narrow as ever — the walls close to arm's width for a "
                "long stretch — but the slime that coated them is gone, leaving bare stone "
                "that shows where it was: long staining, dissolution marks where it ran "
                "thickest. The south end opens into a larger space. No rumbling. No sound "
                "at all except Jean's footsteps and the faint movement of water."
            ),
            (3, 4): (
                "The floor is still dissolved — the passage still crosses stone islands "
                "above where the slime ate through — but the water between them is clear "
                "now: cold, still, faintly luminous. The high-water mark is still visible: "
                "a clean band of stone above the old slime line, dissolution below. It is "
                "just water now."
            ),
            (2, 5): (
                "The passage is open and still. The walls are bare stone — stained where "
                "the slime reached, but bare. The rumbling is gone. Jean's footsteps land "
                "without answer. The passage south opens into a large space: blue-white "
                "light, clean water, the quiet aftermath of something enormous being undone."
            ),
        }
        for coords, description in cleansed.items():
            if coords in current_map:
                tile = current_map[coords]
                tile.spawn_object("TileDescription", player, tile, description=description)


class Ch02GorranAtPools(Event):
    """
    Fires once when Jean first enters the Grondelith map (tile 2,0).

    Gorran led Jean this far but cannot follow into the corrupted interior —
    the corruption is too dense for stone to tolerate. He settles at the
    Atrium threshold (tile 2,1), where he will wait until King Slime is
    defeated. AfterDefeatingKingSlime already looks for him at (2,1).

    Attach to tile (2,0) in grondelith-mineral-pools.json.
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="Ch02GorranAtPools"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )
        # Set description for API serialization
        self.description = (
            "Gorran stops at the threshold of the corrupted interior, unable to proceed. "
            "He settles at the atrium entrance to wait for Jean's return."
        )

    def check_conditions(self):
        story = getattr(self.player.universe, "story", {})
        if story.get("gorran_at_pools"):
            self.tile.remove_event(self.name)
            return
        self.pass_conditions_to_process()

    def process(self):
        # Spawn Gorran at the Atrium (2,1) — where AfterDefeatingKingSlime
        # expects to find him. Don't place him on this entry tile so he doesn't
        # block the passage or trigger combat checks.
        # Use universe.maps lookup rather than player.map so the correct tile is
        # found even when player.map is pointing to a combat arena after a flee.
        pools_map = next(
            (m for m in self.player.universe.maps if m.get("name") == "grondelith-mineral-pools"),
            None,
        )
        atrium_tile = pools_map.get((2, 1)) if pools_map else None
        if atrium_tile is not None:
            gorran_already_there = any(
                n.__class__.__name__ == "Gorran" for n in atrium_tile.npcs_here
            )
            if not gorran_already_there:
                # Check if Gorran is in the player's party
                gorran_in_party = None
                for ally in list(getattr(self.player, "combat_list_allies", [])):
                    if ally.__class__.__name__ == "Gorran":
                        gorran_in_party = ally
                        break

                if gorran_in_party is not None:
                    # Remove Gorran from party and move to tile
                    self.player.combat_list_allies.remove(gorran_in_party)
                    gorran_in_party.tile = atrium_tile
                    atrium_tile.npcs_here.append(gorran_in_party)
                else:
                    # Spawn new Gorran if not in party
                    atrium_tile.spawn_npc("Gorran")

        if not self.player.skip_dialog:
            print_slow(
                "Gorran had come to the threshold and no further. He stood at the entrance "
                "to the atrium — that great vaulted space with its spring-fed pools — "
                "facing south, one hand resting against the stone arch.",
                delay=0.03,
            )
            time.sleep(1.5)
            print_slow(
                "Jean came up beside him. The air changed here. Even at the threshold he could "
                "feel it — a heaviness below the mineral scent, something sweet and wrong.",
                delay=0.03,
            )
            time.sleep(1)
            print_slow(
                "Gorran did not look at him. He tapped his own chest twice — slow, deliberate. "
                "Then he pointed south, toward the deeper passages. Then he drew his hand back.",
                delay=0.03,
            )
            time.sleep(1)
            print_slow(
                "He made a sound. Low and brief. The Golemite equivalent of: I know.",
                delay=0.04,
            )
            time.sleep(1)
            print_slow(
                "He lowered himself beside the arch — that slow, deliberate settling of stone "
                "finding its position. He would wait here. Jean understood that.",
                delay=0.03,
            )
            time.sleep(1.5)
            await_input()

        self.player.universe.story["gorran_at_pools"] = "1"
        self.tile.remove_event(self.name)


class Ch02ArenaEntrance(Event):
    """
    Fires once when Jean first enters the arena tile (2,6) with King Slime present.

    Delivers the isolation/atmosphere narrative as Jean faces the King Slime.
    Sets story["arena_entered"] = "1".

    Attach to the arena tile in grondelith-mineral-pools.json.
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="Ch02ArenaEntrance"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )
        # Set description for API serialization
        self.description = (
            "Jean enters the arena where the King Slime waits. The isolation and "
            "weight of the moment settles over the water."
        )

    def check_conditions(self):
        story = getattr(self.player.universe, "story", {})
        if story.get("arena_entered"):
            self.tile.remove_event(self.name)
            return
        # Only fire if King Slime is still present
        king_alive = any(n.__class__.__name__ == "KingSlime" for n in self.tile.npcs_here)
        if king_alive:
            self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            print_slow(
                "The chamber opened before Jean — vast, vaulted, filled entirely with water. "
                "The pool covered the floor from wall to wall, its surface roiling with a "
                "sickly green luminescence.",
                delay=0.03,
            )
            time.sleep(1)
            print_slow(
                "In the center of that corrupted expanse sat a single stone island. "
                "On it: a shape. Massive. Waiting.",
                delay=0.03,
            )
            time.sleep(1.5)
            print_slow(
                "The green in the water pulsed. The sound that came from it was not a voice — "
                "it was something older. Something hungry.",
                delay=0.03,
            )
            time.sleep(1)
            print_slow(
                "Jean stepped forward. The water began to churn.",
                delay=0.04,
            )
            time.sleep(1.5)

        self.player.universe.story["arena_entered"] = "1"
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
                "Gorran stood at the entrance to the corridor, one hand braced against the arch. "
                "He was looking at the island.",
                delay=0.03,
            )
            time.sleep(1)
            print_slow("Jean followed his gaze.", delay=0.05)
            time.sleep(1)
            print_slow(
                "The fragment was still there. He'd walked out without it.",
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
        # No other character is present in this flashback — it's Jean's solo
        # traumatic memory, so the cast is Jean alone. Key introspective beats
        # are tagged as his internal thought (italic, no reactions to author —
        # there's no one else on stage to react).
        memory_lines = [
            ("The edge catches Jean's finger.", 1.5),
            ("", 0.5),
            (
                "Pain — sudden, immediate, real.",
                1.5,
                {"speaker": "Jean", "emotion": "surprised", "thought": True},
            ),
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
                {"speaker": "Jean", "emotion": "sad", "thought": True},
            ),
            ("emptiness.", 3.0, {"speaker": "Jean", "emotion": "sad", "thought": True}),
        ]
        aftermath = [
            "Silence.",
            "",
            "Jean stood on the stone island. The water around it was blue.",
            "The fragment was in his hand, still sharp, still bright.",
            "",
            (
                "The bleeding finger was real. Everything else was gone.",
                {"speaker": "Jean", "emotion": "sad", "thought": True},
            ),
        ]
        super().__init__(
            player=player,
            tile=tile,
            memory_lines=memory_lines,
            aftermath_text=aftermath,
            cast=[("Jean", "left", "neutral")],
            repeat=repeat,
            name=name,
        )

    def check_conditions(self):
        story = getattr(self.player.universe, "story", {})
        if story.get("king_slime_flash_fired"):
            # Already completed; clean up if still lingering in events_here.
            if self in getattr(self.tile, "events_here", []):
                self.tile.events_here.remove(self)
            return
        if self.needs_input:
            # Mid-flash — waiting for the player to click Continue.
            # Don't call process() again or the dialog will re-stack.
            return
        if any(
            i.__class__.__name__ == "MineralFragment"
            for i in getattr(self.player, "inventory", [])
        ):
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        super().process(user_input)
        if user_input is not None:
            # Completion pass — mark as fired so reloads/re-checks can't replay it.
            self.player.universe.story["king_slime_flash_fired"] = "1"


class AfterKingSlimeReturn(Event):
    """
    Fires once when Jean re-enters the Citadel after king_slime_defeated is set.
    Votha Krr accepts the mineral fragment and sends Jean toward the Echoing Caves.
    Seven stages: greeting, choice, consumption, acknowledgment, wisdom, farewell, cleanup.
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

    def process(self, user_input=None):
        if not hasattr(self, "_stage"):
            self._stage = 1

        # Check if Jean actually has the MineralFragment
        has_fragment = any(
            i.__class__.__name__ == "MineralFragment" for i in self.player.inventory
        )
        if not has_fragment:
            self.needs_input = False
            return

        # Stage 1 — Votha rises and greets Jean; present choice
        if self._stage == 1:
            self.needs_input = True
            self.input_type = "choice"
            begin_conversation(_JEAN_VOTHA_KRR)
            narrate(
                "Votha Krr rose from his throne as Jean entered. His deep-set eyes took in the "
                "bleeding finger, the fragment in Jean's hand, and Jean's expression — all at once."
            )
            say("The pools are clean, little one. You have done well.", "Votha Krr", "neutral")
            narrate(
                "Jean still held the mineral fragment. The cut on his finger had stopped "
                "bleeding but hadn't stopped hurting."
            )
            self.input_prompt = ""
            self.input_options = [
                {"value": "a", "label": "Hand it over."},
                {"value": "b", "label": '"What is this thing, exactly?"'},
                {"value": "c", "label": "[Set it on the edge of the throne without a word.]"},
            ]
            self._stage = 2
            return

        # Stage 2 — Process Jean's choice and narrate the handover
        if self._stage == 2:
            _frag_choice = str(user_input or "a").strip().lower()
            _choice_map = {"0": "a", "1": "b", "2": "c"}
            _frag_choice = _choice_map.get(_frag_choice, _frag_choice)
            if _frag_choice not in ("a", "b", "c"):
                _frag_choice = "a"

            begin_conversation(_JEAN_VOTHA_KRR)
            if _frag_choice == "a":
                narrate("Jean held it out. Votha took it from his hand.")
            elif _frag_choice == "b":
                say("What is this thing, exactly?", "Jean", "neutral")
                say(
                    "A memory, made stone. The mineral pools do not merely hold water — they "
                    "record what passes through them. Light, creature, time. This fragment "
                    "carries something very old. It is right that it returns to stone.",
                    "Votha Krr",
                    "neutral",
                )
                narrate("He took the fragment from Jean's hand.")
            else:  # c
                narrate(
                    "Jean sets the fragment on the armrest of the throne without looking at "
                    "Votha. The Elder watches him do it. Waits. Then reaches out and picks it "
                    "up, slowly, as though giving Jean time to reconsider."
                )

            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 3
            return

        # Stage 3 — Votha consumes the fragment
        if self._stage == 3:
            begin_conversation(_JEAN_VOTHA_KRR)
            narrate("Votha regarded the fragment for a single moment — then placed it in his mouth.")
            narrate(
                "A soft, contented rumble escaped him. The fragment was gone.",
                reactions={"Votha Krr": "happy"},
            )
            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 4
            return

        # Stage 4 — Votha acknowledges Jean's completion and his return
        if self._stage == 4:
            begin_conversation(_JEAN_VOTHA_KRR)
            say(
                "The pools are clean. You have done what we could not do alone, little one.",
                "Votha Krr",
                "neutral",
            )
            narrate(
                "He studied Jean's face. Then — the bleeding finger. He regarded it for a "
                "moment without comment."
            )
            say("You came back.", "Votha Krr", "neutral")
            narrate("He said it simply. As an observation, not a compliment.")
            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 5
            return

        # Stage 5 — Votha's philosophical directive
        if self._stage == 5:
            begin_conversation(_JEAN_VOTHA_KRR)
            say(
                "To mend what is broken, one must first understand the cracks. Go now. Seek "
                "the Echoing Caves to the west, beyond the river. There, the earth sings the "
                "songs of lost things. Perhaps you will find a different kind of strength "
                "there — or, at the very least, a clearer path.",
                "Votha Krr",
                "neutral",
            )
            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 6
            return

        # Stage 6 — Votha's farewell gesture
        if self._stage == 6:
            begin_conversation(_JEAN_VOTHA_KRR)
            narrate(
                "He did not elaborate. When Jean opened his mouth, Votha Krr's only answer "
                "was to press two fingers briefly to his own chest — over the place a human "
                "would call the heart — and then withdraw."
            )
            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = ""
            self.input_options = [{"value": "continue", "label": "Continue"}]
            self._stage = 7
            return

        # Stage 7 — Cleanup
        if self._stage == 7:
            # Remove the MineralFragment from inventory
            for item in list(self.player.inventory):
                if item.__class__.__name__ == "MineralFragment":
                    self.player.inventory.remove(item)
                    break

            self.needs_input = False
            self.completed = True
            self.player.universe.story["votha_krr_response_given"] = "1"
            self.tile.remove_event(self.name)
