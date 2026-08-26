"""Fuzz test for the data-only save format v2 loader (issue #293).

Drives ``tools/save_v2_fuzzer.py``, which feeds random and adversarial JSON
documents through ``validate_save_data`` / ``loads_v2`` / ``apply_data_to_player``
and round-trips realistic player state through ``player_to_data -> dumps_v2 ->
loads_v2``. The hard assertion is **zero security-invariant violations**:

  * malformed documents surface as ``SaveSchemaError`` (never a raw
    ``KeyError``/``TypeError``/``AttributeError``);
  * ``apply_data_to_player`` never leaves the player NaN/None/negative/wrong-type;
  * strict validation rejects unknown top-level keys;
  * realistic players round-trip and restore faithfully.

The fuzzer module is loaded by file path (it is a tools/ script, not an
importable package), matching ``tests/test_save_fuzz.py``.
"""

import importlib.util
import random
from pathlib import Path

import pytest

import src.save_format as sf

_ROOT = Path(__file__).resolve().parents[1]


def _load_fuzzer():
    path = _ROOT / "tools" / "save_v2_fuzzer.py"
    spec = importlib.util.spec_from_file_location("_save_v2_fuzzer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fuzzer = _load_fuzzer()


@pytest.mark.parametrize("seed", [1, 1337, 20240101, 98765])
def test_fuzz_no_security_violations(seed):
    findings = fuzzer.run_fuzz(iterations=400, seed=seed)
    security = fuzzer.security_findings(findings)
    assert not security, "\n".join(str(f) for f in security)


# ---------------------------------------------------------------------------
# Targeted regression checks for the hardening this issue added.
# ---------------------------------------------------------------------------

def _fresh_player():
    return fuzzer._realistic_player(random.Random(0))


def test_loads_v2_wraps_invalid_json():
    with pytest.raises(sf.SaveSchemaError):
        sf.loads_v2("{not valid json")
    with pytest.raises(sf.SaveSchemaError):
        sf.loads_v2("")


def test_apply_rejects_nan_and_inf_hp():
    player = _fresh_player()
    player.hp = 123
    doc = {
        "format_version": sf.SAVE_FORMAT_VERSION,
        "schema_version": sf.SAVE_SCHEMA_VERSION,
        "player": {"name": "Jean", "level": 1, "hp": float("nan"),
                   "maxhp": float("inf")},
        "world": {"map_name": "m"},
    }
    sf.apply_data_to_player(player, doc)
    import math
    assert math.isfinite(player.hp) and player.hp >= 0
    assert math.isfinite(player.maxhp) and player.maxhp >= 1


def test_apply_clamps_negatives_to_floor():
    player = _fresh_player()
    doc = {
        "format_version": sf.SAVE_FORMAT_VERSION,
        "schema_version": sf.SAVE_SCHEMA_VERSION,
        "player": {"name": "Jean", "level": -50, "hp": -999, "maxhp": -1},
        "world": {"map_name": "m"},
    }
    sf.apply_data_to_player(player, doc)
    assert player.level == 1      # floor
    assert player.hp == 0         # floor
    assert player.maxhp == 1      # floor


def test_apply_clamps_overflow_to_ceiling():
    player = _fresh_player()
    doc = {
        "format_version": sf.SAVE_FORMAT_VERSION,
        "schema_version": sf.SAVE_SCHEMA_VERSION,
        "player": {"name": "Jean", "level": 10 ** 40, "hp": 100, "maxhp": 100},
        "world": {"map_name": "m"},
    }
    sf.apply_data_to_player(player, doc)
    assert player.level == sf._SCALAR_CEILING


def test_apply_rejects_non_string_name():
    player = _fresh_player()
    player.name = "Jean"
    doc = {
        "format_version": sf.SAVE_FORMAT_VERSION,
        "schema_version": sf.SAVE_SCHEMA_VERSION,
        "player": {"name": ["not", "a", "string"], "level": 1, "hp": 1,
                   "maxhp": 1},
        "world": {"map_name": "m"},
    }
    sf.apply_data_to_player(player, doc)
    assert player.name == "Jean"  # rejected, prior value kept


def test_apply_ignores_unexpected_stat_keys():
    player = _fresh_player()
    doc = {
        "format_version": sf.SAVE_FORMAT_VERSION,
        "schema_version": sf.SAVE_SCHEMA_VERSION,
        "player": {"name": "Jean", "level": 1, "hp": 1, "maxhp": 1,
                   "stats": {"__evil__": 999, "strength": 20}},
        "world": {"map_name": "m"},
    }
    sf.apply_data_to_player(player, doc)
    assert not hasattr(player, "__evil__")
    assert player.strength == 20


def test_apply_rejects_string_stat_value():
    player = _fresh_player()
    player.strength = 12
    doc = {
        "format_version": sf.SAVE_FORMAT_VERSION,
        "schema_version": sf.SAVE_SCHEMA_VERSION,
        "player": {"name": "Jean", "level": 1, "hp": 1, "maxhp": 1,
                   "stats": {"strength": "notanumber"}},
        "world": {"map_name": "m"},
    }
    sf.apply_data_to_player(player, doc)
    assert player.strength == 12  # rejected, prior value kept


def test_apply_survives_non_dict_stats():
    player = _fresh_player()
    doc = {
        "format_version": sf.SAVE_FORMAT_VERSION,
        "schema_version": sf.SAVE_SCHEMA_VERSION,
        "player": {"name": "Jean", "level": 1, "hp": 1, "maxhp": 1,
                   "stats": [1, 2, 3]},
        "world": {"map_name": "m"},
    }
    # Non-dict stats are skipped entirely: the scalars still apply, and every
    # stat keeps the value it had before the load.
    before = {s: getattr(player, s) for s in sf._ALLOWED_STAT_KEYS}
    sf.apply_data_to_player(player, doc)
    assert player.hp == 1 and player.level == 1
    assert {s: getattr(player, s) for s in sf._ALLOWED_STAT_KEYS} == before


# ---------------------------------------------------------------------------
# Meta-tests on the fuzzer itself.
#
# A fuzzer that cannot fail is a no-op that costs 400 iterations per seed. These
# pin the two properties that make the assertion above mean something: the run
# is reproducible from its seed, and an injected defect really is reported as a
# security finding.
# ---------------------------------------------------------------------------

def test_fuzz_run_is_deterministic_for_a_seed():
    first = fuzzer.run_fuzz(iterations=120, seed=4242)
    second = fuzzer.run_fuzz(iterations=120, seed=4242)
    assert [str(f) for f in first] == [str(f) for f in second]


def test_fuzz_run_actually_varies_between_seeds():
    """Different seeds must drive different documents, or the coverage is one case."""
    import json as _json

    rng_a, rng_b = random.Random(1), random.Random(2)
    docs_a = [_json.dumps(fuzzer._random_document(rng_a), default=str)
              for _ in range(40)]
    docs_b = [_json.dumps(fuzzer._random_document(rng_b), default=str)
              for _ in range(40)]
    assert docs_a != docs_b
    assert len(set(docs_a)) > 20, "generator is producing near-identical documents"


def test_fuzzer_detects_a_broken_sanitizer(monkeypatch):
    """Injected defect: stop sanitizing scalars -> corrupt-state findings appear.

    Without this, ``test_fuzz_no_security_violations`` passing proves nothing --
    it would pass just as happily against a fuzzer whose checks never fire.
    """
    monkeypatch.setattr(
        sf, "_sanitize_scalar",
        lambda key, value, template, current: value,
    )
    findings = fuzzer.security_findings(fuzzer.run_fuzz(iterations=400, seed=7))
    assert findings, "fuzzer failed to notice an unsanitized scalar restore"
    assert {f.category for f in findings} == {"apply-corrupt-state"}


def test_fuzzer_detects_a_leaked_raw_exception(monkeypatch):
    """Injected defect: validation raises KeyError instead of SaveSchemaError."""
    real_validate = sf.validate_save_data

    def leaky(data, *, strict=False):
        try:
            return real_validate(data, strict=strict)
        except sf.SaveSchemaError as exc:
            raise KeyError(str(exc)) from None

    monkeypatch.setattr(sf, "validate_save_data", leaky)
    findings = fuzzer.security_findings(fuzzer.run_fuzz(iterations=300, seed=11))
    assert findings, "fuzzer failed to notice a leaked raw exception type"
    assert {"validate-wrong-error", "loads-wrong-error"} & {
        f.category for f in findings}


def test_fuzzer_restores_cleanly_after_the_injected_defects():
    """The monkeypatched defects above must not bleed into later runs."""
    assert not fuzzer.security_findings(fuzzer.run_fuzz(iterations=200, seed=7))
