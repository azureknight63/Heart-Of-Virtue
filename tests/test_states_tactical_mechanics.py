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
"""
import inspect
import re

import pytest

import src.states as states
from ai.combat_strategist import _STATUS_TACTICAL_NOTES


# Round stats: every percentage in a summary lands on an exact integer, so a
# mismatch is a real disagreement and never a rounding artefact.
_BASE = 100

# Stat word as written in a summary -> the State attribute that carries it.
_STAT_ATTR = {
    "finesse": "add_fin",
    "protection": "add_protection",
    "speed": "add_speed",
    "strength": "add_str",
    "faith": "add_faith",
    "charisma": "add_charisma",
    "endurance": "add_endurance",
}

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


@pytest.mark.parametrize("name,state", _ANNOTATED, ids=_ANNOTATED_IDS)
def test_quoted_percentages_match_the_applied_modifier(name, state):
    """Forward direction: the text cannot claim a modifier the state does not apply."""
    for sign, value, stat in _PCT_TOKEN.findall(state.tactical_mechanics):
        attr = _STAT_ATTR.get(stat)
        if attr is None:
            continue  # a non-stat percentage (e.g. a proc chance)
        expected = int(_BASE * int(value) / 100)
        if sign != "+":
            expected = -expected
        actual = getattr(state, attr, 0)
        assert actual == expected, (
            f"{name}: summary says {sign}{value}% {stat} "
            f"(= {expected} against a {_BASE}-point stat) but {attr} is {actual}"
        )


@pytest.mark.parametrize("name,state", _ANNOTATED, ids=_ANNOTATED_IDS)
def test_quoted_flat_modifiers_match_the_applied_modifier(name, state):
    """Same, for the summaries that quote flat points rather than percentages."""
    text = state.tactical_mechanics
    for sign, value, stat in _FLAT_TOKEN.findall(text):
        attr = _STAT_ATTR.get(stat)
        if attr is None:
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


@pytest.mark.parametrize("name,state", _ANNOTATED, ids=_ANNOTATED_IDS)
def test_every_applied_modifier_is_named_in_the_summary(name, state):
    """Reverse direction: the text cannot silently omit a modifier.

    This is the half that would have caught the old hand-copy losing Resonant's
    finesse penalty from its enemy-perspective row.
    """
    text = state.tactical_mechanics.lower()
    for stat, attr in _STAT_ATTR.items():
        if getattr(state, attr, 0):
            assert stat in text, (
                f"{name}: applies {attr}={getattr(state, attr)} but its summary "
                f"never mentions '{stat}' — {state.tactical_mechanics!r}"
            )


@pytest.mark.parametrize("name,state", _ANNOTATED, ids=_ANNOTATED_IDS)
def test_quoted_tick_interval_matches_execute_on(name, state):
    """The rate the model is told must be the rate ``effect()`` actually runs at."""
    quoted = _TICK_TOKEN.findall(state.tactical_mechanics)
    execute_on = getattr(state, "execute_on", None)

    if execute_on is None:
        # No gate: effect() runs every beat, or the state has no periodic
        # effect at all. Either way it must not advertise an interval.
        assert not quoted, (
            f"{name}: summary quotes a {quoted[0]}-beat interval but the state "
            "has no execute_on gate"
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
