"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""

from src.narration import cprint
import math
import random
import src.functions as functions

# Every percentage a state shows the player (``description``) or the Tactical
# Advisor (``tactical_mechanics``) is rendered through this, so no percentage in
# this module is spelled out by hand.
#
# The two carry DIFFERENT contracts, and the difference is worth knowing.
#
# ``description`` is interpolated from class constants and frozen at
# construction. It cannot disagree with the ``add_*`` assignment about the
# FRACTION, because both read the same constant -- but that is the whole of its
# guarantee. ``int()`` truncation means a 20% penalty on a 7-point stat applies
# 1 point and not 1.4, and a twice-compounded ``Slimed`` still spells out its
# FIRST application's numbers, because nothing re-renders the string.
#
# ``tactical_mechanics`` is read live, and means one of two things depending on
# the state (see ``State._render_tactical_mechanics``). For the states whose
# ``compound()`` moves an ``add_*``, it is derived the other way round -- from
# the delta actually on the books (see ``State._applied_pct``) -- so what
# reaches the combat prompt is what the engine applied, compounding included.
# For the rest it is the NOMINAL class fraction their constructor passed, which
# is exact for them precisely because nothing can move it.
#
# Imported rather than defined here:
# ai/combat_strategist.py needs the identical renderer for the thresholds IT
# quotes, and two copies of a rounding rule is one edit away from the drift
# both copies exist to prevent. src/text_format is dependency-free so neither
# side drags the other's stack in.
from src.text_format import pct as _pct


# Distinguishes "this state never captured a base stat" from "the base stat it
# captured was 0". ``getattr(self, base_attr, 0)`` could not tell the two apart,
# and answered both with the nominal fraction -- so a modifier the engine had
# provably applied as 0 was reported to the combat prompt as the full class
# percentage. See ``State._applied_pct``.
_BASE_NOT_CAPTURED = object()


class State:  # master class for all states
    """
    If beats_max is 0 (default), the state will not expire after n beats.

    """

    # What a re-application does to a compounding state's CLOCKS: stretch both
    # ceilings by ``_COMPOUND_DURATION_MULT``, then top each remainder back up
    # toward its new ceiling by ``1 / _COMPOUND_REFRESH_DIVISOR`` of it.
    #
    # Here rather than on each state because ``Poisoned``, ``Slimed`` and
    # ``Petrified`` all run this identical rule, and three private copies of one
    # rule is three places to retune and two chances to forget. A state that
    # wants a different clock rule overrides the constants; one that wants a
    # different SHAPE (``Enflamed`` refreshes rather than stretches, ``Fervent``
    # adds a flat beat count) simply does not call the helper.
    _COMPOUND_DURATION_MULT = 1.1
    _COMPOUND_REFRESH_DIVISOR = 4

    def __init__(
        self,
        name,
        target,
        source=None,
        apply_announce="",
        description="",
        beats_max=0,
        steps_max=0,
        combat=True,
        world=False,
        hidden=False,
        compounding=False,
        statustype="generic",
        persistent=False,
        tactical_mechanics="",
    ):
        self.name = name
        self.description = description
        # Terse, engine-owned mechanical summary for the combat LLM prompt.
        #
        # ``description`` is player-facing prose; this is the same facts written
        # for a tactical reader — the applied modifiers and the tick interval,
        # nothing else. It exists because ai/combat_strategist.py used to carry
        # a hand-typed copy of these numbers, which had already gone stale in
        # three places (it told the model Poisoned ticks every beat when
        # ``execute_on`` is 5, that Enflamed ticks every 3 beats when it ticks
        # every one, and that Slimed drains fatigue, which it has never done).
        # A wrong number in a combat prompt is worse than a missing one, so the
        # numbers live here, next to the code that applies them, and the adapter
        # only chooses a perspective to narrate them from.
        #
        # tests/test_states_tactical_mechanics.py fails if this text and the
        # state's real ``add_*`` deltas or ``execute_on`` interval disagree.
        self._tactical_mechanics = tactical_mechanics
        self.beats_max = int(beats_max)  # combat beats
        self.beats_left = int(self.beats_max)
        self.steps_max = int(steps_max)  # world steps
        self.steps_left = int(self.steps_max)
        self.apply_announce = apply_announce
        self.compounding = compounding  # something happens when this state is reapplied
        self.persistent = persistent

        self.target = target  # can be the same as the user in abilities with no targets
        self.source = source
        self.combat = combat
        self.world = world
        self.hidden = hidden
        self.statustype = statustype

    @property
    def tactical_mechanics(self):
        """The mechanical summary as it stands RIGHT NOW.

        Read, never stored, because a compounding state's modifiers move after
        ``__init__``: ``Slimed``, ``Petrified`` and ``Fervent`` all deepen an
        ``add_*`` in ``compound()``. A summary rendered once at application
        time therefore kept quoting the FIRST application's numbers for the
        rest of the fight — a stale modifier shipped straight into the combat
        prompt, which is the exact failure ``tactical_mechanics`` was added to
        end. Any state whose numbers can change overrides
        ``_render_tactical_mechanics`` below; the rest fall through to the text
        their constructor passed.
        """
        return self._render_tactical_mechanics()

    def _render_tactical_mechanics(self):
        """Build the summary from the state's current modifiers.

        This default returns the static string the constructor was passed, so
        for the states that take it, ``tactical_mechanics`` reports the NOMINAL
        class fraction. That is exact for them: nothing moves their modifiers
        after ``__init__``, so nominal and applied are the same number.

        Override in any state whose ``add_*`` values change after ``__init__``,
        where the two part company. The criterion is mechanical -- does
        ``compound()`` move an ``add_*``? -- and where it holds, the override
        renders through ``_applied_pct`` and the property means the APPLIED
        delta instead. ``Slimed``, ``Petrified`` and ``Fervent`` are today's
        three; ``tests/test_states_tactical_mechanics.py`` derives that set from
        the behaviour rather than listing it.

        The ``getattr`` default is for unpickling a save written before this
        field existed; overrides get the same protection from
        ``_applied_pct``, which reads every field it needs through ``getattr``
        for the same reason.
        """
        return getattr(self, "_tactical_mechanics", "")

    def _capture_bases(self, target, **stat_to_bonus):
        """Record the target stats this state's modifiers are being taken from.

        ``_applied_pct`` divides by these to report the fraction the engine
        really applied, so every state that renders live captures them. One
        named call rather than the same pair of lines (and the same pair of
        comment lines) copied into each such state.

        Captured through :func:`stat_without_state_bonus`, with the SAME
        ``(stat, add_*)`` pairing the ``add_*`` derivations below use, and not
        with a bare ``getattr(target, attr)``. The two have to be the same
        number or the reported fraction is wrong in a new way: on a
        re-application, ``refresh_stat_bonuses`` has already moved the live
        stat by this state's earlier contribution, so a bare read divides the
        new modifier by an already-penalised base and quotes a penalty deeper
        than the one applied. Keyword form because the pairing is the point --
        ``finesse="add_fin"`` cannot be miscounted the way two positional
        lists could drift out of step.
        """
        for attr, bonus_attr in stat_to_bonus.items():
            setattr(
                self,
                "_base_" + attr,
                stat_without_state_bonus(target, attr, bonus_attr, type(self)),
            )

    def _applied_pct(self, add_attr, base_attr, nominal_pct):
        """``add_attr`` as a percentage of the stat it was taken from.

        Read off the delta on the books rather than re-derived from the class
        fractions, because the two stop agreeing the moment a state compounds.
        ``compound()`` scales its extra step by the holder's CURRENT stat, and
        ``functions.refresh_stat_bonuses`` has already moved that stat by this
        same state's earlier ``add_*``. Summing the nominal fractions therefore
        quotes the combat prompt a modifier the engine never applied, and gets
        it wrong in both directions at once: a twice-compounded ``Petrified``
        added up to −40% finesse and −55% speed against −35 and −46 really
        applied, and to +45% protection against +50. Penalties read worse than
        they were, bonuses weaker, and both went into the prompt as fact.

        ``nominal_pct`` — the class's first-application fraction — is reached
        in exactly one case: ``base_attr`` is absent, because the state was
        unpickled from a save written before the base was captured. There is
        then no delta to divide and nothing better to say. Answering with the
        nominal beats raising, because ``StateEffectSerializer`` reads this
        property through ``getattr(state, "tactical_mechanics", "")`` — an
        exception here would not surface as a failure, it would quietly ship an
        empty mechanics line.

        A base that was captured and is ZERO is a different case, and used to
        share that branch. ``int(0 * fraction)`` is 0, so the engine applied
        nothing; quoting the nominal there told the combat prompt "+25%
        protection" for a modifier provably worth 0. A wrong number is worse
        than a missing one, which is the whole reason this property exists, so
        0 is reported as 0.
        """
        base = getattr(self, base_attr, _BASE_NOT_CAPTURED)
        if base is _BASE_NOT_CAPTURED:
            return _pct(nominal_pct)
        if not base:
            return _pct(0)
        return _pct(abs(getattr(self, add_attr, 0)) / base)

    def _extend_compounded_duration(self):
        """Stretch both clocks' ceilings on a re-application and refresh toward them.

        The block this replaces stood byte-identically in three ``compound()``
        methods. Each state now supplies only what is its own -- the modifier or
        tick it deepens -- and calls this for the part that is everybody's.
        """
        self.beats_max, self.beats_left = self._stretched_clock(
            self.beats_max, self.beats_left
        )
        self.steps_max, self.steps_left = self._stretched_clock(
            self.steps_max, self.steps_left
        )

    @classmethod
    def _stretched_clock(cls, ceiling, remaining):
        """One clock's new ``(ceiling, remaining)`` after a re-application.

        The refresh is a fraction of the NEW ceiling, and cannot push the
        remainder past it.
        """
        ceiling = int(ceiling * cls._COMPOUND_DURATION_MULT)
        return ceiling, min(
            remaining + int(ceiling / cls._COMPOUND_REFRESH_DIVISOR), ceiling
        )

    def effect(self, target):
        """
        to be overwritten by a state - this is the effect that occurs on a beat in combat or a step in the world
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def on_application(self, target):
        """
        to be overwritten by a state - effect that occurs when the state is initially applied
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def on_removal(self, target):
        """
        to be overwritten by a state - effect that occurs when the state is removed or expired
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def process(self, target):
        if self.combat and target.in_combat:
            self.effect(target)
            if self.beats_max > 0:
                self.beats_left -= 1
                if self.beats_left <= 0:
                    target.states.remove(self)
                    functions.refresh_stat_bonuses(target)
                    self.on_removal(target)
        elif self.world and not target.in_combat:
            self.effect(target)
            if self.steps_max > 0:
                self.steps_left -= 1
                if self.steps_left <= 0:
                    target.states.remove(self)
                    functions.refresh_stat_bonuses(target)
                    self.on_removal(target)


#: A state whose bonus is a percentage (or offset) of one of the target's stats
#: must never read that stat straight off the target: ``functions.reset_stats``
#: recomputes ``strength``/``finesse``/``speed``/``protection`` as
#: ``base + sum(add_* from equipped items and active states)``, so an already
#: active instance of the very same state is *folded into the number its own*
#: ``__init__``/``compound`` *reads back*. Re-application then feeds the bonus
#: into itself:
#:
#:   * A ``compounding`` state keeps the existing instance and calls
#:     ``compound()`` on it (see ``functions.inflict``), so the feedback is
#:     geometric and unbounded. Measured on a 20-strength target, ``Fervent``
#:     ran +6, +9, +13, +17, +22, +28, +35, +43 strength over eight
#:     re-applications -- the per-cast increment *accelerating* -- where the
#:     design intent ("the fire burns hotter") is a flat +15% per re-cast.
#:   * A non-compounding state is replaced wholesale, so the feedback converges
#:     rather than exploding, but it converges on the wrong number:
#:     ``SecretPlansState`` settled at +8 strength instead of the +6 a single
#:     cast grants (re-casting bought a free buff), while the percentage
#:     *debuffs* -- ``Disoriented``, ``Resonant`` -- got weaker on re-application
#:     because they were taking their cut of an already reduced stat.
#:
#: Every such bonus in this module therefore goes through
#: :func:`stat_without_state_bonus`, which strips the state's own contribution
#: before the percentage is taken. It deliberately keeps contributions from
#: equipment and from *other* states: that scaling is designed -- a -25%
#: protection mark should scale with the armour actually being worn.
#:
#: Deriving from the ``*_base`` attributes instead (``finesse_base`` etc. do
#: exist and are maintained) would also strip gear and other states, silently
#: retuning every one of these effects for any equipped target; and Player has
#: no ``protection_base`` at all -- its gear protection is recomputed by
#: ``refresh_protection_rating`` -- so the four protection-scaling states could
#: not use that route anyway. Half a rule is what produced this defect once
#: already.
def stat_without_state_bonus(target, stat_attr, bonus_attr, state_cls):
    """Read ``target.<stat_attr>`` with ``state_cls``'s own contribution removed.

    :param target: the player/NPC carrying the stat and a ``states`` list.
    :param stat_attr: live stat to read, e.g. ``"finesse"``.
    :param bonus_attr: the ``add_*`` attribute through which ``state_cls`` feeds
        that stat, e.g. ``"add_fin"``.
    :param state_cls: the state class whose contribution to exclude. Pass
        ``type(self)`` -- that is exactly the class-matching rule
        ``functions.inflict`` uses to decide an instance is already active.
    :return: the stat as it would read with no instance of ``state_cls``
        active, floored at 0. Non-numeric stats and targets without an
        iterable ``states`` (test doubles, partially built combatants) are
        returned untouched.
    """
    value = getattr(target, stat_attr, 0)
    if not isinstance(value, (int, float)):
        return value
    try:
        active = list(getattr(target, "states", ()) or ())
    except TypeError:
        return value
    for existing in active:
        if isinstance(existing, state_cls):
            contribution = getattr(existing, bonus_attr, 0)
            if isinstance(contribution, (int, float)):
                value -= contribution
    return max(0, value)


#: Evasion granted by :class:`Dodging` to a combatant with no finesse at all,
#: and the rate at which that grant decays as the dodger's own finesse rises.
#:
#: The bonus is *diminishing* in finesse (``BASE - int(finesse / DIVISOR)``)
#: rather than growing with it. The old shape, ``50 + int(finesse / 3)``, let
#: base finesse enter the to-hit expression twice — once as the defender
#: term and again, amplified, through the bonus — so the bestiary's evasion
#: spread compounded instead of flattening: a dodging Cave Bat (finesse 24) was
#: about 14% hittable and a dodging Wail Wraith (finesse 40) about 6%, i.e.
#: effectively untouchable, while a dodging King Slime was still easy prey.
#:
#: Decay keeps every dodger inside a single band. Against Jean at base stats
#: (finesse 11, intelligence 10, ``_base.HIT_CHANCE_BASE`` 85) the dodging
#: bestiary now sits at 33.7%–51.5% hittable, and Jean dodging drops incoming
#: hostile accuracy from roughly 70–87% to roughly 34–50%. Dodging is therefore
#: worth a beat for anyone and decisive for no one.
#:
#: Decay also makes the state self-limiting under re-application, and
#: :func:`stat_without_state_bonus` makes it exactly idempotent: ``__init__``
#: subtracts any active Dodging grant before reading finesse, so re-applying
#: re-derives the same number instead of oscillating toward a larger one.
DODGE_EVASION_BASE = 42
DODGE_EVASION_FINESSE_DIVISOR = 2
#: Floor so the state is never worthless (or negative). It binds once decay
#: would drop the grant below it — finesse above 54 at the values above.
DODGE_EVASION_MIN = 15


class Dodging(State):
    # Flat finesse points the stance is worth, plus a share of the holder's own
    # finesse -- a nimble character gets more out of a dodge than a clumsy one.
    # Named for tests/test_combat_strategist_coverage.py, which pins the
    # advisor's _DEFENSIVE_STANCE_BEATS against it. The evasion numbers are
    # module constants beside their rationale (DODGE_EVASION_*), because the
    # decay they describe is a bestiary-wide balance property rather than a
    # per-class tuning knob.
    _DURATION_BEATS = 7

    def __init__(
        self, target
    ):  # increases the target's dodging ability for a short duration
        super().__init__(
            name="Dodging",
            target=target,
            beats_max=self._DURATION_BEATS,
            hidden=True,
        )
        self.add_fin = max(
            DODGE_EVASION_MIN,
            DODGE_EVASION_BASE
            - int(
                stat_without_state_bonus(target, "finesse", "add_fin", type(self))
                / DODGE_EVASION_FINESSE_DIVISOR
            ),
        )

    def _render_tactical_mechanics(self):
        """Quote the grant this instance actually carries.

        A fixed string used to say "+evasion (large finesse bonus)". The decay
        makes that exactly backwards for a nimble dodger -- the nimbler the
        holder, the SMALLER the grant -- and the advisor was being told the
        opposite of the mechanic it was reasoning about.
        """
        return f"+{self.add_fin} finesse (evasion) while the stance holds"


class Parrying(State):
    _DURATION_BEATS = 7

    def __init__(
        self, target
    ):  # parries the next attack, giving the aggressor a large recoil duration
        super().__init__(
            name="Parrying",
            target=target,
            beats_max=self._DURATION_BEATS,
            hidden=True,
            tactical_mechanics="Parry stance active",
        )


class Poisoned(State):
    # Beat interval between damage ticks. Quoted by tactical_mechanics below,
    # so the model is never told a rate the effect does not run at.
    _EXECUTE_ON = 5
    # What a re-application does to the POISON itself: the tick counter jumps a
    # quarter, and since effect() scales damage by ``self.tick``, that is where
    # "worsens if reapplied" is actually spent. The clocks move separately and
    # by a different factor -- ``State._COMPOUND_DURATION_MULT``, which is 1.1,
    # not 1.25. The comment that used to sit in compound() called the whole
    # thing "25%", which was right about the strength and wrong about both
    # durations.
    _COMPOUND_TICK_MULT = 1.25

    def __init__(self, target):
        duration = random.randint(50, 150)
        steps = random.randint(20, 80)
        super().__init__(
            name="Poisoned",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=True,
            world=True,
            statustype="poison",
            persistent=True,
            description="Deals escalating HP damage every few beats. Worsens if reapplied.",
            tactical_mechanics=f"escalating HP DoT every {self._EXECUTE_ON} beats",
        )
        self.tick = 0  # increases at each effect cycle
        # when the tick is a multiple of this number, execute the effect
        self.execute_on = self._EXECUTE_ON

    def on_application(self, target):
        cprint("{} has been poisoned!".format(target.name), "magenta")

    def on_removal(self, target):
        cprint("{} is no longer poisoned!".format(target.name), "white")

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            damage = int(
                target.maxhp * (random.uniform(0.015, 0.035) + (self.tick * 0.003))
            )
            cprint(
                "{} shudders in pain from being poisoned, suffering {} damage!".format(
                    target.name, damage
                ),
                "red",
            )
            target.hp -= damage

    def compound(self, target):
        cprint("{}'s poisoning has gotten worse!".format(target.name), "magenta")
        self.tick = int(self.tick * self._COMPOUND_TICK_MULT)
        self._extend_compounded_duration()


# Balance constants for Enflamed (issue #343) -- tune here rather than
# scattering magic numbers through effect()/compound().
ENFLAMED_DAMAGE_PCT_PER_BEAT = 0.01  # fraction of target maxhp dealt per beat, before fire resistance
ENFLAMED_MIN_DAMAGE_PER_BEAT = 5  # floor once the target is taking any fire damage at all
ENFLAMED_MAX_BEATS = 25
ENFLAMED_MAX_STACKS = 3


class Enflamed(
    State
):  # target is engulfed in flames, taking damage every beat; COMBAT ONLY
    """Fire damage-over-time.

    Deals ENFLAMED_DAMAGE_PCT_PER_BEAT of the target's maxhp each beat
    (scaled by stack count, then reduced/amplified by fire resistance). Each
    beat also rolls a chance -- based on the target's resistance to the
    "enflamed" status itself -- to burn out early, so more fire-resistant
    targets both take less damage per beat and tend to shed the fire sooner.
    Reapplying while already burning adds a stack (capped at
    ENFLAMED_MAX_STACKS) and refreshes the duration, rather than creating a
    second, independent instance.
    """

    def __init__(self, target):
        super().__init__(
            name="Enflamed",
            target=target,
            beats_max=ENFLAMED_MAX_BEATS,
            steps_max=0,
            compounding=True,
            world=False,
            statustype="enflamed",
            persistent=False,
            description=(
                "Deals fire damage every beat, reduced by fire resistance. Each beat "
                "carries a chance to burn out early based on fire resistance. "
                "Stacks up to {} times.".format(ENFLAMED_MAX_STACKS)
            ),
            # No execute_on gate: effect() runs, and burns, on EVERY beat.
            tactical_mechanics=(
                f"fire DoT every beat, stacking up to {ENFLAMED_MAX_STACKS}×; "
                "reduced by fire resistance"
            ),
        )
        self.stacks = 1

    def on_application(self, target):
        cprint("{} has been set aflame!".format(target.name), "magenta")

    def on_removal(self, target):
        cprint("{} is no longer on fire.".format(target.name), "white")

    def effect(self, target):
        resistance_mult = functions.combat_resistance(target, "fire")
        raw_damage = (
            target.maxhp * ENFLAMED_DAMAGE_PCT_PER_BEAT * self.stacks * resistance_mult
        )
        # Floor at ENFLAMED_MIN_DAMAGE_PER_BEAT rather than the raw percentage:
        # 1% of a low-maxhp fodder enemy (e.g. a 20 HP Slime) is well under 5,
        # and Enflamed should stay a meaningful threat against exactly the
        # weak enemies most likely to be shot with a FlareArrow. Only applies
        # once fire is dealing *any* damage -- a target with 0 or negative
        # fire resistance (immune/healed by it) still takes nothing.
        damage = max(ENFLAMED_MIN_DAMAGE_PER_BEAT, math.ceil(raw_damage)) if raw_damage > 0 else 0
        if damage > 0:
            cprint(
                "{} writhes in the flames, suffering {} damage!".format(
                    target.name, damage
                ),
                "red",
            )
            target.hp -= damage

        # Each beat, a chance to burn out early -- scales with the target's
        # resistance to the enflamed status (0.0 = never shakes it off early,
        # 1.0 = always extinguished the very first beat).
        removal_chance = getattr(target, "status_resistance", {}).get("enflamed", 0.0)
        removal_chance = max(0.0, min(1.0, removal_chance))
        if removal_chance > 0 and random.random() < removal_chance:
            # State.process() decrements beats_left immediately after effect()
            # and removes the state once it hits 0 -- landing here at 1 makes
            # that happen on this same beat instead of waiting for beats_max.
            self.beats_left = 1

    def compound(self, target):
        # Reapplying adds a stack (up to the cap) and refreshes the duration,
        # rather than escalating tick/duration multipliers indefinitely.
        if self.stacks < ENFLAMED_MAX_STACKS:
            self.stacks += 1
            cprint(
                "{}'s flames intensify! ({} stacks)".format(target.name, self.stacks),
                "magenta",
            )
        else:
            cprint(
                "{}'s flames are already burning at their fiercest.".format(
                    target.name
                ),
                "magenta",
            )
        self.beats_left = self.beats_max


class Clean(State):
    # Flat stat points (``_POINTS``), not fractions of the holder's stat.
    _CHARISMA_BONUS_POINTS = 1
    _MAX_FATIGUE_BONUS_POINTS = 10

    def __init__(self, target):
        duration = 0
        steps = random.randint(50, 200)
        super().__init__(
            name="Clean",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=False,
            combat=False,
            world=True,
            statustype="clean",
            persistent=True,
            description=(
                f"Charisma +{self._CHARISMA_BONUS_POINTS}, "
                f"Max Fatigue +{self._MAX_FATIGUE_BONUS_POINTS}. "
                "Wears off as you travel."
            ),
        )
        self.tick = 0  # increases at each effect cycle
        self.execute_on = (
            0  # when the tick is a multiple of this number, execute the effect
        )
        self.add_charisma = self._CHARISMA_BONUS_POINTS
        self.add_maxfatigue = self._MAX_FATIGUE_BONUS_POINTS

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint("{} is now clean!".format(target.name), "magenta")

    def on_removal(self, target):
        functions.refresh_stat_bonuses(target)
        cprint("{} is no longer quite so clean!".format(target.name), "white")


# todo Add a Dirty state that can be compounded


class Disoriented(State):
    """Target is disoriented, reducing defensive capabilities and accuracy.

    Disoriented combatants struggle to maintain their defensive positioning,
    suffering reduced finesse and protection until the status expires.
    """

    # Fractions of the holder's own stat (``_PCT``), not flat points.
    _FINESSE_PENALTY_PCT = 0.30
    _PROTECTION_PENALTY_PCT = 0.25

    def __init__(self, target):
        duration = random.randint(8, 15)
        super().__init__(
            name="Disoriented",
            target=target,
            beats_max=duration,
            compounding=False,
            combat=True,
            world=False,
            statustype="disoriented",
            persistent=False,
            description=(
                f"Finesse -{_pct(self._FINESSE_PENALTY_PCT)}, "
                f"Protection -{_pct(self._PROTECTION_PENALTY_PCT)}. "
                "Defensive positioning is compromised."
            ),
            tactical_mechanics=(
                f"−{_pct(self._FINESSE_PENALTY_PCT)} finesse, "
                f"−{_pct(self._PROTECTION_PENALTY_PCT)} protection"
            ),
        )
        self.add_fin = -int(
            stat_without_state_bonus(target, "finesse", "add_fin", type(self))
            * self._FINESSE_PENALTY_PCT
        )
        self.add_protection = -int(
            stat_without_state_bonus(target, "protection", "add_protection", type(self))
            * self._PROTECTION_PENALTY_PCT
        )

    def on_application(self, target):
        cprint(
            "{} is disoriented and struggling to maintain balance!".format(target.name),
            "yellow",
        )
        functions.refresh_stat_bonuses(target)

    def on_removal(self, target):
        cprint("{} regains their bearings!".format(target.name), "green")


class Hawkeye(State):
    def __init__(
        self, target
    ):  # increases the target's accuracy with a ranged weapon for a short duration
        super().__init__(
            name="Hawkeye",
            target=target,
            beats_max=30,
            description="Ranged accuracy greatly increased.",
            tactical_mechanics="+ranged accuracy",
        )


class Slimed(State):
    """Corrosive slime residue clings to Jean's limbs and armor.

    The slime doesn't wash off. It seeps into every joint, every stitched seam,
    filling cracks Jean didn't know he had. The smell alone is enough to turn the stomach.
    """

    # Fractions of the holder's own stat (``_PCT``), not flat points. The
    # ``_COMPOUND_*`` pair is what each RE-application adds on top.
    _FINESSE_PENALTY_PCT = 0.20
    _PROTECTION_PENALTY_PCT = 0.15
    _COMPOUND_FINESSE_PENALTY_PCT = 0.05
    _COMPOUND_PROTECTION_PENALTY_PCT = 0.05
    _EXECUTE_ON = 6

    def __init__(self, target):
        duration = random.randint(30, 80)
        steps = random.randint(10, 40)
        super().__init__(
            name="Slimed",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=True,
            combat=True,
            world=True,
            statustype="slimed",
            persistent=True,
            description=(
                f"Finesse -{_pct(self._FINESSE_PENALTY_PCT)}, "
                f"Protection -{_pct(self._PROTECTION_PENALTY_PCT)}. "
                "Deals periodic acid damage. Worsens if reapplied."
            ),
            # tactical_mechanics is rendered by _render_tactical_mechanics
            # below, not passed here: compound() deepens both penalties, and a
            # summary frozen at first application would go on quoting the
            # original numbers for the rest of the fight.
        )
        self.tick = 0
        self.execute_on = self._EXECUTE_ON
        self._capture_bases(target, finesse="add_fin", protection="add_protection")
        self.add_fin = -int(
            stat_without_state_bonus(target, "finesse", "add_fin", type(self))
            * self._FINESSE_PENALTY_PCT
        )
        self.add_protection = -int(
            stat_without_state_bonus(target, "protection", "add_protection", type(self))
            * self._PROTECTION_PENALTY_PCT
        )

    def _render_tactical_mechanics(self):
        finesse = self._applied_pct(
            "add_fin", "_base_finesse", self._FINESSE_PENALTY_PCT
        )
        protection = self._applied_pct(
            "add_protection", "_base_protection", self._PROTECTION_PENALTY_PCT
        )
        return (
            f"−{finesse} finesse, −{protection} protection, "
            f"acid DoT every {self._EXECUTE_ON} beats"
        )

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint("{} is coated in corrosive slime!".format(target.name), "cyan")

    def on_removal(self, target):
        cprint("The corrosive slime finally sloughs away from {}.".format(target.name), "white")

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            damage = max(1, int(target.maxhp * random.uniform(0.008, 0.018)))
            cprint(
                "The slime burns into {}'s flesh! ({} damage)".format(target.name, damage),
                "red",
            )
            target.hp -= damage

    def compound(self, target):
        # Worsening on re-application is intended (compounding=True, "Worsens if
        # reapplied"). Each coat costs a further 5% of the *unslimed* stats, so
        # the escalation is linear per re-application rather than a fraction of
        # the already-slimed value -- which decayed toward zero finesse and, at
        # ordinary stat magnitudes, truncated to a no-op after the first coat.
        cprint("The slime coating on {} thickens!".format(target.name), "cyan")
        self.add_fin -= int(
            stat_without_state_bonus(target, "finesse", "add_fin", type(self))
            * self._COMPOUND_FINESSE_PENALTY_PCT
        )
        self.add_protection -= int(
            stat_without_state_bonus(target, "protection", "add_protection", type(self))
            * self._COMPOUND_PROTECTION_PENALTY_PCT
        )
        self._extend_compounded_duration()
        functions.refresh_stat_bonuses(target)


class Resonant(State):
    """The Wailing Badlands leave their mark in the chest, behind the sternum.

    A vibration that has no interest in your armor, that moves through iron and bone
    with equal indifference. The wail does not stop at the skin.
    """

    # Fraction of the holder's own finesse (``_PCT``), not flat points.
    _FINESSE_PENALTY_PCT = 0.25
    _EXECUTE_ON = 5

    def __init__(self, target):
        duration = random.randint(12, 22)
        super().__init__(
            name="Resonant",
            target=target,
            beats_max=duration,
            compounding=False,
            combat=True,
            world=False,
            statustype="stun",
            persistent=False,
            description=(
                f"Finesse -{_pct(self._FINESSE_PENALTY_PCT)}. Deals periodic "
                "armor-bypassing damage from resonant vibration."
            ),
            tactical_mechanics=(
                f"−{_pct(self._FINESSE_PENALTY_PCT)} finesse, "
                f"armor-piercing DoT every {self._EXECUTE_ON} beats"
            ),
        )
        self.tick = 0
        self.execute_on = self._EXECUTE_ON
        self.add_fin = -int(
            stat_without_state_bonus(target, "finesse", "add_fin", type(self))
            * self._FINESSE_PENALTY_PCT
        )

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(
            "{} staggers as the resonant wail tears through his defenses!".format(target.name),
            "yellow",
        )

    def on_removal(self, target):
        cprint(
            "The wail fades from {}. The silence, when it comes, is sudden.".format(target.name),
            "white",
        )

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            damage = max(1, int(target.maxhp * random.uniform(0.010, 0.020)))
            cprint(
                "The resonance within {} rebounds! ({} armor-bypassing damage)".format(
                    target.name, damage
                ),
                "yellow",
            )
            target.hp -= damage  # bypasses protection intentionally


class Death(State):
    """A final, absolute stillness. Not a wound — an ending.

    Inflicted by the WailWraith's Death Knell once its prey has nothing left
    to give (below 10% max FP). This is a one-shot execute, not a
    damage-over-time effect: on_application reduces HP to 0 directly and lets
    the ordinary defeat pipeline take it from there (is_alive()/check_revive()
    still run as normal, so a revive-capable state can still save the target).
    """

    def __init__(self, target):
        super().__init__(
            name="Death",
            target=target,
            beats_max=1,
            compounding=False,
            combat=True,
            world=False,
            statustype="death",
            persistent=False,
            description="A final stillness.",
        )

    def on_application(self, target):
        cprint(
            "{} goes still. The wail has claimed what it was owed.".format(
                target.name
            ),
            "magenta",
        )
        target.hp = 0


class Petrified(State):
    """Mineral sediment from the corrupted pools settles into joints and sinew.

    Not encasing, not crushing — just gradually convincing the body that movement
    costs too much. The crust is heavier than it looks. It is also harder.
    """

    # Fractions of the holder's own stat (``_PCT``), not flat points. The
    # ``_COMPOUND_*`` trio is what each RE-application adds on top.
    _FINESSE_PENALTY_PCT = 0.20
    _SPEED_PENALTY_PCT = 0.35
    _PROTECTION_BONUS_PCT = 0.25
    _COMPOUND_FINESSE_PENALTY_PCT = 0.10
    _COMPOUND_SPEED_PENALTY_PCT = 0.10
    _COMPOUND_PROTECTION_BONUS_PCT = 0.10
    _EXECUTE_ON = 6
    _FATIGUE_DRAIN_PCT = 0.05

    def __init__(self, target):
        duration = random.randint(20, 45)
        steps = random.randint(15, 30)
        super().__init__(
            name="Petrified",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=True,
            combat=True,
            world=True,
            statustype="stone",
            persistent=False,
            description=(
                f"Finesse -{_pct(self._FINESSE_PENALTY_PCT)}, "
                f"Speed -{_pct(self._SPEED_PENALTY_PCT)}, "
                f"Protection +{_pct(self._PROTECTION_BONUS_PCT)}. "
                "Drains Fatigue every few beats. Worsens if reapplied."
            ),
            # Rendered live below: compound() deepens all three modifiers.
        )
        self.tick = 0
        self.execute_on = self._EXECUTE_ON
        self._capture_bases(
            target, finesse="add_fin", speed="add_speed", protection="add_protection"
        )
        self.add_fin = -int(
            stat_without_state_bonus(target, "finesse", "add_fin", type(self))
            * self._FINESSE_PENALTY_PCT
        )
        self.add_speed = -int(
            stat_without_state_bonus(target, "speed", "add_speed", type(self))
            * self._SPEED_PENALTY_PCT
        )
        self.add_protection = int(
            stat_without_state_bonus(target, "protection", "add_protection", type(self))
            * self._PROTECTION_BONUS_PCT
        )

    def _render_tactical_mechanics(self):
        finesse = self._applied_pct(
            "add_fin", "_base_finesse", self._FINESSE_PENALTY_PCT
        )
        speed = self._applied_pct("add_speed", "_base_speed", self._SPEED_PENALTY_PCT)
        protection = self._applied_pct(
            "add_protection", "_base_protection", self._PROTECTION_BONUS_PCT
        )
        return (
            f"−{finesse} finesse, −{speed} speed, +{protection} protection, "
            f"fatigue drain every {self._EXECUTE_ON} beats"
        )

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(
            "Mineral sediment from the pools settles into {}'s joints.".format(target.name),
            "white",
        )

    def on_removal(self, target):
        cprint(
            "The mineral crust cracks and falls away from {}.".format(target.name),
            "white",
        )

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            drain = int(target.maxfatigue * self._FATIGUE_DRAIN_PCT)
            target.fatigue = max(0, target.fatigue - drain)
            if drain > 0:
                cprint(
                    "Moving against the mineral crust exhausts {}. ({} fatigue)".format(
                        target.name, drain
                    ),
                    "white",
                )

    def compound(self, target):
        cprint(
            "The mineral sediment deepens its grip on {}.".format(target.name),
            "white",
        )
        # Deepening on re-application is intended (compounding=True, "Worsens if
        # reapplied"); each layer is a share of the *uncrusted* stats, so the crust
        # thickens linearly. Taken off the already-crusted values, the protection
        # term in particular grew geometrically and without bound.
        self.add_fin -= int(
            stat_without_state_bonus(target, "finesse", "add_fin", type(self))
            * self._COMPOUND_FINESSE_PENALTY_PCT
        )
        self.add_speed -= int(
            stat_without_state_bonus(target, "speed", "add_speed", type(self))
            * self._COMPOUND_SPEED_PENALTY_PCT
        )
        self.add_protection += int(
            stat_without_state_bonus(target, "protection", "add_protection", type(self))
            * self._COMPOUND_PROTECTION_BONUS_PCT
        )
        self._extend_compounded_duration()
        functions.refresh_stat_bonuses(target)


class Hollowed(State):
    """A profound spiritual emptiness. Jean knows this better than anyone.

    The absence of feeling that follows overwhelming loss. In Aurelion, it manifests
    as a wound that can be inflicted and — with enough time, or the right presence — healed.
    """

    # Flat stat points (``_POINTS``), not fractions of the holder's stat.
    _FAITH_PENALTY_POINTS = 3
    _CHARISMA_PENALTY_POINTS = 2
    _ENDURANCE_PENALTY_POINTS = 2
    _EXECUTE_ON = 8

    def __init__(self, target):
        duration = random.randint(40, 80)
        steps = random.randint(30, 60)
        super().__init__(
            name="Hollowed",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=False,
            combat=True,
            world=True,
            statustype="apathy",
            persistent=True,
            description=(
                f"Faith -{self._FAITH_PENALTY_POINTS}, "
                f"Charisma -{self._CHARISMA_PENALTY_POINTS}, "
                f"Endurance -{self._ENDURANCE_PENALTY_POINTS}. "
                "Drains HP and Fatigue every few beats."
            ),
            tactical_mechanics=(
                f"−{self._FAITH_PENALTY_POINTS} faith, "
                f"−{self._CHARISMA_PENALTY_POINTS} charisma, "
                f"−{self._ENDURANCE_PENALTY_POINTS} endurance; "
                f"HP+fatigue drain every {self._EXECUTE_ON} beats"
            ),
        )
        self.tick = 0
        self.execute_on = self._EXECUTE_ON
        self.add_faith = -self._FAITH_PENALTY_POINTS
        self.add_charisma = -self._CHARISMA_PENALTY_POINTS
        self.add_endurance = -self._ENDURANCE_PENALTY_POINTS

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(
            "Something goes quiet in {}. The grief has emptied them out.".format(target.name),
            "white",
        )

    def on_removal(self, target):
        cprint("The hollowness in {}'s chest recedes.".format(target.name), "white")
        cprint("It is replaced by something harder to name.", "white")

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            hp_drain = max(1, int(target.maxhp * 0.005))
            fatigue_drain = int(target.maxfatigue * 0.06)
            target.hp -= hp_drain
            target.fatigue = max(0, target.fatigue - fatigue_drain)


class Fervent(State):
    """The moment the sword arm stops calculating and the heart takes over entirely.

    It is not wise. It is not safe. But it is real, and in a world this strange,
    that counts for something.
    """

    # ``_PCT`` values are fractions of the holder's own stat; ``_POINTS``
    # values are flat stat points. The two sat side by side under one naming
    # convention, which read as though endurance dropped by 3%.
    _STRENGTH_BONUS_PCT = 0.30
    _FINESSE_BONUS_PCT = 0.15
    _ENDURANCE_PENALTY_POINTS = 3
    # What each RE-application adds on top.
    _COMPOUND_STRENGTH_BONUS_PCT = 0.15
    _COMPOUND_ENDURANCE_PENALTY_POINTS = 2
    _COMPOUND_DURATION_BEATS = 10
    _EXECUTE_ON = 5

    def __init__(self, target):
        duration = random.randint(25, 50)
        super().__init__(
            name="Fervent",
            target=target,
            beats_max=duration,
            compounding=True,
            combat=True,
            world=False,
            statustype="enraged",
            persistent=False,
            description=(
                f"Strength +{_pct(self._STRENGTH_BONUS_PCT)}, "
                f"Finesse +{_pct(self._FINESSE_BONUS_PCT)}. "
                f"Endurance -{self._ENDURANCE_PENALTY_POINTS}. "
                "Drains HP and Fatigue every few beats."
            ),
            # Rendered live below: compound() raises strength and deepens the
            # endurance cost.
        )
        self.tick = 0
        self.execute_on = self._EXECUTE_ON
        self._capture_bases(target, strength="add_str", finesse="add_fin")
        self.add_str = int(
            stat_without_state_bonus(target, "strength", "add_str", type(self))
            * self._STRENGTH_BONUS_PCT
        )
        self.add_fin = int(
            stat_without_state_bonus(target, "finesse", "add_fin", type(self))
            * self._FINESSE_BONUS_PCT
        )
        self.add_endurance = -self._ENDURANCE_PENALTY_POINTS

    def _render_tactical_mechanics(self):
        strength = self._applied_pct(
            "add_str", "_base_strength", self._STRENGTH_BONUS_PCT
        )
        finesse = self._applied_pct("add_fin", "_base_finesse", self._FINESSE_BONUS_PCT)
        # Endurance is flat points, so compound() moves the applied value and
        # the reported one by the same amount; there is no stat to divide by.
        return (
            f"+{strength} strength, +{finesse} finesse, "
            f"−{abs(self.add_endurance)} endurance; "
            f"HP+fatigue drain every {self._EXECUTE_ON} beats"
        )

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(
            "The fire of conviction ignites in {}!".format(target.name),
            "red",
        )

    def on_removal(self, target):
        cprint(
            "The fire in {}'s chest gutters out. The cost of that intensity settles into his limbs.".format(
                target.name
            ),
            "yellow",
        )

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            self_damage = max(1, int(target.maxhp * random.uniform(0.008, 0.015)))
            fatigue_drain = int(target.maxfatigue * 0.04)
            cprint(
                "{}'s body pays for the oath. ({} overexertion damage)".format(
                    target.name, self_damage
                ),
                "yellow",
            )
            target.hp -= self_damage
            target.fatigue = max(0, target.fatigue - fatigue_drain)

    def compound(self, target):
        # Burning hotter on re-application is intended (compounding=True), but
        # the increment is a flat 15% of the *unfervent* strength. Read off the
        # already-fervent value it compounded geometrically: +6, +9, +13, +17,
        # +22, +28, +35, +43 strength over eight re-applications on a
        # 20-strength target, with no ceiling.
        cprint("The fire in {} burns hotter!".format(target.name), "red")
        self.add_str += int(
            stat_without_state_bonus(target, "strength", "add_str", type(self))
            * self._COMPOUND_STRENGTH_BONUS_PCT
        )
        self.add_endurance -= self._COMPOUND_ENDURANCE_PENALTY_POINTS
        self.beats_left = min(
            self.beats_max, self.beats_left + self._COMPOUND_DURATION_BEATS
        )
        functions.refresh_stat_bonuses(target)


class PhoenixRevive(State):
    # Fractions, not percentages already multiplied out: _pct renders them.
    _REVIVE_CHANCE = 0.25
    _REVIVE_HP_PCT = 0.50

    def __init__(self, target):
        super().__init__(
            name="Phoenix Revive",
            target=target,
            beats_max=0,
            steps_max=0,
            compounding=False,
            combat=True,
            world=False,
            statustype="revive",
            persistent=True,
            description=(
                f"{_pct(self._REVIVE_CHANCE)} chance to revive at "
                f"{_pct(self._REVIVE_HP_PCT)} HP upon fatal damage. Consumed on use."
            ),
        )
        # Instance attribute so a caller can buff a single revive's odds; the
        # class constant is the value the description quotes.
        self.chance = self._REVIVE_CHANCE

    def on_removal(self, target):
        # Remove the revive state after it triggers
        cprint(
            "The warm, golden light around {} has faded.".format(target.name),
            "yellow",
        )

    def try_revive(self, target):
        if target.hp <= 0 and random.random() < self.chance:
            target.hp = int(target.maxhp * self._REVIVE_HP_PCT)
            cprint(
                "A warm, golden light envelopes {}, who is healed for {} HP!".format(
                    target.name, target.hp
                ),
                "yellow",
            )
            if self in target.states:
                target.states.remove(self)
            self.on_removal(target)
            functions.refresh_stat_bonuses(target)
            return True
        return False


class WarCryStunned(State):
    """Applied by War Cry. Prevents NPC move selection for 1 combat beat."""

    def __init__(self, target):
        super().__init__(
            name="War Cry Stunned",
            target=target,
            # beats_max=2 gives 1 effective skip of move selection: cycle_states()
            # decrements and removes the state in the same call that runs just
            # before _process_npc checks `_stunned` for this beat, so beats_max=1
            # would expire before the check ever sees it.
            beats_max=2,
            compounding=False,
            combat=True,
            world=False,
            statustype="stun",
            persistent=False,
            description="Reeling from a war cry — unable to act for one beat.",
        )
        self._stunned = True


#: Default lifetime of a Staggered state, in beats. Long enough for the Heavy
#: Handed passive, whose victim is expected to cast again shortly. Read by
#: src/moves/_utility.py, which is why it is a module constant rather than a
#: class attribute like the rest of this file's tuning values.
STAGGERED_DEFAULT_BEATS = 3


class Staggered(State):
    """Target's next move has +5 prep beats.

    Applied by the Heavy Handed passive and by Disrupt's braced read.

    ``beats_max`` is a parameter because the penalty is only consumed at the
    target's next ``Move.cast()``, so a fixed lifetime silently no-ops whenever
    the target has more than that many beats of committed animation left to
    burn. Disrupt hits exactly that case -- its braced branch deliberately lets
    the current wind-up resolve, which always takes more than the default three
    beats -- so it passes a duration derived from the target's own remaining
    stage beats. Heavy Handed keeps the default.
    """

    #: Prep beats added to the target's next move. Named because it is quoted
    #: three times -- the description, the tactical_mechanics line the advisor
    #: reads, and the penalty itself -- and those three had no way to disagree
    #: only while it was one value.
    _PREP_PENALTY_BEATS = 5

    def __init__(self, target, beats_max=STAGGERED_DEFAULT_BEATS):
        super().__init__(
            name="Staggered",
            target=target,
            beats_max=beats_max,
            compounding=False,
            combat=True,
            world=False,
            statustype="stun",
            persistent=False,
            description=(
                "Reeling from a heavy blow — the next move takes "
                f"+{self._PREP_PENALTY_BEATS} prep beats."
            ),
            tactical_mechanics=(
                f"next move costs +{self._PREP_PENALTY_BEATS} prep beats, once"
            ),
        )
        self.prep_penalty = self._PREP_PENALTY_BEATS
        self.penalty_consumed = False

    def on_application(self, target):
        cprint(f"{target.name} reels from the heavy blow!", "yellow")


class SecretPlansState(State):
    """Applied by Secret Plans: one bonus fraction across three stats."""

    # One fraction of the holder's own stat, applied to all three.
    _STAT_BONUS_PCT = 0.30
    _DURATION_BEATS = 25

    def __init__(self, target):
        super().__init__(
            name="Secret Plans",
            target=target,
            beats_max=self._DURATION_BEATS,
            compounding=False,
            combat=True,
            world=False,
            statustype="generic",
            persistent=False,
            description=(
                f"Strength +{_pct(self._STAT_BONUS_PCT)}, "
                f"Finesse +{_pct(self._STAT_BONUS_PCT)}, "
                f"Speed +{_pct(self._STAT_BONUS_PCT)} for {self._DURATION_BEATS} beats."
            ),
            tactical_mechanics=(
                f"+{_pct(self._STAT_BONUS_PCT)} strength, "
                f"+{_pct(self._STAT_BONUS_PCT)} finesse, "
                f"+{_pct(self._STAT_BONUS_PCT)} speed"
            ),
        )
        self.add_str = int(
            stat_without_state_bonus(target, "strength", "add_str", type(self))
            * self._STAT_BONUS_PCT
        )
        self.add_fin = int(
            stat_without_state_bonus(target, "finesse", "add_fin", type(self))
            * self._STAT_BONUS_PCT
        )
        self.add_speed = int(
            stat_without_state_bonus(target, "speed", "add_speed", type(self))
            * self._STAT_BONUS_PCT
        )

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(f"{target.name}'s hidden plan springs into motion!", "cyan")

    def on_removal(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(f"The momentum of {target.name}'s secret plan fades.", "cyan")


class BloodOfMartyrsState(State):
    """Applied by Blood of Martyrs. Tracks absorbed damage; _absorbing flag intercepts hit()."""

    def __init__(self, target):
        super().__init__(
            name="Blood of Martyrs",
            target=target,
            beats_max=45,
            compounding=False,
            combat=True,
            world=False,
            statustype="generic",
            persistent=False,
            description="Absorbing all incoming damage. The reckoning approaches.",
        )
        self._absorbing = True
        self.absorbed = 0

    def on_application(self, target):
        cprint(f"{target.name} opens himself to the storm. Every blow will be answered.", "yellow")

    def on_removal(self, target):
        self._absorbing = False


class Quarried(State):
    """Applied by Marked Quarry (Mara's ally signature move). The target's
    weak points are called out, reducing their protection.

    A perception mark rather than a mental/physical status — applied with
    force=True, bypassing status resistance (there is no resisting being
    seen clearly)."""

    # Fraction of the holder's own protection, not flat points.
    _PROTECTION_PENALTY_PCT = 0.25
    _DURATION_BEATS = 15

    def __init__(self, target):
        super().__init__(
            name="Quarried",
            target=target,
            beats_max=self._DURATION_BEATS,
            compounding=False,
            combat=True,
            world=False,
            statustype="generic",
            persistent=False,
            description=(
                "Weak points exposed — protection reduced by "
                f"{_pct(self._PROTECTION_PENALTY_PCT)}."
            ),
            tactical_mechanics=f"−{_pct(self._PROTECTION_PENALTY_PCT)} protection",
        )
        self.add_protection = -int(
            stat_without_state_bonus(target, "protection", "add_protection", type(self))
            * self._PROTECTION_PENALTY_PCT
        )

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)

    def on_removal(self, target):
        functions.refresh_stat_bonuses(target)


class StoneBulwarkState(State):
    """Applied by Stone Bulwark (Gorran's ally signature move) to each party
    member: bonus protection scaling with Gorran's own for 20 beats."""

    def __init__(self, target, amount):
        super().__init__(
            name="Stone Bulwark",
            target=target,
            beats_max=20,
            compounding=False,
            combat=True,
            world=False,
            statustype="generic",
            persistent=False,
            description="Shielded by living stone — bonus protection.",
        )
        self.add_protection = int(amount)

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)

    def on_removal(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(f"The stone shielding {target.name} crumbles away.", "cyan")
