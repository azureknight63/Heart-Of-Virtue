"""Hardened save deserialization for Heart of Virtue.

TRUST MODEL
-----------
Pickle save files are **trusted local artifacts** produced by this game engine
for the player who owns them. Python's :mod:`pickle` executes arbitrary code
during deserialization *by design*, so loading a save crafted by an untrusted
third party can result in arbitrary code execution. See ``SECURITY.md`` for the
full trust model and the migration roadmap (issue #13).

This module narrows the blast radius incrementally (issue #13, Phase 1 plus the
cheap Phase 2 hygiene wins):

  * A controlled module-rewrite map (:func:`canonical_module_name`) instead of
    ad-hoc predicates -- legacy bare module names resolve to the running
    engine's ``src.*`` classes and nothing else.
  * An **allow-list** of engine classes derived automatically from the engine
    modules at first use (so it can't drift behind the code).
  * An opt-in **strict mode** (env var ``HOV_STRICT_UNPICKLE``) that rejects any
    class outside the allow-list and disables dynamic placeholder synthesis.
  * Structured **event logging** of every rewrite, placeholder, and rejection,
    both to :mod:`logging` and onto the unpickler's ``events`` list for UI/debug
    inspection.
  * A hard **size cap** enforced before unpickling begins, so an intentionally
    bloated save fails fast.

TODO(security, issue #13): pickle remains inherently unsafe for untrusted
input -- the exec risk is intrinsic to the format. Phase 3 introduces a
data-only (JSON) save format; pickle should then be reserved for one-shot
legacy import only.
"""

import io
import os
import struct
import hashlib
import pickle
import logging
import importlib
import pkgutil
from collections import Counter

logger = logging.getLogger(__name__)

# Reject saves larger than this before unpickling. Current full-game saves are
# well under 1 MB; 5 MB leaves generous headroom while capping memory/CPU
# pressure from an intentionally bloated pickle. See issue #13, Phase 2.
DEFAULT_MAX_SAVE_BYTES = 5 * 1024 * 1024

# Environment variable that toggles strict allow-list enforcement. Kept as an
# env var (rather than plumbing a config handle through the loader) so it is a
# single, testable control surface reachable from any entry point.
STRICT_ENV_VAR = "HOV_STRICT_UNPICKLE"

# --- Integrity header (issue #13, Phase 2) ---------------------------------
# New saves are prefixed with a small header so tampering / truncation is
# detected before unpickling: [4 bytes magic][1 byte version][32 bytes sha256].
# Old headerless saves are still accepted (detected by the absent magic) and
# loaded as legacy format.
HEADER_MAGIC = b"HOVS"
HEADER_VERSION = 1
_HEADER_STRUCT = struct.Struct(">4sB32s")  # magic, version, sha256 digest
HEADER_SIZE = _HEADER_STRUCT.size  # 37 bytes


class RestrictedUnpicklingError(pickle.UnpicklingError):
    """Raised in strict mode when a class is not on the allow-list."""


class SaveTooLargeError(Exception):
    """Raised when a save payload exceeds the configured size cap."""


class SaveIntegrityError(Exception):
    """Raised when a save's integrity header fails validation (tampering)."""


# ---------------------------------------------------------------------------
# Controlled module-rewrite map (narrow, static allow-list of bare -> src.*)
# ---------------------------------------------------------------------------

# Bare, top-level engine module names that legacy saves and map JSON reference
# by their pre-``src.``-convention path. Anything in this set is rewritten to
# ``src.<name>``; every other module path passes through unchanged. Keeping the
# rewrite as an explicit membership test (not a lambda predicate) means the set
# of paths we will silently redirect is auditable at a glance.
LEGACY_BARE_MODULES = frozenset({
    "_unpickle_worker",
    "actions", "animations", "combat_event_config", "combatant",
    "config_manager", "coordinate_config", "enchant_tables", "events",
    "functions", "genericng", "interface", "inventory_utils", "items",
    "loot_tables", "moves", "narration", "npc", "npc_ai_config",
    "objects", "positions", "save_format", "scenario_config",
    "secure_pickle", "shop_conditions", "skilltree", "states", "story",
    "tiles", "tilesets", "universe", "player",
})


def canonical_module_name(mod_name):
    """Map a persisted bare engine module path to its canonical src.* path.

    Save files and map JSON store bare module names ('items', 'story.ch01');
    resolving them as-is would import duplicate bare module objects whose
    classes don't match the running engine's. Non-engine module paths (e.g.
    test modules) pass through unchanged.
    """
    if mod_name.split(".", 1)[0] in LEGACY_BARE_MODULES:
        return "src." + mod_name
    return mod_name


# ---------------------------------------------------------------------------
# Allow-list derivation (auto-generated from the engine to prevent drift)
# ---------------------------------------------------------------------------

# Engine modules deliberately excluded from allow-list derivation: they hold no
# persistable classes and pull no weight into a save graph. Everything else in
# LEGACY_BARE_MODULES is introspected, so the allow-list can't drift behind a
# newly added engine module (the same set that gates canonical rewrites).
_ALLOWLIST_EXCLUDE = frozenset({"_unpickle_worker", "save_format", "secure_pickle"})

# Known-safe stdlib globals that pickle's reconstruction machinery -- and the
# ordinary data objects engine instances embed (compiled regexes, config
# parsers, dates) -- reference. These are benign data/reconstruction helpers,
# NOT the RCE gadgets strict mode exists to block (os.system, eval, subprocess).
# They resolve fine but aren't "engine" classes, so they're allow-listed here.
# Extend this set (guided by the save fuzzer) when a genuine save embeds a new
# stdlib type; never add callables with side effects.
_SAFE_STDLIB = frozenset({
    ("builtins", "object"), ("builtins", "set"), ("builtins", "frozenset"),
    ("builtins", "list"), ("builtins", "dict"), ("builtins", "tuple"),
    ("builtins", "bytearray"), ("builtins", "complex"),
    ("copyreg", "_reconstructor"), ("copyreg", "__newobj__"),
    ("collections", "OrderedDict"), ("collections", "defaultdict"),
    ("re", "_compile"), ("re", "compile"), ("re", "Pattern"),
    ("configparser", "ConfigParser"), ("configparser", "ConverterMapping"),
    ("configparser", "SectionProxy"),
    ("datetime", "datetime"), ("datetime", "date"), ("datetime", "time"),
    ("datetime", "timedelta"),
    ("decimal", "Decimal"), ("uuid", "UUID"),
    # functools.partial is safe here: any callable it wraps is itself a pickle
    # global that goes through find_class, so partial(os.system, ...) is still
    # blocked by the os.system rejection.
    ("functools", "partial"),
})

_allowlist_cache = None


def _collect_module(mod_name, allowed):
    """Add every class object reachable from ``mod_name`` (and, for packages,
    its immediate submodules) to ``allowed``."""
    try:
        mod = importlib.import_module(mod_name)
    except Exception:  # pragma: no cover - defensive; missing optional module
        logger.debug("Allow-list: could not import %s", mod_name)
        return
    for obj in vars(mod).values():
        if isinstance(obj, type):
            allowed.add((obj.__module__, obj.__name__))
    for info in pkgutil.iter_modules(getattr(mod, "__path__", [])):
        _collect_module(f"{mod_name}.{info.name}", allowed)


def _build_allowlist():
    """Introspect the engine modules and return the set of allowed classes.

    The module set is derived from ``LEGACY_BARE_MODULES`` (the canonical list of
    engine top-level modules) so a newly added module is covered automatically.
    Each entry is a ``(module, name)`` tuple keyed on the class's real
    ``__module__`` (which is what pickle stores), so canonical rewrites line up
    with allow-list membership.
    """
    allowed = set(_SAFE_STDLIB)
    for bare in LEGACY_BARE_MODULES:
        if bare in _ALLOWLIST_EXCLUDE:
            continue
        _collect_module("src." + bare, allowed)
    return allowed


def get_allowlist():
    """Return the cached engine **class inventory**, building it on first use.

    This is the concrete set of engine classes (a ``(module, name)`` set) used
    for the drift manifest and by tooling/tests. Strict-mode *enforcement* is
    the broader engine-module rule in :func:`_is_allowed` (which also admits
    engine functions/methods, not just classes) -- this inventory documents the
    class surface, it is not the sole gate.
    """
    global _allowlist_cache
    if _allowlist_cache is None:
        _allowlist_cache = _build_allowlist()
    return _allowlist_cache


def _is_engine_module(module):
    """True if ``module`` is an engine module (``src.<name>[...]`` where
    ``<name>`` is one of the canonical engine top-level modules).

    Pickle references engine classes *and* functions/methods (e.g. an
    ``actions.Save`` command holds ``src.player._ui.PlayerUIMixin.save``); all
    are trusted because they live in engine code. ``os``, ``subprocess``,
    ``builtins.eval`` and friends are not engine modules, so the classic pickle
    RCE gadgets remain blocked.
    """
    if not module.startswith("src."):
        return False
    parts = module.split(".")
    return len(parts) >= 2 and parts[1] in LEGACY_BARE_MODULES


def _is_allowed(module, name):
    """Strict-mode gate: engine-module globals + a curated safe-stdlib set."""
    return _is_engine_module(module) or (module, name) in _SAFE_STDLIB


def strict_mode_enabled():
    """Return True when strict allow-list enforcement is requested via env."""
    return os.environ.get(STRICT_ENV_VAR, "").strip().lower() in (
        "1", "true", "yes", "on",
    )


# Curated set of ``(module, name)`` for classes that have been *removed* from
# the engine but may still appear in old saves. In strict mode these are the
# only classes allowed to fall back to a placeholder; every other unresolved
# class is rejected. It is empty today (no classes have been formally
# deprecated yet); add entries here as classes are retired so legacy saves keep
# loading under strict mode without re-opening the door to arbitrary names.
LEGACY_ALLOWED_MISSING = frozenset()


# --- Telemetry (dev-only, issue #13 Phase 4) -------------------------------
# Cumulative counters across all loads in this process, so a dev can measure
# progress eliminating legacy classes. Cheap to maintain; read via
# get_telemetry() / reset via reset_telemetry().
_TELEMETRY = Counter()


def get_telemetry():
    """Return a snapshot dict of cumulative unpickler event counts."""
    return dict(_TELEMETRY)


def reset_telemetry():
    """Zero the telemetry counters (test/dev helper)."""
    _TELEMETRY.clear()


# ---------------------------------------------------------------------------
# The unpickler
# ---------------------------------------------------------------------------

# Attributes assigned to legacy placeholder classes so downstream game logic
# can access them without exploding. ``_legacy_placeholder`` tags the class so
# callers can choose to reject or warn on it (issue #13 placeholder policy).
# ``keywords`` / ``interactions`` are intentionally omitted here and assigned
# fresh per class in ``_make_placeholder`` (mutable, must not be shared).
_PLACEHOLDER_ATTRS = {
    "hidden": True,
    "announce": "",
    "idle_message": "",
    "description": "",
    "_legacy_placeholder": True,
    "process": lambda self, *a, **k: None,
    "check_conditions": lambda self, *a, **k: None,
    "__init__": lambda self, *a, **k: None,
}


class SafeUnpickler(pickle.Unpickler):
    """Unpickler that redirects legacy modules and gates class resolution.

    Strategy:
      1. Rewrite bare legacy module paths (e.g. 'items', 'story.ch01') to the
         canonical 'src.*' path so old saves resolve to the running engine's
         classes instead of loading duplicate bare modules.
      2. Try normal resolution.
      3. In **strict** mode, reject anything not on the engine allow-list and
         never synthesize placeholders.
      4. In legacy (non-strict) mode, synthesize a benign, tagged placeholder
         class for anything unresolved so old saves still load.

    Every rewrite / placeholder / rejection is recorded on ``self.events`` and
    emitted via :mod:`logging`.
    """

    def __init__(self, file, *, strict=None, events=None):
        super().__init__(file)
        self.strict = strict_mode_enabled() if strict is None else bool(strict)
        self.events = events if events is not None else []

    # ``find_class`` is sometimes exercised on instances built via ``__new__``
    # (bypassing ``__init__``); read state through getattr so those callers,
    # and any subclass that forgets to call super().__init__, still work.
    def _record(self, kind, module, name, **extra):
        event = {"kind": kind, "module": module, "name": name}
        event.update(extra)
        events = getattr(self, "events", None)
        if events is None:
            events = []
            self.events = events
        events.append(event)
        _TELEMETRY[kind] += 1
        if kind == "rejected":
            logger.warning("SafeUnpickler rejected %s.%s", module, name)
        else:
            logger.debug("SafeUnpickler %s: %s.%s", kind, module, name)

    def _make_placeholder(self, module, name):
        placeholder_class_name = f"LegacyMissing_{module.replace('.', '_')}_{name}"
        attrs = dict(_PLACEHOLDER_ATTRS)
        attrs["__doc__"] = f"Placeholder for missing legacy class {module}.{name}"
        attrs["__repr__"] = lambda self: f"<LegacyMissing {module}.{name}>"
        attrs["name"] = name
        # Fresh mutable containers per placeholder class so game logic mutating
        # one legacy placeholder's list can't leak into unrelated ones.
        attrs["keywords"] = []
        attrs["interactions"] = []
        return type(placeholder_class_name, (object,), attrs)

    def find_class(self, module, name):
        strict = getattr(self, "strict", False)
        original = module
        module = canonical_module_name(module)
        if module != original:
            self._record("rewrite", module, name, original=original)

        try:
            cls = super().find_class(module, name)
        except (ImportError, AttributeError, ValueError, TypeError):
            # ImportError/ModuleNotFoundError: module gone. AttributeError: name
            # gone. ValueError/TypeError: a malformed module path from a crafted
            # pickle (e.g. empty components) -- treat all as "unresolved" so we
            # reject (strict) or placeholder (legacy) instead of propagating a
            # raw resolution error out of the loader.
            cls = None

        if cls is not None:
            if strict and not _is_allowed(module, name):
                self._record("rejected", module, name)
                raise RestrictedUnpicklingError(
                    f"Class {module}.{name} is not on the save allow-list"
                )
            return cls

        # Unresolved class. In strict mode only curated, formally-deprecated
        # classes may fall back to a placeholder; everything else is rejected.
        if strict and (module, name) not in LEGACY_ALLOWED_MISSING:
            self._record("rejected", module, name)
            raise RestrictedUnpicklingError(
                f"Class {module}.{name} could not be resolved and strict "
                f"unpickling is enabled"
            )
        self._record("placeholder", module, name)
        return self._make_placeholder(module, name)


# ---------------------------------------------------------------------------
# Integrity header (magic + version + checksum) for tamper detection
# ---------------------------------------------------------------------------

def add_integrity_header(payload):
    """Prefix a pickle ``payload`` (bytes) with a magic/version/sha256 header."""
    digest = hashlib.sha256(payload).digest()
    return _HEADER_STRUCT.pack(HEADER_MAGIC, HEADER_VERSION, digest) + payload


def has_integrity_header(data):
    """Return True if ``data`` begins with the save magic bytes."""
    return len(data) >= 4 and data[:4] == HEADER_MAGIC


def verify_and_strip_header(data):
    """Return the pickle payload from ``data``, validating the header if present.

    Headerless data (legacy saves) is returned unchanged. When the magic is
    present the version and sha256 digest are checked; a mismatch or truncated
    header raises :class:`SaveIntegrityError`.
    """
    if not has_integrity_header(data):
        return data  # legacy headerless save
    if len(data) < HEADER_SIZE:
        raise SaveIntegrityError("Save header is truncated")
    _magic, version, digest = _HEADER_STRUCT.unpack(data[:HEADER_SIZE])
    if version != HEADER_VERSION:
        raise SaveIntegrityError(
            f"Unsupported save header version {version} (expected {HEADER_VERSION})"
        )
    payload = data[HEADER_SIZE:]
    if hashlib.sha256(payload).digest() != digest:
        raise SaveIntegrityError("Save checksum mismatch (file tampered or corrupt)")
    return payload


def serialize_for_save(obj, *, protocol=pickle.HIGHEST_PROTOCOL):
    """Pickle ``obj`` and wrap it in the integrity header for a new save."""
    return add_integrity_header(pickle.dumps(obj, protocol))


def safe_pickle_load(fp, *, strict=None, max_bytes=DEFAULT_MAX_SAVE_BYTES,
                     events=None):
    """Deserialize a save payload with size capping and gated class resolution.

    Accepts both new header-wrapped saves and legacy headerless pickles.

    Args:
        fp: A binary file-like object positioned at the start of the payload.
        strict: Force strict mode on/off; ``None`` resolves from the env var.
        max_bytes: Reject payloads larger than this (``None`` disables the cap).
        events: Optional list to collect structured diagnostics onto.

    Raises:
        SaveTooLargeError: The payload exceeds ``max_bytes``.
        SaveIntegrityError: The integrity header failed validation.
        RestrictedUnpicklingError: Strict mode rejected a class.
        pickle.UnpicklingError / EOFError: Corrupt payload.
    """
    raw = fp.read()
    if max_bytes is not None and len(raw) > max_bytes:
        raise SaveTooLargeError(
            f"Save payload of {len(raw)} bytes exceeds the {max_bytes}-byte cap"
        )
    payload = verify_and_strip_header(raw)
    return SafeUnpickler(io.BytesIO(payload), strict=strict, events=events).load()


# ---------------------------------------------------------------------------
# Sandboxed legacy unpickling (issue #13, Phase 4 -- optional hardening)
# ---------------------------------------------------------------------------

# Default wall-clock budget for the sandbox worker. A save of uncertain
# provenance that spins or bloats is killed after this many seconds.
DEFAULT_SANDBOX_TIMEOUT = 15
# Default address-space cap for the sandbox worker (POSIX only). A crafted
# pickle opcode can declare a huge allocation; bounding the child's memory turns
# that allocation-DoS into a clean worker failure instead of parent OOM. This
# caps *virtual* address space (RLIMIT_AS), which runs well ahead of real usage
# once the interpreter + engine are imported, so it is set generously (2 GiB) --
# low enough to stop a multi-GiB allocation, high enough not to fail normal
# imports on hosts whose allocator reserves large virtual mappings.
DEFAULT_SANDBOX_MEMORY_BYTES = 2 * 1024 * 1024 * 1024


class SandboxError(Exception):
    """Raised when the sandboxed unpickle worker fails or times out."""


def _rlimit_preexec(memory_bytes):
    """Build a preexec_fn that caps the child's address space (POSIX only)."""
    def _apply():  # pragma: no cover - runs only in the forked child
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    return _apply


def load_in_subprocess(data, *, timeout=DEFAULT_SANDBOX_TIMEOUT, strict=True,
                       memory_bytes=DEFAULT_SANDBOX_MEMORY_BYTES):
    """Unpickle ``data`` in an isolated child process and return v2 data.

    The child (``src._unpickle_worker``) does the actual unpickling, so any code
    the pickle executes runs in a disposable process, and converts the result to
    the data-only schema. The parent only ever parses primitive JSON. The child
    is killed if it exceeds ``timeout`` seconds, and (on POSIX) is capped to
    ``memory_bytes`` of address space so an allocation-DoS can't OOM the host.

    Args:
        data: Raw save bytes (header-wrapped or legacy headerless).
        timeout: Seconds before the worker is terminated.
        strict: Run the worker with strict allow-list enforcement (default on,
            since this path exists for untrusted input).
        memory_bytes: Child address-space cap in bytes (POSIX only; ``None``
            disables the cap).

    Returns:
        The data-only (v2) dict produced by the worker.

    Raises:
        SandboxError: The worker timed out, crashed, or produced no output.
    """
    import sys
    import json
    import subprocess

    env = dict(os.environ)
    if strict:
        env[STRICT_ENV_VAR] = "1"
    else:
        env.pop(STRICT_ENV_VAR, None)

    # RLIMIT_AS via preexec_fn is POSIX-only; skip the cap elsewhere.
    preexec = None
    if memory_bytes is not None and os.name == "posix":
        preexec = _rlimit_preexec(memory_bytes)

    # Run from the project root so `-m src._unpickle_worker` resolves regardless
    # of the parent's cwd (this file is at <root>/src/secure_pickle.py).
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "src._unpickle_worker"],
            input=data,
            capture_output=True,
            timeout=timeout,
            env=env,
            cwd=project_root,
            preexec_fn=preexec,
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxError(
            f"Sandboxed unpickle exceeded {timeout}s and was terminated"
        ) from exc

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        raise SandboxError(
            f"Sandboxed unpickle worker failed (exit {proc.returncode}): {stderr}"
        )
    out = proc.stdout.decode("utf-8", "replace").strip()
    if not out:
        raise SandboxError("Sandboxed unpickle worker produced no output")
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise SandboxError("Sandboxed unpickle worker returned invalid JSON") from exc
