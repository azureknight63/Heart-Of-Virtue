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
    """Every ``State`` subclass whose ``__init__`` takes only a target."""
    found = []
    for name, obj in vars(states).items():
        if not (isinstance(obj, type) and issubclass(obj, states.State)):
            continue
        if obj is states.State:
            continue
        params = list(inspect.signature(obj.__init__).parameters)
        if params == ["self", "target"]:
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
