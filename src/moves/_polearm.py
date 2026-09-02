"""Polearm/halberd moves: OverheadSmash, Sweep, BracePosition, HalberdSpin and passive ReachMastery."""

from src.narration import colored, cprint
import random  # a test patches the dice through this module's binding
import src.states as states
import src.positions as positions
from ._base import (
    weapon_scaled_power,
    apply_facing_damage,
    flat_arc_strike_damage,
    hostiles_in_arc,
    Move,
    PassiveMove,
    _apply_to_hit_modifiers,
    resolve_strike_outcome,
    to_hit_chance,
)


def _living_hostile_in_arc(move):
    """True when a living hostile stands within ``move``'s maximum arc range.

    Shared by the two area-of-effect polearm swings (Sweep, HalberdSpin), which
    hit everything in the arc rather than a single assigned target. Allies are
    excluded via ``Move._hostiles_in_proximity`` — an ally standing next to the
    user must not make an arc swing look castable when every enemy is out of
    reach (issue #398).
    """
    if not hasattr(move.user, "combat_proximity"):
        return False
    max_range = move.mvrange[1]
    return any(
        enemy.is_alive() and distance <= max_range
        for enemy, distance in move._hostiles_in_proximity()
    )


class OverheadSmash(Move):
    """Bring the polearm shaft down in a heavy vertical strike.

    Slower than Sweep but deals more single-target damage. The weight of the
    weapon driving downward makes this one of the hardest hits in the polearm kit.

    The polearm tree's heavy, and the roster's biggest single hit: ~2x the
    basic Attack's damage over ~1.9x its beats, with a nine-beat wind-up and a
    five-beat recovery. Almost all of the cost is spent where the player can
    see it — on the beat timeline — because that is what an opponent gets to
    read and punish. Fatigue does the rest: at roughly two-thirds of a full
    bar it is not a move you can throw twice in a row.

    ``__init__`` declared ``[2, 1, 4, 5]``, but ``evaluate()`` overwrote it
    with the plain weapon-derived timing, so "slow" ran on the same twelve
    beats as everything else in the roster. The mods below restore it, routed
    through ``standard_evaluate_attack`` so they scale with weapon weight.
    """
    display_name = 'Overhead Smash'

    web_animation = "heavy_attack"

    def __init__(self, user):
        description = (
            "Raise the polearm and drive it down in a punishing vertical blow. "
            "Slow, but hits with the full weight of the weapon."
        )
        prep = 9
        execute = 2
        recoil = 5
        cooldown = 5
        super().__init__(
            name="Overhead Smash",
            description=description,
            xp_gain=8,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 6),
            stage_announce=[
                f"{user.name} heaves the polearm overhead...",
                "",
                "",
                "",
            ],
            fatigue_cost=0,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "crushing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Polearm":
            return False
        return self.standard_viability_attack(("Polearm",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [9, 2, 5, 5]
            self.fatigue_cost = 25
            return
        # ReachMastery passive: polearm attacks reach further
        reach_bonus = (
            2
            if any(
                getattr(m, "name", "") == "Reach Mastery"
                for m in getattr(self.user, "known_moves", [])
            )
            else 0
        )
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="crushing",
            mod_power="205%",
            mod_prep=5,
            mod_recoil=3,
            mod_cd=1,
            mod_fatigue=45,
            floor_fatigue=25,
            mod_range_max=reach_bonus,
        )
        # A two-beat execute stage, as for the other heavies:
        # ``standard_evaluate_attack`` hard-codes execute to 1. A literal, so
        # repeated evaluate() calls stay idempotent.
        self.stage_beat[1] = 2
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} drives his {wpn} down onto {getattr(self.target, 'name', 'the target')}!",
            "green",
        )

    def execute(self, player):
        self.standard_execute_attack(player, self.power, self.base_damage_type)


class Sweep(Move):
    """Horizontal arc attack hitting all enemies within weapon range ahead of user.

    Frontal arc (90° cone) when coordinates are available; full circle fallback.
    Lower per-target damage than Overhead Smash but covers multiple enemies.

    The polearm's cheap area option: ~45% of a full swing per enemy on a
    seven-beat cycle. Against a single target its damage-per-beat is well
    below the basic Attack's — it starts paying at two enemies in the cone,
    and it is the answer to a crowd rather than to a duel. Halberd Spin is its
    heavy counterpart: more damage per enemy over almost twice the beats, and
    a full 360 degrees instead of a frontal cone.
    """
    display_name = 'Sweep'

    web_animation = "sweep"

    #: Fraction of a full weapon swing each enemy in the cone takes. Above
    #: Reap's and Whirl Attack's: the polearm is the crowd weapon, and a Sweep
    #: that lands under Keep Away on every axis would have no reason to exist
    #: on this tree.
    AREA_POWER_FACTOR = 0.55

    def __init__(self, user):
        description = (
            "Swing the polearm in a wide horizontal arc, striking all enemies ahead. "
            "Lower single-target damage, but clears a path through groups."
        )
        prep = 1
        execute = 2
        recoil = 2
        cooldown = 2
        super().__init__(
            name="Sweep",
            description=description,
            xp_gain=10,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(1, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=45,
            beats_left=prep,
            target=user,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "crushing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Polearm":
            return False
        return _living_hostile_in_arc(self)

    def evaluate(self):
        self.power = weapon_scaled_power(self.user, self.AREA_POWER_FACTOR)
        try:
            arc_range = getattr(
                getattr(self.user, "eq_weapon", None), "wpnrange", (0, 6)
            )
            reach_bonus = (
                2
                if any(
                    getattr(m, "name", "") == "Reach Mastery"
                    for m in getattr(self.user, "known_moves", [])
                )
                else 0
            )
            self.mvrange = (1, arc_range[1] + 2 + reach_bonus)
        except (TypeError, AttributeError):
            pass

    def preview_affected(self):
        """Everything ``execute``'s loop below would swing at: the living
        hostiles inside the 90-degree frontal cone out to ``mvrange[1]``
        (``evaluate`` sets that from the weapon's reach plus Reach Mastery),
        falling back to ``combat_proximity`` distance when either combatant
        has no coordinates.
        """
        return hostiles_in_arc(self, self.preview_reach(), frontal=True)

    def preview_damage(self, target=None, affected=None):
        """Sweep's loop deals ``max(1, int(swing_power - protection))`` — no
        resistance, no heat scaling and no variance roll, so min and max are
        the same number rather than a band. See ``execute``. ``affected`` is a
        server-computed ``preview_affected()`` result the adapter passes back
        in — see ``Move._area_preview_damage``.
        """
        return self._area_preview_damage(target, flat=True, affected=affected)

    def prep(self, user):
        cprint(f"{user.name} winds up for a wide sweep...", "cyan")

    def execute(self, user):
        cprint(f"{user.name} sweeps the polearm in a broad arc!", "cyan")

        # Exactly the set the preview prices: preview_affected() states the
        # arc gate once (see hostiles_in_arc's docstring for the rationale),
        # so the swing and its preview cannot disagree about who is in it.
        for enemy in self.preview_affected():
            # Facing/angle damage (#394) - see apply_facing_damage.
            # Scored per enemy: an arc swing reaches each one from a
            # different angle, so one hoisted multiplier would be wrong
            # for every target but one.
            swing_power = apply_facing_damage(self.user, enemy, self.power)
            # The flat arc line, stated once for predictor and executes both
            # -- see _base.flat_arc_strike_damage.
            base_dmg = flat_arc_strike_damage(enemy, swing_power)
            hit_chance = to_hit_chance(self.user, enemy, base=85, floor=5)
            # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
            hit_chance = _apply_to_hit_modifiers(self.user, enemy, hit_chance)
            # One outcome per enemy, published immediately before that enemy's
            # own line -- see _base.resolve_strike_outcome, which is where that
            # pairing now lives. Sweep has no glancing-blow branch (flat
            # `max(1, power - protection)`, no hit-margin test) and its damage
            # floors at 1, so it can only ever publish hit/parry/miss.
            resolve_strike_outcome(
                self,
                enemy,
                base_dmg,
                hit_chance,
                hit_line=f"{enemy.name} takes {base_dmg} damage from the sweep!",
                parry_line=f"{enemy.name} blocked the sweep!",
                miss_line=f"The sweep passes wide of {enemy.name}!",
            )

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class BracePosition(Move):
    """Set a guarding stance — applies Parrying state with a polearm announcement.

    Mechanically identical to Parry but flavoured for the defensive polearm style.
    The user plants the weapon and waits to intercept.
    """
    display_name = 'Brace Position'

    web_animation = "defend"

    def __init__(self, user):
        description = (
            "Plant your polearm and brace for impact. "
            "Enters a guarding stance to intercept the next incoming attack."
        )
        prep = 1
        execute = 1
        recoil = 5
        cooldown = 3
        super().__init__(
            name="Brace Position",
            description=description,
            xp_gain=5,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(0, 9999),
            stage_announce=[
                f"{user.name} plants the polearm and braces...",
                "",
                "",
                "",
            ],
            fatigue_cost=0,
            beats_left=prep,
            target=user,
            user=user,
            category="Defensive",
        )
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        return getattr(self.user.eq_weapon, "subtype", None) == "Polearm"

    def evaluate(self):
        self.fatigue_cost = max(
            10, 75 - ((2 * self.user.endurance) + (3 * self.user.finesse))
        )

    def execute(self, user):
        wpn = (
            getattr(user.eq_weapon, "name", "polearm")
            if getattr(user, "eq_weapon", None)
            else "polearm"
        )
        cprint(
            f"{user.name} plants the {wpn} and holds the line!",
            "cyan",
        )
        # Remove any existing Parrying state then apply fresh
        user.states = [s for s in user.states if not isinstance(s, states.Parrying)]
        user.states.append(states.Parrying(user))
        user.fatigue -= self.fatigue_cost
        if user.fatigue < 0:
            user.fatigue = 0


class HalberdSpin(Move):
    """360-degree spin at full polearm reach — extended range, heavier recoil.

    Similar to WhirlAttack but with the polearm's greater natural range.
    More damaging per enemy than Sweep but costs more fatigue and has longer
    cooldown.

    The heavy area option: ~70% of a full swing per enemy — over half again
    what Sweep deals — but on a thirteen-beat cycle at twice the fatigue, and
    it ends with the user facing a random direction. Against two or three
    enemies in front of you Sweep is simply better; Halberd Spin is what you
    press when you are *surrounded*, because it is the only polearm swing with
    no frontal-cone restriction and it reaches a unit further out.
    """
    display_name = 'Halberd Spin'

    web_animation = "sweep"

    #: Fraction of a full weapon swing each enemy in the spin takes — the
    #: highest area factor in the roster, paid for in beats and fatigue.
    AREA_POWER_FACTOR = 0.70

    def __init__(self, user):
        description = (
            "Spin the polearm in a full circle at maximum reach, "
            "striking every enemy in range. High fatigue; heavy recoil."
        )
        prep = 3
        execute = 3
        recoil = 3
        cooldown = 4
        super().__init__(
            name="Halberd Spin",
            description=description,
            xp_gain=18,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(1, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=95,
            beats_left=prep,
            target=user,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "slashing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Polearm":
            return False
        return _living_hostile_in_arc(self)

    def evaluate(self):
        self.power = weapon_scaled_power(self.user, self.AREA_POWER_FACTOR)
        try:
            wpn = getattr(self.user, "eq_weapon", None)
            if wpn and hasattr(wpn, "damage"):
                arc_range = getattr(wpn, "wpnrange", (0, 6))
                reach_bonus = (
                    2
                    if any(
                        getattr(m, "name", "") == "Reach Mastery"
                        for m in getattr(self.user, "known_moves", [])
                    )
                    else 0
                )
                self.mvrange = (1, arc_range[1] + 3 + reach_bonus)
        except (TypeError, AttributeError):
            pass

    def preview_affected(self):
        """Everything ``execute``'s loop below would swing at: a full circle
        (no cone gate — that is the whole point of the spin) out to
        ``mvrange[1]``, which ``evaluate`` sets from the weapon's reach plus
        Reach Mastery, falling back to ``combat_proximity`` distance when
        either combatant has no coordinates.
        """
        return hostiles_in_arc(self, self.preview_reach())

    def preview_damage(self, target=None, affected=None):
        """Halberd Spin's loop deals ``max(1, int(swing_power - protection))``
        — no resistance, no heat scaling and no variance roll, so min and max
        are the same number rather than a band. See ``execute``. ``affected``
        is a server-computed ``preview_affected()`` result the adapter passes
        back in — see ``Move._area_preview_damage``.
        """
        return self._area_preview_damage(target, flat=True, affected=affected)

    def prep(self, user):
        cprint(f"{user.name} begins a wide spinning stance...", "cyan")

    def execute(self, user):
        cprint(f"{user.name} spins the halberd in a devastating full circle!", "cyan")

        # Exactly the set the preview prices: preview_affected() states the
        # full-circle gate once (see hostiles_in_arc's docstring), so the
        # spin and its preview cannot disagree about who is in it.
        for enemy in self.preview_affected():
            # Facing/angle damage (#394) - see apply_facing_damage.
            # Scored per enemy: a spin reaches each one from a different
            # angle, so one hoisted multiplier would be wrong for every
            # target but one.
            swing_power = apply_facing_damage(self.user, enemy, self.power)
            # The flat arc line, stated once for predictor and executes both
            # -- see _base.flat_arc_strike_damage.
            base_dmg = flat_arc_strike_damage(enemy, swing_power)
            hit_chance = to_hit_chance(self.user, enemy, base=85, floor=5)
            # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
            hit_chance = _apply_to_hit_modifiers(self.user, enemy, hit_chance)
            # Per-enemy outcomes; see the same call in Sweep above. Halberd
            # Spin shares Sweep's flat damage line and likewise has no glance.
            resolve_strike_outcome(
                self,
                enemy,
                base_dmg,
                hit_chance,
                hit_line=f"{enemy.name} takes {base_dmg} damage!",
                parry_line=f"{enemy.name} parried the spin!",
                miss_line=f"The spin whirls past {enemy.name}!",
            )

        # Random facing after spin
        try:
            if hasattr(user, "combat_position") and user.combat_position is not None:
                user.combat_position.facing = random.choice(
                    list(positions.Direction)
                )
        except Exception:
            pass

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class ReachMastery(PassiveMove):
    """Passive: Extended range training — polearm attacks reach further."""
    display_name = 'Reach Mastery'

    def __init__(self, user):
        super().__init__(
            user,
            "Reach Mastery",
            (
                "You have mastered the reach of your weapon. "
                "Polearm attacks are effective at slightly greater range."
            ),
        )
