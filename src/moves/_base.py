"""Move base class, PassiveMove base, and shared combat helpers."""

from src.narration import colored, cprint, narrate  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
from types import SimpleNamespace
import src.states as states  # noqa: F401
import src.functions as functions  # noqa: F401
import src.items as items  # noqa: F401
import src.positions as positions  # noqa: F401
from src.animations import animate_to_main_screen as animate  # noqa: F401
from src.combatant import (
    MOVE_STAGE_EXECUTE,
    MOVE_STAGE_PREP,
    OUTCOME_KEY,
    OUTCOME_TARGET_KEY,
    PENDING_ANIMATION_ATTR,
)


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


def safe_isfinite(value):
    """``math.isfinite`` that cannot itself raise.

    ``math.isfinite`` floats its argument first, so an int too large for a
    float (``10**400``) raises OverflowError from the very check meant to
    reject bad numbers -- a crafted save carrying an astronomical stat crashed
    the guard instead of being caught by it. Such a value is mathematically
    finite but unusable by every consumer here (they all ``float()`` or
    ``int()`` it next), so it reads as non-finite, which every caller treats
    as "degrade to the safe default".
    """
    try:
        return math.isfinite(value)
    except (TypeError, ValueError, OverflowError):
        return False


def _num(value, default=0.0):
    """Coerce to a *finite* float, or ``default`` for anything else.

    Applied per *term* rather than around a whole expression on purpose:
    a weapon that carries a real ``damage`` but a missing or unusable
    ``str_mod`` should still score off its damage, not collapse to the
    no-weapon fallback. Wrapping the whole sum instead is what made the
    earlier hand-rolled power lines silently bottom out at 1.

    Non-finite counts as unusable: an inf/nan survives ``float()`` and then
    detonates on a downstream ``int()``, mid-beat, off a value only a crafted
    save can supply -- and an int too large to float raises OverflowError from
    ``float()`` itself, which is why that lands in the except tuple too.
    """
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(value):
        return default
    return value


# ── Attack outcome channel ──────────────────────────────────────────────────
# The engine resolves what an attack did; the API must never re-derive it from
# the narration prose. ``hit()``/``miss()``/``parry()`` publish one of these
# names onto the acting entity's pending animation, which the combat adapter
# reads verbatim.
#
# These are engine facts. The *wire* vocabulary that carries them to the client
# is ``OUTCOMES`` in src/api/schemas/combat_beat.py (mirrored in
# frontend/src/utils/combatBeatSchema.js); every name below must be a member of
# it, which tests/test_combat_outcome_channel.py asserts. The engine does not
# import the API schema -- adaptation flows one way only.
OUTCOME_HIT = "hit"
OUTCOME_GLANCE = "glance"
OUTCOME_MISS = "miss"
OUTCOME_PARRY = "parry"
OUTCOME_ABSORB = "absorb"

#: Every outcome a Move can publish. Contract-tested against the wire vocabulary.
MOVE_OUTCOMES = (
    OUTCOME_HIT,
    OUTCOME_GLANCE,
    OUTCOME_MISS,
    OUTCOME_PARRY,
    OUTCOME_ABSORB,
)


def publish_outcome(entity, outcome, target=None):
    """Record ``outcome`` (against ``target``) on ``entity``'s pending animation.

    The adapter tags the acting combatant with a ``_pending_animation`` dict
    before a move runs and reads the outcome the moment it appears, so the
    animation and its impact SFX are attributed to the entity that actually
    swung -- never to a bystander that happens to narrate in the same beat.

    **Outcomes are per target, not per swing.** An arc attack resolves
    independently against every enemy it reaches: one may parry, one may be
    missed, two may be struck clean. Each of those is published separately,
    immediately before the line that narrates it, and the adapter emits one
    impact per publication. ``target`` is the combatant this particular
    resolution happened to -- the *object*, not a wire id; mapping it to an id
    is the API's job, not the engine's.

    Call this once per resolution and narrate immediately afterwards: the
    adapter pairs each published outcome with the next narration line, so a
    publication with no line of its own would be attributed to whatever is
    narrated next.

    A no-op outside the API (no pending animation), and deliberately silent
    about entities that carry a non-dict placeholder, so nothing here can crash
    the combat loop.
    """
    pending = getattr(entity, PENDING_ANIMATION_ATTR, None)
    if isinstance(pending, dict):
        pending[OUTCOME_KEY] = outcome
        # Always assign (never just when target is truthy): a stale target left
        # over from the previous enemy in an arc loop would silently reattribute
        # this resolution to the wrong combatant.
        pending[OUTCOME_TARGET_KEY] = target


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


#: Moved here from ``_sword.py``. It is weapon-agnostic -- it reads only
#: ``user`` and the equipped weapon, and mirrors ``standard_evaluate_attack``'s
#: power line -- but living in a leaf weapon module meant ``_scythe``,
#: ``_polearm``, ``_dagger`` and ``_unarmed`` all imported sideways from a
#: peer, and a scythe maintainer had no reason to look in the sword file.
#: Every module already imports ``_base``, so there is no cycle risk.
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
    flat-damage ones.  It is deliberately pure — it reads ``user`` and returns
    a number, never writing move state — so repeated ``evaluate()`` calls stay
    idempotent.

    Every term is coerced through the module-level ``_num`` (see its docstring
    for why per-term rather than around the whole expression).
    """
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


def _apply_blade_mastery_discount(user, fatigue_cost, floor_fatigue=10):
    """BladeMastery passive: sword attacks cost less fatigue.

    Shared by the standard attack pipeline and any hand-rolled attack (e.g.
    basic Attack) that wants the same discount applied to its own fatigue math.
    """
    if getattr(getattr(user, "eq_weapon", None), "subtype", None) == "Sword" and any(
        getattr(m, "name", "") == "Blade Mastery"
        for m in getattr(user, "known_moves", [])
    ):
        fatigue_cost = max(floor_fatigue, int(fatigue_cost * 0.85))
    return fatigue_cost


#: Hard bounds on any rolled hit chance, applied as the last step of
#: ``_apply_to_hit_modifiers`` — the single funnel every attack path in the
#: moves package passes its final number through.
#:
#: Why a ceiling at all: ``to_hit_chance`` is additive and unbounded above, so
#: whatever base a move family picks, a high-finesse attacker against a
#: low-finesse target eventually exceeds it. At HIT_CHANCE_BASE = 85 a
#: finesse-25 Jean already computes 101 against a finesse-4 KingSlime, and the
#: roll is ``random.randint(0, 100)`` — a guaranteed hit, with no dice left in
#: the dice game. The same creep reaches the ally heavies in ``_npc.py``. No
#: choice of base fixes that; only a ceiling does. 95 is deliberately high
#: enough to leave the tuned band (85 player / 76 hostile / 88+83 ally, and the
#: reshaped ``Dodging`` state) untouched and only trim the extremes.
#:
#: Why a floor: the facing multiplier is *sub*-unit head-on (0.95), and
#: ``int(1 * 0.95)`` is 0 — a positive chance silently truncated into a
#: certain miss. The floor keeps a slim chance slim rather than nil.
#:
#: Neither bound touches non-positive values: those are the auto-miss
#: sentinel (-1, target out of range) and must stay non-positive. See
#: ``_apply_facing_accuracy``.
HIT_CHANCE_CEILING = 95
HIT_CHANCE_FLOOR = 1


def clamp_hit_chance(hit_chance):
    """Bound a real hit chance to [HIT_CHANCE_FLOOR, HIT_CHANCE_CEILING].

    Call this **only** with a value already established to be a genuine chance
    rather than an auto-miss sentinel — every caller here does that with an
    explicit ``if hit_chance <= 0: return hit_chance`` guard first. The floor
    is applied unconditionally by design: the whole reason it exists is that a
    sub-unit multiplier (the 0.95 frontal, HauntingPresence's 0.85) truncates a
    slim-but-real chance to 0, and a floor that bailed out on non-positive
    input would never fire in exactly the case it was written for.
    """
    return max(HIT_CHANCE_FLOOR, min(HIT_CHANCE_CEILING, int(hit_chance)))


def facing_angle_diff(attacker, defender):
    """Attack angle (0-180°) of ``attacker`` against ``defender``'s guard.

    Returns None when either combatant lacks a resolved ``combat_position``
    (the 2D coordinate combat system is not active for this fight), so callers
    can no-op rather than invent an angle.

    Delegates the argument order to ``positions.attack_angle_diff`` — read that
    docstring before touching this. 0° means the defender is looking at the
    attacker; 180° means the attacker is at the defender's back.
    """
    attacker_pos = getattr(attacker, "combat_position", None)
    defender_pos = getattr(defender, "combat_position", None)
    if attacker_pos is None or defender_pos is None:
        return None
    return positions.attack_angle_diff(attacker_pos, defender_pos)


def facing_damage_multiplier(attacker, defender, steepness=1.0):
    """Damage multiplier for ``attacker``'s attack angle against ``defender``.

    ``steepness`` scales the baseline curve's *deviation* from 1.0 rather than
    the multiplier itself, so a steeper move stays anchored to the same shape:
    ``1.0 + (baseline - 1.0) * steepness``. At steepness 1.0 it short-circuits
    to ``positions.get_damage_modifier`` itself (0.85 front / 1.15 flank /
    1.25 deep flank / 1.40 rear) rather than round-tripping through that
    arithmetic, which is not exact in binary floating point; at 2.0 every
    band's bonus and penalty doubles. One table, one shape, one place to
    retune.

    Returns 1.0 (no-op) when positions are unavailable or anything goes wrong.
    """
    try:
        angle_diff = facing_angle_diff(attacker, defender)
        if angle_diff is None:
            return 1.0
        baseline = positions.get_damage_modifier(angle_diff)
        if steepness == 1.0:
            # Return the table value untouched rather than round-tripping
            # it through 1.0 + (x - 1.0): 1.15 is not exactly representable,
            # so that arithmetic yields 1.1499999999999999 and int() then
            # truncates a 115-damage flank to 114.
            return baseline
        # Same truncation hazard one step further out, and the short-circuit
        # above does NOT cover it: at Backstab's steepness of 2.0,
        # 1.0 + (1.15 - 1.0) * 2.0 is 1.2999999999999998, so int() shaved a
        # point off every flank and rear hit by the one move whose entire
        # identity is positional. Round to a precision far finer than any
        # curve this table will ever carry.
        return round(1.0 + (baseline - 1.0) * float(steepness), 9)
    except Exception:
        return 1.0


def apply_facing_damage(attacker, defender, power, steepness=1.0):
    """Scale an attack's ``power`` by the facing/angle damage curve (issue #394).

    Companion to ``_apply_facing_accuracy``: flanks and backs are both easier
    to *hit* and harder to *absorb*. Applied to power (pre-protection), matching
    what Backstab — for a long time the engine's only facing-aware damage
    path — has always done, so armour keeps its full bite from every angle.

    A non-finite power collapses to 0 -- ``int(inf)``/``int(nan)`` raise from
    inside the combat loop, and a crafted save can put any of them on a move.
    Checked BEFORE the sign guard: ``-inf`` satisfies ``power <= 0`` and used
    to be returned untouched, straight into the bare ``int()`` consumers in
    ``_npc.py``. A finite non-positive power is then returned untouched: a
    weaponless or fully-nullified attack should stay at zero rather than be
    floored up to 1 by a flank bonus.
    """
    if not safe_isfinite(power):
        return 0
    if power <= 0:
        return power
    multiplier = facing_damage_multiplier(attacker, defender, steepness)
    if multiplier == 1.0:
        return power
    return max(1, int(power * multiplier))


#: The engine's damage-variance band. ``standard_execute_attack`` and every
#: hand-rolled attack that copies its damage line multiply the resolved damage
#: by ``random.uniform(0.8, 1.2)``; these are the two ends of that roll, and
#: they are what ``damage_bounds`` reports as min and max.
DAMAGE_VARIANCE_MIN = 0.8
DAMAGE_VARIANCE_MAX = 1.2


#: Width of the glancing-blow window: a roll that lands within this many
#: points of the hit chance halves the damage. Previously a bare ``10``
#: copy-pasted into every attack's execute() -- retuning the window meant a
#: sweep across ~24 sites, any one of which could be missed silently.
GLANCE_MARGIN = 10


def apply_glancing_blow(damage, hit_chance, roll):
    """Apply the engine's glancing-blow rule to a resolved damage value.

    Returns ``(int_damage, glance)`` -- the final integer damage exactly as
    the inline block produced it, and whether the blow glanced. The inline
    shape this replaces was::

        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True
        damage = int(damage)

    hand-written at ~24 sites. Bit-identity is grid-proved by
    ``tests/test_moves_base_coverage.py::TestApplyGlancingBlow`` for both
    shapes in use: the float shape above (``int(damage / 2)`` on a glance),
    and ``_npc.py``'s ranged attacks, which halve an already-``int`` damage
    with ``damage // 2`` -- for a non-negative int the two agree, but the
    int path is kept explicit so the equivalence is by construction, not by
    the inputs happening to stay in range.

    Only the sites with exactly that shape route through here. A handful of
    moves put the halving elsewhere in their order of operations and keep it
    inline, each labelled at the site. This docstring deliberately does not
    enumerate them -- per the ``to_hit_chance`` precedent, a partial list in
    the one place people look for authority reads as exhaustive.
    ``grep -rn "NOT apply_glancing_blow" src/moves/`` is the authority; each
    label explains its own shape.
    """
    if hit_chance >= roll and hit_chance - roll < GLANCE_MARGIN:
        if isinstance(damage, int):
            return damage // 2, True
        return int(damage / 2), True
    return int(damage), False


def _resolve_heat(attacker, heat=None):
    """Heat multiplier to score damage with: an explicit override, else the
    attacker's live ``heat``, else 1.0 for anything missing or non-finite.

    NPCs carry ``heat`` too, but a degraded/mock combatant may not; a preview
    must degrade to "no heat scaling" rather than raise inside the poll path.
    """
    if heat is None:
        heat = getattr(attacker, "heat", 1.0)
    try:
        heat = float(heat)
    except (TypeError, ValueError, OverflowError):
        # OverflowError: float(10**400) raises -- an unfloatable int heat is
        # as unusable as a string one.
        return 1.0
    if not math.isfinite(heat):
        return 1.0
    return heat


#: ``Move.hit``'s heat reward for a landed hit by Jean, stated as a name
#: so ``projected_hit_heat_sequence`` below can replay the same reward. The
#: real contract with ``Move.hit``: the heat-tooltip test
#: (``tests/test_heat_rules_contract.py``) AST-counts the *literal*
#: arguments of every ``change_heat()`` call in this file against the
#: player-facing rules table, so ``Move.hit`` must keep passing its literal
#: ``1.25`` -- swapping it for this Name would drop one 1.25 from the counted
#: multiset and fail that contract. ``tests/test_moves_base_coverage.py``
#: pins this constant equal to that literal so the two cannot drift.
HEAT_GAIN_ON_HIT = 1.25


def projected_hit_heat_sequence(user, count):
    """Heat ``user`` would be at before each of ``count`` consecutive landed
    hits, heat feedback included.

    A multi-strike move resolves each strike's damage *before* its ``hit()``,
    and ``Move.hit`` multiplies Jean's heat by ``HEAT_GAIN_ON_HIT`` per landed
    blow -- so strike two is scored at the heat strike one earned. Previews of
    such moves (Lightning Assault) need the same sequence, computed with the
    user's REAL ``change_heat`` rather than a second copy of its
    clamp-and-round arithmetic.

    The replay runs on a **detached shim**, never on the live combatant. The
    earlier save-and-restore mutated ``user.heat`` for the duration of every
    preview poll -- a move resolving mid-window scored at inflated heat and
    its own write was clobbered by the restore -- and replaying from the raw
    ``user.heat`` let a crafted non-finite heat raise out of every combat
    poll. Instead the shim is seeded with the *sanitised* heat
    (``_resolve_heat``) and the real method is invoked unbound
    (``type(user).change_heat(shim, ...)``), so the genuine clamp arithmetic
    still runs with zero live mutation. A replay the method itself cannot
    survive degrades to a flat sequence.

    A combatant without the Jean-gated bookkeeping (an NPC, a degraded user)
    scores every strike at its current heat -- exactly what ``Move.hit`` does
    for it.
    """
    seed = _resolve_heat(user, None)
    if getattr(user, "name", None) != "Jean" or not hasattr(user, "change_heat"):
        return [seed] * count
    shim = SimpleNamespace(heat=seed)
    heats = []
    try:
        change_heat = type(user).change_heat
        for _ in range(count):
            heats.append(shim.heat)
            change_heat(shim, HEAT_GAIN_ON_HIT)
    except (TypeError, ValueError, AttributeError, OverflowError):
        # A change_heat the shim cannot satisfy (a mock, an exotic override):
        # degrade to no-heat rather than raise out of the poll path.
        return [seed] * count
    return heats


def target_protection(target):
    """``target``'s armour value, sanitised into a number the damage line can
    safely subtract.

    A missing, ``None`` or otherwise non-numeric ``protection`` reads as 0
    rather than raising inside the combat loop, and a **bool** reads as 0 too:
    ``isinstance(True, int)`` is True, so an unsanitised subtraction quietly
    charged one point of armour for a flag somebody set on the wrong attribute.

    One definition, three former copies. ``damage_bounds``,
    ``flat_arc_damage_bounds`` and Jab's flat line each carried this block
    verbatim, and all three had to stay in agreement for a preview and the
    ``execute()`` it predicts to agree about the same defender -- while the
    ~20 hand-written execute() copies of the canonical line did not sanitise
    at all, so the preview quietly reported a number for a target whose
    protection made the real swing raise.
    """
    protection = getattr(target, "protection", 0)
    if not isinstance(protection, (int, float)) or isinstance(protection, bool):
        return 0
    if not safe_isfinite(protection):
        # NaN/inf reach int() in flat_arc_damage_bounds and in the three flat
        # arc execute()s, which raise ValueError/OverflowError from inside the
        # combat loop -- a preview poll that 500s every time, or a wedged
        # fight. _resolve_heat and combat_resistance both coerce for the same
        # reason (issue #296); this sanitiser stopped one step short of them.
        # safe_isfinite rather than math.isfinite: an unfloatable int armour
        # (10**400) made the finiteness check itself raise OverflowError.
        return 0
    return protection


def resolve_damage(
    attacker,
    target,
    faced_power,
    damage_type,
    heat=None,
    protection=None,
    variance=None,
):
    """**The engine's canonical damage expression, stated once.**

    ``(((faced_power * resistance) - protection) * heat) * variance``, clamped
    at zero, returned as a float so the caller can apply its own glancing-blow
    halving and ``int()`` where the engine does.

    Scope, precisely: this is the only copy of the *canonical* line, but the
    engine deliberately runs other damage shapes beside it --
    ``flat_resisted_damage`` (Jab: resistance and protection, no heat, no
    variance), the flat arc line in ``flat_arc_damage_bounds`` (Reap, Sweep,
    Halberd Spin: protection only, floored at 1), and ``_npc.py``'s NPC
    family, which rolls its variance into *power* inside ``evaluate()`` and
    subtracts protection flat. Do not trust that as a count -- per the
    ``to_hit_chance`` precedent, an enumeration here reads as exhaustive the
    day after it stops being so; the sibling helpers in this module and
    ``grep -rn "NOT apply_glancing_blow" src/moves/``'s labelled sites are
    the authority. PowerStrike is now on this line; Jab is not and must not
    be -- see ``flat_resisted_damage`` and ``Jab.execute`` for the design
    reasoning. None of those is a drifted copy of this expression; a new
    *canonical* copy is what must never come back.

    This line used to be written out by hand at roughly two dozen ``execute()``
    sites plus ``damage_bounds``, which is the *prediction* of it the player
    commits a beat to. Two of those copies had silently drifted -- Jab and
    Power Strike each advertised twice the damage they dealt, for months --
    because a copy that has drifted is indistinguishable from one that has not.
    ``damage_bounds`` now predicts by calling this function with ``variance``
    pinned to each end of the band, so the two cannot disagree.

    **Term order is load-bearing.** CLAUDE.md records what happened the last
    time an expression in this engine was "simplified" into an algebraically
    equal regrouping (``to_hit_chance``: a one-point shift for ~0.7% of integer
    stat pairs, because binary floating point is not associative and ``int()``
    truncates). ``tests/test_canonical_damage_expression.py`` runs the
    pre-extraction expression against this one over a wide grid and demands
    bit-identical floats; do not regroup these terms.

    ``attacker`` is read for one thing only -- its ``heat`` -- via
    ``_resolve_heat``, so pass the combatant whose heat is being spent
    (which is not always ``move.user``: Riposte scores with a temporarily
    boosted ``player.heat``). ``heat`` overrides that outright; leave it None
    for the live value.

    ``protection`` overrides the defender's armour for the moves that
    deliberately do not score all of it. This docstring does not enumerate
    them -- an earlier enumeration here had already gone stale (it omitted
    Impale's 40% override), and per the CLAUDE.md ``to_hit_chance``
    precedent a partial list in the one place people look for authority
    reads as exhaustive. ``grep -rn "protection=" src/moves/`` is the
    authority; read the call site. Left None it is the sanitised
    ``target_protection`` read.

    A non-positive or non-finite product collapses to ``0.0``. Both were
    already the intent: every call site followed the expression with
    ``max(0, damage)`` or ``if damage <= 0: damage = 0``, and a non-finite
    product crashed on the call site's own ``int()`` before ``Move.hit``'s
    sanitiser (issue #296) could ever see it.
    """
    if protection is None:
        protection = target_protection(target)
    if variance is None:
        variance = random.uniform(DAMAGE_VARIANCE_MIN, DAMAGE_VARIANCE_MAX)
    resistance = functions.combat_resistance(target, damage_type)
    damage = (
        ((faced_power * resistance) - protection) * _resolve_heat(attacker, heat)
    ) * variance
    if damage <= 0 or not math.isfinite(damage):
        return 0.0
    return damage


def damage_bounds(
    attacker,
    target,
    power,
    damage_type,
    heat=None,
    steepness=1.0,
    protection=None,
):
    """Return ``(min, max)`` integer damage for a landed, non-glancing hit.

    **The prediction half of ``resolve_damage``, and nothing more.** It scores
    the facing curve, then calls that function twice with the ``uniform`` roll
    pinned to each end of its band -- so the pair it returns brackets every
    non-glancing outcome exactly rather than approximately, and a change to the
    damage expression reaches the preview by construction rather than by
    somebody remembering to edit a second copy. ``tests/test_preview_damage.py``
    pins the RNG, runs the real ``execute()``, and asserts the HP removed
    equals these numbers rather than merely falling between them.

    **Glancing blows are deliberately excluded from this band.** A glance
    halves the damage, but only lands in the narrow window where the roll
    falls within 10 of the hit chance -- folding it in would widen every
    headline range to 0.4x-1.2x and misrepresent the common case as if it were
    the whole story. The glancing case is a per-outcome detail for the combat
    log, not a property of the move the player is choosing.

    ``steepness`` is passed through to ``apply_facing_damage`` for the moves
    that sharpen the facing curve (Backstab). ``heat`` overrides the
    attacker's own multiplier; leave it None for the live value.
    ``protection`` overrides the defender's armour exactly as it does on
    ``resolve_damage`` -- pass what the ``execute()`` being predicted passes
    (Armor Pierce 0, Impale 40% of it), or leave None for the sanitised read.

    The armour read and the heat resolution are hoisted here and passed into
    both calls: this runs on every combat poll for every viable move, and
    resolving them twice per pair bought nothing. Both hoists are exact --
    ``resolve_damage`` performs the identical reads when handed None, and
    ``_resolve_heat`` is idempotent on its own output.

    Non-positive results collapse to ``(0, 0)``: the expression clamps its
    final product at zero, and a swing that protection fully absorbs is
    non-positive at *both* ends of the variance band (a negative core times
    0.8 and times 1.2 are both negative), so the pair lands on the same floor
    rather than reporting a negative spread.
    """
    power = apply_facing_damage(attacker, target, power, steepness)
    if protection is None:
        protection = target_protection(target)
    heat = _resolve_heat(attacker, heat)
    return (
        int(
            resolve_damage(
                attacker,
                target,
                power,
                damage_type,
                heat=heat,
                protection=protection,
                variance=DAMAGE_VARIANCE_MIN,
            )
        ),
        int(
            resolve_damage(
                attacker,
                target,
                power,
                damage_type,
                heat=heat,
                protection=protection,
                variance=DAMAGE_VARIANCE_MAX,
            )
        ),
    )


def flat_resisted_damage(target, faced_power, damage_type):
    """The *flat resisted* damage line: resistance, then protection, and
    nothing else -- no heat multiplier and no variance roll.

    Jab's expression, and the reason it lives here beside
    ``flat_arc_damage_bounds`` and ``resolve_damage`` rather than in the
    unarmed weapon module: it is a general shape, not an unarmed one. The name
    it had (``flat_unarmed_damage``) claimed the whole unarmed tree while Power
    Strike, in that same file, is deliberately on the canonical line -- so it
    described neither what it computes nor who uses it.

    ``faced_power`` is the move's power *after* ``apply_facing_damage``. The
    facing curve is deliberately left to the callers rather than folded in
    here: ``tests/test_facing_damage_hand_rolled_attacks.py`` is a static scan
    of each ``execute()``'s own source for that call, and a move that reached
    the curve only through a helper would read to it as a move that skips the
    curve entirely. That guard exists because opting out of positional damage
    is silent -- no error, no symptom -- so it is worth keeping literal.

    Dropping heat and variance is a design decision rather than an oversight;
    see ``Jab.execute``. The flat shape has precedent in
    ``flat_arc_damage_bounds`` (Reap, Sweep, Halberd Spin) but not this exact
    expression: those three skip resistance and floor at 1, where this honours
    resistance and floors at 0.

    Returns a float; callers apply their own ``int()`` where the engine does.
    """
    damage = (
        faced_power * functions.combat_resistance(target, damage_type)
    ) - target_protection(target)
    if not math.isfinite(damage):
        # +inf survived `damage > 0` and reached Jab's int(), raising
        # OverflowError inside the preview poll. resolve_damage clamps the
        # same way; this sibling did not.
        return 0.0
    return damage if damage > 0 else 0.0


def flat_arc_strike_damage(target, swing):
    """The flat arc damage line, stated once:
    ``max(1, int(swing - protection))`` -- no resistance, no heat, no
    variance, floored at 1.

    ``swing`` is the move's power AFTER ``apply_facing_damage``; the facing
    call is deliberately left at the call sites for the same reason
    ``flat_resisted_damage`` documents -- the facing-curve guard
    (``tests/test_facing_damage_hand_rolled_attacks.py``) reads each
    ``execute()``'s own source for that call, and a move that reached the
    curve only through a helper would scan as one that skips it.

    This line was hand-written four times -- ``flat_arc_damage_bounds`` plus
    the Sweep, Halberd Spin and Reap loops -- and all four had to agree for
    the preview and the executes to agree about the same defender.
    """
    if (
        not isinstance(swing, (int, float))
        or isinstance(swing, bool)
        or not safe_isfinite(swing)
    ):
        # A crafted save can put a non-finite power on a move; int(inf)
        # raises from inside the combat loop, so degrade to the line's own
        # floor instead. Availability-only -- unreachable for well-formed
        # saves (apply_facing_damage already returns its input for these).
        # Bools are rejected like target_protection rejects them
        # (isinstance(True, int) is True -- a flag is not one point of
        # swing), and safe_isfinite keeps an unfloatable int (10**400) from
        # crashing the check itself with OverflowError.
        return 1
    return max(1, int(swing - target_protection(target)))


def flat_arc_damage_bounds(attacker, target, power, bonuses=()):
    """Damage bounds for the *flat* arc expression used by Reap, Sweep and
    Halberd Spin -- ``flat_arc_strike_damage`` on the facing-scaled swing.

    No resistance, no heat, and no variance roll — which is why these moves
    return an identical min and max: their execute() has no dice in it at all,
    and reporting a +/-20% band for them would advertise a spread the engine
    cannot produce.

    ``bonuses`` are the per-target multipliers applied *in order*, each with
    its own ``int()`` truncation, exactly as the owning loop applies them (the
    only move with any today is Reap -- see its ``_damage_multipliers``, which
    its ``execute()`` loop reads too, so there is one derivation rather than
    two; every multiplier it yields is >= 1.0 -- bonuses, never penalties --
    so the chained truncations can only move the number up from the floor,
    never back under it). Truncating per multiplier rather than once at the
    end is load-bearing: two chained 1.25x on a base of 7 is 10 the way
    the engine does it and 10.9 -> 10 either way here, but the two diverge on
    other bases, and the engine's order is the authority.
    """
    swing = apply_facing_damage(attacker, target, power)
    damage = flat_arc_strike_damage(target, swing)
    for multiplier in bonuses:
        damage = int(damage * multiplier)
    return damage, damage


def preview_payload(low, high, target):
    """The ``preview_damage`` return shape, assembled in one place.

    ``lethal`` is ``max >= target.hp`` — "this could finish it", not "this
    will". Every ``preview_damage`` (the default and the per-move overrides)
    returns through here so the wire shape the client reads is stated once;
    a second copy of that dict in a weapon module is exactly the drift this
    codebase keeps paying for.
    """
    return {"min": low, "max": high, "lethal": bool(high >= getattr(target, "hp", 0))}


def hostiles_in_arc(move, arc_range, frontal=False, require_position=False):
    """The living hostiles an area swing would actually resolve against.

    Mirrors the enemy-selection gate every area ``execute()`` loop runs before
    it deals damage: hostiles only (via ``Move._hostiles_in_proximity`` — an
    ally standing in the arc must never be listed, the friendly-fire bug those
    loops were fixed for), alive, inside ``arc_range``, and — when ``frontal``
    — inside the 90-degree cone ahead of the user. Coordinates are preferred
    when both combatants have them; otherwise the loop falls back to
    ``combat_proximity`` distance, except for moves that require coordinates
    outright (``require_position``, i.e. Whirl Attack, whose loop skips any
    enemy with no ``combat_position``).

    Pure: it reads positions and proximity and returns a list, so a preview
    can call it every poll without touching combat state.
    """
    # A move with no resolvable reach (a malformed ``mvrange``, so
    # ``preview_reach`` reports None) swings at nobody rather than raising
    # inside the poll path -- the same graceful degradation the callers used
    # to get from their own arc lookup.
    if arc_range is None:
        return []
    affected = []
    user = move.user
    user_pos = getattr(user, "combat_position", None)
    proximity = getattr(user, "combat_proximity", None) or {}
    for enemy, _distance in list(move._hostiles_in_proximity()):
        if not enemy.is_alive():
            continue
        enemy_pos = getattr(enemy, "combat_position", None)
        if user_pos is not None and enemy_pos is not None:
            if positions.distance_from_coords(user_pos, enemy_pos) > arc_range:
                continue
            if frontal:
                try:
                    atk_angle = positions.angle_to_target(user_pos, enemy_pos)
                    angle_diff = positions.attack_angle_difference(
                        atk_angle, user_pos.facing
                    )
                    if angle_diff > 90:
                        continue
                except Exception:
                    # Same swallow the arc loops themselves use: an
                    # unresolvable angle keeps the enemy in the swing rather
                    # than silently dropping it.
                    pass
        else:
            if require_position:
                continue
            if proximity.get(enemy, 9999) > arc_range:
                continue
        affected.append(enemy)
    return affected


def resolve_pipeline_strike(move, damage, glance, hit_chance, roll=None):
    """One standard-pipeline strike: roll the dice (or take the caller's
    roll), then dispatch through ``move.parry()`` / ``move.hit(damage,
    glance)`` / ``move.miss()``.

    The ``if hit_chance >= roll: if check_parry: parry else hit / else miss``
    skeleton was hand-written at ~27 sites; this is that skeleton, once, for
    the sites whose hit branch is *bare* -- nothing but the ``hit()`` call.
    Sites with extras in the hit branch (arrow embedding, pushes, status
    infliction, lifesteal) deliberately stay inline rather than growing a
    callback parameter: a hook argument would just be the same divergence
    with worse stack traces.

    ``roll`` follows ``resolve_strike_outcome``'s rule exactly: pass the roll
    you already drew -- every migrated site draws it *before* resolving
    damage, and letting this function roll instead would swap the order the
    draws come off the shared RNG. Left None it rolls here.

    Sibling of ``resolve_strike_outcome``, not a replacement: that function
    is for the arc moves that bypass ``Move.hit()/miss()/parry()`` and
    publish/narrate per target themselves; this one is for moves that route
    through the shared pipeline, which does its own publishing.

    Returns True when the strike landed (``hit()`` ran), False for a parry
    or a miss.
    """
    if roll is None:
        roll = random.randint(0, 100)
    if hit_chance >= roll:
        if functions.check_parry(move.target):
            move.parry()
            return False
        move.hit(damage, glance)
        return True
    move.miss()
    return False


def resolve_strike_outcome(
    move,
    target,
    damage,
    hit_chance,
    *,
    hit_line,
    parry_line,
    miss_line,
    roll=None,
):
    """Resolve one strike against ``target``: roll, publish, narrate, apply.

    **The outcome/narration pairing rule, stated once.** ``publish_outcome``
    documents it in prose -- one publication per resolution, immediately before
    the line that narrates it, because the adapter pairs each published outcome
    with the *next* narration line and an unpaired line is therefore attributed
    to the previous enemy. That rule was then re-implemented by hand in Sweep,
    Halberd Spin, Reap and Chip Away, which differed from one another only in
    their flavour strings and Reap's mark clear. Four copies of a rule is four
    chances to get the ordering subtly wrong in a way nothing fails on.

    These four moves do not route through ``Move.hit()/miss()/parry()``: they
    write HP directly and narrate their own per-target lines, which is why they
    need this rather than the shared pipeline.

    ``roll`` lets a caller supply a to-hit roll it has already taken. Chip Away
    does, and the reason is ordering rather than taste: it rolls *before* it
    scores damage, and its damage carries a ``random.uniform`` band, so letting
    this function roll would swap the order the two draws come off the shared
    RNG -- a silent change to every seeded outcome. Left None, the roll happens
    here, which is what the three flat arc swings (no dice in their damage at
    all) already did inline.

    A zero-damage landing publishes ``absorb``, unconditionally: a blow the
    target shrugged off is not a ``hit`` and must not play the flesh-impact
    cue -- the same rule ``Move.hit`` applies. There used to be an
    ``absorb_on_zero`` opt-in here; it was deleted because the distinction it
    gated is a fact about the damage, not about the caller, and for the flat
    arc swings (floored at 1, so ``damage <= 0`` is unreachable) the
    unconditional rule is provably identical.

    The three narration lines are keyword-only: three same-typed strings in
    a row are exactly the signature a positional call scrambles silently --
    the hit text narrated for a parry -- and every call site already passed
    them by keyword.

    Returns True when the strike landed, False for a parry or a miss.
    """
    if roll is None:
        roll = random.randint(0, 100)
    if hit_chance >= roll:
        if functions.check_parry(target):
            publish_outcome(move.user, OUTCOME_PARRY, target)
            cprint(parry_line, "yellow")
            return False
        # Coerce like Move.hit (issue #296): a NaN damage would otherwise
        # make ``hp - damage`` NaN, and ``max(0, nan)`` evaluates to 0 in
        # CPython -- a crafted non-finite damage silently EXECUTED the
        # target rather than crashing. OverflowError: float(10**400) raises,
        # so an unfloatable int damage crashed the coercion itself.
        try:
            damage = float(damage)
        except (TypeError, ValueError, OverflowError):
            damage = 0
        if not math.isfinite(damage):
            damage = 0
        damage = int(damage)
        # Apply exactly as Move.hit does. The previous write was
        # ``max(0, target.hp - damage)`` with hp read RAW -- ``max(0, nan)``
        # is 0 (a silent kill via the OTHER operand) and an inf hp was
        # unkillable forever. clamp_hp owns the bounds and the non-finite-hp
        # coercion for every real combatant.
        target.hp -= damage
        if hasattr(target, "clamp_hp"):
            target.clamp_hp()
        publish_outcome(
            move.user,
            OUTCOME_ABSORB if damage <= 0 else OUTCOME_HIT,
            target,
        )
        cprint(hit_line, "red")
        return True
    publish_outcome(move.user, OUTCOME_MISS, target)
    cprint(miss_line, "yellow")
    return False


def _apply_facing_accuracy(attacker, defender, hit_chance):
    """Facing/angle system: attacks landing on a defender's flank or rear are
    harder to defend against than a head-on attack (issue #394).

    The accuracy half of the pair whose damage half is ``apply_facing_damage``;
    both read the same angle via ``facing_angle_diff`` so they can never
    disagree about which way the defender is looking. Applied universally so it
    isn't limited to whichever moves happen to consult it directly — the same
    partial-enforcement trap #421 fixed for HauntingPresence. No-op (returns
    hit_chance unchanged) unless both combatants have a resolved
    combat_position — i.e. the 2D coordinate combat system is active.

    Requires hit_chance > 0: a non-positive value is either an auto-miss
    sentinel (-1, out of range) or already zeroed, and must be left alone —
    Python's int() truncates toward zero, so int(-1 * 0.95) is 0, not -1,
    which would turn a guaranteed miss into a chance to hit.

    The result is deliberately NOT bounded here — see the comment on the return
    below. ``_apply_to_hit_modifiers`` owns the single authoritative clamp, run
    once after every modifier. The ceiling matters for this multiplier in
    particular: the rear bonus is 1.30, which used to be clamped at 100 against
    a ``random.randint(0, 100)`` roll — i.e. any halfway competent rear attack
    was an automatic hit, and positioning stopped being a gamble.
    """
    if hit_chance <= 0:
        return hit_chance
    try:
        angle_diff = facing_angle_diff(attacker, defender)
        if angle_diff is None:
            return hit_chance
        modifier = positions.get_accuracy_modifier(angle_diff)
        # Deliberately NOT clamped here. _apply_to_hit_modifiers owns the one
        # authoritative bound, applied after every modifier has run; clamping
        # mid-chain meant HauntingPresence's x0.85 compounded off a truncated
        # 95 instead of the true product (a rear attack against a haunting
        # defender came out at 80 rather than 95), which contradicts the
        # "final clamp runs after every modifier" contract that funnel
        # documents. The sentinel guard above still runs first, so a
        # non-positive chance never reaches this line.
        return int(hit_chance * modifier)
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

    This is also the engine's **authoritative** bound on a hit chance: the
    final ``clamp_hit_chance`` runs after every modifier, so no situational
    adjustment applied upstream (ranged decay, Hawkeye's x1.4, Aimed Shot's
    flat +15, a hand-rolled inline expression, or a literal ``hit_chance =
    100``) can route around the ceiling by landing after it. Bounding inside
    ``to_hit_chance`` instead would not hold: several callers deliberately add
    to its result before getting here.
    """
    if hit_chance <= 0:
        # Auto-miss sentinel (-1, target out of range) or an already-zeroed
        # chance. No modifier and no clamp may touch it — see clamp_hit_chance.
        return hit_chance
    hit_chance = _apply_facing_accuracy(attacker, defender, hit_chance)
    hit_chance = _apply_haunting_presence(attacker, defender, hit_chance)
    return clamp_hit_chance(hit_chance)


#: Default base term of the engine's to-hit expression, plus the weights it
#: applies to the attacker's attributes. These live here, next to the attack
#: paths that consume them, so a balance change is a one-file edit — an earlier
#: copy in the API layer drifted to ``98 + finesse`` and the character sheet
#: disagreed with the dice until someone noticed.
#: Flat fatigue term every standard attack starts from, before weapon weight,
#: endurance and each move's own ``mod_fatigue`` adjust it. Named so a move
#: expressing its cost as an offset from the baseline (rather than
#: reimplementing the whole formula, as Slash once did) does the arithmetic
#: against the real value instead of a copied literal.
STANDARD_FATIGUE_BASE = 85

HIT_CHANCE_BASE = 85
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
        if any(
            getattr(m, "name", "") == "Shadow Step"
            for m in getattr(c, "known_moves", [])
        ):
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
    # Damage type the move's weapon deals, derived in evaluate(). Declared here
    # so every read is safe before the first evaluate() -- preview_damage runs
    # for every known move on every combat poll, and a move restored from a
    # pickled save has whatever __dict__ it was saved with. combat_resistance
    # already treats None as the 1.0 default, so the class-level value is the
    # correct pre-evaluate answer rather than a placeholder. A class attribute
    # rather than getattr() at each site: the sites are not enumerable, and the
    # ones that get missed are exactly the bugs this guards against.
    base_damage_type = None

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

    def _unconditional_preview_hit_chance(
        self, target, base=HIT_CHANCE_BASE, floor=None
    ):
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

    def _within_reach(self, target):
        """True when ``target``'s current distance falls inside this move's
        range band. Unknown distance (no proximity entry) counts as in reach:
        that is a combat that has not wired proximity up yet, not a target
        established to be too far.
        """
        proximity = getattr(self.user, "combat_proximity", None)
        if not isinstance(proximity, dict) or target not in proximity:
            return True
        distance = proximity[target]
        reach = self.preview_reach()
        if reach is not None and distance > reach:
            return False
        mvrange = getattr(self, "mvrange", None)
        if mvrange and len(mvrange) == 2 and distance < mvrange[0]:
            return False
        return True

    def preview_reach(self):
        """Maximum distance, in feet, at which this move can resolve right now
        — or ``None`` when it declares no reach at all.

        Not simply ``mvrange[1]``. A ranged move whose reach is derived from
        the weapon overrides ``get_effective_range_max`` (the static tuple
        would understate it), and an area swing whose ``mvrange`` is a
        placeholder its ``evaluate()`` never narrows overrides this method
        outright (Reap advertises ``(1, 20)`` while a scythe sweeps 5 ft). The
        API renders a range ring from this, so a wrong number here draws a
        ring the move cannot actually reach.
        """
        effective = self.get_effective_range_max(self.user)
        if effective is not None:
            return effective
        mvrange = getattr(self, "mvrange", None)
        if not mvrange or len(mvrange) != 2:
            return None
        return mvrange[1]

    def preview_affected(self):
        """The combatants this move would actually resolve against right now.

        ``[self.target]`` for a targeted move with a resolved target, ``[]``
        for anything untargeted — which is the default here. **An area swing
        must override this**: its damage lands on a *set* selected by its own
        arc/range gate rather than on a single assigned target, and every one
        of them is untargeted with ``self.target`` set to the *user*, so the
        default would report nobody and the client could preview nothing at
        all. Those overrides call ``hostiles_in_arc`` with the gate their own
        ``execute()`` loop runs (see WhirlAttack, Reap, Sweep, HalberdSpin).

        **Pairing rule:** an override that can report a non-empty set must be
        paired with a ``preview_damage(self, target=None, affected=None)``
        that forwards ``affected`` into ``_area_preview_damage`` — the
        adapter prices every affected enemy in one poll by passing the
        already-computed set back through that kwarg. Contract-tested by
        ``tests/test_preview_damage.py`` (TestAreaPreviewPairingContract).

        Pure — no combat state is written, so it is safe to call on every poll.
        """
        if not getattr(self, "targeted", False) or self.passive:
            return []
        target = getattr(self, "target", None)
        if target is None or target is self.user:
            return []
        return [target]

    def _area_preview_damage(self, target, flat=False, bonuses=(), affected=None):
        """Shared body for the area swings' ``preview_damage``.

        Their gating differs from ``_standard_preview_damage`` in one way that
        matters: an area move has no ``self.target`` to fall back on (it
        targets the user), and its reach test is its own arc gate —
        ``preview_affected()`` — rather than ``viable()``, which for these
        moves only asks whether *some* hostile is in the swing and so stays
        True for an enemy the arc cannot reach.

        ``flat`` selects ``flat_arc_damage_bounds`` — the no-resistance,
        no-heat, no-variance expression Reap, Sweep and Halberd Spin's loops
        actually run — over the canonical ``damage_bounds``. ``bonuses`` are
        the per-target multipliers the owning loop applies, in its order.

        ``affected`` lets a caller that already holds this move's
        ``preview_affected()`` result (the adapter prices every affected
        enemy in one poll, so it would otherwise recompute the arc once per
        enemy) supply it; the list is then authoritative for the reach gate.
        Left None the gate recomputes, which is the correct default for a
        single ad-hoc preview.
        """
        if self.passive or target is None or target is self.user:
            return None
        is_alive = getattr(target, "is_alive", None)
        if callable(is_alive) and not is_alive():
            return None
        # ``affected`` is only ever server-computed -- the adapter passes this
        # move's own ``preview_affected()`` result back in -- and when
        # supplied it is authoritative for the reach gate: no recompute.
        affected_targets = (
            affected if affected is not None else self.preview_affected()
        )
        if target not in affected_targets:
            return None

        power = getattr(self, "power", None)
        if (
            not isinstance(power, (int, float))
            or isinstance(power, bool)
            or not safe_isfinite(power)
        ):
            return None

        if flat:
            low, high = flat_arc_damage_bounds(self.user, target, power, bonuses)
        else:
            low, high = damage_bounds(
                self.user, target, power, getattr(self, "base_damage_type", None)
            )
        return preview_payload(low, high, target)

    def _standard_preview_damage(
        self, target=None, power=None, steepness=1.0, protection=None
    ):
        """Shared body for the moves whose ``preview_damage`` is the canonical
        damage expression — the default path below, plus the moves that
        diverge from it only in an argument to it: the ``power`` their
        ``execute()`` actually scores with (Shoot Bow, the masteries), the
        steepness of the facing curve (Backstab), or the ``protection``
        override their damage line passes (Impale, Armor Pierce). Handles the
        target-resolution, viability and reach gating once so those overrides
        stay a one-line call, exactly as ``_standard_preview_hit_chance``
        does for the to-hit side.

        ``power`` of ``None`` means "use ``self.power``" — the attribute the
        canonical path reads. ``protection`` of ``None`` means the sanitised
        ``target_protection`` read, exactly as on ``resolve_damage``.
        """
        if self.passive:
            return None
        resolved = target if target is not None else getattr(self, "target", None)
        if resolved is None or resolved is self.user:
            return None
        is_alive = getattr(resolved, "is_alive", None)
        if callable(is_alive) and not is_alive():
            return None
        if not self._viable_for(resolved):
            return None
        # ...and viable() is not a per-target check either. Most attacks
        # run standard_viability_attack, which asks only whether *some*
        # enemy sits inside mvrange -- so it stays True for a second enemy
        # standing well outside the move's reach, and the preview would
        # price a swing that could not land. execute() resolves that case
        # as an auto-miss (hit_chance = -1); a preview must resolve it as
        # "no number", not as a full-damage promise.
        if not self._within_reach(resolved):
            return None

        if power is None:
            power = getattr(self, "power", None)
        if (
            not isinstance(power, (int, float))
            or isinstance(power, bool)
            or not safe_isfinite(power)
        ):
            return None

        low, high = damage_bounds(
            self.user,
            resolved,
            power,
            getattr(self, "base_damage_type", None),
            steepness=steepness,
            protection=protection,
        )
        return preview_payload(low, high, resolved)

    def preview_damage(self, target=None):
        """Damage this move would deal to ``target`` on a landed, non-glancing
        hit: ``{"min": int, "max": int, "lethal": bool}`` — or ``None`` when a
        damage number isn't meaningful.

        ``None`` covers: an untargeted move that deals no damage (buffs, Rest,
        the pure positioning moves), a move with no scored ``power``, no
        resolvable target, a dead target, a target this move cannot currently
        reach, and any move that isn't viable right now. ``lethal`` is
        ``max >= target.hp`` — i.e. "this could finish it", not "this will".

        The arithmetic lives in ``damage_bounds``; this method only decides
        *whether* a preview applies and *with what power*. Everything it reads
        (facing, heat, resistance, protection, hp) is read live, so the numbers
        reflect the battlefield at the moment of the call rather than a value
        frozen at move selection.

        **Glancing blows are deliberately excluded from the range** — see
        ``damage_bounds``.

        Like ``preview_hit_chance``, this base implementation is the *default*
        path only: the canonical expression with ``self.power`` and
        ``self.base_damage_type``. **A move whose ``execute()`` computes power
        or damage differently MUST override this method** to report what its
        own ``execute()`` really does — a preview that quietly diverges is
        worse than none, because the player commits to the move on it. The
        override belongs on the move, beside the ``execute()`` it mirrors, and
        should be a short call into ``_standard_preview_damage`` /
        ``_area_preview_damage`` here rather than a second copy of the damage
        line. Grep the damage line of the ``execute()`` you are changing rather
        than trusting any enumeration of which moves diverge — a list like that
        lived in this file once and is exactly what this note replaces.
        """
        return self._standard_preview_damage(target)

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
                if getattr(state, "name", "") == "Staggered" and not getattr(
                    state, "penalty_consumed", False
                ):
                    prep += getattr(state, "prep_penalty", 5)
                    state.penalty_consumed = True
                    break

        # QuickReload passive: faster crossbow reload — shave ~20% of prep beats
        # (floored at 1) while wielding a crossbow.
        if (
            prep > 1
            and getattr(getattr(self.user, "eq_weapon", None), "subtype", None)
            == "Crossbow"
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
        publish_outcome(self.user, OUTCOME_PARRY, self.target)
        narrate(
            colored(self.target.name, self.targetcolor)
            + colored(" parried the attack from ", "red")
            + colored(self.user.name, self.usercolor)
            + colored("!", "red")
        )
        self.stage_beat[2] += 10  # add stagger time to the user
        if self.target.name == "Jean":
            self.target.change_heat(1.4)
            # Credit parry experience based on target's weapon if available, otherwise "Basic"
            if hasattr(self.target, "eq_weapon") and self.target.eq_weapon:
                _ensure_weapon_exp(self.target)
                self.target.combat_exp[self.target.eq_weapon.subtype] += 15
            else:
                self.target.combat_exp["Basic"] += 15
        if self.user.name == "Jean":
            self.user.change_heat(0.75)

    def hit(self, damage, glance):
        # Defense-in-depth (issue #296): damage reaches HP here from many move
        # execute() paths. Coerce it to a finite, integral value so a NaN/inf
        # (e.g. from an exotic resistance/heat product) can never poison hp, and
        # clamp hp to [0, maxhp] afterward via the shared Combatant guard.
        # OverflowError: float(10**400) raises, so an unfloatable int damage
        # crashed the coercion meant to contain it.
        try:
            damage = float(damage)
        except (TypeError, ValueError, OverflowError):
            damage = 0
        if not math.isfinite(damage):
            damage = 0
        damage = int(damage)
        # Publish before narrating: the adapter listens on the narration sink,
        # so the outcome must already be on the pending animation when the
        # impact line goes out. A glance and a fully-absorbed blow are distinct
        # outcomes precisely because they sound and look different -- deriving
        # either from the prose below is what this replaces.
        if damage > 0:
            publish_outcome(
                self.user,
                OUTCOME_GLANCE if glance else OUTCOME_HIT,
                self.target,
            )
        else:
            # Zero damage ("did no damage") and negative damage ("absorbed N")
            # are both blows the target shrugged off: no flesh-impact cue.
            publish_outcome(self.user, OUTCOME_ABSORB, self.target)
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
                self.user.change_heat(1.25)
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
                self.user.change_heat(0.75)
            if self.target.name == "Jean":
                self.target.change_heat(1.25)
                self.target.combat_exp["Basic"] += 15

    def miss(self):
        publish_outcome(self.user, OUTCOME_MISS, self.target)
        narrate(colored(self.user.name, self.usercolor) + "'s attack just missed!")
        if self.target.name == "Jean":
            for state in self.target.states:
                if state.name == "Dodging":
                    self.target.change_heat(1.25)
                    self.target.combat_exp["Basic"] += 10
                    break
            self.target.change_heat(1.1)
            self.target.combat_exp["Basic"] += 5
        if self.user.name == "Jean":
            self.user.change_heat(0.85)

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
        # Power calculation. The try/except and the isfinite check are
        # crafted-save armour (issue #296 family): a weapon whose
        # damage/str_mod/fin_mod came off a hostile save can be a string
        # (TypeError in the sum), an unfloatable int (OverflowError when a
        # float term joins the sum), or inf/nan (caught by the finiteness
        # check before the int() below), any of which wedged the beat. A
        # missing weapon (AttributeError: eq_weapon is None on a degraded
        # save) takes the same fallback. Well-formed weapons take the
        # identical arithmetic path.
        weapon = getattr(self.user, "eq_weapon", None)
        try:
            power = (
                weapon.damage
                + base_power
                + self.user.strength * weapon.str_mod
                + self.user.finesse * weapon.fin_mod
            )
        except (TypeError, AttributeError, OverflowError):
            power = 0
        if isinstance(mod_power, str) and "%" in mod_power:
            mod_power_val = int(mod_power.replace("%", ""))
            power = (power * mod_power_val) / 100
        else:
            power += int(mod_power)
        if not isinstance(power, (int, float)) or not safe_isfinite(power):
            power = 0
        power = max(0, int(power))

        # Prep calculation. The divisor is floored at 1: a zero or degraded
        # speed raised ZeroDivisionError (or fed int() a NaN) mid-beat.
        speed = getattr(self.user, "speed", 1)
        if (
            not isinstance(speed, (int, float))
            or not safe_isfinite(speed)
            or speed < 1
        ):
            speed = 1
        # The divisor floor above closed only half the crafted-save surface:
        # weapon weight and endurance are raw save-controlled NUMERATORS
        # feeding the int()s below, so an inf/NaN/str/unfloatable-int weight
        # still wedged the beat (and eq_weapon=None crashed the read itself).
        # Sanitise once through the shared _num family; well-formed values
        # come through arithmetically unchanged.
        weight = _num(getattr(weapon, "weight", 0))
        endurance = _num(getattr(self.user, "endurance", 0))
        prep = int((40 + (weight * 3)) / speed)
        prep += int(mod_prep)
        prep = max(1, prep)

        execute = 1

        # Cooldown calculation
        # int() on the weight term is load-bearing, not cosmetic. Weapon weight
        # is a float and several real weapons are fractional (Baselard 1.2,
        # Shortbow 1.5), which produced a fractional cooldown -- and advance()
        # drains beats_left by exactly 1 per beat and advances the stage only on
        # `while self.beats_left == 0`. A cooldown of 4.2 drains 3.2, 2.2, 1.2,
        # 0.2, -0.8 and never equals 0, so the move is stranded in cooldown for
        # the rest of the fight. Measured: a Baselard Slash fired once in 80
        # beats and never came back. prep and recoil already int() their weight
        # terms; this one did not.
        cooldown = int((3 + weight)) - int(endurance / 10)
        cooldown += int(mod_cd)
        cooldown = max(0, cooldown)

        # Recoil calculation
        recoil = int(1 + (weight / 2))
        recoil += int(mod_recoil)
        recoil = max(1, recoil)

        # Fatigue cost calculation — endurance gives modest relief (coeff 2);
        # strength reduces how much weapon weight burdens the fighter;
        # carry weight adds proportional burden on top.
        wt_mult = max(4, 10 - 0.2 * _num(getattr(self.user, "strength", 0)))
        fatigue_cost = (
            STANDARD_FATIGUE_BASE
            + int(weight * wt_mult)
            - (2 * endurance)
        )
        fatigue_cost += int(mod_fatigue)
        fatigue_cost = max(floor_fatigue, int(fatigue_cost))
        fatigue_cost = _apply_carry_fatigue(self.user, fatigue_cost)

        # BladeMastery passive: sword attacks cost less fatigue
        fatigue_cost = _apply_blade_mastery_discount(
            self.user, fatigue_cost, floor_fatigue
        )

        # Range calculation. A missing weapon or malformed wpnrange keeps the
        # band the move already carries rather than raising mid-beat.
        try:
            mvrange = (
                weapon.wpnrange[0] + int(mod_range_min),
                weapon.wpnrange[1] + int(mod_range_max),
            )
        except (TypeError, AttributeError, IndexError):
            mvrange = self.mvrange

        weapon_name = getattr(weapon, "name", "weapon")
        self.stage_announce[1] = colored(
            f"{self.user.name} strikes with his {weapon_name}!", "green"
        )
        self.stage_beat = [prep, execute, recoil, cooldown]
        self.fatigue_cost = fatigue_cost
        self.mvrange = mvrange

        if base_damage_type == "weapon":
            base_damage_type = items.get_base_damage_type(weapon)
        return power, base_damage_type

    def standard_execute_attack(self, player, power, base_damage_type):
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

        # Facing/angle damage (issue #394). Before this, positioning moved
        # damage for exactly one move in the entire engine (Backstab) and every
        # other attack felt the battlefield only through accuracy — so flanking
        # was a rounding error unless you happened to hold a dagger. Reading
        # the angle *after* the turn_toward above is deliberate and harmless:
        # turn_toward rotates the attacker, and the curve is scored against the
        # defender's facing.
        power = apply_facing_damage(self.user, self.target, power)

        if self.viable():
            hit_chance = to_hit_chance(self.user, self.target, floor=5)
        else:
            hit_chance = (
                -1
            )  # if attacking is no longer viable (enemy is out of range), then auto miss

        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(self.user, self.target, hit_chance)

        roll = random.randint(0, 100)
        # The canonical damage expression, stated once in resolve_damage and
        # predicted by damage_bounds through that same function -- see its
        # docstring for why this must not be re-inlined here or anywhere else.
        damage = resolve_damage(player, self.target, power, base_damage_type)
        damage, glance = apply_glancing_blow(damage, hit_chance, roll)
        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5
        resolve_pipeline_strike(self, damage, glance, hit_chance, roll)
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
