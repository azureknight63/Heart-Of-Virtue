"""
Chapter 03 events
"""

from src.events import Event, dialogue
from src.functions import print_slow, await_input
from neotermcolor import colored
import time


class GorranGestureEvent(Event):
    """
    Jean and Gorran exit Grondia through the Eastern Gate.
    Gorran pauses to place his palm against the sealed gate — a moment of farewell,
    or acknowledgment, or something Jean cannot name.
    This is Gorran's first step into the world beyond the stone city.
    Event fires once on first entry to (0,0) when arriving from the west (Grondia).
    """

    def __init__(self, player, tile, params=None, repeat=False, name="GorranGesture"):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        """Only fires if player's previous tile was Grondia (coming from the west)."""
        # Check if we're entering from Grondia
        previous_tile = getattr(self.player, "previous_tile", None)
        if previous_tile and "Grondia" in str(previous_tile.title):
            self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            print("\n")
            time.sleep(0.3)
            print_slow(
                "Gorran pauses at the gate as it seals. His palm rests flat against the stone — "
                "one breath, maybe two. Then he turns without a word and follows.\n"
            )
            time.sleep(1)
            print_slow("Jean does not ask him.\n")
            time.sleep(0.5)


class EasternRoadTurnbackEvent(Event):
    """
    Jean reaches the eastern road at (5,2) — the road that would lead to the Resolute Plains.
    The moment pulls at him: the open land, the escape, the direction that is not west.
    But Gorran's presence anchors him, and the moment passes.
    This event repeats: the player is always turned back west to (4,2).
    """

    def __init__(
        self, player, tile, params=None, repeat=True, name="EasternRoadTurnback"
    ):
        super().__init__(
            name=name, player=player, tile=tile, repeat=repeat, params=params
        )

    def check_conditions(self):
        """Fire on entry to the eastern road tile (5,2)."""
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            print("\n")
            time.sleep(0.3)
            print_slow("Jean stands at the edge of the road east.\n")
            time.sleep(1)
            print_slow(
                "The Plains are out there — open ground, light, the kind of distance you could "
                "just keep walking into. For a moment the road pulls at him in a way he doesn't examine.\n"
            )
            time.sleep(1.5)
            print_slow(
                "Then Gorran's boots scrape gravel behind him, and whatever the feeling was, "
                "it passes.\n"
            )
            time.sleep(1)
            print_slow(colored("South. That's where this goes.", "cyan") + "\n")
            time.sleep(0.5)

        # Move player west to (4, 2)
        if self.tile and self.player:
            universe = getattr(self.player, "universe", None)
            if universe:
                # Move player west
                self.player.current_tile = universe.tiles.get(
                    (4, 2), self.player.current_tile
                )


class NomadCampArrivalEvent(Event):
    """
    Fires once on Jean's first entry to the NomadCamp tile (2,5) on the Eastern Descent.
    Introduces Mara, Devet, and Liss. Sets story gate 'nomad_camp_reached'.
    Gorran is present throughout but non-verbal.
    Source: docs/lore/story/ch02-ch03-transition.md, Beat 4.
    """

    def __init__(
        self,
        player,
        tile,
        params=None,
        repeat=False,
        name="NomadCampArrival",
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
        self.pass_conditions_to_process()

    def process(self):
        if self.player.skip_dialog:
            self._set_gate()
            return

        print("\n")
        time.sleep(0.5)
        print_slow(
            "Jean smells the camp before he sees it — woodsmoke, dried meat, the particular "
            "warmth of a fire that has been maintained rather than lit. The sound of the river "
            "is constant behind it.",
            delay=0.03,
        )
        time.sleep(1)
        print_slow(
            "A woman is watching them from the camp's edge. She clocked them while they were "
            "still fifty paces out — Jean is sure of it — but by the time he reaches the fire "
            "ring she is already back to what she was doing, crouched over a pack, sorting "
            "something with methodical attention.",
            delay=0.03,
        )
        time.sleep(1)
        print_slow(
            "The camp is neat. Lean-tos of oiled canvas over light poles, angled correctly "
            "against the prevailing wind. A fire built in an established ring, its stones "
            "black with years of use. These are people who know how to be somewhere without "
            "being of it.",
            delay=0.03,
        )
        time.sleep(1.5)
        await_input()

        print_slow(
            "The woman doesn't look up. Her eyes find Jean for one flat second — taking in "
            "his gear, his bearing, the large stone figure standing slightly behind him — "
            "and return to the pack.",
            delay=0.03,
        )
        time.sleep(1)
        dialogue("Mara", "Crossing west?", "cyan")
        time.sleep(0.5)
        print_slow("Not a greeting. A question with a purpose.", delay=0.04)
        time.sleep(1)
        print_slow(
            "When Jean says yes, she names a number. Flat, fair, not open to discussion. "
            "She doesn't look up when she says it. She's already back to the pack before "
            "the last word has settled.",
            delay=0.03,
        )
        time.sleep(1.5)
        await_input()

        print_slow(
            "An older man is tending the fire — unhurried, each movement economical in the "
            "way of someone who has done this ten thousand times. He gives Jean one look "
            "when Jean approaches: the look of someone who has seen desperate people cross "
            "this river before, heading west, and knows most of them aren't running toward "
            "something.",
            delay=0.03,
        )
        time.sleep(1.5)
        print_slow(
            "He doesn't offer this observation aloud. He picks up a bowl and fills it from "
            "the pot and holds it out. It is not a question.",
            delay=0.04,
        )
        time.sleep(1)
        print_slow(
            "Gorran stands where Jean left him, still, watching the fire without watching "
            "it. His presence has settled into the camp's edge the way large stones settle: "
            "without effort, without apology.",
            delay=0.03,
        )
        time.sleep(1.5)
        await_input()

        print_slow(
            "A girl — young, dark-haired, openly curious — is at the camp's far edge. She "
            "is not approaching Gorran. She is simply standing at a distance that is "
            "technically not approaching, watching him with the focused intensity of someone "
            "doing serious research.",
            delay=0.03,
        )
        time.sleep(1)
        print_slow(
            "She asks Mara something in a low voice. Something about Golemites. Whether "
            "they sleep. Whether they eat. Whether the sound they make is a language or "
            "just a sound.",
            delay=0.03,
        )
        time.sleep(1)
        print_slow(
            "Gorran can almost certainly hear her. He gives no indication of this. He "
            "allows her attention with the patient forbearance of a very old, very large "
            "thing being studied by a small one.",
            delay=0.03,
        )
        time.sleep(1.5)
        await_input()

        # Equipment-conditional character-pinning exchange
        has_mace = any(
            item.__class__.__name__ == "Mace" for item in self.player.inventory
        )
        print_slow(
            "A while later — Jean is sitting with the bowl, Gorran nearby, the fire "
            "between them and the river — Mara speaks without looking up from what she "
            "is sorting.",
            delay=0.03,
        )
        time.sleep(1)
        if has_mace:
            print_slow(
                "Her eyes track to Jean's mace for just a moment. Then back to her work.",
                delay=0.04,
            )
            time.sleep(0.5)
            dialogue("Mara", "That's religious kit.", "cyan")
        else:
            print_slow(
                "Her eyes move across Jean — his posture, his hands, the way his weight "
                "sits — and return to her work.",
                delay=0.04,
            )
            time.sleep(0.5)
            dialogue("Mara", "You were a man of the church.", "cyan")
        time.sleep(0.5)
        print_slow("Not a question.", delay=0.05)
        time.sleep(1)
        dialogue("Jean", "It was.", "cyan")
        time.sleep(1)
        print_slow(
            "She doesn't follow up. She files it. The sorting continues.",
            delay=0.04,
        )
        time.sleep(1.5)

        self._set_gate()

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["nomad_camp_reached"] = "1"
