"""Fuzz test for the config INI parser (issue #294).

Drives tools/config_fuzzer.py, which feeds ConfigManager.load() a mix of
structurally random INI text and raw random byte blobs (malformed sections,
duplicate keys, BOM/CRLF, inline-comment edge cases, interpolation-hostile
``%`` values, non-numeric / overflow / inf / nan numeric fields, unknown NPC
class names, ``flag=value=extra`` story tokens, and pure garbage) and asserts
the loader's contract:

  * ``load()`` NEVER raises -- any input degrades to a valid ``GameConfig``.
  * ``startposition`` / ``coordinate_grid_size`` are always 2-tuples of ``int``.
  * ``coordinate_grid_size`` components are always positive.
  * No ``getfloat``-backed field ever ends up ``inf``/``nan``.
  * ``starting_story_flags`` / ``starting_party_members`` are always
    ``list[str]``.

The fuzzer module is loaded by file path (it is a tools/ script, not an
importable package), matching the pattern used by tests/test_save_fuzz.py.
"""

import importlib.util
from pathlib import Path

import pytest

from src.config_manager import ConfigManager, GameConfig

_ROOT = Path(__file__).resolve().parents[1]


def _load_fuzzer():
    path = _ROOT / "tools" / "config_fuzzer.py"
    spec = importlib.util.spec_from_file_location("_config_fuzzer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fuzzer = _load_fuzzer()


@pytest.mark.parametrize("seed", [1, 1337, 42, 20240101])
def test_fuzz_no_invariant_violations(seed):
    """Seeded, reproducible: no input breaks the loader's contract."""
    findings = fuzzer.run_fuzz(iterations=400, seed=seed)
    assert not findings, "\n".join(str(f) for f in findings)


def test_load_never_raises_on_random_bytes(tmp_path):
    """A file of pure random bytes must still yield a valid GameConfig."""
    import random

    rng = random.Random(98765)
    path = tmp_path / "garbage.ini"
    for _ in range(200):
        path.write_bytes(fuzzer.random_bytes_blob(rng))
        cfg = ConfigManager(str(path)).load()
        assert isinstance(cfg, GameConfig)


def test_load_never_raises_on_random_ini_text(tmp_path):
    """Structurally random INI text must never crash the parser."""
    import random

    rng = random.Random(54321)
    path = tmp_path / "fuzz.ini"
    for _ in range(200):
        text = fuzzer.random_ini_text(rng)
        path.write_text(text, encoding="utf-8", errors="surrogatepass")
        cfg = ConfigManager(str(path)).load()
        assert isinstance(cfg, GameConfig)
        # Hand-parsed tuple fields keep their arity/type contract.
        assert isinstance(cfg.startposition, tuple) and len(cfg.startposition) == 2
        assert isinstance(cfg.coordinate_grid_size, tuple)
        assert len(cfg.coordinate_grid_size) == 2
        w, h = cfg.coordinate_grid_size
        assert w > 0 and h > 0


@pytest.mark.parametrize(
    "value",
    [
        "",             # empty
        "   ",          # whitespace only
        "1",            # too few components
        "1,2,3",        # too many components
        "x,y",          # non-numeric
        "(1, 2)",       # parenthesized (valid)
        "  ( 3 , 4 ) ",  # parens + whitespace (valid)
        "99999999999999999999,1",  # huge int
        "-5,-5",        # negative (valid tuple, just negative)
        "1e10,1e10",    # float-looking (invalid int)
        ",",            # empty components
    ],
)
def test_startposition_always_int_pair(tmp_path, value):
    path = tmp_path / "sp.ini"
    path.write_text(f"[game]\nstartposition = {value}\n")
    cfg = ConfigManager(str(path)).load()
    assert isinstance(cfg.startposition, tuple) and len(cfg.startposition) == 2
    assert all(isinstance(c, int) for c in cfg.startposition)


@pytest.mark.parametrize(
    "value",
    ["", "0,0", "-1,-1", "1,2,3", "x,y", "abc", "10", "1e5,1e5"],
)
def test_coordinate_grid_size_always_positive_int_pair(tmp_path, value):
    path = tmp_path / "grid.ini"
    path.write_text(f"[game]\ncoordinate_grid_size = {value}\n")
    cfg = ConfigManager(str(path)).load()
    assert isinstance(cfg.coordinate_grid_size, tuple)
    assert len(cfg.coordinate_grid_size) == 2
    w, h = cfg.coordinate_grid_size
    assert isinstance(w, int) and isinstance(h, int)
    assert w > 0 and h > 0


@pytest.mark.parametrize(
    "value",
    ["inf", "-inf", "nan", "NaN", "Infinity", "1e400", "abc", "", "%"],
)
def test_float_fields_never_non_finite(tmp_path, value):
    import math

    path = tmp_path / "f.ini"
    path.write_text(
        f"[game]\nanimation_speed = {value}\n"
        f"[combat_testing]\ndifficulty_scaling = {value}\n"
    )
    cfg = ConfigManager(str(path)).load()
    assert math.isfinite(cfg.animation_speed)
    assert math.isfinite(cfg.difficulty_scaling)


def test_duplicate_keys_and_sections_do_not_crash(tmp_path):
    path = tmp_path / "dup.ini"
    path.write_text(
        "[game]\n"
        "testmode = true\n"
        "testmode = false\n"
        "[game]\n"
        "skipdialog = true\n"
    )
    cfg = ConfigManager(str(path)).load()
    assert isinstance(cfg, GameConfig)


def test_interpolation_hostile_percent_value(tmp_path):
    """A stray ``%`` in a value must not raise (interpolation disabled)."""
    path = tmp_path / "pct.ini"
    path.write_text("[game]\nstartmap = 100%_complete\nlog_file = a%(b)s\n")
    cfg = ConfigManager(str(path)).load()
    assert isinstance(cfg, GameConfig)
    assert cfg.startmap == "100%_complete"


def test_story_flag_value_extra_token(tmp_path):
    """``flag=value=extra`` tokens parse as opaque strings, never crash."""
    path = tmp_path / "flags.ini"
    path.write_text(
        "[game]\n"
        "starting_story_flags = a, flag=value=extra, , b\n"
        "starting_party_members = Gorran, NotARealClass, \n"
    )
    cfg = ConfigManager(str(path)).load()
    assert isinstance(cfg.starting_story_flags, list)
    assert all(isinstance(f, str) for f in cfg.starting_story_flags)
    assert "" not in cfg.starting_story_flags  # empty tokens dropped
    assert isinstance(cfg.starting_party_members, list)
    assert all(isinstance(m, str) for m in cfg.starting_party_members)


def test_bom_and_crlf(tmp_path):
    path = tmp_path / "bom.ini"
    path.write_bytes(b"\xef\xbb\xbf[game]\r\ntestmode = true\r\n")
    cfg = ConfigManager(str(path)).load()
    assert isinstance(cfg, GameConfig)
