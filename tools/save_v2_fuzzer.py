#!/usr/bin/env python3
"""Fuzzer for the data-only save format v2 loader (issue #293).

Complements ``tools/save_fuzzer.py`` (which fuzzes the *pickle* loader). This
tool targets the JSON/data-only path in :mod:`src.save_format`:

  * ``validate_save_data`` / ``loads_v2`` / ``read_v2_file`` -- schema + version
    validation against random and adversarial documents.
  * ``apply_data_to_player`` -- writing an untrusted document's scalars/stats/
    story-flags back onto a Player without corrupting its state.
  * ``player_to_data -> dumps_v2 -> loads_v2`` -- round-trip stability for any
    reachable (realistic) player state.

Security invariants (must be zero -- a violation is a real defect):

  * Any malformed document surfaces as ``SaveSchemaError`` (or validates); the
    loader never leaks a raw ``KeyError``/``TypeError``/``AttributeError`` etc.
  * ``apply_data_to_player`` never leaves the player in a corrupt state: no NaN/
    inf, no ``None`` scalar/stat, no negative HP/level/stat, correct types.
  * Strict validation rejects unknown top-level keys.
  * A realistic player round-trips: ``loads_v2(dumps_v2(...))`` validates.

Everything else is informational. This mirrors the Finding /
security-vs-coverage split and seeded-RNG CLI of ``tools/save_fuzzer.py``.

Usage:
    python tools/save_v2_fuzzer.py                    # 500 iterations, random seed
    python tools/save_v2_fuzzer.py --iterations 5000
    python tools/save_v2_fuzzer.py --seed 1337        # reproducible run
"""

import os
import sys
import json
import math
import random
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import save_format as sf  # noqa: E402

# Finding categories that indicate a genuine invariant breach (must be zero).
_SECURITY_CATEGORIES = frozenset({
    "validate-wrong-error",     # validate raised something other than SaveSchemaError
    "loads-wrong-error",        # loads_v2 raised something other than SaveSchemaError
    "strict-accepts-unknown",   # strict validation kept an unknown top-level key
    "strict-wrong-error",       # strict rejection used the wrong error type
    "apply-crash",              # apply_data_to_player raised an uncontrolled error
    "apply-corrupt-state",      # apply left the player NaN/None/negative/wrong-type
    "roundtrip-validate-fail",  # realistic player failed to round-trip
    "roundtrip-crash",          # round-trip raised unexpectedly
    "harness-error",            # the fuzzer itself blew up
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
    """Filter to genuine invariant breaches (must be empty)."""
    return [f for f in findings if f.is_security]


def coverage_findings(findings):
    """Filter to informational findings (non-breaches)."""
    return [f for f in findings if not f.is_security]


# ---------------------------------------------------------------------------
# A minimal, dependency-free stand-in for the engine Player
# ---------------------------------------------------------------------------

class _Universe:
    def __init__(self):
        self.story = {"gorran_first": "1"}


class _FuzzPlayer:
    """A lightweight object exposing exactly the attributes save_format reads.

    Using a real ``src.player.Player`` would drag in the whole engine/universe;
    ``save_format`` only touches scalar attributes, stats, ``preferences``,
    ``map``/``current_room``/``universe`` -- so a stand-in is sufficient and
    keeps the fuzzer a pure-``tests/`` unit with no Flask session.
    """

    def __init__(self):
        for key, default in sf._PLAYER_SCALARS.items():
            setattr(self, key, default)
        for stat in sf._PLAYER_STATS:
            setattr(self, stat, 10)
            setattr(self, f"{stat}_base", 10)
        self.preferences = {"arrow": "Wooden Arrow"}
        self.map = {"name": "Verdette"}
        self.current_room = type("Room", (), {"name": "The Crossing"})()
        self.universe = _Universe()


def _realistic_player(rng):
    """A player with random but *legitimate* (in-domain) scalar state."""
    p = _FuzzPlayer()
    p.name = rng.choice(["Jean", "Testy", "Crusader-é", ""])
    p.level = rng.randint(1, 60)
    p.hp = rng.randint(0, 5000)
    p.maxhp = rng.randint(1, 5000)
    p.fatigue = rng.randint(0, 2000)
    p.maxfatigue = rng.randint(1, 2000)
    p.heat = round(rng.uniform(0.0, 5.0), 3)
    p.protection = rng.randint(0, 100)
    p.time_elapsed = rng.randint(0, 10 ** 7)
    p.location_x = rng.randint(0, 50)
    p.location_y = rng.randint(0, 50)
    p.exp = rng.randint(0, 10 ** 6)
    p.pending_attribute_points = rng.randint(0, 20)
    for stat in sf._PLAYER_STATS:
        setattr(p, stat, rng.randint(1, 99))
        setattr(p, f"{stat}_base", rng.randint(1, 99))
    return p


# ---------------------------------------------------------------------------
# Random value / document generation
# ---------------------------------------------------------------------------

_HOSTILE_NUMBERS = [
    float("nan"), float("inf"), float("-inf"),
    -1, -999999, 0, 2 ** 63, -(2 ** 63), 10 ** 30, -1e18, 3.14,
]


def _random_json_value(rng, depth=3):
    """A random JSON-serializable value of arbitrary shape."""
    if depth <= 0 or rng.random() < 0.4:
        return rng.choice([
            rng.randint(-10 ** 9, 10 ** 9),
            rng.uniform(-1e6, 1e6),
            "".join(rng.choice("abcDEF123 _/\n\t\x00é")
                    for _ in range(rng.randint(0, 12))),
            True, False, None,
            rng.choice(_HOSTILE_NUMBERS),
        ])
    kind = rng.randint(0, 1)
    size = rng.randint(0, 4)
    if kind == 0:
        return [_random_json_value(rng, depth - 1) for _ in range(size)]
    return {"".join(rng.choice("abcxyz_0123") for _ in range(rng.randint(1, 6))):
            _random_json_value(rng, depth - 1) for _ in range(size)}


def _random_document(rng):
    """A random document that is *sometimes* a plausible save (arbitrary shape).

    Frequently missing keys / wrong versions / wrong nested types, occasionally
    not even a dict -- exercises validate_save_data's rejection paths.
    """
    roll = rng.random()
    if roll < 0.15:
        # Not a dict at all.
        return rng.choice([[1, 2, 3], "a string", 42, None, 3.14, True])
    doc = {}
    if rng.random() < 0.85:
        doc["format_version"] = rng.choice(
            [sf.SAVE_FORMAT_VERSION, sf.SAVE_FORMAT_VERSION, 0, 1, 999, "2",
             None, -1])
    if rng.random() < 0.85:
        doc["player"] = _random_maybe_player(rng)
    if rng.random() < 0.85:
        doc["world"] = _random_maybe_world(rng)
    if rng.random() < 0.3:
        doc["schema_version"] = rng.choice([1, 2, "x", None])
    if rng.random() < 0.3:
        doc[rng.choice(["evil", "extra", "smuggled"])] = _random_json_value(rng)
    return doc


def _random_maybe_player(rng):
    if rng.random() < 0.25:
        return rng.choice([[], "player", 5, None])
    p = {}
    for key in ("name", "level", "hp", "maxhp"):
        if rng.random() < 0.8:
            p[key] = rng.choice([_random_json_value(rng),
                                 rng.choice(_HOSTILE_NUMBERS), "Jean", 10])
    if rng.random() < 0.5:
        p["stats"] = rng.choice([
            {s: rng.choice(_HOSTILE_NUMBERS) for s in sf._PLAYER_STATS},
            {"bogus_key": 5, "strength": "notanumber"},
            [1, 2, 3], "stats", None,
        ])
    if rng.random() < 0.3:
        p["preferences"] = rng.choice([{"arrow": "x"}, [1], "p", None])
    return p


def _random_maybe_world(rng):
    if rng.random() < 0.25:
        return rng.choice([[], "world", 7, None])
    w = {}
    if rng.random() < 0.8:
        w["map_name"] = rng.choice(["Verdette", 5, None, ["x"]])
    if rng.random() < 0.5:
        w["story_flags"] = rng.choice([
            {"flag": "1"}, {i: i for i in range(rng.randint(0, 50))},
            [1, 2], "flags", None,
        ])
    return w


def _hostile_valid_document(rng):
    """A *schema-valid* document (required keys present) whose values are
    hostile -- the payload apply_data_to_player must survive and sanitize."""
    player = {"name": rng.choice(["Jean", 5, None, ["x"]]),
              "level": rng.choice(_HOSTILE_NUMBERS),
              "hp": rng.choice(_HOSTILE_NUMBERS),
              "maxhp": rng.choice(_HOSTILE_NUMBERS)}
    for key in sf._PLAYER_SCALARS:
        if rng.random() < 0.6:
            player[key] = rng.choice(
                _HOSTILE_NUMBERS + [None, "str", [1], {"a": 1}, True])
    if rng.random() < 0.8:
        stats = {}
        for stat in sf._PLAYER_STATS:
            stats[stat] = rng.choice(_HOSTILE_NUMBERS + [None, "x", [1]])
            stats[f"{stat}_base"] = rng.choice(_HOSTILE_NUMBERS + [None])
        # Sometimes inject unexpected/gigantic keys.
        if rng.random() < 0.5:
            stats["__evil__"] = 999
            stats["hp"] = -5
        player["stats"] = stats
    if rng.random() < 0.5:
        player["preferences"] = {"arrow": "x"}
    world = {"map_name": rng.choice(["Verdette", 5, None]),
             "story_flags": {str(i): i for i in range(rng.randint(0, 200))}}
    return {
        "format_version": sf.SAVE_FORMAT_VERSION,
        "schema_version": sf.SAVE_SCHEMA_VERSION,
        "player": player,
        "world": world,
    }


# ---------------------------------------------------------------------------
# Player-state invariant check (post-apply)
# ---------------------------------------------------------------------------

def _player_state_problems(player):
    """Return a list of corruption problems, or ``[]`` when the player is clean."""
    problems = []
    for key in sf._PLAYER_SCALARS:
        val = getattr(player, key)
        if key in sf._STRING_SCALARS:
            if not isinstance(val, str):
                problems.append(f"{key} not str: {val!r}")
            continue
        if val is None:
            problems.append(f"{key} is None")
        elif isinstance(val, bool):
            problems.append(f"{key} is bool")
        elif not isinstance(val, (int, float)):
            problems.append(f"{key} wrong type: {type(val).__name__}")
        elif isinstance(val, float) and not math.isfinite(val):
            problems.append(f"{key} not finite: {val}")
        elif val < sf._SCALAR_FLOORS.get(key, 0):
            problems.append(f"{key} below floor: {val}")
    for stat in sf._PLAYER_STATS:
        for name in (stat, f"{stat}_base"):
            val = getattr(player, name)
            if val is None:
                problems.append(f"{name} is None")
            elif isinstance(val, bool):
                problems.append(f"{name} is bool")
            elif not isinstance(val, (int, float)):
                problems.append(f"{name} wrong type: {type(val).__name__}")
            elif isinstance(val, float) and not math.isfinite(val):
                problems.append(f"{name} not finite: {val}")
            elif val < 0:
                problems.append(f"{name} negative: {val}")
    return problems


# ---------------------------------------------------------------------------
# Per-category invariant checks
# ---------------------------------------------------------------------------

def _check_validate_random(rng, seed, i):
    doc = _random_document(rng)
    strict = rng.random() < 0.5
    try:
        sf.validate_save_data(doc, strict=strict)
    except sf.SaveSchemaError:
        return []  # correct: malformed doc rejected cleanly
    except Exception as exc:  # noqa: BLE001
        return [Finding(seed, i, "validate-wrong-error",
                        f"strict={strict} {type(exc).__name__}: {exc} "
                        f"doc={doc!r:.200}")]
    return []  # validated -> it was a well-formed doc, fine


def _check_loads_garbage(rng, seed, i):
    if rng.random() < 0.5:
        # Random (usually invalid) text.
        text = "".join(rng.choice("{}[]\":,abc012 \n\txyz")
                       for _ in range(rng.randint(0, 60)))
    else:
        # Valid JSON of an arbitrary shape.
        text = json.dumps(_random_json_value(rng))
    try:
        sf.loads_v2(text, strict=rng.random() < 0.5)
    except sf.SaveSchemaError:
        return []
    except Exception as exc:  # noqa: BLE001
        return [Finding(seed, i, "loads-wrong-error",
                        f"{type(exc).__name__}: {exc} text={text!r:.120}")]
    return []


def _check_strict_unknown(rng, seed, i):
    doc = sf.player_to_data(_realistic_player(rng))
    doc[rng.choice(["evil", "extra", "smuggled_field"])] = _random_json_value(rng)
    findings = []
    # Non-strict tolerates the extra key.
    try:
        sf.validate_save_data(doc, strict=False)
    except Exception as exc:  # noqa: BLE001
        findings.append(Finding(seed, i, "validate-wrong-error",
                                f"non-strict rejected extra key: "
                                f"{type(exc).__name__}: {exc}"))
    # Strict must reject it with SaveSchemaError.
    try:
        sf.validate_save_data(doc, strict=True)
        findings.append(Finding(seed, i, "strict-accepts-unknown",
                                "strict validation kept an unknown top-level key"))
    except sf.SaveSchemaError:
        pass  # correct
    except Exception as exc:  # noqa: BLE001
        findings.append(Finding(seed, i, "strict-wrong-error",
                                f"{type(exc).__name__}: {exc}"))
    return findings


def _check_apply_hostile(rng, seed, i):
    doc = _hostile_valid_document(rng)
    player = _realistic_player(rng)
    try:
        sf.apply_data_to_player(player, doc)
    except sf.SaveSchemaError:
        return []  # a documented, controlled rejection is acceptable
    except Exception as exc:  # noqa: BLE001
        return [Finding(seed, i, "apply-crash",
                        f"{type(exc).__name__}: {exc}")]
    problems = _player_state_problems(player)
    if problems:
        return [Finding(seed, i, "apply-corrupt-state", "; ".join(problems))]
    return []


def _check_roundtrip(rng, seed, i):
    player = _realistic_player(rng)
    try:
        text = sf.dumps_v2(player)
        data = sf.loads_v2(text, strict=True)
    except Exception as exc:  # noqa: BLE001
        return [Finding(seed, i, "roundtrip-crash",
                        f"{type(exc).__name__}: {exc}")]
    findings = []
    if data["player"]["level"] != player.level:
        findings.append(Finding(seed, i, "roundtrip-validate-fail",
                                f"level {data['player']['level']} != {player.level}"))
    # Applying a clean round-trip must leave the player clean and faithful.
    target = _realistic_player(rng)
    try:
        sf.apply_data_to_player(target, data)
    except Exception as exc:  # noqa: BLE001
        return findings + [Finding(seed, i, "apply-crash",
                                   f"round-trip apply: {type(exc).__name__}: {exc}")]
    problems = _player_state_problems(target)
    if problems:
        findings.append(Finding(seed, i, "apply-corrupt-state",
                                "round-trip: " + "; ".join(problems)))
    # Faithful restore of an in-domain value (no clamping should have occurred).
    if target.level != player.level:
        findings.append(Finding(seed, i, "roundtrip-validate-fail",
                                f"restored level {target.level} != {player.level}"))
    return findings


_CATEGORIES = (
    _check_validate_random,
    _check_loads_garbage,
    _check_strict_unknown,
    _check_apply_hostile,
    _check_roundtrip,
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
        print(f"NOTE: {len(coverage)} informational finding(s):")
        seen = set()
        for f in coverage:
            if f.detail not in seen:
                seen.add(f.detail)
                print("  " + str(f))

    if security:
        print(f"FAIL: {len(security)} invariant violation(s):")
        for f in security[:50]:
            print("  " + str(f))
        return 1
    print(f"OK: {args.iterations} iterations, no invariant violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
