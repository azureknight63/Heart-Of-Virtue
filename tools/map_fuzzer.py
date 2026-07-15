#!/usr/bin/env python3
"""Map-JSON deserialization fuzzer for Heart of Virtue (issue #290 hardening).

Map files (``src/resources/maps/*.json``) and map-editor output store entities
as ``{"__class__", "__module__", "props"}`` or ``{"__class_type__": "mod:Class"}``
markers that :meth:`src.universe.Universe._deserialize_saved_instance` resolves by
dynamic import + ``getattr`` + instantiation. Because map data is
attacker-influenceable, that is the same risk class as the pickle loader -- so
this fuzzer feeds the loader a random mix of benign engine payloads and
adversarial ones (dangerous ``__module__``/``__class_type__`` values, malformed
dotted paths, recursion-bomb ``props`` graphs, garbage shapes) and asserts the
hardened loader's invariants:

  * **Dangerous globals are never resolved.** A hostile ``os``/``subprocess``/…
    reference is refused by the shared engine allow-list gate
    (``secure_pickle._is_allowed``); the loader returns ``None`` and never hands
    back ``os.system`` et al.
  * **No unbounded recursion.** A deeply nested ``props`` graph is depth-capped
    (``MAX_DESERIALIZE_DEPTH``); the loader returns without a ``RecursionError``.
  * **No uncontrolled crash.** Any input yields either a value, ``None``, or a
    *controlled* exception -- never a ``RecursionError``/``MemoryError`` or an
    executed side effect.

The security invariant (which the CI test asserts is never violated) is the
dangerous-resolution / recursion / harness-error set; a benign payload that the
loader declines is an informational coverage note, not a breach.

Usage:
    python tools/map_fuzzer.py                    # 500 iterations, random seed
    python tools/map_fuzzer.py --iterations 5000
    python tools/map_fuzzer.py --seed 1337        # reproducible run
"""

import os
import sys
import random
import argparse
import importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.universe import Universe, MAX_DESERIALIZE_DEPTH  # noqa: E402

# Categories that indicate a genuine security-invariant breach (must be zero).
# Everything else -- notably the loader declining a benign engine payload -- is
# a coverage note, not a breach.
_SECURITY_CATEGORIES = frozenset({
    "dangerous-resolved", "recursion-not-bounded", "uncontrolled-crash",
    "harness-error",
})

# Resolvable-but-disallowed (module, name) pairs the gate must never resolve.
_DANGEROUS_GLOBALS = [
    ("os", "system"), ("os", "mkdir"), ("os", "remove"), ("os", "removedirs"),
    ("subprocess", "Popen"), ("subprocess", "run"), ("shutil", "rmtree"),
    ("builtins", "eval"), ("builtins", "exec"), ("builtins", "__import__"),
    ("posix", "system"), ("webbrowser", "open"), ("sys", "exit"),
]

# The actual objects those pairs resolve to -- if the loader ever returns one of
# these (or a callable from os/subprocess/…), the gate failed.
_DANGEROUS_MODULES = frozenset({
    "os", "subprocess", "shutil", "builtins", "posix", "webbrowser", "sys",
    "importlib", "socket", "ctypes",
})


class Finding:
    """An invariant violation, carrying enough context to reproduce it."""

    def __init__(self, seed, iteration, category, detail):
        self.seed = seed
        self.iteration = iteration
        self.category = category
        self.detail = detail

    @property
    def is_security(self):
        return self.category in _SECURITY_CATEGORIES

    def __str__(self):
        tag = "SECURITY" if self.is_security else "coverage"
        return (f"[{tag} seed={self.seed} iter={self.iteration} "
                f"{self.category}] {self.detail}")


def security_findings(findings):
    """Filter to genuine security-invariant breaches (must be empty)."""
    return [f for f in findings if f.is_security]


def coverage_findings(findings):
    """Filter to informational coverage notes."""
    return [f for f in findings if not f.is_security]


# ---------------------------------------------------------------------------
# Benign engine class pool (payloads the loader is allowed to resolve)
# ---------------------------------------------------------------------------

_benign_pool = None


def _build_benign_pool():
    """(bare_module, class_name) pairs for real engine classes."""
    pairs = []
    for bare in ("items", "npc", "objects", "tiles", "events"):
        try:
            mod = importlib.import_module("src." + bare)
        except Exception:
            continue
        names = [n for n in vars(mod)
                 if isinstance(getattr(mod, n, None), type)
                 and getattr(getattr(mod, n), "__module__", "").startswith("src.")]
        for n in random.sample(names, min(4, len(names))):
            pairs.append((bare, n))
    return pairs or [("items", "Item")]


def _pool():
    global _benign_pool
    if _benign_pool is None:
        _benign_pool = _build_benign_pool()
    return _benign_pool


# ---------------------------------------------------------------------------
# Random / adversarial payload generation
# ---------------------------------------------------------------------------

def _random_module_name(rng):
    kind = rng.randint(0, 4)
    if kind == 0:
        return rng.choice(list(_DANGEROUS_MODULES))
    if kind == 1:  # malformed dotted path
        parts = [rng.choice(["", "a", "os", "src", "..", "1"])
                 for _ in range(rng.randint(1, 4))]
        return ".".join(parts)
    if kind == 2:
        return rng.choice(["OS", "Os.System", "src.", "src", ""])
    if kind == 3:
        return rng.choice([None, 123, [], {}])
    return "".join(rng.choice("abcxyz._") for _ in range(rng.randint(0, 10)))


def _random_props(rng, depth):
    if depth <= 0 or rng.random() < 0.4:
        return rng.choice([0, -1, 2 ** 40, "x" * rng.randint(0, 8), None, True])
    return {f"k{i}": _random_props(rng, depth - 1) for i in range(rng.randint(0, 3))}


def _make_payload(rng):
    """Return (payload, expectation) where expectation is one of
    'benign', 'dangerous', 'malformed', 'recursion'."""
    pick = rng.random()
    if pick < 0.30:  # benign engine payload
        bare, name = rng.choice(_pool())
        return ({"__class__": name, "__module__": bare,
                 "props": {} if rng.random() < 0.5 else _random_props(rng, 2)},
                "benign")
    if pick < 0.55:  # dangerous global via __class_type__ or __class__/__module__
        mod, name = rng.choice(_DANGEROUS_GLOBALS)
        if rng.random() < 0.5:
            return ({"__class_type__": f"{mod}:{name}"}, "dangerous")
        return ({"__class__": name, "__module__": mod, "props": {}}, "dangerous")
    if pick < 0.75:  # recursion-bomb props under a benign class
        bare, name = rng.choice(_pool())
        deep = cur = {}
        for _ in range(MAX_DESERIALIZE_DEPTH + 50):
            nxt = {}
            cur["n"] = nxt
            cur = nxt
        return ({"__class__": name, "__module__": bare, "props": {"deep": deep}},
                "recursion")
    # malformed / garbage shapes
    shape = rng.randint(0, 4)
    if shape == 0:
        return ({"__class_type__": rng.choice(["a::b", "nocolon", ":", "os:", ""])},
                "malformed")
    if shape == 1:
        return ({"__class__": rng.choice([None, 1, ""]),
                 "__module__": _random_module_name(rng),
                 "props": rng.choice([None, [], "x", {}])}, "malformed")
    if shape == 2:
        return (rng.choice([None, 42, "string", [], ("t",)]), "malformed")
    if shape == 3:
        return ({"__module__": _random_module_name(rng)}, "malformed")
    return ({"__class__": "X", "__module__": _random_module_name(rng),
             "props": _random_props(rng, 3)}, "malformed")


# ---------------------------------------------------------------------------
# Invariant check
# ---------------------------------------------------------------------------

def _is_dangerous_result(result):
    """True if the loader handed back a reference into a dangerous module."""
    if result is None:
        return False
    mod = getattr(result, "__module__", None)
    if isinstance(mod, str) and mod.split(".")[0] in _DANGEROUS_MODULES:
        return True
    # A resolved class object: check where it lives.
    owner = getattr(result, "__self__", None)
    if owner is not None:
        omod = getattr(type(owner), "__module__", "")
        if isinstance(omod, str) and omod.split(".")[0] in _DANGEROUS_MODULES:
            return True
    return False


def _check(rng, universe, seed, i):
    payload, expectation = _make_payload(rng)
    findings = []
    try:
        result = universe._deserialize_saved_instance(payload)
    except RecursionError as exc:
        return [Finding(seed, i, "recursion-not-bounded",
                        f"{expectation}: {type(exc).__name__}")]
    except MemoryError as exc:  # noqa: BLE001
        return [Finding(seed, i, "uncontrolled-crash",
                        f"{expectation}: {type(exc).__name__}")]
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        # Controlled, expected error classes for malformed input -- acceptable
        # for hostile shapes, noted for benign ones.
        if expectation in ("benign",):
            findings.append(Finding(seed, i, "benign-controlled-error",
                                    f"{type(exc).__name__}: {exc}"))
        return findings
    except Exception as exc:  # noqa: BLE001 - anything else is uncontrolled
        return [Finding(seed, i, "uncontrolled-crash",
                        f"{expectation}: {type(exc).__name__}: {exc}")]

    if _is_dangerous_result(result):
        findings.append(Finding(seed, i, "dangerous-resolved",
                                f"loader resolved dangerous ref: {result!r}"))
    elif expectation == "dangerous" and result is not None:
        # A dangerous payload that resolved to a *non*-dangerous object is still
        # a gate miss worth flagging (should have been refused -> None).
        findings.append(Finding(seed, i, "dangerous-resolved",
                                f"dangerous payload not refused: {result!r}"))
    return findings


def run_fuzz(iterations=500, seed=None):
    """Run the fuzzer and return a list of :class:`Finding` (empty == clean)."""
    if seed is None:
        seed = random.randrange(2 ** 32)
    rng = random.Random(seed)
    universe = Universe()
    findings = []
    for i in range(iterations):
        try:
            findings.extend(_check(rng, universe, seed, i))
        except Exception as exc:  # noqa: BLE001 - the harness itself must not die
            findings.append(Finding(seed, i, "harness-error",
                                    f"{type(exc).__name__}: {exc}"))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=None,
                        help="Fix the RNG seed for a reproducible run.")
    args = parser.parse_args(argv)

    findings = run_fuzz(args.iterations, args.seed)
    security = security_findings(findings)
    coverage = coverage_findings(findings)

    if coverage:
        seen = set()
        print(f"NOTE: {len(coverage)} coverage note(s):")
        for f in coverage:
            if f.detail not in seen:
                seen.add(f.detail)
                print("  " + str(f))

    if security:
        print(f"FAIL: {len(security)} security-invariant violation(s):")
        for f in security[:50]:
            print("  " + str(f))
        return 1
    print(f"OK: {args.iterations} iterations, no security-invariant violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
