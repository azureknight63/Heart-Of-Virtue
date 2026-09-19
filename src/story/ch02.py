"""
Chapter 02 events
"""

import time
import types

from src import items
from src.events import Event, gate_is_set, set_story_gate, story_gates
from src.functions import print_slow, await_input
from src.npc._progression import join_party
from src.objects import TileDescription
from src.story.effects import MemoryFlash, NPCSpawnerEvent
from src.journal import (
    complete_objective,
    set_objective,
    OBJ_CH01_FOLLOW_GORRAN,
    OBJ_CH02_EXPLORE_GRONDIA,
    OBJ_CH02_FIND_MARA,
    OBJ_CH02_HEAD_EAST,
    OBJ_CH02_KING_SLIME,
    OBJ_CH02_VOTHA_KRR,
)
from src.narration import (
    ANSI_ESCAPE_RE,
    narrate,
    say,
    begin_conversation,
    end_conversation,
    enter_op,
    exit_op,
    react,
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


#: The beta route, authored once. The briefing renders it as its numbered task
#: list and the journal stores it as the player's objectives, so the two can
#: never drift — which they had already begun to do when they were separate
#: literals a hundred lines apart.
_BETA_ROUTE = (
    (OBJ_CH02_EXPLORE_GRONDIA, "Explore Grondia and speak with its inhabitants."),
    (OBJ_CH02_KING_SLIME, "Reach the Grondelith Mineral Pools and defeat the King Slime."),
    (OBJ_CH02_VOTHA_KRR, "Return to the Citadel and speak with Votha Krr."),
    (OBJ_CH02_HEAD_EAST, "Exit Grondia and head east to the river."),
    (OBJ_CH02_FIND_MARA, "Find Mara at the river camp and arrange a crossing."),
)

#: The route as the briefing modal shows it: "1. …\n\n2. …".
_BETA_ROUTE_PROSE = "\n\n".join(
    "%d. %s" % (index, text) for index, (_key, text) in enumerate(_BETA_ROUTE, start=1)
)


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
                + _BETA_ROUTE_PROSE + "\n\n"
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
            complete_objective(self.player, OBJ_CH01_FOLLOW_GORRAN)
            # The five steps this briefing just listed, recorded where the
            # player can re-read them after the modal closes (issue #538).
            for key, text in _BETA_ROUTE:
                set_objective(self.player, key, text, chapter=2)
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
                "place. The halls were vast and echoed with the sound of their footsteps."
            )
            say(
                "The ceiling ran up into darkness the way the roof of a nave runs up into "
                "candle-smoke, and a hand had half-lifted toward my brow before I thought "
                "about it. I let the old gesture finish. It steadied me.",
                "Jean",
                "neutral",
                thought=True,
            )
            say(
                "Then the air reached me, and the carvings lost me entirely — steady, "
                "slow-moving, cool at my feet and perceptibly warmer at my shoulders. "
                "Convection, working the way it's supposed to, on a scale I had never "
                "encountered. I wanted to find where it rose.",
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
            react("Jean", "surprised")
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
            react("Jean", "happy")
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
            react("Elder", "concerned")
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
            react("Jean", "concerned")
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
                    "The slimes would not kill you the way they kill us. That is why I ask.",
                    "Votha Krr",
                    "neutral",
                )
                say("Is it centralized? Or spread through the whole system?", "Jean", "curious")
                say(
                    "There is a heart to it. One great slime at the center. Remove it, and the "
                    "rest will follow.",
                    "Votha Krr",
                    "neutral",
                )
                say(
                    "Wait — you said it wouldn't kill me the same way. There are others here "
                    "like me?",
                    "Jean",
                    "surprised",
                )
                say(
                    "We have known your kind before. Traded with them. Fought alongside them.",
                    "Votha Krr",
                    "neutral",
                )
                narrate("He paused, searching for the word with the patience of stone finding water.")
                say("Humans.", "Votha Krr", "curious")
                narrate("The word rumbled from him like a landslide, reverberating into Jean's chest.")
                say(
                    "I was quiet, but my mind was already moving — tracing the shape of the "
                    "problem. An infestation with a center. Corrupted channels. A source. I'd had "
                    "that kind of job before. Somewhere, in some life. I didn't ask myself why "
                    "I was so sure of that.",
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
            self.needs_input = True
            self.input_type = "choice"
            begin_conversation(_JEAN_VOTHA_KRR)
            narrate(
                "Votha Krr waved a hand, and a Grondite attendant stepped forward, carrying a "
                "small bundle of supplies. The attendant handed the bundle to Jean, who took it "
                "gratefully."
            )
            # Narrate the hand-over first, THEN grant the items -- previously
            # this ran before the narration above and was followed by a
            # redundant "[Received: ...]" summary, so the same grant rendered
            # three times total (add_items_to_inventory narrates once per
            # item on its own; see issue #540 item 18).
            loot = [items.Antidote(5), items.Restorative(2)]
            self.player.add_items_to_inventory(loot)
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
                "curious",
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


#: What ``Universe`` names the Grondelith pools map: the file stem.
POOLS_MAP_NAME = "grondelith-mineral-pools"

#: The Atrium: the great vaulted space one tile inside the pools. A session
#: saved before #613 may still have Gorran waiting here (``GORRAN_WAIT_COORDS``).
ATRIUM_COORDS = (2, 1)

#: Where Gorran waits while Jean goes into the pools alone: the entry tile,
#: which is the tile the map authors ``Ch02GorranAtPools`` onto and the tile
#: Jean is standing on while that scene plays. The scene says he "had come to
#: the threshold and no further" and that Jean "came up beside him", so the
#: fiction puts them both here.
THRESHOLD_COORDS = (2, 0)

#: Where ``AfterDefeatingKingSlime`` looks for the waiting Gorran: the
#: threshold first, then the Atrium, so a session that was already inside the
#: pools when #613 shipped still gets him back.
GORRAN_WAIT_COORDS = (THRESHOLD_COORDS, ATRIUM_COORDS)

#: Gorran's class name: what every lookup in this module matches on, and what
#: ``MapTile.spawn_npc`` is asked for when he has to be stood up.
GORRAN = "Gorran"

#: Where ``_wear_waiting_idle_line`` keeps his ordinary line while he waits.
_IDLE_LINE_BEFORE_WAIT = "idle_message_before_wait"

#: What the room prints about Gorran while he waits. A room renders
#: ``npc.idle_message`` (``NPCSerializer`` / ``RoomContents.jsx``), and his
#: ordinary "bumbling about" -- the line of a wandering NPC -- rendered
#: directly under the scene that settles him against the arch (#613).
GORRAN_WAITING_IDLE_MESSAGE = (
    " waits beside the arch, one broad hand resting against the stone."
)

#: The story key holding the game tick at which Jean was last reminded to
#: hand over the mineral fragment, how many ticks must pass before the next
#: reminder, and the "never reminded" sentinel (far below any real tick, so
#: the first call always passes the rate limit).
FRAGMENT_REMINDER_TICK_KEY = "fragment_reminder_tick"
FRAGMENT_REMINDER_TICKS = 3
FRAGMENT_REMINDER_NEVER = -999

#: What the arena reads once King Slime falls; ``AfterDefeatingKingSlime``
#: writes it as the arena tile's own description.
CLEANSED_ARENA_DESCRIPTION = (
    "The circular cavern is still. The pool that filled it — wall to wall with "
    "pulsating corruption — is gone. Clean, luminescent blue water rests in its place, "
    "glowing faintly from below. The single stone island at the centre is bare and quiet. "
    "The arena smells of minerals and cold water."
)

#: What each corrupted channel tile reads once King Slime falls. Physical
#: damage (acid pitting, dissolved floors, staining) persists as geological
#: evidence; active slime, living corruption and every rumbling reference
#: are gone.
CLEANSED_CHANNEL_DESCRIPTIONS = types.MappingProxyType({
    (1, 2): (
        "A gap barely wide enough to squeeze through. The thin film of slime that "
        "reached this far has dried to a faint dark line across the threshold, as "
        "though it stopped here and went no further. Beyond: cold, clean air, sharp "
        "with minerals. Silence, on both sides of the gap now."
    ),
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
})


def find_pools_map(player):
    """The loaded pools map, or None when ``player``'s universe has none.

    Looked up in ``universe.maps`` by name, not through ``player.map``,
    which can point elsewhere -- a combat arena after a flee, say.
    """
    maps = getattr(getattr(player, "universe", None), "maps", None)
    if not isinstance(maps, (list, tuple)):
        return None
    return next(
        (m for m in maps if isinstance(m, dict) and m.get("name") == POOLS_MAP_NAME), None
    )


def _coordinate_tiles(pools_map):
    """``(coords, tile)`` for each tile entry of a loaded map -- the
    ``(x, y)``-keyed ones; ``"name"`` is no tile."""
    for coords, tile in pools_map.items():
        if isinstance(coords, tuple):
            yield coords, tile


def _move_npc_to(npc, destination, also_from=None):
    """Stand ``npc`` on ``destination`` exactly once, and off every room he
    is known to be listed in: those :func:`_rooms_of` names, the destination
    itself, and ``also_from``, a room known to hold him that neither of his
    own attributes points at (see :func:`_unlist_npc` for what is skipped).

    ``current_room`` is what ``Player.recall_friends`` reads to take a
    follower off his old room, so it moves with the listing. Appending without
    removing is how Gorran came to stand in two rooms at once (#613).
    """
    _unlist_npc(npc, *_rooms_of(npc), destination, also_from)
    npc.current_room = destination
    npc.tile = destination
    destination.npcs_here.append(npc)


def _rooms_of(npc):
    """The rooms ``npc``'s own attributes say he is in: ``current_room``, and
    ``tile``, the older attribute these events have always set."""
    return getattr(npc, "current_room", None), getattr(npc, "tile", None)


def _unlist_npc(npc, *rooms):
    """Take ``npc`` off each room's ``npcs_here``, every time he is listed.
    ``None``, and anything without an ``npcs_here`` list, is skipped."""
    for room in rooms:
        npcs_here = getattr(room, "npcs_here", None)
        if isinstance(npcs_here, list):
            while npc in npcs_here:
                npcs_here.remove(npc)


def _is_gorran(npc):
    """Whether ``npc`` is Gorran, matched by class name (``GORRAN``, the name
    ``spawn_npc`` is asked for). The stub ``spawn_npc`` falls back to when the
    class cannot be built is a ``_StubNPC`` and does not match."""
    return npc.__class__.__name__ == GORRAN


def _find_gorran(npcs):
    """The first Gorran in ``npcs``, or None."""
    return next((npc for npc in npcs if _is_gorran(npc)), None)


def _party(player):
    """``player.combat_list_allies`` when it is a list, else an empty list:
    how this module searches the party. A caller that removes from the result
    edits the party itself; one that must *add* to it goes through
    ``combat_list_allies`` directly, since the empty fallback is a throwaway."""
    allies = getattr(player, "combat_list_allies", None)
    return allies if isinstance(allies, list) else []


def _wear_waiting_idle_line(npc):
    """Give ``npc`` the waiting idle line, keeping his ordinary one for
    ``_restore_ordinary_idle_line``.

    Guarded rather than assumed: the spawn fallback in ``MapTile.spawn_npc``
    stands up a stub with no idle line at all, and a missing flavour line must
    not crash the beat. Wearing it twice keeps the ordinary line, rather than
    saving the waiting line in its place.
    """
    ordinary_line = getattr(npc, "idle_message", None)
    if isinstance(ordinary_line, str) and ordinary_line != GORRAN_WAITING_IDLE_MESSAGE:
        setattr(npc, _IDLE_LINE_BEFORE_WAIT, ordinary_line)
        npc.idle_message = GORRAN_WAITING_IDLE_MESSAGE


def _restore_ordinary_idle_line(npc):
    """Put back the line ``_wear_waiting_idle_line`` kept, if it kept one."""
    ordinary_line = getattr(npc, _IDLE_LINE_BEFORE_WAIT, None)
    if isinstance(ordinary_line, str):
        npc.idle_message = ordinary_line
        delattr(npc, _IDLE_LINE_BEFORE_WAIT)


def _is_hostile(npc):
    """Whether the sweep treats ``npc`` as an enemy: ``npc.friend`` is the
    engine's only friend/foe flag (``src/npc/_base.py``), so anything
    without it set is hostile."""
    return not getattr(npc, "friend", False)


class AfterDefeatingKingSlime(Event):
    """
    Fires once KingSlime is absent from the arena tile.
    Rewrites the cleansed pool tiles' descriptions, grants the MineralFragment
    straight into Jean's inventory (nothing is dropped on the floor), and
    queues the memory flash that fires on that possession. Gorran is then
    brought from where he waited (``GORRAN_WAIT_COORDS``) to the arena and
    rejoins the party (#577), and every enemy and spawner still in the pools
    is swept out (#594).
    """

    GATE_KEY = "king_slime_defeated"

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
        if self.gate_is_set(self.GATE_KEY):
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
            "I didn't know what to do with my hands when they weren't needed.",
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

        # Overwrite, don't spawn a TileDescription: that object only ADDS
        # text and has no real name, so the corrupted and cleansed prose
        # rendered together (#573) and a nameless interactable appeared
        # (#572). Same pattern as Ch01BridgeWall (src/story/ch01.py).
        self.tile.description = CLEANSED_ARENA_DESCRIPTION

        # Grant the MineralFragment straight to Jean's inventory. Spawning it as
        # a floor item relied on the player picking it up before leaving, backed
        # only by Ch02FragmentReminder — which is attached to this pools tile and
        # is never evaluated once Jean crosses to another map, so leaving without
        # the fragment could soft-lock the Votha Krr hand-over. Granting it here
        # guarantees he carries it. The memory flash still fires on possession
        # (see Ch02KingSlimeMemoryFlash.check_conditions). See #378 / #371.
        self.player.add_items_to_inventory([items.MineralFragment()])

        # Queue the memory flash so it fires once the fragment is in inventory
        self.tile.events_here.append(Ch02KingSlimeMemoryFlash(
            player=self.player, tile=self.tile, repeat=False
        ))

        # Set the story flag so AfterKingSlimeReturn can fire later
        self.set_story_gate(self.GATE_KEY)
        complete_objective(self.player, OBJ_CH02_KING_SLIME)

        pools_map = find_pools_map(self.player)
        gorran = self._summon_gorran(pools_map)
        if gorran is not None:
            self._rejoin_party(gorran)

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

        self._cleanse_pool_tiles(pools_map)

        self.tile.remove_event(self.name)

    def _summon_gorran(self, pools_map):
        """Bring Gorran to the arena tile and return him, or None when he is
        nowhere to be found.

        He lives as an ally NPC. ``Ch02GorranAtPools`` sat him down to wait at
        one of ``GORRAN_WAIT_COORDS`` in ``pools_map`` -- a dict keyed by
        ``(x, y)`` tuples, looked up through the universe (``find_pools_map``)
        because after a flee ``player.map`` can point at a combat arena with
        none of those tiles in it (it is the fallback when the pools map is
        not loaded). A Gorran who never left the party is found in
        ``combat_list_allies`` instead. Either way he comes off the room he
        stood in and onto this one -- ``current_room`` included, since he is
        about to rejoin the party and follow Jean out, and a follower whose
        ``current_room`` still named the wait tile stayed listed in the arena
        for good (#613).
        """
        current_map = pools_map or self.player.map
        gorran = old_tile = None
        for coords in GORRAN_WAIT_COORDS:
            if coords not in current_map:
                continue
            wait_tile = current_map[coords]
            gorran = _find_gorran(getattr(wait_tile, "npcs_here", []))
            if gorran is not None:
                old_tile = wait_tile
                break
        if gorran is None:
            gorran = _find_gorran(_party(self.player))
        if gorran is None:
            return None
        _move_npc_to(gorran, self.tile, also_from=old_tile)
        return gorran

    def _rejoin_party(self, gorran):
        """Put Gorran back in the party (#577).

        ``Ch02GorranAtPools`` took him out of ``combat_list_allies`` to wait
        at the threshold, and that list is the single source of truth for the
        status party, battle allies and tile-following -- without this he
        stayed behind for good. Same join as Ch01's escape beat -- literally
        so since #625: ``join_party`` flags him a friend, puts him behind the
        player at index 0, and levels him up to Jean.

        His waiting idle line goes with the wait (#613): he follows Jean out
        of the pools from here, and "waits beside the arch" would travel with
        him all the way down the Eastern Descent.
        """
        join_party(self.player, gorran)
        _restore_ordinary_idle_line(gorran)

    def _cleanse_pool_tiles(self, pools_map):
        """Rewrite each corrupted channel tile of ``pools_map`` as
        ``CLEANSED_CHANNEL_DESCRIPTIONS`` has it, then sweep the enemies and
        spawners still in the pools (#594, ``_clear_pool_enemies``) and tell
        the player the channels are clear. ``pools_map`` is
        ``find_pools_map``'s result: None -- a universe that has not loaded
        the pools map -- has nothing to rewrite and is left alone rather than
        raised on."""
        if pools_map is None:
            return
        for coords, description in CLEANSED_CHANNEL_DESCRIPTIONS.items():
            if coords in pools_map:
                # Overwrite, don't spawn a TileDescription -- see the
                # arena comment in process() (#572/#573).
                pools_map[coords].description = description
        self._clear_pool_enemies(pools_map)
        narrate(
            "Back along the channels, the last of the slime slackened and ran to "
            "nothing, and the glands that had studded the walls went still. Nothing "
            "in the pools would rise to meet him now."
        )

    def _clear_pool_enemies(self, pools_map):
        """Sweep every remaining enemy out of the pools and spend every
        spawner still armed there (#594). Bookkeeping only: the narration
        belongs to ``_cleanse_pool_tiles``.

        The pools map places no static NPC: every enemy comes from an
        ``NPCSpawnerEvent``. The plain ones fire on map entry, so by now
        their NPCs stand on the channel tiles; the ``PulsingGlandEvent``
        glands fire only on tile entry, so any Jean has not walked past
        would still burst a fresh slime on the way out. Both contradict the
        cleansing he just watched, so every NPC without ``friend`` set is
        removed -- the CaveBats at the walkway included; two bats ambushing
        him after "the corruption recedes" reads no better than a slime --
        and every spawner is marked run and dropped. Allies (Gorran) stay.

        Filtered by ``isinstance`` rather than ``tile.remove_event(name)``:
        that stops at the first name match and several tiles carry more
        than one event named ``NPCSpawnerEvent``.
        """
        for _coords, tile in _coordinate_tiles(pools_map):
            npcs_here = getattr(tile, "npcs_here", None)
            if isinstance(npcs_here, list):
                for npc in [n for n in npcs_here if _is_hostile(n)]:
                    npcs_here.remove(npc)
                    self._forget_combatant(npc)
            events_here = getattr(tile, "events_here", None)
            if isinstance(events_here, list):
                for event in [e for e in events_here if isinstance(e, NPCSpawnerEvent)]:
                    event.has_run = True
                    events_here.remove(event)

    def _forget_combatant(self, npc):
        """Drop ``npc`` from Jean's enemy bookkeeping if it is there.

        Combat is expected to be over when this event fires -- tile events
        are only evaluated outside a fight (``GameService.trigger_tile_events``
        and ``Universe.game_tick_events`` both gate on ``player.in_combat``) and the
        API clears ``combat_list`` at fight end -- so this is belt-and-braces;
        it exists so a swept NPC can never linger as a phantom enemy. It
        leaves a live fight's bookkeeping to the combat engine, and is
        guarded rather than assumed: the story tests hand the event a Mock
        player.
        """
        if getattr(self.player, "in_combat", False):
            return
        combat_list = getattr(self.player, "combat_list", None)
        if isinstance(combat_list, list) and npc in combat_list:
            combat_list.remove(npc)
        proximity = getattr(self.player, "combat_proximity", None)
        if isinstance(proximity, dict):
            proximity.pop(npc, None)


def _prose_of(text):
    """``text`` as its words alone. ``TileDescription`` re-wraps and colours
    what it is given, so the text it stores never equals its source prose."""
    return " ".join(ANSI_ESCAPE_RE.sub("", str(text)).split())


#: The cleansed prose, indexed by its words alone, for the on-load repair:
#: what a pre-#572 save left on a tile as a nameless object is matched here
#: and folded back into the tile's own description. Built once from the
#: constants above, which never change, rather than per load.
_CLEANSED_BY_PROSE = types.MappingProxyType({
    _prose_of(text): text
    for text in (CLEANSED_ARENA_DESCRIPTION, *CLEANSED_CHANNEL_DESCRIPTIONS.values())
})


def fold_legacy_cleansed_descriptions(player):
    """Repair the pools tiles of a save taken after King Slime fell under the
    pre-#572 code; returns how many objects it folded.

    That code ADDED each cleansed description as a nameless
    ``TileDescription`` object instead of overwriting the tile's own text, so
    such a save renders the corrupted and cleansed prose together (#573)
    beside an interactable with no name (#572). ``src.story.repair_loaded_save``
    runs this on every load: each object carrying cleansed prose comes off
    its tile, and that prose becomes the tile's description -- what
    ``AfterDefeatingKingSlime`` writes now. Matched on the prose itself, so an
    authored ``TileDescription`` -- whose prose is its own -- is left alone,
    and a repaired save has nothing left to fold. Anything the save restored
    in a shape this does not expect is skipped, never raised on.
    """
    if not gate_is_set(player, AfterDefeatingKingSlime.GATE_KEY):
        return 0
    pools = find_pools_map(player)
    if pools is None:
        return 0
    folded = 0
    for _coords, tile in _coordinate_tiles(pools):
        objects = getattr(tile, "objects_here", None)
        # Only a real list, since the loop below removes from it.
        if not isinstance(objects, list):
            continue
        for obj in list(objects):
            if not isinstance(obj, TileDescription) or not isinstance(obj.description, str):
                continue
            text = _CLEANSED_BY_PROSE.get(_prose_of(obj.description))
            if text is None:
                continue
            objects.remove(obj)
            tile.description = text
            folded += 1
    return folded


class Ch02GorranAtPools(Event):
    """
    Fires once when Jean first enters the Grondelith map, on the entry tile.

    Gorran led Jean this far but cannot follow into the corrupted interior —
    the corruption is too dense for stone to tolerate. He settles here, at
    ``THRESHOLD_COORDS``, and waits until King Slime is defeated;
    ``AfterDefeatingKingSlime`` brings him in and returns him to the party
    (#577).

    Attach to tile ``THRESHOLD_COORDS`` in grondelith-mineral-pools.json.
    """

    GATE_KEY = "gorran_at_pools"

    def __init__(
        self, player, tile, params=None, repeat=False, name="Ch02GorranAtPools"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )
        # Set description for API serialization
        self.description = (
            "Gorran stops at the threshold of the corrupted interior, unable to proceed. "
            "He settles beside the arch to wait for Jean's return."
        )

    def process(self):
        # The wait lasts until the King Slime falls, and only the aftermath
        # brings him back. With the boss already dead (a start past it, a
        # harness), seating him would strand him for good -- so the scene only
        # records itself.
        if not self.gate_is_set(AfterDefeatingKingSlime.GATE_KEY):
            self._seat_gorran_at_the_threshold()
            if not self.player.skip_dialog:
                self._narrate_the_wait()

        self.set_story_gate(self.GATE_KEY)
        complete_objective(self.player, OBJ_CH02_EXPLORE_GRONDIA)
        self.tile.remove_event(self.name)

    def _seat_gorran_at_the_threshold(self):
        """Stand Gorran on this tile — the threshold — and take him out of
        the party, to wait there while Jean goes in alone.

        ``combat_list_allies`` is the single source of truth for the status
        party, the battle allies and tile-following
        (``Player.recall_friends``), so leaving it is what keeps him out of
        the pools; ``AfterDefeatingKingSlime`` puts him back (#577).

        This tile, not the Atrium one further in: the scene seats him at the
        threshold he comes to "and no further", with Jean coming up beside
        him, so the fiction puts them both here (#613). He is *moved* rather
        than merely appended: the passage into the pools is a teleport,
        which does not recall the party, so he arrives still listed in the
        Grondia room he last followed Jean to.
        """
        # The party's instance first: it carries his level and state, and it
        # is the one that would otherwise follow Jean in.
        gorran = _find_gorran(_party(self.player)) or _find_gorran(self.tile.npcs_here)
        if gorran is None:
            # Nobody to seat: a session that reached the pools without him (a
            # config with no ``starting_party_members``, or a harness driving
            # the beat directly). Stand one up so the scene has its subject.
            gorran = self.tile.spawn_npc(GORRAN)
        else:
            _move_npc_to(gorran, self.tile)
        for stray in self._remove_every_gorran_from_the_party():
            if stray is not gorran:
                _unlist_npc(stray, *_rooms_of(stray))
        _wear_waiting_idle_line(gorran)

    def _remove_every_gorran_from_the_party(self):
        """Drop every Gorran from ``combat_list_allies``; returns those dropped.

        Every one, not merely the one just seated: a second instance leaves
        exactly the defect this closes — one Gorran sitting at the arch while
        another walks the pools behind Jean — and the list is what does the
        walking. The caller takes any second instance off the room it stood
        in, or it would be left listed there for good.
        """
        allies = _party(self.player)
        removed = [a for a in allies if _is_gorran(a)]
        for gorran in removed:
            allies.remove(gorran)
        return removed

    def _narrate_the_wait(self):
        """Gorran stops at the threshold, and Jean understands he will wait."""
        print_slow(
            "Gorran had come to the threshold and no further. He stood at the entrance "
            "to the atrium — that great vaulted space with its spring-fed pools — "
            "facing south, one hand resting against the stone arch."
        )
        time.sleep(1.5)
        print_slow(
            "Jean came up beside him. The air changed here. Even at the threshold he could "
            "feel it — a heaviness below the mineral scent, something sweet and wrong."
        )
        time.sleep(1)
        print_slow(
            "Gorran did not look at him. He tapped his own chest twice — slow, deliberate. "
            "Then he pointed south, toward the deeper passages. Then he drew his hand back."
        )
        time.sleep(1)
        print_slow(
            "He made a sound. Low and brief. The Golemite equivalent of: I know."
        )
        time.sleep(1)
        print_slow(
            "He lowered himself beside the arch — that slow, deliberate settling of stone "
            "finding its position. He would wait here. Jean understood that."
        )
        time.sleep(1.5)
        await_input()


class Ch02ArenaEntrance(Event):
    """
    Fires once when Jean first enters the arena tile (2,6) with King Slime present.

    Delivers the isolation/atmosphere narrative as Jean faces the King Slime.
    Sets its ``GATE_KEY`` story gate, ``arena_entered``.

    Attach to the arena tile in grondelith-mineral-pools.json.
    """

    GATE_KEY = "arena_entered"

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
        if self.retire_if_gate_set():
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
                "sickly green luminescence."
            )
            time.sleep(1)
            print_slow(
                "In the center of that corrupted expanse sat a single stone island. "
                "On it: a shape. Massive. Waiting."
            )
            time.sleep(1.5)
            print_slow(
                "The green in the water pulsed. The sound that came from it was not a voice — "
                "it was something older. Something hungry."
            )
            time.sleep(1)
            print_slow(
                "Jean stepped forward. The water began to churn."
            )
            time.sleep(1.5)

        self.set_story_gate(self.GATE_KEY)
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
        # Done once Votha has received the fragment
        if gate_is_set(player, AfterKingSlimeReturn.GATE_KEY):
            self.tile.remove_event(self.name)
            return

        # Only active after the King Slime is defeated
        if not gate_is_set(player, AfterDefeatingKingSlime.GATE_KEY):
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

        # Rate-limit so the reminder doesn't spam a corridor. The sentinel
        # is far enough below any real tick that the first call always passes.
        last_tick = int(
            story_gates(player).get(FRAGMENT_REMINDER_TICK_KEY, FRAGMENT_REMINDER_NEVER)
        )
        if player.universe.game_tick - last_tick < FRAGMENT_REMINDER_TICKS:
            return

        set_story_gate(
            player, FRAGMENT_REMINDER_TICK_KEY, str(player.universe.game_tick)
        )
        self._remind(player)

    def _remind(self, player):
        if not player.skip_dialog:
            print_slow("A rumble from behind — low, insistent.")
            time.sleep(1)
            print_slow(
                "Gorran stood at the entrance to the corridor, one hand braced against the arch. "
                "He was looking at the island."
            )
            time.sleep(1)
            print_slow("Jean followed his gaze.")
            time.sleep(1)
            print_slow(
                "The fragment was still there. He'd walked out without it."
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
    Memory flash triggered once the MineralFragment is in Jean's inventory --
    granted automatically by AfterDefeatingKingSlime (#378/#371), not picked
    up off the floor. The razor edge still cuts Jean's finger; the sharp pain
    unlocks a violent, fragmented memory of the explosion.
    """

    GATE_KEY = "king_slime_flash_fired"

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
            ("The fragment is already in his hand — the edge catches his finger.", 1.8),
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
                "And where something warm should have been, there in my arms —",
                2.0,
                {"speaker": "Jean", "emotion": "concerned", "thought": True},
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
                "My bleeding finger was real. Everything else was gone.",
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
        if self.retire_if_gate_set():
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
            self.set_story_gate(self.GATE_KEY)


class AfterKingSlimeReturn(Event):
    """
    Fires once when Jean re-enters the Citadel after king_slime_defeated is set.
    Votha Krr accepts the mineral fragment and sends Jean toward the Echoing Caves.
    Seven stages: greeting, choice, consumption, acknowledgment, wisdom, farewell, cleanup.
    """

    GATE_KEY = "votha_krr_response_given"

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

    def _has_fragment(self):
        """True when Jean is carrying the MineralFragment."""
        return any(
            i.__class__.__name__ == "MineralFragment" for i in self.player.inventory
        )

    def check_conditions(self):
        slime_defeated = self.gate_is_set(AfterDefeatingKingSlime.GATE_KEY)
        already_given = self.gate_is_set(self.GATE_KEY)
        if not slime_defeated or already_given:
            return
        # Only start the hand-over once Jean actually has the fragment. If he
        # reaches the Citadel first, do nothing and leave the event attached so
        # it can fire on a later visit — never self-destruct here. See #371.
        if self._has_fragment():
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        if not hasattr(self, "_stage"):
            self._stage = 1

        # Defensive: if the fragment is somehow absent at the first stage, keep
        # the event alive (needs_input=True) rather than letting the one-time
        # removal in pass_conditions_to_process permanently drop it. See #371.
        if self._stage == 1 and not self._has_fragment():
            self.needs_input = True
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
            say("The pools are clean, little one. You have done well.", "Votha Krr", "happy")
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
                say("What is this thing, exactly?", "Jean", "curious")
                say(
                    "A memory, made stone. The mineral pools do not merely hold water — they "
                    "record what passes through them. Light, creature, time. This fragment "
                    "carries something very old. It is right that it returns to stone.",
                    "Votha Krr",
                    "neutral",
                )
                narrate("He took the fragment from Jean's hand.")
            else:  # c
                react("Votha Krr", "skeptical")
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
            react("Votha Krr", "concerned")
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
            self.set_story_gate(self.GATE_KEY)
            complete_objective(self.player, OBJ_CH02_VOTHA_KRR)
            self.tile.remove_event(self.name)
