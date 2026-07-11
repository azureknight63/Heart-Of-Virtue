"""Tests for src/secure_pickle.py — hardened save deserialization (issue #13).

Covers: allowlist pass/fail, placeholder gating (legacy vs strict), integrity
header roundtrip, checksum tampering, version/size rejection, legacy headerless
compatibility, event logging, and the functions.save/load integration.
"""

import io
import os
import pickle

import pytest

import src.functions as functions
import src.secure_pickle as secure_pickle
from src.secure_pickle import (
    MAGIC,
    RestrictedUnpicklingError,
    SafeUnpickler,
    SaveIntegrityError,
)


@pytest.fixture(autouse=True)
def _reset_strict_mode():
    """Keep the process-wide strict flag from leaking between tests."""
    yield
    secure_pickle.set_strict_mode(None)


def _unpickler(strict):
    return SafeUnpickler(io.BytesIO(b""), strict=strict)


class _EvilReduce:
    """Pickles to a REDUCE of os.system — the classic pickle RCE payload."""

    def __reduce__(self):
        return (os.system, ("echo pwned > /tmp/should_never_exist",))


# ---------------------------------------------------------------------------
# Allowlist: dangerous globals are never resolved
# ---------------------------------------------------------------------------


class TestAllowlist:
    def test_os_system_becomes_placeholder_in_legacy_mode(self):
        blob = pickle.dumps(os.system)
        result = secure_pickle.loads(blob, strict=False)
        assert getattr(result, "_legacy_placeholder", False) is True
        assert result is not os.system

    def test_os_system_rejected_in_strict_mode(self):
        blob = pickle.dumps(os.system)
        with pytest.raises(RestrictedUnpicklingError):
            secure_pickle.loads(blob, strict=True)

    def test_builtins_eval_never_resolves(self):
        blob = pickle.dumps(eval)
        result = secure_pickle.loads(blob, strict=False)
        assert getattr(result, "_legacy_placeholder", False) is True
        with pytest.raises(RestrictedUnpicklingError):
            secure_pickle.loads(blob, strict=True)

    def test_reduce_rce_payload_is_neutralized(self):
        blob = pickle.dumps(_EvilReduce())
        # Legacy mode: os.system degrades to a placeholder class, which the
        # REDUCE op then calls with the attacker args — yielding an inert
        # placeholder instance, executing nothing.
        result = secure_pickle.loads(blob, strict=False)
        assert getattr(type(result), "_legacy_placeholder", False) is True
        with pytest.raises(RestrictedUnpicklingError):
            secure_pickle.loads(blob, strict=True)

    def test_engine_class_resolves_in_strict_mode(self):
        import src.items as items

        blob = secure_pickle.dumps(items.Fists())
        loaded = secure_pickle.loads(blob, strict=True)
        assert isinstance(loaded, items.Fists)

    def test_engine_module_function_is_refused(self):
        blob = pickle.dumps(functions.save)
        result = secure_pickle.loads(blob, strict=False)
        assert getattr(result, "_legacy_placeholder", False) is True
        with pytest.raises(RestrictedUnpicklingError):
            secure_pickle.loads(blob, strict=True)

    def test_stdlib_support_types_resolve(self):
        import collections
        import datetime
        import re

        payload = {
            "od": collections.OrderedDict(a=1),
            "dd": collections.defaultdict(list, {"k": [1]}),
            "dq": collections.deque([1, 2]),
            "when": datetime.datetime(2026, 7, 11, 12, 0),
            "pattern": re.compile(r"a+b"),
            "fs": frozenset({1, 2}),
        }
        loaded = secure_pickle.loads(secure_pickle.dumps(payload), strict=True)
        assert loaded["od"]["a"] == 1
        assert loaded["dd"]["k"] == [1]
        assert loaded["pattern"].match("aab")

    def test_fresh_player_roundtrips_in_strict_mode(self):
        """A real Player graph must be fully covered by the allowlist."""
        from src.player import Player

        player = Player()
        player.name = "Jean"
        loaded = secure_pickle.loads(secure_pickle.dumps(player), strict=True)
        assert isinstance(loaded, Player)
        assert loaded.name == "Jean"


# ---------------------------------------------------------------------------
# Placeholder gating and event logging
# ---------------------------------------------------------------------------


class TestPlaceholdersAndEvents:
    def test_missing_engine_class_placeholder_in_legacy_mode(self):
        up = _unpickler(strict=False)
        cls = up.find_class("story.ch01", "NonExistentEvent99999")
        assert cls.__name__.startswith("LegacyMissing_src_story_ch01_")
        assert cls._legacy_placeholder is True
        kinds = [e["kind"] for e in up.events]
        assert "rewrite" in kinds
        assert "placeholder" in kinds

    def test_missing_engine_class_raises_in_strict_mode(self):
        up = _unpickler(strict=True)
        with pytest.raises(RestrictedUnpicklingError):
            up.find_class("story.ch01", "NonExistentEvent99999")
        assert any(e["kind"] == "rejected" for e in up.events)

    def test_placeholder_surface_matches_legacy_contract(self):
        up = _unpickler(strict=False)
        cls = up.find_class("ghost_mod_xyz", "GhostClass")
        obj = cls("any", args=True)
        assert obj.hidden is True
        assert obj.process() is None
        assert obj.check_conditions() is None
        assert "LegacyMissing ghost_mod_xyz.GhostClass" in repr(obj)


# ---------------------------------------------------------------------------
# Strict mode resolution: explicit param > set_strict_mode > env var
# ---------------------------------------------------------------------------


class TestStrictModeResolution:
    def test_default_is_legacy(self, monkeypatch):
        monkeypatch.delenv("HOV_STRICT_UNPICKLE", raising=False)
        secure_pickle.set_strict_mode(None)
        assert secure_pickle.strict_mode_enabled() is False

    def test_env_var_enables_strict(self, monkeypatch):
        monkeypatch.setenv("HOV_STRICT_UNPICKLE", "true")
        secure_pickle.set_strict_mode(None)
        assert secure_pickle.strict_mode_enabled() is True

    def test_set_strict_mode_overrides_env(self, monkeypatch):
        monkeypatch.setenv("HOV_STRICT_UNPICKLE", "1")
        secure_pickle.set_strict_mode(False)
        assert secure_pickle.strict_mode_enabled() is False

    def test_config_flag_parsed(self, tmp_path):
        from src.config_manager import ConfigManager

        ini = tmp_path / "cfg.ini"
        ini.write_text("[game]\nstrict_unpickle = True\n")
        config = ConfigManager(str(ini)).load()
        assert config.strict_unpickle is True


# ---------------------------------------------------------------------------
# Integrity header
# ---------------------------------------------------------------------------


class TestIntegrityHeader:
    def test_dumps_prepends_header_and_roundtrips(self):
        payload = {"gold": 42, "items": ["sword", "bread"]}
        blob = secure_pickle.dumps(payload)
        assert blob.startswith(MAGIC)
        assert secure_pickle.loads(blob) == payload

    def test_legacy_headerless_blob_still_loads(self):
        blob = pickle.dumps({"legacy": True}, protocol=pickle.HIGHEST_PROTOCOL)
        assert secure_pickle.loads(blob) == {"legacy": True}

    def test_tampered_payload_rejected(self):
        blob = bytearray(secure_pickle.dumps({"hp": 100}))
        blob[-1] ^= 0xFF
        with pytest.raises(SaveIntegrityError, match="checksum"):
            secure_pickle.loads(bytes(blob))

    def test_tampered_digest_rejected(self):
        blob = bytearray(secure_pickle.dumps({"hp": 100}))
        blob[len(MAGIC) + 1] ^= 0xFF  # first digest byte
        with pytest.raises(SaveIntegrityError, match="checksum"):
            secure_pickle.loads(bytes(blob))

    def test_truncated_header_rejected(self):
        with pytest.raises(SaveIntegrityError, match="truncated"):
            secure_pickle.loads(MAGIC + b"\x01\x00\x00")

    def test_unknown_version_rejected(self):
        blob = MAGIC + bytes([99]) + b"\x00" * 32 + b"payload"
        with pytest.raises(SaveIntegrityError, match="version"):
            secure_pickle.loads(blob)


# ---------------------------------------------------------------------------
# Size cap
# ---------------------------------------------------------------------------


class TestSizeCap:
    def test_oversize_blob_rejected(self, monkeypatch):
        monkeypatch.setenv("HOV_MAX_SAVE_BYTES", "64")
        blob = secure_pickle.dumps("x" * 1000)
        with pytest.raises(SaveIntegrityError, match="limit"):
            secure_pickle.loads(blob)

    def test_oversize_stream_rejected(self, monkeypatch):
        monkeypatch.setenv("HOV_MAX_SAVE_BYTES", "64")
        blob = secure_pickle.dumps("x" * 1000)
        with pytest.raises(SaveIntegrityError, match="limit"):
            secure_pickle.load_stream(io.BytesIO(blob))

    def test_default_cap_allows_normal_saves(self, monkeypatch):
        monkeypatch.delenv("HOV_MAX_SAVE_BYTES", raising=False)
        blob = secure_pickle.dumps(list(range(1000)))
        assert secure_pickle.loads(blob) == list(range(1000))

    def test_garbage_env_value_ignored(self, monkeypatch):
        monkeypatch.setenv("HOV_MAX_SAVE_BYTES", "not-a-number")
        assert secure_pickle.max_save_bytes() == secure_pickle.DEFAULT_MAX_SAVE_BYTES


# ---------------------------------------------------------------------------
# functions.py integration
# ---------------------------------------------------------------------------


class TestFunctionsIntegration:
    def test_save_writes_header_and_load_roundtrips(self, tmp_path):
        target = tmp_path / "hardened_save"
        functions.save({"level": 7}, str(target))
        written = (tmp_path / "hardened_save.sav").read_bytes()
        assert written.startswith(MAGIC)
        assert functions.load(str(tmp_path / "hardened_save.sav")) == {"level": 7}

    def test_load_rejects_tampered_save(self, tmp_path):
        target = tmp_path / "tampered.sav"
        functions.save({"level": 7}, str(target))
        raw = bytearray(target.read_bytes())
        raw[-1] ^= 0xFF
        target.write_bytes(bytes(raw))
        with pytest.raises(RuntimeError):
            functions.load(str(target))

    def test_load_accepts_legacy_headerless_save(self, tmp_path):
        target = tmp_path / "legacy.sav"
        with open(target, "wb") as f:
            pickle.dump({"old": "format"}, f, pickle.HIGHEST_PROTOCOL)
        assert functions.load(str(target)) == {"old": "format"}

    def test_safe_pickle_load_returns_none_on_strict_violation(self, tmp_path):
        secure_pickle.set_strict_mode(True)
        blob = pickle.dumps(os.system)
        assert functions._safe_pickle_load(io.BytesIO(blob)) is None

    def test_reexports_available_from_functions(self):
        assert functions.SafeUnpickler is SafeUnpickler
        assert functions.canonical_module_name("items") == "src.items"
        assert "items" in functions.LEGACY_BARE_MODULES
        assert functions.RestrictedUnpicklingError is RestrictedUnpicklingError
        assert functions.SaveIntegrityError is SaveIntegrityError
