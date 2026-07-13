"""Fuzz test for the hardened save loader (issue #13).

Drives tools/save_fuzzer.py, which populates saves with a random mix of real
engine classes/values plus adversarial payloads (disallowed globals, malicious
__reduce__, tampered headers, oversized blobs, garbage) and asserts the loader's
security invariants. The hard assertion is **zero security-invariant
violations**; allow-list coverage gaps (benign objects strict mode declines to
load) are reported informationally, not failed, since they drift with the stdlib
types engine objects happen to embed.

The fuzzer module is loaded by file path (it is a tools/ script, not an
importable package), matching the pattern used by the manifest-drift test.
"""

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load_fuzzer():
    path = _ROOT / "tools" / "save_fuzzer.py"
    spec = importlib.util.spec_from_file_location("_save_fuzzer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fuzzer = _load_fuzzer()


@pytest.mark.parametrize("seed", [1, 1337, 20240101])
def test_fuzz_no_security_violations(seed):
    findings = fuzzer.run_fuzz(iterations=300, seed=seed)
    security = fuzzer.security_findings(findings)
    assert not security, "\n".join(str(f) for f in security)


def test_fuzz_only_configmanager_coverage_gap_is_expected():
    """Coverage gaps must be limited to the known, intentional ones.

    ``builtins.getattr`` is deliberately NOT allow-listed (it is a pickle gadget
    primitive), so ConfigManager's parser-backed reduce declines under strict
    mode. That standalone instance never appears in a real save (session_manager
    stores the GameConfig dataclass, not the ConfigManager), so this is an
    accepted limitation, not a breach. Guard against *new* gaps creeping in.
    """
    findings = fuzzer.run_fuzz(iterations=1500, seed=98765)
    assert fuzzer.security_findings(findings) == []
    unexpected = [
        f for f in fuzzer.coverage_findings(findings)
        if "getattr" not in f.detail and "ConfigManager" not in f.detail
        and "configparser" not in f.detail
    ]
    assert not unexpected, "\n".join(str(f) for f in unexpected)


def test_disallowed_global_is_blocked_in_strict_mode():
    import io
    import src.secure_pickle as sp

    data = sp.add_integrity_header(fuzzer.craft_global_pickle("os", "system"))
    with pytest.raises(sp.RestrictedUnpicklingError):
        sp.safe_pickle_load(io.BytesIO(data), strict=True)


def test_malicious_reduce_side_effect_never_fires_in_strict_mode(tmp_path):
    import io
    import src.secure_pickle as sp

    sentinel = tmp_path / "created_by_pickle"
    data = sp.serialize_for_save(fuzzer._EvilReduce(str(sentinel)))
    with pytest.raises(sp.RestrictedUnpicklingError):
        sp.safe_pickle_load(io.BytesIO(data), strict=True)
    assert not sentinel.exists(), "malicious os.mkdir reduce executed!"
