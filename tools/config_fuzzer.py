#!/usr/bin/env python3
"""Config-INI fuzzer for Heart of Virtue (issue #294).

Feeds ``src.config_manager.ConfigManager.load()`` a mix of structurally
random INI text and raw random byte blobs, focusing on the hand-parsed
fields (``startposition``, ``coordinate_grid_size``, the comma-split
``starting_story_flags``/``starting_party_members`` lists) plus the many
``getboolean``/``getint``/``getfloat`` fields, and asserts the loader's
invariants:

  * ``load()`` **never raises**, for any input -- malformed INI, non-UTF8
    bytes, duplicate keys/sections, missing sections, unknown keys,
    interpolation-hostile values (``%``), or pure garbage all degrade to a
    valid ``GameConfig`` with sane fallback values.
  * ``startposition`` / ``coordinate_grid_size`` are always 2-tuples of
    ``int``.
  * ``coordinate_grid_size`` components are always positive (a
    non-positive grid is nonsensical and would break downstream bounds
    math).
  * No ``getfloat``-backed field ever ends up ``inf``/``nan``.
  * ``starting_story_flags`` / ``starting_party_members`` are always
    ``list[str]`` (unknown NPC class names / malformed flag tokens are not
    validated at parse time -- that happens downstream -- but parsing
    itself must never choke on them).

This target is not security-sensitive (a malformed config file is not an
attacker-controlled trust boundary the way a save file is), so the bar is a
simple pass/fail on "the loader stayed within its documented contract" --
no strict/legacy split, no allow-list. The seeded, reproducible structure
and ``Finding`` record mirror ``tools/save_fuzzer.py``.

Usage:
    python tools/config_fuzzer.py                     # 500 iterations, random seed
    python tools/config_fuzzer.py --iterations 5000
    python tools/config_fuzzer.py --seed 1337          # reproducible run
"""

import os
import sys
import math
import random
import argparse
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config_manager import ConfigManager, GameConfig  # noqa: E402


class Finding:
    """An invariant violation, carrying enough context to reproduce it."""

    def __init__(self, seed, iteration, category, detail):
        self.seed = seed
        self.iteration = iteration
        self.category = category
        self.detail = detail

    def __str__(self):
        return (
            f"[seed={self.seed} iter={self.iteration} {self.category}] "
            f"{self.detail}"
        )


# ---------------------------------------------------------------------------
# Random value pools targeting the hand-parsed fields
# ---------------------------------------------------------------------------

_NASTY_TOKENS = [
    "", " ", "   ", "0", "-1", "abc", "1.5", "1e400", "inf", "-inf", "nan",
    "NaN", "Infinity", "true", "false", "TRUE", "yes", "no", "on", "off",
    "%", "%%", "%(bogus)s", "100%", "50%off", "a=b=c", "flag=value=extra",
    "\t", "\n", "\x00", "é", "日本語", "١٢٣", "🎮", "-" * 20,
    "9" * 400, str(2 ** 64), str(-(2 ** 64)), "0x10", "1_000", ",", ",,",
    "(", ")", "()", "( )", "(1,2)", "1,2,3,4", "1", "1,", ",1", "1 , 2",
    "-5,-5", "0,0", "99999999999999999999,1", "1,99999999999999999999",
    "1e10,1e10", "x,y", "1,2,3",
]

_SECTION_NAMES = [
    "game", "development", "combat_testing", "testing_locations",
    "GAME", "Game", "unknown_section", "", "game ", " game",
]

_GAME_KEYS = [
    "testmode", "skipdialog", "skipintro", "startmap", "startposition",
    "use_colour", "enable_animations", "animation_speed", "starting_exp",
    "debug_mode", "coordinate_grid_size", "ai_difficulty",
    "starting_story_flags", "starting_party_members", "log_file",
    "test_scenario", "max_enemies_standard", "grid_display_interval",
    "unknown_key_xyz", "STARTPOSITION", "startPosition",
]

_COMBAT_TESTING_KEYS = [
    "starting_difficulty", "difficulty_scaling", "npc_decision_delay",
    "npc_flanking_threshold", "npc_retreat_health_threshold",
    "npc_flanking_distance_range", "validate_grid_bounds",
]


def _random_value(rng):
    """A random raw value string, biased toward known-nasty tokens."""
    if rng.random() < 0.6:
        return rng.choice(_NASTY_TOKENS)
    kind = rng.randint(0, 3)
    if kind == 0:
        return str(rng.randint(-(10 ** 12), 10 ** 12))
    if kind == 1:
        return str(rng.uniform(-1e12, 1e12))
    n = rng.randint(0, 40)
    charset = "abcXYZ019 _,.()%=;#\t日é\x00"
    return "".join(rng.choice(charset) for _ in range(n))


def random_ini_text(rng):
    """Build structurally random INI text: random sections/keys/values,
    duplicate keys/sections, BOM, CRLF, and inline-comment edge cases."""
    lines = []
    if rng.random() < 0.1:
        lines.append("﻿")  # BOM, glued onto the first line below

    n_sections = rng.randint(0, 5)
    newline = "\r\n" if rng.random() < 0.3 else "\n"
    for _ in range(n_sections):
        section = rng.choice(_SECTION_NAMES)
        lines.append(f"[{section}]")
        n_keys = rng.randint(0, 8)
        key_pool = rng.choice([_GAME_KEYS, _COMBAT_TESTING_KEYS])
        for _ in range(n_keys):
            key = rng.choice(key_pool)
            value = _random_value(rng)
            sep = rng.choice(["=", " = ", "="])
            line = f"{key}{sep}{value}"
            if rng.random() < 0.2:
                comment = rng.choice([" ; trailing", " # trailing", ""])
                line += comment
            lines.append(line)
        if rng.random() < 0.15:
            # A duplicate section reopened later.
            lines.append(f"[{section}]")
            lines.append(f"{rng.choice(key_pool)}={_random_value(rng)}")
    if rng.random() < 0.1:
        # A stray malformed line with no '=' and no section header context.
        lines.append(rng.choice(["garbage line", "  indented=weird", "==="]))
    return newline.join(lines) + newline


def random_bytes_blob(rng):
    n = rng.randint(0, 400)
    return bytes(rng.randint(0, 255) for _ in range(n))


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------

def _check_tuple_arity(cfg, seed, i):
    findings = []
    for attr in ("startposition", "coordinate_grid_size"):
        value = getattr(cfg, attr)
        if not (isinstance(value, tuple) and len(value) == 2):
            findings.append(Finding(seed, i, "bad-tuple-arity",
                                     f"{attr}={value!r}"))
            continue
        x, y = value
        if not (isinstance(x, int) and isinstance(y, int)):
            findings.append(Finding(seed, i, "bad-tuple-type",
                                     f"{attr}={value!r}"))
    return findings


def _check_grid_size_positive(cfg, seed, i):
    w, h = cfg.coordinate_grid_size
    if w <= 0 or h <= 0:
        return [Finding(seed, i, "nonpositive-grid-size",
                         f"coordinate_grid_size={cfg.coordinate_grid_size!r}")]
    return []


_FLOAT_FIELDS = (
    "animation_speed", "difficulty_scaling", "npc_decision_delay",
    "npc_flanking_threshold", "npc_retreat_health_threshold",
)


def _check_floats_finite(cfg, seed, i):
    findings = []
    for attr in _FLOAT_FIELDS:
        value = getattr(cfg, attr)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            findings.append(Finding(seed, i, "non-finite-float",
                                     f"{attr}={value!r}"))
    return findings


def _check_list_fields(cfg, seed, i):
    findings = []
    for attr in ("starting_story_flags", "starting_party_members"):
        value = getattr(cfg, attr)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            findings.append(Finding(seed, i, "bad-list-field",
                                     f"{attr}={value!r}"))
    return findings


def _run_one(rng, seed, i, path):
    findings = []
    try:
        cfg = ConfigManager(str(path)).load()
    except Exception as exc:  # noqa: BLE001 - any raise here IS the finding
        return [Finding(seed, i, "load-raised", f"{type(exc).__name__}: {exc}")]

    if not isinstance(cfg, GameConfig):
        return [Finding(seed, i, "bad-return-type", f"{type(cfg).__name__}")]

    findings.extend(_check_tuple_arity(cfg, seed, i))
    # Only check grid-size positivity/float-finiteness if arity was sane --
    # otherwise the attribute access above already flagged the real bug.
    if isinstance(cfg.coordinate_grid_size, tuple) and len(cfg.coordinate_grid_size) == 2:
        findings.extend(_check_grid_size_positive(cfg, seed, i))
    findings.extend(_check_floats_finite(cfg, seed, i))
    findings.extend(_check_list_fields(cfg, seed, i))
    return findings


_STRATEGIES = ("structured_ini", "random_bytes", "empty_file")


def run_fuzz(iterations=500, seed=None):
    """Run the fuzzer and return a list of :class:`Finding` (empty == clean)."""
    if seed is None:
        seed = random.randrange(2 ** 32)
    rng = random.Random(seed)
    findings = []
    with tempfile.TemporaryDirectory(prefix="hov_config_fuzz_") as tmpdir:
        path = os.path.join(tmpdir, "fuzz.ini")
        for i in range(iterations):
            strategy = rng.choice(_STRATEGIES)
            try:
                if strategy == "structured_ini":
                    text = random_ini_text(rng)
                    with open(path, "w", encoding="utf-8", errors="surrogatepass") as f:
                        f.write(text)
                elif strategy == "random_bytes":
                    blob = random_bytes_blob(rng)
                    with open(path, "wb") as f:
                        f.write(blob)
                else:  # empty_file
                    open(path, "w").close()

                findings.extend(_run_one(rng, seed, i, path))
            except Exception as exc:  # noqa: BLE001 - the harness must not die
                findings.append(Finding(seed, i, "harness-error",
                                         f"{type(exc).__name__}: {exc}"))
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=None,
                         help="Fix the RNG seed for a reproducible run.")
    args = parser.parse_args(argv)

    findings = run_fuzz(args.iterations, args.seed)

    if findings:
        print(f"FAIL: {len(findings)} invariant violation(s):")
        for f in findings[:50]:
            print("  " + str(f))
        return 1
    print(f"OK: {args.iterations} iterations, no invariant violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
