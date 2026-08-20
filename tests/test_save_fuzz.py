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


def test_protocol0_crafting_cannot_express_the_dotted_traversal_vector():
    """Pins a known blind spot in this fuzzer's adversarial crafting.

    ``craft_global_pickle`` emits the protocol-0 ``GLOBAL`` opcode, which
    resolves ``name`` with a plain ``getattr`` -- no dotted attribute
    traversal. The engine-module-trust bypass (a stream naming
    ``("src.secure_pickle", "os.system")``, which walks out of the trusted
    module into ``os``) is only expressible from protocol 4's ``STACK_GLOBAL``
    onward, so this fuzzer structurally cannot generate it and the vector is
    covered by ``tests/test_secure_pickle.py`` instead.

    Both halves are asserted so the note cannot rot silently: if protocol 0
    ever gained dotted lookup, the first assertion fails and the fuzzer should
    be extended; if strict mode ever stopped blocking the protocol-4 form, the
    second fails.
    """
    import io
    import src.secure_pickle as sp

    events = []
    # Legacy mode is the permissive leg: if protocol 0 could reach os.system,
    # this is where it would come back live. It comes back as an inert
    # placeholder instead, because getattr(src.secure_pickle, "os.system")
    # simply does not exist.
    proto0 = sp.safe_pickle_load(
        io.BytesIO(fuzzer.craft_global_pickle("src.secure_pickle", "os.system")),
        strict=False, events=events)
    assert getattr(proto0, "_legacy_placeholder", False) is True
    assert events[-1]["kind"] == "placeholder"

    proto4 = (b"\x80\x04"
              b"\x8c\x11src.secure_pickle"
              b"\x8c\x09os.system"
              b"\x93.")
    with pytest.raises(sp.RestrictedUnpicklingError):
        sp.safe_pickle_load(io.BytesIO(proto4), strict=True)


# ---------------------------------------------------------------------------
# Meta-tests on the fuzzer itself.
#
# ``test_fuzz_no_security_violations`` passing is only meaningful if the fuzzer
# is (a) reproducible from its seed and (b) actually capable of reporting a
# breach. A fuzzer that can never fail is the most expensive no-op in a suite.
# ---------------------------------------------------------------------------

def test_fuzz_run_is_deterministic_for_a_seed():
    first = fuzzer.run_fuzz(iterations=120, seed=4242)
    second = fuzzer.run_fuzz(iterations=120, seed=4242)
    assert [str(f) for f in first] == [str(f) for f in second]


def test_fuzzer_reports_a_breach_when_the_allow_list_is_disabled(monkeypatch):
    """Injected defect: strict mode trusts every global.

    The fuzzer must then report gadgets getting through *and* a malicious
    ``__reduce__`` actually firing -- if it stays silent, its clean runs prove
    nothing about the loader.
    """
    import src.secure_pickle as secure_pickle

    monkeypatch.setattr(secure_pickle, "_is_allowed", lambda module, name: True)
    findings = fuzzer.security_findings(fuzzer.run_fuzz(iterations=400, seed=5))

    assert findings, "fuzzer failed to notice a disabled allow-list"
    categories = {f.category for f in findings}
    assert "disallowed-not-blocked" in categories
    assert "reduce-side-effect-fired" in categories


def test_fuzzer_is_clean_again_once_the_defect_is_reverted():
    """The monkeypatched defect above must not bleed into later runs."""
    assert fuzzer.security_findings(fuzzer.run_fuzz(iterations=400, seed=5)) == []
