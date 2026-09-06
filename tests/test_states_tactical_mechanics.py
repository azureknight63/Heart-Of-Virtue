"""Guard: a State's ``tactical_mechanics`` text must match what it applies.

``tactical_mechanics`` is the terse mechanical summary the engine hands to the
combat LLM prompt (``StateEffectSerializer.serialize_state`` puts it on the
wire; ``CombatStrategist._format_status_effects`` renders it). It exists
because ai/combat_strategist.py used to keep a hand-typed copy of these numbers
in a module constant, and that copy had already gone stale in three places:
it told the model Poisoned ticks every beat when ``_EXECUTE_ON`` is 5, that
Enflamed ticks every 3 beats when it burns every single one, and that Slimed
drains fatigue, which it has never done.

Moving the text next to the code removes the *distance* that caused that drift;
these tests remove the possibility. Each state is built against a target with
round 100-point stats so every percentage lands on an exact integer, and then:

  * every percentage the text quotes must equal the ``add_*`` delta actually
    assigned (forward direction — the text cannot overstate);
  * every non-zero ``add_*`` the state assigns must be named in the text
    (reverse direction — the text cannot omit, which is how the old copy lost
    Resonant's finesse penalty);
  * the tick interval the text quotes must equal ``execute_on`` (or, for a
    state with no gate, the text must say "every beat").

Retune a multiplier in src/states.py without updating its summary and one of
these fails.

Every check runs TWICE: once on a freshly applied state, and once on one that
has been re-applied through ``compound()``. The second pass is not symmetry for
its own sake. ``tactical_mechanics`` was originally a plain string rendered in
``__init__``, while ``Slimed``, ``Petrified`` and ``Fervent`` all deepen an
``add_*`` in ``compound()`` — so a state that had been re-applied went on
quoting its FIRST application's numbers to the combat prompt for the rest of the
fight. Building only fresh instances is exactly why nothing caught it.

The compound pass runs the REAL ``functions.refresh_stat_bonuses``. That is not
a detail of the fixture: it is the call that writes a state's ``add_*`` onto
``target.finesse`` and friends, and so it is the reason the SECOND
``compound()`` scales its extra step by an already-reduced stat. This module
used to mock it out, which left every compound check measuring arithmetic no
live combat performs — they passed green against a renderer that was quoting
the combat prompt numbers the engine had never applied.
"""
import contextlib
import inspect
import re
from unittest import mock

import pytest

import src.functions as functions
import src.states as states
from ai.combat_strategist import _STATUS_TACTICAL_NOTES


# Round stats: every percentage in a summary lands on an exact integer, so a
# mismatch is a real disagreement and never a rounding artefact.
_BASE = 100

# Stat word as written in a summary -> the State attribute that carries it.
# This is a SPELLING table only: it says how a stat is written in prose, not
# which stats get checked. The checked set is derived per state from the
# ``add_*`` attributes the built instance actually carries (see
# ``_applied_add_attrs``), because a hand-maintained checklist is exactly what
# went stale before -- ``add_maxfatigue`` (src/states.py, ``Clean``) was assigned
# by a real state and named in no table, so fatigue claims were the one class of
# claim this guard could not check, and "Slimed drains fatigue, which it has
# never done" is one of the three drifts the module docstring cites.
_STAT_ATTR = {
    "finesse": "add_fin",
    "protection": "add_protection",
    "speed": "add_speed",
    "strength": "add_str",
    "faith": "add_faith",
    "charisma": "add_charisma",
    "endurance": "add_endurance",
    "fatigue": "add_maxfatigue",
}

_ATTR_STAT = {attr: word for word, attr in _STAT_ATTR.items()}
assert len(_ATTR_STAT) == len(_STAT_ATTR), "two stat words share one attribute"

# Nouns that legitimately follow a signed number without naming a stat. A word
# in neither this set nor _STAT_ATTR FAILS rather than being skipped: silently
# ignoring an unrecognised word is how a summary could quote a stat this guard
# does not know about and still pass with nothing checked.
_NON_STAT_WORDS = frozenset(
    {
        "prep",  # Staggered: "next move costs +5 prep beats"
        "beats",
        "chance",
        "stacks",
    }
)


def _applied_add_attrs(state):
    """Every ``add_*`` the built instance carries, zero-valued ones included.

    Derived from the instance rather than from ``_STAT_ATTR`` so a state that
    starts applying ``add_maxhp`` or ``add_damage`` is caught by
    ``test_every_applied_attribute_has_a_spelling`` instead of passing unchecked.
    """
    return sorted(a for a in vars(state) if a.startswith("add_"))


# The unicode MINUS SIGN the prompt text uses, plus the ASCII hyphen, so a
# summary written either way is parsed the same.
_SIGN = r"[+−-]"

_PCT_TOKEN = re.compile(rf"({_SIGN})(\d+)%\s+([a-z]+)")
_FLAT_TOKEN = re.compile(rf"({_SIGN})(\d+)\s+([a-z]+)")
_TICK_TOKEN = re.compile(r"every (\d+) beats?")


# Every primary stat carries the same round base, so a percentage of any of
# them lands on an exact integer and one denominator serves every check below.
# They used to split 100/20, which quietly meant a summary quoting a percentage
# of endurance, faith or charisma would have been checked against the wrong
# base; none does today, and now none can.
_STAT_FIELDS = (
    "strength",
    "finesse",
    "speed",
    "endurance",
    "charisma",
    "intelligence",
    "faith",
)


class _Target:
    """Minimal combatant with round stats, enough for any State's ``__init__``.

    Carries the ``*_base`` fields and resistance tables ``functions.reset_stats``
    reads, because the compound pass below runs the real
    ``functions.refresh_stat_bonuses`` rather than a stub of it.
    """

    name = "Test Target"
    in_combat = True

    def __init__(self):
        self.states = []
        self.hp = self.maxhp = self.maxhp_base = 1000
        self.fatigue = self.maxfatigue = self.maxfatigue_base = 1000
        for field in _STAT_FIELDS:
            setattr(self, field, _BASE)
            setattr(self, f"{field}_base", _BASE)
        self.protection = self.protection_base = _BASE
        self.resistance = {}
        self.resistance_base = {}
        self.status_resistance = {}
        self.status_resistance_base = {}


def _state_classes():
    """Every ``State`` subclass constructible from a target alone.

    "Constructible from a target alone", not "whose signature is exactly
    ``(self, target)``". The stricter test read the same for a long time and
    then quietly stopped: ``Staggered`` gained an optional ``beats_max`` (so
    Disrupt can hold a target past a committed wind-up) and dropped out of
    every check in this module at once -- including the one that would have
    reported its missing summary. A default argument does not make a state
    less checkable, and a filter that treats it that way fails open on exactly
    the states somebody has just been editing.
    """
    found = []
    for name, obj in vars(states).items():
        if not (isinstance(obj, type) and issubclass(obj, states.State)):
            continue
        if obj is states.State:
            continue
        params = list(inspect.signature(obj.__init__).parameters.values())
        if [p.name for p in params[:2]] != ["self", "target"]:
            continue
        if any(p.default is inspect.Parameter.empty for p in params[2:]):
            continue
        found.append((name, obj))
    return sorted(found)


def _annotated_states():
    """Built instances of every state that declares a tactical summary."""
    built = []
    for name, cls in _state_classes():
        instance = cls(_Target())
        if instance.tactical_mechanics:
            built.append((name, instance))
    return built


_ANNOTATED = _annotated_states()
_ANNOTATED_IDS = [name for name, _ in _ANNOTATED]


def test_the_annotated_set_is_not_empty():
    """A refactor that silently dropped every summary would otherwise make the
    parametrized tests below vacuous — they would collect zero cases and pass."""
    assert len(_ANNOTATED) >= 10


def _check_quoted_percentages(name, state):
    for sign, value, stat in _PCT_TOKEN.findall(state.tactical_mechanics):
        attr = _STAT_ATTR.get(stat)
        if attr is None:
            assert stat in _NON_STAT_WORDS, (
                f"{name}: summary quotes {sign}{value}% {stat!r}, a word that is "
                f"neither a known stat nor a known non-stat noun. Add it to "
                f"_STAT_ATTR (with the add_* attribute it names) or to "
                f"_NON_STAT_WORDS -- {state.tactical_mechanics!r}"
            )
            continue
        expected = int(_BASE * int(value) / 100)
        if sign != "+":
            expected = -expected
        actual = getattr(state, attr, 0)
        assert actual == expected, (
            f"{name}: summary says {sign}{value}% {stat} "
            f"(= {expected} against a {_BASE}-point stat) but {attr} is {actual}"
        )


def _check_quoted_flat_modifiers(name, state):
    text = state.tactical_mechanics
    for sign, value, stat in _FLAT_TOKEN.findall(text):
        attr = _STAT_ATTR.get(stat)
        if attr is None:
            assert stat in _NON_STAT_WORDS, (
                f"{name}: summary quotes {sign}{value} {stat!r}, a word that is "
                f"neither a known stat nor a known non-stat noun. Add it to "
                f"_STAT_ATTR or to _NON_STAT_WORDS -- {text!r}"
            )
            continue
        # A percentage token is also a flat-token match once the '%' is passed
        # over; skip anything the percentage pass already owns.
        if f"{sign}{value}% {stat}" in text:
            continue
        expected = int(value) if sign == "+" else -int(value)
        actual = getattr(state, attr, 0)
        assert actual == expected, (
            f"{name}: summary says {sign}{value} {stat} but {attr} is {actual}"
        )


def _check_every_modifier_is_named(name, state):
    text = state.tactical_mechanics.lower()
    for attr in _applied_add_attrs(state):
        if not getattr(state, attr):
            continue
        stat = _ATTR_STAT[attr]  # spelling guaranteed by the test below
        assert stat in text, (
            f"{name}: applies {attr}={getattr(state, attr)} but its summary "
            f"never mentions '{stat}' — {state.tactical_mechanics!r}"
        )


def _check_tick_interval(name, state):
    quoted = _TICK_TOKEN.findall(state.tactical_mechanics)
    execute_on = getattr(state, "execute_on", None)

    if not execute_on:
        # No interval. Either the attribute is absent, or it is 0 -- which real
        # states do set (src/states.py, ``Clean``) and which means "every beat",
        # since ``tick % 0`` is not a gate any effect() can evaluate. Testing
        # ``is None`` sent the 0 case down the branch below, where it demanded a
        # quoted interval equal to 0: unsatisfiable, because _TICK_TOKEN would
        # have to match "every 0 beats".
        assert not quoted, (
            f"{name}: summary quotes a {quoted[0]}-beat interval but the state "
            f"has no execute_on gate (execute_on={execute_on!r}; 0 and absent "
            "both mean every beat)"
        )
        return

    assert quoted, (
        f"{name}: ticks every {execute_on} beats but its summary quotes no "
        f"interval — {state.tactical_mechanics!r}"
    )
    for value in quoted:
        assert int(value) == execute_on, (
            f"{name}: summary says every {value} beats, execute_on is {execute_on}"
        )


@pytest.mark.parametrize("name,state", _ANNOTATED, ids=_ANNOTATED_IDS)
def test_quoted_percentages_match_the_applied_modifier(name, state):
    """Forward direction: the text cannot claim a modifier the state does not apply."""
    _check_quoted_percentages(name, state)


@pytest.mark.parametrize("name,state", _ANNOTATED, ids=_ANNOTATED_IDS)
def test_quoted_flat_modifiers_match_the_applied_modifier(name, state):
    """Same, for the summaries that quote flat points rather than percentages."""
    _check_quoted_flat_modifiers(name, state)


@pytest.mark.parametrize("name,state", _ANNOTATED, ids=_ANNOTATED_IDS)
def test_every_applied_attribute_has_a_spelling(name, state):
    """Fail-closed half of the reverse direction.

    ``test_every_applied_modifier_is_named_in_the_summary`` can only check the
    ``add_*`` attributes it knows how to spell. Before this, an unmapped one --
    ``add_maxfatigue`` was already such a case -- was simply not iterated, so a
    state could apply it and say nothing, and the guard would report success.
    A new ``add_*`` now fails here until someone gives it a word.
    """
    unmapped = [a for a in _applied_add_attrs(state) if a not in _ATTR_STAT]
    assert not unmapped, (
        f"{name}: applies {unmapped} with no entry in _STAT_ATTR, so the "
        "summary-omission check cannot see them. Add the word each one is "
        "written as in prose."
    )


@pytest.mark.parametrize("name,state", _ANNOTATED, ids=_ANNOTATED_IDS)
def test_every_applied_modifier_is_named_in_the_summary(name, state):
    """Reverse direction: the text cannot silently omit a modifier.

    This is the half that would have caught the old hand-copy losing Resonant's
    finesse penalty from its enemy-perspective row.
    """
    _check_every_modifier_is_named(name, state)


@pytest.mark.parametrize("name,state", _ANNOTATED, ids=_ANNOTATED_IDS)
def test_quoted_tick_interval_matches_execute_on(name, state):
    """The rate the model is told must be the rate ``effect()`` actually runs at."""
    _check_tick_interval(name, state)


# ---------------------------------------------------------------------------
# The same four checks, against a state that has been re-applied
# ---------------------------------------------------------------------------

_COMPOUND_APPLICATIONS = 2


@contextlib.contextmanager
def _quiet_narration():
    """Silence a state's own ``cprint``. Nothing else is stubbed.

    ``functions.refresh_stat_bonuses`` runs for real, and ``_Target`` is built
    to satisfy it. It used to be mocked out alongside ``cprint`` on the grounds
    that it was not under test — but it is the single call that decides what a
    second ``compound()`` multiplies by, so stubbing it removed exactly the
    divergence these compound checks exist to catch.
    """
    with mock.patch.object(states, "cprint"):
        yield


def _compoundable():
    """Annotated states that deepen themselves when re-applied."""
    found = []
    for name, cls in _state_classes():
        instance = cls(_Target())
        if not instance.tactical_mechanics:
            continue
        if not getattr(instance, "compounding", False):
            continue
        if not callable(getattr(cls, "compound", None)):
            continue
        found.append((name, cls))
    return found


_COMPOUNDABLE = _compoundable()
_COMPOUNDABLE_IDS = [name for name, _ in _COMPOUNDABLE]


def _compounded(cls, times=_COMPOUND_APPLICATIONS):
    """One application then ``times`` re-applications, the way the engine does it.

    Mirrors ``functions.add_state``: the state joins ``target.states`` and
    ``refresh_stat_bonuses`` writes its ``add_*`` onto the target BEFORE any
    re-application, because ``compound()`` scales its extra step by the target's
    current stat rather than by its base.
    """
    target = _Target()
    state = cls(target)
    with _quiet_narration():
        target.states.append(state)
        functions.refresh_stat_bonuses(target)
        for _ in range(times):
            state.compound(target)
    return state


def _add_snapshot(state):
    """Every ``add_*`` the state carries right now, as a comparable mapping."""
    return {attr: getattr(state, attr) for attr in _applied_add_attrs(state)}


def test_the_compoundable_set_is_not_empty():
    """Without this the parametrized cases below would collect nothing and pass."""
    assert len(_COMPOUNDABLE) >= 3


@pytest.mark.parametrize("name,cls", _COMPOUNDABLE, ids=_COMPOUNDABLE_IDS)
def test_a_compounded_state_still_reports_what_it_applies(name, cls):
    """All four checks again, after the state has been re-applied twice.

    ``compound()`` is the one place a state's modifiers change after
    construction, so it is the one place a summary rendered at construction
    goes stale — and, because ``compound()`` scales its extra step by the
    holder's CURRENT stat rather than the base, the one place a summary
    ACCUMULATED from the class fractions goes wrong even while it moves. A
    twice-compounded ``Petrified`` summed to −40% finesse and −55% speed
    against the −35 and −46 the engine applied, and to +45% protection
    against +50: penalties reading worse than they were, bonuses weaker, all
    of it quoted to the combat prompt as fact. That divergence only exists
    while ``refresh_stat_bonuses`` runs, which is why ``_quiet_narration``
    no longer stubs it.
    """
    state = _compounded(cls)
    _check_quoted_percentages(name, state)
    _check_quoted_flat_modifiers(name, state)
    _check_every_modifier_is_named(name, state)
    _check_tick_interval(name, state)


def _states_whose_compound_moves_a_modifier():
    """Compoundable states where re-application really does change an ``add_*``.

    Derived rather than named. ``Enflamed`` and ``Poisoned`` compound too, but
    by adding a stack or refreshing a clock, and their summaries are right to
    stay put. Writing down the three that move a modifier today would leave the
    fourth unguarded on the day someone adds it.
    """
    found = []
    for name, cls in _COMPOUNDABLE:
        if _add_snapshot(cls(_Target())) != _add_snapshot(_compounded(cls)):
            found.append((name, cls))
    return found


_DEEPENING = _states_whose_compound_moves_a_modifier()
_DEEPENING_IDS = [name for name, _ in _DEEPENING]


def test_the_deepening_set_is_not_empty():
    """A renderer frozen at construction would empty this set, not fail on it."""
    assert len(_DEEPENING) >= 3


@pytest.mark.parametrize("name,cls", _DEEPENING, ids=_DEEPENING_IDS)
def test_deepening_a_modifier_actually_moves_the_summary(name, cls):
    """Guards against the checks above passing vacuously.

    A state whose ``compound()`` really does change an ``add_*`` but reports the
    same text before and after has a summary frozen at construction, and the
    checks above would happily confirm a stale number matches a stale number.
    """
    fresh = cls(_Target()).tactical_mechanics
    deepened = _compounded(cls).tactical_mechanics
    assert deepened != fresh, (
        f"{name}.compound() deepens a modifier but tactical_mechanics still "
        f"reads {fresh!r} — the combat prompt is being handed the first "
        "application's numbers."
    )


def test_every_state_the_strategist_annotates_carries_its_own_mechanics():
    """The strategist keeps only the perspective notes; the numbers come from here.

    Closes the loop from the adapter's side: an entry in
    ``_STATUS_TACTICAL_NOTES`` with no engine-side summary would render as bare
    advice with no mechanics at all.
    """
    annotated = {name for name, _ in _ANNOTATED}
    by_state_name = {
        instance.name for _, instance in _ANNOTATED if instance.name
    }
    missing = [
        n
        for n in _STATUS_TACTICAL_NOTES
        if n not in annotated and n not in by_state_name
    ]
    assert not missing, f"no tactical_mechanics on src/states.py for: {missing}"


def test_a_combat_state_that_applies_modifiers_declares_its_mechanics():
    """The reverse of the test above, and the direction a new effect breaks in.

    Every other check in this module runs over ``_ANNOTATED`` — the states that
    already declare a summary. A new status effect that declares none is caught
    by none of them: it is silently excluded from the whole module and reaches
    the combat prompt as a bare name with no mechanics attached.

    The exemptions are derived, not listed. A state that never enters combat
    (``combat=False``) never reaches the prompt, and a state that assigns no
    non-zero ``add_*`` has no modifier to state — ``Death``, ``PhoenixRevive``
    and ``WarCryStunned`` are all of that kind.
    """
    silent = []
    for name, cls in _state_classes():
        state = cls(_Target())
        if state.tactical_mechanics or not state.combat:
            continue
        applied = {
            attr: getattr(state, attr)
            for attr in _applied_add_attrs(state)
            if getattr(state, attr)
        }
        if applied:
            silent.append(f"{name} applies {applied}")
    assert not silent, (
        "combat states that move a stat but tell the combat prompt nothing: "
        f"{silent}. Give each one a tactical_mechanics summary."
    )


def test_the_strategist_table_holds_only_perspective_notes():
    """Regression: the mechanical column used to live in the adapter as well."""
    for name, entry in _STATUS_TACTICAL_NOTES.items():
        assert set(entry) == {"player_note", "enemy_note"}, name


# ---------------------------------------------------------------------------
# What the summary reports when there is no stat to take a fraction OF
# ---------------------------------------------------------------------------


def _states_that_render_live():
    """States whose summary is built at read time rather than at construction.

    Derived from the override itself, not named: these are exactly the states
    that compute their text instead of repeating the static string their
    constructor was handed.
    """
    return [
        (name, cls)
        for name, cls in _state_classes()
        if cls._render_tactical_mechanics
        is not states.State._render_tactical_mechanics
    ]


def _states_that_report_percentages():
    """The subset whose live text is a FRACTION of a captured base stat.

    Not every live renderer is one. ``Dodging``'s grant is an absolute number
    of finesse points computed from a decay curve, so it has no base to divide
    by and captures none -- and the two checks below, which are about what
    ``_applied_pct`` answers when the base is 0 or missing, have nothing to
    say about it. Parametrizing them over every live renderer made them fail
    on Dodging for the right reason (their premise genuinely does not hold)
    and the wrong subject.

    Derived by asking whether the override reaches for ``_applied_pct``, which
    is the thing under test, rather than by listing the states that do. A
    state that starts reporting percentages joins this set the moment it calls
    the helper -- which is the direction that matters, since the risk is a
    percentage nobody checks, not a flat number checked twice.
    """
    return [
        (name, cls)
        for name, cls in _states_that_render_live()
        if "_applied_pct" in cls._render_tactical_mechanics.__code__.co_names
    ]


_LIVE = _states_that_render_live()
_LIVE_IDS = [name for name, _ in _LIVE]
_PCT_LIVE = _states_that_report_percentages()
_PCT_LIVE_IDS = [name for name, _ in _PCT_LIVE]


def test_the_live_rendering_set_is_not_empty():
    """The two checks below are parametrized over it; an empty set passes both."""
    assert len(_LIVE) >= 3


def test_the_percentage_reporting_subset_is_not_empty():
    """Same non-vacuity guard, for the narrower set.

    And a check that the two really are different sets: if ``_PCT_LIVE`` ever
    equals ``_LIVE`` again the split has stopped doing anything, and if it
    empties out the two checks it feeds collect nothing and pass.
    """
    assert len(_PCT_LIVE) >= 3
    assert len(_PCT_LIVE) < len(_LIVE), (
        "every live renderer now reports percentages, so the _PCT_LIVE split "
        "is dead weight -- fold it back into _LIVE"
    )


def _zero_stat_target():
    """A holder with no stat to take a fraction of.

    ``_Target`` pins every stat at 100 so percentages land on exact integers,
    which is right for every other check here and is also why nothing ever
    exercised the zero branch.
    """
    target = _Target()
    for field in _STAT_FIELDS:
        setattr(target, field, 0)
        setattr(target, f"{field}_base", 0)
    target.protection = target.protection_base = 0
    return target


@pytest.mark.parametrize("name,cls", _PCT_LIVE, ids=_PCT_LIVE_IDS)
def test_a_modifier_taken_from_a_zero_stat_is_reported_as_zero(name, cls):
    """``int(0 * fraction)`` is 0, and the summary has to say so.

    The renderer used to answer a zero base with the NOMINAL class fraction,
    on the reasoning that a state with nothing to divide by is better served
    by the nominal than by an exception. But the two cases it lumped together
    are not alike. A missing ``_base_*`` really does leave nothing to say. A
    captured base of 0 says something exact: the engine multiplied 0 by the
    fraction, put 0 on the books, and the combat prompt was told "+25%
    protection" for a modifier provably worth nothing.

    That is the same class of defect as the stale summary this whole module
    exists to prevent -- a number in the prompt the engine never applied --
    and it sat inside the property written to end them.
    """
    with _quiet_narration():
        state = cls(_zero_stat_target())

    quoted = _PCT_TOKEN.findall(state.tactical_mechanics)
    assert quoted, (
        f"{name} quotes no percentage against a zero-stat holder, so this case "
        f"checks nothing -- {state.tactical_mechanics!r}"
    )
    for sign, value, stat in quoted:
        attr = _STAT_ATTR[stat]
        # Assert the premise before the conclusion: if the fixture ever stops
        # producing a zero delta, this must fail loudly rather than confirm
        # "0%" against a modifier that is no longer 0.
        assert getattr(state, attr, 0) == 0, (
            f"{name}: fixture no longer zeroes {stat} -- {attr} is "
            f"{getattr(state, attr, 0)}, so the zero branch is not under test"
        )
        assert int(value) == 0, (
            f"{name}: {attr} is 0 against a zero {stat}, so the engine applied "
            f"nothing -- but the summary hands the combat prompt "
            f"{sign}{value}% {stat}"
        )


@pytest.mark.parametrize("name,cls", _PCT_LIVE, ids=_PCT_LIVE_IDS)
def test_a_state_missing_its_captured_bases_still_reports_the_nominal(name, cls):
    """The other half of the split, and the reason it needs a sentinel.

    A state unpickled from a save written before ``_capture_bases`` existed
    carries no ``_base_*`` at all. There is genuinely no delta to divide, so
    the nominal is the best answer available -- and it must stay the answer,
    or the fix above would have traded a wrong number for a different wrong
    number on every old save.

    Checked by equality against the freshly built summary rather than against
    a spelled-out string: ``_Target``'s stats are round, so the applied
    fraction and the nominal fraction are the same number, and the fallback
    has to reproduce the live rendering exactly.
    """
    with _quiet_narration():
        state = cls(_Target())
    rendered_live = state.tactical_mechanics

    captured = [attr for attr in vars(state) if attr.startswith("_base_")]
    assert captured, (
        f"{name} captures no base stat, so the old-save path is not under test"
    )
    for attr in captured:
        delattr(state, attr)

    assert state.tactical_mechanics == rendered_live, (
        f"{name}: with its captured bases gone the summary reads "
        f"{state.tactical_mechanics!r}, not the {rendered_live!r} an old save "
        "should still render"
    )


def test_every_combat_state_with_mechanics_carries_a_perspective_note():
    """The mirror of ``..._the_strategist_annotates_carries_its_own_mechanics``.

    That test walks the table and demands engine-side mechanics for each entry.
    This one walks the engine and demands a table entry for each combat state
    that has mechanics to explain. Without it, a new status effect can declare
    a perfect summary and still reach the model as bare numbers with no
    statement of what they IMPLY: ``_format_status_effects`` renders the
    mechanics and simply omits the ``->`` clause when the lookup misses, so
    nothing anywhere reports the gap.

    The exemption is derived, not listed: a state with ``combat=False`` never
    reaches a combat prompt, so it has no perspective to be written from. The
    lookup key is the state's runtime ``name``, because that is what
    ``StateEffectSerializer.serialize_state`` puts on the wire and what
    ``_STATUS_TACTICAL_NOTES.get`` is handed.
    """
    missing = [
        f"{cls_name} (wire name {instance.name!r})"
        for cls_name, instance in _ANNOTATED
        if instance.combat and instance.name not in _STATUS_TACTICAL_NOTES
    ]
    assert not missing, (
        "combat states that state their mechanics but have no perspective note "
        f"in ai/combat_strategist._STATUS_TACTICAL_NOTES: {missing}. The model "
        "is told what they do and not what to do about it."
    )


# ---------------------------------------------------------------------------
# One clock rule, not three copies of one clock rule
# ---------------------------------------------------------------------------


def _states_whose_compound_stretches_the_clock():
    """Compoundable states that re-apply by moving ``beats_max``.

    Derived, not listed. ``Enflamed`` compounds by adding a stack and topping
    ``beats_left`` back to an unchanged ceiling, and ``Fervent`` by adding a
    flat beat count; neither stretches, and neither should be dragged into a
    rule it does not follow. What is left is the set that does.

    Measured before-and-after on ONE instance. Comparing a fresh instance
    against a separately built compounded one would compare two independent
    ``random.randint`` durations and call the difference a stretch -- which
    swept in ``Fervent``, whose ceiling never moves.
    """
    found = []
    for name, cls in _COMPOUNDABLE:
        target = _Target()
        with _quiet_narration():
            state = cls(target)
            target.states.append(state)
            functions.refresh_stat_bonuses(target)
            before = state.beats_max
            state.compound(target)
        if state.beats_max != before:
            found.append((name, cls))
    return found


_STRETCHING = _states_whose_compound_stretches_the_clock()
_STRETCHING_IDS = [name for name, _ in _STRETCHING]


def test_the_stretching_set_is_not_empty():
    """Parametrized over it below; an empty set would pass vacuously."""
    assert len(_STRETCHING) >= 3


@pytest.mark.parametrize("name,cls", _STRETCHING, ids=_STRETCHING_IDS)
def test_a_re_application_stretches_both_clocks_by_the_shared_rule(name, cls):
    """Every stretching state must use ``State``'s constants, not its own copy.

    The expected values are computed from ``State._COMPOUND_DURATION_MULT`` and
    ``State._COMPOUND_REFRESH_DIVISOR`` deliberately -- read off the BASE class
    rather than off ``cls``. Reading them off ``cls`` would follow a state that
    had quietly re-declared its own private pair and confirm it against itself,
    which is exactly the shape this guard exists to prevent: the rule had one
    encoding, then three, and each copy was a separate place to retune and
    forget.

    This pins the SHAPE of the rule and its uniformity across the states that
    follow it, not the numbers. ``tests/test_states_coverage.py`` pins what
    ``_COMPOUND_DURATION_MULT`` actually is.
    """
    target = _Target()
    with _quiet_narration():
        state = cls(target)
        target.states.append(state)
        functions.refresh_stat_bonuses(target)

    # Run both clocks down before re-applying, the way ``State.process()`` does
    # on every beat. Without this the refresh term is INVISIBLE: a freshly
    # applied state has ``beats_left == beats_max``, so topping up by any
    # fraction of a larger ceiling saturates at that ceiling and every divisor
    # produces the same answer. A guard that skipped this step would confirm a
    # ``_COMPOUND_REFRESH_DIVISOR`` of 3, 4 or 40 equally happily -- which is
    # how the divisor came to be the one half of this rule nothing pinned.
    state.beats_left = state.beats_max // 3
    state.steps_left = state.steps_max // 3

    before = {
        "beats": (state.beats_max, state.beats_left),
        "steps": (state.steps_max, state.steps_left),
    }
    with _quiet_narration():
        state.compound(target)
    after = {
        "beats": (state.beats_max, state.beats_left),
        "steps": (state.steps_max, state.steps_left),
    }

    mult = states.State._COMPOUND_DURATION_MULT
    divisor = states.State._COMPOUND_REFRESH_DIVISOR

    for clock, (ceiling_before, left_before) in before.items():
        expected_ceiling = int(ceiling_before * mult)
        expected_left = min(
            left_before + int(expected_ceiling / divisor), expected_ceiling
        )
        assert after[clock] == (expected_ceiling, expected_left), (
            f"{name}: re-application moved the {clock} clock from "
            f"{(ceiling_before, left_before)} to {after[clock]}, but the rule "
            f"State declares (x{mult} ceiling, refresh by 1/{divisor} of it) "
            f"gives {(expected_ceiling, expected_left)}"
        )
