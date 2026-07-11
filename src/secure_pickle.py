"""Hardened save (de)serialization for Heart of Virtue.

TRUST MODEL
-----------
Pickle save blobs are *trusted server-side artifacts*: they are produced by
this codebase (``pickle.dumps`` of the live Player graph) and stored either on
local disk or in the game's own database. Players never upload raw save bytes
through any API route. Pickle is nevertheless an unsafe format by design, so
this module applies defense-in-depth for the day a blob is tampered with or a
new ingestion path is added:

1. **Class allowlist** (enforced in *every* mode): ``find_class`` only ever
   resolves classes defined in the game engine (``src.*`` modules) plus a
   small curated set of stdlib support types. Dangerous globals such as
   ``os.system``, ``subprocess.Popen``, or ``builtins.eval`` are never
   resolved — in legacy mode they degrade to an inert placeholder, in strict
   mode they raise :class:`RestrictedUnpicklingError`.
2. **Integrity header**: new saves are prefixed with magic bytes, a format
   version, and a SHA-256 digest of the payload. Tampered or truncated saves
   are rejected before unpickling. Headerless blobs are treated as legacy
   saves (loadable, logged).
3. **Size cap**: oversized blobs are rejected before deserialization.
4. **Strict mode** (``strict_unpickle`` config flag / ``HOV_STRICT_UNPICKLE``
   env var): disables placeholder synthesis entirely — any class that cannot
   be resolved from the allowlist raises instead of being papered over.
5. **Event log**: every rewrite, placeholder, and rejection is recorded on the
   unpickler (``SafeUnpickler.events``) and mirrored to the module logger.

Remaining risk: even with an allowlist, unpickling constructs engine objects
whose ``__setstate__``/``__init__`` run engine code. Do not feed this module
bytes from an untrusted party; a data-only save format (issue #13 Phase 3) is
the eventual exit from pickle altogether.
"""

import hashlib
import io
import logging
import os
import pickle

logger = logging.getLogger("hov.secure_pickle")

# ----------------- Errors -----------------


class RestrictedUnpicklingError(pickle.UnpicklingError):
    """A pickled global was outside the allowlist (or unresolvable in strict mode)."""


class SaveIntegrityError(pickle.UnpicklingError):
    """A save blob failed header, checksum, version, or size validation."""


# ----------------- Legacy module remapping -----------------

# Top-level engine modules that legacy save data and map JSON reference by
# bare name (the persisted format predates the src.*-only import convention).
LEGACY_BARE_MODULES = frozenset({
    "actions", "animations", "combat_event_config", "combatant",
    "config_manager", "coordinate_config", "enchant_tables", "events",
    "functions", "genericng", "interface", "inventory_utils", "items",
    "loot_tables", "moves", "narration", "npc", "npc_ai_config",
    "objects", "positions", "scenario_config", "shop_conditions",
    "skilltree", "states", "story", "tiles", "tilesets", "universe",
    "player", "secure_pickle",
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


# ----------------- Allowlist -----------------

# Stdlib support types that legitimately appear in pickled Player graphs
# (container/scalar reconstruction and legacy protocol machinery). Anything
# stdlib beyond this set is treated exactly like an unknown global.
#
# Verified empirically against a populated in-game Player: the graph resolves
# only src.* modules plus builtins.getattr (bound methods stored as instance
# state pickle as getattr(obj, name)) and re._compile (compiled patterns).
# getattr is a known gadget primitive, so the integrity header/checksum and
# the server-side-only trust model (see module docstring) remain load-bearing.
STDLIB_ALLOWLIST = frozenset({
    ("copyreg", "_reconstructor"),
    ("copyreg", "__newobj__"),
    ("copyreg", "__newobj_ex__"),
    ("builtins", "getattr"),
    ("re", "_compile"),
    ("builtins", "object"),
    ("builtins", "list"),
    ("builtins", "dict"),
    ("builtins", "tuple"),
    ("builtins", "set"),
    ("builtins", "frozenset"),
    ("builtins", "str"),
    ("builtins", "int"),
    ("builtins", "float"),
    ("builtins", "bool"),
    ("builtins", "bytes"),
    ("builtins", "bytearray"),
    ("builtins", "complex"),
    ("builtins", "range"),
    ("builtins", "slice"),
    ("collections", "OrderedDict"),
    ("collections", "defaultdict"),
    ("collections", "deque"),
    ("collections", "Counter"),
    ("datetime", "datetime"),
    ("datetime", "date"),
    ("datetime", "time"),
    ("datetime", "timedelta"),
    ("datetime", "timezone"),
})


def _is_engine_module(module):
    return module == "src" or module.startswith("src.")


# ----------------- Strict mode & size cap configuration -----------------

_TRUTHY = {"1", "true", "yes", "on"}

# 32 MB default: a full Player graph (universe, maps, tiles, NPCs) pickles to
# low single-digit MB today; the cap is a DoS guard, not a budget.
DEFAULT_MAX_SAVE_BYTES = 32 * 1024 * 1024

_strict_mode = None  # tri-state: None = fall back to env var


def set_strict_mode(enabled):
    """Set process-wide strict unpickling (wired from the strict_unpickle config flag).

    Pass ``None`` to clear the override and fall back to the
    ``HOV_STRICT_UNPICKLE`` environment variable.
    """
    global _strict_mode
    _strict_mode = enabled if enabled is None else bool(enabled)


def strict_mode_enabled():
    """Resolve the effective strict-mode setting (config override, then env var)."""
    if _strict_mode is not None:
        return _strict_mode
    return os.environ.get("HOV_STRICT_UNPICKLE", "").strip().lower() in _TRUTHY


def max_save_bytes():
    """Maximum accepted save blob size (env-overridable via HOV_MAX_SAVE_BYTES)."""
    raw = os.environ.get("HOV_MAX_SAVE_BYTES", "").strip()
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            logger.warning("Ignoring non-integer HOV_MAX_SAVE_BYTES=%r", raw)
    return DEFAULT_MAX_SAVE_BYTES


# ----------------- Placeholder synthesis (legacy mode only) -----------------


def _make_placeholder_class(module, name):
    """Synthesize a benign stand-in class for an unresolvable legacy global.

    Instances absorb any constructor args and expose the no-op surface game
    logic commonly touches. Tagged with ``_legacy_placeholder`` so downstream
    code (and tests) can detect and reject or warn on them.
    """
    placeholder_class_name = f"LegacyMissing_{module.replace('.', '_')}_{name}"
    return type(
        placeholder_class_name,
        (object,),
        {
            "__doc__": f"Placeholder for missing legacy class {module}.{name}",
            "__init__": lambda self, *a, **k: None,
            "__repr__": lambda self: f"<LegacyMissing {module}.{name}>",
            "_legacy_placeholder": True,
            # Commonly accessed attributes in game logic
            "name": name,
            "hidden": True,
            "announce": "",
            "idle_message": "",
            "description": "",
            "keywords": [],
            "interactions": [],
            # Benign no-op methods
            "process": lambda self, *a, **k: None,
            "check_conditions": lambda self, *a, **k: None,
        },
    )


# ----------------- SafeUnpickler -----------------


class SafeUnpickler(pickle.Unpickler):
    """Unpickler restricted to engine classes, resilient to missing legacy ones.

    Resolution strategy for each pickled global ``(module, name)``:
      1. Redirect bare legacy module paths (e.g. 'items', 'story.ch01') to the
         canonical 'src.*' path so old saves resolve to the running engine's
         classes instead of loading duplicate bare modules.
      2. Curated stdlib support types (STDLIB_ALLOWLIST) resolve normally.
      3. Engine (``src.*``) modules resolve normally, but only to classes —
         module-level functions and other callables are refused.
      4. Everything else never resolves: legacy mode substitutes a benign
         placeholder class (logged); strict mode raises
         :class:`RestrictedUnpicklingError`.

    Diagnostics for every rewrite/placeholder/rejection accumulate in
    ``self.events`` as ``{"kind", "module", "name", "detail"}`` dicts.
    """

    def __init__(self, *args, strict=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.strict = strict_mode_enabled() if strict is None else bool(strict)
        self.events = []

    def _record(self, kind, module, name, detail=""):
        self.events.append(
            {"kind": kind, "module": module, "name": name, "detail": detail}
        )
        logger.warning("secure_pickle %s: %s.%s %s", kind, module, name, detail)

    def _refuse(self, module, name, detail):
        if self.strict:
            self._record("rejected", module, name, detail)
            raise RestrictedUnpicklingError(
                f"Refusing to unpickle {module}.{name}: {detail}"
            )
        self._record("placeholder", module, name, detail)
        return _make_placeholder_class(module, name)

    def find_class(self, module, name):
        original_module = module
        module = canonical_module_name(module)
        if module != original_module:
            self._record("rewrite", original_module, name, f"-> {module}")

        if (module, name) in STDLIB_ALLOWLIST:
            return super().find_class(module, name)

        if not _is_engine_module(module):
            # Never resolved, resolvable or not: this is the arbitrary-code-
            # execution vector (os.system, builtins.eval, ...).
            return self._refuse(module, name, "module outside the engine allowlist")

        try:
            resolved = super().find_class(module, name)
        except (ModuleNotFoundError, AttributeError) as exc:
            return self._refuse(module, name, f"unresolvable engine class ({exc})")

        if not isinstance(resolved, type):
            # Engine module-level functions are callable via REDUCE with
            # attacker-chosen args; only classes may be reconstructed.
            return self._refuse(module, name, "engine global is not a class")

        return resolved


# ----------------- Integrity header -----------------

MAGIC = b"HOVS"
FORMAT_VERSION = 1
_DIGEST_LEN = 32  # sha256
HEADER_LEN = len(MAGIC) + 1 + _DIGEST_LEN


def dumps(obj):
    """Pickle ``obj`` and prepend the integrity header (magic, version, sha256)."""
    payload = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    digest = hashlib.sha256(payload).digest()
    return MAGIC + bytes([FORMAT_VERSION]) + digest + payload


def _validate_and_strip_header(data):
    """Return the pickle payload from a save blob, verifying any header present.

    Blobs without the HOVS magic are legacy raw pickles and pass through
    unchanged (logged at info level).
    """
    if not data.startswith(MAGIC):
        logger.info("secure_pickle: loading legacy headerless save blob")
        return data
    if len(data) < HEADER_LEN:
        raise SaveIntegrityError("Save header is truncated")
    version = data[len(MAGIC)]
    if version != FORMAT_VERSION:
        raise SaveIntegrityError(f"Unsupported save format version {version}")
    digest = data[len(MAGIC) + 1: HEADER_LEN]
    payload = data[HEADER_LEN:]
    if hashlib.sha256(payload).digest() != digest:
        raise SaveIntegrityError("Save checksum mismatch (file corrupt or tampered)")
    return payload


def loads(data, strict=None):
    """Deserialize a save blob (header-aware, size-capped, allowlisted).

    Raises :class:`SaveIntegrityError` on size/header/checksum problems and
    :class:`RestrictedUnpicklingError` on disallowed globals (strict mode).
    """
    limit = max_save_bytes()
    if len(data) > limit:
        raise SaveIntegrityError(
            f"Save blob is {len(data)} bytes; limit is {limit}"
        )
    payload = _validate_and_strip_header(data)
    return SafeUnpickler(io.BytesIO(payload), strict=strict).load()


def load_stream(fp, strict=None):
    """Deserialize a save from a binary file object (reads at most the size cap)."""
    limit = max_save_bytes()
    data = fp.read(limit + 1)
    if len(data) > limit:
        raise SaveIntegrityError(f"Save blob exceeds the {limit}-byte limit")
    return loads(data, strict=strict)


def dump_file(obj, filename):
    """Serialize ``obj`` with the integrity header and write it to ``filename``."""
    with open(filename, "wb") as f:
        f.write(dumps(obj))
