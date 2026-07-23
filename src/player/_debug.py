"""Debug mixin for Player — cheat commands.

Live debug surface is the ``/api/debug/*`` endpoints (TheAdjutant). Only
``supersaiyan`` remains here — it is invoked via ``session_manager``'s
god_mode path. The terminal-era commands (testevent, spawnobject,
print_story_vars, alter) were removed with the terminal-mode teardown.
"""


class PlayerDebugMixin:
    """Debug and testing commands for the Player (not for production use)."""

    def supersaiyan(self):
        """Makes player super strong! Debug only."""
        self.strength_base = 1000
        self.strength = 1000
        self.finesse_base = 1000
        self.finesse = 1000
        self.speed_base = 1000
        self.speed = 1000
        self.maxhp_base = 10000
        self.maxhp = 10000
        self.hp = 10000
        self.maxfatigue_base = 10000
        self.maxfatigue = 10000
        self.fatigue = 10000
