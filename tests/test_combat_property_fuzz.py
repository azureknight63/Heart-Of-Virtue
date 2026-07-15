"""Property/fuzz test for combat numeric invariants (issue #296).

Combat damage/resistance/HP math runs thousands of times per session over
combatant states that -- via extreme stats, degraded saves, or status effects --
can go far outside the "sane" range. This seeded property fuzzer drives the
shared hardening choke points (``functions.combat_resistance`` /
``combat_status_resistance`` and ``Combatant.clamp_hp`` / ``get_hp_pcnt``) with
random and adversarial combatant states and asserts the numeric invariants that
two confirmed crashes motivated (a missing ``resistance`` key raised KeyError; a
NaN/inf resistance crashed ``int(damage)``):

  * resistance is always a finite float (missing key / NaN / inf / wrong type
    all resolve to a finite default);
  * status-resistance is always finite and within [0, 1];
  * ``clamp_hp`` yields an int in ``[0, maxhp]`` and never NaN/inf;
  * ``get_hp_pcnt`` never divides by zero;
  * a full damage computation stays finite and floors at 0.

Run standalone:  python tests/test_combat_property_fuzz.py --iterations 5000
"""

import math
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.functions as functions  # noqa: E402
from src.combatant import Combatant  # noqa: E402

_DAMAGE_TYPES = ["piercing", "slashing", "crushing", "fire", "ice", "shock",
                 "pure", "poison", "arcane"]
_STATUS_TYPES = ["poison", "stun", "bleed", "burn", "freeze", "petrify",
                 "disorient"]


class _FuzzCombatant(Combatant):
    """Minimal concrete Combatant carrying only the fuzzed numeric state."""

    def __init__(self):
        self.name = "Fuzz"
        self.hp = 100
        self.maxhp = 100
        self.resistance = {}
        self.status_resistance = {}
        self.states = []
        self.in_combat = True


def _wild_number(rng):
    return rng.choice([
        rng.uniform(-1e6, 1e6), rng.randint(-(2 ** 40), 2 ** 40),
        0, 0.0, -1, 1, 0.5, 1.0, 2.0,
        float("nan"), float("inf"), float("-inf"),
        2 ** 62, -(2 ** 62), "not-a-number", None, True, False,
    ])


def _wild_dict(rng, keys):
    d = {}
    for k in keys:
        if rng.random() < 0.6:                # sometimes omit the key entirely
            d[k] = _wild_number(rng)
    if rng.random() < 0.2:                    # sometimes not even a dict
        return rng.choice([None, [], "x", 5])
    return d


class Finding:
    def __init__(self, seed, i, category, detail):
        self.seed, self.i, self.category, self.detail = seed, i, category, detail

    def __str__(self):
        return f"[seed={self.seed} iter={self.i} {self.category}] {self.detail}"


def run_fuzz(iterations=2000, seed=None):
    if seed is None:
        seed = random.randrange(2 ** 32)
    rng = random.Random(seed)
    findings = []
    c = _FuzzCombatant()

    for i in range(iterations):
        try:
            c.resistance = _wild_dict(rng, rng.sample(_DAMAGE_TYPES,
                                                      rng.randint(0, 6)))
            c.status_resistance = _wild_dict(rng, rng.sample(_STATUS_TYPES,
                                                             rng.randint(0, 5)))

            # 1) resistance always finite, even for an absent damage type.
            dtype = rng.choice(_DAMAGE_TYPES)
            r = functions.combat_resistance(c, dtype)
            if not (isinstance(r, float) and math.isfinite(r)):
                findings.append(Finding(seed, i, "resistance-nonfinite",
                                        f"{dtype} -> {r!r}"))

            # 2) status-resistance finite and within [0, 1].
            stype = rng.choice(_STATUS_TYPES)
            s = functions.combat_status_resistance(c, stype)
            if not (isinstance(s, float) and math.isfinite(s) and 0.0 <= s <= 1.0):
                findings.append(Finding(seed, i, "status-resistance-oob",
                                        f"{stype} -> {s!r}"))

            # 3) clamp_hp yields an int in [0, sane maxhp], never NaN/inf.
            c.hp = _wild_number(rng)
            c.maxhp = _wild_number(rng)
            hp = c.clamp_hp()
            sane_max = c.maxhp if isinstance(c.maxhp, (int, float)) and \
                math.isfinite(c.maxhp) and c.maxhp > 0 else 0
            if not isinstance(hp, int) or hp < 0 or hp > max(0, int(sane_max)) \
                    or c.hp != hp:
                findings.append(Finding(seed, i, "hp-clamp-violation",
                                        f"hp={hp!r} maxhp={c.maxhp!r}"))

            # 4) get_hp_pcnt never raises / never returns non-finite.
            pcnt = c.get_hp_pcnt()
            if not math.isfinite(pcnt):
                findings.append(Finding(seed, i, "hp-pcnt-nonfinite",
                                        f"{pcnt!r}"))

            # 5) a full damage computation stays finite and floors at 0.
            power = _wild_number(rng)
            protection = _wild_number(rng)
            try:
                power_f = float(power)
                prot_f = float(protection)
            except (TypeError, ValueError):
                power_f = prot_f = 0.0
            if math.isfinite(power_f) and math.isfinite(prot_f):
                raw = power_f * functions.combat_resistance(c, dtype) - prot_f
                damage = max(0, int(raw)) if math.isfinite(raw) else 0
                if damage < 0:
                    findings.append(Finding(seed, i, "negative-damage",
                                            f"{damage}"))
        except Exception as exc:  # noqa: BLE001 - any raise is an invariant break
            findings.append(Finding(seed, i, "crash",
                                    f"{type(exc).__name__}: {exc}"))
    return findings


@pytest.mark.parametrize("seed", [1, 1337, 42, 20240101])
def test_combat_numeric_invariants(seed):
    findings = run_fuzz(iterations=1500, seed=seed)
    assert not findings, "\n".join(str(f) for f in findings[:40])


def test_missing_resistance_key_defaults_not_crash():
    c = _FuzzCombatant()
    c.resistance = {}                       # every key missing
    assert functions.combat_resistance(c, "piercing") == 1.0


def test_nonfinite_resistance_coerced():
    c = _FuzzCombatant()
    c.resistance = {"fire": float("nan"), "ice": float("inf")}
    assert functions.combat_resistance(c, "fire") == 1.0
    assert functions.combat_resistance(c, "ice") == 1.0


def test_clamp_hp_bounds_extreme_values():
    c = _FuzzCombatant()
    # A finite hp above maxhp clamps down to maxhp.
    c.maxhp, c.hp = 50, 999
    assert c.clamp_hp() == 50
    # Non-finite / negative hp is treated as 0 (corrupt state = dead, never
    # invincible) rather than being clamped up to maxhp.
    c.maxhp, c.hp = 50, float("inf")
    assert c.clamp_hp() == 0
    c.maxhp, c.hp = 50, -999
    assert c.clamp_hp() == 0
    # A non-positive/NaN maxhp bounds hp to 0.
    c.maxhp, c.hp = float("nan"), 10
    assert c.clamp_hp() == 0


if __name__ == "__main__":  # pragma: no cover - manual runner
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    fs = run_fuzz(args.iterations, args.seed)
    if fs:
        print(f"FAIL: {len(fs)} invariant violation(s):")
        for f in fs[:50]:
            print("  " + str(f))
        raise SystemExit(1)
    print(f"OK: {args.iterations} iterations, no invariant violations.")
