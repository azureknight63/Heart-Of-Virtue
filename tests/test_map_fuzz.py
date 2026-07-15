"""Fuzz test for the hardened map-JSON deserializer (issue #290).

Drives tools/map_fuzzer.py, which feeds Universe._deserialize_saved_instance a
random mix of benign engine payloads and adversarial ones (dangerous
__module__/__class_type__ references, malformed dotted paths, recursion-bomb
props graphs, garbage shapes) and asserts the loader's security invariants. The
hard assertion is **zero security-invariant violations**; a benign payload the
loader declines is reported informationally, not failed.

The fuzzer module is loaded by file path (it is a tools/ script, not an
importable package), matching tests/test_save_fuzz.py.
"""

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load_fuzzer():
    path = _ROOT / "tools" / "map_fuzzer.py"
    spec = importlib.util.spec_from_file_location("_map_fuzzer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fuzzer = _load_fuzzer()


@pytest.mark.parametrize("seed", [1, 1337, 20240101])
def test_fuzz_no_security_violations(seed):
    findings = fuzzer.run_fuzz(iterations=500, seed=seed)
    security = fuzzer.security_findings(findings)
    assert not security, "\n".join(str(f) for f in security)


def test_dangerous_class_type_is_refused():
    """A hostile ``os:system`` __class_type__ resolves to None, not os.system."""
    from src.universe import Universe

    u = Universe()
    for spec in ("os:system", "subprocess:Popen", "builtins:eval",
                 "shutil:rmtree", "posix:system"):
        assert u._deserialize_saved_instance({"__class_type__": spec}) is None


def test_dangerous_module_class_is_refused():
    """A hostile ``__class__``/``__module__`` pair is refused before import."""
    from src.universe import Universe

    u = Universe()
    payload = {"__class__": "system", "__module__": "os", "props": {}}
    assert u._deserialize_saved_instance(payload) is None


def test_recursion_bomb_is_depth_bounded():
    """A deeply nested props graph must not raise RecursionError."""
    from src.universe import Universe, MAX_DESERIALIZE_DEPTH

    deep = cur = {}
    for _ in range(MAX_DESERIALIZE_DEPTH + 100):
        nxt = {}
        cur["n"] = nxt
        cur = nxt
    payload = {"__class__": "Item", "__module__": "items", "props": {"d": deep}}
    u = Universe()
    # Must return (a value or None) without blowing the stack.
    u._deserialize_saved_instance(payload)


def test_real_maps_still_load():
    """The hardening must not refuse legitimate shipped maps."""
    from src.universe import Universe

    maps_dir = _ROOT / "src" / "resources" / "maps"
    u = Universe()
    from src.player import Player

    player = Player()
    loaded = 0
    for jf in sorted(maps_dir.glob("*.json"))[:5]:
        try:
            u._load_single_json_map(player, jf)
            loaded += 1
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"legitimate map {jf.name} failed to load: {exc}")
    assert loaded > 0
