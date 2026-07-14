#!/usr/bin/env python3
"""Save-deserialization fuzzer for Heart of Virtue (issue #13 hardening).

Populates save payloads with a random mix of real engine classes and random
values, plus adversarial payloads (disallowed globals, malicious ``__reduce__``,
tampered integrity headers, oversized blobs, and raw garbage), then feeds every
one through :func:`src.secure_pickle.safe_pickle_load` and checks the hardened
loader's invariants:

  * **Benign graphs** of allow-listed classes + random values load in legacy
    (non-strict) mode without crashing.
  * **Strict mode** never returns a class outside the allow-list -- a disallowed
    global raises ``RestrictedUnpicklingError`` *before* any ``REDUCE`` runs, so
    a malicious payload's side effect never fires.
  * **Tampering** a header-wrapped save is detected (``SaveIntegrityError``).
  * **Oversized** payloads are rejected (``SaveTooLargeError``).
  * **Garbage** raises a controlled exception rather than hanging or executing.

SAFETY: adversarial ``REDUCE`` payloads that reference a resolvable-but-
disallowed callable (e.g. ``os.mkdir``) are only ever loaded in **strict** mode,
where the allow-list blocks the global before the reduce fires. They are never
loaded in legacy mode -- that mode is intentionally unguarded (pickle executes
arbitrary code by design; see SECURITY.md), so loading such a payload there
would actually run it.

Usage:
    python tools/save_fuzzer.py                     # 500 iterations, random seed
    python tools/save_fuzzer.py --iterations 5000
    python tools/save_fuzzer.py --seed 1337         # reproducible run
"""

import io
import os
import sys
import random
import argparse
import importlib
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import secure_pickle as sp  # noqa: E402

# Finding categories that indicate a genuine security-invariant breach (must be
# zero). Everything else -- notably a clean strict-mode rejection of a benign
# object -- is an allow-list *coverage gap*: a tuning signal for _SAFE_STDLIB,
# not a breach, since it drifts with what stdlib types engine objects embed.
_SECURITY_CATEGORIES = frozenset({
    "benign-legacy-crash", "strict-unexpected-error",
    "disallowed-not-blocked", "disallowed-wrong-error",
    "reduce-not-blocked", "reduce-side-effect-fired", "reduce-wrong-error",
    "tamper-undetected", "tamper-wrong-error",
    "oversize-not-rejected", "oversize-wrong-error",
    "harness-error",
})

# Resolvable-but-disallowed callables used to probe the strict-mode guard. None
# of these are on the engine allow-list.
_DANGEROUS_GLOBALS = [
    ("os", "system"), ("os", "mkdir"), ("os", "remove"), ("os", "removedirs"),
    ("subprocess", "Popen"), ("subprocess", "run"), ("shutil", "rmtree"),
    ("builtins", "eval"), ("builtins", "exec"), ("builtins", "__import__"),
    ("posix", "system"), ("webbrowser", "open"),
]


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
    """Filter to allow-list coverage gaps (informational tuning signal)."""
    return [f for f in findings if not f.is_security]


# ---------------------------------------------------------------------------
# Sample pool of real, picklable engine instances
# ---------------------------------------------------------------------------

_sample_pool = None
_class_refs = None


def _build_sample_pool():
    """Instantiate the no-arg-constructable engine classes that round-trip.

    Returns (instances, class_refs): real object samples plus the class objects
    themselves (pickling a class exercises ``find_class`` directly).
    """
    instances = []
    class_refs = []
    for module, name in sorted(sp.get_allowlist()):
        if not module.startswith("src."):
            continue
        try:
            cls = getattr(importlib.import_module(module), name)
        except Exception:
            continue
        # A class reference always pickles; keep it for find_class fuzzing.
        try:
            sp.serialize_for_save(cls)
            class_refs.append(cls)
        except Exception:
            pass
        # Keep an instance only if it constructs and round-trips cleanly.
        try:
            inst = cls()
            sp.serialize_for_save(inst)
            instances.append(inst)
        except Exception:
            continue
    return instances, class_refs


def _pool():
    global _sample_pool, _class_refs
    if _sample_pool is None:
        _sample_pool, _class_refs = _build_sample_pool()
    return _sample_pool, _class_refs


# ---------------------------------------------------------------------------
# Random value / graph generation
# ---------------------------------------------------------------------------

def _random_primitive(rng):
    kind = rng.randint(0, 6)
    if kind == 0:
        return rng.randint(-10 ** 9, 10 ** 9)
    if kind == 1:
        return rng.uniform(-1e6, 1e6)
    if kind == 2:
        n = rng.randint(0, 24)
        return "".join(rng.choice("abcDEF123 _/\n\t\x00é") for _ in range(n))
    if kind == 3:
        return bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 16)))
    if kind == 4:
        return rng.choice([True, False])
    if kind == 5:
        return None
    return rng.choice([0, -1, 1, 2 ** 31, -(2 ** 31), 3.14, float("inf")])


def random_graph(rng, depth=4):
    """Build a random object graph mixing primitives, engine instances, and
    engine class references inside random containers."""
    instances, class_refs = _pool()
    if depth <= 0 or rng.random() < 0.35:
        pick = rng.random()
        if pick < 0.6 or not instances:
            return _random_primitive(rng)
        if pick < 0.85 or not class_refs:
            return rng.choice(instances)
        return rng.choice(class_refs)

    container = rng.randint(0, 3)
    size = rng.randint(0, 5)
    if container == 0:
        return [random_graph(rng, depth - 1) for _ in range(size)]
    if container == 1:
        return tuple(random_graph(rng, depth - 1) for _ in range(size))
    if container == 2:
        # dict with primitive keys (hashable) and arbitrary values
        return {_random_primitive(rng): random_graph(rng, depth - 1)
                for _ in range(size)}
    # set of primitives (must be hashable)
    return {_random_primitive(rng) for _ in range(size)}


# ---------------------------------------------------------------------------
# Adversarial payload crafting
# ---------------------------------------------------------------------------

def craft_global_pickle(module, name):
    """A minimal pickle that resolves ``module.name`` via find_class and stops.

    Uses the protocol-0 GLOBAL ('c') opcode, which pushes find_class(module,
    name) and returns it. No REDUCE, so nothing is *called* -- loading merely
    resolves the reference (safe to run in either mode).
    """
    return b"c" + module.encode() + b"\n" + name.encode() + b"\n."


class _EvilReduce:
    """On unpickle, would call ``os.mkdir(path)`` -- a detectable side effect.

    Only ever loaded in strict mode by this fuzzer, where the allow-list blocks
    the ``os.mkdir`` global before the reduce executes.
    """

    def __init__(self, path):
        self.path = path

    def __reduce__(self):
        import os as _os
        return (_os.mkdir, (self.path,))


def _random_disallowed_global(rng):
    """Return a (module, name) the strict-mode gate must reject."""
    if rng.random() < 0.5:
        pair = rng.choice(_DANGEROUS_GLOBALS)
    else:
        pair = (
            "".join(rng.choice("abcxyz._") for _ in range(rng.randint(1, 12))),
            "".join(rng.choice("ABCXYZ_") for _ in range(rng.randint(1, 10))),
        )
    return pair if not sp._is_allowed(*pair) else ("os", "system")


# ---------------------------------------------------------------------------
# Per-category invariant checks
# ---------------------------------------------------------------------------

def _check_benign(rng, seed, i):
    graph = random_graph(rng)
    data = sp.serialize_for_save(graph)
    findings = []
    # Legacy mode must not crash on a benign, allow-listed graph.
    try:
        sp.safe_pickle_load(io.BytesIO(data), strict=False)
    except Exception as exc:  # noqa: BLE001 - any error here is a finding
        findings.append(Finding(seed, i, "benign-legacy-crash",
                                f"{type(exc).__name__}: {exc}"))
    # Strict mode must either succeed or raise ONLY RestrictedUnpicklingError
    # (a rejection points at an allow-list gap, reported as info, not a crash).
    events = []
    try:
        sp.safe_pickle_load(io.BytesIO(data), strict=True, events=events)
    except sp.RestrictedUnpicklingError as exc:
        findings.append(Finding(seed, i, "strict-rejects-allowlisted",
                                f"allow-list gap: {exc}"))
    except Exception as exc:  # noqa: BLE001
        findings.append(Finding(seed, i, "strict-unexpected-error",
                                f"{type(exc).__name__}: {exc}"))
    return findings


def _check_disallowed_global(rng, seed, i):
    module, name = _random_disallowed_global(rng)
    data = sp.add_integrity_header(craft_global_pickle(module, name))
    try:
        sp.safe_pickle_load(io.BytesIO(data), strict=True)
    except sp.RestrictedUnpicklingError:
        return []  # correct: strict blocked the disallowed global
    except Exception as exc:  # noqa: BLE001
        return [Finding(seed, i, "disallowed-wrong-error",
                        f"{module}.{name} -> {type(exc).__name__}: {exc}")]
    return [Finding(seed, i, "disallowed-not-blocked",
                    f"strict mode resolved disallowed global {module}.{name}")]


def _check_malicious_reduce(rng, seed, i):
    tmp = tempfile.mkdtemp(prefix="hov_fuzz_")
    sentinel = os.path.join(tmp, "should_not_exist")
    data = sp.serialize_for_save(_EvilReduce(sentinel))
    findings = []
    try:
        sp.safe_pickle_load(io.BytesIO(data), strict=True)
        findings.append(Finding(seed, i, "reduce-not-blocked",
                                "strict mode did not block os.mkdir reduce"))
    except sp.RestrictedUnpicklingError:
        pass  # correct
    except Exception as exc:  # noqa: BLE001
        findings.append(Finding(seed, i, "reduce-wrong-error",
                                f"{type(exc).__name__}: {exc}"))
    if os.path.exists(sentinel):
        findings.append(Finding(seed, i, "reduce-side-effect-fired",
                                "malicious os.mkdir side effect executed!"))
    try:
        os.rmdir(sentinel)
    except OSError:
        pass
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    return findings


def _check_tamper(rng, seed, i):
    graph = random_graph(rng, depth=2)
    data = bytearray(sp.serialize_for_save(graph))
    if len(data) <= sp.HEADER_SIZE:
        return []
    # Flip a byte somewhere in the payload region (after the header) so the
    # sha256 must fail. Header-region flips fall back to legacy parsing and are
    # exercised in the dedicated unit test.
    idx = rng.randint(sp.HEADER_SIZE, len(data) - 1)
    data[idx] ^= 1 << rng.randint(0, 7)
    try:
        sp.safe_pickle_load(io.BytesIO(bytes(data)), strict=False)
    except sp.SaveIntegrityError:
        return []  # correct: checksum caught the tamper
    except Exception as exc:  # noqa: BLE001
        return [Finding(seed, i, "tamper-wrong-error",
                        f"{type(exc).__name__}: {exc}")]
    return [Finding(seed, i, "tamper-undetected",
                    "checksum did not detect a payload byte flip")]


def _check_oversize(rng, seed, i):
    blob = os.urandom(rng.randint(200, 2000))
    data = sp.serialize_for_save(blob)
    try:
        sp.safe_pickle_load(io.BytesIO(data), strict=False, max_bytes=64)
    except sp.SaveTooLargeError:
        return []
    except Exception as exc:  # noqa: BLE001
        return [Finding(seed, i, "oversize-wrong-error",
                        f"{type(exc).__name__}: {exc}")]
    return [Finding(seed, i, "oversize-not-rejected",
                    "payload above cap was not rejected")]


def _check_garbage(rng, seed, i):
    data = bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 128)))
    # For truly random bytes the invariant is only that the loader terminates
    # with a controlled exception rather than executing code or hanging. Malformed
    # pickle can raise a wide, version-dependent range of interpreter errors
    # (e.g. SystemError on bad bytearray buffer opcodes), so any Exception here is
    # acceptable; the targeted adversarial categories assert precise types.
    try:
        sp.safe_pickle_load(io.BytesIO(data), strict=False)
    except Exception:  # noqa: BLE001 - any controlled raise is a pass here
        return []
    return []  # a random blob that happens to be a valid pickle is fine


_CATEGORIES = (
    _check_benign,
    _check_disallowed_global,
    _check_malicious_reduce,
    _check_tamper,
    _check_oversize,
    _check_garbage,
)


def run_fuzz(iterations=500, seed=None):
    """Run the fuzzer and return a list of :class:`Finding` (empty == clean)."""
    if seed is None:
        seed = random.randrange(2 ** 32)
    rng = random.Random(seed)
    findings = []
    for i in range(iterations):
        check = rng.choice(_CATEGORIES)
        try:
            findings.extend(check(rng, seed, i))
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
        print(f"NOTE: {len(coverage)} allow-list coverage gap(s) "
              f"(tune _SAFE_STDLIB):")
        seen = set()
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
