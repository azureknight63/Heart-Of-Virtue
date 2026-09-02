"""Ranged weapon moves: ShootBow, ShootCrossbow and crossbow skills; passives EagleEye, MarksmanEye."""

from src.narration import colored, cprint, narrate  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import src.states as states  # noqa: F401
import src.functions as functions  # noqa: F401
import src.items as items  # noqa: F401
import src.positions as positions  # noqa: F401
from src.animations import animate_to_main_screen as animate  # noqa: F401
from ._base import (
    apply_glancing_blow,
    resolve_pipeline_strike,
    Move,
    PassiveMove,
    _ensure_weapon_exp,
    _apply_carry_fatigue,
    _apply_to_hit_modifiers,
    apply_facing_damage,
    to_hit_chance,
    resolve_damage,
)  # noqa: F401


def _crossbow_close_range_penalty(user, range_min):
    """Return True if any enemy is within the crossbow's minimum range."""
    if not hasattr(user, "combat_proximity"):
        return False
    return any(dist < range_min for dist in user.combat_proximity.values())


def _apply_crossbow_range_decay(move, user, target, hit_chance):
    """Distance accuracy decay shared by the crossbow-family moves
    (ShootCrossbow, BroadheadBolt, AimedShot, PinningBolt): subtract
    ``move.decay`` per foot past ``move.base_range``, floored at 2.

    Factored out so each move's ``preview_hit_chance`` and ``execute()`` stay
    byte-identical to each other -- one derivation, called from both places,
    rather than two copies that can drift apart.
    """
    if target in getattr(user, "combat_proximity", {}):
        target_distance = user.combat_proximity[target]
        if target_distance > move.base_range:
            accuracy_decay = (target_distance - move.base_range) * move.decay
            hit_chance -= accuracy_decay
            if hit_chance < 2:
                hit_chance = 2
    return hit_chance


class ShootBow(
    Move
):  # ranged attack with a bow, player only. Requires having arrows in inventory;
    display_name = 'Shoot Bow'
    # this is checked when available skills are evaluated in combat.py
    web_animation = "projectile"

    def __init__(self, player):
        description = (
            "Fire an arrow at a target enemy. You must have arrows in your inventory to use. "
            "If you have multiple types of arrows, you may choose which type to fire."
        )
        prep = 10
        execute = 1
        recoil = 1  # bows do not have significant recoil
        cooldown = 3
        fatigue_cost = max(10, 100 - (2 * player.endurance))
        fatigue_cost = _apply_carry_fatigue(player, fatigue_cost)
        mvrange = (6, 50)
        super().__init__(
            name="Shoot Bow",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                f"{player.name} reaches into his quiver.",
                colored(f"{player.name} lets his arrow fly!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=player,
            verbose_targeting=True,
        )
        self.arrow = (
            items.WoodenArrow()
        )  # modified later, based on player arrow type fired;
        # arrow type chosen at prep stage
        self.power = 0
        self.base_damage_type = items.get_base_damage_type(player.eq_weapon)
        self.accuracy = 1.0
        # Seeded from the equipped weapon, not hardcoded. A literal here is what
        # let this silently drift a whole balance pass out of date: it matched
        # the Shortbow's old range_decay by coincidence, so nothing looked wrong
        # until that constant moved and the placeholder stayed put.
        wpn = getattr(player, "eq_weapon", None)
        self.base_range = getattr(wpn, "range_base", 20)
        self.decay = getattr(wpn, "range_decay", 1.5)
        self.evaluate()

    def get_effective_range_max(self, user):
        """Distance at which this shot's accuracy reaches zero.

        Uses `self.decay` -- the weapon rate scaled by the loaded arrow -- not
        the weapon's bare rate. Reading the weapon directly made the targeting
        ceiling disagree with the accuracy curve underneath it: a Shortbow with
        iron arrows allowed shots out to 87 ft while hit chance had already
        bottomed out at 62, so the last 25 ft were legal shots floored at 2%.
        """
        wpn = getattr(user, "eq_weapon", None)
        decay = self._decay_for(user)
        if wpn is None or not decay:
            return None
        # The weapon's range_base, not self.base_range: calculate_hit_chance
        # subtracts from the weapon's plateau, so zero accuracy lands there too.
        return getattr(wpn, "range_base", 0) + (100 / decay)

    def get_accuracy_falloff(self, user):
        """Falloff measured from the *weapon's* range_base, not ``self.base_range``.

        ShootBow is the one move where those two differ: ``evaluate`` folds the
        arrow's range modifier into ``self.base_range``, but
        ``calculate_hit_chance`` above subtracts from ``wpn_range_base``. This
        override reports what the hit-chance calculation actually does, since
        that — not the unused attribute — is the accuracy the player will see.
        """
        if not self.decay or self.decay <= 0:
            return None
        wpn = getattr(user, "eq_weapon", None)
        if wpn is None:
            return None
        return (getattr(wpn, "range_base", 0), self.decay)

    def calculate_hit_chance(
        self, enemy
    ):  # estimate the hit chance for enemy and return as a string (ex "48%")
        hit_chance = 2

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return hit_chance

        range_min = self.mvrange[0]
        effective_range = self.get_effective_range_max(self.user)
        if effective_range is None:
            return hit_chance
        range_max = effective_range

        if enemy not in self.user.combat_proximity:
            return hit_chance

        target_distance = self.user.combat_proximity[enemy]
        close_range_distraction = (
            0  # if any enemy is within minimum range, accuracy is halved
        )
        for e, dist in self.user.combat_proximity.items():
            if e != self.user and dist < range_min:
                close_range_distraction = 1
                break
        if (
            range_min <= target_distance <= range_max
        ):  # check if target is still in range
            hit_chance = to_hit_chance(self.user, enemy)
            hit_chance = int(hit_chance - close_range_distraction * (hit_chance / 2))
            wpn_range_base = getattr(self.user.eq_weapon, "range_base", 0)
            if target_distance > wpn_range_base:
                accuracy_decay = (target_distance - wpn_range_base) * self.decay
                hit_chance -= accuracy_decay
            # Hawkeye (#476): +40% hit chance while the buff is active.
            if any(isinstance(state, states.Hawkeye) for state in getattr(self.user, "states", [])):
                hit_chance = int(hit_chance * 1.4)
            if hit_chance < 2:  # Minimum hit chance
                hit_chance = 2
            if hit_chance > 100:  # Maximum hit chance
                hit_chance = 100
        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(self.user, enemy, hit_chance)
        return hit_chance

    def viable(self):
        viability = False
        has_bow = False
        enemy_in_range = False
        has_arrows = False

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        if not getattr(self.user, "eq_weapon", None):
            return False

        if self.user.eq_weapon.subtype == "Bow":
            has_bow = True

        range_min = self.mvrange[0]
        effective_range = self.get_effective_range_max(self.user)
        if effective_range is not None:
            range_max = effective_range
            for enemy, distance in self.user.combat_proximity.items():
                if range_min <= distance <= range_max:
                    enemy_in_range = True
                    break

        if hasattr(self.user, "inventory"):
            for item in self.user.inventory:
                if hasattr(item, "subtype"):
                    if item.subtype == "Arrow":
                        has_arrows = True
                        break

        if has_bow and enemy_in_range and has_arrows:
            viability = True
        return viability

    @staticmethod
    def _select_arrow(player):
        """The arrow this shot will use, chosen with no side effects.

        Deliberately pure: `evaluate` calls it every beat, on every known move,
        for every combatant -- `Move.advance` runs `evaluate()` before it checks
        whether the move is the current one -- so anything that narrates,
        mutates the player, or fires an effect cannot live here. `prep` calls it
        too, so the line the player reads and the effects that fire describe the
        same arrow the aim preview has been showing.

        Returns None when the quiver is empty; `viable()` already blocks the
        move in that case, but `evaluate` runs regardless of viability.
        """
        arrowtypes = [
            item
            for item in getattr(player, "inventory", [])
            # count guards a stack that has not had a chance to remove itself
            if getattr(item, "subtype", None) == "Arrow" and getattr(item, "count", 0) > 0
        ]
        if not arrowtypes:
            return None
        preferred = getattr(player, "preferences", {}).get("arrow")
        for arrow in arrowtypes:
            if arrow.name == preferred:
                return arrow
        return arrowtypes[0]

    def _decay_for(self, user, arrow=None):
        """Accuracy decay per foot for this shot: weapon rate, scaled by the
        loaded arrow and by Eagle Eye.

        The single derivation of that number. `get_effective_range_max` reads
        it live rather than trusting `self.decay`, so swapping a weapon cannot
        leave the reported reach a beat behind the accuracy it describes.
        """
        wpn = getattr(user, "eq_weapon", None)
        if wpn is None:
            return None
        decay = getattr(wpn, "range_decay", 0)
        if not decay:
            return None
        if arrow is None:
            arrow = getattr(self, "arrow", None)
        if arrow is not None:
            decay *= getattr(arrow, "range_decay_modifier", 1)
        # EagleEye passive: reduce accuracy decay at long range
        if any(
            getattr(m, "name", "") == "Eagle Eye"
            for m in getattr(user, "known_moves", [])
        ):
            decay *= 0.7
        return decay or None

    def _apply_arrow(self, player, arrow):
        """Fold the weapon and the chosen arrow into this shot's range profile.

        Recomputed from scratch every call rather than adjusted in place, so
        running it once per beat lands on the same numbers as running it once --
        Eagle Eye's multiplier in particular must not compound.
        """
        if arrow is None:
            return
        self.arrow = arrow
        wpn = getattr(player, "eq_weapon", None)
        if wpn is None:
            return
        self.base_range = wpn.range_base * arrow.range_base_modifier
        self.decay = self._decay_for(player, arrow) or 0
        # in case the arrow has a different base damage type than Piercing
        self.base_damage_type = items.get_base_damage_type(arrow)
        self.power = arrow.power

    def prep(self, player):
        arrow = self._select_arrow(player)
        if arrow is None:
            return
        self._apply_arrow(player, arrow)
        narrate(
            "{} knocks a {} and takes aim!".format(player.name, self.arrow.name.lower())
        )
        if self.arrow.effects:
            for effect in self.arrow.effects:
                if effect.trigger == "prep":
                    # Arrow effects are constructed once, with no player/move
                    # context (see FlareArrowImpact) -- rebind to this live
                    # shot before firing so process() sees the real target/user.
                    # This stays in prep, not in the shared derivation above:
                    # firing it from evaluate() would re-trigger it every beat
                    # of the aim instead of once per shot.
                    effect.move = self
                    effect.process()

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        # Derive power from the currently-selected arrow rather than resetting it
        # to 0 (issue #414). advance() calls evaluate() every beat, including the
        # beat between prep() (which loads the arrow's power) and execute(); a
        # hard reset here wiped the arrow's contribution so only the finesse term
        # ever reached the damage calc. self.arrow defaults to a WoodenArrow set
        # in __init__ and is replaced with the chosen arrow in prep().
        # Re-derive the shot's arrow and range profile every beat. Without this
        # the aim preview described the __init__ placeholder rather than the
        # arrow that would actually be loosed: a 10-beat aim reported 0.05
        # decay and a 97% hit chance for a shot that resolved at 2.1 and 45%.
        # The client's range gradient and the Check dialog both read these, and
        # both are only shown while the move is pending -- i.e. almost entirely
        # during prep, so the stale values were the ones players actually saw.
        self._apply_arrow(self.user, self._select_arrow(self.user))
        arrow = getattr(self, "arrow", None)
        power = getattr(arrow, "power", 0) if arrow is not None else 0
        prep = int(
            100 / ((self.user.speed * 0.7) + (self.user.strength * 0.3))
        )  # starting prep of 10
        if prep < 1:
            prep = 1
        execute = 1
        recoil = 1
        cooldown = 3 - int(self.user.endurance / 20)
        if cooldown < 0:
            cooldown = 0
        fatigue_cost = max(10, int(math.ceil(100 - (2 * self.user.endurance))))
        fatigue_cost = _apply_carry_fatigue(self.user, fatigue_cost)
        self.power = power
        self.stage_beat = [prep, execute, recoil, cooldown]
        self.fatigue_cost = fatigue_cost
        # Only set base_damage_type if arrow is available
        if hasattr(self, "arrow") and self.arrow:
            self.base_damage_type = items.get_base_damage_type(self.arrow)

    def preview_damage(self, target=None):
        """Shoot Bow scores the canonical damage expression, but not on
        ``self.power``: ``execute`` adds ``finesse * weapon.fin_mod`` to it
        immediately before the damage line, while ``evaluate`` — which runs
        every beat — resets it to the arrow's contribution alone. The value
        sitting on the move between beats therefore understates the shot by
        exactly that term, and a preview that read it would underprice every
        shot the player is about to take.
        """
        weapon = getattr(self.user, "eq_weapon", None)
        power = getattr(self, "power", 0) or 0
        try:
            power += float(getattr(self.user, "finesse", 0)) * float(
                getattr(weapon, "fin_mod", 0)
            )
        except (TypeError, ValueError):
            pass
        return self._standard_preview_damage(target, power=power)

    def execute(self, player):
        self.prep_colors()

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

        range_min = self.mvrange[0]
        effective_range = self.user.eq_weapon.range_base + (
            100 / self.user.eq_weapon.range_decay
        )
        range_max = effective_range
        target_distance = player.combat_proximity[self.target]
        if (
            range_min <= target_distance <= range_max
        ):  # check if target is still in range
            hit_chance = self.calculate_hit_chance(self.target)
            narrate(self.stage_announce[1])
            if self.arrow.count > 1:
                self.arrow.count -= 1
            else:
                self.user.inventory.remove(self.arrow)

        else:
            cprint(
                "Jean relaxes his bow as his target is no longer in range.",
                "green",
            )
            return
        roll = random.randint(0, 100)
        arrow_recovery = self.arrow.sturdiness
        self.power += self.user.finesse * self.user.eq_weapon.fin_mod
        # Facing/angle damage (issue #394). Applied to ranged shots on the
        # same curve as melee: the bands are a property of how well the
        # *defender* covers that angle (see positions.get_damage_modifier),
        # not of the attacker's leverage, and the accuracy half of the pair
        # already applies here through _apply_to_hit_modifiers.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = resolve_damage(player, self.target, power, self.base_damage_type)
        damage, glance = apply_glancing_blow(damage, hit_chance, roll)
        if glance:
            # A glancing arrow is more likely to survive intact.
            arrow_recovery *= 1.1
        player.combat_exp["Bow"] += 10
        arrow_location = "tile"
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                arrow_recovery *= 0.3
                self.parry()
            else:
                self.hit(damage, glance)
                arrow_location = "target"
                # Stuck arrows aren't recoverable mid-fight (issue #418) — only
                # from the corpse if the target dies (see NPCLootMixin).
                if hasattr(self.target, "embedded_arrows"):
                    self.target.embedded_arrows.append(self.arrow.__class__.__name__)
                if self.arrow.effects:
                    for effect in self.arrow.effects:
                        if effect.trigger == "execute":
                            # See prep()'s "prep" branch for why this rebind
                            # is needed before process() runs.
                            effect.move = self
                            effect.process()
        else:
            arrow_recovery *= 1.8
            self.miss()
        self.user.fatigue -= self.fatigue_cost
        if arrow_recovery >= random.random():
            # arrow survived the shot; spawn one. Only the "tile" case is handled
            # here — a "target" arrow is embedded in a living creature and is
            # recovered separately (guaranteed) if that creature later dies; see
            # NPC.drop_embedded_arrows (issue #418).
            if arrow_location == "tile":
                self.user.current_room.spawn_item(
                    self.arrow.__class__.__name__,
                    hidden=1,
                    hfactor=random.randint(40, 80),
                )


class Hawkeye(Move):
    """Bow mastery: a brief, powerful burst of ranged accuracy.

    Quick to call on (prep mirrors Dodge/Parry's snap-cast feel) but gated
    behind a long cooldown rather than AimedShot's per-use commitment, so the
    1.4x hit-chance window it grants (states.Hawkeye, 30 beats) can't be kept
    up continuously. See issue #476 for the balance reasoning.
    """
    display_name = 'Hawkeye'

    web_animation = "buff"

    def __init__(self, player):
        description = (
            "Steady your breath and sharpen your focus. Greatly increases "
            "hit chance with ranged weapons for a short time."
        )
        prep = 3
        execute = 1
        recoil = 2
        cooldown = 60
        fatigue_cost = _apply_carry_fatigue(player, max(15, 60 - (2 * player.endurance)))
        super().__init__(
            name="Hawkeye",
            description=description,
            xp_gain=3,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            stage_announce=[
                colored(f"{player.name} narrows his eyes, tracking the target's every twitch.", "yellow"),
                colored(f"{player.name}'s vision sharpens to a razor's edge!", "yellow"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=player,
            user=player,
            category="Maneuver",
        )

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        wpn = getattr(self.user, "eq_weapon", None)
        return wpn is not None and getattr(wpn, "subtype", None) == "Bow"

    def execute(self, player):
        narrate(self.stage_announce[1])
        for state in list(player.states):
            if isinstance(state, states.Hawkeye):
                player.states.remove(state)
        player.states.append(states.Hawkeye(player))
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)


"""
NPC MOVES
"""


class EagleEye(PassiveMove):
    """Passive: Sharpened long-range eye. Improves accuracy at distance."""
    display_name = 'Eagle Eye'

    def __init__(self, user):
        super().__init__(
            user,
            "Eagle Eye",
            (
                "Your eye reads distance and wind with practiced ease. "
                "Ranged attacks suffer less accuracy decay at long range."
            ),
        )


class ShootCrossbow(Move):
    """Fire a bolt from a crossbow.

    Slower reload than a bow (prep=15) but heavier bolt (higher base power).
    No arrows required — bolts are integral to the crossbow.
    Accuracy is halved if any enemy is within minimum range (close-range penalty).
    """
    display_name = 'Shoot Crossbow'

    web_animation = "projectile"

    def __init__(self, user):
        description = (
            "Fire a heavy bolt at a target. Slower to reload than a bow "
            "but hits harder. Enemies at close range disrupt your aim."
        )
        prep = 15
        execute = 1
        recoil = 2
        cooldown = 5
        fatigue_cost = _apply_carry_fatigue(user, max(10, 100 - (2 * user.endurance)))
        super().__init__(
            name="Shoot Crossbow",
            description=description,
            xp_gain=3,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(6, 40),
            stage_announce=[
                f"{user.name} cranks the crossbow and loads a bolt.",
                colored(f"{user.name} fires his crossbow!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.base_range = 15
        self.decay = 0.06
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Crossbow":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        rmin, rmax = self.mvrange
        return any(rmin <= dist <= rmax for dist in self.user.combat_proximity.values())

    def get_effective_range_max(self, user):
        """Return the effective maximum range, accounting for base_range and decay."""
        if self.decay and self.decay > 0:
            return self.base_range + (100 / self.decay)
        return None

    def evaluate(self):
        wpn = getattr(self.user, "eq_weapon", None)
        if not wpn:
            self.power = 0
            self.fatigue_cost = 10
            return
        self.power = max(
            1,
            wpn.damage
            + 15
            + int(self.user.strength * wpn.str_mod)
            + int(self.user.finesse * wpn.fin_mod),
        )
        self.fatigue_cost = _apply_carry_fatigue(self.user, max(10, 100 - (2 * self.user.endurance)))
        # mvrange stays static; effective range comes from range_base/decay via get_effective_range_max
        # Initialize range/decay from weapon (handle MagicMock in tests)
        range_base = getattr(wpn, "range_base", 15)
        if isinstance(range_base, (int, float)):
            self.base_range = range_base
        decay = getattr(wpn, "range_decay", 0.06)
        if isinstance(decay, (int, float)):
            self.decay = decay
        # MarksmanEye passive: reduce accuracy decay at range
        if any(
            getattr(m, "name", "") == "Marksman's Eye"
            for m in getattr(self.user, "known_moves", [])
        ):
            self.decay *= 0.7

    def preview_hit_chance(self, target=None):
        t = target if target is not None else self.target
        if not self._viable_for(t):
            return None
        hit_chance = to_hit_chance(self.user, t, floor=5)
        if _crossbow_close_range_penalty(self.user, self.mvrange[0]):
            hit_chance = int(hit_chance * 0.5)
        hit_chance = _apply_crossbow_range_decay(self, self.user, t, hit_chance)
        return _apply_to_hit_modifiers(self.user, t, hit_chance)

    def execute(self, player):
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

        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1

        roll = random.randint(0, 100)
        # Facing/angle damage (issue #394). Applied to ranged shots on the
        # same curve as melee: the bands are a property of how well the
        # *defender* covers that angle (see positions.get_damage_modifier),
        # not of the attacker's leverage, and the accuracy half of the pair
        # already applies here through _apply_to_hit_modifiers.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = resolve_damage(player, self.target, power, self.base_damage_type)
        damage, glance = apply_glancing_blow(damage, hit_chance, roll)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5

        resolve_pipeline_strike(self, damage, glance, hit_chance, roll)

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class BroadheadBolt(Move):
    """Fire a heavy broadhead bolt — high damage, same reload as ShootCrossbow."""
    display_name = 'Broadhead Bolt'

    web_animation = "projectile"

    def __init__(self, user):
        description = (
            "Load and fire a wide broadhead bolt designed for maximum damage. "
            "The head tears a wide wound on impact."
        )
        prep = 15
        execute = 1
        recoil = 2
        cooldown = 6
        fatigue_cost = _apply_carry_fatigue(user, max(10, 110 - (2 * user.endurance)))
        super().__init__(
            name="Broadhead Bolt",
            description=description,
            xp_gain=8,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(6, 40),
            stage_announce=[
                f"{user.name} loads a broadhead bolt...",
                colored(f"{user.name} fires a broadhead bolt!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.base_range = 15
        self.decay = 0.06
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Crossbow":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        rmin, rmax = self.mvrange
        return any(rmin <= dist <= rmax for dist in self.user.combat_proximity.values())

    def get_effective_range_max(self, user):
        """Return the effective maximum range, accounting for base_range and decay."""
        if self.decay and self.decay > 0:
            return self.base_range + (100 / self.decay)
        return None

    def evaluate(self):
        wpn = getattr(self.user, "eq_weapon", None)
        if not wpn:
            self.power = 0
            self.fatigue_cost = 15
            return
        self.power = max(
            1,
            wpn.damage
            + 25
            + int(self.user.strength * wpn.str_mod)
            + int(self.user.finesse * wpn.fin_mod),
        )
        self.fatigue_cost = _apply_carry_fatigue(self.user, max(15, 110 - (2 * self.user.endurance)))
        # mvrange stays static; effective range comes from range_base/decay via get_effective_range_max
        # Initialize range/decay from weapon (handle MagicMock in tests)
        range_base = getattr(wpn, "range_base", 15)
        if isinstance(range_base, (int, float)):
            self.base_range = range_base
        decay = getattr(wpn, "range_decay", 0.06)
        if isinstance(decay, (int, float)):
            self.decay = decay
        # MarksmanEye passive: reduce accuracy decay at range
        if any(
            getattr(m, "name", "") == "Marksman's Eye"
            for m in getattr(self.user, "known_moves", [])
        ):
            self.decay *= 0.7

    def preview_hit_chance(self, target=None):
        """Broadhead Bolt applies distance decay but -- unlike ShootCrossbow
        and PinningBolt -- does NOT apply the crossbow close-range penalty;
        this mirrors execute() exactly (see the missing
        ``_crossbow_close_range_penalty`` call there)."""
        t = target if target is not None else self.target
        if not self._viable_for(t):
            return None
        hit_chance = to_hit_chance(self.user, t, floor=5)
        hit_chance = _apply_crossbow_range_decay(self, self.user, t, hit_chance)
        return _apply_to_hit_modifiers(self.user, t, hit_chance)

    def execute(self, player):
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

        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1

        roll = random.randint(0, 100)
        # Facing/angle damage (issue #394). Applied to ranged shots on the
        # same curve as melee: the bands are a property of how well the
        # *defender* covers that angle (see positions.get_damage_modifier),
        # not of the attacker's leverage, and the accuracy half of the pair
        # already applies here through _apply_to_hit_modifiers.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = resolve_damage(player, self.target, power, self.base_damage_type)
        damage, glance = apply_glancing_blow(damage, hit_chance, roll)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 10
        player.combat_exp["Basic"] += 5

        resolve_pipeline_strike(self, damage, glance, hit_chance, roll)

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class AimedShot(Move):
    """Slow, deliberate aimed shot — +50% power and +15 accuracy on top of base.

    Takes 25 beats to line up. Worth the wait against high-finesse targets or
    when one decisive shot is needed.
    """
    display_name = 'Aimed Shot'

    web_animation = "projectile"

    def __init__(self, user):
        description = (
            "Take careful aim for an extended time before firing. "
            "+50% damage and improved accuracy — but you are exposed while aiming."
        )
        prep = 25
        execute = 1
        recoil = 2
        cooldown = 8
        fatigue_cost = _apply_carry_fatigue(user, max(10, 90 - (2 * user.endurance)))
        super().__init__(
            name="Aimed Shot",
            description=description,
            xp_gain=15,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(6, 40),
            stage_announce=[
                f"{user.name} raises the crossbow and begins to aim...",
                colored(f"{user.name} fires a perfectly aimed shot!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.base_range = 15
        self.decay = 0.06
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Crossbow":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        rmin, rmax = self.mvrange
        return any(rmin <= dist <= rmax for dist in self.user.combat_proximity.values())

    def get_effective_range_max(self, user):
        """Return the effective maximum range, accounting for base_range and decay."""
        if self.decay and self.decay > 0:
            return self.base_range + (100 / self.decay)
        return None

    def evaluate(self):
        wpn = getattr(self.user, "eq_weapon", None)
        if not wpn:
            self.power = 0
            self.fatigue_cost = 10
            return
        base = (
            wpn.damage
            + 15
            + int(self.user.strength * wpn.str_mod)
            + int(self.user.finesse * wpn.fin_mod)
        )
        self.power = max(1, int(base * 1.5))
        self.fatigue_cost = _apply_carry_fatigue(self.user, max(10, 90 - (2 * self.user.endurance)))
        # mvrange stays static; effective range comes from range_base/decay via get_effective_range_max
        # Initialize range/decay from weapon (handle MagicMock in tests)
        range_base = getattr(wpn, "range_base", 15)
        if isinstance(range_base, (int, float)):
            self.base_range = range_base
        decay = getattr(wpn, "range_decay", 0.06)
        if isinstance(decay, (int, float)):
            self.decay = decay
        # MarksmanEye passive: reduce accuracy decay at range
        if any(
            getattr(m, "name", "") == "Marksman's Eye"
            for m in getattr(self.user, "known_moves", [])
        ):
            self.decay *= 0.7

    def preview_hit_chance(self, target=None):
        t = target if target is not None else self.target
        if not self._viable_for(t):
            return None
        hit_chance = min(100, max(5, to_hit_chance(self.user, t) + 15))
        if _crossbow_close_range_penalty(self.user, self.mvrange[0]):
            hit_chance = int(hit_chance * 0.5)
        hit_chance = _apply_crossbow_range_decay(self, self.user, t, hit_chance)
        return _apply_to_hit_modifiers(self.user, t, hit_chance)

    def execute(self, player):
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

        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1

        roll = random.randint(0, 100)
        # Facing/angle damage (issue #394). Applied to ranged shots on the
        # same curve as melee: the bands are a property of how well the
        # *defender* covers that angle (see positions.get_damage_modifier),
        # not of the attacker's leverage, and the accuracy half of the pair
        # already applies here through _apply_to_hit_modifiers.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = resolve_damage(player, self.target, power, self.base_damage_type)
        damage, glance = apply_glancing_blow(damage, hit_chance, roll)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 10
        player.combat_exp["Basic"] += 5

        resolve_pipeline_strike(self, damage, glance, hit_chance, roll)

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class PinningBolt(Move):
    """Bolt aimed to pin the target — deals damage and applies Disoriented on hit."""
    display_name = 'Pinning Bolt'

    web_animation = "projectile"

    def __init__(self, user):
        description = (
            "Fire a bolt aimed to pin or impede the target. "
            "On a hit, the target is disoriented and their movement impaired."
        )
        prep = 15
        execute = 1
        recoil = 2
        cooldown = 6
        fatigue_cost = _apply_carry_fatigue(user, max(10, 100 - (2 * user.endurance)))
        super().__init__(
            name="Pinning Bolt",
            description=description,
            xp_gain=10,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(6, 40),
            stage_announce=[
                f"{user.name} loads a bolt meant to pin...",
                colored(f"{user.name} fires a pinning bolt!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.base_range = 15
        self.decay = 0.06
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Crossbow":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        rmin, rmax = self.mvrange
        return any(rmin <= dist <= rmax for dist in self.user.combat_proximity.values())

    def get_effective_range_max(self, user):
        """Return the effective maximum range, accounting for base_range and decay."""
        if self.decay and self.decay > 0:
            return self.base_range + (100 / self.decay)
        return None

    def evaluate(self):
        wpn = getattr(self.user, "eq_weapon", None)
        if not wpn:
            self.power = 0
            self.fatigue_cost = 10
            return
        self.power = max(
            1,
            wpn.damage
            + 10
            + int(self.user.strength * wpn.str_mod)
            + int(self.user.finesse * wpn.fin_mod),
        )
        self.fatigue_cost = _apply_carry_fatigue(self.user, max(10, 100 - (2 * self.user.endurance)))
        # mvrange stays static; effective range comes from range_base/decay via get_effective_range_max
        # Initialize range/decay from weapon (handle MagicMock in tests)
        range_base = getattr(wpn, "range_base", 15)
        if isinstance(range_base, (int, float)):
            self.base_range = range_base
        decay = getattr(wpn, "range_decay", 0.06)
        if isinstance(decay, (int, float)):
            self.decay = decay
        # MarksmanEye passive: reduce accuracy decay at range
        if any(
            getattr(m, "name", "") == "Marksman's Eye"
            for m in getattr(self.user, "known_moves", [])
        ):
            self.decay *= 0.7

    def preview_hit_chance(self, target=None):
        t = target if target is not None else self.target
        if not self._viable_for(t):
            return None
        hit_chance = to_hit_chance(self.user, t, floor=5)
        if _crossbow_close_range_penalty(self.user, self.mvrange[0]):
            hit_chance = int(hit_chance * 0.5)
        hit_chance = _apply_crossbow_range_decay(self, self.user, t, hit_chance)
        return _apply_to_hit_modifiers(self.user, t, hit_chance)

    def execute(self, player):
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

        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1

        roll = random.randint(0, 100)
        # Facing/angle damage (issue #394). Applied to ranged shots on the
        # same curve as melee: the bands are a property of how well the
        # *defender* covers that angle (see positions.get_damage_modifier),
        # not of the attacker's leverage, and the accuracy half of the pair
        # already applies here through _apply_to_hit_modifiers.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = resolve_damage(player, self.target, power, self.base_damage_type)
        damage, glance = apply_glancing_blow(damage, hit_chance, roll)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 6
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
                            self.target.states.append(states.Disoriented(self.target))
                            cprint(
                                f"{self.target.name} is pinned and disoriented!", "red"
                            )
                        except Exception:
                            pass
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class QuickReload(PassiveMove):
    """Passive: Crossbow reload training reduces prep time."""
    display_name = 'Quick Reload'

    def __init__(self, user):
        description = (
            "Practiced hands load faster. "
            "Crossbow attacks require fewer beats to reload."
        )
        super().__init__(user, "Quick Reload", description)


class MarksmanEye(PassiveMove):
    """Passive: Accuracy bonus at range for crossbow attacks."""
    display_name = "Marksman's Eye"

    def __init__(self, user):
        super().__init__(
            user,
            "Marksman's Eye",
            (
                "Distance doesn't shake your aim. "
                "Crossbow shots maintain accuracy further out."
            ),
        )
