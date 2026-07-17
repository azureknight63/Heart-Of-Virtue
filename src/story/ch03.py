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
                "Then Gorran's boots scraped gravel behind him, and whatever the feeling was, "
                "it passed.\n"
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
