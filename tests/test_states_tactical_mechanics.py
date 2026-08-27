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
"""
import contextlib
import inspect
import re
from unittest import mock

import pytest

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


class _Target:
    """Minimal combatant with round stats, enough for any State's ``__init__``."""

    name = "Test Target"
    in_combat = True
    hp = maxhp = 1000
    fatigue = maxfatigue = 1000
    finesse = protection = speed = strength = _BASE
    endurance = faith = charisma = intelligence = 20

    def __init__(self):
        self.states = []
        self.status_resistance = {}
        self.resistance = {}


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
def _quiet_engine():
    """``compound()`` narrates and refreshes stat bonuses; neither is under test.

    ``refresh_stat_bonuses`` in particular wants a full combatant (base stat
    and resistance tables), which ``_Target`` deliberately is not.
    """
    with mock.patch.object(states, "cprint"), mock.patch.object(
        states.functions, "refresh_stat_bonuses"
    ):
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
    target = _Target()
    state = cls(target)
    with _quiet_engine():
        for _ in range(times):
            state.compound(target)
    return state


def test_the_compoundable_set_is_not_empty():
    """Without this the parametrized cases below would collect nothing and pass."""
    assert len(_COMPOUNDABLE) >= 3


@pytest.mark.parametrize("name,cls", _COMPOUNDABLE, ids=_COMPOUNDABLE_IDS)
def test_a_compounded_state_still_reports_what_it_applies(name, cls):
    """All four checks again, after the state has been re-applied twice.

    ``compound()`` is the one place a state's modifiers change after
    construction, so it is the one place a summary rendered at construction
    goes stale.
    """
    state = _compounded(cls)
    _check_quoted_percentages(name, state)
    _check_quoted_flat_modifiers(name, state)
    _check_every_modifier_is_named(name, state)
    _check_tick_interval(name, state)


@pytest.mark.parametrize(
    "cls_name",
    ["Slimed", "Petrified", "Fervent"],
)
def test_deepening_a_modifier_actually_moves_the_summary(cls_name):
    """Guards against the checks above passing vacuously.

    These three are the states whose ``compound()`` really does change an
    ``add_*``. If one of them reports the same text before and after, the
    summary is frozen again and the test above would happily confirm a stale
    number matches a stale number.
    """
    cls = getattr(states, cls_name)
    fresh = cls(_Target()).tactical_mechanics
    deepened = _compounded(cls).tactical_mechanics
    assert deepened != fresh, (
        f"{cls_name}.compound() deepens a modifier but tactical_mechanics still "
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


def test_the_strategist_table_holds_only_perspective_notes():
    """Regression: the mechanical column used to live in the adapter as well."""
    for name, entry in _STATUS_TACTICAL_NOTES.items():
        assert set(entry) == {"player_note", "enemy_note"}, name
