"""Scythe weapon moves: Reap, ReapersMark, DeathsHarvest and passives GrimPersistence, HauntingPresence."""

from src.narration import colored, cprint, narrate  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import src.states as states  # noqa: F401
import src.functions as functions  # noqa: F401
import src.items as items  # noqa: F401
import src.positions as positions  # noqa: F401
from src.animations import animate_to_main_screen as animate  # noqa: F401
from ._base import (
    weapon_scaled_power,
    apply_facing_damage,
    hostiles_in_arc,
    Move,
    OUTCOME_HIT,
    OUTCOME_MISS,
    OUTCOME_PARRY,
    PassiveMove,
    _ensure_weapon_exp,
    _apply_to_hit_modifiers,
    publish_outcome,
    to_hit_chance,
)  # noqa: F401


class Reap(Move):
    """Wide frontal arc sweep hitting all enemies in front of the user.

    Lower per-target damage than a single strike but covers all threats in
    the frontal hemisphere. Falls back to full-circle hit if coordinates
    are unavailable (mirrors WhirlAttack fallback).

    The scythe's cheap area option: ~45% of a full swing per enemy on a
    seven-beat cycle. Its single-target damage-per-beat is deliberately far
    below a real strike's — it only pays from the second enemy onward.

    Its power used to be ``weapon.damage * 0.65 + strength * 0.2``, which
    drops the weapon's ``str_mod``/``fin_mod`` entirely. That is fatal on the
    one weapon Reap can be used with: a Scythe deals 5 flat damage and earns
    the rest through ``str_mod=2``/``fin_mod=2``, so Reap scored **5** power
    while Death's Harvest — same weapon, same stats — scored 60. It now goes
    through ``weapon_scaled_power``, which mirrors the standard power line.
    """
    display_name = 'Reap'

    web_animation = "sweep"

    #: Fraction of a full weapon swing each enemy in the arc takes.
    AREA_POWER_FACTOR = 0.45

    def __init__(self, user):
        description = (
            "Sweep your scythe in a wide arc ahead of you, "
            "striking all enemies in its path."
        )
        prep = 1
        execute = 2
        recoil = 2
        cooldown = 2
        super().__init__(
            name="Reap",
            description=description,
            xp_gain=12,
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
        self.base_damage_type = "slashing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Scythe":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        return any(e.is_alive() for e in self.user.combat_proximity)

    def evaluate(self):
        self.power = weapon_scaled_power(self.user, self.AREA_POWER_FACTOR)

    def preview_reach(self):
        """Reap's arc is scored against the *weapon's* reach — see the
        ``wpn_range`` line at the top of ``execute`` — not its own ``mvrange``,
        which ``evaluate`` never narrows from the ``(1, 20)`` placeholder. The
        default would advertise a 20 ft sweep for a 5 ft scythe.
        """
        wpnrange = getattr(getattr(self.user, "eq_weapon", None), "wpnrange", (0, 5))
        try:
            return wpnrange[1]
        except (TypeError, IndexError):
            return 5

    def preview_affected(self):
        """Everything ``execute``'s loop below would swing at: the living
        hostiles inside the 90-degree frontal hemisphere at weapon reach,
        falling back to ``combat_proximity`` distance when either combatant
        has no coordinates.
        """
        return hostiles_in_arc(self, self.preview_reach(), frontal=True)

    def preview_damage(self, target=None):
        """Reap does not run the canonical damage expression at all: its loop
        deals ``max(1, int(swing_power - protection))``, with no resistance,
        no heat scaling and no variance roll — so min and max are the same
        number — then applies ``_damage_multipliers`` in order. See ``execute``.
        """
        return self._area_preview_damage(
            target, flat=True, bonuses=self._damage_multipliers(target)
        )

    def prep(self, user):
        cprint(f"{user.name} raises the scythe for a wide sweep...", "magenta")

    def _damage_multipliers(self, enemy):
        """The per-target damage multipliers this sweep applies to ``enemy``,
        in the order ``execute``'s loop applies them.

        The single derivation of the pair, read by both the loop and
        ``preview_damage`` — the numbers and their order used to be stated
        twice, once here and once in a preview lookup table in another file.
        Order and per-multiplier truncation are load-bearing: the loop
        ``int()``s after each one, not once at the end.

        * Grim Persistence (passive): +25% against a target below 35% HP.
        * Reaper's Mark: +25% against a marked target.
        """
        multipliers = []
        if any(
            getattr(m, "name", "") == "Grim Persistence"
            for m in getattr(self.user, "known_moves", [])
        ):
            maxhp = getattr(enemy, "maxhp", 0) or 0
            if getattr(enemy, "hp", 0) < (maxhp * 0.35):
                multipliers.append(1.25)
        if getattr(enemy, "_reapers_mark", False) is True:
            multipliers.append(1.25)
        return multipliers

    def execute(self, user):
        cprint(f"{user.name} sweeps the scythe in a devastating arc!", "magenta")
        wpn_range = getattr(getattr(self.user, "eq_weapon", None), "wpnrange", (0, 5))
        arc_range = wpn_range[1]

        # Hostiles only. This loop used to walk combat_proximity directly,
        # which holds BOTH sides -- so every arc and spin dealt full damage
        # to Jean's own allies, silently and with no warning. Measured
        # before the fix: Whirl Attack dealt 27 to Gorran against 23 to the
        # enemy it was aimed at. Blood of Martyrs was the only area move
        # that got this right, purely because it happened to iterate
        # combat_list. _hostiles_in_proximity is that same rule, shared.
        for enemy, _distance in list(self._hostiles_in_proximity()):
            if not enemy.is_alive():
                continue

            # Frontal arc check when coordinates available
            if (
                hasattr(self.user, "combat_position")
                and self.user.combat_position is not None
                and hasattr(enemy, "combat_position")
                and enemy.combat_position is not None
            ):
                dist = positions.distance_from_coords(
                    self.user.combat_position, enemy.combat_position
                )
                if dist > arc_range:
                    continue
                try:
                    atk_angle = positions.angle_to_target(
                        self.user.combat_position, enemy.combat_position
                    )
                    angle_diff = positions.attack_angle_difference(
                        atk_angle, self.user.combat_position.facing
                    )
                    if angle_diff > 90:  # outside frontal hemisphere
                        continue
                except Exception:
                    pass
            else:
                dist = self.user.combat_proximity.get(enemy, 9999)
                if dist > arc_range:
                    continue

            # Facing/angle damage (#394) - see apply_facing_damage.
            # Scored per enemy: an arc swing reaches each one from a
            # different angle, so one hoisted multiplier would be wrong
            # for every target but one.
            swing_power = apply_facing_damage(self.user, enemy, self.power)
            base_dmg = max(1, int(swing_power - enemy.protection))
            # Truncated per multiplier, in order -- see _damage_multipliers.
            for multiplier in self._damage_multipliers(enemy):
                base_dmg = int(base_dmg * multiplier)
            # ReapersMark is consumed on a landed hit; see below.
            marked = getattr(enemy, "_reapers_mark", False) is True
            hit_chance = to_hit_chance(self.user, enemy, base=85, floor=5)
            # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
            hit_chance = _apply_to_hit_modifiers(self.user, enemy, hit_chance)
            # One outcome per enemy, published immediately before that enemy's
            # own line (see _base.publish_outcome) -- a single outcome for the
            # whole arc would report whoever narrated first as everyone's
            # result. Reap deals flat `max(1, power - protection)` with no
            # hit-margin test, so it has no glancing blow to report.
            if random.randint(0, 100) <= hit_chance:
                if functions.check_parry(enemy):
                    publish_outcome(self.user, OUTCOME_PARRY, enemy)
                    cprint(f"{enemy.name} parried the sweep!", "yellow")
                else:
                    enemy.hp = max(0, enemy.hp - base_dmg)
                    if marked:
                        enemy._reapers_mark = False
                    publish_outcome(self.user, OUTCOME_HIT, enemy)
                    cprint(
                        f"{enemy.name} takes {base_dmg} damage from the sweep!", "red"
                    )
            else:
                # Previously silent: a whiffed enemy produced no line at all, so
                # the arc went quiet and the player could not tell a miss from an
                # enemy standing outside the cone.
                publish_outcome(self.user, OUTCOME_MISS, enemy)
                cprint(f"The scythe passes wide of {enemy.name}!", "yellow")

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class ReapersMark(Move):
    """Mark a target — next attack against them deals +25% more damage.

    Sets a '_reapers_mark' flag on the target that attack moves can check.
    """
    display_name = "Reaper's Mark"

    web_animation = "debuff"

    def __init__(self, user):
        description = (
            "Fix your gaze on one enemy, marking them for death. "
            "Your next attack against this target deals bonus damage."
        )
        prep = 1
        execute = 1
        recoil = 0
        cooldown = 3
        super().__init__(
            name="Reaper's Mark",
            description=description,
            xp_gain=5,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 9999),
            stage_announce=[
                f"{user.name} marks a target for death...",
                "",
                "",
                "",
            ],
            fatigue_cost=10,
            beats_left=prep,
            target=None,
            user=user,
            category="Tactical",
        )
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Scythe":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        return any(e.is_alive() for e in self.user.combat_proximity)

    def evaluate(self):
        pass

    def preview_hit_chance(self, target=None):
        """Reaper's Mark only flags the target for a future bonus -- it deals
        no damage and rolls no to-hit itself."""
        return None

    def execute(self, user):
        if self.target and self.target.is_alive():
            self.target._reapers_mark = True
            cprint(
                f"{user.name} marks {self.target.name} — death follows close behind.",
                "magenta",
            )
        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class DeathsHarvest(Move):
    """Draining scythe strike — heals user for 30% of damage dealt on a hit.

    Slower and heavier than Reap; designed for the final exchange in a drawn-out
    fight where the user needs to recover while still pressing the assault.

    The scythe tree's heavy: ~1.75x the basic Attack's damage over ~1.7x its
    beats, with a ten-beat wind-up and a six-beat recovery, and 30% of the
    damage returned as HP. Committing to it is a real bet — the scythe is the
    slowest weapon in the game, so a whiffed Harvest is the longest window any
    enemy will ever get — and landing it is the only way a scythe fighter
    heals in combat.

    ``__init__`` declared ``[2, 1, 3, 5]``; ``evaluate()`` used to overwrite it
    with plain weapon timing, so "slower and heavier than Reap" ran on the same
    twelve beats as everything else. The mods below restore the commitment.
    """
    display_name = "Death's Harvest"

    web_animation = "heavy_attack"

    def __init__(self, user):
        description = (
            "A deliberate, draining strike that channels your enemy's life force "
            "back into you. Heals for 30% of damage dealt on a successful hit."
        )
        prep = 10
        execute = 2
        recoil = 6
        cooldown = 6
        super().__init__(
            name="Death's Harvest",
            description=description,
            xp_gain=15,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} draws back the scythe, gathering energy...",
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
        if getattr(self.user.eq_weapon, "subtype", None) != "Scythe":
            return False
        return self.standard_viability_attack(("Scythe",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [10, 2, 6, 6]
            self.fatigue_cost = 25
            return
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="slashing",
            mod_power="180%",
            mod_prep=4,
            mod_recoil=2,
            # The scythe's weight already gives it the roster's longest natural
            # cooldown (9 beats at base stats); trimming it keeps the added
            # commitment in the *visible* prep/recoil stages, where an opponent
            # can actually read and punish it, rather than in dead air.
            mod_cd=-3,
            mod_fatigue=5,
            floor_fatigue=25,
        )
        # A two-beat execute stage, as for the other heavies:
        # ``standard_evaluate_attack`` hard-codes execute to 1. A literal, so
        # repeated evaluate() calls stay idempotent.
        self.stage_beat[1] = 2
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} drives his {wpn} through {getattr(self.target, 'name', 'the target')}!",
            "magenta",
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
        # Facing/angle damage (#394) - see apply_facing_damage.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = (
            (
                (power * functions.combat_resistance(self.target, self.base_damage_type))
                - self.target.protection
            )
            * player.heat
        ) * random.uniform(0.8, 1.2)
        damage = max(0, damage)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True

        # GrimPersistence passive: +25% damage vs targets below 35% HP
        if (
            any(
                getattr(m, "name", "") == "Grim Persistence"
                for m in getattr(player, "known_moves", [])
            )
            and self.target.hp < (self.target.maxhp * 0.35)
        ):
            damage *= 1.25

        # ReapersMark: marked target takes +25% damage; consumed on a landed hit
        marked = getattr(self.target, "_reapers_mark", False) is True
        if marked:
            damage *= 1.25

        damage = int(damage)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 8
        player.combat_exp["Basic"] += 5

        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                # Lifesteal must be based on the damage actually applied, not the
                # pre-absorption value (issue #420): Blood of Martyrs fully absorbs
                # the hit inside hit(), so no life is drained and nothing is healed.
                absorbed = any(
                    getattr(s, "_absorbing", False)
                    for s in getattr(self.target, "states", [])
                )
                self.hit(damage, glance)
                if marked:
                    self.target._reapers_mark = False
                applied = 0 if absorbed else damage
                heal = max(1, int(applied * 0.30)) if applied > 0 else 0
                if heal > 0:
                    player.hp = min(player.maxhp, player.hp + heal)
                    cprint(
                        f"{player.name} drains {heal} HP from {self.target.name}!",
                        "green" if player.name == "Jean" else "cyan",
                    )
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class GrimPersistence(PassiveMove):
    """Passive: Attacks deal bonus damage against targets below 35% HP."""
    display_name = 'Grim Persistence'

    def __init__(self, user):
        super().__init__(
            user,
            "Grim Persistence",
            (
                "You press wounded prey relentlessly. "
                "Attacks against enemies below 35% HP deal increased damage."
            ),
        )


class HauntingPresence(PassiveMove):
    """Passive: Enemies near you suffer an unsettling aura (future hook)."""
    display_name = 'Haunting Presence'

    def __init__(self, user):
        super().__init__(
            user,
            "Haunting Presence",
            (
                "Your very presence unsettles those nearby. "
                "Enemies in close range feel the weight of their mortality."
            ),
        )
