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
import pickle
import logging
import importlib
import pkgutil

logger = logging.getLogger(__name__)

# Reject saves larger than this before unpickling. Current full-game saves are
# well under 1 MB; 5 MB leaves generous headroom while capping memory/CPU
# pressure from an intentionally bloated pickle. See issue #13, Phase 2.
DEFAULT_MAX_SAVE_BYTES = 5 * 1024 * 1024

# Environment variable that toggles strict allow-list enforcement. Kept as an
# env var (rather than plumbing a config handle through the loader) so it is a
# single, testable control surface reachable from any entry point.
STRICT_ENV_VAR = "HOV_STRICT_UNPICKLE"


class RestrictedUnpicklingError(pickle.UnpicklingError):
    """Raised in strict mode when a class is not on the allow-list."""


class SaveTooLargeError(Exception):
    """Raised when a save payload exceeds the configured size cap."""


# ---------------------------------------------------------------------------
# Controlled module-rewrite map (narrow, static allow-list of bare -> src.*)
# ---------------------------------------------------------------------------

# Bare, top-level engine module names that legacy saves and map JSON reference
# by their pre-``src.``-convention path. Anything in this set is rewritten to
# ``src.<name>``; every other module path passes through unchanged. Keeping the
# rewrite as an explicit membership test (not a lambda predicate) means the set
# of paths we will silently redirect is auditable at a glance.
LEGACY_BARE_MODULES = frozenset({
    "actions", "animations", "combat_event_config", "combatant",
    "config_manager", "coordinate_config", "enchant_tables", "events",
    "functions", "genericng", "interface", "inventory_utils", "items",
    "loot_tables", "moves", "narration", "npc", "npc_ai_config",
    "objects", "positions", "scenario_config", "secure_pickle",
    "shop_conditions", "skilltree", "states", "story", "tiles",
    "tilesets", "universe", "player",
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

# Top-level engine modules whose classes may legitimately appear in a save.
_ALLOWLIST_MODULES = (
    "src.items", "src.npc", "src.states", "src.objects", "src.player",
    "src.tiles", "src.universe", "src.combatant", "src.events",
    "src.actions", "src.functions", "src.narration",
)

# Engine packages whose submodules also contribute classes (e.g. story chapters,
# per-weapon move modules). ``_collect_package`` also collects the package root.
_ALLOWLIST_PACKAGES = ("src.story", "src.moves")

# Known-safe stdlib globals that pickle's reconstruction machinery references
# for ordinary object graphs. These resolve fine but are not "engine" classes,
# so they must be allow-listed explicitly for strict mode to accept real saves.
_SAFE_STDLIB = frozenset({
    ("builtins", "object"), ("builtins", "set"), ("builtins", "frozenset"),
    ("builtins", "list"), ("builtins", "dict"), ("builtins", "tuple"),
    ("builtins", "bytearray"), ("builtins", "complex"),
    ("copyreg", "_reconstructor"), ("copyreg", "__newobj__"),
    ("collections", "OrderedDict"), ("collections", "defaultdict"),
})

_allowlist_cache = None


def _collect_module(mod_name, allowed):
    """Add every class object reachable from ``mod_name`` to ``allowed``."""
    try:
        mod = importlib.import_module(mod_name)
    except Exception:  # pragma: no cover - defensive; missing optional module
        logger.debug("Allow-list: could not import %s", mod_name)
        return
    for obj in vars(mod).values():
        if isinstance(obj, type):
            allowed.add((obj.__module__, obj.__name__))


def _collect_package(pkg_name, allowed):
    """Add classes from a package and each of its immediate submodules."""
    try:
        pkg = importlib.import_module(pkg_name)
    except Exception:  # pragma: no cover - defensive
        logger.debug("Allow-list: could not import package %s", pkg_name)
        return
    _collect_module(pkg_name, allowed)
    for info in pkgutil.iter_modules(getattr(pkg, "__path__", [])):
        _collect_module(f"{pkg_name}.{info.name}", allowed)


def _build_allowlist():
    """Introspect the engine modules and return the set of allowed classes.

    Each entry is a ``(module, name)`` tuple keyed on the class's real
    ``__module__`` (which is what pickle stores), so canonical rewrites line up
    with allow-list membership.
    """
    allowed = set(_SAFE_STDLIB)
    for mod_name in _ALLOWLIST_MODULES:
        _collect_module(mod_name, allowed)
    for pkg_name in _ALLOWLIST_PACKAGES:
        _collect_package(pkg_name, allowed)
    return allowed


def get_allowlist():
    """Return the cached class allow-list, building it on first use."""
    global _allowlist_cache
    if _allowlist_cache is None:
        _allowlist_cache = _build_allowlist()
    return _allowlist_cache


def _is_allowed(module, name):
    return (module, name) in get_allowlist()


def strict_mode_enabled():
    """Return True when strict allow-list enforcement is requested via env."""
    return os.environ.get(STRICT_ENV_VAR, "").strip().lower() in (
        "1", "true", "yes", "on",
    )


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
        except (ModuleNotFoundError, AttributeError):
            cls = None

        if cls is not None:
            if strict and not _is_allowed(module, name):
                self._record("rejected", module, name)
                raise RestrictedUnpicklingError(
                    f"Class {module}.{name} is not on the save allow-list"
                )
            return cls

        # Unresolved class.
        if strict:
            self._record("rejected", module, name)
            raise RestrictedUnpicklingError(
                f"Class {module}.{name} could not be resolved and strict "
                f"unpickling is enabled"
            )
        self._record("placeholder", module, name)
        return self._make_placeholder(module, name)


def safe_pickle_load(fp, *, strict=None, max_bytes=DEFAULT_MAX_SAVE_BYTES,
                     events=None):
    """Deserialize a save payload with size capping and gated class resolution.

    Args:
        fp: A binary file-like object positioned at the start of the payload.
        strict: Force strict mode on/off; ``None`` resolves from the env var.
        max_bytes: Reject payloads larger than this (``None`` disables the cap).
        events: Optional list to collect structured diagnostics onto.

    Raises:
        SaveTooLargeError: The payload exceeds ``max_bytes``.
        RestrictedUnpicklingError: Strict mode rejected a class.
        pickle.UnpicklingError / EOFError: Corrupt payload.
    """
    raw = fp.read()
    if max_bytes is not None and len(raw) > max_bytes:
        raise SaveTooLargeError(
            f"Save payload of {len(raw)} bytes exceeds the {max_bytes}-byte cap"
        )
    return SafeUnpickler(io.BytesIO(raw), strict=strict, events=events).load()
