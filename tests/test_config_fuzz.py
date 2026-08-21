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
    defaults = GameConfig()
    for _ in range(200):
        path.write_bytes(fuzzer.random_bytes_blob(rng))
        cfg = ConfigManager(str(path)).load()
        # Not just "a GameConfig came back": random bytes carry no settings, so
        # every field must still hold its documented default. A loader that
        # half-parsed garbage into real fields would pass the isinstance check.
        assert cfg == defaults


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


# (raw value, exact parsed startposition). Malformed input degrades to the
# (0, 0) origin; anything int-parseable is honoured verbatim, parens and
# whitespace included. Pinning the *value*, not just the shape, is what makes
# this catch a parser that silently drops a valid coordinate.
_STARTPOSITION_CASES = [
    ("", (0, 0)),                            # empty
    ("   ", (0, 0)),                         # whitespace only
    ("1", (0, 0)),                           # too few components
    ("1,2,3", (0, 0)),                       # too many components
    ("x,y", (0, 0)),                         # non-numeric
    (",", (0, 0)),                           # empty components
    ("1e10,1e10", (0, 0)),                   # float-looking (invalid int)
    ("4,7", (4, 7)),                         # the ordinary case
    ("(1, 2)", (1, 2)),                      # parenthesized
    ("  ( 3 , 4 ) ", (3, 4)),                # parens + whitespace
    ("99999999999999999999,1", (99999999999999999999, 1)),  # huge int
    ("-5,-5", (-5, -5)),                     # negative is a legal tile coord
]


@pytest.mark.parametrize("value,expected", _STARTPOSITION_CASES)
def test_startposition_parses_to_exact_int_pair(tmp_path, value, expected):
    path = tmp_path / "sp.ini"
    path.write_text(f"[game]\nstartposition = {value}\n")
    cfg = ConfigManager(str(path)).load()
    assert cfg.startposition == expected
    assert all(isinstance(c, int) for c in cfg.startposition)


_DEFAULT_GRID = (50, 50)

# Grid size must stay strictly positive: a zero/negative grid would divide by
# zero downstream, so every degenerate spelling falls back to the default.
_GRID_CASES = [
    ("", _DEFAULT_GRID),
    ("0,0", _DEFAULT_GRID),        # zero is not a usable grid
    ("-1,-1", _DEFAULT_GRID),      # negative is not a usable grid
    ("1,2,3", _DEFAULT_GRID),
    ("x,y", _DEFAULT_GRID),
    ("abc", _DEFAULT_GRID),
    ("10", _DEFAULT_GRID),         # single component
    ("1e5,1e5", _DEFAULT_GRID),    # float-looking
    ("7,9", (7, 9)),               # the ordinary case
    ("1,1", (1, 1)),               # smallest legal grid
]


@pytest.mark.parametrize("value,expected", _GRID_CASES)
def test_coordinate_grid_size_parses_to_exact_positive_pair(
    tmp_path, value, expected
):
    path = tmp_path / "grid.ini"
    path.write_text(f"[game]\ncoordinate_grid_size = {value}\n")
    cfg = ConfigManager(str(path)).load()
    assert cfg.coordinate_grid_size == expected
    w, h = cfg.coordinate_grid_size
    assert isinstance(w, int) and isinstance(h, int)
    assert w > 0 and h > 0


@pytest.mark.parametrize(
    "value",
    ["inf", "-inf", "nan", "NaN", "Infinity", "1e400", "abc", "", "%"],
)
def test_non_finite_float_fields_fall_back_to_defaults(tmp_path, value):
    import math

    defaults = GameConfig()
    path = tmp_path / "f.ini"
    path.write_text(
        f"[game]\nanimation_speed = {value}\n"
        f"[combat_testing]\nnpc_decision_delay = {value}\n"
    )
    cfg = ConfigManager(str(path)).load()
    assert math.isfinite(cfg.animation_speed)
    assert math.isfinite(cfg.npc_decision_delay)
    # Rejected values must land on the documented defaults, not on 0.0 —
    # a 0.0 npc_decision_delay would silently change combat pacing.
    assert cfg.animation_speed == defaults.animation_speed
    assert cfg.npc_decision_delay == defaults.npc_decision_delay


def test_finite_float_fields_are_honoured(tmp_path):
    """The rejection path above must not swallow legitimate values."""
    path = tmp_path / "ok.ini"
    path.write_text(
        "[game]\nanimation_speed = 2.5\n"
        "[combat_testing]\nnpc_decision_delay = 0.25\n"
    )
    cfg = ConfigManager(str(path)).load()
    assert cfg.animation_speed == 2.5
    assert cfg.npc_decision_delay == 0.25


def test_duplicate_keys_and_sections_resolve_last_wins(tmp_path):
    """strict=False keeps the file usable: the last spelling of a key wins."""
    path = tmp_path / "dup.ini"
    path.write_text(
        "[game]\n"
        "testmode = true\n"
        "testmode = false\n"
        "[game]\n"
        "skipdialog = true\n"
    )
    cfg = ConfigManager(str(path)).load()
    assert cfg.testmode is False       # second `testmode` overrides the first
    assert cfg.skipdialog is True      # the repeated [game] section is merged


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


def test_bom_and_crlf_settings_are_not_silently_dropped(tmp_path):
    """A UTF-8 BOM (what Windows editors / PowerShell write) must still parse.

    Regression: the loader read with ``encoding="utf-8"``, so the BOM became a
    literal prefix on the first section header, configparser raised
    MissingSectionHeaderError, and the whole config silently degraded to
    defaults — the game would boot on the wrong map with no warning.
    """
    path = tmp_path / "bom.ini"
    path.write_bytes(
        b"\xef\xbb\xbf[game]\r\ntestmode = true\r\nstartmap = dark-grotto\r\n"
    )
    cfg = ConfigManager(str(path)).load()
    assert cfg.testmode is True
    assert cfg.startmap == "dark-grotto"


def test_undecodable_bytes_degrade_to_defaults(tmp_path):
    """Truly unreadable files still fall back rather than raising."""
    defaults = GameConfig()
    path = tmp_path / "bad.ini"
    path.write_bytes(b"\xff\xfe[game]\ntestmode = true\n")
    cfg = ConfigManager(str(path)).load()
    assert cfg.testmode == defaults.testmode
    assert cfg.startmap == defaults.startmap
