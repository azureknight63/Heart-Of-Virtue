"""Mastery moves — one per stat. Unlock when the stat exceeds 30 and is the player's highest."""

from src.narration import colored, cprint, narrate
import random
import src.states as states
import src.functions as functions
from ._base import (
    Move,
    OUTCOME_ABSORB,
    OUTCOME_HIT,
    _ensure_weapon_exp,
    _apply_to_hit_modifiers,
    apply_facing_damage,
    damage_bounds,
    preview_payload,
    projected_hit_heat_sequence,
    publish_outcome,
    to_hit_chance,
    resolve_damage,
    target_protection,
)


def _all_stats(p):
    return [
        p.strength,
        p.finesse,
        p.speed,
        p.endurance,
        p.charisma,
        p.intelligence,
        p.faith,
    ]


def _is_highest(p, stat_val):
    stats = _all_stats(p)
    highest = max(stats)
    return stat_val == highest and stats.count(highest) == 1


def _proximity_of(user):
    """The user's ``combat_proximity`` when it is a real distance mapping.

    Returns ``None`` when the user carries no usable proximity data (a
    combatant not yet wired into a fight, or a degraded/mock user). Callers
    read that as *range unknown* and decline to block, the same trust rule
    ``Move._hostiles_in_proximity`` applies to a missing ``combat_list``:
    a gate that fires on absent information would silently disable the move
    outside real combat.
    """
    proximity = getattr(user, "combat_proximity", None)
    return proximity if isinstance(proximity, dict) else None


def _reaches(move, target):
    """True when ``target`` stands inside ``move.mvrange``.

    Bounds are **inclusive at both ends** — ``range_min <= distance <=
    range_max`` — matching ``Move.standard_viability_attack``. A move that
    used strict bounds would be uncastable at exactly its own stated reach.

    A target absent from a populated ``combat_proximity`` is out of range,
    not unknown: the player's proximity map holds every combatant in the
    fight, so a miss there means the pair has no measured distance.
    """
    proximity = _proximity_of(move.user)
    if proximity is None:
        return True
    if target is None or target is move.user:
        return False
    distance = proximity.get(target)
    if distance is None:
        return False
    range_min, range_max = move.mvrange
    return range_min <= distance <= range_max


def _in_range(move):
    """Reachability half of a targeted mastery move's ``viable()``.

    None of the mastery moves checked ``mvrange`` at all, so every one of
    the three targeted ones was castable — and, for Killing Precision, a
    guaranteed hit — against a combatant at any distance the client cared
    to name.

    When a target is already committed (``move.target`` is some combatant
    other than the user: the adapter assigns it before ``execute()``, and
    ``Move._viable_for`` swaps one in for a per-target preview) the gate is
    that target's own distance. Before a target is committed the move is
    offered whenever *some* hostile stands inside the band, which is what
    ``standard_viability_attack`` does; allies are excluded via
    ``Move._hostiles_in_proximity`` so a friend standing next to Jean
    cannot make an attack look reachable.
    """
    target = move.target
    if target is not None and target is not move.user:
        return _reaches(move, target)
    if _proximity_of(move.user) is None:
        return True
    range_min, range_max = move.mvrange
    return any(
        range_min <= distance <= range_max
        for _, distance in move._hostiles_in_proximity()
    )


def _mastery_strike_power(move, default=None):
    """The power expression the three striking masteries score inside
    ``execute()``: ``int(weapon.damage * a + stat * b)``, with the
    coefficients read off the move itself — its ``WEAPON_FACTOR``,
    ``STAT_NAME`` and ``STAT_FACTOR`` class attributes, declared together so
    a retune is one edit beside the move.

    They never set ``self.power`` — the number exists only at strike time —
    so their previews must recompute it from the same live reads, through
    this one derivation rather than a per-move copy. Returns ``default`` when
    the reads cannot produce a number (no weapon, or garbage on a degraded
    save): previews leave it ``None`` and degrade to "no estimate", while
    ``execute()`` passes ``default=0`` to score a null strike rather than
    raise mid-beat.
    """
    weapon = getattr(move.user, "eq_weapon", None)
    if weapon is None:
        return default
    try:
        return int(
            float(getattr(weapon, "damage", 0)) * move.WEAPON_FACTOR
            + float(getattr(move.user, move.STAT_NAME, 0)) * move.STAT_FACTOR
        )
    except (TypeError, ValueError, OverflowError):
        return default


class Pulverize(Move):
    """Strength mastery: devastating overhead blow that ignores all protection."""

    display_name = "Pulverize"

    web_animation = "heavy_attack"
    #: The damage type execute() scores with — declared so the default
    #: preview machinery reads the same resistance term the strike applies.
    base_damage_type = "crushing"
    #: Power expression coefficients: ``int(weapon.damage * WEAPON_FACTOR +
    #: STAT_NAME * STAT_FACTOR)`` — one derivation, read by execute() and
    #: preview_damage() both (see _mastery_strike_power).
    WEAPON_FACTOR = 1.8
    STAT_NAME = "strength"
    STAT_FACTOR = 3.0

    def __init__(self, player):
        super().__init__(
            name="Pulverize",
            description=(
                "A thunderous overhead blow that shatters armor entirely and leaves the target "
                "reeling with resonant damage. Only available when Strength is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=True,
            stage_beat=[2, 1, 4, 35],
            stage_announce=[
                colored(
                    f"{player.name} raises his weapon high, drawing on every ounce of strength.",
                    "red",
                ),
                colored(f"{player.name} drives down a crushing blow!", "red"),
                colored(
                    f"{player.name} steadies himself after the devastating strike.",
                    "yellow",
                ),
                "",
            ],
            fatigue_cost=90,
            beats_left=2,
            target=player,
            user=player,
            category="Mastery",
            mvrange=(0, 5),
        )

    #: Canonical timing, re-seeded every beat by evaluate() so a
    #: parry stagger cannot accumulate across uses.
    STAGE_BEATS = tuple([2, 1, 4, 35])

    def evaluate(self):
        """Re-seed the timing each beat.

        ``Move.parry()`` does ``self.stage_beat[2] += 10`` to stagger a
        parried attacker. Moves built through ``standard_evaluate_attack``
        have that erased by the fresh list it assigns every beat; this
        move carries a literal timing, so without re-seeding the penalty
        accumulated permanently and was pickled into the save with
        ``known_moves``. Only the three mastery moves that actually call
        ``parry()`` need this.
        """
        self.stage_beat = list(self.STAGE_BEATS)

    def learnable_when(self, player):
        return player.strength > 30 and _is_highest(player, player.strength)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        if not _is_highest(self.user, self.user.strength):
            return False
        # Reachability: a targeted strike is not castable against a
        # combatant outside mvrange (see _in_range).
        return _in_range(self)

    def preview_damage(self, target=None):
        """Pulverize scores its power at strike time and never sets
        ``self.power``, so the default preview reported None and the player
        committed a long cooldown blind. (The same strike-time-power story
        holds for Killing Precision and Lightning Assault, whose previews
        point here rather than repeating it.) Same power derivation as
        execute() (see _mastery_strike_power), same ``protection=0``
        armour-ignoring override.
        """
        power = _mastery_strike_power(self)
        if power is None:
            return None
        return self._standard_preview_damage(target, power=power, protection=0)

    def execute(self, player):
        self.prep_colors()
        narrate(self.stage_announce[1])
        target = self.target
        # Reachability re-check at strike time: a target that has left the
        # move's band during its wind-up — or one the client named directly,
        # bypassing the range-filtered target list — cannot be struck. Mirrors
        # the `if self.viable()` / `hit_chance = -1` auto-miss that
        # `Move.standard_execute_attack` applies in _base.py, but scoped to
        # range alone: the stat-dominance half of viable() can flip mid-move
        # (Secret Plans buffs strength/finesse/speed by 30%), and a buff must
        # not turn a landed strike into a miss.
        if _reaches(self, target):
            hit_chance = to_hit_chance(player, target, floor=5)
        else:
            hit_chance = -1
        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(player, target, hit_chance)
        roll = random.randint(0, 100)
        # One derivation, shared with preview_damage. A degraded read (no
        # weapon on a crafted save) scores 0 rather than raising mid-beat.
        power = _mastery_strike_power(self, default=0)
        # Facing/angle damage (issue #394). This hand-rolled execute() never
        # reaches standard_execute_attack, so without this line the whole
        # positional damage curve silently skips the move.
        power = apply_facing_damage(player, target, power)
        # The canonical damage expression (see _base.resolve_damage), with the
        # protection term overridden to zero: Pulverize ignores armour
        # entirely, which is the whole identity of the strength mastery.
        # Resistance is read through functions.combat_resistance rather than
        # target.resistance.get(): the shared choke point falls back to
        # resistance_base and coerces a non-finite multiplier, where the raw
        # dict read raised on a target carrying no resistance mapping at all.
        damage = int(resolve_damage(player, target, power, "crushing", protection=0))
        _ensure_weapon_exp(player)
        player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
        if hit_chance >= roll:
            if functions.check_parry(target):
                self.parry()
            else:
                self.hit(damage, False)
                functions.inflict(states.Resonant(target), target, force=True)
        else:
            self.miss()


class KillingPrecision(Move):
    """Finesse mastery: surgically unerring strike that never misses."""

    display_name = "Killing Precision"

    web_animation = "pierce"
    #: The damage type execute() scores with — declared so the default
    #: preview machinery reads the same resistance term the strike applies.
    base_damage_type = "piercing"
    #: Power expression coefficients — see _mastery_strike_power.
    WEAPON_FACTOR = 1.5
    STAT_NAME = "finesse"
    STAT_FACTOR = 2.5
    #: Fraction of the target's protection the strike scores.
    PROTECTION_SCALE = 0.2

    def __init__(self, player):
        super().__init__(
            name="Killing Precision",
            description=(
                "A surgically precise thrust that never misses, ignores 80% of armor, "
                "and ignites your heat. Only available when Finesse is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=True,
            stage_beat=[1, 1, 2, 30],
            stage_announce=[
                colored(
                    f"{player.name} centres his breathing and locates the gap.", "cyan"
                ),
                colored(f"{player.name} drives a perfect, unerring strike!", "cyan"),
                colored(f"{player.name} withdraws, composure intact.", "yellow"),
                "",
            ],
            fatigue_cost=75,
            beats_left=1,
            target=player,
            user=player,
            category="Mastery",
            mvrange=(0, 5),
        )

    #: Canonical timing, re-seeded every beat by evaluate() so a
    #: parry stagger cannot accumulate across uses.
    STAGE_BEATS = tuple([1, 1, 2, 30])

    def evaluate(self):
        """Re-seed the timing each beat.

        ``Move.parry()`` does ``self.stage_beat[2] += 10`` to stagger a
        parried attacker. Moves built through ``standard_evaluate_attack``
        have that erased by the fresh list it assigns every beat; this
        move carries a literal timing, so without re-seeding the penalty
        accumulated permanently and was pickled into the save with
        ``known_moves``. Only the three mastery moves that actually call
        ``parry()`` need this.
        """
        self.stage_beat = list(self.STAGE_BEATS)

    def learnable_when(self, player):
        return player.finesse > 30 and _is_highest(player, player.finesse)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        if not _is_highest(self.user, self.user.finesse):
            return False
        # Reachability: a targeted strike is not castable against a
        # combatant outside mvrange (see _in_range).
        return _in_range(self)

    def preview_hit_chance(self, target=None):
        """Killing Precision never misses (see execute(): no roll, no
        to_hit_chance call) -- a viable cast is a guaranteed 100% hit."""
        t = target if target is not None else self.target
        return 100 if self._viable_for(t) else None

    def preview_damage(self, target=None):
        """Same strike-time-power story as ``Pulverize.preview_damage`` (the
        default preview reported None); same fifth-of-protection override as
        execute(), same ``max(1, ...)`` floor: a viable cast always deals at
        least 1, and a preview reporting 0-0 for it would promise an absorb
        the engine cannot produce.
        """
        power = _mastery_strike_power(self)
        if power is None:
            return None
        resolved = target if target is not None else getattr(self, "target", None)
        if resolved is None or resolved is self.user:
            # Cheap gates first; the protection read below is only worth
            # taking for a resolvable target.
            return None
        gated = self._standard_preview_damage(
            resolved,
            power=power,
            protection=target_protection(resolved) * self.PROTECTION_SCALE,
        )
        if gated is None:
            return None
        return preview_payload(max(1, gated["min"]), max(1, gated["max"]), resolved)

    def execute(self, player):
        self.prep_colors()
        narrate(self.stage_announce[1])
        target = self.target
        # One derivation, shared with preview_damage. A degraded read (no
        # weapon on a crafted save) scores 0 rather than raising mid-beat.
        power = _mastery_strike_power(self, default=0)
        # Facing/angle damage (issue #394). The guaranteed hit is an
        # *accuracy* guarantee — there is no roll for the accuracy half of
        # the pair to modify — but the damage half still applies. Exempting
        # it would make Killing Precision the only move that dodges the 0.85
        # frontal penalty, i.e. the best head-on option in the game and an
        # active incentive not to position.
        power = apply_facing_damage(player, target, power)
        # The canonical damage expression with only a fifth of the target's
        # armour scored — see _base.resolve_damage, and Pulverize above for
        # why resistance now goes through functions.combat_resistance.
        damage = max(
            1,
            int(
                resolve_damage(
                    player,
                    target,
                    power,
                    "piercing",
                    protection=target_protection(target) * self.PROTECTION_SCALE,
                )
            ),
        )
        _ensure_weapon_exp(player)
        player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
        # Always hits — no roll, but parry can still work. The guarantee is
        # deliberate (an endgame payoff gated behind finesse > 30) and is NOT
        # weakened here; it is only made conditional on the target being
        # reachable, which the move never checked. Without this, a client that
        # named any combatant — at any distance — got a guaranteed >= 1 damage
        # hit, since damage is floored at 1 and no roll exists to fail.
        if not _reaches(self, target):
            self.miss()
        elif functions.check_parry(target):
            self.parry()
        else:
            self.hit(damage, False)


class LightningAssault(Move):
    """Speed mastery: three rapid strikes; Disoriented if all land."""

    display_name = "Lightning Assault"

    web_animation = "quick_attack"
    #: The damage type execute() scores with — declared so the default
    #: preview machinery reads the same resistance term the strikes apply.
    base_damage_type = "slashing"
    #: Power expression coefficients (per strike) — see _mastery_strike_power.
    WEAPON_FACTOR = 0.55
    STAT_NAME = "speed"
    STAT_FACTOR = 0.75
    STRIKES = 3

    def __init__(self, player):
        super().__init__(
            name="Lightning Assault",
            description=(
                "Three consecutive strikes so fast they blur into one lethal instant. "
                "If all three land, the target is left Disoriented. "
                "Only available when Speed is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=True,
            stage_beat=[1, 1, 1, 30],
            stage_announce=[
                colored(
                    f"{player.name} shifts his weight and explodes forward.", "cyan"
                ),
                colored(f"{player.name} unleashes a blinding flurry of blows!", "cyan"),
                colored(f"{player.name} resets his stance.", "yellow"),
                "",
            ],
            fatigue_cost=70,
            beats_left=1,
            target=player,
            user=player,
            category="Mastery",
            mvrange=(0, 5),
        )

    #: Canonical timing, re-seeded every beat by evaluate() so a
    #: parry stagger cannot accumulate across uses.
    STAGE_BEATS = tuple([1, 1, 1, 30])

    def evaluate(self):
        """Re-seed the timing each beat.

        ``Move.parry()`` does ``self.stage_beat[2] += 10`` to stagger a
        parried attacker. Moves built through ``standard_evaluate_attack``
        have that erased by the fresh list it assigns every beat; this
        move carries a literal timing, so without re-seeding the penalty
        accumulated permanently and was pickled into the save with
        ``known_moves``. Only the three mastery moves that actually call
        ``parry()`` need this.
        """
        self.stage_beat = list(self.STAGE_BEATS)

    def learnable_when(self, player):
        return player.speed > 30 and _is_highest(player, player.speed)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        if not _is_highest(self.user, self.user.speed):
            return False
        # Reachability: a targeted strike is not castable against a
        # combatant outside mvrange (see _in_range).
        return _in_range(self)

    def _flurry_heats(self):
        """The heat each of the three strikes is actually scored with — see
        ``_base.projected_hit_heat_sequence`` for why the heat feedback
        between strikes belongs in the preview.
        """
        return projected_hit_heat_sequence(self.user, self.STRIKES)

    def preview_damage(self, target=None):
        """Same strike-time-power story as ``Pulverize.preview_damage`` (the
        default preview reported None). The band is the full flurry with all
        three strikes landing — each strike ``int()``s its own damage, so the
        ends are per-strike bounds summed, at the heat each strike really
        runs at (see ``_flurry_heats``). A strike that lands but is fully
        absorbed takes ``Move.hit``'s 0.75x heat branch, where this replay
        assumes the 1.25x landed-hit reward for every strike.

        The gate call IS strike one: ``_standard_preview_damage`` with
        ``heat`` left None scores at ``_resolve_heat(user, None)``, which is
        exactly ``_flurry_heats()``'s first entry, so its payload is reused
        rather than repriced — and the armour read is hoisted once and passed
        into every bounds call instead of being re-resolved per strike. This
        preview runs on every combat poll.
        """
        power = _mastery_strike_power(self)
        if power is None:
            return None
        resolved = target if target is not None else getattr(self, "target", None)
        protection = target_protection(resolved)
        gate = self._standard_preview_damage(
            resolved, power=power, protection=protection
        )
        if gate is None:
            return None
        low, high = gate["min"], gate["max"]
        for heat in self._flurry_heats()[1:]:
            strike_low, strike_high = damage_bounds(
                self.user,
                resolved,
                power,
                self.base_damage_type,
                heat=heat,
                protection=protection,
            )
            low += strike_low
            high += strike_high
        return preview_payload(low, high, resolved)

    def execute(self, player):
        self.prep_colors()
        narrate(self.stage_announce[1])
        target = self.target
        # Reachability re-check at strike time: a target that has left the
        # move's band during its wind-up — or one the client named directly,
        # bypassing the range-filtered target list — cannot be struck. Mirrors
        # the `if self.viable()` / `hit_chance = -1` auto-miss that
        # `Move.standard_execute_attack` applies in _base.py, but scoped to
        # range alone: the stat-dominance half of viable() can flip mid-move
        # (Secret Plans buffs strength/finesse/speed by 30%), and a buff must
        # not turn a landed strike into a miss.
        if _reaches(self, target):
            hit_chance = to_hit_chance(player, target, floor=5)
        else:
            hit_chance = -1
        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(player, target, hit_chance)
        _ensure_weapon_exp(player)
        player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
        hits_landed = 0
        # One derivation, shared with preview_damage. A degraded read (no
        # weapon on a crafted save) scores 0 rather than raising mid-beat.
        # Hoisted above the loop: nothing it reads changes between strikes.
        base_power = _mastery_strike_power(self, default=0)
        for _ in range(self.STRIKES):
            roll = random.randint(0, 100)
            # Facing/angle damage (issue #394). Inside the loop rather than
            # hoisted: a future strike that repositions mid-flurry should be
            # scored where it lands.
            power = apply_facing_damage(player, target, base_power)
            damage = int(resolve_damage(player, target, power, "slashing"))
            if hit_chance >= roll:
                if functions.check_parry(target):
                    self.parry()
                else:
                    self.hit(damage, False)
                    hits_landed += 1
                    if not target.is_alive():
                        break
            else:
                self.miss()
        if hits_landed == self.STRIKES:
            functions.inflict(states.Disoriented(target), target, force=True)
            cprint(
                f"{target.name} is left reeling from the relentless assault!", "yellow"
            )


class Ironhide(Move):
    """Endurance mastery: purge ailments, recover HP and fatigue."""

    display_name = "Ironhide"

    web_animation = "defend"

    def __init__(self, player):
        super().__init__(
            name="Ironhide",
            description=(
                "Dig in with sheer grit — heal 30% of max HP, purge all active ailments, "
                "and restore 60 fatigue. "
                "Only available when Endurance is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=False,
            stage_beat=[1, 1, 1, 40],
            stage_announce=[
                colored(
                    f"{player.name} sets his jaw and braces against the pain.", "yellow"
                ),
                colored(
                    f"{player.name} refuses to fall — sheer will closes his wounds!",
                    "yellow",
                ),
                colored(
                    f"{player.name} exhales, tension bleeding out of his frame.",
                    "yellow",
                ),
                "",
            ],
            fatigue_cost=25,
            beats_left=1,
            target=player,
            user=player,
            category="Mastery",
        )

    def learnable_when(self, player):
        return player.endurance > 30 and _is_highest(player, player.endurance)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        return _is_highest(self.user, self.user.endurance)

    def execute(self, player):
        narrate(self.stage_announce[1])
        heal = int(player.maxhp * 0.30)
        player.hp = min(player.hp + heal, player.maxhp)
        cprint(f"{player.name} recovers {heal} HP!", "green")
        # Purge negative ailment types
        negative_types = {"poison", "stun", "stone", "disoriented", "enflamed"}
        removed = [
            s for s in player.states if getattr(s, "statustype", "") in negative_types
        ]
        for state in removed:
            player.states.remove(state)
            if hasattr(state, "on_removal"):
                try:
                    state.on_removal(player)
                except Exception:
                    pass
        if removed:
            cprint(f"All ailments purged from {player.name}!", "green")
        player.fatigue = min(player.fatigue + 60, player.maxfatigue)
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
        functions.refresh_stat_bonuses(player)


class WarCry(Move):
    """Charisma mastery: interrupts all winding enemy moves and stuns for 1 beat."""

    display_name = "War Cry"

    web_animation = "buff"

    def __init__(self, player):
        super().__init__(
            name="War Cry",
            description=(
                "A thunderous battle command that interrupts every enemy's winding move "
                "and stuns the entire field for one beat. "
                "Only available when Charisma is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=False,
            stage_beat=[1, 1, 2, 30],
            stage_announce=[
                colored(f"{player.name} draws breath for a battle command.", "magenta"),
                colored(
                    f"{player.name} unleashes a war cry that shakes the field!",
                    "magenta",
                ),
                colored(f"{player.name} surveys the stunned field.", "yellow"),
                "",
            ],
            fatigue_cost=60,
            beats_left=1,
            target=player,
            user=player,
            category="Mastery",
        )

    def learnable_when(self, player):
        return player.charisma > 30 and _is_highest(player, player.charisma)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        return _is_highest(self.user, self.user.charisma)

    def execute(self, player):
        narrate(self.stage_announce[1])
        affected = 0
        for enemy in list(getattr(player, "combat_list", [])):
            if not enemy.is_alive():
                continue
            # Interrupt any move in prep or execute stage
            cm = getattr(enemy, "current_move", None)
            if cm is not None and getattr(cm, "current_stage", -1) in (0, 1):
                cm.interrupted = True
            # Apply brief stun (beats_max=2 gives 1 effective skip of move selection)
            functions.inflict(states.WarCryStunned(enemy), enemy, force=True)
            affected += 1
        if affected:
            cprint(
                f"{affected} {'enemy' if affected == 1 else 'enemies'} recoil from the war cry!",
                "magenta",
            )
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)


class SecretPlans(Move):
    """Intelligence mastery: +30% speed and damage for player and all allies; resets cooldowns."""

    display_name = "Secret Plans"

    web_animation = "buff"

    def __init__(self, player):
        super().__init__(
            name="Secret Plans",
            description=(
                "Reveal the hidden agenda. Jean and all allies gain +30% speed and damage "
                "for 25 beats, and all move cooldowns reset immediately. "
                "Only available when Intelligence is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=False,
            stage_beat=[2, 1, 2, 50],
            stage_announce=[
                colored(
                    f"{player.name} reads the field and pieces together the advantage.",
                    "cyan",
                ),
                colored(f"{player.name} puts the plan into motion!", "cyan"),
                colored(f"The plan is set. {player.name} stands ready.", "yellow"),
                "",
            ],
            fatigue_cost=75,
            beats_left=2,
            target=player,
            user=player,
            category="Mastery",
        )

    def learnable_when(self, player):
        return player.intelligence > 30 and _is_highest(player, player.intelligence)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        return _is_highest(self.user, self.user.intelligence)

    def execute(self, player):
        narrate(self.stage_announce[1])
        targets = [player] + list(getattr(player, "combat_list_allies", []))
        for entity in targets:
            if not entity.is_alive():
                continue
            functions.inflict(states.SecretPlansState(entity), entity, force=True)
            # Reset cooldowns: set beats_left = 0 on all moves in cooldown stage
            for move in getattr(entity, "known_moves", []):
                if getattr(move, "current_stage", -1) == 3:
                    move.beats_left = 0
        cprint(f"Secret Plans activated — {len(targets)} combatant(s) surging!", "cyan")
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)


class BloodOfMartyrs(Move):
    """Faith mastery: absorb all damage for 40 beats, then detonate for 2× absorbed."""

    display_name = "Blood of Martyrs"

    web_animation = "buff"

    def __init__(self, player):
        super().__init__(
            name="Blood of Martyrs",
            description=(
                "Take every blow for 40 beats — absorbing all incoming damage. "
                "Then unleash a map-wide pure energy blast equal to twice the amount absorbed. "
                "Only available when Faith is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=False,
            # 40-beat prep (absorbing), 1-beat execute (detonation), 5 recoil, 55 cooldown
            stage_beat=[40, 1, 5, 55],
            stage_announce=[
                colored(
                    f"{player.name} opens himself to every blow, faith holding him upright.",
                    "yellow",
                ),
                colored(
                    f"{player.name} releases the gathered pain as a wave of holy fire!",
                    "yellow",
                ),
                colored(
                    f"{player.name} sinks to one knee, spent but unbroken.", "yellow"
                ),
                "",
            ],
            fatigue_cost=40,
            beats_left=40,
            target=player,
            user=player,
            category="Mastery",
        )
        self._absorb_state = None

    def learnable_when(self, player):
        return player.faith > 30 and _is_highest(player, player.faith)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        # Cannot stack — block if absorption is already active
        if any(
            getattr(s, "_absorbing", False) for s in getattr(self.user, "states", [])
        ):
            return False
        return _is_highest(self.user, self.user.faith)

    def cast(self):
        """Override cast to apply the absorption state before the prep phase begins."""
        super().cast()
        absorb_state = states.BloodOfMartyrsState(self.user)
        result = functions.inflict(absorb_state, self.user, force=True)
        # Keep a reference so execute() can read the absorbed total
        self._absorb_state = result if result else absorb_state

    def execute(self, player):
        narrate(self.stage_announce[1])
        # Collect absorbed damage from the state
        absorbed = 0
        for state in list(player.states):
            if getattr(state, "_absorbing", False):
                absorbed = getattr(state, "absorbed", 0)
                player.states.remove(state)
                break
        self._absorb_state = None
        detonation = int(absorbed * 2)
        if detonation <= 0:
            cprint(
                f"{player.name} releases the oath, but no damage was absorbed.",
                "yellow",
            )
        else:
            cprint(
                f"{player.name} unleashes {detonation} pure holy damage across the battlefield!",
                "yellow",
            )
            for enemy in list(getattr(player, "combat_list", [])):
                if enemy.is_alive():
                    # Pure damage — bypasses protection and resistance scaling (pure type, resist=1.0)
                    pure_damage = int(
                        detonation * functions.combat_resistance(enemy, "pure")
                    )
                    enemy.hp -= pure_damage
                    if hasattr(enemy, "clamp_hp"):
                        enemy.clamp_hp()
                    # One outcome per enemy, published immediately before that
                    # enemy's own line — the detonation is a battlefield-wide
                    # set of independent resolutions, not one swing (see
                    # _base.publish_outcome). Without this the whole blast fell
                    # through to the adapter's end-of-move fallback: one
                    # animation and no per-target impact at all. A ``pure``
                    # resistance of 0 collapses the blast against that enemy,
                    # which is an `absorb` — the same distinction Move.hit()
                    # draws — and must not play the flesh-impact cue.
                    publish_outcome(
                        self.user,
                        OUTCOME_HIT if pure_damage > 0 else OUTCOME_ABSORB,
                        enemy,
                    )
                    cprint(f"  {enemy.name} takes {pure_damage} damage!", "red")
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
