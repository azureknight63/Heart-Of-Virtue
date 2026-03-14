"""
Shared base class for all combat participants (Player, NPC).

Provides:
  - _init_resistances(): initialises resistance and status-resistance dicts from
    a single canonical definition so the values never drift between classes.
  - is_alive(), cycle_states(), get_equipped_items(): methods whose logic is
    identical across Player and NPC.

Usage (in each subclass __init__):
    self._init_resistances()
"""

# ── Canonical defaults ────────────────────────────────────────────────────────
# 1.0 = no effect, 0.5 = half damage/chance, 2.0 = double.
# Negative damage-resistance values mean the damage heals instead.
# Status-resistance values cannot be negative.

_DEFAULT_RESISTANCE = {
    "fire": 1.0,
    "ice": 1.0,
    "shock": 1.0,
    "earth": 1.0,
    "light": 1.0,
    "dark": 1.0,
    "piercing": 1.0,
    "slashing": 1.0,
    "crushing": 1.0,
    "spiritual": 1.0,
    "pure": 1.0,
}

_DEFAULT_STATUS_RESISTANCE = {
    "generic": 1.0,     # Default status type for all states
    "stun": 1.0,        # Unable to move; typically short duration
    "poison": 1.0,      # Drains HP every combat turn/game tick; persists
    "enflamed": 1.0,    # Fire damage over time (matches State.statustype="enflamed")
    "sloth": 1.0,       # Drains Fatigue every combat turn
    "apathy": 1.0,      # Drains HEAT every combat turn
    "blind": 1.0,       # Misses physical attacks more frequently; persists
    "incoherence": 1.0, # Miracles fail more frequently; persists
    "mute": 1.0,        # Cannot use Miracles; persists
    "enraged": 1.0,     # Double physical damage given and taken
    "enchanted": 1.0,   # Double magical damage given and taken
    "ethereal": 1.0,    # Immune to physical; 3× magical damage; persists
    "berserk": 1.0,     # Auto-attack, 1.5× physical damage
    "slow": 1.0,        # All move times doubled
    "sleep": 1.0,       # Unable to move; removed upon physical damage
    "confusion": 1.0,   # Uses random moves on random targets; removed on physical damage
    "cursed": 1.0,      # Sets luck to 1; chance of random move/target; persists
    "stop": 1.0,        # Unable to move; not removed with damage
    "stone": 1.0,       # Unable to move; immune to damage; permanent death if it persists
    "frozen": 1.0,      # Unable to move; removed with Fire magic; permanent death if it persists
    "doom": 1.0,        # Death after n turns/ticks; persists; lifted only by purification
    "death": 1.0,
    "disoriented": 1.0, # Reduced finesse and protection
}


class Combatant:
    """Base class for Player and NPC.  Do not instantiate directly."""

    def _init_resistances(self):
        """Initialise resistance and status-resistance dicts to canonical defaults."""
        self.resistance = dict(_DEFAULT_RESISTANCE)
        self.resistance_base = dict(_DEFAULT_RESISTANCE)
        self.status_resistance = dict(_DEFAULT_STATUS_RESISTANCE)
        self.status_resistance_base = dict(_DEFAULT_STATUS_RESISTANCE)

    # ── Shared methods ────────────────────────────────────────────────────────

    def is_alive(self):
        return self.hp > 0

    def cycle_states(self):
        """Process all active states.  Iterates over a snapshot so states that
        remove themselves during process() do not cause skipped entries."""
        for state in self.states[:]:
            state.process(self)

    def get_equipped_items(self):
        """Return all items in inventory that are currently equipped."""
        return [item for item in self.inventory if getattr(item, "isequipped", False)]

    def refresh_moves(self):
        """Return the subset of known_moves that are currently viable."""
        return [move for move in self.known_moves if move.viable()]

    def get_hp_pcnt(self):
        """Return remaining HP as a decimal fraction (0.0–1.0)."""
        return float(self.hp) / float(self.maxhp)
