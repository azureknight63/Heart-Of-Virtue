"""Unarmed/fist moves: PowerStrike, Jab and passives IronFist, CleaveInstinct, HeavyHanded."""

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
    Move,
    PassiveMove,
    DAMAGE_VARIANCE_MAX,
    DAMAGE_VARIANCE_MIN,
    _apply_carry_fatigue,
    _resolve_heat,
    apply_facing_damage,
    preview_payload,
)  # noqa: F401


def flat_unarmed_damage(target, faced_power, damage_type):
    """Jab's damage line, stated once so ``execute()`` and ``preview_damage()``
    cannot drift apart again.

    ``faced_power`` is the move's power *after* ``apply_facing_damage``. The
    facing curve is deliberately left to the two callers rather than folded in
    here: ``tests/test_facing_damage_hand_rolled_attacks.py`` is a static scan
    of each ``execute()``'s own source for that call, and a move that reaches
    the curve only through a helper reads to it as a move that skips the curve
    entirely. That guard exists because opting out of positional damage is
    silent -- no error, no symptom -- so it is worth keeping literal.

    What is left is the whole rest of the line: the target's resistance, then
    its protection, then nothing. No momentum multiplier and no
    ``random.uniform`` band -- a design decision rather than an oversight, see
    ``Jab.execute``. The flat shape has precedent (``flat_arc_damage_bounds``
    in ``_base`` serves Reap, Sweep and Halberd Spin) but not this exact
    expression: those three skip resistance and floor at 1, where Jab honours
    resistance and floors at 0. Written here rather than borrowed and quietly
    mis-stated.

    Returns a float; callers apply their own ``int()`` where the engine does.
    """
    protection = getattr(target, "protection", 0)
    if not isinstance(protection, (int, float)) or isinstance(protection, bool):
        protection = 0
    damage = (
        faced_power * functions.combat_resistance(target, damage_type)
    ) - protection
    return damage if damage > 0 else 0.0


class PowerStrike(Move):
    display_name = 'Power Strike'
    web_animation = "heavy_attack"

    def __init__(self, user):
        description = ""
        prep = 0
        execute = 4
        recoil = 3
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        self.target = user
        mvrange = (0, 5)
        if not hasattr(user, "eq_weapon") or user.eq_weapon is None:
            self.weapon = items.Rock()
        else:
            self.weapon = user.eq_weapon
        if not hasattr(self.weapon, "name"):
            self.weapon.name = "a rock"
        super().__init__(
            name="Power Strike",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=["This", "will", "update", "dynamically"],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=self.target,
            user=user,
            category="Offensive",
        )
        self.evaluate()

    def current_weapon(self):
        """The weapon Power Strike actually swings, read live from the user.

        ``__init__`` seeds ``self.weapon`` once, but the user equips and
        unequips freely afterwards.  Reading the cache instead of the user made
        viability permanently wrong in both directions: a Power Strike acquired
        while bare-handed (the skill-tree path every player takes) stayed
        un-castable even holding a mace, and one built while holding a mace
        stayed castable bare-handed.
        """
        weapon = getattr(self.user, "eq_weapon", None)
        if weapon is None:
            weapon = items.Rock()
        if not hasattr(weapon, "name"):
            weapon.name = "a rock"
        return weapon

    def viable(self):
        viability = False
        # Deliberately NOT assigning self.weapon here: viable() is a predicate,
        # and Move._viable_for calls it during hit-chance PREVIEW with a
        # temporarily swapped target. evaluate() refreshes self.weapon every
        # beat, so the write was redundant as well as surprising.
        weapon = self.current_weapon()
        if getattr(weapon, "subtype", None) != "Bludgeon":
            return False
        range_min = self.mvrange[0]
        range_max = self.mvrange[1]

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        # Inclusive bounds, matching standard_viability_attack. The strict
        # `<` form here made PowerStrike the one move in the game uncastable
        # at exactly its minimum and maximum reach.
        for enemy, distance in self.user.combat_proximity.items():
            if range_min <= distance <= range_max:
                viability = True
                break
        return viability

    #: Power as a multiple of a full weapon swing. Sits with the heavy
    #: archetype (Impale 190%, OverheadSmash 205%) -- Power Strike is the
    #: bludgeon tree's committed swing and carries the longest cycle in it.
    POWER_FACTOR = 1.9

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        # Refresh the weapon reference unconditionally — the announcement text
        # in refresh_announcements() reads it, and a stale name is how "swings
        # his fists mightily" ended up narrating a mace blow.
        weapon = self.current_weapon()
        self.weapon = weapon
        # Scale off the full weapon-and-stats expression like every other
        # attack. This used to be `weapon.damage * uniform(1.5, 2.5)` -- no
        # strength, no finesse, and neither of the weapon's stat multipliers --
        # which is the exact defect weapon_scaled_power was extracted to fix,
        # and PowerStrike was the one move left out of that sweep. The result
        # was the worst move in the roster (1.92 damage per beat against a
        # 2.75-7.0 band) that got RELATIVELY worse as Jean levelled, because
        # the basic Attack scales with strength and this did not.
        #
        # The variance moved to execute() with the rest of the damage roll:
        # evaluate() runs every beat, so rolling here re-rolled the move's
        # power continuously and broke the idempotence contract the whole
        # package relies on.
        power = weapon_scaled_power(self.user, self.POWER_FACTOR)
        # Damage type, derived the engine's own way (items.get_base_damage_type
        # on the weapon in hand) rather than named here. Without it execute()
        # and preview_damage both scored combat_resistance(target, None) --
        # which is the 1.0 default for every target, so the resistance term was
        # present in the expression and inert: a Bludgeon-resistant enemy took
        # a full Power Strike.
        self.base_damage_type = items.get_base_damage_type(weapon)
        prep = int(50 / self.user.speed)
        if prep < 1:
            prep = 1
        execute = 4
        # Recoil and cooldown were both roughly double any peer's, on top of a
        # 26-beat cycle. Trimmed so the move reads as a heavy commitment rather
        # than a punishment: it is still the longest cycle in the unarmed tree.
        recoil = int(50 / self.user.speed)
        if recoil < 0:
            recoil = 0
        recoil += 1
        cooldown = 7 - int(self.user.endurance / 10)
        if cooldown < 0:
            cooldown = 0
        fatigue_cost = max(25, 100 - (2 * self.user.endurance))
        fatigue_cost = _apply_carry_fatigue(self.user, fatigue_cost)

        # IronFist passive: +25% damage
        if any(
            getattr(m, "name", "") == "Iron Fist"
            for m in getattr(self.user, "known_moves", [])
        ):
            power *= 1.25

        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.refresh_announcements(self.user)

    def refresh_announcements(self, user):
        self.stage_announce = [
            colored(
                f"{user.name} grips {user.pronouns['possessive']} {self.weapon.name} "
                f"in preparation to strike!",
                "red",
            ),
            colored(
                f"{user.name} swings {user.pronouns['possessive']} "
                f"{self.weapon.name} mightily at {self.target.name}!",
                "red",
            ),
            f"{user.name} recoils heavily from the attack.",
            "",
        ]

    def preview_hit_chance(self, target=None):
        t = target if target is not None else self.target
        return self._standard_preview_hit_chance(t, base=85, floor=1)

    def execute(self, npc):
        self.refresh_announcements(npc)
        narrate(self.stage_announce[1])

        # Face the target when attacking
        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        self.prep_colors()
        glance = False
        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1
        roll = random.randint(0, 100)
        # Facing/angle damage (issue #394). This hand-rolled execute() never
        # reaches standard_execute_attack, so without this line the whole
        # positional damage curve silently skips the move.
        power = apply_facing_damage(self.user, self.target, self.power)
        # The canonical damage expression -- the one standard_execute_attack
        # runs and damage_bounds predicts: resistance, then protection, then
        # heat, then the same +/-20% band. This used to be
        # `power * uniform(0.8, 1.2) - protection`, which dropped the
        # resistance and heat terms and subtracted protection on the wrong
        # side of the roll. Two consequences: preview_damage (which has always
        # computed this line) overstated the move by the whole heat multiplier
        # -- 128-192 advertised against 64-96 dealt at heat 2.0 -- and the
        # heavy bludgeon finisher, the move whose entire role is to cash in
        # accumulated momentum, was the one attack momentum could not move.
        #
        # The variance stays here rather than in evaluate(): evaluate() runs
        # once per beat for every known move, so rolling there re-rolled the
        # move's power continuously -- the displayed power flickered and the
        # value that landed was whichever beat happened to be last.
        resistance = functions.combat_resistance(self.target, self.base_damage_type)
        damage = (
            ((power * resistance) - self.target.protection)
            * _resolve_heat(self.user)
            * random.uniform(DAMAGE_VARIANCE_MIN, DAMAGE_VARIANCE_MAX)
        )
        if damage <= 0:
            damage = 0
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                # HeavyHanded passive: apply Staggered on Bludgeon hit
                if any(
                    getattr(m, "name", "") == "Heavy Handed"
                    for m in getattr(self.user, "known_moves", [])
                ):
                    if self.target and self.target.is_alive():
                        try:
                            functions.inflict(states.Staggered(self.target), self.target)
                        except Exception:
                            pass
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost
        # Prevent negative fatigue
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class Jab(Move):
    display_name = 'Jab'
    web_animation = "quick_attack"

    def __init__(self, user):
        description = ""
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        self.target = user
        mvrange = (0, 5)
        # Seeded only so the attribute exists before evaluate() runs; evaluate()
        # replaces it with the live value on every beat.  Jab is fists-only, so
        # the seed is always a pair of fists.
        self.weapon = items.Fists()
        super().__init__(
            name="Jab",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=["This", "will", "update", "dynamically"],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=self.target,
            user=user,
            category="Offensive",
        )
        self.evaluate()

    @staticmethod
    def _is_unarmed(user):
        """True when ``user`` is genuinely fighting bare-handed.

        The engine models "unarmed" two ways: ``eq_weapon`` may be absent or
        ``None`` (most NPCs), or it may be an ``items.Fists()`` instance —
        ``Player.__init__`` equips ``self.fists`` by default and
        ``unequip_item`` restores it when a weapon comes off.  Both count.
        """
        weapon = getattr(user, "eq_weapon", None)
        if weapon is None:
            return True
        return getattr(weapon, "subtype", None) == "Unarmed"

    def current_weapon(self):
        """The weapon Jab actually swings with, read live rather than cached.

        Jab is fists-only, so this is always ``items.Fists()``-equivalent: the
        equipped weapon when it really is a pair of fists, and a fresh
        ``items.Fists()`` otherwise so that ``evaluate()`` never reports
        sword-scaled numbers for a move that cannot be cast with a sword.
        """
        weapon = getattr(self.user, "eq_weapon", None)
        if weapon is None or not self._is_unarmed(self.user):
            weapon = items.Fists()
        if not hasattr(weapon, "name"):
            weapon.name = "fists"
        return weapon

    def viable(self):
        # Jab is fists-only.  ``standard_viability_attack`` short-circuits its
        # weapon check whenever "Unarmed" is in the allowed subtypes, so it
        # cannot express "requires bare hands" on its own — gate first, then
        # defer to it for the proximity/range half of the check.
        if not self._is_unarmed(self.user):
            return False
        return self.standard_viability_attack(("Unarmed",))

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        # Read the CURRENT weapon every time.  A reference cached in
        # __init__ went stale the moment the user equipped or dropped
        # anything, which made the same named move report different power
        # depending on whether it came from the skill tree (built while Jean
        # was unarmed) or was constructed later.
        weapon = self.current_weapon()
        self.weapon = weapon
        power = (
            weapon.damage
            + (self.user.strength * weapon.str_mod)
            + (self.user.finesse * weapon.fin_mod)
        ) / 2
        # Damage type, derived the engine's own way rather than named here, so
        # execute() and preview_damage score the same term. Left unset, both
        # asked combat_resistance() about None -- the 1.0 default for every
        # target -- so a resistance-bearing enemy took an unresisted punch.
        # Note items.item_types maps no base damage type to the "Unarmed"
        # subtype, so fists fall through to "pure"; that is exactly what the
        # basic Attack scores with fists equipped, so the two stay comparable.
        self.base_damage_type = items.get_base_damage_type(weapon)
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 50 - (3 * self.user.endurance)
        if fatigue_cost <= 5:
            fatigue_cost = 5

        # IronFist passive: +25% damage when wielding Fists
        if any(
            getattr(m, "name", "") == "Iron Fist"
            for m in getattr(self.user, "known_moves", [])
        ):
            power *= 1.25

        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.refresh_announcements(self.user)

    def refresh_announcements(self, user):
        self.stage_announce = [
            "",
            colored(f"{user.name} swings a swift jab!", "red"),
            "",
            "",
        ]

    def preview_hit_chance(self, target=None):
        t = target if target is not None else self.target
        return self._standard_preview_hit_chance(t, floor=1)

    def preview_damage(self, target=None):
        """Jab's own preview, because Jab's damage is flat.

        The default preview computes the canonical expression -- resistance,
        protection, heat, +/-20% band -- which is not what ``execute()`` runs
        (see the comment there for why it deliberately is not). Left on the
        default, this move advertised 14-21 for a swing that removed 9 HP at
        heat 2.0: a 2x overstatement the player commits a beat to.

        ``_standard_preview_damage`` is called only for its gating -- passive,
        no target, dead target, not viable, out of reach -- so that this
        override stays a statement about *damage* and does not fork the rules
        about when a preview applies at all. Its numbers are then discarded
        and replaced with the flat line, reported as a single value rather
        than a band because ``execute()`` rolls no dice.
        """
        gated = self._standard_preview_damage(target)
        if gated is None:
            return None
        resolved = target if target is not None else self.target
        faced = apply_facing_damage(self.user, resolved, self.power)
        damage = int(flat_unarmed_damage(resolved, faced, self.base_damage_type))
        return preview_payload(damage, damage, resolved)

    def execute(self, npc):
        self.refresh_announcements(npc)
        narrate(self.stage_announce[1])

        # Face the target when attacking
        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        self.prep_colors()
        glance = False
        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1
        roll = random.randint(0, 100)
        # Facing/angle damage (issue #394). This hand-rolled execute() never
        # reaches standard_execute_attack, so without this line the whole
        # positional damage curve silently skips the move.
        power = apply_facing_damage(self.user, self.target, self.power)
        # Jab is deliberately NOT on the canonical damage line, and the
        # omission is the move's design rather than an oversight:
        #
        #   Unarmed trades damage capacity for tactical control. Its moves
        #   exist to stack heat; the heavy moves exist to spend it.
        #
        # Jab has the shortest cycle in the game -- one beat, no prep, no
        # recoil, no cooldown -- and ``Move.hit`` grants a flat 1.25x momentum
        # per landed hit regardless of how much damage it dealt, so Jab is
        # already the fastest heat generator by an order of magnitude: it is the
        # only move that holds the 10.0 clamp, where Attack-on-fists plateaus
        # at 1.96 and Power Strike at 1.37. Multiplying its damage by the heat
        # it uniquely generates closes that into a compounding loop -- measured
        # at 29.85 sustained damage per beat against Power Strike's 2.97, i.e.
        # 10x the finisher it is meant to be setting up. So the builder builds
        # and does not also cash in.
        #
        # What it does NOT get to skip is the target's resistances. That was a
        # separate defect with no design behind it: `power - protection` asked
        # nothing about what the target was made of. Nor may the *preview* skip
        # any of this -- preview_damage() above reports exactly this line, and
        # the whole reason this comment exists is that it once did not, quoting
        # 14-21 for a swing that removed 9 HP at heat 2.0.
        damage = flat_unarmed_damage(self.target, power, self.base_damage_type)
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost
        # Prevent negative fatigue
        if self.user.fatigue < 0:
            self.user.fatigue = 0


"""
PLAYER MOVES
"""


class IronFist(PassiveMove):
    """Passive: Conditioned hands deal more damage unarmed."""
    display_name = 'Iron Fist'

    def __init__(self, user):
        super().__init__(
            user,
            "Iron Fist",
            (
                "Your hands have been hardened through relentless training. "
                "Unarmed strikes carry greater force."
            ),
        )


class CleaveInstinct(PassiveMove):
    """Passive: A kill carries momentum into the next attack."""
    display_name = 'Cleave Instinct'

    def __init__(self, user):
        super().__init__(
            user,
            "Cleave Instinct",
            (
                "The rush of the kill carries you forward. "
                "After felling an enemy, your next strike begins with less wind-up."
            ),
        )


class HeavyHanded(PassiveMove):
    """Passive: Bludgeon blows stagger opponents — they reel longer after impact."""
    display_name = 'Heavy Handed'

    def __init__(self, user):
        super().__init__(
            user,
            "Heavy Handed",
            (
                "Your crushing blows leave enemies reeling. "
                "Bludgeon strikes impose additional stagger on their targets."
            ),
        )
