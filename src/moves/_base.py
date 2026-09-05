"""Move base class, PassiveMove base, and shared combat helpers."""

from src.narration import colored, cprint, narrate  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import src.states as states  # noqa: F401
import src.functions as functions  # noqa: F401
import src.items as items  # noqa: F401
import src.positions as positions  # noqa: F401
from src.animations import animate_to_main_screen as animate  # noqa: F401
from src.combatant import MOVE_STAGE_EXECUTE, MOVE_STAGE_PREP


def _apply_carry_fatigue(user, fatigue_cost):
    """Scale fatigue_cost up proportionally to carry weight burden.

    +0% at 0% carry, +50% at 100% carry, capped at +75% at 150% carry.
    Returns the original cost unchanged for NPCs (no weight_tolerance).
    """
    try:
        wt = float(getattr(user, "weight_tolerance", 0) or 0)
        if wt > 0:
            wc = float(getattr(user, "weight_current", 0) or 0)
            weight_pct = min(wc / wt, 1.5)
            fatigue_cost = int(math.ceil(fatigue_cost * (1.0 + 0.5 * weight_pct)))
    except (TypeError, ValueError):
        pass
    return fatigue_cost


def display_name_of(move, default="Unknown"):
    """Return a move's player-facing name with a safe internal-name fallback."""
    return getattr(move, "display_name", None) or getattr(move, "name", default)


def _apply_work_the_gap(user, target, landed_hits=1):
    """WorkTheGap passive: each landed pick strike shaves the target's
    protection (a progressive armour strip), floored at 0.

    No-op unless the user knows the "Work the Gap" passive and at least one
    hit landed. The reduction is applied to ``protection_base`` (not just
    ``protection``) so it survives ``refresh_stat_bonuses()``, which resets
    ``protection -> protection_base`` every beat under the declarative
    protection model — see functions.reset_stats. This makes the strip
    persist for the rest of the fight.
    """
    if landed_hits <= 0:
        return
    if not any(
        getattr(m, "name", "") == "Work the Gap"
        for m in getattr(user, "known_moves", [])
    ):
        return
    cur = getattr(target, "protection", None)
    if not isinstance(cur, (int, float)) or cur <= 0:
        return
    before = int(cur)
    amount = 2 * landed_hits
    base = getattr(target, "protection_base", None)
    if isinstance(base, (int, float)):
        target.protection_base = max(0, int(base) - amount)
    target.protection = max(0, before - amount)
    if target.protection < before:
        cprint(
            f"{getattr(target, 'name', 'The target')}'s guard is pried open "
            f"(protection {before} -> {int(target.protection)}).",
            "cyan",
        )


# Helper to ensure weapon subtype EXP pools exist (referenced in parry/hit/standard_execute_attack)


def _ensure_weapon_exp(user):
    """Guarantee combat_exp (and skill_exp if present) contain an entry for the current weapon's subtype.
    Needed when weapons are assigned directly (tests or scripted events) bypassing equip_item().
    """
    try:
        wpn = getattr(user, "eq_weapon", None)
        if wpn and hasattr(wpn, "subtype"):
            if not hasattr(user, "combat_exp"):
                return
            if wpn.subtype not in user.combat_exp:
                user.combat_exp[wpn.subtype] = 0
            if hasattr(user, "skill_exp") and wpn.subtype not in user.skill_exp:
                user.skill_exp[wpn.subtype] = 0
    except Exception:
        # Silent fail to avoid disrupting combat flow if something unexpected occurs
        pass


def _apply_blade_mastery_discount(user, fatigue_cost, floor_fatigue=10):
    """BladeMastery passive: sword attacks cost less fatigue.

    Shared by the standard attack pipeline and any hand-rolled attack (e.g.
    basic Attack) that wants the same discount applied to its own fatigue math.
    """
    if (
        getattr(getattr(user, "eq_weapon", None), "subtype", None) == "Sword"
        and any(
            getattr(m, "name", "") == "Blade Mastery"
            for m in getattr(user, "known_moves", [])
        )
    ):
        fatigue_cost = max(floor_fatigue, int(fatigue_cost * 0.85))
    return fatigue_cost


def _apply_facing_accuracy(attacker, defender, hit_chance):
    """Facing/angle system: attacks landing on a defender's flank or rear are
    harder to defend against than a head-on attack (issue #394).

    Mirrors positions.get_damage_modifier (already wired into Backstab's
    damage) on the accuracy side, applied universally so it isn't limited to
    whichever moves happen to consult it directly — the same partial-
    enforcement trap #421 fixed for HauntingPresence. No-op (returns
    hit_chance unchanged) unless both combatants have a resolved
    combat_position — i.e. the 2D coordinate combat system is active.

    Requires hit_chance > 0: a non-positive value is either an auto-miss
    sentinel (-1, out of range) or already zeroed, and must be left alone —
    Python's int() truncates toward zero, so int(-1 * 0.95) is 0, not -1,
    which would turn a guaranteed miss into a chance to hit. The result is
    capped at 100 since the multiplier can exceed 1.0 (rear attacks).
    """
    if hit_chance <= 0:
        return hit_chance
    try:
        attacker_pos = getattr(attacker, "combat_position", None)
        defender_pos = getattr(defender, "combat_position", None)
        if attacker_pos is None or defender_pos is None:
            return hit_chance
        attack_angle = positions.angle_to_target(attacker_pos, defender_pos)
        angle_diff = positions.attack_angle_difference(attack_angle, defender_pos.facing)
        return min(100, int(hit_chance * positions.get_accuracy_modifier(angle_diff)))
    except Exception:
        return hit_chance


def _apply_haunting_presence(attacker, defender, hit_chance):
    """HauntingPresence passive: defender's unsettling aura rattles close-range attackers.

    No-op (returns hit_chance unchanged) unless the defender knows the passive,
    the attack was already going to have a chance to land, and the attacker is
    within 3 units of proximity. Shared by every attack path so the passive
    isn't limited to whichever moves happen to call standard_execute_attack.
    """
    if (
        hit_chance > 0
        and any(
            getattr(m, "name", "") == "Haunting Presence"
            for m in getattr(defender, "known_moves", [])
        )
        and hasattr(defender, "combat_proximity")
        and defender.combat_proximity.get(attacker, 9999) <= 3
    ):
        hit_chance = int(hit_chance * 0.85)
    return hit_chance


def _apply_to_hit_modifiers(attacker, defender, hit_chance):
    """Apply the shared universal to-hit modifiers, in order: facing/angle
    accuracy (#394), then HauntingPresence (#421).

    Every attack in the moves package funnels through this single call
    instead of each hand-rolling the same two-call sequence — the exact
    duplication #464 was filed over. Adding a future universal to-hit
    modifier is a one-file change here instead of another sweep across every
    attack path.
    """
    hit_chance = _apply_facing_accuracy(attacker, defender, hit_chance)
    hit_chance = _apply_haunting_presence(attacker, defender, hit_chance)
    return hit_chance


#: Default base term of the engine's to-hit expression, plus the weights it
#: applies to the attacker's attributes. These live here, next to the attack
#: paths that consume them, so a balance change is a one-file edit — an earlier
#: copy in the API layer drifted to ``98 + finesse`` and the character sheet
#: disagreed with the dice until someone noticed.
HIT_CHANCE_BASE = 98
HIT_CHANCE_FINESSE_WEIGHT = 0.7
HIT_CHANCE_INTELLIGENCE_WEIGHT = 0.3


def to_hit_chance(user, target, base=HIT_CHANCE_BASE, floor=None):
    """Return the pre-modifier hit chance for ``user`` attacking ``target``.

    ``base`` is the move family's accuracy ceiling before either combatant's
    attributes apply; ``floor`` clamps the truncated result. **The call sites
    are not uniform** — bases of 85/90/95/98/105 and floors of 1, 5, or none
    are all in use, and which move takes which is not guessable from its
    weapon class.

    This docstring deliberately does NOT enumerate them. It used to, and the
    list was wrong twice: it named ``Riposte`` as an 85 site (it takes the
    default 98, and reconciling the code to that claim would have quietly cost
    it 13 points of accuracy), and after that was corrected the list still
    omitted ``PowerStrike``. A partial enumeration in the one place people look
    for authority is worse than none, because it reads as exhaustive.

    ``grep -rn "to_hit_chance" src/moves/`` is the authority. Read the call
    site you are changing.

    Situational modifiers are deliberately *not* applied here. Callers still
    pass the result through `_apply_to_hit_modifiers`, and several interpose
    their own adjustments first (ranged accuracy decay, the Hawkeye buff,
    Aimed Shot's flat +15, the crossbow close-range halving), so folding those
    in would change when each one lands relative to the clamps.

    Term order is load-bearing: ``base - target.finesse`` is evaluated before
    the weighted attacker terms are added. Folding the attacker's terms first
    and subtracting evasion last shifts the truncated result by one point for
    roughly 0.7% of integer stat combinations, so this must not be "simplified"
    into ``attacker_accuracy(...) - target.finesse``.
    """
    chance = int(
        base
        - target.finesse
        + (user.finesse * HIT_CHANCE_FINESSE_WEIGHT)
        + (user.intelligence * HIT_CHANCE_INTELLIGENCE_WEIGHT)
    )
    if floor is not None:
        chance = max(floor, chance)
    return chance


def attacker_accuracy(finesse, intelligence, base=HIT_CHANCE_BASE):
    """Return the attacker-side half of the to-hit roll, with no defender term.

    The API renders accuracy and evasion as two separate ratings so a client
    can show ``accuracy - evasion``; this is the accuracy half. It takes raw
    attribute values rather than a combatant because those callers each apply
    their own missing/garbage-value policy before the arithmetic, which is an
    API-layer concern rather than an engine one.

    An indicative rating, not a per-move hit chance: it assumes the default
    base, ignores every situational modifier, and — per ``to_hit_chance`` —
    parts company with the real roll by a point for a small fraction of stat
    combinations because the ``int()`` truncation lands on a different
    intermediate value here (there is no defender term to subtract first).
    Not a floating-point association artifact: it is truncation order, which
    is why ``to_hit_chance`` must not be rewritten in terms of this function.
    """
    return int(
        base
        + (finesse * HIT_CHANCE_FINESSE_WEIGHT)
        + (intelligence * HIT_CHANCE_INTELLIGENCE_WEIGHT)
    )


def select_weighted_target(candidates):
    """Pick a random combat target, weighting down targets with Shadow Step.

    Targets with Shadow Step in known_moves get weight 0.5; others get weight 1.0.
    """
    if not candidates:
        return None
    weights = []
    for c in candidates:
        w = 1.0
        if any(getattr(m, "name", "") == "Shadow Step" for m in getattr(c, "known_moves", [])):
            w = 0.5
        weights.append(w)
    return random.choices(candidates, weights=weights, k=1)[0]


default_animations = {
    "p": "None",  # prep
    "e": "None",  # execute
    "r": "None",  # recoil
    "c": "None",  # cooldown
}


class Move:  # master class for all moves
    # Animation type the web client plays for this move ("attack", "pulse",
    # "pierce", "projectile", ...). Subclasses declare their type as a class
    # attribute; None lets the combat adapter auto-determine a fallback
    # (attack for targeted damaging moves, pulse otherwise). The full set of
    # valid types lives in frontend/src/utils/animationConfigs.js.
    web_animation = None
    # Concrete engine moves must declare a player-facing name. Internal `name`
    # values remain stable for command routing and AI logic.
    display_name = None
    # Power multiple this move applies to its user's base damage.
    #
    # Declared HERE, on the base class, so it is part of the Move interface
    # rather than a private attribute the serializer happens to probe for. The
    # wire's `damage_multiplier` (src/api/serializers/combat.py) is read off
    # it, and the Tactical Advisor decides POTENTIALLY LETHAL from that number
    # — so a heavy move that leaves this at 1.0 understates itself to the
    # model. Any move that hits for more (or less) than its user's raw damage
    # overrides it. See TelegraphedSurge and GorranClub in src/moves/_npc.py.
    #
    # A move that ROLLS its power declares the band instead, as
    # `_POWER_ROLL_MIN`/`_POWER_ROLL_MAX`, and derives this as their midpoint
    # — the factor the hit CENTRES on, which is what the wire means. The
    # midpoint and not the ceiling: `_estimate_incoming_damage`
    # (ai/combat_strategist.py) already renders the wire value as a ±20%
    # band and flags POTENTIALLY LETHAL when that band's midpoint reaches half
    # the player's HP, so a ceiling here would double-count the high roll and
    # cry wolf. `_rolled_power()` below is the single place the band is rolled,
    # so the roll and the number derived from it cannot be retuned apart.
    _DAMAGE_MULTIPLIER: float = 1.0

    # Heat multipliers the shared outcome handlers below (parry/hit/miss)
    # apply to Jean's combat heat. `Player.change_heat(mult)` multiplies the
    # running heat and clamps it to [0.5, 10], so a value above 1 rewards the
    # outcome and one below 1 punishes it.
    #
    # Named rather than inlined because each one prices a tuning decision, and
    # because ONE of them is read from outside the engine: ai/combat_strategist
    # quotes the cost of a miss in the combat LLM prompt and used to carry its
    # own hand-copied 0.85 with nothing holding the pair in step. That is
    # `_HEAT_MISS_PENALTY` alone; the rest are internal, and named for
    # consistency rather than because anything else reads them. Values that
    # repeat are separate constants on purpose — they are independently
    # tunable outcomes that happen to agree today.
    #
    # These eight are every heat outcome that is a FIXED factor. There is a
    # ninth, and it is deliberately not here: when Jean takes damage, `hit()`
    # scales his heat by `1 - damage/maxhp`, a proportion of the blow rather
    # than a constant, so there is no value to name. It stays inline at its
    # call site, where the two operands are in scope.
    _HEAT_PARRY_REWARD = 1.4  # Jean parries an incoming attack
    _HEAT_PARRIED_PENALTY = 0.75  # Jean's own attack is parried
    _HEAT_HIT_REWARD = 1.25  # Jean lands damage
    _HEAT_ABSORBED_PENALTY = 0.75  # Jean's hit is fully absorbed by the target
    _HEAT_ABSORB_REWARD = 1.25  # Jean's armour absorbs an incoming hit
    _HEAT_DODGE_REWARD = 1.25  # Jean is missed while Dodging (stacks with the next)
    _HEAT_EVADED_REWARD = 1.1  # Jean is missed at all
    _HEAT_MISS_PENALTY = 0.85  # Jean's own attack misses

    def __init__(
        self,
        name,
        description,
        xp_gain,
        current_stage,
        beats_left,
        stage_announce,
        target,
        user,
        stage_beat,
        targeted,
        mvrange=(0, 9999),
        heat_gain=0,
        fatigue_cost=0,
        instant=False,
        verbose_targeting=False,
        category="Miscellaneous",
        passive=False,
    ):
        if type(self) is not Move:
            display_name = getattr(type(self), "display_name", None)
            if not isinstance(display_name, str) or not display_name.strip():
                raise TypeError(
                    f"{type(self).__name__} must declare a non-empty display_name"
                )
        self.name = name
        self.description = description
        self.category = category
        self.xp_gain = xp_gain
        self.heat_gain = heat_gain
        self.current_stage = current_stage
        self.stage_beat = stage_beat
        self.beats_left = beats_left
        self.stage_announce = stage_announce
        self.fatigue_cost = fatigue_cost
        self.target = target  # can be the same as the user in abilities with no targets
        self.user = user
        self.targeted = targeted  # Is the move targeted at something?
        self.verbose_targeting = verbose_targeting  # If set to true, the target menu will always appear even with
        # 1 target and will show additional info
        self.interrupted = False  # When a move is interrupted, skip all remaining actions for that move, set the
        # move's cooldown
        self.initialized = False
        self.usercolor = "white"
        self.targetcolor = "white"
        self.mvrange = mvrange  # tuple containing the min and max ranges for the move
        self.instant = instant  # moves flagged as instant do not allow any beats to pass before completing all stages
        self.weight = (
            1  # only used by NPCs to determine the chance that move is selected for use
        )
        self.passive = passive
        self.fatigue_per_beat = 0

    def beat_update(self, user):
        """Called on every beat while the move is active (beats_left > 0)."""
        pass

    def get_effective_range_max(self, user):
        """Override in moves that compute range dynamically (e.g. ranged weapons with decay).
        Return a float/int to override mvrange[1] during target selection, or None to use mvrange[1].
        """
        return None

    def beats_until_resolve(self):
        """Beats from now until this move's effect lands, or None once it has.

        ``beats_left`` on its own is beats remaining in the *current stage*,
        which is not the number a player can act on: a move showing 3 with a
        4-beat execute stage actually lands 9 beats away. This walks the same
        stage machine ``advance`` does, so the two can never disagree.

        It lives here rather than in the web client on purpose. The rule that
        makes it non-obvious — ``advance``'s ``while self.beats_left == 0``
        loop runs a zero-length stage in the *same* beat as the one before it,
        so a move with no execute stage resolves as soon as prep ends — is a
        property of that loop twenty lines below, and a second copy of it in
        JavaScript would drift from this one exactly as the inlined to-hit
        arithmetic did (see CLAUDE.md).

        Returns None for a move in recoil or cooldown: its effect already
        happened, so there is nothing left to count down to.
        """
        stage = getattr(self, "current_stage", None)
        if stage not in (MOVE_STAGE_PREP, MOVE_STAGE_EXECUTE):
            return None
        left = getattr(self, "beats_left", None)
        if not isinstance(left, (int, float)) or isinstance(left, bool) or left < 0:
            return None

        # One extra beat in every case: draining to zero does not advance the
        # stage, the *next* beat does.
        if stage == MOVE_STAGE_EXECUTE:
            return int(left) + 1

        stage_beats = getattr(self, "stage_beat", None) or []
        execute_beats = stage_beats[1] if len(stage_beats) > 1 else 0
        if not isinstance(execute_beats, (int, float)) or execute_beats <= 0:
            # Zero-length execute stage: prep and execute fire on one beat.
            return int(left) + 1
        return int(left) + 1 + int(execute_beats) + 1

    def get_accuracy_falloff(self, user):
        """Distance beyond which this move's accuracy decays, and how fast.

        Returns ``(start_ft, points_per_ft)`` — accuracy is flat out to
        ``start_ft``, then loses ``points_per_ft`` hit-chance points for every
        foot past it — or ``None`` when accuracy does not decay with distance.

        This is the same pair the decaying moves' own ``calculate_hit_chance``
        subtracts with (``hit_chance -= (distance - start) * decay``), exposed
        so a caller can *describe* the curve without re-deriving it. The web
        battlefield draws the range indicator from it: a decaying move has no
        meaningful hard edge — reach is unbounded and far shots simply decay
        to a vanishing chance — so it renders as a gradient that dissolves
        outward rather than as a ring.

        The default covers every move that carries ``decay``/``base_range``
        (the crossbow line: ShootCrossbow, BroadheadBolt, AimedShot,
        PinningBolt). Moves with no ``decay`` attribute — every melee move —
        fall through to ``None``.
        """
        decay = getattr(self, "decay", 0)
        if not decay or decay <= 0:
            return None
        return (getattr(self, "base_range", 0), decay)

    def _viable_for(self, target):
        """True if this move is viable with ``target`` temporarily assigned as
        ``self.target``.

        ``viable()`` implementations are written assuming ``self.target`` is
        already the resolved target (the adapter sets it that way before
        ``execute()`` runs), but ``preview_hit_chance`` below is called earlier,
        while the target list is still being built — before any target has been
        committed. This swaps ``self.target`` in for the duration of the check
        and always restores it, so a ``viable()`` that reads ``self.target``
        (Advance, VertigoSpin, FeintAndPivot, Riposte's proximity scan, ...)
        sees the same combatant it would see at real execute time.
        """
        if target is None or target is self.user:
            return False
        original_target = self.target
        self.target = target
        try:
            return bool(self.viable())
        finally:
            self.target = original_target

    def _standard_preview_hit_chance(self, target, base=HIT_CHANCE_BASE, floor=None):
        """Shared body for moves whose ``preview_hit_chance`` only diverges
        from the default in its ``to_hit_chance`` base/floor — no situational
        modifiers (ranged decay, Hawkeye, close-range halving, ...) interpose
        before the roll. Handles the viability/target-swap dance once so those
        per-move overrides stay a one-line call; moves with situational
        modifiers still need their own override (see ``preview_hit_chance``'s
        docstring) since those live at the call site, not here, by the same
        rule that governs ``to_hit_chance`` itself.
        """
        if not self._viable_for(target):
            return None
        hit_chance = to_hit_chance(self.user, target, base=base, floor=floor)
        return _apply_to_hit_modifiers(self.user, target, hit_chance)

    def _unconditional_preview_hit_chance(self, target, base=HIT_CHANCE_BASE, floor=None):
        """Shared body for moves whose execute() computes hit_chance
        unconditionally — gated only on "target exists and is alive", never
        on ``self.viable()`` (VertigoSpin, FeintAndPivot). Deliberately does
        NOT call ``_viable_for``/``self.viable()``: those moves' execute()
        never checks viability before rolling (only a target-alive early
        return), and adding one here would make the preview auto-miss for a
        configuration execute() would still roll for — see the two callers'
        own docstrings for the concrete regression this caused once already.
        """
        if target is None or not target.is_alive():
            return None
        hit_chance = to_hit_chance(self.user, target, base=base, floor=floor)
        return _apply_to_hit_modifiers(self.user, target, hit_chance)

    def preview_hit_chance(self, target=None):
        """Return the hit chance this move would actually roll against
        ``target`` (or ``self.target`` if omitted) with its current
        parameters, as an integer percentage — or ``None`` when a per-target
        hit chance isn't meaningful (an untargeted move, a status/positioning
        move with no to-hit roll, a move that isn't currently viable, or no
        resolvable target).

        This base implementation is the *default* to-hit path only:
        ``to_hit_chance(..., floor=5)`` plus the shared
        ``_apply_to_hit_modifiers`` chain — the same two calls
        ``standard_execute_attack`` and most hand-rolled ``execute()`` methods
        make with no other arguments. Per CLAUDE.md's "To-hit arithmetic"
        note, the ``to_hit_chance`` call sites are **not uniform** — bases of
        85/90/95/98/105 and floors of 1/5/none are all in use, and several
        moves interpose situational modifiers (ranged accuracy decay,
        Hawkeye, Aimed Shot's flat bonus, the crossbow close-range halving)
        before the roll, or skip the roll entirely (Reaper's Mark, the pure
        positioning moves, Killing Precision's guaranteed hit). **Any move
        whose execute() path is not the plain default MUST override this
        method** to report what its own execute() actually computes, not this
        fallback — grep ``to_hit_chance`` call sites and read them; do not
        trust an enumeration, including this one.

        A move that already defines ``calculate_hit_chance`` (ShootBow) is
        the authoritative estimate for that move; this delegates to it so the
        two can never disagree.
        """
        if hasattr(self, "calculate_hit_chance"):
            t = target if target is not None else self.target
            if t is None:
                return None
            return self.calculate_hit_chance(t)

        if not self.targeted or self.passive:
            return None
        t = target if target is not None else self.target
        return self._standard_preview_hit_chance(t, floor=5)

    def can_use_coordinates(self, user):
        """Check if 2D coordinate-based movement is available for this move."""
        if not (hasattr(user, "combat_position") and user.combat_position is not None):
            return False

        # If targeted at someone else, they must also have coordinates
        if getattr(self, "target", None) and self.target is not user:
            return (
                hasattr(self.target, "combat_position")
                and self.target.combat_position is not None
            )

        return True

    def viable(self):
        """Check arbitrary conditions to see if the move is available for use; return True or False"""
        viability = True
        return viability

    def learnable_when(self, player) -> bool:
        """Override to gate skill-tree availability on player state (e.g. stat thresholds)."""
        return True

    def process_stage(self, user):
        if user.current_move == self:
            if self.current_stage == 0:
                self.prep(user)
            elif self.current_stage == 1:
                self.execute(user)
            elif self.current_stage == 2:
                self.recoil()
            elif self.current_stage == 3:
                self.cooldown(
                    user
                )  # the cooldown stage will typically never be rewritten,
                # so this will usually just pass

    def cast(
        self,
    ):  # this is what happens when the ability is first chosen by the player
        self.current_stage = 0  # initialize prep stage
        if hasattr(self, "refresh_announcements"):
            self.refresh_announcements(self.user)
        if self.stage_announce[0] != "":
            narrate(
                self.stage_announce[0]
            )  # Print the prep announce message for the move

        # CleaveInstinct passive: next move after a kill gets prep=1 (skip zero-beat moves)
        prep = self.stage_beat[0]
        if (
            prep > 0
            and getattr(self.user, "_cleave_instinct_pending", False)
            and any(
                getattr(m, "name", "") == "Cleave Instinct"
                for m in getattr(self.user, "known_moves", [])
            )
        ):
            prep = 1
            self.user._cleave_instinct_pending = False

        # Staggered state: add +5 prep beats to caster's next move (consumed after first use)
        if prep > 0 and isinstance(getattr(self.user, "states", None), list):
            for state in self.user.states:
                if getattr(state, "name", "") == "Staggered" and not getattr(state, "penalty_consumed", False):
                    prep += getattr(state, "prep_penalty", 5)
                    state.penalty_consumed = True
                    break

        # QuickReload passive: faster crossbow reload — shave ~20% of prep beats
        # (floored at 1) while wielding a crossbow.
        if (
            prep > 1
            and getattr(getattr(self.user, "eq_weapon", None), "subtype", None) == "Crossbow"
            and any(
                getattr(m, "name", "") == "Quick Reload"
                for m in getattr(self.user, "known_moves", [])
            )
        ):
            prep = max(1, int(round(prep * 0.8)))

        self.beats_left = prep

    def advance(self, user):
        self.user = user  # Ensure user is always current
        if self.interrupted:
            # WarCry-style interrupt (issue #417): abort immediately, skipping
            # whatever prep/execute progress was made, straight to cooldown.
            # Mirrors the stage-3 transition below (current_stage > 0 keeps
            # advance() ticking this move's cooldown down on future beats even
            # after user.current_move is cleared) so the interrupted actor
            # still pays the move's normal cooldown before acting again.
            self.interrupted = False
            self.current_stage = 3
            self.beats_left = self.stage_beat[3]
            if user.current_move == self:
                user.current_move = None
            self.initialized = False
            return
        self.evaluate()
        if (
            user.current_move == self or self.current_stage > 0
        ):  # only advance the move if it's the player's
            # current move or if it's already been used (past prep stage)
            if self.beats_left > 0:
                self.beats_left -= 1
                self.beat_update(user)
            else:
                while (
                    self.beats_left == 0
                ):  # this loop will advance stages until the current stage has a beat count,
                    # effectively skipping unused stages; if the move is instant, pretend all beat counts are 0!
                    self.process_stage(user)
                    self.current_stage += 1  # switch to next stage
                    if (
                        self.current_stage == 3
                    ):  # when the move enters cooldown, detach it from the player so he can
                        # do something else.
                        user.current_move = None
                        self.initialized = False
                    if (
                        self.current_stage > 3
                    ):  # if the move is coming out of cooldown, switch back to the prep stage
                        # and break the while loop
                        self.current_stage = 0
                        self.beats_left = self.stage_beat[self.current_stage]
                        break
                    self.beats_left = self.stage_beat[
                        self.current_stage
                    ]  # set beats remaining for current stage

    def prep(
        self, user
    ):  # what happens during these stages. Each move will overwrite prep/execute/recoil/cooldown
        # depending on whether something is supposed to happen at that stage
        pass

    def execute(self, user):
        if self.stage_announce[1] != "":
            narrate(self.stage_announce[1])

    def recoil(self):
        if self.stage_announce[2] != "":
            narrate(self.stage_announce[2])

    def cooldown(self, user):
        pass

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        pass

    def _rolled_power(self):
        """The user's damage rolled through this move's declared power band.

        For moves that declare `_POWER_ROLL_MIN`/`_POWER_ROLL_MAX`. Deliberately
        NOT given defaults on this class: a move that calls this without
        declaring a band should raise here rather than silently roll a
        1.0–1.0 no-op, which would look exactly like a working roll.

        Here rather than in each `evaluate()` because the expression stood
        identically in five of them, and because `_DAMAGE_MULTIPLIER` is
        derived from the same two bounds. One roll site means a retune cannot
        move the roll while leaving the wire's midpoint behind — which is the
        entire claim those derivations make.
        """
        return self.user.damage * random.uniform(
            self._POWER_ROLL_MIN, self._POWER_ROLL_MAX
        )

    def prep_colors(self):  # prepares usercolor, targetcolor for prints
        # Check if user is player generally (by name or class, assuming Player class has no friend attr)
        is_user_player = (
            self.user.name == "Jean" or self.user.__class__.__name__ == "Player"
        )

        if is_user_player:
            self.usercolor = "green"
        else:
            if not getattr(self.user, "friend", False):
                self.usercolor = "magenta"
            else:
                self.usercolor = "cyan"

        is_target_player = (
            self.target.name == "Jean" or self.target.__class__.__name__ == "Player"
        )

        if is_target_player:
            self.targetcolor = "green"
        else:
            if not getattr(self.target, "friend", False):
                self.targetcolor = "magenta"
            else:
                self.targetcolor = "cyan"

    def parry(self):
        narrate(
            colored(self.target.name, self.targetcolor)
            + colored(" parried the attack from ", "red")
            + colored(self.user.name, self.usercolor)
            + colored("!", "red")
        )
        self.stage_beat[2] += 10  # add stagger time to the user
        if self.target.name == "Jean":
            self.target.change_heat(self._HEAT_PARRY_REWARD)
            # Credit parry experience based on target's weapon if available, otherwise "Basic"
            if hasattr(self.target, "eq_weapon") and self.target.eq_weapon:
                _ensure_weapon_exp(self.target)
                self.target.combat_exp[self.target.eq_weapon.subtype] += 15
            else:
                self.target.combat_exp["Basic"] += 15
        if self.user.name == "Jean":
            self.user.change_heat(self._HEAT_PARRIED_PENALTY)

    def hit(self, damage, glance):
        # Defense-in-depth (issue #296): damage reaches HP here from many move
        # execute() paths. Coerce it to a finite, integral value so a NaN/inf
        # (e.g. from an exotic resistance/heat product) can never poison hp, and
        # clamp hp to [0, maxhp] afterward via the shared Combatant guard.
        try:
            damage = float(damage)
        except (TypeError, ValueError):
            damage = 0
        if not math.isfinite(damage):
            damage = 0
        damage = int(damage)
        if damage > 0:
            if glance:
                narrate(
                    colored(self.user.name, self.usercolor)
                    + colored(" just barely hit ", "yellow")
                    + colored(self.target.name, self.targetcolor)
                    + colored(" for ", "yellow")
                    + colored(damage, "red")
                    + colored(" damage!", "yellow")
                )
            else:
                narrate(
                    colored(self.user.name, self.usercolor)
                    + colored(" struck ", "yellow")
                    + colored(self.target.name, self.targetcolor)
                    + colored(" for ", "yellow")
                    + colored(damage, "red")
                    + colored(" damage!", "yellow")
                )
            # Blood of Martyrs absorption — intercept before HP is reduced
            for _s in getattr(self.target, "states", []):
                if getattr(_s, "_absorbing", False):
                    _s.absorbed += damage
                    damage = 0
                    break
            self.target.hp -= damage
            if hasattr(self.target, "clamp_hp"):
                self.target.clamp_hp()
            if self.user.name == "Jean":
                self.user.change_heat(self._HEAT_HIT_REWARD)
                _ensure_weapon_exp(self.user)
                self.user.combat_exp[self.user.eq_weapon.subtype] += damage / 4
            if self.target.name == "Jean":
                self.target.change_heat(
                    1 - (damage / self.target.maxhp)
                )  # reduce heat by the percentage of dmg done to maxhp
                self.target.combat_exp["Basic"] += 15
        elif damage == 0:
            narrate(
                colored(self.user.name, self.usercolor)
                + colored(" struck ", "yellow")
                + colored(self.target.name, self.targetcolor)
                + colored(" but did no damage!", "yellow")
            )
        else:
            cprint(
                "{} struck {}, but {} absorbed {} damage!".format(
                    colored(self.user.name, self.usercolor),
                    colored(self.target.name, self.targetcolor),
                    colored(self.target.name, self.targetcolor),
                    colored(damage, "red"),
                ),
                "yellow",
            )
            if self.user.name == "Jean":
                self.user.change_heat(self._HEAT_ABSORBED_PENALTY)
            if self.target.name == "Jean":
                self.target.change_heat(self._HEAT_ABSORB_REWARD)
                self.target.combat_exp["Basic"] += 15

    def miss(self):
        narrate(colored(self.user.name, self.usercolor) + "'s attack just missed!")
        if self.target.name == "Jean":
            for state in self.target.states:
                if state.name == "Dodging":
                    self.target.change_heat(self._HEAT_DODGE_REWARD)
                    self.target.combat_exp["Basic"] += 10
                    break
            self.target.change_heat(self._HEAT_EVADED_REWARD)
            self.target.combat_exp["Basic"] += 5
        if self.user.name == "Jean":
            self.user.change_heat(self._HEAT_MISS_PENALTY)

    def standard_viability_attack(self, subtypes=()):
        """
        Standard viability loadout for a typical attack-type ability
        :return: boolean true or false
        """
        viability = False
        has_weapon = False
        enemy_near = False
        allowed_subtypes = subtypes

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        # Special case for Unarmed: don't require an actual weapon equipped
        if "Unarmed" in allowed_subtypes:
            has_weapon = True  # Unarmed is always available
        elif hasattr(self.user, "eq_weapon") and self.user.eq_weapon:
            if len(subtypes) > 0:
                if self.user.eq_weapon.subtype in allowed_subtypes:
                    has_weapon = True
            else:
                has_weapon = True

        # Check if enemy is in range
        range_min = self.mvrange[0]
        range_max = self.mvrange[1]
        for enemy, distance in self.user.combat_proximity.items():
            if range_min <= distance <= range_max:
                enemy_near = True
                break

        if has_weapon and enemy_near:
            viability = True
        return viability

    def _hostiles_in_proximity(self):
        """Yield ``(combatant, distance)`` for hostile entries in the user's
        ``combat_proximity``.

        ``combat_list`` holds the opposing side for any combatant (for the
        player, its enemies; for an enemy NPC, the player and allies — see the
        combat adapter's side assignment), so an entry absent from it is a
        same-side ally and must not make an attack look viable. Only a
        populated ``combat_list`` is trusted to filter: when it is missing or
        empty (combat not yet wired up, or a degraded/mock user) the side is
        unknown, so every proximity entry is yielded rather than none.
        """
        proximity = getattr(self.user, "combat_proximity", None) or {}
        hostiles = getattr(self.user, "combat_list", None)
        for combatant, distance in proximity.items():
            if hostiles and combatant not in hostiles:
                continue
            yield combatant, distance

    def standard_evaluate_attack(
        self,
        base_power,
        base_damage_type,
        mod_power=0,
        mod_prep=0,
        mod_cd=0,
        mod_recoil=0,
        mod_fatigue=0,
        mod_range_min=0,
        mod_range_max=0,
        floor_fatigue=10,
    ):
        """
        Standard evaluation sequence for typical attack-type abilities
        :return: tuple (self.power, self.base_damage_type)
        """
        # Power calculation
        power = (
            self.user.eq_weapon.damage
            + base_power
            + self.user.strength * self.user.eq_weapon.str_mod
            + self.user.finesse * self.user.eq_weapon.fin_mod
        )
        if isinstance(mod_power, str) and "%" in mod_power:
            mod_power_val = int(mod_power.replace("%", ""))
            power = (power * mod_power_val) / 100
        else:
            power += int(mod_power)
        power = max(0, int(power))

        # Prep calculation
        prep = int((40 + (self.user.eq_weapon.weight * 3)) / self.user.speed)
        prep += int(mod_prep)
        prep = max(1, prep)

        execute = 1

        # Cooldown calculation
        cooldown = (3 + self.user.eq_weapon.weight) - int(self.user.endurance / 10)
        cooldown += int(mod_cd)
        cooldown = max(0, cooldown)

        # Recoil calculation
        recoil = int(1 + (self.user.eq_weapon.weight / 2))
        recoil += int(mod_recoil)
        recoil = max(1, recoil)

        # Fatigue cost calculation — endurance gives modest relief (coeff 2);
        # strength reduces how much weapon weight burdens the fighter;
        # carry weight adds proportional burden on top.
        wt_mult = max(4, 10 - 0.2 * self.user.strength)
        fatigue_cost = (
            85 + int(self.user.eq_weapon.weight * wt_mult) - (2 * self.user.endurance)
        )
        fatigue_cost += int(mod_fatigue)
        fatigue_cost = max(floor_fatigue, int(fatigue_cost))
        fatigue_cost = _apply_carry_fatigue(self.user, fatigue_cost)

        # BladeMastery passive: sword attacks cost less fatigue
        fatigue_cost = _apply_blade_mastery_discount(self.user, fatigue_cost, floor_fatigue)

        # Range calculation
        mvrange = (
            self.user.eq_weapon.wpnrange[0] + int(mod_range_min),
            self.user.eq_weapon.wpnrange[1] + int(mod_range_max),
        )

        weapon_name = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} strikes with his {weapon_name}!", "green"
        )
        self.stage_beat = [prep, execute, recoil, cooldown]
        self.fatigue_cost = fatigue_cost
        self.mvrange = mvrange

        if base_damage_type == "weapon":
            base_damage_type = items.get_base_damage_type(self.user.eq_weapon)
        return power, base_damage_type

    def standard_execute_attack(self, player, power, base_damage_type):
        glance = False  # switch for determining a glancing blow
        self.prep_colors()
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

        if self.viable():
            hit_chance = to_hit_chance(self.user, self.target, floor=5)
        else:
            hit_chance = (
                -1
            )  # if attacking is no longer viable (enemy is out of range), then auto miss

        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(self.user, self.target, hit_chance)

        roll = random.randint(0, 100)
        damage = (
            (
                (power * functions.combat_resistance(self.target, base_damage_type))
                - self.target.protection
            )
            * player.heat
        ) * random.uniform(0.8, 1.2)
        if damage <= 0:
            damage = 0
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)
        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5
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
ANY MOVES
"""


class PassiveMove(Move):
    """Base for flag passives — never castable; queried by other moves for effect checks.

    Subclasses only need to supply name and description. All timing values are zero,
    targeted=False, passive=True, and viable() always returns False.
    """

    def __init__(self, user, name, description, category="Passive"):
        super().__init__(
            name=name,
            description=description,
            xp_gain=0,
            current_stage=0,
            stage_beat=[0, 0, 0, 0],
            targeted=False,
            stage_announce=["", "", "", ""],
            fatigue_cost=0,
            beats_left=0,
            target=user,
            user=user,
            category=category,
            passive=True,
        )

    def viable(self):
        return False
