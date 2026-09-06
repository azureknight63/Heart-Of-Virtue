import logging
from typing import Any, Dict, List, Literal, NamedTuple, Optional, Tuple, TypedDict

from ai.llm_client import GenericLLMClient
from src.text_format import pct as _pct

logger = logging.getLogger(__name__)

# Which side of the fight a status effect is being read from, and the
# _STATUS_TACTICAL_NOTES column each side reads.
#
# The parameter was a bare `str` resolved by `"enemy_note" if perspective ==
# "enemy" else "player_note"`, so any misspelling fell through to the player
# column and quietly narrated an ENEMY's effects as advice about Jean's own —
# the exact confusion the perspective split exists to prevent. The Literal
# catches it statically; the dict below catches it at runtime, loudly.
Perspective = Literal["player", "enemy"]
_PERSPECTIVE_NOTE_KEYS: Dict[Perspective, str] = {
    "player": "player_note",
    "enemy": "enemy_note",
}


# ---------------------------------------------------------------------------
# Tactical thresholds
# ---------------------------------------------------------------------------
# Every threshold this module BRANCHES ON lives here exactly once. Each used to
# be re-typed independently into three places that must agree — the static
# system prompt's prose, the heuristic fallback's scoring, and the runtime
# prompt builder's labels and alerts — with nothing linking them: the heat
# bands appeared at five sites, the 25%/50% HP and fatigue bands at nine, and
# "defensively vulnerable" existed as three separate copies of one rule.
# _SYSTEM_PROMPT below interpolates these constants, so a threshold the model
# is told and the same threshold the code applies cannot drift apart.
#
# Not every number in that prompt is one of these, and the difference matters
# when editing it. The heat range (0.5×–10×) and the two reach distances
# (> 5ft, ≤ 1ft) are the ENGINE's facts, quoted as background for the model;
# nothing here branches on them, so nothing here owns them and a hand-check
# against the engine is the only thing keeping them true. Do not add a number
# to that prompt without either giving it a constant above or knowing which
# of these two kinds it is.
_HP_CRITICAL_PCT = 0.25
_HP_LOW_PCT = 0.50
_FATIGUE_CRITICAL_PCT = 0.25
_FATIGUE_LOW_PCT = 0.50

# The most moves the heuristic fallback will offer, however many the caller
# asks for. The LLM path deliberately does NOT share this cap — it returns
# whatever `max_suggestions` the caller requested — because the model ranks a
# whole battlefield while this ladder returns the first branch that matches,
# and its fourth-best guess is not worth showing. Pinned by
# tests/test_combat_strategist_coverage.py::test_results_capped_between_1_and_3.
_MAX_FALLBACK_SUGGESTIONS = 3

# An enemy below this HP fraction is worth finishing off before a healthier one.
_FINISHABLE_HP_PCT = 0.30

# How soon a telegraphed blow must land for the enemy throwing it to outrank a
# wounded one in `_rank_enemies`.
#
# Its OWN number, deliberately not a second reader of `_LAST_DEFENSIBLE_BEAT`.
# Ranking answers "who should Jean hit first", a question with no Dodge in it,
# so borrowing the defensive bound tied it to a constant that moves for
# unrelated reasons: when the defensive window became a range, this silently
# widened from 4 beats to 10 and almost every charging enemy started outranking
# the sub-`_FINISHABLE_HP_PCT` finish-them-off rule this ranking exists to
# apply. Retuning `Dodging`'s stance duration would have re-ranked every
# multi-enemy fight with nothing saying so.
#
# 4 beats is the value the predicate held before that coupling, and the reason
# it is small is the reason ranking is a separate question: a blow landing this
# soon costs Jean the beat he would otherwise spend finishing a wounded enemy,
# while one further out can wait until after the kill.
_IMMINENT_CHARGE_BEATS = 4

_HEAT_BLAZING = 2.0
_HEAT_HOT = 1.2
_HEAT_COLD = 0.8
# ENGINE-OWNED: this is `Move._HEAT_MISS_PENALTY` (src/moves/_base.py), which
# `Move.miss()` passes to `change_heat` when one of Jean's attacks misses.
# Restated rather than imported because this module must stay importable
# without the game engine (see src/text_format.py's docstring), so the pair is
# guarded instead: tests/test_combat_strategist_coverage.py reads the engine's
# value straight out of src/moves/_base.py and fails if the two drift.
_HEAT_MISS_PENALTY = 0.85

# ENGINE-OWNED, and both must stay on the ENGINE'S SCALE — the same
# `Move.beats_until_resolve()` scale `_incoming_beats` reads a threat off.
#
# _DEFENSIVE_WINDOW_BEATS is the beat the window OPENS on, not its length:
# Dodge and Parry cost exactly this many beats to land, so a hit arriving any
# sooner than this cannot be defended against at all.
#
# The number is `Move.beats_until_resolve()` for a freshly built Dodge, NOT the
# raw stage cost: `stage_beat=[1, 1, 5, 2]` reads as "1 prep + 1 execute", but
# the engine's countdown adds a beat at each stage boundary (draining a stage
# to zero does not advance it — the NEXT beat does), so a Dodge cast now
# resolves on beat 4, which is what tests/test_move_beats_until_resolve.py
# drives against the real `advance` loop.
#
# _DEFENSIVE_STANCE_BEATS is how long the resulting stance then HOLDS
# (`Dodging._DURATION_BEATS`), which is what makes the window a range rather
# than a single beat: a Dodge cast now is up from beat 4 through beat 10.
#
# tests/test_combat_strategist_coverage.py pins both against the real engine —
# the cost against a real Dodge/Parry, the duration against `Dodging` — so
# retuning either fails there rather than silently mis-timing every defensive
# alert in the game. It has gone wrong silently before: the cost was once 2,
# Dodge's value on the DELETED `_beats_until_impact` scale, carried over
# unchanged when `_incoming_beats` switched to the engine's field.
_DEFENSIVE_WINDOW_BEATS = 4
_DEFENSIVE_STANCE_BEATS = 7

# The last beat a defence cast NOW is still standing for. Measured, not
# reasoned: driving the real engine at the combat loop's own per-beat order
# (every player move advances, THEN the NPCs' do, then states cycle) puts the
# `Dodging` state on Jean for the enemy's half of beats 4 through 10 inclusive.
# See tests/test_combat_strategist_coverage.py::TestDefensiveWindowMatchesTheEngine.
_LAST_DEFENSIBLE_BEAT = _DEFENSIVE_WINDOW_BEATS + _DEFENSIVE_STANCE_BEATS - 1

# Below both of these Jean's defenses will not meaningfully absorb a hit.
#
# `defense` here is the serializer's name for the engine's `protection`, which
# already includes worn armour (Player.refresh_protection_rating). A starting
# Jean measures evasion 11 / defense 4, so he opens the game vulnerable on both
# counts; _LOW_DEFENSE is a high-end gate that only clears once he is in real
# armour (body pieces run 1–14 protection).
_LOW_EVASION = 15
_LOW_DEFENSE = 10

# A telegraphed hit is flagged potentially lethal at this fraction of current HP.
_LETHAL_HP_FRACTION = 0.5

# Status effects that tick damage on the holder. Time works against whoever
# carries one, which is the whole reason both sides read the same set: on Jean
# it means end the fight, on an enemy it means Jean can afford to wait. Spelled
# once because the two copies had ALREADY diverged — the enemy-side literal was
# missing Hollowed, so an enemy bleeding out from it read as no clock at all,
# while _STATUS_TACTICAL_NOTES' own Hollowed enemy_note says the opposite
# ("Weakening over time — Jean can afford a measured approach").
#
# ENGINE-DERIVED, spelled out here only because this module must stay
# importable without the game engine (see src/text_format.py's docstring).
# The membership rule is mechanical: a State whose `effect()` runs
# ``target.hp -= …``. tests/test_combat_strategist_coverage.py derives the set
# straight from src/states.py by that rule and fails on any difference, so a
# new damage-over-time state cannot be forgotten here the way Slimed was —
# its own note at _STATUS_TACTICAL_NOTES says "Acid is eating HP on a timer"
# while `dot_active` read False for it. Fervent qualifies too: it is a buff,
# but it bills the holder HP every 5 beats, and both of its notes below
# already give the advice a clock implies.
_DOT_STATUSES = frozenset(
    {"Poisoned", "Enflamed", "Slimed", "Resonant", "Hollowed", "Fervent"}
)

# Status effects that make Dodge unreliable, so a defensive beat buys less than
# the scorer would otherwise assume. Same arrangement as _DOT_STATUSES: the
# rule is "a State whose ``__init__`` assigns a NEGATED ``add_fin``", evasion
# being ``int(round(finesse))``, and the same test derives it from
# src/states.py. Resonant was missing despite cutting finesse by 25% — a
# deeper cut than either Slimed's or Petrified's, both of which were listed.
_DODGE_IMPAIRING_STATUSES = frozenset(
    {"Disoriented", "Slimed", "Petrified", "Resonant"}
)

# Opening bid per move category, before every situational adjustment in
# `_score_move`. Hoisted rather than rebuilt per move per request.
#
# The keys are the ENGINE's category vocabulary, which is what
# ApiCombatAdapter forwards verbatim (`"category": getattr(move, "category", …)`)
# — NOT the frontend's button names. The two are not the same list: the
# `Special` BUTTON collects the engine's `Mastery` moves (see
# CATEGORY_GROUPS in frontend/src/utils/categories.js), and this table used to
# be keyed on the button, so it held a "Special" no move ever carries while
# the seven 2500-XP `Mastery` moves fell through to the default and scored
# below Defensive. `Tactical` and `Utility` were missing for the same reason.
# tests/test_combat_strategist_coverage.py checks this table against the same
# AST-derived vocabulary tests/test_move_categories_ui_contract.py holds the
# frontend to, in both directions.
_CATEGORY_BASE_SCORES: Dict[str, int] = {
    "Offensive": 85,
    # Capstone moves: strong, but expensive enough that a plain attack still
    # edges them at neutral heat.
    "Mastery": 80,
    "Maneuver": 75,
    # Marks and set-up (MarkedQuarry, ReapersMark): they buy a later hit.
    "Tactical": 70,
    "Defensive": 65,
    # Check/Wait/CrusaderOath — Check and Wait carry explicit overrides in
    # `_score_move`, so this only ever prices the buffs.
    "Utility": 40,
    "Miscellaneous": 40,
}
# The bid for a category this table has never heard of. Deliberately the
# Miscellaneous price rather than a second copy of the number: an unrecognised
# category IS miscellaneous as far as the scorer is concerned.
_DEFAULT_CATEGORY_SCORE = _CATEGORY_BASE_SCORES["Miscellaneous"]

# Jean's damage/XP multiplier, banded. One classification, read by all four
# places that used to re-derive it independently: the fallback's offensive
# adjustment, the prompt's heat label, the fallback's offensive reasoning, and
# the alert block. The round before this one unified the numbers but left four
# copies of the if/elif ladder over them.
HeatBand = Literal["BLAZING", "HOT", "WARM", "COLD"]

_HEAT_OFFENSIVE_BONUS: Dict[HeatBand, int] = {
    "BLAZING": 10,  # attack now
    "HOT": 5,  # lean offensive
    "WARM": 0,
    "COLD": -10,  # rebuild before spending resources
}

# `{swing}` is the band's distance from baseline in whole percent, always
# positive — the sign is already in the prose.
_HEAT_LABEL_BODY: Dict[HeatBand, str] = {
    "BLAZING": "BLAZING — attacks deal +{swing}% damage; protect this streak",
    "HOT": "HOT — attacks deal +{swing}% bonus damage",
    "WARM": "WARM — baseline damage",
    "COLD": "COLD — attacks deal −{swing}% damage; land hits to rebuild",
}

# What the scorer says when it has nothing situational to say. Spelled once
# because both readers must agree: it is the WARM heat note AND the reasoning
# every unhandled category falls through to, and the two were separate string
# literals 700 lines apart.
_NO_TACTICAL_READ = "Tactical analysis unavailable; {name} is a viable fallback."

_HEAT_OFFENSIVE_NOTE: Dict[HeatBand, str] = {
    "BLAZING": (
        "Heat is BLAZING ({heat:.1f}×); {name} for amplified damage — don't miss."
    ),
    "HOT": "Heat is elevated ({heat:.1f}×); {name} while the combo holds.",
    "WARM": _NO_TACTICAL_READ,
    "COLD": "Heat is low ({heat:.1f}×); {name} to rebuild combo before committing.",
}

# Only the two extremes are worth a line in SITUATIONAL ALERTS; HOT and WARM
# are already covered by the heat label on the player line.
_HEAT_ALERTS: Dict[HeatBand, str] = {
    "BLAZING": (
        "⚠ BLAZING HEAT ({heat:.2f}×): Maximize offense now — missing or "
        "being hit collapses the combo."
    ),
    "COLD": (
        "⚠ COLD HEAT ({heat:.2f}×): Land hits to rebuild combo before using "
        "expensive moves."
    ),
}


def _heat_band(heat: float) -> HeatBand:
    """Classify a heat multiplier into the band every heat lookup is keyed on."""
    if heat >= _HEAT_BLAZING:
        return "BLAZING"
    if heat >= _HEAT_HOT:
        return "HOT"
    if heat < _HEAT_COLD:
        return "COLD"
    return "WARM"


# How depleted a HP or fatigue pool is. The same arrangement `_heat_band`
# above uses, and for the same reason: the critical/low/ok ladder over
# _HP_*_PCT and _FATIGUE_*_PCT was written out three times — Jean's HP flag,
# Jean's fatigue flag and an enemy's fatigue tag — each with its own copy of
# the two comparisons and its own strings welded into them. Only the strings
# actually differ between the three, so only the strings are per-site now.
VitalBand = Literal["CRITICAL", "LOW", "OK"]


def _vital_band(pct: float, critical_pct: float, low_pct: float) -> VitalBand:
    """Classify a vitals fraction against its own two thresholds."""
    if pct < critical_pct:
        return "CRITICAL"
    if pct < low_pct:
        return "LOW"
    return "OK"


_PLAYER_HP_FLAGS: Dict[VitalBand, str] = {
    "CRITICAL": " ⚠ HP CRITICAL",
    "LOW": " LOW",
    "OK": "",
}

_PLAYER_FATIGUE_FLAGS: Dict[VitalBand, str] = {
    "CRITICAL": " ⚠ FATIGUE CRITICAL",
    "LOW": " LOW",
    "OK": "",
}

# An enemy's fatigue reads as an opportunity rather than a warning, so it says
# what Jean should do about it rather than restating the number.
_ENEMY_FATIGUE_FLAGS: Dict[VitalBand, str] = {
    "CRITICAL": " ⚠ FATIGUE CRITICAL — likely to Rest",
    "LOW": " [fatigue LOW]",
    "OK": "",
}


class TacticalState(TypedDict):
    """The reduced combat picture `_derive_tactical_state` hands the scorer.

    Every threshold comparison in the heuristic path is resolved into one of
    these fields, so `_score_move` branches on named booleans instead of
    re-deriving arithmetic. Declared rather than left as a bare
    ``Dict[str, Any]`` because it is consumed by string subscript at roughly
    twenty call sites across two methods: a mistyped key there raises a
    KeyError only on the branch that reads it, i.e. only in the tactical
    situation that branch exists for.
    """

    heat: float
    heat_band: HeatBand
    hp_critical: bool
    fatigue_critical: bool
    fatigue_low: bool
    # Not derivable from the two above. Fatigue as a FRACTION of max is not the
    # signal that matters -- whether Jean can still pay for an attack is. The
    # two diverge for a wide band on a heavy weapon; see `_offense_priced_out`.
    offense_priced_out: bool
    defensively_vulnerable: bool
    dot_active: bool
    dodge_impaired: bool
    enemy_dot_active: bool
    enemy_likely_resting: bool
    # None when nothing is incoming — never a sentinel. See `_incoming_beats`.
    incoming_beats: Optional[int]
    in_defensive_window: bool
    # Pre-rendered "low–high" band, not a number: it is prompt/reasoning text.
    estimated_damage: str
    incoming_lethal: bool


class IncomingThreat(TypedDict):
    """What one telegraphed enemy move is worth, per `_estimate_incoming_damage`.

    Declared rather than left a bare ``Dict[str, Any]`` for the same reason
    `TacticalState` above is: these dicts are read by string subscript at nine
    sites across four methods, and a mistyped key raises only on the branch
    that reads it.
    """

    # Pre-rendered "low–high" band, not a number: it is prompt/reasoning text.
    estimated_damage: str
    midpoint: int
    potentially_lethal: bool


class WorstThreat(TypedDict):
    """The single most pressing charge, per `_worst_incoming_threat`.

    Deliberately NOT ``IncomingThreat`` plus a key: it drops ``midpoint``,
    which no caller of `_worst_incoming_threat` reads, and adds the beat count,
    which `_estimate_incoming_damage` never produces.
    """

    # None when nothing is incoming — never a sentinel. See `_incoming_beats`.
    beats_until_resolve: Optional[int]
    estimated_damage: str
    potentially_lethal: bool


class PlayerVitals(NamedTuple):
    """Jean's HP/fatigue/heat, guarded once.

    Carries the raw numerator and denominator alongside each percentage
    because `_player_block` prints all three.
    """

    hp: int
    max_hp: int
    hp_pct: float
    fatigue: int
    max_fatigue: int
    fatigue_pct: float
    heat: float


class PlayerDefenses(NamedTuple):
    """Jean's two defensive stats. Named so the pair cannot be swapped silently."""

    evasion: int
    defense: int


def _is_defensively_vulnerable(evasion: Any, defense: Any) -> bool:
    """True when Jean's defenses will not meaningfully absorb an incoming hit.

    One encoding of the rule, used by both the heuristic fallback's scoring and
    the runtime prompt's vulnerability note. The system prompt states the
    complement of it ("reduce urgency if evasion >= X or defense >= Y") off the
    same two constants.
    """
    return (evasion or 0) < _LOW_EVASION and (defense or 0) < _LOW_DEFENSE


def _player_defenses(player: Dict[str, Any]) -> PlayerDefenses:
    """Return Jean's ``(evasion, defense)`` from a serialized player.

    ``defense`` is the serializer's name for the engine's ``protection``, which
    ALREADY includes worn armour — Player.refresh_protection_rating folds gear
    in before CombatantSerializer reads it. This helper used to add
    ``equipment.armor.defense`` on top, a key the serializer has never emitted
    (its armour block carries ``name`` and ``protection`` only, and its own
    docstring says summing both would double-count), so the sum was a no-op
    that also made `_player_block` print "Armor Defense: 0" for a fully
    armoured Jean.
    """
    stats = player.get("stats") or {}
    return PlayerDefenses(stats.get("evasion", 0), stats.get("defense", 0))


def _player_vitals(player: Dict[str, Any]) -> PlayerVitals:
    """Read Jean's vitals off the wire, applying every guard exactly once.

    One place owns the "or 1" denominators and the "or 0"/"or 1.0" defaults,
    for the heuristic path (`_derive_tactical_state`), the prompt path
    (`_build_user_prompt`) and `_ensure_target_ids` alike.
    """
    hp = player.get("hp") or 0
    max_hp = player.get("max_hp") or 1
    fatigue = player.get("fatigue") or 0
    max_fatigue = player.get("max_fatigue") or 1
    return PlayerVitals(
        hp=hp,
        max_hp=max_hp,
        hp_pct=hp / max_hp,
        fatigue=fatigue,
        max_fatigue=max_fatigue,
        fatigue_pct=fatigue / max_fatigue,
        heat=float(player.get("heat") or 1.0),
    )


def _defense_lands_in_time(beats_until_resolve: Optional[int]) -> bool:
    """True when a Dodge or Parry cast THIS beat is standing when the hit lands.

    The one encoding of the timing rule, read by the fallback scorer and the
    prompt's INCOMING alert. Both bounds are the engine's, and both were
    measured against the real combat loop rather than reasoned about:

      * Below `_DEFENSIVE_WINDOW_BEATS` the defence resolves after the hit.
      * AT it the two land on the same beat, and the defence still wins: the
        combat loop advances every player move before it runs the NPCs' turns
        (ApiCombatAdapter's beat loop), so the `Dodging` state is on Jean by the
        time the enemy's execute fires. The bound is therefore ``>=``, not ``>``.
      * Above `_LAST_DEFENSIBLE_BEAT` the stance has expired again before the
        hit arrives, so the beat is better spent elsewhere and re-cast later.

    The comparison used to run the other way — ``incoming_beats <=
    _DEFENSIVE_WINDOW_BEATS`` — which scored Dodge 80-97 for exactly the hits
    it could no longer reach and stayed silent for every hit it could. The
    module already said as much in prose — `_enemy_block`'s "too late for a
    clean Dodge/Parry" — while scoring those same beats as urgent defence.
    """
    return (
        beats_until_resolve is not None
        and _DEFENSIVE_WINDOW_BEATS <= beats_until_resolve <= _LAST_DEFENSIBLE_BEAT
    )


def _charge_is_worth_flagging(beats_until_resolve: Optional[int]) -> bool:
    """True when a telegraphed hit deserves a line in SITUATIONAL ALERTS.

    Deliberately only the LOWER bound of `_defense_lands_in_time` is dropped,
    and the upper bound kept: a hit landing in one beat cannot be dodged, but
    it is the most urgent fact on the battlefield and the model must be told —
    including that spending the beat on a stance would waste it. Past
    `_LAST_DEFENSIBLE_BEAT` there is nothing to say yet, because a stance cast
    now would have expired before the blow arrived.

    Reading the defensive bound here is therefore correct: this predicate is
    about what a DEFENCE can reach. `_rank_enemies` asks a different question
    and reads `_IMMINENT_CHARGE_BEATS` instead.
    """
    return (
        beats_until_resolve is not None
        and beats_until_resolve <= _LAST_DEFENSIBLE_BEAT
    )


def _offerable_moves(available_moves: List[Any]) -> List[Dict[str, Any]]:
    """The moves Jean may actually be told to cast this beat.

    One owner for "which moves are offerable", because the answer is a promise
    the two consumers make to each other: `_moves_block` renders this list for
    the model and `_get_fallback_suggestions` scores it when the model is
    unavailable, so anything one shows the other must be able to pick. They had
    already diverged — the fallback additionally skipped a move literally named
    ``"Cancel"``, a string that appears nowhere in ``src/`` or
    ``frontend/src/`` outside two unrelated dialog tests, so it filtered
    something no serializer emits while the prompt happily offered it.
    """
    return [
        m
        for m in available_moves
        if isinstance(m, dict) and m.get("available", True)
    ]


def _enemy_max_fatigue(enemy: Dict[str, Any]) -> int:
    """Max fatigue for a serialized enemy, tolerating both wire spellings.

    ``CombatantSerializer`` emits ``max_fatigue`` and its legacy ``maxfatigue``
    alias; never trust either alone, and never divide by zero.
    """
    return max(enemy.get("max_fatigue") or enemy.get("maxfatigue") or 1, 1)


def _incoming_beats(mip: Optional[Dict[str, Any]]) -> Optional[int]:
    """Beats until a charging enemy move lands, or None if nothing is coming.

    A pure read of the wire field ``beats_until_resolve``, which the engine
    computes in ``Move.beats_until_resolve`` (src/moves/_base.py) and the
    serializer puts on the payload. Deliberately performs NO arithmetic: this
    module used to walk the stage machine itself, and the copy had drifted from
    the engine in all three of its branches. The damaging one was recoil and
    cooldown — ``move_in_progress`` (src/combatant.py) intentionally keeps
    returning a move through its aftermath stages, so a move that had ALREADY
    HIT still carried a small ``beats_left`` and got announced to the model as
    an incoming attack, spending Jean's beat on a phantom Dodge.

    The engine returns None for exactly that case; None here means "not
    incoming", and every caller must skip rather than substitute a sentinel.
    """
    if not mip:
        return None
    beats = mip.get("beats_until_resolve")
    if isinstance(beats, bool) or not isinstance(beats, int):
        return None
    return beats


# What a status effect MEANS for Jean, from both sides of the fight.
#
# Advice only. The effect's numbers are NOT here: they are the engine's, and
# they arrive on the wire as ``tactical_mechanics``, which src/states.py
# derives from the ``add_*`` delta actually on a state's books — see
# ``State._applied_pct`` and the module docstring above it. That is a stronger
# guarantee than interpolating the class constant, and deliberately so: the
# constant is what the state MEANS to apply, and the two diverge on integer
# truncation and on a compounded state, which is how a summary once reported
# −40% for an applied −35%. This table used to carry a hand-typed ``mechanics`` column
# beside the notes, and it had already gone stale in three places — it told the
# model Poisoned ticks every beat when ``Poisoned._EXECUTE_ON`` is 5, that
# Enflamed ticks every 3 beats when it burns every single one, and that Slimed
# drains fatigue, which it has never done. A wrong number in a combat prompt is
# worse than a missing one, so the numbers have exactly one owner now and this
# module contributes only the half an engine cannot know: which side of the
# fight is holding the effect.
#
# ``player_note`` and ``enemy_note`` are both written from JEAN's point of view
# (an enemy's Parrying reads "do not attack", not "you are parrying").
_STATUS_TACTICAL_NOTES: Dict[str, Dict[str, str]] = {
    "Disoriented": {
        "player_note": (
            "Dodge is less reliable; consider Rest or UseItem instead of "
            "defensive moves"
        ),
        "enemy_note": (
            "Easier to hit — press offense while their accuracy and defense "
            "are reduced"
        ),
    },
    "Slimed": {
        "player_note": (
            "Acid is eating HP on a timer; end the fight rather than trade beats"
        ),
        "enemy_note": "Impaired and draining — good time to press the attack",
    },
    "Resonant": {
        "player_note": "HP draining through armor; end combat quickly or heal",
        "enemy_note": "Taking sustained damage — time is working in Jean's favour",
    },
    "Petrified": {
        "player_note": (
            "Slower and harder to dodge but tankier; prefer offense over evasion"
        ),
        "enemy_note": (
            "Slower but tankier — finesse-based moves may be less effective; "
            "sustain pressure"
        ),
    },
    "Fervent": {
        "player_note": (
            "Bonus damage now but bleeding resources — press the attack, don't stall"
        ),
        "enemy_note": (
            "Dealing more damage but bleeding resources — play defensively and "
            "outlast them"
        ),
    },
    "Poisoned": {
        "player_note": (
            "Each wasted beat costs HP; aggressive offense to end combat is preferred"
        ),
        "enemy_note": (
            "Time works in Jean's favour — no need to rush; avoid unnecessary risk"
        ),
    },
    "Enflamed": {
        "player_note": "Time pressure — prioritize finishing the fight quickly",
        "enemy_note": "Burning down — steady pressure is enough; avoid overcommitting",
    },
    "Hollowed": {
        "player_note": "Sustained drain; UseItem or Rest only if absolutely necessary",
        "enemy_note": "Weakening over time — Jean can afford a measured approach",
    },
    "Staggered": {
        "player_note": (
            "Jean's next move alone winds up far slower; spend it on something "
            "cheap and burn the penalty rather than on a committed attack"
        ),
        "enemy_note": (
            "Their next move is slow to wind up — a free window; press the "
            "attack before it closes"
        ),
    },
    "Secret Plans": {
        "player_note": (
            "Stronger, faster and defter for a while; commit to expensive "
            "moves now, while they are at their best"
        ),
        "enemy_note": (
            "Buffed across the board on a timer — avoid trading blows; defend "
            "or disengage until it lapses"
        ),
    },
    "Quarried": {
        "player_note": (
            "Jean's armour is compromised, so hits land harder; favour evasion "
            "over absorbing them"
        ),
        "enemy_note": (
            "Their protection is down — this is the window for the heaviest "
            "move available"
        ),
    },
    "Hawkeye": {
        "player_note": "Ranged attacks are more reliable now; prefer them if available",
        "enemy_note": (
            "Their ranged attacks are more reliable — close the distance or break "
            "line of fire"
        ),
    },
    "Dodging": {
        "player_note": "Already dodging; another Dodge would be redundant",
        "enemy_note": (
            "Harder to land hits right now — consider waiting a beat or using a "
            "guaranteed move"
        ),
    },
    "Parrying": {
        "player_note": "Already parrying; wait for the enemy to trigger it",
        "enemy_note": (
            "Do not attack — they will parry and deal recoil damage; wait for "
            "stance to expire"
        ),
    },
}


# Kept deliberately terse: this block is static and re-sent on every
# combat turn, so prose here is paid for once per beat forever. It carries
# all nine priorities, every threshold the model needs statically, and the
# output contract, and nothing else — the 2.0x BLAZING band, for instance,
# lives in the runtime heat label and alert block rather than here because
# it is only ever true some of the time. tools/measure_llm_tokens.py sizes
# it; no test holds it to a budget, so a figure quoted here would go stale
# the first time a line was added.
#
# Do not trim the "between the two it is baseline" clause or the fatigue
# framing above the priorities. An earlier pass cut both as redundant --
# the heat bands were only ever described at the extremes -- and the
# model started answering Rest for a healthy player at 80% fatigue with
# no incoming threat, because nothing told it what to do at heat 1.0.
# It reproduced 3/3 against the trimmed prompt and 0/3 against this one.
# tests/integration/test_tactical_advisor_live.py is the guard; re-run
# it after editing this string.
_SYSTEM_PROMPT = (
    "You are the Tactical Strategist for Jean Claire (male human). Analyze the combat "
    "state and suggest the best moves. Weigh everything given: attributes, consumables, "
    "status effects, and the combat log's narrative flow.\n\n"
    "HEAT is Jean's damage/XP multiplier (0.5×–10×); the context labels the current band. "
    f"At {_HEAT_HOT}× and above, favor offense and protect the streak — a miss "
    f"drops heat "
    f"×{_HEAT_MISS_PENALTY}. "
    f"Below {_HEAT_COLD}×, land cheap hits to rebuild before committing to expensive moves. "
    "Between the two it is baseline: offense and defense trade evenly, so act on "
    "the situation.\n\n"
    "Fatigue is a resource to spend, not to hoard: Rest only when priority 1 or 4 "
    "below actually applies.\n\n"
    "PRIORITIES, in order:\n"
    f"1. Fatigue < {_pct(_FATIGUE_CRITICAL_PCT)}: prefer Rest; avoid high-cost offense.\n"
    "1b. Offense priced out: when the alerts say no attack is affordable, "
    "'Available Moves' is showing only what Jean can still pay for — every attack "
    "he knows costs more than he has. Rest is the only move that restores fatigue; "
    "zero-cost maneuvers (Advance, Withdraw, Turn, Check) do not, so recommending "
    "one leaves Jean exactly where he is next beat. Prefer Rest unless an incoming "
    "hit must be answered this beat.\n"
    f"2. Telegraphed attack: Dodge/Parry land {_DEFENSIVE_WINDOW_BEATS} beats after "
    f"casting and then hold for {_DEFENSIVE_STANCE_BEATS} beats, counting the beat "
    "it goes up on. "
    f"Beats until impact {_DEFENSIVE_WINDOW_BEATS}–{_LAST_DEFENSIBLE_BEAT} → strongly "
    f"prefer them. Under {_DEFENSIVE_WINDOW_BEATS}, the defense resolves after "
    f"the hit; over {_LAST_DEFENSIBLE_BEAT}, the stance expires before it. "
    "In both cases spend the beat on something else. "
    f"Weigh estimated incoming damage against Jean's HP; reduce urgency if evasion ≥ "
    f"{_LOW_EVASION} or defense ≥ {_LOW_DEFENSE}. "
    "Cooldown ETAs are shown for unavailable defensive moves.\n"
    "3. Status effects: each carries a tactical note — honor it. Enemy effects are "
    "already written from Jean's perspective.\n"
    f"4. HP < {_pct(_HP_CRITICAL_PCT)}: prefer UseItem, Rest, or Withdraw over offense.\n"
    "5. Allies present: focus fire the weakest or most dangerous enemy; Jean may target "
    "what an ally is already engaging.\n"
    "6. Target Priority section, when shown, wins unless a more urgent threat "
    "(e.g. incoming lethal hit) overrides it.\n"
    "7. Enemy fatigue LOW/CRITICAL: they may Rest instead of attacking — press offense.\n"
    "8. Enemy > 5ft: Advance usually beats a short-reach attack.\n"
    "9. Enemy ≤ 1ft: Dodge or Withdraw before ranged/sweeping moves.\n\n"
    "Suggest only moves from 'Available Moves'. Each suggestion is a JSON object:\n"
    "- move_name: exact move name.\n"
    "- target_id: exact ID from the Enemies list when the move needs a target "
    "(e.g. 'enemy_12345'); null ONLY for self-targeted or non-targeted moves.\n"
    "- score: 1-100 tactical advantage.\n"
    "- reasoning: one brief sentence."
)


def wrap_suggestions_prompt(user_prompt: str, max_suggestions: int) -> str:
    """Wrap a built combat context with the JSON output instruction.

    Public because the shape of the request the model actually receives is not
    only ``get_suggestions``' business: ``tools/measure_llm_tokens.py`` sizes
    the real production prompt and used to keep a hand-copy of this f-string,
    with a comment admitting it "mirrors that wrapper exactly". It is the
    wrapper now — import it rather than restating it.
    """
    return (
        f"{user_prompt}\nReturn the result as a JSON object with a key 'suggestions' "
        f"containing a list of exactly {max_suggestions} move objects."
    )


class CombatLLMAdapter(GenericLLMClient):
    """``GenericLLMClient`` with per-feature combat overrides.

    The base client reads only the global ``MYNX_LLM_*`` variables, so the
    strategist could not be pointed at a different model without moving Mynx
    too — and the two want opposite things: combat runs a request per beat and
    wants something fast and cheap, Mynx runs occasionally and wants something
    capable. Mirrors the convention ``NpcChatLLMAdapter`` established for NPC
    chat (ai/llm_client.py).

      - COMBAT_LLM_ENABLED=1                  -> override MYNX_LLM_ENABLED
      - COMBAT_LLM_PROVIDER=ollama|openrouter -> override MYNX_LLM_PROVIDER
      - COMBAT_LLM_MODEL=<model_id>           -> override MYNX_LLM_MODEL

    Each list falls back to the MYNX_* name, so an existing MYNX_*-only
    configuration keeps working exactly as before.
    """

    # Declared as data rather than re-applied after super().__init__(): the
    # base class resolves the gate, runs model discovery and validates the
    # provider *inside* __init__, so an override applied afterwards had combat
    # dialling a host the base class had checked for nothing. See
    # GenericLLMClient._resolve_provider.
    #
    # The gate DOES fall back to MYNX_LLM_ENABLED, where NpcChatLLMAdapter's
    # deliberately does not, and the difference is real rather than an
    # oversight. Chat is player-authored prose being shipped to a third party,
    # so switching on the mynx pet must not switch that on by implication.
    # Combat is not: the strategist reads a battlefield the operator's own
    # engine produced, and until this branch it was a bare GenericLLMClient
    # gated on MYNX_LLM_ENABLED alone. Dropping the fallback would silently
    # turn the Tactical Advisor off on every existing install at upgrade — a
    # regression, not a tightening. An explicit COMBAT_LLM_ENABLED=0 still
    # wins, because _first_env takes the first non-empty value.
    _ENABLED_ENV_VARS = ("COMBAT_LLM_ENABLED", "MYNX_LLM_ENABLED")
    _PROVIDER_ENV_VARS = ("COMBAT_LLM_PROVIDER", "MYNX_LLM_PROVIDER")
    _MODEL_ENV_VARS = ("COMBAT_LLM_MODEL", "MYNX_LLM_MODEL")


class CombatStrategist:
    """Strategist that suggests tactical moves during combat using an LLM."""

    def __init__(self, client: Optional[GenericLLMClient] = None):
        logger.debug("Initializing CombatStrategist")
        self.client = client or CombatLLMAdapter()
        # Static text, built once at import (see _SYSTEM_PROMPT above); this is
        # a reference, not a re-concatenation. Kept as an instance attribute
        # because tools/measure_llm_tokens.py reads it off a live strategist.
        self.system_prompt = _SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_suggestions(
        self, combat_context: Dict[str, Any], max_suggestions: int = 1
    ) -> List[Dict[str, Any]]:
        """Fetch movement suggestions from the LLM or fallback to heuristics.

        ``GenericLLMClient.generate_structured`` is typed and documented as
        returning a dict or None — it explicitly discards a non-dict payload —
        so the response is unpacked as dict-or-nothing. Anything else is a
        contract violation on the client's side, not a shape to handle here.
        """
        logger.debug(
            "CombatStrategist.get_suggestions called (max: %s)", max_suggestions
        )

        suggestions = []
        if self.client.available():
            try:
                user_prompt = self._build_user_prompt(combat_context)
                wrapped_prompt = wrap_suggestions_prompt(user_prompt, max_suggestions)

                logger.debug(
                    "Requesting %s suggestions for %s",
                    max_suggestions,
                    combat_context.get("player", {}).get("name"),
                )
                raw_response = self.client.generate_structured(
                    self.system_prompt, wrapped_prompt
                )

                raw_suggestions = (
                    raw_response.get("suggestions", [])
                    if isinstance(raw_response, dict)
                    else []
                )

                for s in raw_suggestions:
                    if isinstance(s, dict) and "move_name" in s:
                        try:
                            s["score"] = int(s.get("score", 0))
                        except (ValueError, TypeError):
                            s["score"] = 0
                        suggestions.append(s)

            except Exception as e:
                logger.error("Error in LLM suggestion flow: %s", e, exc_info=True)

        if not suggestions:
            logger.debug("Using heuristic fallback for combat suggestions.")
            return self._get_fallback_suggestions(combat_context, max_suggestions)

        suggestions.sort(key=lambda x: x["score"], reverse=True)
        results = suggestions[:max_suggestions]
        self._ensure_target_ids(results, combat_context)
        logger.debug("CombatStrategist returning %s suggestions.", len(results))
        return results

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    def _derive_tactical_state(self, ctx: Dict[str, Any]) -> TacticalState:
        """Reduce a combat context to the flags the fallback scorer needs.

        Every threshold comparison in the heuristic path happens here, once,
        against the module constants — so the scorer below is pure branching on
        named booleans rather than a second copy of the same arithmetic.
        """
        player = ctx.get("player", {})
        vitals = _player_vitals(player)
        defenses = _player_defenses(player)

        hp_band = _vital_band(vitals.hp_pct, _HP_CRITICAL_PCT, _HP_LOW_PCT)
        fatigue_band = _vital_band(
            vitals.fatigue_pct, _FATIGUE_CRITICAL_PCT, _FATIGUE_LOW_PCT
        )

        player_status_names = {
            s.get("name", "") for s in player.get("status_effects", [])
        }
        enemies = ctx.get("enemies", [])

        # Beats-until-impact and estimated damage for the charge Jean's next
        # beat should answer — NOT simply the soonest one. See
        # `_threat_worth_defending`.
        threat = self._threat_worth_defending(enemies, vitals.hp)
        incoming_beats = threat["beats_until_resolve"]

        return {
            "heat": vitals.heat,
            "heat_band": _heat_band(vitals.heat),
            "hp_critical": hp_band == "CRITICAL",
            "fatigue_critical": fatigue_band == "CRITICAL",
            # "CRITICAL" is inside "LOW": the scorer's low-fatigue branch is
            # only reached after the critical one has already returned.
            "fatigue_low": fatigue_band in ("CRITICAL", "LOW"),
            # Read off the context rather than the vitals: this is an
            # affordability question, and the answer lives in
            # `fatigue_locked_moves`, which the adapter supplies alongside
            # `available_moves` precisely because the latter has already had
            # everything unaffordable stripped out of it.
            "offense_priced_out": self._offense_priced_out(ctx),
            "defensively_vulnerable": _is_defensively_vulnerable(*defenses),
            # Active DoT on player accelerates urgency to end combat
            "dot_active": bool(player_status_names & _DOT_STATUSES),
            # Dodge reliability is impaired by certain status effects
            "dodge_impaired": bool(player_status_names & _DODGE_IMPAIRING_STATUSES),
            # If any enemy has DoT, time is on Jean's side — slightly less aggressive
            "enemy_dot_active": any(
                any(
                    s.get("name", "") in _DOT_STATUSES
                    for s in e.get("status_effects", [])
                )
                for e in enemies
            ),
            # If an enemy is likely to Rest (low fatigue), that's an offensive window
            "enemy_likely_resting": any(
                _vital_band(
                    (e.get("fatigue") or 0) / _enemy_max_fatigue(e),
                    _FATIGUE_CRITICAL_PCT,
                    _FATIGUE_LOW_PCT,
                )
                == "CRITICAL"
                for e in enemies
            ),
            "incoming_beats": incoming_beats,
            "in_defensive_window": _defense_lands_in_time(incoming_beats),
            "estimated_damage": threat["estimated_damage"],
            "incoming_lethal": threat["potentially_lethal"],
        }

    @staticmethod
    def _score_defensive_move(name: str, state: TacticalState) -> Tuple[int, str]:
        """Score Dodge/Parry against a hit that is still inside the defensive window.

        Ordered most-constrained first: an impaired Dodge is worth little
        against a survivable hit and a great deal against a lethal one, so the
        two impairment branches must both be tested before the plain lethal
        branch, which would otherwise swallow them.
        """
        min_bui = state["incoming_beats"]
        est_damage = state["estimated_damage"]
        est_lethal = state["incoming_lethal"]

        if state["dodge_impaired"] and not est_lethal:
            # Status effect reduces defensive move value when the hit is survivable
            return 60, (
                f"Attack in ~{min_bui} beat(s) but status effect impairs {name} "
                "reliability; consider UseItem or accepting the hit."
            )
        if state["dodge_impaired"] and est_lethal:
            # Even impaired, better than a one-shot
            return 88, (
                f"Incoming hit is potentially lethal in ~{min_bui} beat(s); "
                f"{name} reliability is reduced by status effect but still "
                "preferable to dying."
            )
        if est_lethal:
            return 97, (
                f"Potentially lethal hit (~{est_damage} dmg) landing in "
                f"~{min_bui} beat(s); {name} is critical."
            )
        if state["defensively_vulnerable"]:
            return 95, (
                f"Attack landing in ~{min_bui} beat(s) and Jean's defenses are "
                f"low (~{est_damage} estimated dmg); {name} now."
            )
        return 80, (
            f"Attack in ~{min_bui} beat(s) (~{est_damage} estimated dmg); "
            f"{name} is advisable but Jean's defenses may absorb it."
        )

    @staticmethod
    def _score_move(move: Dict[str, Any], state: TacticalState) -> Tuple[int, str]:
        """Score one available move against the derived tactical state.

        Returns ``(score, reasoning)``. Branches are ordered by CONSEQUENCE,
        first match wins — deliberately NOT by the system prompt's priority
        numbering, which runs 2, 1, 4, 3 through the first four branches here.
        The prompt's list ranks considerations for a model weighing all of them
        at once; this ladder short-circuits, so a lethal hit landing inside the
        defensive window (prompt priority 2) has to be tested before critical
        fatigue (priority 1). Reordering these to match the prompt's numbers
        would put Rest ahead of surviving the next beat.
        """
        name = move.get("name", "Unknown")
        category = move.get("category", "Miscellaneous")
        base_score = _CATEGORY_BASE_SCORES.get(category, _DEFAULT_CATEGORY_SCORE)

        if state["in_defensive_window"] and name in ("Dodge", "Parry"):
            return CombatStrategist._score_defensive_move(name, state)

        if state["fatigue_critical"] and name == "Rest":
            return 90, (
                "Fatigue critically low; Rest is essential to maintain move availability."
            )

        # Issue #504: Rest was never missing from the candidate set -- it lost a
        # scoring contest inside a dead band. Measuring fatigue pressure as a
        # fraction of max disconnects it from what moves actually COST: with a
        # heavy weapon (Rusted Iron Mace, maxfatigue 190, Attack 90) the two
        # diverge across the whole 25%-47.4% band, where Attack is already
        # unaffordable but Rest scored 72 and lost to Advance (80), Maneuver
        # (75) and Dodge. Every move that wins there costs 0 fatigue, and
        # nothing restores fatigue passively -- Rest and SecondWind are its only
        # writers -- so fatigue never moved, the 25% line was never crossed, and
        # the advice repeated forever. Only the top-scored move is shown, so an
        # 8-point loss made Rest invisible.
        if state["offense_priced_out"] and name == "Rest":
            return 90, (
                "No attack is affordable at this fatigue; Rest is the only move "
                "that restores it -- a zero-cost maneuver leaves Jean here next beat."
            )

        if state["hp_critical"] and name == "UseItem":
            return 88, "HP critically low; use a healing consumable before engaging."

        if state["dot_active"] and category == "Offensive":
            # Player DoT ticking — reward aggression to end the fight
            return min(95, base_score + 8), (
                f"DoT is draining HP; {name} to end combat quickly."
            )

        if state["enemy_likely_resting"] and category == "Offensive":
            # Enemy likely to Rest next turn — safe offensive window
            return min(95, base_score + 6), (
                f"Enemy fatigue is critical — they may Rest next turn; {name} to "
                "exploit the window."
            )

        if state["enemy_dot_active"] and category == "Offensive":
            # Enemy has DoT — time favours Jean, slightly less frantic. Named
            # generically: _DOT_STATUSES covers acid, resonance and spiritual
            # drain as well as poison and fire.
            return base_score, (
                f"Enemy is losing HP on a timer — {name} while time works in "
                "Jean's favour."
            )

        if state["fatigue_low"] and name in ("Wait", "Rest"):
            return (
                72,
                f"Fatigue is low; {name} conserves resources for a better opportunity.",
            )

        if name == "Advance":
            return 80, "Close the distance to bring offensive moves into range."

        if name in ("Wait", "Check"):
            return 20, f"{name} cedes initiative; use only if no better option exists."

        if category == "Offensive":
            heat_band = state["heat_band"]
            score = min(99, base_score + _HEAT_OFFENSIVE_BONUS[heat_band])
            return score, _HEAT_OFFENSIVE_NOTE[heat_band].format(
                heat=state["heat"], name=name
            )

        return base_score, _NO_TACTICAL_READ.format(name=name)

    def _get_fallback_suggestions(
        self, combat_context: Dict[str, Any], max_suggestions: int
    ) -> List[Dict[str, Any]]:
        """Provide context-aware suggestions based on combat state when the LLM is unavailable."""
        available = _offerable_moves(combat_context.get("available_moves", []))
        if not available:
            return [
                {
                    "move_name": "Check",
                    "target_id": None,
                    "score": 10,
                    "reasoning": "No other moves available; reassess the battlefield.",
                }
            ]

        state = self._derive_tactical_state(combat_context)

        scored_moves = []
        for m in available:
            score, reasoning = self._score_move(m, state)
            scored_moves.append(
                {
                    "move_name": m.get("name", "Unknown"),
                    "target_id": None,
                    "score": score,
                    "reasoning": reasoning,
                }
            )

        scored_moves.sort(key=lambda x: x["score"], reverse=True)

        results = scored_moves[
            : max(1, min(_MAX_FALLBACK_SUGGESTIONS, max_suggestions))
        ]
        self._ensure_target_ids(results, combat_context)
        return results

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_user_prompt(self, ctx: Dict[str, Any]) -> str:
        """Construct the context string for the LLM.

        Pure assembly: every section is built by its own ``_*_block`` helper.
        Section order is READING order — the battlefield described once, top to
        bottom, then the alerts drawn from it, then the menu of moves. It is
        not the system prompt's priority order and does not try to be: allies
        (priority 5) are described beside the enemies they are fighting rather
        than between the two halves of priority 2, and the alert block is
        placed last of the situational sections so it reads as a summary of
        everything above it.
        """
        player = ctx.get("player", {})
        enemies = ctx.get("enemies", [])

        # Derived ONCE here and handed down. `_player_defenses` used to be
        # re-called inside each block that wanted it, so those sections each
        # re-read the wire independently while `PlayerVitals` beside them was
        # threaded properly.
        vitals = _player_vitals(player)
        defenses = _player_defenses(player)

        enemies_block, imminent_alerts = self._enemy_block(enemies, vitals, defenses)
        # Multi-enemy target priority
        priority_block = (
            self._build_target_priority(enemies, vitals.hp) if len(enemies) > 1 else ""
        )
        history_str = "\n".join(ctx.get("history", [])[-5:])

        return (
            f"{self._player_block(player, vitals, defenses)}\n\n"
            f"{enemies_block}\n"
            f"{self._ally_block(ctx.get('allies', []))}"
            f"{self._cooldown_block(ctx.get('defensive_cooldowns', {}))}"
            f"{priority_block}"
            f"{self._alert_block(imminent_alerts, vitals, ctx)}\n"
            f"Recent History:\n{history_str}\n"
            f"Previous Move: {ctx.get('last_move', 'None')}\n\n"
            f"Available Moves:\n{self._moves_block(ctx.get('available_moves', []))}"
        )

    @staticmethod
    def _heat_label(heat: float) -> str:
        """Render the heat band the system prompt's HEAT paragraph refers to."""
        band = _heat_band(heat)
        swing = int(abs(heat - 1) * 100)
        return f"{heat:.2f}× [{_HEAT_LABEL_BODY[band].format(swing=swing)}]"

    def _player_block(
        self,
        player: Dict[str, Any],
        vitals: PlayerVitals,
        defenses: PlayerDefenses,
    ) -> str:
        """Jean's vitals, attributes, stats, passives, statuses and consumables."""
        pos = player.get("position") or {}
        hp_flag = _PLAYER_HP_FLAGS[
            _vital_band(vitals.hp_pct, _HP_CRITICAL_PCT, _HP_LOW_PCT)
        ]
        fatigue_flag = _PLAYER_FATIGUE_FLAGS[
            _vital_band(vitals.fatigue_pct, _FATIGUE_CRITICAL_PCT, _FATIGUE_LOW_PCT)
        ]

        p_attrs = ", ".join(
            [f"{k}: {v}" for k, v in player.get("attributes", {}).items()]
        )
        passives = self._extract_names(player.get("passives", []))

        p_stats = player.get("stats", {})

        # Populated by ApiCombatAdapter's context build, which spreads
        # `serialize_combatant` (which has no consumables key of its own)
        # and adds `CombatStateSerializer._get_consumables`. Read under one
        # spelling on purpose — a second tolerated key would be a guess.
        p_consumables = ", ".join(
            [
                f"{c.get('name', 'Item')} (Qty: {c.get('qty', 1)})"
                for c in player.get("consumables", [])
            ]
        )

        # Status effects with mechanical context
        status_lines = self._format_status_effects(player.get("status_effects", []))

        return (
            f"Player: {player.get('name', 'Jean')} (Male Human) "
            f"[HP: {vitals.hp}/{vitals.max_hp}{hp_flag}, "
            f"Fatigue: {vitals.fatigue}/{vitals.max_fatigue}{fatigue_flag}, "
            f"Heat: {self._heat_label(vitals.heat)}, "
            f"Pos: {pos.get('x')},{pos.get('y')}, Facing: {pos.get('facing')}]\n"
            f"Attributes: [{p_attrs}]\n"
            # No separate armour line: `defense` is the engine's `protection`,
            # which already has worn armour folded into it.
            f"Combat Stats: [Evasion: {defenses.evasion}, "
            f"Defense: {defenses.defense}, "
            f"Accuracy: {p_stats.get('accuracy', 80)}, "
            f"Speed: {p_stats.get('speed', 0)}]\n"
            f"Passives: {', '.join(passives) or 'None'}\n"
            f"Status Effects:\n{status_lines}\n"
            f"Consumables: [{p_consumables or 'None'}]"
        )

    def _enemy_block(
        self,
        enemies: List[Dict[str, Any]],
        vitals: PlayerVitals,
        defenses: PlayerDefenses,
    ) -> Tuple[str, List[str]]:
        """Enemy roster plus the imminent-attack alerts it generated.

        Returns ``(block, imminent_alerts)`` — the alerts belong at the top of
        the SITUATIONAL ALERTS section (system prompt priority 2) rather than
        inline here, so they are handed back rather than emitted.

        Takes `PlayerVitals` and `PlayerDefenses`, never the raw player dict.
        It needs exactly Jean's HP and his two defensive stats, and while it
        took the dict AND a separately-derived ``player_hp`` beside it the two
        could disagree: a caller passing a player carrying no ``hp`` alongside
        ``player_hp=100`` estimated lethality against 100 while rendering the
        vulnerability note off the dict, with nothing tying them together.
        """
        enemy_list = []
        imminent_alerts: List[str] = []

        for e in enemies:
            mip = e.get("move_in_process")
            # A move still in recoil/cooldown is reported by the engine with
            # bui None: its effect already landed, so it is not a threat and
            # must not be announced as one.
            bui = _incoming_beats(mip)
            threat = (
                self._estimate_incoming_damage(mip, e, vitals.hp)
                if bui is not None
                else None
            )

            if threat is not None:
                alert = self._incoming_charge_alert(e, mip, bui, threat, defenses)
                if alert:
                    imminent_alerts.append(alert)

            enemy_list.append(self._enemy_roster_line(e, mip, bui, threat))

        return "Enemies:\n" + "\n".join(enemy_list), imminent_alerts

    @staticmethod
    def _charge_timing_note(bui: int) -> str:
        """What a defensive beat spent NOW buys against a hit ``bui`` beats out.

        Three cases off the same bounds `_defense_lands_in_time` uses. Only
        reached for a charge `_charge_is_worth_flagging` has already accepted,
        so there is no "too far out to matter" case to write.
        """
        if bui < _DEFENSIVE_WINDOW_BEATS:
            return (
                "too late for a clean Dodge/Parry; one cast now resolves "
                "after the hit"
            )
        if bui == _DEFENSIVE_WINDOW_BEATS:
            return (
                "Dodge/Parry NOW — cast this beat and it goes up on the beat "
                "the blow lands, the last moment it can"
            )
        # Slack BEFORE the cast, not margin after the hit: the stance covers
        # beats _DEFENSIVE_WINDOW_BEATS.._LAST_DEFENSIBLE_BEAT, so a blow this
        # far out can still be met if Jean waits. Phrased as a deadline
        # because it once read "with N beat(s) to spare", which at the far
        # edge of the window claimed 6 beats of margin on a hit the stance
        # expires exactly in time for.
        return (
            f"Dodge/Parry lands in time; the cast can wait up to "
            f"{bui - _DEFENSIVE_WINDOW_BEATS} more beat(s) and still meet it"
        )

    @staticmethod
    def _incoming_charge_alert(
        enemy: Dict[str, Any],
        mip: Dict[str, Any],
        bui: int,
        threat: IncomingThreat,
        defenses: PlayerDefenses,
    ) -> Optional[str]:
        """One SITUATIONAL ALERTS line for a telegraphed hit, or None.

        The hit still gets an alert when it is too soon to defend against —
        that a beat spent on Dodge would be wasted is exactly what the model
        needs told — but no alert at all once the charge is far enough out
        that a stance cast now expires before it arrives.
        """
        if not _charge_is_worth_flagging(bui):
            return None

        vuln_note = (
            f" Jean's evasion ({defenses.evasion}) and defense "
            f"({defenses.defense}) are low — this will hurt."
            if _is_defensively_vulnerable(defenses.evasion, defenses.defense)
            else " Jean's defenses may reduce impact."
        )
        lethal_note = ", LETHAL" if threat["potentially_lethal"] else ""
        return (
            f"⚠ INCOMING: {enemy.get('name')} lands {mip.get('name')} "
            f"in ~{bui} beat(s) (~{threat['estimated_damage']} dmg"
            f"{lethal_note}). "
            f"{CombatStrategist._charge_timing_note(bui)}.{vuln_note}"
        )

    def _enemy_roster_line(
        self,
        enemy: Dict[str, Any],
        mip: Optional[Dict[str, Any]],
        bui: Optional[int],
        threat: Optional[IncomingThreat],
    ) -> str:
        """One ``- Name [...]`` entry in the Enemies list."""
        e_pos = enemy.get("position") or {}
        # `or 0`, not a get() default: the wire can carry an explicit null,
        # which a default never replaces and which the division below would
        # raise a TypeError on.
        e_fatigue = enemy.get("fatigue") or 0
        e_max_fatigue = _enemy_max_fatigue(enemy)
        fat_tag = _ENEMY_FATIGUE_FLAGS[
            _vital_band(
                e_fatigue / e_max_fatigue,
                _FATIGUE_CRITICAL_PCT,
                _FATIGUE_LOW_PCT,
            )
        ]

        if threat is None:
            mip_str = ""
        else:
            lethal_tag = (
                " ⚠ POTENTIALLY LETHAL" if threat["potentially_lethal"] else ""
            )
            mip_str = (
                f", Charging: {mip.get('name')} "
                f"({bui} beat{'s' if bui != 1 else ''} until impact, "
                f"~{threat['estimated_damage']} estimated dmg{lethal_tag})"
            )

        # Enemy status effects — use enemy perspective notes
        e_statuses = self._format_status_effects(
            enemy.get("status_effects", []), perspective="enemy"
        )
        status_str = (
            f"\n    Status: {e_statuses.strip()}"
            if e_statuses.strip() != "None"
            else ""
        )

        return (
            f"- {enemy.get('name')} [ID: {enemy.get('id')}, "
            f"HP: {enemy.get('hp')}/{enemy.get('max_hp')}, "
            f"Fatigue: {e_fatigue}/{e_max_fatigue}{fat_tag}, "
            f"Pos: {e_pos.get('x')},{e_pos.get('y')}, "
            f"Dist: {enemy.get('distance')}ft{mip_str}]{status_str}"
        )

    @staticmethod
    def _ally_block(allies: List[Dict[str, Any]]) -> str:
        """Friendly combatants, or an empty string when Jean fights solo."""
        if not allies:
            return ""
        ally_lines = []
        for a in allies:
            a_pos = a.get("position") or {}
            ally_lines.append(
                f"- {a.get('name')} [ID: {a.get('id')}, "
                f"HP: {a.get('hp')}/{a.get('max_hp')}, "
                f"Pos: {a_pos.get('x')},{a_pos.get('y')}, "
                f"Dist: {a.get('distance')}ft]"
            )
        return "Allies (friendly — do not attack):\n" + "\n".join(ally_lines) + "\n"

    @staticmethod
    def _cooldown_block(def_cooldowns: Dict[str, Any]) -> str:
        """ETAs for defensive moves the player cannot cast yet."""
        if not def_cooldowns:
            return ""
        cd_parts = [
            f"{name} in {beats} beat{'s' if beats != 1 else ''}"
            for name, beats in def_cooldowns.items()
        ]
        return "Defensive moves on cooldown: " + ", ".join(cd_parts) + "\n"

    @staticmethod
    def _alert_block(
        imminent_alerts: List[str], vitals: PlayerVitals, ctx: Dict[str, Any]
    ) -> str:
        """Situational alerts, most immediately fatal first.

        A telegraphed hit leads because it is the only entry with a clock on
        it. HP CRITICAL then precedes FATIGUE CRITICAL — the reverse of the
        system prompt's numbering, where fatigue is priority 1 and HP is
        priority 4 — because dying ends the fight and running out of fatigue
        only narrows it. Heat is last: it changes what is worth doing, never
        whether Jean survives the beat.
        """
        alerts = list(imminent_alerts)
        if _vital_band(vitals.hp_pct, _HP_CRITICAL_PCT, _HP_LOW_PCT) == "CRITICAL":
            alerts.append("⚠ HP CRITICAL: Prioritize healing or defensive moves.")
        if (
            _vital_band(
                vitals.fatigue_pct, _FATIGUE_CRITICAL_PCT, _FATIGUE_LOW_PCT
            )
            == "CRITICAL"
        ):
            alerts.append("⚠ FATIGUE CRITICAL: Prefer Rest or zero-cost moves.")
        if CombatStrategist._offense_priced_out(ctx):
            # Separate from FATIGUE CRITICAL above, and reached at fatigue
            # levels that clear it: unavailable moves are stripped from the
            # prompt, so without this the model is told offense is ABSENT
            # rather than priced out, and reaches for a zero-cost maneuver that
            # leaves Jean exactly where he is (issue #504).
            #
            # A locked attack is guaranteed here, but its cost is only quoted
            # when the context actually carried one -- a hand-built context
            # without fatigue_cost would otherwise read "costs 0 fatigue".
            cheapest = CombatStrategist._cheapest_locked_offense(ctx)
            cost_note = (
                f" (cheapest attack costs {cheapest} fatigue)" if cheapest else ""
            )
            alerts.append(
                f"⚠ OFFENSE PRICED OUT: no attack is affordable at "
                f"{vitals.fatigue} fatigue{cost_note}. Rest is the only move "
                "that restores fatigue — zero-cost maneuvers will not."
            )
        heat_alert = _HEAT_ALERTS.get(_heat_band(vitals.heat))
        if heat_alert:
            alerts.append(heat_alert.format(heat=vitals.heat))
        if not alerts:
            return ""
        return "\nSITUATIONAL ALERTS:\n" + "\n".join(alerts) + "\n"

    @staticmethod
    def _moves_block(available_moves: List[Any]) -> str:
        """Available moves with fatigue cost, description and viable targets."""
        move_descriptions = []
        for m in _offerable_moves(available_moves):
            name = m.get("name")
            cost = m.get("fatigue_cost", 0)
            desc = m.get("description", "")
            cost_str = f" [Cost: {cost} fatigue]" if cost else " [No fatigue cost]"
            desc_str = f" — {desc}" if desc else ""
            targets = m.get("viable_targets", [])
            if targets:
                target_info = ", ".join(
                    [
                        f"{t.get('name')} (ID: {t.get('id')}, {t.get('distance')}ft)"
                        for t in targets
                    ]
                )
                move_descriptions.append(
                    f"{name}{cost_str} [Targets: {target_info}]{desc_str}"
                )
            else:
                move_descriptions.append(f"{name}{cost_str}{desc_str}")
        return "\n".join(f"  {d}" for d in move_descriptions)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _offense_priced_out(ctx: Dict[str, Any]) -> bool:
        """True when Jean can afford no attack but fatigue is the only thing stopping him.

        Nothing restores fatigue passively — Rest and Second Wind are the only
        writers that add it — so in this state every zero-cost move on offer
        (Advance, Withdraw, Turn, Check) leaves the situation exactly as it was
        and the same advice repeats forever. Rest is the only move that ends
        the loop.

        The condition deliberately is *not* "no Offensive move available":
        offense also disappears when the enemy is out of range or the move is
        on cooldown, and there Advance (or waiting out the cooldown) is the
        right call rather than Rest. ``fatigue_locked_moves`` — supplied by
        ApiCombatAdapter alongside ``available_moves`` — carries the moves
        priced out by fatigue specifically, which keeps the pure range/cooldown
        case out of this branch entirely. Absent that key (older or hand-built
        contexts) this is False and scoring behaves as it did before.

        The mixed case — one attack out of reach but affordable, another
        affordable only after resting — resolves to Rest by design. Advising
        Rest there is at worst a beat spent early rather than late, and it
        cannot loop: the moment fatigue clears the cheapest attack this returns
        False again. Under-firing would leave the reported soft-lock in place,
        so the tie breaks toward the move that always makes progress.
        """
        usable = [
            m for m in ctx.get("available_moves", []) if m.get("available", True)
        ]
        if any(m.get("category") == "Offensive" for m in usable):
            return False
        return any(
            m.get("category") == "Offensive"
            for m in ctx.get("fatigue_locked_moves", [])
        )

    @staticmethod
    def _cheapest_locked_offense(ctx: Dict[str, Any]) -> Optional[int]:
        """Fatigue cost of the cheapest attack Jean currently cannot pay for."""
        costs = [
            m.get("fatigue_cost") or 0
            for m in ctx.get("fatigue_locked_moves", [])
            if m.get("category") == "Offensive"
        ]
        return min(costs) if costs else None

    @staticmethod
    def _format_status_effects(
        status_effects: List[Any],
        perspective: Perspective = "player",
    ) -> str:
        """
        Render status effects with mechanical notes and remaining duration.

        The mechanical half is ENGINE-OWNED and read straight off the wire:
        ``tactical_mechanics``, which ``State`` (src/states.py) derives from
        the ``add_*`` delta it actually put on the books rather than from the
        class constant it meant to apply, so the model is never told a modifier
        or a tick interval the engine did not actually apply — truncation and
        compounding included. ``description`` — player-facing prose — is the
        fallback for a state that declares no tactical summary.

        This module supplies only the half the engine cannot know: which side
        of the fight is holding the effect. Pass perspective="enemy" for an
        enemy's effects so the implication is written from Jean's viewpoint,
        not the affected entity's.
        """
        note_key = _PERSPECTIVE_NOTE_KEYS[perspective]
        if not status_effects:
            return "  None"
        lines = []
        for s in status_effects:
            if not s:
                continue
            is_dict = isinstance(s, dict)
            name = s.get("name", "Unknown") if is_dict else str(s)
            beats_left = s.get("beats_left", 0) if is_dict else 0
            mechanics = (
                (s.get("tactical_mechanics") or s.get("description") or "").strip()
                if is_dict
                else ""
            )
            note_entry = _STATUS_TACTICAL_NOTES.get(name)
            if note_entry:
                detail_parts = [mechanics] if mechanics else []
                if beats_left > 0:
                    detail_parts.append(f"~{beats_left} beats remaining")
                detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
                lines.append(f"  {name}{detail} → {note_entry[note_key]}")
            else:
                duration_str = (
                    f", ~{beats_left} beats remaining" if beats_left > 0 else ""
                )
                lines.append(
                    f"  {name}{duration_str}{': ' + mechanics if mechanics else ''}"
                )
        return "\n".join(lines) if lines else "  None"

    @staticmethod
    def _estimate_incoming_damage(
        mip: Dict[str, Any],
        enemy: Dict[str, Any],
        player_hp: int,
    ) -> IncomingThreat:
        """
        Estimate damage range for a telegraphed enemy move.

        Uses the enemy's serialized damage stat and the move's own
        ``damage_multiplier``, which the serializer reads off the live move
        object (``Move._DAMAGE_MULTIPLIER``). This module used to keep a local
        table keyed on move CLASS names while the wire carries the runtime
        INSTANCE name, so every heavy hitter in the game — SlimeVolley ("Slime
        Volley"), TidalSurge ("Tidal Surge"), GorranClub ("NPC_Attack") — missed
        the lookup and was estimated at 1.0x, and the POTENTIALLY LETHAL flag
        never fired for the moves that most needed it.

        Protection is not available for the enemy's view of the player, so the
        estimate is conservative (raw power before mitigation).
        """
        try:
            multiplier = float(mip.get("damage_multiplier", 1.0))
        except (TypeError, ValueError):
            multiplier = 1.0
        enemy_damage = (enemy.get("stats") or {}).get("damage", 0) or enemy.get(
            "damage", 0
        )

        low = max(0, int(enemy_damage * multiplier * 0.8))
        high = max(0, int(enemy_damage * multiplier * 1.2))
        midpoint = (low + high) // 2

        return {
            "estimated_damage": f"{low}–{high}",
            "midpoint": midpoint,
            "potentially_lethal": midpoint >= player_hp * _LETHAL_HP_FRACTION,
        }

    def _worst_incoming_threat(
        self, enemies: List[Dict[str, Any]], player_hp: int
    ) -> WorstThreat:
        """Return the combined threat metrics for the most dangerous incoming charge.

        ``beats_until_resolve`` is None when nothing is actually incoming —
        every enemy is idle, or its move has already landed and is only playing
        out its recoil/cooldown. Callers must test for None rather than compare
        against a sentinel.
        """
        best: WorstThreat = {
            "beats_until_resolve": None,
            "estimated_damage": "0–0",
            "potentially_lethal": False,
        }
        for e in enemies:
            mip = e.get("move_in_process")
            bui = _incoming_beats(mip)
            if bui is None:
                continue
            threat = self._estimate_incoming_damage(mip, e, player_hp)
            current = best["beats_until_resolve"]
            if (
                current is None
                or bui < current
                or (bui == current and threat["potentially_lethal"])
            ):
                # Field by field, not `{**threat, ...}`: the two shapes differ
                # by `midpoint`, which nothing downstream of here reads.
                best = {
                    "beats_until_resolve": bui,
                    "estimated_damage": threat["estimated_damage"],
                    "potentially_lethal": threat["potentially_lethal"],
                }
        return best

    def _threat_worth_defending(
        self, enemies: List[Dict[str, Any]], player_hp: int
    ) -> WorstThreat:
        """The charge the tactical state should be built around.

        The soonest charge and the soonest DEFENSIBLE charge are different
        enemies whenever a harmless blow lands before a dangerous one, because
        the window `_defense_lands_in_time` describes is a range with a floor:
        a hit arriving sooner than a Dodge takes to resolve cannot be answered
        at all. Handing the scorer that hit reports `in_defensive_window` False
        for a fight in which a lethal blow was squarely inside the window, and
        `estimated_damage` and `incoming_lethal` then describe the wrong enemy
        as well. Measured, not reasoned: a gnat at 2 beats beside a lethal ogre
        at 6 scored Dodge 65 and answered with an attack, while the prompt's own
        alert block — which reads the enemies one at a time — correctly said
        "LETHAL … Dodge/Parry lands in time" on the very same input.

        So: the soonest charge a defence cast NOW would still be standing for,
        and only when none qualifies does the most pressing charge overall stand
        in. That fallback is what keeps `estimated_damage` honest in the common
        case where nothing is defensible and the state exists only to describe
        what is about to land.
        """
        defensible = [
            e
            for e in enemies
            if _defense_lands_in_time(_incoming_beats(e.get("move_in_process")))
        ]
        # `_worst_incoming_threat` on the filtered list, rather than a second
        # selection loop: the soonest-then-lethal tie-break is identical, and
        # the two must not be able to disagree about which of two simultaneous
        # charges matters more.
        return self._worst_incoming_threat(defensible or enemies, player_hp)

    @staticmethod
    def _rank_enemies(
        enemies: List[Dict[str, Any]], player_hp: int
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """Rank enemies by threat, highest priority first.

        Returns ``(priority, hp_pct, enemy)`` tuples sorted by that key, where a
        LOWER priority number is more urgent: (0) incoming lethal charge,
        (1) incoming non-lethal charge, (2) below `_FINISHABLE_HP_PCT` — finish
        them off, (3) everything else.

        HP% is the second sort key at EVERY tier, not only at tier 2, so tier-3
        enemies come out weakest-first as well; wire order breaks ties within a
        tier and nothing more. Tier 2 is therefore not "the tier sorted by HP"
        but "the tier that outranks tier 3 for being nearly dead".

        The single owner of this ranking. ``_build_target_priority`` renders it
        for the model and ``_priority_target_id`` picks a target from it; the
        two used to hold verbatim copies of this loop kept in step only by a
        docstring saying they matched, so diverging them would have made the
        priority list the model was shown disagree with the target actually
        filled into its suggestion.
        """
        scored = []
        for e in enemies:
            mip = e.get("move_in_process")
            bui = _incoming_beats(mip)
            lethal = (
                CombatStrategist._estimate_incoming_damage(mip, e, player_hp)[
                    "potentially_lethal"
                ]
                if bui is not None
                else False
            )
            hp_pct = (e.get("hp") or 0) / (e.get("max_hp") or 1)
            # `_IMMINENT_CHARGE_BEATS`, not either defensive predicate: this
            # ranks WHO TO HIT, and whether a Dodge would arrive in time has no
            # bearing on that. An enemy whose blow lands next beat is
            # unavoidable AND the most urgent thing on the field, so the bound
            # is one-sided — everything from zero beats up to the threshold.
            imminent = bui is not None and bui <= _IMMINENT_CHARGE_BEATS

            priority = (
                0
                if (lethal and imminent)
                else 1 if imminent else 2 if hp_pct < _FINISHABLE_HP_PCT else 3
            )
            scored.append((priority, hp_pct, e))

        # Stable sort: enemies tied on (priority, hp_pct) keep wire order, which
        # is what _priority_target_id's first-wins tie-break used to do.
        scored.sort(key=lambda x: (x[0], x[1]))
        return scored

    def _build_target_priority(
        self, enemies: List[Dict[str, Any]], player_hp: int
    ) -> str:
        """Render the enemy threat ranking for the prompt when several are present."""
        lines = ["Target Priority (highest → lowest):"]
        for rank, (priority, hp_pct, e) in enumerate(
            self._rank_enemies(enemies, player_hp), 1
        ):
            reason = (
                "incoming LETHAL charge"
                if priority == 0
                else (
                    "incoming charge"
                    if priority == 1
                    else (
                        f"low HP ({int(hp_pct * 100)}%)"
                        if priority == 2
                        else "standard threat"
                    )
                )
            )
            lines.append(f"  {rank}. {e.get('name')} (ID: {e.get('id')}) — {reason}")
        return "\n".join(lines) + "\n"

    def _priority_target_id(
        self, enemies: List[Dict[str, Any]], player_hp: int
    ) -> Optional[str]:
        """Return the ID of the highest-priority enemy, per `_rank_enemies`."""
        ranked = self._rank_enemies(enemies, player_hp)
        return ranked[0][2].get("id") if ranked else None

    def _ensure_target_ids(
        self, suggestions: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> None:
        """
        Ensure targeted moves resolve to a valid, in-range target_id.

        Returns nothing on purpose: the whole contract is the in-place rewrite
        of ``suggestions`` at the end of this method, which both callers rely
        on because they have already sliced the list they hand in.

        Each move's own `viable_targets` (already range-filtered by
        ApiCombatAdapter._get_available_targets, using that move's mvrange /
        get_effective_range_max) is the sole source of truth for who it can hit.
        A missing target_id — or one that isn't among that move's viable
        targets (e.g. an LLM hallucination) — is replaced with the
        highest-priority target drawn from that move's own viable set, never
        from the global enemy list. Fixes issue #122 ("Tactical Advisor
        targets far enemies"): previously a missing target_id was auto-filled
        from the highest-priority enemy across the WHOLE fight, which could
        be out of range for the specific move being suggested.

        A targeted move with zero viable targets is dropped from the results
        entirely — a move that cannot reach anyone should never be suggested.
        """
        # Kept as an ORDERED list, not an id->enemy dict: the per-move scoping
        # below has to preserve wire order for _rank_enemies' tie-break.
        enemies_in_order = [
            e for e in context.get("enemies", []) if isinstance(e, dict)
        ]
        # Through `_player_vitals` like every other read of this field: the
        # inline version here applied its own `or 1` where that helper applies
        # `or 0`, so the same absent-HP payload was worth two different numbers
        # depending on which path reached it.
        player_hp = _player_vitals(context.get("player") or {}).hp
        moves_by_name = {
            m.get("name"): m
            for m in context.get("available_moves", [])
            if isinstance(m, dict)
        }

        kept: List[Dict[str, Any]] = []
        for s in suggestions:
            move = moves_by_name.get(s.get("move_name"))

            if move is None or not move.get("targeted"):
                kept.append(s)
                continue

            viable_targets = move.get("viable_targets") or []
            viable_ids = {
                t.get("id")
                for t in viable_targets
                if isinstance(t, dict) and t.get("id")
            }

            if not viable_ids:
                # Targeted move with nothing in range — cannot be suggested at all.
                logger.debug(
                    "Dropping suggestion for '%s' — no viable target in range",
                    s.get("move_name"),
                )
                continue

            if s.get("target_id") not in viable_ids:
                # Rank only the enemies THIS move can actually reach — not every
                # enemy in the fight.
                # Filter `enemies` IN ORDER rather than iterating `viable_ids`:
                # that is a set, so its iteration order varies between processes
                # (string hashing is salted per interpreter), and _rank_enemies'
                # stable sort would then break ties differently from run to run
                # — contradicting the "keep wire order" tie-break it documents.
                scoped_enemies = [
                    e for e in enemies_in_order if e.get("id") in viable_ids
                ]
                if scoped_enemies:
                    new_target_id = self._priority_target_id(scoped_enemies, player_hp)
                else:
                    # No richer enemy data available to rank by — fall back to the
                    # nearest of the move's own viable targets. Same dict guard as
                    # viable_ids above, in case a non-dict entry ever slips through.
                    dict_targets = [t for t in viable_targets if isinstance(t, dict)]
                    new_target_id = (
                        min(dict_targets, key=lambda t: t.get("distance", 0)).get("id")
                        if dict_targets
                        else None
                    )
                logger.debug(
                    "Resolving target_id for '%s' to in-range target %s",
                    s.get("move_name"),
                    new_target_id,
                )
                s["target_id"] = new_target_id

            kept.append(s)

        suggestions[:] = kept

    def _extract_names(self, items: List[Any]) -> List[str]:
        """Extract 'name' from a list of objects or dicts."""
        extracted = []
        for item in items:
            if not item:
                continue
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    extracted.append(str(name))
            else:
                extracted.append(str(item))
        return extracted
