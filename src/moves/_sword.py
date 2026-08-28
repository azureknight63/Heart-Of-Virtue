"""Sword weapon moves: PommelStrike, Thrust, DisarmingSlash, Riposte, WhirlAttack, VertigoSpin and passives BladeMastery, CounterGuard."""

from src.narration import colored, cprint, narrate  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import src.states as states  # noqa: F401
import src.functions as functions  # noqa: F401
import src.items as items  # noqa: F401
import src.positions as positions  # noqa: F401
from src.animations import animate_to_main_screen as animate  # noqa: F401
from ._base import (
    Move,
    PassiveMove,
    _ensure_weapon_exp,
    _apply_to_hit_modifiers,
    to_hit_chance,
)  # noqa: F401


def weapon_scaled_power(user, factor):
    """Weapon-scaled power for the sweep/spin/pivot moves that deliberately do
    *not* route through ``standard_evaluate_attack``.

    Those moves keep hand-rolled ``evaluate()`` bodies because their timing is
    fixed rather than weapon-derived — but every one of them used to score
    power as ``weapon.damage * k + strength * k2``, which drops the weapon's
    ``str_mod``/``fin_mod`` entirely.  On a stat-scaling weapon that is not a
    small discrepancy: a Scythe deals only 5 flat damage and earns the rest
    through ``str_mod=2``/``fin_mod=2``, so Reap — a Scythe-only move — scored
    **5** power against Death's Harvest's 60 on the very same weapon.

    This mirrors ``standard_evaluate_attack``'s power line
    (``damage + strength*str_mod + finesse*fin_mod``) and then applies the
    caller's archetype ``factor``, so an area/utility move stays a fixed
    fraction of a full swing on *every* weapon rather than only on the
    flat-damage ones.  It lives in ``_sword.py`` because this module hosts the
    package's two weapon-agnostic moves (WhirlAttack, VertigoSpin); the
    scythe/polearm/dagger modules import it from here.  It is deliberately
    pure — it reads ``user`` and returns a number, never writing move state —
    so repeated ``evaluate()`` calls stay idempotent.
    """
    def _num(value, default=0.0):
        """Coerce to float, or ``default`` for anything non-numeric.

        Applied per *term* rather than around the whole expression on purpose:
        a weapon that carries a real ``damage`` but a missing or unusable
        ``str_mod`` should still score off its damage, not collapse to the
        no-weapon fallback. Wrapping the whole sum instead is what made the
        earlier hand-rolled versions silently bottom out at 1.
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    wpn = getattr(user, "eq_weapon", None)
    damage = _num(getattr(wpn, "damage", None), default=None) if wpn else None
    strength = _num(getattr(user, "strength", 0))
    if damage is None:
        base = strength
    else:
        base = (
            damage
            + strength * _num(getattr(wpn, "str_mod", 0))
            + _num(getattr(user, "finesse", 0)) * _num(getattr(wpn, "fin_mod", 0))
        )
    return max(1, int(base * _num(factor)))


class PommelStrike(Move):
    """
    Quick strike using the pommel of the weapon. This kind of attack serves to fill in gap time for weapons that
    have a longer execute time on their normal or special attacks. It also has a small chance to stun the target.
    """
    display_name = 'Pommel Strike'

    web_animation = "attack"

    def __init__(self, player):
        description = "Quick strike using the pommel of the weapon."
        prep = 1
        execute = 1
        recoil = 1  # modified later, based on player weapon
        cooldown = 2
        weapon = "fist"  # modified later, based on player weapon
        fatigue_cost = 0
        mvrange = (0, 5)
        super().__init__(
            name="Pommel Strike",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                f"{player.name} quickly turns his weapon...",
                colored(
                    f"{player.name} quickly strikes with the pommel of his {{}}!".format(
                        weapon
                    ),
                    "green",
                ),
                f"{player.name} braces himself from the recoil of his attack.",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=player,
        )
        self.power = 0  # enter the base damage bonus of the attack
        self.base_damage_type = "crushing"
        self.evaluate()

    def viable(self):
        viability = self.standard_viability_attack(
            ("Axe", "Pick", "Scythe", "Spear", "Bludgeon", "Sword")
        )
        return viability

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.fatigue_cost = 10
            return
        # base_power MUST be a literal, never ``self.power``.  ``advance()``
        # calls ``evaluate()`` on every beat for every known move, and
        # ``standard_evaluate_attack`` computes
        # ``weapon.damage + base_power + str*str_mod + fin*fin_mod``.  Feeding
        # the previous result back in as ``base_power`` made the move's power
        # compound without bound (51 -> 102 -> 153 -> ... on a Longsword).
        evaluation = self.standard_evaluate_attack(
            base_power=-10,
            base_damage_type=self.base_damage_type,
            mod_prep=(-1 * (self.user.eq_weapon.weight * 3)),
            mod_fatigue=-35,
            floor_fatigue=10,
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]

    def execute(self, player):
        self.standard_execute_attack(player, self.power, self.base_damage_type)


class WhirlAttack(Move):
    """360-degree spinning attack that damages nearby enemies.

    A multi-beat attack that involves spinning to hit all enemies in range,
    ending with a random facing direction. High fatigue cost reflects the effort
    of rapid rotation and multiple strikes.
    """
    display_name = 'Whirl Attack'

    web_animation = "sweep"

    def __init__(self, user):
        description = "Spin to attack all nearby enemies."
        # Area chip: a short 7-beat cycle with a 2-beat spin, deliberately the
        # cheapest sustained option in the roster. Single-target throughput is
        # poor by design (~0.40x a full swing); it only pays against 2+ enemies.
        prep = 1
        execute = 2
        recoil = 1
        cooldown = 3
        fatigue_cost = 45
        target = user  # Self-targeted, affects multiple enemies
        super().__init__(
            name="Whirl Attack",
            description=description,
            xp_gain=15,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(1, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
            category="Offensive",
        )
        self.affected_enemies = []  # Track enemies hit
        self.evaluate()

    def viable(self):
        """Whirl Attack is viable if there are enemies nearby."""
        if (
            not hasattr(self.user, "combat_position")
            or self.user.combat_position is None
        ):
            return False

        # Check if there are enemies within range
        for enemy in self.user.combat_proximity.keys():
            if enemy.is_alive():
                if (
                    hasattr(enemy, "combat_position")
                    and enemy.combat_position is not None
                ):
                    dist = positions.distance_from_coords(
                        self.user.combat_position, enemy.combat_position
                    )
                    if dist <= self.mvrange[1]:
                        return True
        return False

    #: Fraction of a full weapon swing each enemy in the spin takes. The
    #: lowest area factor in the roster — Whirl Attack hits a full 360 degrees
    #: with no arc restriction, so it trades per-target damage for coverage.
    AREA_POWER_FACTOR = 0.40

    def evaluate(self):
        """Adjusts move power based on weapon and stats."""
        wpn = getattr(self.user, "eq_weapon", None)
        if wpn is not None and hasattr(wpn, "base_damage_type"):
            self.base_damage_type = wpn.base_damage_type
        self.power = weapon_scaled_power(self.user, self.AREA_POWER_FACTOR)

    def prep(self, user):
        """Prep stage - announce the spin."""
        cprint(f"{user.name} begins to spin...", "magenta")

    def execute(self, user):
        """Execute stage - hit all nearby enemies and end facing random direction."""
        cprint(f"{user.name} whirls around with devastating force!", "magenta")

        self.affected_enemies = []
        base_damage_type = getattr(self, "base_damage_type", "slashing")
        original_target = self.target

        # Award skill-tree progression exp for using the move (issue #402): the
        # bespoke HP math this used to run gave none.
        if hasattr(self.user, "eq_weapon") and self.user.eq_weapon:
            _ensure_weapon_exp(self.user)
            self.user.combat_exp[self.user.eq_weapon.subtype] += 5
        self.user.combat_exp["Basic"] += 5

        # Find all enemies in range
        try:
            for enemy in list(self.user.combat_proximity.keys()):
                if not enemy.is_alive():
                    continue

                if hasattr(enemy, "combat_position") and enemy.combat_position is not None:
                    dist = positions.distance_from_coords(
                        self.user.combat_position, enemy.combat_position
                    )
                    if dist <= self.mvrange[1]:
                        # Route damage through the shared pipeline (issue #402):
                        # resistances, heat scaling, and self.hit()/parry() bookkeeping.
                        self.target = enemy
                        self.prep_colors()
                        damage = (
                            (
                                (self.power * functions.combat_resistance(enemy, base_damage_type))
                                - enemy.protection
                            )
                            * self.user.heat
                        ) * random.uniform(0.8, 1.2)
                        damage = max(0, damage)

                        hit_chance = to_hit_chance(self.user, enemy, base=85)
                        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
                        hit_chance = _apply_to_hit_modifiers(self.user, enemy, hit_chance)
                        roll = random.randint(0, 100)
                        glance = False
                        if hit_chance >= roll and hit_chance - roll < 10:
                            damage /= 2
                            glance = True
                        damage = int(damage)

                        if hit_chance >= roll:
                            if functions.check_parry(enemy):
                                self.parry()
                            else:
                                self.hit(damage, glance)
                                self.affected_enemies.append(enemy)
        finally:
            # Restore the original target even if a hit() raises mid-loop, so the
            # facing/fatigue stages below don't act on a stale loop enemy.
            self.target = original_target

        # Set random facing
        random_facing = random.choice(list(positions.Direction))
        user.combat_position.facing = random_facing

        # Deduct fatigue
        user.fatigue -= self.fatigue_cost
        if user.fatigue < 0:
            user.fatigue = 0
        cprint(f"{user.name} ends facing {random_facing.name}!", "cyan")


class VertigoSpin(Move):
    """Attack that rotates target's facing and applies Disoriented status.

    A powerful spinning attack that not only damages the target but also
    leaves them disoriented, affecting their facing and reducing defensive bonuses.
    """
    display_name = 'Vertigo Spin'

    web_animation = "sweep"

    def __init__(self, user):
        description = "Spin attack that disorients the target."
        # Utility-first. The damage is deliberately about half a full swing:
        # the reason to press this is Disoriented plus the random re-facing it
        # forces on the target, which hands every subsequent attack in the
        # fight a flank or rear angle on the shared facing curve.
        prep = 1
        execute = 2
        recoil = 2
        cooldown = 3
        # Cheaper than every same-length attack it competes with, so the low
        # damage buys something concrete rather than just being a worse strike.
        fatigue_cost = 42
        target = user  # Will be set when move is selected
        super().__init__(
            name="Vertigo Spin",
            description=description,
            xp_gain=25,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(1, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
            category="Offensive",
        )
        self.evaluate()

    def viable(self):
        """Vertigo Spin is viable if target is nearby."""
        if (
            not hasattr(self.user, "combat_position")
            or self.user.combat_position is None
        ):
            return False

        if not self.target or not self.target.is_alive():
            return False

        if (
            hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            dist = positions.distance_from_coords(
                self.user.combat_position, self.target.combat_position
            )
            return 1 <= dist <= self.mvrange[1]

        return False

    #: Fraction of a full weapon swing this deals. Above the pure area moves
    #: (it is single-target) but well below a real attack — the status is the
    #: payload, not the damage.
    POWER_FACTOR = 0.55

    def evaluate(self):
        """Adjusts move power based on weapon and stats."""
        wpn = getattr(self.user, "eq_weapon", None)
        if wpn is not None and hasattr(wpn, "base_damage_type"):
            self.base_damage_type = wpn.base_damage_type
        self.power = weapon_scaled_power(self.user, self.POWER_FACTOR)

    def prep(self, user):
        """Prep stage - announce the spin."""
        if self.target:
            cprint(
                f"{user.name} begins spinning toward {self.target.name}...",
                "red",
            )

    def preview_hit_chance(self, target=None):
        """Unlike most moves, VertigoSpin's execute() never calls
        ``self.viable()`` before rolling -- its only real gate is "target
        exists and is alive" (checked in execute() and mirrored here), so
        this deliberately goes through ``_unconditional_preview_hit_chance``,
        not ``_standard_preview_hit_chance`` (which would additionally
        require ``combat_position`` via ``viable()`` and make the preview
        auto-miss in situations execute() itself would still roll for).
        """
        t = target if target is not None else self.target
        return self._unconditional_preview_hit_chance(t, base=85)

    def execute(self, user):
        """Execute stage - spin attack and apply Disoriented status."""
        if not self.target or not self.target.is_alive():
            cprint("Target is no longer available!", "red")
            return

        self.prep_colors()

        # Route damage through the shared pipeline (issue #402): resistances,
        # heat scaling, and self.hit()/miss()/parry() bookkeeping (which also
        # awards combat exp for the wielder).
        base_damage_type = getattr(self, "base_damage_type", "slashing")
        damage = (
            (
                (self.power * functions.combat_resistance(self.target, base_damage_type))
                - self.target.protection
            )
            * self.user.heat
        ) * random.uniform(0.8, 1.2)
        damage = max(0, damage)

        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1
        roll = random.randint(0, 100)
        glance = False
        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True
        damage = int(damage)

        if hasattr(self.user, "eq_weapon") and self.user.eq_weapon:
            _ensure_weapon_exp(self.user)
            self.user.combat_exp[self.user.eq_weapon.subtype] += 5
        self.user.combat_exp["Basic"] += 5

        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)

                # Rotate target's facing randomly
                random_facing = random.choice(list(positions.Direction))
                if (
                    hasattr(self.target, "combat_position")
                    and self.target.combat_position is not None
                ):
                    self.target.combat_position.facing = random_facing

                # Apply Disoriented status
                try:
                    # inflict() rolls against status resistance and handles
                    # duplicate compounding, unlike a raw states.append().
                    functions.inflict(states.Disoriented(self.target), self.target)
                except Exception as e:
                    cprint(f"Could not apply Disoriented status: {e}", "yellow")
        else:
            self.miss()

        # Deduct fatigue
        user.fatigue -= self.fatigue_cost
        if user.fatigue < 0:
            user.fatigue = 0


# This file contains the QuickSwap move to be added to src/moves.py


class Thrust(Move):
    """The roster's chip attack: ~40% of a full swing on a five-beat cycle.

    Deliberately the *worst* damage-per-beat of any sword or spear strike and
    by far the best damage-per-fatigue. It exists to fill a gap the basic
    Attack cannot: a complete attack cycle short enough to land inside a
    narrow opening, at a quarter of the fatigue, so an exhausted fighter still
    has an offensive option. Pressing it repeatedly is slower than pressing
    Attack — that is the trade, and it is what keeps Attack relevant.

    Viable for Sword and Spear. Each weapon's natural stats (weight, damage,
    range) differentiate their feel: a lighter sword thrusts quicker; a spear
    reaches farther.
    """
    display_name = 'Thrust'

    web_animation = "pierce"

    def __init__(self, user):
        description = (
            "Drive the point of your weapon forward in a fast, direct thrust. "
            "A fraction of a full swing's power, but it costs almost nothing "
            "and is over in a heartbeat."
        )
        prep = 1
        execute = 1
        recoil = 1
        cooldown = 0
        super().__init__(
            name="Thrust",
            description=description,
            xp_gain=3,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} lines up a thrust...",
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
        self.base_damage_type = "piercing"
        self.evaluate()

    def viable(self):
        return self.standard_viability_attack(("Sword", "Spear"))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [1, 1, 1, 0]
            self.fatigue_cost = 10
            return
        # Chip archetype. Power is a *percentage* of the full swing so the
        # 40% ratio holds on every weapon rather than only on flat-damage
        # ones; the timing mods drive prep/recoil/cooldown to their floors so
        # the whole cycle is ~5 beats regardless of weapon weight.
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="piercing",
            mod_power="40%",
            mod_prep=-10,
            mod_recoil=-1,
            mod_cd=-3,
            mod_fatigue=-70,
            floor_fatigue=12,
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        weapon_name = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} thrusts with his {weapon_name}!", "green"
        )

    def execute(self, player):
        self.standard_execute_attack(player, self.power, self.base_damage_type)


# ---------------------------------------------------------------------------
# SWORD
# ---------------------------------------------------------------------------


class DisarmingSlash(Move):
    """Calculated slash that rattles the target, applying Disoriented on hit.

    Utility-first: 60% of a full swing on a compressed eight-beat cycle. Its
    damage-per-beat is deliberately well under the basic Attack's — the
    Disoriented state is what you are buying, and the short cycle is what lets
    you buy it early in an exchange instead of committing to a full swing.
    """
    display_name = 'Disarming Slash'

    web_animation = "attack"

    def __init__(self, user):
        description = (
            "A calculated slash aimed at the target's guard. "
            "Deals lighter damage but leaves them rattled and disoriented."
        )
        prep = 1
        execute = 1
        recoil = 2
        cooldown = 3
        super().__init__(
            name="Disarming Slash",
            description=description,
            xp_gain=8,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} feints at the target's guard...",
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
        self.base_damage_type = "slashing"
        self.evaluate()

    def viable(self):
        return self.standard_viability_attack(("Sword",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [1, 1, 2, 3]
            self.fatigue_cost = 10
            return
        # Debuff opener: short prep and cooldown so it can be thrown early,
        # paid for with 60% power — the Disoriented state is the payload.
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="slashing",
            mod_power="60%",
            mod_prep=-2,
            mod_cd=-2,
            mod_fatigue=-45,
            floor_fatigue=15,
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} slashes at {getattr(self.target, 'name', 'the target')}'s guard with his {wpn}!",
            "green",
        )

    def execute(self, player):
        glance = False
        self.prep_colors()
        narrate(self.stage_announce[1])

        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        if self.viable():
            hit_chance = to_hit_chance(self.user, self.target, floor=5)
        else:
            hit_chance = -1
        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(self.user, self.target, hit_chance)

        roll = random.randint(0, 100)
        damage = (
            (
                (self.power * functions.combat_resistance(self.target, self.base_damage_type))
                - self.target.protection
            )
            * player.heat
        ) * random.uniform(0.8, 1.2)
        damage = max(0, damage)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True
        damage = int(damage)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5

        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                if self.target and self.target.is_alive():
                    already = any(
                        isinstance(s, states.Disoriented) for s in self.target.states
                    )
                    if not already:
                        try:
                            # inflict() emits the disoriented message via
                            # Disoriented.on_application when the state lands.
                            functions.inflict(
                                states.Disoriented(self.target), self.target
                            )
                        except Exception:
                            pass
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class Riposte(Move):
    """Counterattack delivered while still in guard — usable only while Parrying.

    The roster's high-risk, high-tempo option. Prep is genuinely **zero** —
    the guard is already up — which makes it the only attack in the game that
    resolves without a telegraph, and gives it by far the best
    damage-per-beat. The risk is entirely up front: reaching it costs a beat
    spent on Parry that does no damage at all, and it evaporates the moment
    the Parrying state does, so it only pays on a correct read of the
    opponent's timing.

    ``__init__`` has always declared ``prep = 0``, but ``evaluate()`` used to
    overwrite the whole ``stage_beat`` from ``standard_evaluate_attack`` —
    whose prep is weapon-weight derived — so the documented near-instant
    counter actually wound up on a 4-beat wind-up, slower than a Thrust. The
    prep is now re-forced to 0 after the standard evaluation.
    """
    display_name = 'Riposte'

    web_animation = "quick_attack"

    def __init__(self, user):
        description = (
            "While your guard is up, drive a quick counterstrike into your opponent. "
            "Only usable while actively parrying. Heat-boosted damage."
        )
        prep = 0
        execute = 1
        recoil = 2
        cooldown = 2
        super().__init__(
            name="Riposte",
            description=description,
            xp_gain=10,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                "",
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
        self.base_damage_type = "slashing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Sword":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        is_parrying = any(isinstance(s, states.Parrying) for s in self.user.states)
        if not is_parrying:
            return False
        range_min, range_max = self.mvrange
        return any(
            range_min <= dist <= range_max
            for dist in self.user.combat_proximity.values()
        )

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [0, 1, 2, 2]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="slashing",
            mod_power="85%",
            mod_cd=-2,
            mod_fatigue=-25,
            floor_fatigue=12,
        )
        # Zero prep is the whole identity of the move (see the class
        # docstring). ``standard_evaluate_attack`` cannot express it — its prep
        # is floored at 1 — so re-force it here. Assigning a literal, never a
        # value derived from the move's own state, keeps evaluate() idempotent.
        self.stage_beat[0] = 0
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} counters with his {wpn}!", "green"
        )

    def execute(self, player):
        glance = False
        self.prep_colors()
        narrate(self.stage_announce[1])

        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        if self.viable():
            hit_chance = to_hit_chance(self.user, self.target, floor=5)
        else:
            hit_chance = -1
        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(self.user, self.target, hit_chance)

        roll = random.randint(0, 100)

        # Heat boost: still in guard, momentum from deflection
        old_heat = player.heat
        player.heat = min(10.0, player.heat * 1.3)
        try:
            damage = (
                (
                    (self.power * functions.combat_resistance(self.target, self.base_damage_type))
                    - self.target.protection
                )
                * player.heat
            ) * random.uniform(0.8, 1.2)
        finally:
            player.heat = old_heat

        damage = max(0, damage)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True
        damage = int(damage)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 8
        player.combat_exp["Basic"] += 5

        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class BladeMastery(PassiveMove):
    """Passive: Sword discipline; reduces fatigue cost of sword attacks."""
    display_name = 'Blade Mastery'

    def __init__(self, user):
        super().__init__(
            user,
            "Blade Mastery",
            (
                "Years of swordsmanship have made each technique economical. "
                "Sword attacks cost less fatigue."
            ),
        )


class CounterGuard(PassiveMove):
    """Passive: Parrying while sword-equipped costs less fatigue."""
    display_name = 'Counter Guard'

    def __init__(self, user):
        super().__init__(
            user,
            "Counter Guard",
            (
                "Your guard is second nature. "
                "Maintaining a parry stance with a sword costs less fatigue."
            ),
        )
