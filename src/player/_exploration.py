"""Exploration mixin for Player.

The terminal exploration surface (``search`` and ``view_map``) was removed
with the terminal-mode teardown. The web API owns these now:
``GameService.search`` handles searching, and the frontend renders the map
from the ``/world/explored`` route.

What remains here is prayer (issue #646), the out-of-combat cure for
Hollowed. ``GameService.pray`` adapts it and refuses it mid-fight.
"""

from src import functions
import src.states as states
from src.narration import narrate


def _prayer_outcome(prayed, cleared=(), cost=0, refusal=None):
    """The dict ``Player.pray`` returns; see its docstring for the fields."""
    return {
        "prayed": prayed,
        "cleared": [getattr(s, "name", type(s).__name__) for s in cleared],
        "fatigue_cost": cost,
        "refusal": refusal,
    }


class PlayerExplorationMixin:
    """Out-of-combat actions the Player takes where he stands."""

    #: What a prayer that lifts Hollowed costs, as a fraction of max fatigue.
    #: A quarter: enough that praying straight into the next fight is a real
    #: trade (fatigue does not regenerate while exploring -- a won fight
    #: refills it -- so Jean carries the cost into that fight), cheap enough
    #: that it is always the right call once the fighting is done. Scales
    #: with max fatigue so it stays a quarter at any level. A prayer with
    #: nothing to lift costs nothing -- see ``pray``.
    PRAYER_FATIGUE_COST_PCT = 0.25

    #: The status family prayer lifts: ``states.APATHY_STATUSTYPE``, the one
    #: constant Hollowed declares and the Oath lock (``src/moves/_utility.py``)
    #: also reads.
    _PRAYER_CURES_STATUSTYPE = states.APATHY_STATUSTYPE

    def prayer_fatigue_cost(self):
        """Fatigue a prayer that lifts Hollowed costs right now (at least 1)."""
        return max(1, int(self.maxfatigue * self.PRAYER_FATIGUE_COST_PCT))

    def _prayer_cures(self, state):
        return getattr(state, "statustype", "") == self._PRAYER_CURES_STATUSTYPE

    def pray(self):
        """Kneel and pray. Lifts every apathy state (Hollowed) for fatigue.

        With nothing to lift, the prayer is free and changes nothing: it is
        habit and flavour, and charging for it would punish a player for
        finding the command. With too little fatigue to pay, it is refused
        and nothing changes.

        Out-of-combat only; the caller (``GameService.pray``) enforces that.

        :returns: ``{"prayed": bool, "cleared": [state names],
            "fatigue_cost": int, "refusal": str | None}``. ``refusal`` is the
            player-facing reason when ``prayed`` is False.
        """
        if not any(self._prayer_cures(s) for s in self.states):
            narrate(
                f"{self.name} folds his hands and says the old words under his "
                "breath. They come easily, out of long habit."
            )
            narrate("Nothing in him needs mending just now. He says amen and rises.")
            return _prayer_outcome(True)

        cost = self.prayer_fatigue_cost()
        if self.fatigue < cost:
            return _prayer_outcome(False, refusal=(
                f"{self.name} is too spent to kneel and hold still that long. "
                f"Prayer needs {cost} fatigue; he has {int(self.fatigue)}."
            ))

        narrate(
            f"{self.name} kneels where he stands and folds his hands. The words "
            "are the old ones. He has said them since he was a boy."
        )
        narrate("I can't feel anyone listening, he thinks. I say them anyway.")
        narrate(
            "Nothing answers. But the saying is something to hold, and he holds "
            "it until his knees ache."
        )
        self.fatigue -= cost
        cleared = functions.remove_states(self, self._prayer_cures)
        narrate(f"The prayer cost {self.name} {cost} fatigue.")
        return _prayer_outcome(True, cleared, cost)
