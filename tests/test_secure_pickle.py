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


def test_allowlist_stdlib_paths_are_interpreter_independent():
    """Non-engine entries must name a public module, not a private submodule.

    The allow-list is derived by reading ``obj.__module__`` off every class an
    engine module imports, and CPython relocates stdlib implementations into
    private submodules between releases: ``pathlib.Path.__module__`` is
    ``pathlib`` up to 3.12 and ``pathlib._local`` on 3.13+. Without
    canonicalisation the generated manifest differs by interpreter, so
    ``test_allowlist_manifest_matches_code`` passes on whichever version wrote
    the file and fails on every other -- which is exactly what happened: the
    committed manifest was generated on CI's 3.11 and failed on a 3.13 dev box.

    Engine modules are exempt: ``src.npc._chat_llm`` is our own private module
    and its path is stable because we control it.
    """
    offenders = sorted(
        (module, name)
        for module, name in sp.get_allowlist()
        if not sp._is_engine_module(module)
        and any(part.startswith("_") for part in module.split("."))
    )
    assert not offenders, (
        "Allow-list entries name private stdlib submodules, which makes the "
        "generated manifest interpreter-version-dependent: %s" % offenders
    )


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


# The classic pickle RCE gadget surface. SECURITY.md / the module docstring
# name os, subprocess, builtins.eval and getattr specifically; the rest are the
# neighbouring primitives an attacker reaches for when the named ones are shut.
# Each must be rejected *individually* -- a single spot-check of os.system would
# not notice a rule that special-cased only that one name.
RCE_GADGETS = [
    ("os", "system"), ("os", "popen"), ("os", "remove"), ("os", "execv"),
    ("posix", "system"), ("nt", "system"),
    ("subprocess", "Popen"), ("subprocess", "run"), ("subprocess", "call"),
    ("builtins", "eval"), ("builtins", "exec"), ("builtins", "getattr"),
    ("builtins", "__import__"), ("builtins", "open"), ("builtins", "compile"),
    ("shutil", "rmtree"), ("pty", "spawn"), ("socket", "socket"),
    ("pickle", "loads"), ("codecs", "decode"), ("operator", "attrgetter"),
]


@pytest.mark.parametrize("module,name", RCE_GADGETS)
def test_strict_rejects_rce_gadget(module, name):
    """Every documented-blocked global must raise, not merely be absent."""
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    with pytest.raises(sp.RestrictedUnpicklingError) as exc:
        up.find_class(module, name)
    assert f"{module}.{name}" in str(exc.value)
    assert up.events[-1] == {"kind": "rejected", "module": module, "name": name}


@pytest.mark.parametrize("module,name", RCE_GADGETS)
def test_legacy_mode_still_resolves_gadgets(module, name):
    """Documents the trust model honestly: only *strict* mode blocks gadgets.

    Non-strict mode is the legacy compatibility path and offers no protection
    against a hostile save -- if this ever starts raising, the compatibility
    contract changed and SECURITY.md needs updating.
    """
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=False)
    resolved = up.find_class(module, name)
    assert resolved is not None
    assert not [e for e in up.events if e["kind"] == "rejected"]


def test_strict_rejects_gadget_smuggled_under_a_src_prefix():
    """``_is_engine_module`` keys on the *second* path component, so a crafted
    'src.os' must not inherit engine trust from the 'src.' prefix alone."""
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    for module in ("src.os", "src.subprocess", "src.api.routes.debug", "srcx.items"):
        with pytest.raises(sp.RestrictedUnpicklingError):
            up.find_class(module, "system")


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


# ---------------------------------------------------------------------------
# find_class robustness: malformed module paths must not escape the loader
# ---------------------------------------------------------------------------

# A crafted pickle can name an arbitrary module string. ``super().find_class``
# raises ValueError/TypeError (not just ImportError) on some of these; the
# loader must convert every one into its normal unresolved-class handling.
MALFORMED_MODULE_PATHS = ["", ".", "...", ".items", "src.", "src..items",
                          "\x00bad", " ", "a" * 5000, "src.items."]


@pytest.mark.parametrize("module", MALFORMED_MODULE_PATHS)
def test_malformed_module_path_is_rejected_not_raised_in_strict_mode(module):
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    with pytest.raises(sp.RestrictedUnpicklingError):
        up.find_class(module, "Whatever")


@pytest.mark.parametrize("module", MALFORMED_MODULE_PATHS)
def test_malformed_module_path_becomes_a_placeholder_in_legacy_mode(module):
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=False)
    cls = up.find_class(module, "Whatever")
    assert cls.__name__.startswith("LegacyMissing_")
    assert getattr(cls(), "_legacy_placeholder", False) is True


@pytest.mark.parametrize("name", ["", ".", "Foo.Bar.Baz", "\x00", "x" * 5000])
def test_malformed_class_name_is_handled(name):
    """A malformed *name* (dotted qualname components that don't resolve, NULs)
    must funnel into the same unresolved handling rather than propagating."""
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    with pytest.raises(sp.RestrictedUnpicklingError):
        up.find_class("src.items", name)


# ---------------------------------------------------------------------------
# Strict mode is engine-MODULE based: functions and methods are trusted too
# ---------------------------------------------------------------------------

def test_strict_trusts_engine_module_functions_not_just_classes():
    """``_is_allowed`` admits any global from an engine module. A rule that
    checked only the derived *class* inventory would break saves holding an
    ``actions.Save`` command (which pickles a bound engine method)."""
    import src.functions as functions

    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    resolved = up.find_class("src.functions", "canonical_module_name")
    assert resolved is functions.canonical_module_name
    assert ("src.functions", "canonical_module_name") not in sp.get_allowlist()
    assert not [e for e in up.events if e["kind"] == "rejected"]


def test_strict_round_trips_an_engine_function_and_method():
    from src.player import Player
    import src.functions as functions

    payload = {"fn": functions.canonical_module_name, "meth": Player.gain_exp}
    events = []
    loaded = sp.safe_pickle_load(
        io.BytesIO(sp.serialize_for_save(payload)), strict=True, events=events)
    assert loaded["fn"] is functions.canonical_module_name
    assert loaded["meth"] is Player.gain_exp
    assert [e for e in events if e["kind"] == "rejected"] == []


@pytest.mark.parametrize("module,name", sorted(sp._SAFE_STDLIB))
def test_strict_accepts_every_curated_safe_stdlib_global(module, name):
    """The curated set is the accept side of the boundary; if one of these
    stops resolving, real saves embedding that type break under strict mode."""
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    assert up.find_class(module, name) is not None
    assert not [e for e in up.events if e["kind"] == "rejected"]


@pytest.mark.parametrize("module,name", [
    ("collections", "ChainMap"), ("collections", "Counter"),
    ("datetime", "timezone"), ("re", "sub"), ("functools", "reduce"),
    ("itertools", "chain"), ("copyreg", "pickle"),
])
def test_strict_rejects_stdlib_globals_outside_the_curated_set(module, name):
    """The reject side: neighbouring stdlib names in *allow-listed modules*
    are still rejected -- membership is per (module, name), not per module."""
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=True)
    with pytest.raises(sp.RestrictedUnpicklingError):
        up.find_class(module, name)


def test_is_engine_module_boundary():
    assert sp._is_engine_module("src.items") is True
    assert sp._is_engine_module("src.story.ch02") is True
    assert sp._is_engine_module("src.player._leveling") is True
    assert sp._is_engine_module("src.api.routes.debug") is False
    assert sp._is_engine_module("src") is False
    assert sp._is_engine_module("items") is False
    assert sp._is_engine_module("notsrc.items") is False


# ---------------------------------------------------------------------------
# Size cap: the real 5 MB default, enforced before any opcode executes
# ---------------------------------------------------------------------------

def test_default_cap_is_five_megabytes():
    assert sp.DEFAULT_MAX_SAVE_BYTES == 5 * 1024 * 1024


def test_payload_over_the_real_default_cap_is_rejected():
    """Uses the module default (no max_bytes override), with a payload that
    genuinely exceeds 5 MB -- a cap tested only at max_bytes=10 would not
    notice DEFAULT_MAX_SAVE_BYTES being widened to, say, 5 GB."""
    oversize = sp.serialize_for_save({"pad": "x" * (sp.DEFAULT_MAX_SAVE_BYTES + 1024)})
    assert len(oversize) > sp.DEFAULT_MAX_SAVE_BYTES
    with pytest.raises(sp.SaveTooLargeError) as exc:
        sp.safe_pickle_load(io.BytesIO(oversize))
    assert str(sp.DEFAULT_MAX_SAVE_BYTES) in str(exc.value)


def test_payload_just_under_the_cap_still_loads():
    """Pins the boundary from the other side so the cap can't be tightened to
    something that rejects a legitimate save."""
    payload = {"pad": "x" * (sp.DEFAULT_MAX_SAVE_BYTES // 2)}
    assert sp.safe_pickle_load(io.BytesIO(sp.serialize_for_save(payload))) == payload


def test_size_cap_fires_before_any_pickle_opcode_executes(tmp_path):
    """The cap's security value is that an oversize hostile save never reaches
    the unpickler at all. Assert the embedded side effect did not fire."""
    sentinel = tmp_path / "fired"
    oversize = sp.serialize_for_save(
        {"evil": _MkdirReduce(str(sentinel)),
         "pad": "x" * (sp.DEFAULT_MAX_SAVE_BYTES + 1024)})
    with pytest.raises(sp.SaveTooLargeError):
        sp.safe_pickle_load(io.BytesIO(oversize), strict=False)
    assert not sentinel.exists()


# ---------------------------------------------------------------------------
# Integrity header: each tamper mode rejected independently
# ---------------------------------------------------------------------------

def _wrapped():
    return sp.add_integrity_header(pickle.dumps({"a": 1}, pickle.HIGHEST_PROTOCOL))


def test_header_layout_is_magic_version_sha256():
    payload = pickle.dumps({"a": 1}, pickle.HIGHEST_PROTOCOL)
    wrapped = sp.add_integrity_header(payload)
    assert sp.HEADER_SIZE == 37
    assert wrapped[:4] == sp.HEADER_MAGIC == b"HOVS"
    assert wrapped[4] == sp.HEADER_VERSION
    assert wrapped[5:37] == __import__("hashlib").sha256(payload).digest()
    assert wrapped[37:] == payload


@pytest.mark.parametrize("mutate,label", [
    (lambda b: b[:4] + bytes([b[4] ^ 0xFF]) + b[5:], "version byte flipped"),
    (lambda b: b[:10] + bytes([b[10] ^ 0xFF]) + b[11:], "digest byte flipped"),
    (lambda b: b[:-1] + bytes([b[-1] ^ 0xFF]), "last payload byte flipped"),
    (lambda b: b[:sp.HEADER_SIZE + 2] + bytes([b[sp.HEADER_SIZE + 2] ^ 0xFF])
     + b[sp.HEADER_SIZE + 3:], "mid payload byte flipped"),
    (lambda b: b[:-5], "payload truncated"),
    (lambda b: b[:sp.HEADER_SIZE], "payload removed entirely"),
    (lambda b: b + b"\x00" * 8, "payload extended"),
])
def test_each_tamper_mode_is_detected_independently(mutate, label):
    with pytest.raises(sp.SaveIntegrityError):
        sp.verify_and_strip_header(mutate(_wrapped()))


# Filtered rather than skipped inside the body: a runtime skip would silently
# shrink the matrix if HEADER_VERSION ever moved into it.
@pytest.mark.parametrize(
    "version", [v for v in (0, 2, 99, 255) if v != sp.HEADER_VERSION])
def test_unknown_header_versions_are_rejected(version):
    payload = pickle.dumps({"a": 1}, pickle.HIGHEST_PROTOCOL)
    digest = __import__("hashlib").sha256(payload).digest()
    bad = sp._HEADER_STRUCT.pack(sp.HEADER_MAGIC, version, digest) + payload
    with pytest.raises(sp.SaveIntegrityError) as exc:
        sp.verify_and_strip_header(bad)
    assert str(version) in str(exc.value)


@pytest.mark.parametrize("bad_magic", [b"XOVS", b"HOV\x00", b"hovs", b"\x00\x00\x00\x00"])
def test_wrong_magic_is_treated_as_headerless_and_fails_as_garbage(bad_magic):
    """A corrupted magic makes the file look headerless, so it is handed to
    pickle unchanged -- which must fail cleanly rather than yield an object."""
    corrupted = bad_magic + _wrapped()[4:]
    assert not sp.has_integrity_header(corrupted)
    with pytest.raises((pickle.UnpicklingError, EOFError, ValueError)):
        sp.safe_pickle_load(io.BytesIO(corrupted), strict=True)


@pytest.mark.parametrize("prefix_len", [0, 1, 3, 4, 5, 20, 36])
def test_truncated_headers_never_yield_an_object(prefix_len):
    truncated = _wrapped()[:prefix_len]
    with pytest.raises((sp.SaveIntegrityError, pickle.UnpicklingError, EOFError)):
        sp.safe_pickle_load(io.BytesIO(truncated), strict=True)


def test_tampering_with_a_headered_save_cannot_swap_in_a_gadget():
    """End-to-end: re-pointing a valid save at a hostile payload without
    recomputing the digest must be caught by the header, before find_class."""
    good = _wrapped()
    hostile = pickle.dumps({"x": 1}, pickle.HIGHEST_PROTOCOL)
    forged = good[:sp.HEADER_SIZE] + hostile
    with pytest.raises(sp.SaveIntegrityError):
        sp.safe_pickle_load(io.BytesIO(forged), strict=True)


# ---------------------------------------------------------------------------
# Malicious __reduce__ payloads: constructed AND executed against the loader
# ---------------------------------------------------------------------------

class _MkdirReduce:
    """Pickles to ``os.mkdir(path)`` -- an observable, harmless side effect."""

    def __init__(self, path):
        self.path = path

    def __reduce__(self):
        import os
        return (os.mkdir, (self.path,))


class _SystemReduce:
    def __init__(self, path):
        self.path = path

    def __reduce__(self):
        import os
        return (os.system, (f"touch {self.path}",))


class _EvalReduce:
    def __init__(self, path):
        self.path = path

    def __reduce__(self):
        return (eval, (f"__import__('os').mkdir({self.path!r})",))


@pytest.mark.parametrize("factory", [_MkdirReduce, _SystemReduce, _EvalReduce])
def test_malicious_reduce_is_blocked_and_never_fires_under_strict_mode(
        factory, tmp_path):
    sentinel = tmp_path / f"fired_{factory.__name__}"
    data = sp.serialize_for_save(factory(str(sentinel)))
    with pytest.raises(sp.RestrictedUnpicklingError):
        sp.safe_pickle_load(io.BytesIO(data), strict=True)
    assert not sentinel.exists(), f"{factory.__name__} side effect executed!"


def test_malicious_reduce_nested_deep_inside_a_save_graph(tmp_path):
    """Gadgets buried in a nested container must be caught too -- find_class
    is consulted per global, not just for the top-level object."""
    sentinel = tmp_path / "deep"
    graph = {"inv": [{"slot": ("a", [_MkdirReduce(str(sentinel))])}]}
    with pytest.raises(sp.RestrictedUnpicklingError):
        sp.safe_pickle_load(io.BytesIO(sp.serialize_for_save(graph)), strict=True)
    assert not sentinel.exists()


def test_strict_mode_from_env_blocks_a_malicious_reduce(monkeypatch, tmp_path):
    """The env-var control surface must actually gate the loader, not just the
    ``strict`` kwarg -- production entry points rely on the env var alone."""
    sentinel = tmp_path / "env_fired"
    data = sp.serialize_for_save(_MkdirReduce(str(sentinel)))
    monkeypatch.setenv(sp.STRICT_ENV_VAR, "1")
    with pytest.raises(sp.RestrictedUnpicklingError):
        sp.safe_pickle_load(io.BytesIO(data))
    assert not sentinel.exists()


# ---------------------------------------------------------------------------
# Sandbox worker: strict enforcement is propagated into the child
# ---------------------------------------------------------------------------

def test_sandbox_blocks_a_gadget_and_the_side_effect_never_fires(tmp_path):
    sentinel = tmp_path / "sandbox_fired"
    data = sp.serialize_for_save(_MkdirReduce(str(sentinel)))
    with pytest.raises(sp.SandboxError) as exc:
        sp.load_in_subprocess(data, strict=True, timeout=60)
    assert "rejected" in str(exc.value)
    assert not sentinel.exists()


def test_sandbox_rejects_a_tampered_save(tmp_path):
    forged = bytearray(sp.serialize_for_save({"a": 1}))
    forged[-1] ^= 0xFF
    with pytest.raises(sp.SandboxError):
        sp.load_in_subprocess(bytes(forged), strict=True, timeout=60)


def test_sandbox_memory_cap_default_is_bounded():
    """RLIMIT_AS exists to turn an allocation-DoS into a clean worker failure;
    an unset/None default would silently remove that protection."""
    assert sp.DEFAULT_SANDBOX_MEMORY_BYTES == 2 * 1024 * 1024 * 1024
    assert sp.DEFAULT_SANDBOX_TIMEOUT > 0


def test_rlimit_preexec_sets_address_space_limit():
    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    applied = {}
    orig = resource.setrlimit
    try:
        resource.setrlimit = lambda which, limits: applied.update(
            {"which": which, "limits": limits})
        sp._rlimit_preexec(123456)()
    finally:
        resource.setrlimit = orig
    assert applied == {"which": resource.RLIMIT_AS, "limits": (123456, 123456)}
    assert resource.getrlimit(resource.RLIMIT_AS) == (soft, hard)



# ---------------------------------------------------------------------------
# Dotted-name traversal: strict mode must not inherit trust from the *named*
# module when the object it resolves to lives somewhere else.
#
# From protocol 4 onward pickle's STACK_GLOBAL carries the module and a dotted
# *attribute path* as two independent strings, and resolution walks that path
# with getattr. Attribute traversal can leave the named module entirely -- e.g.
# ``("src.secure_pickle", "os.system")`` names a genuine engine module (so the
# engine-module trust rule says yes) yet lands on ``os.system``. Neither
# ``pickle.dumps`` nor a ``__reduce__`` fixture can express that pair, so these
# tests hand-assemble the opcodes; nor can a direct ``find_class`` call, since
# the C unpickler reads ``proto`` off the stream and ignores an assignment.
# ---------------------------------------------------------------------------

def _short_unicode(text):
    encoded = text.encode()
    assert len(encoded) < 256, "helper only emits SHORT_BINUNICODE"
    return b"\x8c" + bytes([len(encoded)]) + encoded


def craft_stack_global(module, name):
    """A protocol-4 pickle that resolves ``module:name`` and returns it."""
    return (b"\x80\x04" + _short_unicode(module) + _short_unicode(name)
            + b"\x93" + b".")


def craft_stack_global_call(module, name, args=()):
    """A protocol-4 pickle that resolves ``module:name`` and *calls* it."""
    out = b"\x80\x04" + _short_unicode(module) + _short_unicode(name) + b"\x93"
    out += b"("                              # MARK
    for arg in args:
        out += _short_unicode(arg)
    out += b"tR."                            # TUPLE, REDUCE, STOP
    return out


# Each pair is a *real* attribute path that resolves today: the module is a
# genuine engine module (``_is_engine_module`` says yes) but the object it
# reaches is not engine code at all.
SMUGGLED_VIA_ENGINE_MODULE = [
    ("src.secure_pickle", "os.system"),
    ("src.secure_pickle", "os.popen"),
    ("src.secure_pickle", "os.mkdir"),
    ("src.secure_pickle", "importlib.import_module"),
    ("src.secure_pickle", "pickle.loads"),
    ("src.save_format", "os.system"),
    ("src.items", "random.SystemRandom"),
    # Bare legacy path: canonical_module_name rewrites it to src.secure_pickle
    # first, so the rewrite must not launder the traversal either.
    ("secure_pickle", "os.system"),
]


@pytest.mark.parametrize("module,name", SMUGGLED_VIA_ENGINE_MODULE)
def test_smuggled_path_really_resolves_in_legacy_mode(module, name):
    """Non-vacuity guard for the rejection tests below, and an honest statement
    of the trust model (mirrors ``test_legacy_mode_still_resolves_gadgets``):
    every pair here genuinely reaches a non-engine object.

    If this starts failing, the *fixture* is stale -- the path stopped
    resolving -- and the rejection tests below would be proving nothing.
    """
    target = sp.safe_pickle_load(
        io.BytesIO(craft_stack_global(module, name)), strict=False)
    assert not sp._is_engine_module(getattr(target, "__module__", "") or ""), (
        f"{module}:{name} no longer escapes the engine module"
    )


@pytest.mark.parametrize("module,name", SMUGGLED_VIA_ENGINE_MODULE)
def test_smuggled_path_is_rejected_in_strict_mode(module, name):
    events = []
    with pytest.raises(sp.RestrictedUnpicklingError) as exc:
        sp.safe_pickle_load(io.BytesIO(craft_stack_global(module, name)),
                            strict=True, events=events)
    assert name in str(exc.value)
    assert events[-1]["kind"] == "rejected"


def test_smuggled_gadget_never_executes_end_to_end(tmp_path):
    """The attack is live in legacy mode and dead in strict mode.

    ``os.mkdir`` is used as the payload because its effect is observable,
    reversible and confined to ``tmp_path`` -- executing it in the legacy leg
    is what proves the strict leg is blocking something real.
    """
    legacy_dir = tmp_path / "legacy_fired"
    sp.safe_pickle_load(
        io.BytesIO(craft_stack_global_call(
            "src.secure_pickle", "os.mkdir", (str(legacy_dir),))),
        strict=False)
    assert legacy_dir.is_dir(), "the smuggled call never ran; test is vacuous"

    strict_dir = tmp_path / "strict_blocked"
    with pytest.raises(sp.RestrictedUnpicklingError):
        sp.safe_pickle_load(
            io.BytesIO(craft_stack_global_call(
                "src.secure_pickle", "os.mkdir", (str(strict_dir),))),
            strict=True)
    assert not strict_dir.exists(), "smuggled gadget executed under strict mode!"


def test_smuggled_gadget_gains_nothing_from_a_valid_integrity_header(tmp_path):
    """A hostile save is self-signed: the HOVS header proves transport
    integrity, never intent. A validly-headered crafted stream must still be
    rejected at class-resolution time."""
    sentinel = tmp_path / "signed_smuggle"
    payload = craft_stack_global_call(
        "src.secure_pickle", "os.mkdir", (str(sentinel),))
    signed = sp.add_integrity_header(payload)
    assert sp.verify_and_strip_header(signed) == payload  # header is genuinely valid
    with pytest.raises(sp.RestrictedUnpicklingError):
        sp.safe_pickle_load(io.BytesIO(signed), strict=True)
    assert not sentinel.exists()


def test_sandbox_also_blocks_a_smuggled_gadget(tmp_path):
    sentinel = tmp_path / "sandbox_smuggle"
    payload = craft_stack_global_call(
        "src.secure_pickle", "os.mkdir", (str(sentinel),))
    with pytest.raises(sp.SandboxError) as exc:
        sp.load_in_subprocess(sp.add_integrity_header(payload),
                              strict=True, timeout=60)
    assert "allow-list" in str(exc.value)
    assert not sentinel.exists()


def test_module_objects_are_never_handed_back_in_strict_mode():
    """``src.secure_pickle:os`` resolves to the ``os`` *module* itself.
    Admitting a module object leaves the traversal open one indirection later,
    so it is refused outright."""
    stream = craft_stack_global("src.secure_pickle", "os")
    import os as _os
    assert sp.safe_pickle_load(io.BytesIO(stream), strict=False) is _os
    with pytest.raises(sp.RestrictedUnpicklingError):
        sp.safe_pickle_load(io.BytesIO(stream), strict=True)


@pytest.mark.parametrize("module,name", [
    ("src.items", "Gold"),                       # plain engine class
    ("src.player", "Player"),
    ("copyreg", "_reconstructor"),               # curated safe stdlib
    ("builtins", "dict"),
    # Re-export: canonical_module_name is *defined* in src.secure_pickle but
    # reachable through src.functions. The provenance gate follows the
    # definition, not the import site, or every engine re-export would break.
    ("src.functions", "canonical_module_name"),
    # Nested attribute path that stays inside engine code -- unbound methods
    # pickle exactly like this and must keep working.
    ("src.player", "Player.gain_exp"),
])
def test_provenance_gate_still_admits_legitimate_globals(module, name):
    events = []
    resolved = sp.safe_pickle_load(
        io.BytesIO(craft_stack_global(module, name)), strict=True, events=events)
    assert resolved is not None
    assert [e for e in events if e["kind"] == "rejected"] == []


def test_resolved_global_is_trusted_unit():
    import os as _os

    from src.items import Gold

    assert sp._resolved_global_is_trusted(Gold) is True
    assert sp._resolved_global_is_trusted(dict) is True
    assert sp._resolved_global_is_trusted(_os.system) is False
    assert sp._resolved_global_is_trusted(_os) is False          # module object
    assert sp._resolved_global_is_trusted(object()) is False     # no __module__


# ---------------------------------------------------------------------------
# _sanitize_type_name: attacker-controlled text reaching type()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("LegacyMissing_src_items_Gold", "LegacyMissing_src_items_Gold"),
    ("has\x00nul", "has_nul"),
    ("dots.and-dashes", "dots_and_dashes"),
    ("", "_"),                       # never yields the empty name type() rejects
    ("\x00\x00\x00", "___"),
    ("emoji\U0001f600", "emoji_"),   # non-alphanumeric symbols collapse too
])
def test_sanitize_type_name(raw, expected):
    assert sp.SafeUnpickler._sanitize_type_name(raw) == expected
    # Whatever comes out must be accepted by type() -- that is the whole point.
    assert type(sp.SafeUnpickler._sanitize_type_name(raw), (object,), {})


def test_placeholder_for_a_nul_bearing_module_does_not_crash():
    """Regression: a crafted module path containing a NUL used to reach
    ``type()`` unsanitized and raise ValueError *after* find_class's guarded
    super() call, escaping the loader as an unhandled crash."""
    up = sp.SafeUnpickler(io.BytesIO(b""), strict=False)
    cls = up.find_class("mod\x00ule", "Na\x00me")
    assert "\x00" not in cls.__name__
    assert getattr(cls(), "_legacy_placeholder", False) is True
