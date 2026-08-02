"""
Chapter 03 events
"""

from src.events import Event
from src.functions import print_slow
from src.narration import narrate, say, begin_conversation, enter_op, exit_op
import time

# Recurring conversation cast, to avoid retyping the same tuple at every stage.
_JEAN_MARA = [("Jean", "left", "neutral"), ("Mara", None, "neutral")]
_JEAN_MARA_GORRAN = [
    ("Jean", "left", "neutral"),
    ("Mara", None, "neutral"),
    ("Gorran", None, "neutral"),
]
_JEAN_DEVET = [("Jean", "left", "neutral"), ("Devet", None, "neutral")]
_JEAN_GORRAN_LISS = [
    ("Jean", "left", "neutral"),
    ("Gorran", None, "neutral"),
    ("Liss", "right", "neutral"),
]


class GorranGestureEvent(Event):
    """
    Jean and Gorran exit Grondia through the Eastern Gate.
    Gorran pauses to place his palm against the sealed gate — a moment of farewell,
    or acknowledgment, or something Jean cannot name.
    This is Gorran's first step into the world beyond the stone city.
    Event fires once on first entry to the tile (any time the player arrives
    here from another tile), then sets gorran_gesture_done so it won't repeat.
    """

    def __init__(self, player, tile, params=None, repeat=False, name="GorranGesture"):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("gorran_gesture_done") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        prev = getattr(self.player, "previous_tile", None)
        if prev is None:
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow(
                "Gorran paused at the gate as it sealed. His palm rested flat against the stone — "
                "one breath, maybe two. Then he turned without a word and followed.\n"
            )
            time.sleep(1)
            print_slow("Jean did not ask him.\n")
            time.sleep(0.5)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["gorran_gesture_done"] = "1"


class EasternRoadTurnbackEvent(Event):
    """
    Jean reaches the eastern road — the road that would lead to the Resolute Plains.
    The moment pulls at him: the open land, the escape, the direction that is not west.
    But Gorran's presence anchors him, and the moment passes.
    This event repeats: the player is always turned back west to the preceding tile.
    """

    def __init__(
        self, player, tile, params=None, repeat=True, name="EasternRoadTurnback"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        """Fire on entry to the eastern road tile."""
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow("Jean stood at the edge of the road east.\n")
            time.sleep(1)
            print_slow(
                "The Plains were out there — open ground, light, the kind of distance you could "
                "just keep walking into. For a moment the road pulled at him in a way he didn't examine.\n"
            )
            time.sleep(1.5)
            print_slow(
                "Then the grind of Gorran's step on the gravel behind him, and whatever the "
                "feeling was, it passed.\n"
            )
            time.sleep(1)
            begin_conversation([("Jean", "left", "neutral")])
            say("South. That's where this goes.", "Jean", "neutral", thought=True)
            time.sleep(0.5)

        # Move player west to AddersShelf (5, 4) — tile immediately west of RoadEast
        if self.tile and self.player:
            universe = getattr(self.player, "universe", None)
            if universe:
                dest = universe.get_tile(5, 4)
                if dest:
                    self.player.location_x = 5
                    self.player.location_y = 4
                    self.player.current_room = dest


class NomadCampSmellEvent(Event):
    """
    Fires once on Jean's first entry to CampEntry (2,0) in the nomad camp sub-map.
    Sensory arrival — woodsmoke, warmth, river sound. No characters yet.
    Sets story gate 'nomad_camp_entered'.
    """

    def __init__(self, player, tile, params=None, repeat=False, name="NomadCampSmell"):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("nomad_camp_entered") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow(
                "Jean smelled the camp before he saw it — woodsmoke, dried meat, the particular "
                "warmth of a fire that had been maintained rather than lit."
            )
            time.sleep(1)
            print_slow("The sound of the river was constant behind it.")
            time.sleep(0.5)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["nomad_camp_entered"] = "1"


class CampEntryGreetingEvent(Event):
    """
    Fires once on Jean's first entry to CampEntry (3,0) after the smell event fires.

    Jean and Gorran stand at the camp's east edge. Jean notices aloud how thoroughly
    human this place is — tents built for people, laundry on a line, food cooking
    that's meant for human mouths. Gorran rumbles knowingly. Then Liss comes tearing
    around the fire ring, spots Jean, then Gorran, and flees in a fluster. Jean closes
    by asking Gorran what that was about, then names the actual goal: ask around the
    camp for a way across the river.

    Gate: 'nomad_camp_entered' must be '1' (smell event already fired).
    Sets: 'camp_entry_greeting_done'.
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="CampEntryGreeting"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("camp_entry_greeting_done") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        # Only fire after the smell event has run
        if story.get("nomad_camp_entered") != "1":
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow(
                "Jean stopped at the edge of the camp and let himself take it in — the fire, "
                "the packed earth, the smell of food. The river was close enough to hear."
            )
            time.sleep(1)
            print_slow("Gorran stood beside him. Said nothing. That was usual.")
            time.sleep(0.5)
            begin_conversation(
                [
                    ("Jean", "left", "neutral"),
                    ("Gorran", None, "neutral"),
                ]
            )
            say("Tents.", "Jean", "curious")
            time.sleep(0.4)
            say(
                "Real ones, too — sized for people. Not lean-tos, not burrows. "
                "Somebody built this to last.",
                "Jean",
                "curious",
            )
            time.sleep(0.6)
            say(
                "Clothes on a line, over there. Someone's doing laundry like the world "
                "hasn't ended.",
                "Jean",
                "neutral",
            )
            time.sleep(0.6)
            say(
                "And whatever's cooking on that fire smells like real food. For real, "
                "human mouths.",
                "Jean",
                "happy",
            )
            time.sleep(0.5)
            print_slow(
                "Gorran made the low sound he sometimes made — not agreement exactly, "
                "but not disagreement either. Jean had come to recognize it as a kind "
                "of knowing."
            )
            time.sleep(1)
            # Liss spots Jean, then Gorran, and flees in a fluster
            print_slow(
                "A girl came around the fire ring at a half-run, dark hair flying, and "
                "pulled up short when she saw Jean."
            )
            time.sleep(0.8)
            say(
                "Oh — hi! You're new. Are you—",
                "Liss",
                "surprised",
                enter=enter_op("Liss", side="right", emotion="surprised"),
            )
            time.sleep(0.5)
            print_slow("Her eyes slid past Jean's shoulder and found Gorran.")
            time.sleep(0.5)
            say(
                "Oh! OH. You're— he's— that's a real one, isn't it, that's—",
                "Liss",
                "surprised",
                leave=exit_op("Liss", transition="fade"),
            )
            time.sleep(0.5)
            print_slow(
                "Whatever she meant to say next dissolved into a half-squeal, half-gasp. "
                "She backed up two steps, spun, and bolted for the fire ring, hair "
                "streaming behind her."
            )
            time.sleep(1.5)
            print_slow("Jean watched her go, then glanced at Gorran.")
            time.sleep(0.5)
            say("What exactly was that about?", "Jean", "skeptical")
            time.sleep(0.7)
            print_slow(
                "Gorran didn't answer. Of course he didn't. Jean was fairly sure that "
                "not-answering was itself an answer."
            )
            time.sleep(1)
            say(
                "Well — we're not getting anywhere standing here. Let's ask around, "
                "see if anyone knows a way across that river.",
                "Jean",
                "neutral",
            )
            time.sleep(0.5)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["camp_entry_greeting_done"] = "1"


class MaraFirstContactEvent(Event):
    """
    Fires once on Jean's first entry to RiversEdge (1,0) in the nomad camp sub-map.
    Mara clocked them fifty paces out, already back to her pack by the time Jean arrives.

    Beat 1: "Crossing west?" — the fee, named flat, not negotiated.
    Beat 2: Her extracting gaze moves to Gorran for the first time; he answers with a
            rumble, not words (he is Stage 1 — spoken words only in hurt-combat
            contexts, so this stays narrated gesture/sound, never a spoken line).
    Beat 3: The crucifix — Jean notices it, notices himself noticing it, and looks
            away. Mara notices both and files them without comment. Nothing spoken.
    Beat 4: The guide-service offer, stated flat, not sold.
    Beat 5: She ties it off — the raft isn't ready; walk the camp, come back later.

    Sets story gate 'mara_intro_done'.
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="MaraFirstContact"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("mara_intro_done") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow(
                "A woman at the camp's western edge had clocked them while they were still fifty "
                "paces out — Jean was sure of it. By the time he reached her she was back to what "
                "she'd been doing: crouched over a pack, sorting something with methodical attention."
            )
            time.sleep(1)
            print_slow("She didn't look up.")
            time.sleep(0.5)

            # Beat 1 — the fee
            begin_conversation(_JEAN_MARA)
            say("Crossing west?", "Mara", "neutral")
            time.sleep(0.8)
            print_slow("Not a greeting. A question with a purpose.")
            time.sleep(0.5)
            say("That's the idea.", "Jean", "neutral")
            time.sleep(0.8)
            say(
                "Ten gold. Raft holds his weight fine — current's slow this time of year.",
                "Mara",
                "neutral",
            )
            time.sleep(0.8)
            say("You're sure that's fair?", "Jean", "skeptical")
            time.sleep(0.8)
            say(
                "It's not padded and I'm not in the mood for haggling. Take it or don't.",
                "Mara",
                "neutral",
            )
            time.sleep(1)

            # Beat 2 — Gorran, appraised aloud; he answers with a rumble, not words
            print_slow("For the first time, her attention moved past Jean to Gorran.")
            time.sleep(0.8)
            begin_conversation(_JEAN_MARA_GORRAN)
            say(
                "Never had one this close. He's not going to take my raft apart, is he?",
                "Mara",
                "curious",
            )
            time.sleep(0.8)
            say("He'll be fine.", "Jean", "neutral")
            time.sleep(0.8)
            print_slow(
                "A low rumble moved up through Gorran's chest — not aggressive, more the sound "
                "of a rockslide pausing to consider participating in a conversation. "
                "The mooring post hummed faintly with it."
            )
            time.sleep(1)
            say(
                "That's either agreement or he's warming up to eat something. "
                "How can you tell the difference?",
                "Mara",
                "skeptical",
            )
            time.sleep(0.8)
            say("No idea. At least he only eats rocks. Small consolation. \n\nWe're headed to a place called the Wailing Badlands.", "Jean", "neutral")
            time.sleep(1)

            # Beat 3 — the crucifix, nothing spoken
            print_slow(
                "She turned back to her pack, and for a moment the cord at her throat caught the "
                "light — a small, tarnished crucifix, worn smooth with handling. Something in Jean "
                "snagged on it, a wrongness he couldn't place, and he looked away before he understood "
                "why. She noticed him notice it. She noticed him look away. She filed both in her mind without "
                "comment and went back to sorting."
            )
            time.sleep(1.5)

            # Beat 4 — the guide offer, stated flat
            begin_conversation(_JEAN_MARA)
            say(
                "I'm headed that way myself, next couple of days. Caves, not the Badlands — I don't "
                "go that far without a better reason than I've got right now. I'll guide you that far. Fee's normally "
                "separate from the crossing, but I'll cut it since it won't be out of my way.",
                "Mara",
                "neutral",
            )
            time.sleep(0.8)
            say("What takes you to the... Caves?", "Jean", "curious")
            time.sleep(0.8)
            print_slow(
                "She turns back to Jean, holding his gaze for an uncomfortable moment."
            )
            time.sleep(1.5)
            say(
                "Business. My business.",
                "Mara",
                "neutral",
            )
            time.sleep(0.8)
            say("Alright, fair enough. I accept your terms.", "Jean", "neutral")
            time.sleep(1)

            # Beat 5 — tied off; sends Jean around the camp
            say(
                "Not yet, though. Raft needs restrung and I want another hour of light before I "
                "commit anyone's weight to it. Walk the camp, eat something. Come back when the "
                "sun's lower and I'll have it sorted.",
                "Mara",
                "neutral",
            )
            time.sleep(0.8)
            print_slow(
                "She was already back to the pack before the last word had settled."
            )
            time.sleep(1)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["mara_intro_done"] = "1"


class DevetIntroEvent(Event):
    """
    Fires once on Jean's first entry to FireRing (1,1) in the nomad camp sub-map.
    Devet tends the fire. He offers food wordlessly — not a question — then two
    short, dry exchanges give the player a sense of him without breaking his
    terseness: he deflects a direct question about himself and declines a
    compliment in the same minimal register. He offers no commentary on Jean
    ("heading west" look) or on Gorran — that restraint is the character, so it
    stays narrated rather than spoken. Gorran settles at the camp's edge.
    Sets story gate 'devet_intro_done'.
    """

    def __init__(self, player, tile, params=None, repeat=False, name="DevetIntro"):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("devet_intro_done") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow(
                "An older man was tending the fire — unhurried, each movement economical in the "
                "way of someone who has done this ten thousand times. He gave Jean one look when "
                "Jean approached: the look of someone who had seen desperate people cross this "
                "river before, heading west, and knew most of them weren't running toward something."
            )
            time.sleep(1.5)
            print_slow(
                "He didn't offer this observation aloud. His eyes moved to Gorran once — a brief, "
                "unhurried assessment, the same one he'd have given an unfamiliar dog — and returned "
                "to the pot. If a Golemite unsettled him, nothing in his face admitted it."
            )
            time.sleep(1)

            begin_conversation(_JEAN_DEVET)
            say("Eat.", "Devet", "neutral")
            time.sleep(0.5)
            print_slow(
                "He filled a bowl from the pot and held it out. It was not a question. "
                "Root vegetables, some kind of meat, with an enthralling aroma making Jean's stomach growl. "
                "He began to realize how long it had been since he'd eaten a warm meal. "
                "More accurately, he wondered just how long that really had been."
            )
            time.sleep(0.8)
            say("Thank you.", "Jean", "neutral")
            time.sleep(0.5)
            print_slow(
                "The old man had already turned back to the fire. The thanks hadn't needed an answer."
            )
            time.sleep(1)

            say("How long have you been doing this?", "Jean", "curious")
            time.sleep(0.8)
            say(
                "Long enough I don't remember what I was doing before.",
                "Devet",
                "neutral",
            )
            time.sleep(1)
            print_slow(
                "A quiet pause settled in between the two for a moment."
            )
            say("Probably something less useful.", "Devet", "neutral")
            time.sleep(0.5)
            print_slow("It took Jean a second to realize that had been a joke. He lifted the bowl and took a careful sip.")
            time.sleep(1)

            say("It's good.", "Jean", "happy")
            time.sleep(0.8)
            say("It's food.", "Devet", "neutral")
            time.sleep(1)

            print_slow(
                "Gorran stood where Jean had left him, still. Gradually, he rumbled and sat on the ground while Jean ate."
                "His presence had settled into the campfire's edge the way large stones settle: without effort, without apology."
            )
            time.sleep(1)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["devet_intro_done"] = "1"


class LissObservingEvent(Event):
    """
    Fires once on Jean's first entry to CampFarEdge (2,1) in the nomad camp sub-map.
    Liss is not-approaching Gorran at the camp's boundary — three rapid-fire bursts
    of unfiltered curiosity, each met with total Gorran stillness (the comedic
    engine here: her chatter against his total silence — he is Stage 1 language
    and does not speak outside hurt-combat, so his half of every "exchange" stays
    narrated gesture/non-reaction, never a line). Jean gets two short, dry asides.
    Closes on the small, wordless moment where she gives up asking and just sits
    near him — the seed of the friendship, not its arrival. Jean's reaction stays
    oblique: an unexamined smile, then an unnamed ache in his chest — grief
    surfacing beneath his notice rather than a stated observation that the moment
    was warm.
    Sets story gate 'liss_gorran_done'.
    """

    def __init__(self, player, tile, params=None, repeat=False, name="LissObserving"):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("liss_gorran_done") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow(
                "A girl was at the camp's far corner — young, dark-haired, turning a stone over "
                "in one hand out of habit. Not approaching Gorran. Orbiting him instead, in loose, "
                "unhurried circles, hands clasped behind her back like someone sizing up a fact "
                "she wasn't sure she believed yet."
            )
            time.sleep(1)

            # Gorran does not react to Liss anywhere in this scene — the prose is
            # explicit that he gives no indication of having heard her.
            begin_conversation(_JEAN_GORRAN_LISS)

            # Burst 1 — sleep
            print_slow(
                "She spun a half-turn on one heel, already talking before she'd fully stopped."
            )
            time.sleep(0.6)
            say(
                "Does he sleep? He doesn't look like he's sleeping, but maybe that's just what "
                "it looks like when he does — do Golemites even close their eyes, or— "
                "sorry. Does he sleep? Yes or no.",
                "Liss",
                "curious",
            )
            time.sleep(1)
            print_slow(
                "Gorran didn't answer. Didn't move. His stillness could have meant anything, "
                "including no, including yes, including that he'd heard the question and elected "
                "not to dignify it with the effort of a response."
            )
            time.sleep(1)
            print_slow(
                "She reached out and poked his shin once, experimentally — the way you'd poke "
                "a small animal to check whether it was asleep or just very good at pretending."
            )
            time.sleep(0.8)
            say("I've been trying to figure that out for weeks.", "Jean", "neutral")
            time.sleep(1)

            # Burst 2 — the stone, held up for comparison
            print_slow(
                "She held the stone from her hand up next to his forearm, comparing the color, "
                "tilting her head like a jeweler. Then she crouched and tapped it twice against "
                "the toe of his foot — stone on stone, a small testing sound, like she expected "
                "a different note back."
            )
            time.sleep(1)
            say(
                "Does it hurt? When you crack, I mean. Not that you look cracked. You don't. I "
                "just mean — a rock cracks and it doesn't feel it, because it's a rock, but "
                "you're not just a rock, so—",
                "Liss",
                "curious",
            )
            time.sleep(1)
            print_slow(
                "Gorran's eyes moved once — not to her, to the stone in her hand — the way "
                "something very old regards something very new. Then away again. Nothing else."
            )
            time.sleep(1)
            say("Okay. Well, that was more than just standing there. I guess you don't talk much.", "Liss", "happy")
            time.sleep(1)

            # Burst 3 — cold and bone (canonical exchange)
            print_slow(
                "A new thought visibly arrived. She clapped once, delighted with herself, and "
                "bounced up onto her toes, hopping a half-step closer without seeming to notice "
                "she'd moved."
            )
            time.sleep(0.8)
            say(
                "You're made of stone — does the cold feel different because of that? Devet "
                "says it settles in his bones, and I thought, if you're basically already bone, "
                "does it feel like anything, or is it just cold the same as everything else?",
                "Liss",
                "curious",
            )
            time.sleep(1)
            say("Oh, but not bone. STONE. Still hard and cold. But maybe different?", "Liss", "happy")
            time.sleep(1)
            print_slow("Gorran regarded the nearby river, watching the current weave between boulders.")
            time.sleep(0.8)
            say("You don't have to answer.", "Liss", "neutral")
            time.sleep(0.8)
            print_slow("He didn't.")
            time.sleep(0.8)
            say("I'll probably ask again sometime.", "Liss", "neutral")
            time.sleep(1)
            say("He's not going to answer that one either.", "Jean", "neutral")
            time.sleep(0.8)
            say("I know. I'll keep asking anyway. Mara says I ask too much, but I think it's fine.", "Liss", "happy")
            time.sleep(1)

            # The seed, not the arrival
            print_slow(
                "Turning to say something else to Jean, she caught her own foot on nothing at "
                "all and overbalanced — one arm windmilling before she caught herself on the "
                "nearest solid thing, which happened to be Gorran's leg. He didn't shift his "
                "weight. He didn't need to. She held on a moment longer than the stumble required, "
                "then let go, a little sheepish, and didn't try to explain it."
            )
            time.sleep(1.2)
            print_slow(
                "Something in her ran out of questions before it ran out of curiosity. She "
                "stopped talking, came a few steps closer than she'd allowed herself before, "
                "and sat, watching the river instead of him."
            )
            time.sleep(1.5)
            print_slow(
                "Gorran allowed this without acknowledging it. Neither of them said anything "
                "else."
            )
            time.sleep(1.2)
            print_slow(
                "Jean watched them — the girl and the old stone thing, both passively mesmerized by the "
                "undulating water — and found he was smiling before he'd decided to."
            )
            time.sleep(1.2)
            say("...", "Jean", "concerned")
            print_slow(
                "Then something moved under it, low and sudden — a tightness in his chest that "
                "had no name and offered no explanation for itself. It was gone as quickly as it "
                "came. He didn't chase it. He turned back to the fire."
            )
            time.sleep(1)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["liss_gorran_done"] = "1"


class IronAndOathIntroEvent(Event):
    """
    Fires once on Jean's first entry to Tradepost (4,3) in the nomad camp sub-map.

    Beat 1: Arrival & First Impressions — Kaelen and Vespera welcome Jean.
    Beat 2: Kaelen's Smithing Eye & Gorran's Presence — Kaelen examines Gorran's granite armor.
    Beat 3: Vespera's Grounding & Sales Pitch — Vespera pivots to practical armor/weapon needs.
    Beat 4: Liss's Stalking & Vespera's Somber Stillness — Liss crashes into the weapon rack and flees;
            Vespera experiences a moment of quiet grief/stillness, Kaelen's warm hand at her back.
    Beat 5: Transition to Commerce — Invitation to trade.

    Sets story gate 'iron_and_oath_intro_done'.
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="IronAndOathIntro"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("iron_and_oath_intro_done") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow(
                "The metallic scraping of a hand file against steel and the sharp snap of waxed thread "
                "echoed beneath the canvas awning. A man in an oil-cured leather apron was sharpening a pommel "
                "while a sharp-eyed woman beside him inspected the buckle alignment of a leather cuirass."
            )
            time.sleep(1)

            begin_conversation(
                [
                    ("Jean", "left", "neutral"),
                    ("Gorran", "left", "neutral"),
                    ("Kaelen", "right", "curious"),
                    ("Vespera", "right", "happy"),
                ]
            )

            # Beat 1 — First Impressions
            say(
                "Welcome to Iron & Oath, traveler. If you're looking for iron that holds or leather "
                "that doesn't split in the river damp, you're at the right stall.",
                "Vespera",
                "happy",
            )
            time.sleep(0.8)
            say("By the forge... That's a Golemite.", "Kaelen", "curious")
            time.sleep(0.8)

            # Beat 2 — Kaelen's Smithing Eye & Gorran's Presence
            say(
                "Look at the grain along his shoulders, Vespera. That's natural granite weave. "
                "You couldn't forge plates with that kind of density if you had a bellows the size of a barn.",
                "Kaelen",
                "curious",
            )
            time.sleep(1)
            print_slow(
                "A low, subsonic vibration rolled through the gravel underfoot as Gorran shifted his weight. "
                "The tools hanging from the counter rack chimed softly against one another."
            )
            time.sleep(1)
            say("Gorran travels with me. He isn't armor.", "Jean", "neutral")
            time.sleep(0.8)
            say(
                "No offense intended, friend! A smith sees good structure, he can't help but admire it.",
                "Kaelen",
                "happy",
            )
            time.sleep(1)

            # Beat 3 — Vespera's Grounding & Sales Pitch
            say(
                "Pay him no mind, Jean. He'd lecture the river on its current if it stood still long enough. "
                "But he's right about one thing — the road west isn't kind to poor steel.",
                "Vespera",
                "skeptical",
            )
            time.sleep(0.8)
            say(
                "You've come down from Grondia, heading across the water. The Badlands will chew through "
                "cheap straps and dull a soft edge in three days.",
                "Vespera",
                "concerned",
            )
            time.sleep(0.8)
            say(
                "Everything on this rack is tempered for long travel. Light enough not to exhaust your arm "
                "on a ten-mile march, hard enough to take a beating.",
                "Kaelen",
                "neutral",
            )
            time.sleep(1)

            # Beat 4 — Liss's Stalking & Vespera's Somber Stillness
            print_slow(
                "At the side of the stall, nine-year-old Liss was creeping behind a stack of crates, "
                "staring wide-eyed at Gorran in intense, unblinking research."
            )
            time.sleep(1)
            print_slow(
                "Trying to sneak closer for a better view, her foot caught a support cord. "
                "She crashed directly into a wooden rack of practice spears with a loud, wooden clatter!"
            )
            time.sleep(1)

            begin_conversation(
                [
                    ("Jean", "left", "neutral"),
                    ("Gorran", "left", "neutral"),
                    ("Kaelen", "right", "curious"),
                    ("Vespera", "right", "concerned"),
                    ("Liss", "right", "surprised"),
                ]
            )

            say("Eek!", "Liss", "surprised")
            time.sleep(0.5)
            print_slow(
                "She scrambled up instantly, dark hair flying, and fled into the camp interior without looking back."
            )
            time.sleep(1)

            begin_conversation(
                [
                    ("Jean", "left", "neutral"),
                    ("Gorran", "left", "neutral"),
                    ("Kaelen", "right", "curious"),
                    ("Vespera", "right", "sad"),
                ]
            )

            say(
                "That girl's got more nerve than sense. One of these days she's going to try to take a chisel "
                "to a Golemite just to see what's inside.",
                "Kaelen",
                "happy",
            )
            time.sleep(1)
            print_slow(
                "A sudden, somber stillness settled over Vespera. Her smile faded into a quiet, distant stare "
                "as she watched the spot where Liss had vanished. Her fingers gently traced the leather spine "
                "of her ledger."
            )
            time.sleep(1.5)
            print_slow(
                "Kaelen noticed her shift instantly. He set the fallen spear down, stepped over, and quietly "
                "rested a warm, soot-stained hand on the small of her back."
            )
            time.sleep(1)
            say("Vespera...", "Kaelen", "concerned")
            time.sleep(0.8)
            say("I'm alright, love.", "Vespera", "sad")
            time.sleep(1)
            say(
                "Right then. As I was saying — Vespera fits the harness, I balance the blade. "
                "Nobody leaves our counter with gear that fails 'em.",
                "Kaelen",
                "neutral",
            )
            time.sleep(1)

            # Beat 5 — Transition to Commerce
            say(
                "Take your time, Jean. Check the rivets, test the balance. We buy fair, we sell honest, "
                "and if you need anything repaired before crossing, Kaelen's got the hearth lit.",
                "Vespera",
                "happy",
            )
            time.sleep(1)

        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["iron_and_oath_intro_done"] = "1"


class AnvilIntroEvent(Event):
    """
    Fires the first time Jean interacts with Anvil (talk or pet) at the
    Tradepost, provided he's already met Kaelen & Vespera
    (iron_and_oath_intro_done). Anvil.talk()/pet() set the trigger flag
    'anvil_conversation_ready' on first use; this event picks it up via the
    normal post-action tile-event check.

    Jean registers the "boulder" at the stall's edge as a living creature.
    Kaelen and Vespera introduce Anvil and explain how a Shell-back survives
    the river route alone — Kaelen technical and proud, Vespera grounding
    him, then unguarded for a moment describing Anvil's care routine with a
    warmth that outruns simple animal husbandry. Jean notices it, privately,
    without either of them naming it.

    Sets story gate 'anvil_conversation_done' so it never repeats.
    """

    def __init__(self, player, tile, params=None, repeat=False, name="AnvilIntro"):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("anvil_conversation_done") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        if story.get("iron_and_oath_intro_done") != "1":
            return
        if story.get("anvil_conversation_ready") != "1":
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow(
                "Jean's attention snagged on the far corner of the stall — a shape "
                "he'd taken for a heap of stacked stone since he'd arrived. It shifted, "
                "fractionally, and resolved into something with a shell."
            )
            time.sleep(1)

            begin_conversation(
                [
                    ("Jean", "left", "surprised"),
                    ("Gorran", "left", "neutral"),
                    ("Kaelen", "right", "curious"),
                    ("Vespera", "right", "happy"),
                ]
            )

            say("That's... alive?", "Jean", "surprised")
            time.sleep(0.8)
            say(
                "That's Anvil. Iron & Oath doesn't move an inch without him — every "
                "rack, every crate, the hearth stones themselves, all of it rides on "
                "his back when we relocate.",
                "Vespera",
                "happy",
            )
            time.sleep(1)
            say(
                "Named him myself. Seemed fitting — the one thing in the stall that "
                "doesn't move for anybody.",
                "Kaelen",
                "happy",
            )
            time.sleep(0.5)
            say(
                "Turned out he meant it rather more literally than I did. I've never "
                "won an argument with that animal.",
                "Kaelen",
                "curious",
            )
            time.sleep(1)

            print_slow(
                "A faint hiss vented from somewhere inside the shell — not alarm, "
                "just acknowledgment — and the thick sensory stalks tracked Jean's "
                "hands for a long moment before losing interest."
            )
            time.sleep(1)

            say(
                "How does something that slow keep pace with a camp that has to "
                "tear down and move three, four times a year?",
                "Jean",
                "curious",
            )
            time.sleep(0.8)
            say(
                "Ah — now that's the interesting part. He doesn't keep pace. We send "
                "him off alone, a day ahead, loaded with everything heavy. No rest "
                "stops, no feeding stops — he grazes as he walks and simply doesn't "
                "stop moving.",
                "Kaelen",
                "curious",
            )
            time.sleep(0.8)
            say(
                "And the river doesn't slow him either. Seals that hatch of his shut "
                "tight as a strongbox and just walks the bottom of the ford, submerged, "
                "calm as you like. Every other pack animal on this route dreads that "
                "crossing. Anvil's the only one who's never once minded it.",
                "Kaelen",
                "curious",
            )
            time.sleep(1)
            say(
                "Kaelen. He asked how the animal keeps up, not for the full natural "
                "history.",
                "Vespera",
                "skeptical",
            )
            time.sleep(0.5)
            say("I'm answering the question!", "Kaelen", "happy")
            time.sleep(1)

            say(
                "He's not wrong, though. Clean his plates, check the hatch seal, feed "
                "him — same order, every time, since I first took over his care. Took "
                "the better part of a year before he'd settle for me the way he "
                "settles now.",
                "Vespera",
                "neutral",
            )
            time.sleep(1.2)

            say(
                "There was something in the way she said it — not the flat, practical "
                "tone she used for ledgers and armor fittings, but something rounder, "
                "more careful. The tone of someone describing a routine that mattered "
                "more than the routine itself.",
                "Jean",
                "neutral",
                thought=True,
            )
            time.sleep(1)

            print_slow(
                "As if in answer, the great shape shifted its weight and settled "
                "flush against the ground beside her, foot easing down the way it "
                "never had for anyone else Jean had watched him tolerate."
            )
            time.sleep(1)

            say(
                "Don't let him hear you say that — he'll expect a written apology "
                "before he moves another inch for me.",
                "Kaelen",
                "happy",
            )
            time.sleep(0.8)
            say(
                "He's spoiled well past reason and I take full responsibility for it. "
                "Now — did you come here to admire my livestock, or were you after "
                "something for the road?",
                "Vespera",
                "happy",
            )
            time.sleep(1)

        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["anvil_conversation_done"] = "1"


class MaraObservationEvent(Event):
    """
    Fires once on Jean's re-entry to RiversEdge (1,0) after all three character
    introduction gates are set (mara_intro_done, devet_intro_done, liss_gorran_done).
    Mara makes her observation about Jean's background — religious kit or posture.
    Sets story gate 'nomad_ferry_ready' (the main chapter completion gate).
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="MaraObservation"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("nomad_ferry_ready") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        # Wait until all three character beats are complete
        if not (
            story.get("mara_intro_done") == "1"
            and story.get("devet_intro_done") == "1"
            and story.get("liss_gorran_done") == "1"
        ):
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            # Match any bludgeon/mace (RustedIronMace, Mace, …) — they are
            # sibling Weapon subclasses sharing subtype "Bludgeon", so an exact
            # class-name check missed Jean's starting RustedIronMace.
            has_mace = any(
                getattr(item, "subtype", None) == "Bludgeon"
                for item in self.player.inventory
            )
            print_slow(
                "A while later — Jean was sitting with the bowl, Gorran nearby, the fire "
                "between them and the river — Mara looked up from what she was sorting."
            )
            time.sleep(1)
            begin_conversation(_JEAN_MARA)
            if has_mace:
                print_slow(
                    "Her eyes tracked to Jean's mace for just a moment. Then back to her work."
                )
                time.sleep(0.5)
                say("That's religious kit. You are - or were - a man of the church.", "Mara", "neutral")
            else:
                print_slow(
                    "Her eyes moved across Jean — his posture, his hands, the way his weight "
                    "sat — and returned to her work."
                )
                time.sleep(0.5)
                say("You are - or were - a man of the church.", "Mara", "neutral")
            time.sleep(0.5)
            print_slow("Not a question.")
            time.sleep(1)
            say("Not a priest, if that's what you mean.", "Jean", "neutral")
            time.sleep(1)
            print_slow(
                "Jean looked up at the sky with consternation. Why had he said that? "
                "He was trying to remember something just out of reach."
            )
            print_slow("Confused, Mara watched Jean for a moment. She filed the exchange. The sorting continued.")
            time.sleep(1)
            say(
                "When you're ready, head to the ferry landing and we'll be off. "
                "Don't wait too long - crossing in the dark is unpleasant for everyone.", "Mara", "neutral"
            )

        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["nomad_ferry_ready"] = "1"


class DemoEndEvent(Event):
    """
    Fires when Jean interacts with the Ferry Landing passageway (via events_before).

    Shows a narrated message that the crossing is visible but the demo ends here.
    Blocks the passageway interaction from completing — Jean is not teleported.
    Sets story gate 'demo_ended'.
    """

    def __init__(self, player, tile, params=None, repeat=True, name="DemoEnd"):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        """Only fires after the second conversation with Mara (ferry is ready.)"""
        story = getattr(getattr(self.player, "universe", None), "story", {})
        # Only fire after the ferry is ready
        if story.get("nomad_ferry_ready") != "1":
            return
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            narrate("\n")
            time.sleep(0.3)
            print_slow(
                "The ferry is ready. The crossing is short — you can see the far bank clearly."
            )
            time.sleep(1)
            print_slow("But beyond the river is where the demo ends.")
            time.sleep(0.5)
            print_slow("\n[The full journey continues in the complete release. You may continue exploring the area, but can go no further in the story.]\n")
            time.sleep(1)
            print_slow("\n[Be sure to submit feedback using the Feedback button at the top of the UI, next to 'Account'. Thank you for helping to make this game better! -Alex]\n")
            time.sleep(1)
