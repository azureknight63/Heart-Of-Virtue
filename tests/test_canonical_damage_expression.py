"""One damage expression, stated once, proved unchanged.

``((power * resistance) - protection) * heat * random.uniform(0.8, 1.2)`` is
the engine's canonical damage line. It was written out by hand at roughly two
dozen call sites across ``src/moves/``, and ``damage_bounds`` -- the thing that
*predicts* it for the player before they commit -- wrote it out a
twenty-something'th time. That is the exact shape of the defect this area keeps
paying for: a preview that predicts one expression while ``execute()`` runs a
subtly different one shipped a 2x lie to the player twice (Jab, then Power
Strike), and neither was caught for months, because a copy that drifts is
indistinguishable from a copy that has not.

So the copies are gone: ``_base.resolve_damage`` is the line, and
``damage_bounds`` predicts by *calling it* with the variance roll pinned to
each end of its band rather than by restating it.

Term order is load-bearing in this codebase -- CLAUDE.md records that folding
``to_hit_chance``'s terms differently shifted the truncated result by a point
for ~0.7% of integer stat pairs -- so this module does not take "looks
equivalent" for an answer. It runs the pre-refactor expression, exactly as it
was written, against the helper over a wide grid of inputs and demands
bit-identical floats.
"""

import ast
import itertools
import math
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.moves._base import (  # noqa: E402
    DAMAGE_VARIANCE_MAX,
    DAMAGE_VARIANCE_MIN,
    damage_bounds,
    flat_arc_damage_bounds,
    resolve_damage,
    target_protection,
)
import src.moves as _moves_pkg  # noqa: E402


class _Target:
    """The two attributes the damage line reads off a defender."""

    def __init__(self, resistance, protection):
        self.resistance = {"slashing": resistance}
        self.protection = protection
        self.hp = 10 ** 9
        self.maxhp = 10 ** 9

    def is_alive(self):
        return True


class _Attacker:
    def __init__(self, heat):
        self.heat = heat


# ── the expression as it was written, before the extraction ─────────────────
#
# Copied verbatim from the pre-refactor sources rather than re-derived. The
# parenthesisation is the point: `(((power * resistance) - protection) * heat)
# * variance` is what every execute() ran, and any regrouping of it -- however
# algebraically identical -- is a different sequence of binary floating-point
# operations and therefore a different truncated integer for some inputs.


def _legacy_full_protection(power, resistance, protection, heat, variance):
    """``_base.standard_execute_attack`` and ~20 weapon-module copies."""
    return (((power * resistance) - protection) * heat) * variance


def _legacy_no_protection(power, resistance, heat, variance):
    """Pulverize (``power * res * heat * variance``) and Armor Pierce
    (``((power * res) * heat) * variance``) -- protection ignored outright."""
    return power * resistance * heat * variance


def _legacy_partial_protection(power, resistance, protection, heat, variance):
    """Killing Precision -- only 20% of protection applies."""
    return (power * resistance - protection * 0.2) * heat * variance


#: A grid, not a handful. Every axis carries the awkward values as well as the
#: tidy ones: a resistance that is not representable in binary (0.85, 1.15), a
#: protection that outweighs the swing (so the clamp fires), a heat far off 1.0
#: (the term Power Strike used to drop), and both ends of the variance band
#: plus a spread between them.
_POWERS = (0, 1, 3, 7, 13, 25, 47, 100, 137, 250, 999)
_RESISTANCES = (0.0, 0.15, 0.5, 0.85, 1.0, 1.15, 1.4, 2.0)
_PROTECTIONS = (0, 1, 3, 7, 12, 15, 18, 28, 60, 250)
_HEATS = (0.5, 0.75, 1.0, 1.25, 1.9, 2.0, 3.3, 10.0)
_VARIANCES = (0.8, 0.9, 1.0, 1.1, 1.2)


def _clamped(value):
    """What every call site did to the legacy float immediately afterwards:
    ``max(0, damage)`` or ``if damage <= 0: damage = 0``. Both collapse a
    non-positive roll to zero before the glance halving and the final int()."""
    return value if value > 0 else 0.0


class TestTheArithmeticIsUnchanged:
    def test_resolve_damage_reproduces_the_canonical_line_bit_for_bit(self):
        mismatches = []
        for power, resistance, protection, heat, variance in itertools.product(
            _POWERS, _RESISTANCES, _PROTECTIONS, _HEATS, _VARIANCES
        ):
            expected = _clamped(
                _legacy_full_protection(power, resistance, protection, heat, variance)
            )
            actual = resolve_damage(
                _Attacker(heat),
                _Target(resistance, protection),
                power,
                "slashing",
                variance=variance,
            )
            if actual != expected or int(actual) != int(expected):
                mismatches.append(
                    (power, resistance, protection, heat, variance, expected, actual)
                )
        assert not mismatches, (
            f"{len(mismatches)} of "
            f"{len(_POWERS) * len(_RESISTANCES) * len(_PROTECTIONS) * len(_HEATS) * len(_VARIANCES)}"
            f" grid points diverge from the pre-refactor expression; first 5: "
            f"{mismatches[:5]}"
        )

    def test_a_zero_protection_override_reproduces_the_armour_ignoring_line(self):
        """Pulverize and Armor Pierce drop the protection term entirely.

        Their expression is ``power * res * heat * variance`` -- one fewer
        binary operation than the canonical line. Subtracting an integer zero
        is exact for every finite float, so routing them through the helper
        with ``protection=0`` has to land on the same bits.
        """
        mismatches = []
        for power, resistance, heat, variance in itertools.product(
            _POWERS, _RESISTANCES, _HEATS, _VARIANCES
        ):
            expected = _clamped(
                _legacy_no_protection(power, resistance, heat, variance)
            )
            actual = resolve_damage(
                _Attacker(heat),
                _Target(resistance, 999),  # ignored: the override wins
                power,
                "slashing",
                protection=0,
                variance=variance,
            )
            if actual != expected:
                mismatches.append((power, resistance, heat, variance, expected, actual))
        assert not mismatches, mismatches[:5]

    def test_a_scaled_protection_override_reproduces_killing_precision(self):
        mismatches = []
        for power, resistance, protection, heat, variance in itertools.product(
            _POWERS, _RESISTANCES, _PROTECTIONS, _HEATS, _VARIANCES
        ):
            expected = _clamped(
                _legacy_partial_protection(
                    power, resistance, protection, heat, variance
                )
            )
            actual = resolve_damage(
                _Attacker(heat),
                _Target(resistance, protection),
                power,
                "slashing",
                protection=protection * 0.2,
                variance=variance,
            )
            if actual != expected:
                mismatches.append(
                    (power, resistance, protection, heat, variance, expected, actual)
                )
        assert not mismatches, mismatches[:5]

    def test_damage_bounds_predicts_exactly_what_resolve_damage_computes(self):
        """The whole point of the extraction.

        ``damage_bounds`` is the preview. It must not merely bracket the roll
        -- it must be the same expression with the roll pinned, so a change to
        one cannot fail to reach the other.
        """
        mismatches = []
        for power, resistance, protection, heat in itertools.product(
            _POWERS, _RESISTANCES, _PROTECTIONS, _HEATS
        ):
            attacker, target = _Attacker(heat), _Target(resistance, protection)
            low, high = damage_bounds(attacker, target, power, "slashing")
            expected = (
                int(
                    resolve_damage(
                        attacker, target, power, "slashing",
                        variance=DAMAGE_VARIANCE_MIN,
                    )
                ),
                int(
                    resolve_damage(
                        attacker, target, power, "slashing",
                        variance=DAMAGE_VARIANCE_MAX,
                    )
                ),
            )
            if (low, high) != expected:
                mismatches.append(
                    (power, resistance, protection, heat, (low, high), expected)
                )
        assert not mismatches, mismatches[:5]

    def test_damage_bounds_forwards_a_protection_override_to_both_ends(self):
        """Item the preview path needs: ``damage_bounds(protection=...)``
        must be ``resolve_damage(protection=...)`` with the roll pinned to
        each end -- same rule as the default-protection case above, so an
        armour-scaling move's preview (Impale x0.4, Armor Pierce 0) cannot
        drift from its execute()."""
        mismatches = []
        for power, resistance, protection, heat in itertools.product(
            _POWERS, _RESISTANCES, _PROTECTIONS, _HEATS
        ):
            for override in (0, protection * 0.2, protection * 0.4):
                attacker = _Attacker(heat)
                target = _Target(resistance, protection)
                got = damage_bounds(
                    attacker, target, power, "slashing", protection=override
                )
                expected = (
                    int(
                        resolve_damage(
                            attacker, target, power, "slashing",
                            protection=override, variance=DAMAGE_VARIANCE_MIN,
                        )
                    ),
                    int(
                        resolve_damage(
                            attacker, target, power, "slashing",
                            protection=override, variance=DAMAGE_VARIANCE_MAX,
                        )
                    ),
                )
                if got != expected:
                    mismatches.append(
                        (power, resistance, protection, heat, override,
                         got, expected)
                    )
        assert not mismatches, mismatches[:5]

    def test_damage_bounds_on_a_positioned_pair_scores_the_facing_curve(self):
        """The grid above runs position-less combatants, so
        ``apply_facing_damage`` is a no-op across all of it and a regression
        in how ``damage_bounds`` feeds the faced power into the expression
        would be invisible. This case stands the attacker at the defender's
        back (the 1.40x band) and demands the bounds equal the engine's own
        faced power run through ``resolve_damage`` -- with a premise check
        that the curve genuinely engaged."""
        from src.moves._base import apply_facing_damage
        from src.positions import CombatPosition, Direction

        mismatches = []
        for power, resistance, protection, heat in itertools.product(
            _POWERS, _RESISTANCES, _PROTECTIONS, _HEATS
        ):
            attacker = _Attacker(heat)
            target = _Target(resistance, protection)
            attacker.combat_position = CombatPosition(0, 0, Direction.E)
            # Defender faces AWAY from the attacker: a rear attack.
            target.combat_position = CombatPosition(3, 0, Direction.E)
            faced = apply_facing_damage(attacker, target, power)
            # int(power * 1.40) only exceeds power from 3 up -- at 1 the
            # truncation collapses the bonus, which is expected, not broken.
            if power >= 3:
                assert faced > power, (
                    "premise broken: the rear-attack fixture no longer "
                    "engages the facing multiplier at all"
                )
            got = damage_bounds(attacker, target, power, "slashing")
            expected = (
                int(
                    resolve_damage(
                        attacker, target, faced, "slashing",
                        variance=DAMAGE_VARIANCE_MIN,
                    )
                ),
                int(
                    resolve_damage(
                        attacker, target, faced, "slashing",
                        variance=DAMAGE_VARIANCE_MAX,
                    )
                ),
            )
            if got != expected:
                mismatches.append(
                    (power, resistance, protection, heat, got, expected)
                )
        assert not mismatches, mismatches[:5]

    def test_flat_arc_damage_bounds_reproduces_the_hand_written_line(self):
        """The flat arc expression -- ``max(1, int(swing - protection))``
        with per-multiplier truncation -- was hand-written four times
        (``flat_arc_damage_bounds`` plus the Sweep/Halberd Spin/Reap loops).
        This differential pins the exact legacy arithmetic so the extraction
        into one helper cannot shift a point anywhere on the grid, positioned
        or not."""
        from src.moves._base import apply_facing_damage
        from src.positions import CombatPosition, Direction

        mismatches = []
        for power, protection in itertools.product(_POWERS, _PROTECTIONS):
            for bonuses in ((), (1.25,), (1.25, 1.25), (1.25, 1.1)):
                for positioned in (False, True):
                    attacker = _Attacker(1.0)
                    target = _Target(1.0, protection)
                    if positioned:
                        attacker.combat_position = CombatPosition(
                            0, 0, Direction.E
                        )
                        target.combat_position = CombatPosition(
                            3, 0, Direction.E
                        )
                    swing = apply_facing_damage(attacker, target, power)
                    legacy = max(1, int(swing - protection))
                    for multiplier in bonuses:
                        legacy = int(legacy * multiplier)
                    got = flat_arc_damage_bounds(
                        attacker, target, power, bonuses
                    )
                    if got != (legacy, legacy):
                        mismatches.append(
                            (power, protection, bonuses, positioned,
                             got, legacy)
                        )
        assert not mismatches, mismatches[:5]

    def test_the_default_variance_stays_inside_the_advertised_band(self, seeded):
        """No variance argument means the real roll, and the real roll is the
        band ``damage_bounds`` reports -- not a wider one. The ``seeded``
        fixture restores the process RNG state afterwards -- a bare
        ``random.seed`` here leaked a pinned RNG into whichever test
        ``pytest-randomly`` ran next."""
        attacker, target = _Attacker(2.0), _Target(1.0, 10)
        low, high = damage_bounds(attacker, target, 100, "slashing")
        with seeded(1234):
            for _ in range(2000):
                rolled = int(resolve_damage(attacker, target, 100, "slashing"))
                assert low <= rolled <= high, (rolled, low, high)


class TestDegradedInputsDegradeInsteadOfCrashing:
    def test_a_non_numeric_protection_is_treated_as_none(self):
        """The sanitised read ``damage_bounds`` has always used, now shared.

        An execute() that read ``self.target.protection`` raw raised a
        TypeError inside the combat loop for a target whose protection was
        ``None``, while the preview for that same target quietly showed a
        number -- the two disagreed about whether the move was even possible.
        """
        target = _Target(1.0, None)
        assert resolve_damage(_Attacker(1.0), target, 100, "slashing", variance=1.0) == 100.0
        assert damage_bounds(_Attacker(1.0), target, 100, "slashing") == (80, 120)

    def test_a_boolean_protection_is_not_silently_worth_one_point(self):
        """``isinstance(True, int)`` is True, so a bool protection used to be
        subtracted as 1. It is a flag someone set on the wrong attribute, not
        an armour value."""
        assert target_protection(_Target(1.0, True)) == 0
        assert target_protection(_Target(1.0, False)) == 0

    def test_a_non_finite_product_collapses_to_zero_rather_than_crashing(self):
        """``int(nan)`` raises ValueError, and it raised at the *call site*,
        before ``Move.hit``'s sanitiser could ever see the number (issue #296
        established the product can go non-finite through an exotic
        resistance)."""
        assert resolve_damage(
            _Attacker(1.0), _Target(1.0, 0), float("inf"), "slashing", variance=1.0
        ) == 0.0
        assert resolve_damage(
            _Attacker(1.0), _Target(0.0, 0), float("inf"), "slashing", variance=1.0
        ) == 0.0  # inf * 0.0 -> nan

    def test_a_non_finite_heat_falls_back_to_no_scaling(self):
        """``_resolve_heat`` degrades a NaN/inf heat to 1.0 rather than
        letting it poison the product -- so the non-finite clamp above has to
        be reached through the *power* term, which nothing sanitises."""
        assert not math.isfinite(float("inf"))
        assert resolve_damage(
            _Attacker(1.0), _Target(1.0, 0), 100, "slashing",
            heat=float("nan"), variance=1.0,
        ) == 100.0


# ---------------------------------------------------------------------------
# The DRY guard: no copy may come back
# ---------------------------------------------------------------------------


from tests._moves_scan import move_module_paths  # noqa: E402


def _move_module_paths():
    """The weapon modules only: ``_base`` holds the canonical line itself."""
    return move_module_paths(exclude=("_base",))


def _reads_resistance_dict(node):
    """True for the ``x.resistance`` half of ``x.resistance.get(...)``/``[...]``."""
    return isinstance(node, ast.Attribute) and node.attr == "resistance"


def _damage_term_flags(node):
    """``(resistance, protection, uniform, heat)`` referenced under ``node``.

    The four markers of a hand-written damage line: a resistance read
    (``combat_resistance(...)``, or the ``target.resistance.get(...)`` /
    ``[...]`` spelling three of the deleted copies used), a ``protection``
    attribute read, a ``random.uniform`` roll, and a ``heat`` read.
    """
    resistance = protection = uniform = heat = False
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            named = getattr(child.func, "id", None) or getattr(
                child.func, "attr", None
            )
            if named == "combat_resistance":
                resistance = True
            elif named == "uniform":
                uniform = True
            elif named == "get" and _reads_resistance_dict(
                getattr(child.func, "value", None)
            ):
                # `target.resistance.get("crushing", 1.0)` -- how three of
                # the copies this module deleted actually spelled it. A
                # scan looking only for combat_resistance() calls does not
                # see them.
                resistance = True
        elif isinstance(child, ast.Attribute) and child.attr == "protection":
            protection = True
        elif isinstance(child, ast.Attribute) and child.attr == "heat":
            heat = True
        elif isinstance(child, ast.Subscript) and _reads_resistance_dict(
            child.value
        ):
            resistance = True
    return resistance, protection, uniform, heat


def _hand_written_damage_lines(path):
    """Function and class names in ``path`` that spell the canonical line out
    by hand.

    The signature is a ``random.uniform`` roll next to ANY term the canonical
    expression owns -- see ``_damage_term_flags``. Deliberately a disjunction
    rather than the conjunction it started as: requiring all three meant a
    PARTIAL copy passed, and every historical drift here was partial.
    PowerStrike's real bug was ``power * uniform(0.8, 1.2) - protection``
    with resistance and heat gone, so it carried two of the three markers and
    the original scan would have certified it clean.
    ``test_the_damage_line_scan_catches_a_partial_copy`` pins that shape and
    two others.

    Applied at TWO scopes. Function scope catches the inline copies. Class
    scope catches the *split* copy ``_npc.py``'s attack family shipped for
    months unseen: the variance roll lives in ``evaluate()`` (rolled into
    ``self.power``) and the protection subtraction in ``execute()``, so no
    single function ever held both markers and the function-scoped scan was
    structurally blind to it.
    ``test_the_damage_line_scan_catches_a_split_copy`` is the positive
    control. A class already flagged through one of its own methods is not
    reported a second time.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = []
    flagged_functions = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        resistance, protection, uniform, heat = _damage_term_flags(node)
        if uniform and (resistance or protection or heat):
            offenders.append(f"{path.name}:{node.name} (line {node.lineno})")
            flagged_functions.add(node)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods = [
            child
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if any(method in flagged_functions for method in methods):
            continue  # already reported at function scope
        resistance = protection = uniform = heat = False
        for method in methods:
            r, p, u, h = _damage_term_flags(method)
            resistance |= r
            protection |= p
            uniform |= u
            heat |= h
        if uniform and (resistance or protection or heat):
            offenders.append(
                f"{path.name}:{node.name} (class scope, line {node.lineno})"
            )
    return offenders


@pytest.mark.parametrize(
    "path", _move_module_paths(), ids=[p.name for p in _move_module_paths()]
)
def test_no_weapon_module_writes_the_damage_line_by_hand(path):
    """The copies are what this whole module exists to prevent coming back.

    A new attack does not need its own damage line; it needs
    ``resolve_damage``. If it genuinely needs a *different* line, that is a
    divergence its ``preview_damage`` has to declare (see
    tests/test_preview_damage.py) -- which starts with not writing it here.
    """
    offenders = _hand_written_damage_lines(path)
    assert not offenders, (
        "these functions spell the canonical damage expression out by hand "
        "instead of calling src.moves._base.resolve_damage: " + ", ".join(offenders)
    )


def test_the_protection_sanitiser_has_exactly_one_definition():
    """The ``getattr`` + ``isinstance`` + bool-exclusion block existed three
    times (``damage_bounds``, ``flat_arc_damage_bounds`` and the flat line that
    is now ``flat_resisted_damage``)
    and had to agree in all three for the preview and the execute to agree."""
    base = pathlib.Path(_moves_pkg.__file__).parent / "_base.py"
    tree = ast.parse(base.read_text(encoding="utf-8"))
    definitions = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "target_protection"
    ]
    assert definitions == ["target_protection"]

    bool_guards = sum(
        1
        for path in (base,) + _move_module_paths()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and (getattr(node.func, "id", None) == "isinstance")
        and any(
            isinstance(arg, ast.Name) and arg.id == "bool" for arg in ast.walk(node)
        )
        and "protection" in ast.dump(node)
    )
    # Exactly one: the definition inside target_protection() itself. `<= 1`
    # would also pass at zero -- i.e. with the sanitiser deleted outright --
    # which is the vacuous-guard failure mode this file keeps documenting.
    assert bool_guards == 1, (
        f"expected exactly the target_protection() copy of the protection "
        f"sanitiser, found {bool_guards}"
    )


def test_the_damage_line_scan_catches_a_partial_copy():
    """The positive control this guard went without.

    A guard that only fires on a complete copy cannot catch the copies that
    actually happen. Every historical drift in this package was PARTIAL --
    PowerStrike kept its variance roll and its facing curve while dropping
    resistance and heat, which is precisely why nothing detected it for
    months. Each snippet below is a real shape from this package's history and
    must be flagged; the canonical call must not be.
    """
    import tempfile

    partial_copies = {
        "power_strike_pre_fix": (
            "def execute(self, x):\n"
            "    damage = self.power * random.uniform(0.8, 1.2)"
            " - self.target.protection\n"
        ),
        "resistance_dict_get": (
            "def execute(self, x):\n"
            "    damage = (self.power"
            " * self.target.resistance.get('crushing', 1.0))"
            " * random.uniform(0.8, 1.2)\n"
        ),
        "heat_only": (
            "def execute(self, x):\n"
            "    damage = self.power * self.user.heat"
            " * random.uniform(0.8, 1.2)\n"
        ),
    }
    for name, source in partial_copies.items():
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
            fh.write(source)
            probe = pathlib.Path(fh.name)
        try:
            assert _hand_written_damage_lines(probe), (
                f"the scan does not flag {name} -- the shape it exists to catch"
            )
        finally:
            probe.unlink()


def test_the_damage_line_scan_catches_a_split_copy():
    """The class-scope positive control.

    ``_npc.py``'s attack family carried the copy SPLIT across methods --
    ``evaluate()`` rolled the variance into ``self.power``, ``execute()``
    subtracted raw ``.protection`` -- so no single function held both
    markers and the function-scoped scan certified it for months. The fixed
    shape (protection routed through the ``target_protection`` sanitiser,
    via ``_npc_flat_damage``) must NOT be flagged: a call is not an
    attribute read.
    """
    import tempfile

    split_copy = (
        "class Biter:\n"
        "    def evaluate(self):\n"
        "        self.power = self.user.damage * random.uniform(0.8, 1.2)\n"
        "    def execute(self, x):\n"
        "        damage = self.power - self.target.protection\n"
    )
    fixed = (
        "class Clean:\n"
        "    def evaluate(self):\n"
        "        self.power = self.user.damage * random.uniform(0.8, 1.2)\n"
        "    def execute(self, x):\n"
        "        damage = _npc_flat_damage(self.power, self.target)\n"
    )
    for name, source, expected in (
        ("split copy", split_copy, True),
        ("sanitised call", fixed, False),
    ):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
            fh.write(source)
            probe = pathlib.Path(fh.name)
        try:
            flagged = bool(_hand_written_damage_lines(probe))
            assert flagged is expected, (
                f"the scan {'missed' if expected else 'wrongly flagged'} "
                f"the {name}"
            )
        finally:
            probe.unlink()


def test_the_damage_line_scan_does_not_flag_the_canonical_call():
    """...and does not fire on a move that routes through the helper."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(
            "def execute(self, x):\n"
            "    damage = resolve_damage(self.user, self.target,"
            " power, self.base_damage_type)\n"
        )
        probe = pathlib.Path(fh.name)
    try:
        assert not _hand_written_damage_lines(probe)
    finally:
        probe.unlink()
