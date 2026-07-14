"""Tests for src.secure_pickle -- allow-list, strict mode, size cap, events.

Covers the Phase 1 (issue #13) hardening of save deserialization:
  * allow-list pass (known engine class resolves in strict mode)
  * allow-list fail (unknown class raises in strict mode)
  * placeholder path (legacy / non-strict mode still loads unknown classes)
  * oversize payload rejected before unpickling
  * structured event logging (rewrite / placeholder / rejection)
  * env-var strict-mode toggle
"""

import io
import sys
import types
import pickle

import pytest

import src.secure_pickle as sp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dump(obj):
    return io.BytesIO(pickle.dumps(obj, pickle.HIGHEST_PROTOCOL))


# ---------------------------------------------------------------------------
# canonical_module_name / allow-list derivation
# ---------------------------------------------------------------------------

def test_canonical_rewrites_bare_engine_module():
    assert sp.canonical_module_name("items") == "src.items"
    assert sp.canonical_module_name("story.ch01") == "src.story.ch01"


def test_canonical_passes_through_non_engine_module():
    assert sp.canonical_module_name("some.random.module") == "some.random.module"
    assert sp.canonical_module_name("src.items") == "src.items"


def test_allowlist_contains_known_engine_classes():
    allow = sp.get_allowlist()
    # Player and a well-known item class must be present.
    assert ("src.player", "Player") in allow
    # Safe stdlib reconstruction globals are included.
    assert ("copyreg", "_reconstructor") in allow


# ---------------------------------------------------------------------------
# Strict mode: allow-list pass / fail
# ---------------------------------------------------------------------------

def test_strict_allows_known_engine_class():
    from src.player import Player

    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    assert up.find_class("src.player", "Player") is Player
    # Bare legacy path is rewritten then allowed.
    assert up.find_class("player", "Player") is Player


def test_strict_rejects_unknown_class():
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    with pytest.raises(sp.RestrictedUnpicklingError):
        up.find_class("os", "system")


def test_strict_rejects_unresolvable_class():
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    with pytest.raises(sp.RestrictedUnpicklingError):
        up.find_class("totally_missing_mod_xyz", "Ghost")
    # The rejection is recorded as an event.
    assert any(e["kind"] == "rejected" for e in up.events)


# ---------------------------------------------------------------------------
# Legacy (non-strict) mode: placeholder synthesis
# ---------------------------------------------------------------------------

def test_legacy_synthesizes_placeholder_and_tags_it():
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=False)
    cls = up.find_class("totally_missing_mod_xyz", "Ghost")
    assert cls is not None
    obj = cls()
    assert getattr(obj, "_legacy_placeholder", False) is True
    assert getattr(obj, "hidden", None) is True
    assert cls.__name__.startswith("LegacyMissing_")
    assert any(e["kind"] == "placeholder" for e in up.events)


def test_placeholder_mutable_attrs_are_not_shared():
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=False)
    cls_a = up.find_class("missing_mod_a", "Alpha")
    cls_b = up.find_class("missing_mod_b", "Beta")
    cls_a.keywords.append("leak")
    # The second placeholder class must not see the first's mutation.
    assert cls_b.keywords == []
    assert cls_a.interactions is not cls_b.interactions


def test_legacy_records_rewrite_event():
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=False)
    # story is a real engine package; rewrite to src.story.ch01 should be logged.
    up.find_class("story.ch01", "NonExistentEvent99999")
    assert any(
        e["kind"] == "rewrite" and e["module"] == "src.story.ch01"
        for e in up.events
    )


# ---------------------------------------------------------------------------
# End-to-end round trips via safe_pickle_load
# ---------------------------------------------------------------------------

def test_safe_pickle_load_round_trip_simple_data():
    payload = {"a": 1, "b": [1, 2, 3], "c": ("x", "y")}
    assert sp.safe_pickle_load(_dump(payload)) == payload


def test_safe_pickle_load_placeholder_for_missing_class():
    # Build a pickle referencing a class that won't exist at load time.
    mod = types.ModuleType("story.ephemeral_secure_mod")
    exec("class Ghost:\n    def __init__(self):\n        self.x = 1", mod.__dict__)
    sys.modules["story.ephemeral_secure_mod"] = mod
    # Ensure the parent 'story' package placeholder exists for pickle to import.
    story_pkg = sys.modules.get("story")
    created_story = False
    if story_pkg is None:
        story_pkg = types.ModuleType("story")
        story_pkg.__path__ = []
        sys.modules["story"] = story_pkg
        created_story = True
    try:
        data = pickle.dumps(mod.Ghost(), pickle.HIGHEST_PROTOCOL)
    finally:
        del sys.modules["story.ephemeral_secure_mod"]
        if created_story:
            del sys.modules["story"]

    loaded = sp.safe_pickle_load(io.BytesIO(data))
    assert loaded.__class__.__name__.startswith(
        "LegacyMissing_src_story_ephemeral_secure_mod_Ghost"
    )


# ---------------------------------------------------------------------------
# Size cap
# ---------------------------------------------------------------------------

def test_oversize_payload_rejected():
    payload = _dump({"blob": "x" * 100})
    with pytest.raises(sp.SaveTooLargeError):
        sp.safe_pickle_load(payload, max_bytes=10)


def test_size_cap_can_be_disabled():
    payload = {"blob": "x" * 100}
    assert sp.safe_pickle_load(_dump(payload), max_bytes=None) == payload


# ---------------------------------------------------------------------------
# Env-var strict toggle
# ---------------------------------------------------------------------------

def test_strict_mode_enabled_reads_env(monkeypatch):
    monkeypatch.setenv(sp.STRICT_ENV_VAR, "true")
    assert sp.strict_mode_enabled() is True
    monkeypatch.setenv(sp.STRICT_ENV_VAR, "0")
    assert sp.strict_mode_enabled() is False
    monkeypatch.delenv(sp.STRICT_ENV_VAR, raising=False)
    assert sp.strict_mode_enabled() is False


def test_unpickler_defaults_strict_from_env(monkeypatch):
    monkeypatch.setenv(sp.STRICT_ENV_VAR, "yes")
    up = sp.SafeUnpickler(io.BytesIO(b""))
    assert up.strict is True
    with pytest.raises(sp.RestrictedUnpicklingError):
        up.find_class("os", "system")


def test_events_list_is_shared_when_passed():
    events = []
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=False, events=events)
    up.find_class("items", "NonExistentItemXYZ")
    assert events is up.events
    assert len(events) >= 1


# ---------------------------------------------------------------------------
# Phase 2: integrity header (magic + version + checksum)
# ---------------------------------------------------------------------------

def test_header_round_trip():
    payload = pickle.dumps({"a": 1})
    wrapped = sp.add_integrity_header(payload)
    assert sp.has_integrity_header(wrapped)
    assert sp.verify_and_strip_header(wrapped) == payload


def test_headerless_data_passes_through():
    payload = pickle.dumps({"a": 1})
    assert not sp.has_integrity_header(payload)
    assert sp.verify_and_strip_header(payload) == payload


def test_tampered_payload_detected():
    wrapped = bytearray(sp.add_integrity_header(pickle.dumps({"a": 1})))
    wrapped[-1] ^= 0xFF  # flip a payload byte after the header
    with pytest.raises(sp.SaveIntegrityError):
        sp.verify_and_strip_header(bytes(wrapped))


def test_bad_header_version_rejected():
    payload = pickle.dumps({"a": 1})
    digest = __import__("hashlib").sha256(payload).digest()
    bad = sp._HEADER_STRUCT.pack(sp.HEADER_MAGIC, 99, digest) + payload
    with pytest.raises(sp.SaveIntegrityError):
        sp.verify_and_strip_header(bad)


def test_truncated_header_rejected():
    with pytest.raises(sp.SaveIntegrityError):
        sp.verify_and_strip_header(sp.HEADER_MAGIC + b"\x01\x02")


def test_serialize_for_save_round_trips_through_loader():
    data = sp.serialize_for_save({"x": [1, 2, 3]})
    assert sp.safe_pickle_load(io.BytesIO(data)) == {"x": [1, 2, 3]}


def test_loader_still_reads_legacy_headerless_save():
    legacy = pickle.dumps({"legacy": True}, pickle.HIGHEST_PROTOCOL)
    assert sp.safe_pickle_load(io.BytesIO(legacy)) == {"legacy": True}


# ---------------------------------------------------------------------------
# Phase 2: telemetry + curated legacy-missing gating
# ---------------------------------------------------------------------------

def test_telemetry_counts_events():
    sp.reset_telemetry()
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=False)
    up.find_class("items", "GhostItemXYZ")  # rewrite + placeholder
    tel = sp.get_telemetry()
    assert tel.get("placeholder", 0) >= 1
    sp.reset_telemetry()
    assert sp.get_telemetry() == {}


def test_strict_allows_curated_legacy_missing(monkeypatch):
    monkeypatch.setattr(
        sp, "LEGACY_ALLOWED_MISSING", frozenset({("src.items", "RetiredItem")})
    )
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    # Curated deprecated class -> placeholder even under strict mode.
    cls = up.find_class("src.items", "RetiredItem")
    assert getattr(cls(), "_legacy_placeholder", False) is True
    # A non-curated missing class is still rejected.
    with pytest.raises(sp.RestrictedUnpicklingError):
        up.find_class("src.items", "SomeOtherMissing")


# ---------------------------------------------------------------------------
# Strict mode must accept a real, full Player save (allow-list completeness)
# ---------------------------------------------------------------------------

def test_strict_mode_round_trips_real_player():
    from src.player import Player

    p = Player()
    p.__dict__.pop("_combat_adapter", None)  # holds an unpicklable lock/closure
    data = sp.serialize_for_save(p)
    events = []
    loaded = sp.safe_pickle_load(io.BytesIO(data), strict=True, events=events)
    assert type(loaded).__name__ == "Player"
    assert loaded.name == p.name
    # A genuine save must not trip a single allow-list rejection under strict mode.
    assert [e for e in events if e["kind"] == "rejected"] == []


# ---------------------------------------------------------------------------
# Phase 4: sandboxed subprocess loader
# ---------------------------------------------------------------------------

def test_sandbox_loads_and_converts_to_v2():
    from src import items

    data = sp.serialize_for_save(items.Gold(7))
    result = sp.load_in_subprocess(data, strict=True, timeout=60)
    assert result["format_version"] == 2
    assert "player" in result and "world" in result


def test_sandbox_reports_worker_failure_on_garbage():
    with pytest.raises(sp.SandboxError):
        sp.load_in_subprocess(b"not a pickle at all", strict=True, timeout=60)


# ---------------------------------------------------------------------------
# Phase 4: allow-list manifest drift guard
# ---------------------------------------------------------------------------

def test_allowlist_manifest_matches_code():
    """The checked-in manifest must match the live allow-list (no drift)."""
    import importlib.util

    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    tool_path = root / "tools" / "gen_allowlist_manifest.py"
    spec = importlib.util.spec_from_file_location("_gen_manifest", tool_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--check"]) == 0, (
        "Allow-list manifest is stale; run "
        "`python tools/gen_allowlist_manifest.py` to regenerate."
    )
