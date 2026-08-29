"""Re-application (stat-stacking) contract for `src/states.py`.

A state whose bonus is a percentage of one of the target's stats must not
derive that bonus from the *current* value of a stat it is itself modifying.
`functions.reset_stats` rebuilds `strength`/`finesse`/`speed`/`protection` as
``base + sum(add_* from items and active states)``, so an active instance of
the state is already baked into the number its own ``__init__``/``compound``
reads back.  Re-applying then feeds the bonus into itself: geometrically (and
without bound) for a ``compounding`` state, whose existing instance is kept and
``compound()``-ed, and toward the wrong fixed point for a non-compounding one,
whose instance is replaced wholesale by `functions.inflict`.

These tests pin three things:

1. the value of a *single* application, so a convergence fix cannot silently
   retune a buff or debuff;
2. the behaviour under repeated application -- exactly constant for the
   non-compounding states, and a *constant* (linear, non-accelerating)
   increment for the three states whose escalation is deliberate; and
3. an AST guard that fails when a future state is written with the offending
   shape, so the rule stops being half-enforced.
"""

import ast
import inspect
import pathlib
from unittest.mock import Mock

import pytest

import src.functions as functions
import src.states as states
from src.narration import capture_narration
from src.npc import NPC


STATES_PY = pathlib.Path(states.__file__)


@pytest.fixture
def dummy():
    """A real NPC with flat, round stats and no equipment.

    Round numbers keep the expected values below exact under ``int()``
    truncation; a real NPC (rather than a Mock) means `refresh_stat_bonuses`,
    `reset_stats` and `inflict` all run for real.
    """
    npc = NPC(
        name="StackingDummy",
        description="A patient target.",
        damage=1,
        aggro=0,
        exp_award=1,
        maxhp=500,
        protection=40,
        speed=40,
        finesse=40,
        strength=40,
        endurance=40,
    )
    npc.in_combat = True
    functions.refresh_stat_bonuses(npc)
    return npc


def apply_n(target, state_cls, times, **kwargs):
    """Inflict `state_cls` `times` times, refreshing stats like combat does."""
    for _ in range(times):
        with capture_narration():
            functions.inflict(state_cls(target, **kwargs), target, force=True)
            functions.refresh_stat_bonuses(target)
    active = [s for s in target.states if isinstance(s, state_cls)]
    assert len(active) == 1, "re-application must never stack duplicate instances"
    return active[0]


def bonus_trace(target, state_cls, times, bonus_attr, **kwargs):
    """Return the `bonus_attr` value after each of `times` applications."""
    trace = []
    for _ in range(times):
        with capture_narration():
            functions.inflict(state_cls(target, **kwargs), target, force=True)
            functions.refresh_stat_bonuses(target)
        active = [s for s in target.states if isinstance(s, state_cls)]
        trace.append(getattr(active[0], bonus_attr))
    return trace


# ---------------------------------------------------------------------------
# Single-application values -- these pin today's tuning. A fix for the stacking
# defect must not move them.
# ---------------------------------------------------------------------------

SINGLE_APPLICATION_BONUSES = {
    # state class -> {bonus attribute: value on a 40/40/40/40 target}
    states.Dodging: {"add_fin": 22},          # max(15, 42 - 40 // 2)
    states.Disoriented: {"add_fin": -12, "add_protection": -10},
    states.Resonant: {"add_fin": -10},
    states.Quarried: {"add_protection": -10},
    states.Slimed: {"add_fin": -8, "add_protection": -6},
    states.Petrified: {"add_fin": -8, "add_speed": -14, "add_protection": 10},
    states.Fervent: {"add_str": 12, "add_fin": 6},
    states.SecretPlansState: {"add_str": 12, "add_fin": 12, "add_speed": 12},
}


@pytest.mark.parametrize(
    "state_cls,expected",
    list(SINGLE_APPLICATION_BONUSES.items()),
    ids=lambda v: getattr(v, "__name__", ""),
)
def test_single_application_bonus_is_unchanged(dummy, state_cls, expected):
    state = apply_n(dummy, state_cls, 1)
    for attr, value in expected.items():
        assert getattr(state, attr) == value, (
            f"{state_cls.__name__}.{attr} retuned: "
            f"{getattr(state, attr)} != {value}"
        )


# ---------------------------------------------------------------------------
# Non-compounding states: re-application replaces the instance, so the bonus
# must be *identical* every time, not converge toward a different number.
# ---------------------------------------------------------------------------

NON_COMPOUNDING = [
    (states.Dodging, "add_fin"),
    (states.Disoriented, "add_fin"),
    (states.Disoriented, "add_protection"),
    (states.Resonant, "add_fin"),
    (states.Quarried, "add_protection"),
    (states.SecretPlansState, "add_str"),
    (states.SecretPlansState, "add_fin"),
    (states.SecretPlansState, "add_speed"),
]


@pytest.mark.parametrize(
    "state_cls,bonus_attr",
    NON_COMPOUNDING,
    ids=[f"{c.__name__}.{a}" for c, a in NON_COMPOUNDING],
)
def test_non_compounding_reapplication_is_idempotent(dummy, state_cls, bonus_attr):
    assert not state_cls(dummy).compounding, (
        f"{state_cls.__name__} is compounding -- it belongs in the "
        "linear-escalation tests below"
    )
    trace = bonus_trace(dummy, state_cls, 10, bonus_attr)
    assert len(set(trace)) == 1, (
        f"{state_cls.__name__}.{bonus_attr} drifted under re-application: {trace}"
    )


# ---------------------------------------------------------------------------
# Compounding states: escalation is intentional (`compounding=True`, "Worsens
# if reapplied"), but it must be *linear* -- a fixed fraction of the unafflicted
# stat per re-application -- not a fraction of the already-afflicted value,
# which compounds geometrically and without bound.
# ---------------------------------------------------------------------------

LINEAR_ESCALATION = [
    # state class, bonus attr, first application, per-re-application increment
    (states.Fervent, "add_str", 12, 6),        # 30% then +15% of base strength
    (states.Slimed, "add_fin", -8, -2),        # 20% then -5% of base finesse
    (states.Slimed, "add_protection", -6, -2),  # 15% then -5% of base protection
    (states.Petrified, "add_fin", -8, -4),     # 20% then -10% of base finesse
    (states.Petrified, "add_speed", -14, -4),  # 35% then -10% of base speed
    (states.Petrified, "add_protection", 10, 4),  # 25% then +10% of base protection
]


@pytest.mark.parametrize(
    "state_cls,bonus_attr,first,increment",
    LINEAR_ESCALATION,
    ids=[f"{c.__name__}.{a}" for c, a, _f, _i in LINEAR_ESCALATION],
)
def test_compounding_escalation_is_linear(dummy, state_cls, bonus_attr, first, increment):
    assert state_cls(dummy).compounding, (
        f"{state_cls.__name__} is not compounding -- escalation is not intended"
    )
    trace = bonus_trace(dummy, state_cls, 6, bonus_attr)
    expected = [first + increment * n for n in range(6)]
    assert trace == expected, (
        f"{state_cls.__name__}.{bonus_attr} did not escalate linearly: "
        f"{trace} != {expected}"
    )
    deltas = [b - a for a, b in zip(trace, trace[1:])]
    assert len(set(deltas)) == 1, (
        f"{state_cls.__name__}.{bonus_attr} increment accelerated: {deltas}"
    )


def test_fervent_strength_does_not_run_away(dummy):
    """The headline regression: Fervent's strength used to grow geometrically.

    Before the fix, eight re-applications on a 20-strength target produced
    +6, +9, +13, +17, +22, +28, +35, +43 strength -- ratio ~1.15 per cast, with
    no ceiling. The escalation itself is intended; the acceleration was not.
    """
    trace = bonus_trace(dummy, states.Fervent, 8, "add_str")
    assert trace == [12, 18, 24, 30, 36, 42, 48, 54]
    # Total growth stays proportional to the number of casts (linear), so the
    # final value can never exceed first-cast * number-of-casts.
    assert trace[-1] <= trace[0] * len(trace)


def test_petrified_protection_buff_does_not_run_away(dummy):
    """Petrified grants protection while it debuffs finesse/speed -- taken off
    the already-crusted protection that positive term grew geometrically."""
    trace = bonus_trace(dummy, states.Petrified, 8, "add_protection")
    deltas = {b - a for a, b in zip(trace, trace[1:])}
    assert deltas == {4}, trace


def test_secret_plans_recast_grants_no_free_stats(dummy):
    """Re-casting Secret Plans used to settle at +8 strength on a 20-strength
    target where a single cast granted +6 -- a free buff for spamming it."""
    baseline = dummy.strength
    apply_n(dummy, states.SecretPlansState, 1)
    single = dummy.strength
    apply_n(dummy, states.SecretPlansState, 9)
    assert dummy.strength == single
    assert single == baseline + 12


# ---------------------------------------------------------------------------
# The helper itself
# ---------------------------------------------------------------------------


def test_stat_without_state_bonus_excludes_only_its_own_class(dummy):
    disoriented = states.Disoriented(dummy)
    resonant = states.Resonant(dummy)
    dummy.states.extend([disoriented, resonant])
    functions.refresh_stat_bonuses(dummy)

    # finesse now carries both debuffs; the helper strips only the one asked for
    assert dummy.finesse == 40 + disoriented.add_fin + resonant.add_fin
    assert (
        states.stat_without_state_bonus(dummy, "finesse", "add_fin", states.Disoriented)
        == dummy.finesse - disoriented.add_fin
    )
    assert (
        states.stat_without_state_bonus(dummy, "finesse", "add_fin", states.Resonant)
        == dummy.finesse - resonant.add_fin
    )


def test_stat_without_state_bonus_tolerates_test_doubles():
    """States are constructed against Mocks all over the suite; the helper must
    degrade to a plain read rather than exploding on a non-iterable `states`."""
    mock = Mock()
    mock.finesse = 30
    assert states.stat_without_state_bonus(mock, "finesse", "add_fin", states.Dodging) == 30

    no_states = Mock(spec=["finesse"])
    no_states.finesse = 30
    assert (
        states.stat_without_state_bonus(no_states, "finesse", "add_fin", states.Dodging)
        == 30
    )

    non_numeric = Mock()
    non_numeric.finesse = "unset"
    assert (
        states.stat_without_state_bonus(non_numeric, "finesse", "add_fin", states.Dodging)
        == "unset"
    )


def test_stat_without_state_bonus_floors_at_zero(dummy):
    """A stat already clamped to 0 by someone else's stacked debuffs must not
    reconstruct to a negative 'clean' value and flip the sign of the next
    bonus. refresh_stat_bonuses clamps primary stats at 0, so subtracting a
    positive own-contribution from a clamped stat can go negative."""
    class _Buff(states.State):
        def __init__(self, target):
            super().__init__(name="Buff", target=target)
            self.add_fin = 10

    buff = _Buff(dummy)
    crusher = states.State(name="Crusher", target=dummy)
    crusher.add_fin = -9999
    dummy.states.extend([buff, crusher])
    functions.refresh_stat_bonuses(dummy)

    assert dummy.finesse == 0  # clamped
    assert states.stat_without_state_bonus(dummy, "finesse", "add_fin", _Buff) == 0


# ---------------------------------------------------------------------------
# Guard: no future state may reintroduce the shape.
# ---------------------------------------------------------------------------

#: Stats that `functions.refresh_stat_bonuses` rebuilds from base + add_*; a
#: bonus derived from any of these must go through `stat_without_state_bonus`.
GUARDED_STATS = {
    "strength",
    "finesse",
    "speed",
    "endurance",
    "charisma",
    "intelligence",
    "faith",
    "protection",
    "maxhp",
    "maxfatigue",
    "weight_tolerance",
}

#: (class name, method name) pairs allowed to read a guarded stat straight off
#: the target inside a method that also writes an `add_*` bonus.
#:
#: Empty on purpose. Add an entry ONLY for a bonus that provably cannot feed
#: back into itself -- e.g. one derived from a stat the state never modifies --
#: and say why here. Anything else belongs behind `stat_without_state_bonus`.
GUARD_EXEMPTIONS: set[tuple[str, str]] = set()


def _state_subclass_names():
    return {
        name
        for name, obj in vars(states).items()
        if inspect.isclass(obj) and issubclass(obj, states.State)
    }


def _find_violations():
    tree = ast.parse(STATES_PY.read_text(encoding="utf-8"))
    state_names = _state_subclass_names()
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
        if not bases & state_names:
            continue
        for method in node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            writes_bonus = any(
                isinstance(t, ast.Attribute)
                and isinstance(t.value, ast.Name)
                and t.value.id == "self"
                and t.attr.startswith("add_")
                for stmt in ast.walk(method)
                for t in (
                    stmt.targets
                    if isinstance(stmt, ast.Assign)
                    else [stmt.target] if isinstance(stmt, ast.AugAssign) else []
                )
            )
            if not writes_bonus or (node.name, method.name) in GUARD_EXEMPTIONS:
                continue
            for sub in ast.walk(method):
                if (
                    isinstance(sub, ast.Attribute)
                    and isinstance(sub.value, ast.Name)
                    and sub.value.id in ("target", "self")
                    and sub.attr in GUARDED_STATS
                ):
                    violations.append(
                        f"{node.name}.{method.name} (line {sub.lineno}) reads "
                        f"{sub.value.id}.{sub.attr} directly"
                    )
    return violations


def test_no_state_derives_a_bonus_from_the_unbased_stat():
    """Enumerate every State subclass in src/states.py and fail if any method
    that assigns an `add_*` bonus reads a guarded stat straight off the target.

    This is the rule the Dodging fix wrote down and only half-enforced:
    Fervent, Slimed, Petrified, Disoriented, Resonant, Quarried and
    SecretPlansState all still carried the shape afterwards.
    """
    violations = _find_violations()
    assert not violations, (
        "State bonuses must be derived via states.stat_without_state_bonus(), "
        "not from the live (already-bonused) stat:\n  " + "\n  ".join(violations)
    )


def test_guard_detects_the_shape_it_is_meant_to_catch():
    """Non-vacuity for the guard: the AST scan must actually fire on the shape
    (asserted against a synthetic module, so it stays true if states.py is
    clean)."""
    source = (
        "class Bad(State):\n"
        "    def __init__(self, target):\n"
        "        self.add_fin = int(target.finesse * 0.15)\n"
    )
    tree = ast.parse(source)
    found = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id == "target"
        and n.attr in GUARDED_STATS
    ]
    assert found, "the guard's matcher no longer recognizes the offending shape"
