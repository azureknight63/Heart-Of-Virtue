"""
Shared base class for all combat participants (Player, NPC).

Provides:
  - _init_resistances(): initialises resistance and status-resistance dicts from
    a single canonical definition so the values never drift between classes.
  - is_alive(), cycle_states(), get_equipped_items(): methods whose logic is
    identical across Player and NPC.
  - exp_needed_for_level(): the single leveling curve shared by the Player and
    ally NPC progression.

Usage (in each subclass __init__):
    self._init_resistances()
"""


import math


def exp_needed_for_level(level, intelligence):
    """Exp required to advance from `level` to the next.

    Single source of the leveling curve — used by Player._level_up_api and
    AllyProgressionMixin.exp_to_level so ally pacing always matches Jean's.
    The per-level requirement is floored at 1 so very high intelligence
    (>= 165) can't zero it and spin exp-gain loops forever.
    """
    return int(level) * max(1, 165 - int(intelligence))


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
    "generic": 1.0,  # Default status type for all states
    "stun": 1.0,  # Unable to move; typically short duration
    "poison": 1.0,  # Drains HP every combat turn/game tick; persists
    "slimed": 1.0,  # Corrosive slime coating; drains HP and lowers finesse/protection; persists
    "enflamed": 1.0,  # Fire damage over time (matches State.statustype="enflamed")
    "sloth": 1.0,  # Drains Fatigue every combat turn
    "apathy": 1.0,  # Drains HEAT every combat turn
    "blind": 1.0,  # Misses physical attacks more frequently; persists
    "incoherence": 1.0,  # Miracles fail more frequently; persists
    "mute": 1.0,  # Cannot use Miracles; persists
    "enraged": 1.0,  # Double physical damage given and taken
    "enchanted": 1.0,  # Double magical damage given and taken
    "ethereal": 1.0,  # Immune to physical; 3× magical damage; persists
    "berserk": 1.0,  # Auto-attack, 1.5× physical damage
    "slow": 1.0,  # All move times doubled
    "sleep": 1.0,  # Unable to move; removed upon physical damage
    "confusion": 1.0,  # Uses random moves on random targets; removed on physical damage
    "cursed": 1.0,  # Sets luck to 1; chance of random move/target; persists
    "stop": 1.0,  # Unable to move; not removed with damage
    "stone": 1.0,  # Unable to move; immune to damage; permanent death if it persists
    "frozen": 1.0,  # Unable to move; removed with Fire magic; permanent death if it persists
    "doom": 1.0,  # Death after n turns/ticks; persists; lifted only by purification
    "death": 1.0,
    "disoriented": 1.0,  # Reduced finesse and protection
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

    def check_revive(self):
        """Consult revive-capable states (e.g. PhoenixRevive) before death is
        finalized. Returns True if a state revived this combatant, in which
        case the caller must not proceed with death handling."""
        for state in self.states[:]:
            try_revive = getattr(state, "try_revive", None)
            if try_revive and try_revive(self):
                return True
        return False

    def cycle_states(self):
        """Process all active states.  Iterates over a snapshot so states that
        remove themselves during process() do not cause skipped entries."""
        for state in self.states[:]:
            state.process(self)

    def is_stunned(self):
        """True if any active state blocks move selection for this beat
        (e.g. WarCryStunned). Checked by combat orchestration, not by
        select_move() itself, so it applies even to NPC subclasses that
        override select_move() entirely."""
        return any(getattr(state, "_stunned", False) for state in self.states)

    def get_equipped_items(self):
        """Return all items in inventory that are currently equipped."""
        return [item for item in self.inventory if getattr(item, "isequipped", False)]

    def refresh_moves(self):
        """Return the subset of known_moves that are currently viable."""
        return [move for move in self.known_moves if move.viable()]

    def get_hp_pcnt(self):
        """Return remaining HP as a decimal fraction (0.0–1.0).

        Guards against maxhp <= 0 (fuzzer/extreme-stat case) so the divide
        never raises ZeroDivisionError in the combat loop.
        """
        maxhp = getattr(self, "maxhp", 0)
        try:
            maxhp = float(maxhp)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(maxhp) or maxhp <= 0:
            return 0.0
        return float(self.hp) / maxhp

    # ── Numeric guards (issue #296 hardening) ─────────────────────────────────
    # A missing resistance key (direct dict indexing) and non-finite values
    # (NaN/inf) were both confirmed to crash the combat damage path — the former
    # with KeyError, the latter with a ValueError inside int(damage). These
    # helpers are the single, shared choke point that keeps damage finite and
    # HP bounded for both Player and NPC (never duplicated in subclasses).

    def get_resistance(self, damage_type, default=1.0):
        """Return a sanitized damage-resistance multiplier for `damage_type`.

        Resolves a missing key to the base-dict value (or `default`) and coerces
        a non-finite value (NaN/inf) to `default`. The magnitude is intentionally
        NOT clamped — a multiplier may be negative (damage heals) or > 1
        (vulnerability); only finiteness is enforced so downstream int(damage)
        can never blow up.
        """
        resist = getattr(self, "resistance", None)
        if isinstance(resist, dict) and damage_type in resist:
            value = resist[damage_type]
        else:
            base = getattr(self, "resistance_base", None)
            if isinstance(base, dict) and damage_type in base:
                value = base[damage_type]
            else:
                value = default
        try:
            value = float(value)
        except (TypeError, ValueError):
            return float(default)
        if not math.isfinite(value):
            return float(default)
        return value

    def get_status_resistance(self, status_type, default=0.0):
        """Return a sanitized status-resistance fraction, clamped to [0.0, 1.0].

        Consumed as ``1 - resistance`` by :func:`functions.inflict`. A missing
        key falls back to `default` (matching the historical ``.get(..., 0.0)``);
        NaN/inf/out-of-range values are coerced into [0, 1] so the resulting
        application chance stays sane.
        """
        resist = getattr(self, "status_resistance", None)
        if isinstance(resist, dict) and status_type in resist:
            value = resist[status_type]
        else:
            value = default
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = float(default)
        if not math.isfinite(value):
            value = float(default)
        return min(1.0, max(0.0, value))

    def clamp_hp(self):
        """Clamp ``hp`` into [0, maxhp], coercing non-finite hp/maxhp to 0.

        Combat damage and heal paths mutate ``hp`` directly; calling this right
        after such a mutation keeps the HP-never-NaN/inf and HP-in-[0, maxhp]
        invariants without every call site repeating the bounds logic. Returns
        the clamped hp.
        """
        maxhp = getattr(self, "maxhp", 0)
        try:
            maxhp = float(maxhp)
            if not math.isfinite(maxhp) or maxhp < 0:
                maxhp = 0.0
        except (TypeError, ValueError):
            maxhp = 0.0
        hp = getattr(self, "hp", 0)
        try:
            hp = float(hp)
        except (TypeError, ValueError):
            hp = 0.0
        if not math.isfinite(hp):
            hp = 0.0
        self.hp = int(max(0.0, min(hp, maxhp)))
        return self.hp
