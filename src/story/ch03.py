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
    Event fires once on first entry to (0,2) when arriving from the west (Grondia).
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
        self.pass_conditions_to_process()

    def process(self):
        if not self.player.skip_dialog:
            print("\n")
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
            print("\n")
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
            print_slow(colored("South. That's where this goes.", "cyan") + "\n")
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


class NomadCampArrivalEvent(Event):
    """
    Fires once on Jean's first entry to the NomadCamp tile (3,6) on the Eastern Descent.
    Introduces Mara, Devet, and Liss. Sets story gate 'nomad_camp_reached'.
    Gorran is present throughout but non-verbal.

    Delivery modes:
      API (stdout redirected to StringIO): 5 staged dialogs, each gated by a
        "Continue" choice button. process() is re-entered via process_event_input
        with user_input="continue" to advance the stage.
      Terminal (stdout is a real TTY): all beats run sequentially in one call
        with await_input() pauses between them.
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
        self.stage = 0
        self.input_type = "choice"
        self.input_prompt = ""
        self.input_options = [{"value": "continue", "label": "Continue"}]

    def check_conditions(self):
        story = getattr(getattr(self.player, "universe", None), "story", {})
        if story.get("nomad_camp_reached") == "1":
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            return
        self.pass_conditions_to_process()

    def process(self, user_input=None):
        import io
        import sys

        if self.player.skip_dialog:
            self.completed = True
            self.needs_input = False
            self._set_gate()
            return

        if isinstance(sys.stdout, io.StringIO):
            # API mode: one beat per dialog, advanced by the "Continue" choice.
            if user_input is not None:
                self.stage += 1
            self._render_api_stage(self.stage)
            if self.stage >= 4:
                self.needs_input = False
                self.completed = True
                self._set_gate()
            else:
                self.needs_input = True
        else:
            # Terminal mode: all beats in sequence with await_input() pauses.
            self._render_terminal()
            self.needs_input = False
            self.completed = True
            self._set_gate()

    # ------------------------------------------------------------------
    # API mode: one method per beat — called individually as stage advances
    # ------------------------------------------------------------------

    def _render_api_stage(self, stage):
        if stage == 0:
            print_slow(
                "Jean smelled the camp before he saw it — woodsmoke, dried meat, the particular "
                "warmth of a fire that had been maintained rather than lit. The sound of the river "
                "was constant behind it."
            )
            print_slow(
                "A woman was watching them from the camp's edge. She had clocked them while they were "
                "still fifty paces out — Jean was sure of it — but by the time he reached the fire "
                "ring she was already back to what she had been doing, crouched over a pack, sorting "
                "something with methodical attention."
            )
            print_slow(
                "The camp was neat. Lean-tos of oiled canvas over light poles, angled correctly "
                "against the prevailing wind. A fire built in an established ring, its stones "
                "black with years of use. These were people who knew how to be somewhere without "
                "being of it."
            )
        elif stage == 1:
            print_slow(
                "The woman didn't look up. Her eyes found Jean for one flat second — taking in "
                "his gear, his bearing, the large stone figure standing slightly behind him — "
                "and returned to the pack."
            )
            dialogue("Mara", "Crossing west?", "cyan")
            print_slow("Not a greeting. A question with a purpose.")
            print_slow(
                "When Jean said yes, she named a number. Flat, fair, not open to discussion. "
                "She didn't look up when she said it. She was already back to the pack before "
                "the last word had settled."
            )
        elif stage == 2:
            print_slow(
                "An older man was tending the fire — unhurried, each movement economical in the "
                "way of someone who has done this ten thousand times. He gave Jean one look "
                "when Jean approached: the look of someone who had seen desperate people cross "
                "this river before, heading west, and knew most of them weren't running toward "
                "something."
            )
            print_slow(
                "He didn't offer this observation aloud. He picked up a bowl and filled it from "
                "the pot and held it out. It was not a question."
            )
            print_slow(
                "Gorran stood where Jean had left him, still, watching the fire without watching "
                "it. His presence had settled into the camp's edge the way large stones settle: "
                "without effort, without apology."
            )
        elif stage == 3:
            print_slow(
                "A girl — young, dark-haired, openly curious — was at the camp's far edge. She "
                "was not approaching Gorran. She was simply standing at a distance that was "
                "technically not approaching, watching him with the focused intensity of someone "
                "doing serious research."
            )
            print_slow(
                "She asked Mara something in a low voice. Something about Golemites. Whether "
                "they slept. Whether they ate. Whether the sound they made was a language or "
                "just a sound."
            )
            print_slow(
                "Gorran could almost certainly hear her. He gave no indication of this. He "
                "allowed her attention with the patient forbearance of a very old, very large "
                "thing being studied by a small one."
            )
        elif stage == 4:
            has_mace = any(
                item.__class__.__name__ == "Mace" for item in self.player.inventory
            )
            print_slow(
                "A while later — Jean was sitting with the bowl, Gorran nearby, the fire "
                "between them and the river — Mara spoke without looking up from what she "
                "was sorting."
            )
            if has_mace:
                print_slow(
                    "Her eyes tracked to Jean's mace for just a moment. Then back to her work."
                )
                dialogue("Mara", "That's religious kit.", "cyan")
            else:
                print_slow(
                    "Her eyes moved across Jean — his posture, his hands, the way his weight "
                    "sat — and returned to her work."
                )
                dialogue("Mara", "You were a man of the church.", "cyan")
            print_slow("Not a question.")
            dialogue("Jean", "It was.", "cyan")
            print_slow(
                "She didn't follow up. She filed it. The sorting continued."
            )

    # ------------------------------------------------------------------
    # Terminal mode: sequential flow, await_input() provides the pacing
    # ------------------------------------------------------------------

    def _render_terminal(self):
        print("\n")
        time.sleep(0.5)
        print_slow(
            "Jean smelled the camp before he saw it — woodsmoke, dried meat, the particular "
            "warmth of a fire that had been maintained rather than lit. The sound of the river "
            "was constant behind it."
        )
        time.sleep(1)
        print_slow(
            "A woman was watching them from the camp's edge. She had clocked them while they were "
            "still fifty paces out — Jean was sure of it — but by the time he reached the fire "
            "ring she was already back to what she had been doing, crouched over a pack, sorting "
            "something with methodical attention."
        )
        time.sleep(1)
        print_slow(
            "The camp was neat. Lean-tos of oiled canvas over light poles, angled correctly "
            "against the prevailing wind. A fire built in an established ring, its stones "
            "black with years of use. These were people who knew how to be somewhere without "
            "being of it."
        )
        time.sleep(1.5)
        await_input()

        print_slow(
            "The woman didn't look up. Her eyes found Jean for one flat second — taking in "
            "his gear, his bearing, the large stone figure standing slightly behind him — "
            "and returned to the pack."
        )
        time.sleep(1)
        dialogue("Mara", "Crossing west?", "cyan")
        time.sleep(0.5)
        print_slow("Not a greeting. A question with a purpose.")
        time.sleep(1)
        print_slow(
            "When Jean said yes, she named a number. Flat, fair, not open to discussion. "
            "She didn't look up when she said it. She was already back to the pack before "
            "the last word had settled."
        )
        time.sleep(1.5)
        await_input()

        print_slow(
            "An older man was tending the fire — unhurried, each movement economical in the "
            "way of someone who has done this ten thousand times. He gave Jean one look "
            "when Jean approached: the look of someone who had seen desperate people cross "
            "this river before, heading west, and knew most of them weren't running toward "
            "something."
        )
        time.sleep(1.5)
        print_slow(
            "He didn't offer this observation aloud. He picked up a bowl and filled it from "
            "the pot and held it out. It was not a question."
        )
        time.sleep(1)
        print_slow(
            "Gorran stood where Jean had left him, still, watching the fire without watching "
            "it. His presence had settled into the camp's edge the way large stones settle: "
            "without effort, without apology."
        )
        time.sleep(1.5)
        await_input()

        print_slow(
            "A girl — young, dark-haired, openly curious — was at the camp's far edge. She "
            "was not approaching Gorran. She was simply standing at a distance that was "
            "technically not approaching, watching him with the focused intensity of someone "
            "doing serious research."
        )
        time.sleep(1)
        print_slow(
            "She asked Mara something in a low voice. Something about Golemites. Whether "
            "they slept. Whether they ate. Whether the sound they made was a language or "
            "just a sound."
        )
        time.sleep(1)
        print_slow(
            "Gorran could almost certainly hear her. He gave no indication of this. He "
            "allowed her attention with the patient forbearance of a very old, very large "
            "thing being studied by a small one."
        )
        time.sleep(1.5)
        await_input()

        has_mace = any(
            item.__class__.__name__ == "Mace" for item in self.player.inventory
        )
        print_slow(
            "A while later — Jean was sitting with the bowl, Gorran nearby, the fire "
            "between them and the river — Mara spoke without looking up from what she "
            "was sorting."
        )
        time.sleep(1)
        if has_mace:
            print_slow(
                "Her eyes tracked to Jean's mace for just a moment. Then back to her work."
            )
            time.sleep(0.5)
            dialogue("Mara", "That's religious kit.", "cyan")
        else:
            print_slow(
                "Her eyes moved across Jean — his posture, his hands, the way his weight "
                "sat — and returned to her work."
            )
            time.sleep(0.5)
            dialogue("Mara", "You were a man of the church.", "cyan")
        time.sleep(0.5)
        print_slow("Not a question.")
        time.sleep(1)
        dialogue("Jean", "It was.", "cyan")
        time.sleep(1)
        print_slow(
            "She didn't follow up. She filed it. The sorting continued."
        )
        time.sleep(1.5)

    def _set_gate(self):
        story = getattr(getattr(self.player, "universe", None), "story", None)
        if story is not None:
            story["nomad_camp_reached"] = "1"
