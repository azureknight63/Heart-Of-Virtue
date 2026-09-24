"""Exploration mixin for Player.

The terminal exploration surface (``search`` and ``view_map``) was removed
with the terminal-mode teardown. The web API owns these now:
``GameService.search`` handles searching, and the frontend renders the map
from the ``/world/explored`` route.

What remains here is prayer (issue #646), the out-of-combat cure for
Hollowed. ``GameService.pray`` adapts it and refuses it mid-fight.
"""

from src import functions
from src.narration import narrate


class PlayerExplorationMixin:
    """Out-of-combat actions the Player takes where he stands."""

    #: What a prayer that lifts Hollowed costs, as a fraction of max fatigue.
    #: A quarter: enough that praying straight into the next fight is a real
    #: trade (fatigue does not regenerate while exploring -- a won fight
    #: refills it -- so Jean carries the cost into that fight), cheap enough that it is always the right call once the
    #: fighting is done. Scales with max fatigue so it stays a quarter at any
    #: level. A prayer with nothing to lift costs nothing -- see ``pray``.
    PRAYER_FATIGUE_COST_PCT = 0.25

    #: The status family prayer lifts. Hollowed is the only apathy state
    #: (``src/states.py``); keyed on the family, as the Oath lock is
    #: (``src/moves/_utility.py``), so the two cannot disagree.
    _PRAYER_CURES_STATUSTYPE = "apathy"

    def prayer_fatigue_cost(self):
        """Fatigue a prayer that lifts Hollowed costs right now (at least 1)."""
        return max(1, int(self.maxfatigue * self.PRAYER_FATIGUE_COST_PCT))

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
        afflictions = [
            s for s in self.states
            if getattr(s, "statustype", "") == self._PRAYER_CURES_STATUSTYPE
        ]
        if not afflictions:
            narrate(
                f"{self.name} folds his hands and says the old words under his "
                "breath. They come easily, out of long habit."
            )
            narrate("Nothing in him needs mending just now. He says amen and rises.")
            return {"prayed": True, "cleared": [], "fatigue_cost": 0, "refusal": None}

        cost = self.prayer_fatigue_cost()
        if self.fatigue < cost:
            return {
                "prayed": False,
                "cleared": [],
                "fatigue_cost": 0,
                "refusal": (
                    f"{self.name} is too spent to kneel and hold still that long. "
                    f"Prayer needs {cost} fatigue; he has {int(self.fatigue)}."
                ),
            }

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
        self.states = [s for s in self.states if s not in afflictions]
        functions.refresh_stat_bonuses(self)
        for state in afflictions:
            state.on_removal(self)
        narrate(f"The prayer cost {self.name} {cost} fatigue.")
        return {
            "prayed": True,
            "cleared": [getattr(s, "name", type(s).__name__) for s in afflictions],
            "fatigue_cost": cost,
            "refusal": None,
        }
