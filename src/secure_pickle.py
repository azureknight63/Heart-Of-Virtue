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
  * **Strict mode on by default** -- rejects any class outside the allow-list and
    disables dynamic placeholder synthesis. ``HOV_STRICT_UNPICKLE=0`` opts out
    for debugging a save the allow-list refuses; there is no supported reason to
    run the game that way. It was opt-in until the beta flip, which meant the
    allow-list documented in SECURITY.md was not gating any default load.
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
import sys
import types
import struct
import hashlib
import pickle
import logging
import re
import enum
import copyreg
import importlib
import pkgutil
import _compat_pickle
from collections import Counter

logger = logging.getLogger(__name__)

# Reject saves larger than this before unpickling. Current full-game saves are
# well under 1 MB; 5 MB leaves generous headroom while capping memory/CPU
# pressure from an intentionally bloated pickle. See issue #13, Phase 2.
DEFAULT_MAX_SAVE_BYTES = 5 * 1024 * 1024

# Environment variable that can *disable* strict allow-list enforcement. Kept as
# an env var (rather than plumbing a config handle through the loader) so it is a
# single, testable control surface reachable from any entry point. Note the
# polarity: this is an opt-out, and absence means strict.
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
    "journal", "loot_tables", "map_placeholders", "moves", "narration", "npc",
    "npc_ai_config", "npc_level_tables", "objects", "positions", "save_format",
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


def _public_module(obj):
    """Return the public module a class is exported from.

    CPython relocates stdlib implementations into private submodules between
    releases -- ``pathlib.Path.__module__`` is ``pathlib`` through 3.12 and
    ``pathlib._local`` on 3.13+. Recording the raw ``__module__`` therefore made
    the generated manifest interpreter-dependent, so the drift check passed only
    on whichever version wrote the file (CI's 3.11) and failed everywhere else.

    Only rewrites when the private module's parent genuinely re-exports the same
    object, so a class that is only ever reachable at a private path keeps it.
    Walks *every* trailing private component, not just the last one: a nested
    relocation (``pkg._impl._local``) collapsed one level still contains a
    private component, and ``tests/test_secure_pickle.py`` rejects a private
    component anywhere in the path -- so stopping at one level would reproduce
    the interpreter-dependent manifest this function exists to end, one
    release later.

    Engine modules are unaffected: their paths are ours and do not move.
    """
    module = obj.__module__
    if not isinstance(module, str):
        # Vanishingly rare (some C-extension types), but the caller previously
        # stored __module__ verbatim and could not fail here. Preserve that
        # rather than letting a string operation abort allow-list construction,
        # which would break save loading outright.
        return module
    # Engine paths are ours and do not move between interpreters. They must be
    # left alone: src/moves/__init__.py re-exports every class from its private
    # submodules, so the parent-re-export check below would happily collapse
    # ("src.moves._dagger", "Backstab") to ("src.moves", "Backstab") and rewrite
    # 300+ engine entries.
    if _is_engine_module(module):
        return module
    # A top-level module has no parent to be re-exported from.
    if "." not in module:
        return module

    candidate = module
    while "." in candidate:
        parent, _, tail = candidate.rpartition(".")
        if not tail.startswith("_"):
            break
        try:
            # The parent of an already-imported submodule is already in
            # sys.modules -- importlib.import_module() would just look it up
            # there anyway, so check the cache directly and only pay for a real
            # import on the (rare) miss.
            parent_mod = sys.modules.get(parent)
            if parent_mod is None:
                parent_mod = importlib.import_module(parent)
        except Exception:  # pragma: no cover - defensive; parent may not import
            logger.debug("Allow-list: could not resolve public parent of %s", candidate)
            break
        # Re-run the identity check at every level: the rewrite is only valid
        # for as long as each successive parent really re-exports this object.
        if getattr(parent_mod, obj.__name__, None) is not obj:
            break
        candidate = parent

    # Nothing qualified -- keep the path pickle would actually record.
    if candidate == module or _has_private_component(candidate):
        return module
    return candidate


def _has_private_component(module):
    """True if any dotted component of ``module`` starts with an underscore."""
    return any(part.startswith("_") for part in module.split("."))


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
            allowed.add((_public_module(obj), obj.__name__))
    for info in pkgutil.iter_modules(getattr(mod, "__path__", [])):
        _collect_module(f"{mod_name}.{info.name}", allowed)


def _build_allowlist():
    """Introspect the engine modules and return the set of allowed classes.

    The module set is derived from ``LEGACY_BARE_MODULES`` (the canonical list of
    engine top-level modules) so a newly added module is covered automatically.

    Each entry is a ``(module, name)`` tuple keyed on :func:`_public_module`,
    **not** on the raw ``__module__``. That distinction is the whole point of the
    function: ``__module__`` is what pickle stores, but it is not
    interpreter-stable (``pathlib.Path.__module__`` is ``pathlib`` through 3.12
    and ``pathlib._local`` on 3.13+), so keying the manifest on it made the file
    reproduce only on the interpreter that wrote it -- a developer on a newer
    Python regenerated it, the drift test went green locally, and CI (pinned to
    3.11) failed on the same commit. :func:`_public_module` canonicalizes the
    known cases; extend it rather than re-keying on ``__module__``.

    This set is an inventory for the drift manifest and for tooling/tests. It
    is **not** the enforcement gate: nothing on the save-load path consults
    :func:`get_allowlist`. Strict-mode enforcement is :func:`_is_allowed`,
    which applies the broader engine-module rule to whatever path pickle
    actually recorded.
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


def _resolved_global_is_trusted(obj):
    """Second strict-mode gate: the *resolved* object must itself originate in
    a trusted module.

    ``_is_allowed`` only inspects the ``(module, name)`` pair the pickle
    stream names. That is not sufficient on its own: from protocol 4 onward
    pickle resolves ``name`` as a **dotted attribute path** (so that nested
    classes and unbound methods can be pickled), and attribute traversal can
    walk straight out of the trusted module into an imported one. A crafted
    stream naming ``("src.secure_pickle", "os.system")`` passes
    ``_is_engine_module`` -- the module really is an engine module -- yet
    resolves to ``os.system`` and hands the attacker arbitrary code execution.

    Checking the resolved object's own ``__module__`` closes that: every
    curated safe-stdlib global and every engine class/function reports a
    trusted owner, while ``os.system`` reports ``posix``/``nt`` and is
    rejected. Module objects are rejected outright -- a save has no legitimate
    reason to embed one, and admitting them would re-open the traversal.

    Only a class or a plain function is ever a legitimate global (issue #638).
    Everything else a dotted path can reach -- a module-level engine
    *instance* (``src.npc._loot:loot``), an enum member, a bound method -- is
    shared process state, and ``__module__`` does not tell it apart: an
    instance inherits its class's ``__module__``. Handing one back let BUILD
    rewrite it for every session in the process.
    """
    if not isinstance(obj, (type, types.FunctionType)):
        return False
    owner = getattr(obj, "__module__", None)
    if not isinstance(owner, str):
        # Objects with no declaring module are not part of any save this
        # engine writes; refuse rather than guess.
        return False
    return _is_allowed(owner, obj.__name__)


def is_trusted_engine_class(obj):
    """True when ``obj`` is a CLASS that resolves from a trusted module.

    The gate for a map's ``module:Class`` reference (``__class_type__``
    markers, legacy ``__class__``/``__module__`` payloads, placeholder
    ``class`` fields). ``_is_allowed`` alone vets only the pair the map
    names, and every engine module re-exports what it imports -- so
    ``story:import_module`` passed it and resolved to
    ``importlib.import_module``. A map only ever names classes, so anything
    else, however it got there, is refused (issue #620).
    """
    return isinstance(obj, type) and _resolved_global_is_trusted(obj)


#: An attribute name an instance may never carry when a class in its MRO
#: declares it as a policy constant (``KEYWORD_METHOD_ALIASES``,
#: ``CROSSING_METHOD_NAMES``, ``_DELEGATED_CROSSING_VERBS``, ...).
_POLICY_CONSTANT_NAME = re.compile(r"_*[A-Z][A-Z0-9_]*")


def _is_behaviour(raw):
    """Whether a class-dict entry is BEHAVIOUR an instance must not shadow:
    anything callable (functions, nested classes), a static/classmethod, or
    any other non-data descriptor. A data descriptor (``property`` with a
    setter) is not: attribute lookup consults it before the instance
    ``__dict__``, and setting through it runs the class's own validation."""
    if isinstance(raw, (staticmethod, classmethod)) or callable(raw):
        return True
    kind = type(raw)
    return hasattr(kind, "__get__") and not (
        hasattr(kind, "__set__") or hasattr(kind, "__delete__")
    )


def shadows_class_behaviour(cls, name):
    """True when an instance attribute ``name`` on a ``cls`` instance would
    shadow behaviour the class declares -- and so must never be restored
    from a save or applied from a map prop (issue #620).

    Interaction handlers are resolved from the class, but the methods they
    run call ``self.<method>`` (``go`` -> ``self.enter``, ``wash`` ->
    ``self.clean``, ``take_all`` -> ``self.refresh_description``), and an
    instance ``__dict__`` entry wins over any non-data descriptor. So the
    map loader and the save loader both refuse, at the one point each writes
    instance state:

    * dunder names (``__class__`` reassigns the instance's type outright);
    * a name the nearest declaring class in the MRO binds to behaviour
      (:func:`_is_behaviour`);
    * a name that class binds to an UPPER_CASE policy constant.

    Plain data defaults (``hidden = False``, ``keywords``) and data
    descriptors stay writable -- that is what map props and saved state are
    for.
    """
    if not isinstance(name, str):
        return False
    if name.startswith("__") and name.endswith("__"):
        return True
    for klass in getattr(cls, "__mro__", ()):
        declared = vars(klass)
        if name in declared:
            return bool(
                _is_behaviour(declared[name])
                or _POLICY_CONSTANT_NAME.fullmatch(name)
            )
    return False


# Explicit opt-out values. Anything else -- including an unset variable, an empty
# value, and a typo -- leaves strict enforcement ON. Fail closed: a misspelled
# deploy variable must not silently retire the allow-list, which is precisely how
# this gate spent its first life inert.
STRICT_OPT_OUT_VALUES = frozenset({"0", "false", "no", "off"})


def strict_mode_enabled():
    """Return True unless strict enforcement is explicitly disabled via env.

    Strict is the **default** posture: an entry point that sets nothing gets
    allow-list enforcement and no placeholder synthesis. Set
    ``HOV_STRICT_UNPICKLE=0`` (or false/no/off) to opt out, which is a debugging
    affordance for loading a save the allow-list rejects -- not a supported way
    to run the game.
    """
    return os.environ.get(STRICT_ENV_VAR, "").strip().lower() not in STRICT_OPT_OUT_VALUES


# Curated set of ``(module, name)`` for classes that have been *removed* from
# the engine but may still appear in old saves. In strict mode these are the
# only classes allowed to fall back to a placeholder; every other unresolved
# class is rejected. Keyed on the canonical ``src.`` module: ``find_class``
# canonicalises a bare pickled name before it checks here.
#
# Now that strict is the default, this set is the *only* remaining path by which
# a save naming a retired class loads at all. Retiring a class without adding it
# here turns every save referencing it into a hard load failure -- the intended
# trade in beta, but a decision to make deliberately rather than discover. Add
# the entry in the same change that retires the class.
LEGACY_ALLOWED_MISSING = frozenset({
    # Issue #579: the ferry's demo end moved onto ``Passageway.end_demo``.
    # It was placed on no tile in any shipped map, so no save should name
    # it; listed so one that does still loads.
    ("src.story.ch03", "DemoEndEvent"),
    # Issue #646: the Hollowed-curing consumable, retired for prayer.
    ("src.items", "Relic"),
})


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


#: What BUILD may never apply state to. BUILD's slot-state branch is a bare
#: ``setattr`` on whatever sits beneath it on the stack, and a class or a
#: function gets there through ``find_class`` exactly like any other global --
#: so ``GLOBAL src.objects Passageway`` + ``BUILD (None, {"enter": ...})``
#: rewrote ``Passageway.enter`` for every session in the process, and a
#: function's ``__defaults__`` the same way. No save this engine writes ever
#: builds one of these (issue #620).
_UNBUILDABLE = (
    type,
    types.FunctionType,
    types.BuiltinFunctionType,
    types.MethodType,
    types.ModuleType,
    types.CodeType,
)

# --- Allocation tracking and the REDUCE policy (issue #638) -----------------
#
# Every opcode that writes into an object (BUILD, APPEND(S), SETITEM(S),
# ADDITEMS) may only write into one THIS load allocated. Every opcode that
# calls something (REDUCE, OBJ, INST) may, in strict mode, only call a class
# whose construction is known or one of three stdlib reconstruction helpers.
# Both are positive rules: they do not enumerate what an attacker might reach,
# they enumerate what a genuine save needs.

#: Stdlib functions pickle's own reconstruction machinery emits as REDUCE
#: targets: ``Pattern.__reduce__`` names ``re._compile``; protocol 0/1
#: ``object.__reduce_ex__`` names ``copyreg._reconstructor``; a hand-written
#: ``__reduce__`` may name ``copyreg.__newobj__``.
_REDUCE_HELPERS = frozenset({re._compile, copyreg._reconstructor,
                             copyreg.__newobj__})

#: Exact builtin types whose constructor may hand back a cached, shared
#: instance (``()``, ``frozenset()``, small ints, interned strings). Their
#: subclasses always allocate.
_CACHED_IMMUTABLES = frozenset({int, float, complex, str, bytes, tuple,
                                frozenset, bool})

#: ``Py_TPFLAGS_HEAPTYPE``: set on classes defined in Python, clear on C types.
_HEAPTYPE_FLAG = 1 << 9

_safe_stdlib_classes_cache = None


def _safe_stdlib_classes():
    """The class objects named by ``_SAFE_STDLIB`` (resolved once)."""
    global _safe_stdlib_classes_cache
    if _safe_stdlib_classes_cache is None:
        found = set()
        for module, name in _SAFE_STDLIB:
            try:
                obj = getattr(importlib.import_module(module), name)
            except (ImportError, AttributeError):  # pragma: no cover - stdlib
                continue
            if isinstance(obj, type):
                found.add(obj)
        _safe_stdlib_classes_cache = frozenset(found)
    return _safe_stdlib_classes_cache


def _new_allocates(cls):
    """True when ``cls.__new__(cls, ...)`` always returns a NEW object.

    That holds when the ``__new__`` the MRO resolves is a C slot
    (``object.__new__``, ``dict.__new__``, ``BaseException.__new__``...) and
    ``cls`` is not a builtin that caches instances. A Python-level ``__new__``
    may return anything -- ``Enum.__new__`` returns the existing member -- so
    it never counts. No engine class defines ``__new__``.
    """
    if not isinstance(cls, type) or cls in _CACHED_IMMUTABLES:
        return False
    for klass in cls.__mro__:
        if "__new__" in vars(klass):
            raw = vars(klass)["__new__"]
            if isinstance(raw, staticmethod):
                raw = raw.__func__
            return not isinstance(raw, types.FunctionType)
    return False  # pragma: no cover - object always defines __new__


def _is_c_type(cls):
    return isinstance(cls, type) and not cls.__flags__ & _HEAPTYPE_FLAG


def _call_allocates(func, args):
    """True when ``func(*args)`` is known to return a NEW object."""
    if not isinstance(args, tuple):
        return False
    if func is copyreg._reconstructor:
        # base.__new__(cls, state) -- fresh when base is a C type cls derives
        # from, which is the only shape copyreg itself ever writes.
        return (len(args) == 3 and isinstance(args[0], type)
                and _is_c_type(args[1]) and issubclass(args[0], args[1])
                and args[0] not in _CACHED_IMMUTABLES)
    if func is copyreg.__newobj__:
        return bool(args) and _new_allocates(args[0])
    if isinstance(func, type):
        # A metaclass __call__ (EnumType's) can return anything.
        return type(func).__call__ is type.__call__ and _new_allocates(func)
    return False


def _reduce_refusal(func, args):
    """Why strict mode refuses to call ``func(*args)`` at load time, or None.

    REDUCE, OBJ and INST each call an object from the stream. A genuine save
    only ever calls:

    * a class named in ``_SAFE_STDLIB`` (datetime, Decimal, OrderedDict,
      defaultdict, functools.partial, ...);
    * an engine ``Enum`` subclass with one argument -- value lookup, which is
      how a combat save restores ``Direction``;
    * an engine exception class;
    * one of ``_REDUCE_HELPERS``, with arguments of the shape pickle writes.

    Everything else -- an engine function or method (``write_v2_file`` opens a
    path for writing; ``seek_class`` walks modules), an ordinary engine class
    (its ``__init__`` runs with attacker arguments and may register itself in
    a module-level table) -- is refused. Engine functions still load as
    *values*; only calling them during a load is refused.
    """
    if not isinstance(args, tuple):
        return "call arguments are not a tuple"
    if func in _REDUCE_HELPERS:
        if func is re._compile:
            return None
        if func is copyreg._reconstructor and not _call_allocates(func, args):
            return "copyreg._reconstructor with a non-C base type"
        if func is copyreg.__newobj__ and not (args and isinstance(args[0], type)):
            return "copyreg.__newobj__ without a class"
        return None
    if not isinstance(func, type):
        return "not a class or a pickle reconstruction helper"
    if func in _safe_stdlib_classes():
        return None
    if _is_engine_module(getattr(func, "__module__", "") or ""):
        if issubclass(func, enum.Enum):
            return None if len(args) == 1 else "enum call is not a value lookup"
        if issubclass(func, BaseException):
            return None
    return "engine classes are restored with NEWOBJ, never called"


class SafeUnpickler(pickle._Unpickler):
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
      5. In every mode, gate BUILD (:meth:`load_build`): refuse it on a class,
         function or module, and drop any restored instance attribute that
         would shadow behaviour its class declares
         (:func:`shadows_class_behaviour`).
      6. In every mode, write only into objects this load allocated
         (issue #638): BUILD and the container opcodes refuse any target not
         in ``self._fresh``. In strict mode, call only what
         :func:`_reduce_refusal` admits (REDUCE, OBJ, INST).

    Built on the pure-Python ``pickle._Unpickler`` because step 5 needs the
    BUILD opcode, which the C unpickler gives no hook for. Measured on a full
    17-map world save (440 KiB): 6 ms in C, 54 ms here, paid once per load.

    Every rewrite / placeholder / rejection / drop is recorded on
    ``self.events`` and emitted via :mod:`logging`.
    """

    #: What the pure-Python ``find_class`` reads before ``load`` has set it.
    #: The C unpickler kept these internally, so an instance built through
    #: ``__new__`` (which several callers do to exercise ``find_class`` on
    #: its own) resolved classes fine; without these it raised
    #: ``AttributeError``, read here as "unresolved", and was rejected.
    proto = 0
    fix_imports = True

    def __init__(self, file, *, strict=None, events=None):
        super().__init__(file)
        self.strict = strict_mode_enabled() if strict is None else bool(strict)
        self.events = events if events is not None else []
        self._fresh = {}

    def load(self):
        """Unpickle, keeping the loader's documented failure contract.

        The pure-Python engine reports a corrupt stream as whatever broke --
        ``KeyError`` for an unknown opcode, ``IndexError`` for a stack
        underflow -- where the C one raised ``UnpicklingError``. Callers
        catch the documented types, so the rest are re-raised as
        ``UnpicklingError``.
        """
        self._fresh = {}
        try:
            return super().load()
        except (pickle.UnpicklingError, EOFError, MemoryError, RecursionError):
            raise
        except Exception as exc:
            raise pickle.UnpicklingError(
                f"Corrupt save payload ({type(exc).__name__}: {exc})"
            ) from exc
        finally:
            self._fresh = {}

    def load_build(self):
        """BUILD, gated (issue #620): never onto a class, function or module,
        and never an attribute that shadows what the instance's class
        declares. Refused and dropped in every mode -- strictness governs
        which classes may appear, and no save this engine writes needs
        either of these."""
        stack = self.stack
        if len(stack) >= 2:
            inst = stack[-2]
            if isinstance(inst, _UNBUILDABLE):
                label = getattr(inst, "__qualname__", type(inst).__name__)
                self._record("rejected", getattr(inst, "__module__", "?"), label,
                             reason="BUILD on a non-instance")
                raise RestrictedUnpicklingError(
                    f"Refusing to restore state onto {label!r}: saves restore "
                    "instances, never classes, functions or modules"
                )
            self._require_fresh(inst, "BUILD")
            stack[-1] = self._without_shadowing(type(inst), stack[-1])
        pickle._Unpickler.load_build(self)

    # -- allocation tracking (issue #638) ----------------------------------
    #
    # ``_fresh`` maps id -> object for everything this load allocated. It
    # holds a strong reference, so an id can never be recycled onto a shared
    # object mid-load and pass the check by coincidence.

    def _mark_fresh(self, obj):
        fresh = getattr(self, "_fresh", None)
        if fresh is None:
            fresh = self._fresh = {}
        fresh[id(obj)] = obj

    def _require_fresh(self, target, opcode):
        """Refuse ``opcode`` writing into anything this load did not
        allocate: a shared engine singleton, an enum member, a cached regex."""
        if getattr(self, "_fresh", {}).get(id(target)) is target:
            return
        cls = type(target)
        self._record("rejected", cls.__module__, cls.__qualname__,
                     reason=f"{opcode} on an object this load did not create")
        raise RestrictedUnpicklingError(
            f"Refusing {opcode} onto a {cls.__qualname__!r} this save did not "
            "create: a load may only fill in objects it allocated"
        )

    def _refuse_call(self, func, args):
        """Strict-mode gate for every opcode that calls a stream object."""
        if not getattr(self, "strict", True):
            return
        reason = _reduce_refusal(func, args)
        if reason is None:
            return
        label = getattr(func, "__qualname__", type(func).__qualname__)
        self._record("rejected", getattr(func, "__module__", "?"), label,
                     reason=f"call refused: {reason}")
        raise RestrictedUnpicklingError(
            f"Refusing to call {label!r} while loading a save: {reason}"
        )

    def load_reduce(self):
        stack = self.stack
        if len(stack) >= 2:
            func, args = stack[-2], stack[-1]
            self._refuse_call(func, args)
            fresh = _call_allocates(func, args)
        else:
            fresh = False
        pickle._Unpickler.load_reduce(self)
        if fresh:
            self._mark_fresh(stack[-1])

    def _instantiate(self, klass, args):
        """OBJ / INST: a call when there are arguments (or ``klass`` is not a
        class), else ``klass.__new__(klass)`` -- gated like REDUCE / NEWOBJ."""
        if args or not isinstance(klass, type) or hasattr(klass, "__getinitargs__"):
            self._refuse_call(klass, tuple(args))
            fresh = _call_allocates(klass, tuple(args))
        else:
            fresh = _new_allocates(klass)
        pickle._Unpickler._instantiate(self, klass, args)
        if fresh:
            self._mark_fresh(self.stack[-1])

    def _newobj(self, depth, opcode_loader):
        stack = self.stack
        cls = stack[-depth] if len(stack) >= depth else None
        if cls is not None and not isinstance(cls, type):
            # The C unpickler refuses this too; __new__ lookup on a
            # non-class would reach an arbitrary object's attribute.
            label = type(cls).__qualname__
            self._record("rejected", type(cls).__module__, label,
                         reason="NEWOBJ on a non-class")
            raise RestrictedUnpicklingError(
                f"Refusing NEWOBJ on a {label!r}: it is not a class")
        opcode_loader(self)
        if cls is not None and _new_allocates(cls):
            self._mark_fresh(stack[-1])

    def load_newobj(self):
        self._newobj(2, pickle._Unpickler.load_newobj)

    def load_newobj_ex(self):
        self._newobj(3, pickle._Unpickler.load_newobj_ex)

    def _allocating(loader):
        """Wrap an opcode that pushes a brand-new container."""
        def load(self):
            loader(self)
            self._mark_fresh(self.stack[-1])
        return load

    def _writing(loader, locate):
        """Wrap an opcode that writes into the object ``locate`` finds."""
        def load(self):
            try:
                target = locate(self)
            except IndexError:
                target = None  # underflow: let the stock loader report it
            else:
                self._require_fresh(target, loader.__name__[5:].upper())
            loader(self)
        return load

    dispatch = dict(pickle._Unpickler.dispatch)
    dispatch[pickle.BUILD[0]] = load_build
    dispatch[pickle.REDUCE[0]] = load_reduce
    dispatch[pickle.NEWOBJ[0]] = load_newobj
    dispatch[pickle.NEWOBJ_EX[0]] = load_newobj_ex
    for _code, _loader in (
        (pickle.EMPTY_LIST, pickle._Unpickler.load_empty_list),
        (pickle.EMPTY_DICT, pickle._Unpickler.load_empty_dictionary),
        (pickle.EMPTY_SET, pickle._Unpickler.load_empty_set),
        (pickle.LIST, pickle._Unpickler.load_list),
        (pickle.DICT, pickle._Unpickler.load_dict),
    ):
        dispatch[_code[0]] = _allocating(_loader)
    for _code, _loader, _locate in (
        (pickle.APPEND, pickle._Unpickler.load_append,
         lambda self: self.stack[-2]),
        (pickle.SETITEM, pickle._Unpickler.load_setitem,
         lambda self: self.stack[-3]),
        (pickle.APPENDS, pickle._Unpickler.load_appends,
         lambda self: self.metastack[-1][-1]),
        (pickle.SETITEMS, pickle._Unpickler.load_setitems,
         lambda self: self.metastack[-1][-1]),
        (pickle.ADDITEMS, pickle._Unpickler.load_additems,
         lambda self: self.metastack[-1][-1]),
    ):
        dispatch[_code[0]] = _writing(_loader, _locate)
    del _code, _loader, _locate, _allocating, _writing

    def _without_shadowing(self, cls, state):
        """``state`` minus every key :func:`shadows_class_behaviour` refuses,
        in both the ``__dict__`` and the slot-state halves."""
        def clean(part):
            if not isinstance(part, dict):
                return part
            kept = {}
            for key, value in part.items():
                if shadows_class_behaviour(cls, key):
                    self._record("dropped", cls.__module__, cls.__qualname__,
                                 attribute=key)
                    continue
                kept[key] = value
            return kept

        if isinstance(state, tuple) and len(state) == 2:
            return (clean(state[0]), clean(state[1]))
        return clean(state)

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
        if kind in ("rejected", "dropped"):
            logger.warning("SafeUnpickler %s %s.%s %s", kind, module, name,
                           extra.get("attribute") or extra.get("reason") or "")
        else:
            logger.debug("SafeUnpickler %s: %s.%s", kind, module, name)

    @staticmethod
    def _sanitize_type_name(raw):
        """Coerce an arbitrary string into something ``type()`` will accept.

        A crafted pickle can name a module containing characters that are legal
        in a pickle stream but illegal in a Python type name -- most sharply a
        NUL, which makes ``type()`` raise ``ValueError`` outright. That raise
        happened *after* ``find_class``'s guarded ``super()`` call, so it
        escaped as an unhandled crash rather than degrading to a placeholder.
        Everything outside ``[A-Za-z0-9_]`` collapses to an underscore.
        """
        cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw)
        return cleaned or "_"

    def _make_placeholder(self, module, name):
        placeholder_class_name = self._sanitize_type_name(
            f"LegacyMissing_{module.replace('.', '_')}_{name}"
        )
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
        # Default True, not False: an instance built via __new__ (bypassing
        # __init__) must not be a back door to placeholder synthesis now that
        # strict is the posture everywhere else. Callers that genuinely want
        # legacy behaviour pass strict=False and say so.
        strict = getattr(self, "strict", True)
        if getattr(self, "proto", 0) < 3 and getattr(self, "fix_imports", True):
            # Protocols 0-2 spell stdlib names the Python 2 way
            # (``__builtin__.set``, ``copy_reg._reconstructor``); the stock
            # find_class maps them, so the allow-list must judge the mapped
            # name or it refuses every set in a protocol-2 save.
            if (module, name) in _compat_pickle.NAME_MAPPING:
                module, name = _compat_pickle.NAME_MAPPING[(module, name)]
            elif module in _compat_pickle.IMPORT_MAPPING:
                module = _compat_pickle.IMPORT_MAPPING[module]
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
            if strict and not (_is_allowed(module, name)
                               and _resolved_global_is_trusted(cls)):
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
    # Write the value explicitly in BOTH directions. Deleting the variable used
    # to mean "not strict"; since the default flip, absence means strict, so a
    # pop here would run the child strictly and silently invert strict=False.
    # Setting it also stops a stray value in the parent's environment from
    # overriding the caller's argument.
    env[STRICT_ENV_VAR] = "1" if strict else "0"

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
