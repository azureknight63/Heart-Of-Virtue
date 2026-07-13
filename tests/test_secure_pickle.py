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
