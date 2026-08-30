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

    def test_the_default_variance_stays_inside_the_advertised_band(self):
        """No variance argument means the real roll, and the real roll is the
        band ``damage_bounds`` reports -- not a wider one."""
        import random

        attacker, target = _Attacker(2.0), _Target(1.0, 10)
        low, high = damage_bounds(attacker, target, 100, "slashing")
        random.seed(1234)
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
        """``_resolve_heat`` degrades a NaN/inf momentum to 1.0 rather than
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


def _move_module_paths():
    package_dir = pathlib.Path(_moves_pkg.__file__).parent
    return tuple(
        path
        for path in sorted(package_dir.glob("*.py"))
        if path.stem not in ("__init__", "_base")
    )


def _reads_resistance_dict(node):
    """True for the ``x.resistance`` half of ``x.resistance.get(...)``/``[...]``."""
    return isinstance(node, ast.Attribute) and node.attr == "resistance"


def _hand_written_damage_lines(path):
    """Function names in ``path`` that spell the canonical line out by hand.

    The signature is a ``random.uniform`` roll next to ANY term the canonical
    expression owns: a resistance read (``combat_resistance(...)``, or the
    ``target.resistance.get(...)``/``[...]`` spelling three of the deleted
    copies used), a ``protection`` attribute, or a ``heat`` read.

    Deliberately a disjunction rather than the conjunction it started as.
    Requiring all three meant a PARTIAL copy passed -- and every historical
    drift here was partial. PowerStrike's real bug was
    ``power * uniform(0.8, 1.2) - protection`` with resistance and heat gone,
    so it carried two of the three markers and the original scan would have
    certified it clean. ``test_the_damage_line_scan_catches_a_partial_copy``
    pins that shape and two others.

    ``_npc.py`` rolls variance into *power* rather than into the damage line,
    so it does not trip this; that exemption is why its four hand-written
    resisted lines are out of scope here.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
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
        # A hand-written damage line is a variance roll next to ANY of the
        # terms the canonical expression owns -- not all three at once.
        # Requiring the conjunction is what let the shape that motivated this
        # module slip through: PowerStrike's real bug was
        # `power * uniform(0.8, 1.2) - protection`, with resistance and heat
        # dropped entirely, so it carried two of the three markers and a
        # three-way AND would have certified it as clean.
        if uniform and (resistance or protection or heat):
            offenders.append(f"{path.name}:{node.name} (line {node.lineno})")
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
    assert bool_guards <= 1, (
        f"{bool_guards} copies of the protection sanitiser survive -- it belongs "
        "in target_protection() only"
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
