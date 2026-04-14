"""
Chapter 03 events
"""

from src.events import Event
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

    def __init__(
        self, player, tile, params=None, repeat=False, name="GorranGesture"
    ):
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
            print_slow(
                "Jean stands at the edge of the road east.\n"
            )
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
            print_slow(
                colored("South. That's where this goes.", "cyan") + "\n"
            )
            time.sleep(0.5)

        # Move player west to (4, 2)
        from src.universe import Universe

        if self.tile and self.player:
            universe = getattr(self.player, "universe", None)
            if universe:
                # Move player west
                self.player.current_tile = universe.tiles.get(
                    (4, 2), self.player.current_tile
                )
