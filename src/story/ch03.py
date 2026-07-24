"""
Chapter 03 events
"""

from src.events import Event
from src.functions import print_slow
from src.narration import narrate, say, begin_conversation
import time

# Recurring conversation cast, to avoid retyping the same tuple at every stage.
_JEAN_MARA = [("Jean", "left", "neutral"), ("Mara", None, "neutral")]


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


class MaraFirstContactEvent(Event):
    """
    Fires once on Jean's first entry to RiversEdge (1,0) in the nomad camp sub-map.
    Mara clocked them fifty paces out, already back to her pack by the time Jean arrives.
    "Crossing west?" Names a price. Not a greeting.
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
            begin_conversation(_JEAN_MARA)
            say("Crossing west?", "Mara", "neutral")
            time.sleep(0.5)
            print_slow(
                "Not a greeting. A question with a purpose. When Jean said yes, she named a number. "
                "Flat, fair, not open to discussion. She was already back to the pack before the "
                "last word had settled."
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
    Devet tends the fire, wordless. Hands Jean a bowl — not a question. Gorran settles.
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
                "He didn't offer this observation aloud. He picked up a bowl and filled it from "
                "the pot and held it out. It was not a question."
            )
            time.sleep(1)
            print_slow(
                "Gorran stood where Jean had left him, still. His presence had settled into the "
                "camp's edge the way large stones settle: without effort, without apology."
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
    Liss is not-approaching Gorran at the camp's boundary. Direct, literal curiosity.
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
                "A girl was at the camp's far corner — young, dark-haired. Not approaching "
                "Gorran. Just standing at a distance that was technically not approaching, "
                "watching him with the focused intensity of someone conducting serious research."
            )
            time.sleep(1)
            # Gorran does not react to Liss (the prose is explicit: he gives no
            # indication of having heard her) — no reaction is authored here.
            begin_conversation(
                [
                    ("Jean", "left", "neutral"),
                    ("Gorran", None, "neutral"),
                    ("Liss", "right", "neutral"),
                ]
            )
            say(
                "Does the Golemite sleep? He doesn't look like he's sleeping. But I think he might be.",
                "Liss",
                "curious",
            )
            time.sleep(0.5)
            print_slow(
                "She said this to no one in particular. Or perhaps to Gorran directly — it was "
                "hard to say."
            )
            time.sleep(1)
            print_slow(
                "Gorran gave no indication of having heard this. He allowed her attention with "
                "the patient forbearance of a very old, very large thing being studied by a small one."
            )
            time.sleep(1)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["liss_gorran_done"] = "1"


class MaraObservationEvent(Event):
    """
    Fires once on Jean's re-entry to RiversEdge (1,0) after all three character
    introduction gates are set (mara_intro_done, devet_intro_done, liss_gorran_done).
    Mara makes her observation about Jean's background — religious kit or posture.
    Jean: "It was."
    Sets story gate 'nomad_camp_reached' (the main chapter completion gate).
    """

    def __init__(
        self, player, tile, params=None, repeat=False, name="MaraObservation"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("nomad_camp_reached") == "1":
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
                "between them and the river — Mara spoke without looking up from what she "
                "was sorting."
            )
            time.sleep(1)
            begin_conversation(_JEAN_MARA)
            if has_mace:
                print_slow(
                    "Her eyes tracked to Jean's mace for just a moment. Then back to her work."
                )
                time.sleep(0.5)
                say("That's religious kit.", "Mara", "neutral")
            else:
                print_slow(
                    "Her eyes moved across Jean — his posture, his hands, the way his weight "
                    "sat — and returned to her work."
                )
                time.sleep(0.5)
                say("You were a man of the church.", "Mara", "neutral")
            time.sleep(0.5)
            print_slow("Not a question.")
            time.sleep(1)
            say("It was.", "Jean", "neutral")
            time.sleep(1)
            print_slow("She didn't follow up. She filed it. The sorting continued.")
            time.sleep(1)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["nomad_camp_reached"] = "1"


class CampEntryGreetingEvent(Event):
    """
    Fires once on Jean's first entry to CampEntry (3,0) after the smell event fires.

    Jean and Gorran stand at the camp's east edge. A quiet beat of arrival — not
    triumphant, just present. Then from across the camp, Liss spots Gorran for the
    first time and scurries off. Jean watches her go.

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
            say("Not bad.", "Jean", "neutral", thought=True)
            time.sleep(0.5)
            print_slow(
                "Gorran made the low sound he sometimes made — not agreement exactly, "
                "but not disagreement either. Jean had stopped trying to classify it."
            )
            time.sleep(1)
            # Liss spots Gorran and scurries off
            print_slow(
                "From somewhere in the interior of the camp, a girl spotted them — "
                "dark-haired, young. Her eyes went wide. She made a sound — half-squeal, "
                "half-gasp — and scurried off toward the fire ring, hair flying."
            )
            time.sleep(1.5)
            print_slow(
                "Jean watched her go. He didn't know what to make of that. He filed it."
            )
            time.sleep(0.5)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["camp_entry_greeting_done"] = "1"


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
        """Always fires when the ferry landing is interacted with."""
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
            print_slow("\n[The full journey continues in the complete release.]\n")
            time.sleep(1)
        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["demo_ended"] = "1"


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

