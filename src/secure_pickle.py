"""secure_pickle
Phase 1 hardening for game save (pickle) deserialization.

Trust Model:
    - Pickle save files are treated as trusted local artifacts created by the game itself.
    - NEVER open a save file from an untrusted origin with strict mode disabled.
    - Strict mode (config flag / env var) enforces an allow-list and rejects unknown classes.

Features Implemented (Issue #13 Phase 1):
    1. Allow‑list of permitted (module, class) tuples built at import time.
    2. Config + environment driven strict mode toggle:
         * config_dev.ini -> [Startup] strict_unpickle = {True|False}
         * env override: HOV_STRICT_UNPICKLE=(1/0/true/false)
    3. Placeholder synthesis only allowed when NOT strict; placeholders tagged with _legacy_placeholder=True
    4. Diagnostic event logging in EVENT_LOG for: unknown class, placeholder creation, rejection.
    5. Inline TODO markers for remaining risk areas (integrity header, checksum, size limits, migration away from pickle).

Remaining Risks / TODO (Phases 2+):
    - TODO: Integrity header + checksum to detect tampering.
    - TODO: Maximum file size cap prior to unpickling.
    - TODO: Narrow rewrite mapping (currently none applied).
    - TODO: Data-only (JSON/msgpack) format & automatic migration.
    - TODO: Sandboxed unpickling in a subprocess.

Usage:
    from secure_pickle import load, save_unsafe
    obj = load('file.sav')  # honors strict flag
    obj = load('file.sav', strict=True)  # override

NOTE: Saving still uses vanilla pickle via functions.save(). This module focuses on defensive loading first.
"""
from __future__ import annotations
import os
import pickle
import inspect
import importlib
import pkgutil
from typing import Set, Tuple, Any, List, Optional
import configparser

# Public event log structure entries are dicts with: type, module, name, strict, detail
EVENT_LOG: List[dict] = []

ALLOWED_CLASS_WHITELIST: Set[Tuple[str, str]] = set()
_ALLOWLIST_INITIALIZED = False

# Exception raised when a disallowed class is encountered in strict mode
class RestrictedUnpicklingError(Exception):
    pass


def _log(event_type: str, module: str, name: str, strict: bool, detail: str = ""):
    EVENT_LOG.append({
        "type": event_type,
        "module": module,
        "name": name,
        "strict": strict,
        "detail": detail
    })


def _iter_package_classes(root_pkg_name: str):
    """Yield (module_name, class_name, class_obj) for all classes inside a root package or single module."""
    try:
        root = importlib.import_module(root_pkg_name)
    except ImportError:
        return  # silently ignore missing optional packages
    if hasattr(root, "__path__"):  # it's a package
        for finder, modname, ispkg in pkgutil.walk_packages(root.__path__, root.__name__ + "."):
            try:
                mod = importlib.import_module(modname)
            except Exception:
                continue
            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if obj.__module__ == mod.__name__:
                    yield (obj.__module__, name, obj)
    else:  # single module file
        for name, obj in inspect.getmembers(root, inspect.isclass):
            if obj.__module__ == root.__name__:
                yield (obj.__module__, name, obj)


def _build_allowlist():
    global ALLOWED_CLASS_WHITELIST, _ALLOWLIST_INITIALIZED
    if _ALLOWLIST_INITIALIZED:
        return
    # Base targets outlined in Issue #13 + additional modules required for Player objects & combat moves.
    targets = ["items", "npc", "states", "objects", "story", "player", "moves", "skilltree"]
    for pkg in targets:
        for module_name, class_name, _ in _iter_package_classes(pkg):
            ALLOWED_CLASS_WHITELIST.add((module_name, class_name))
    _ALLOWLIST_INITIALIZED = True


# Configuration / Strict Mode -------------------------------------------------

def _read_config_strict_default() -> bool:
    config = configparser.ConfigParser()
    base_dir = os.path.dirname(__file__)
    cfg_path = os.path.abspath(os.path.join(base_dir, '..', 'config_dev.ini'))
    strict_default = False
    if os.path.exists(cfg_path):
        try:
            config.read(cfg_path)
            if config.has_option('Startup', 'strict_unpickle'):
                strict_default = config.getboolean('Startup', 'strict_unpickle')
        except Exception:
            pass
    env_val = os.environ.get('HOV_STRICT_UNPICKLE')
    if env_val is not None:
        if env_val.lower() in ("1", "true", "yes", "on"):
            strict_default = True
        elif env_val.lower() in ("0", "false", "no", "off"):
            strict_default = False
    return strict_default


STRICT_MODE_DEFAULT = _read_config_strict_default()
_build_allowlist()


class SafeUnpickler(pickle.Unpickler):
    """Hardened unpickler enforcing allow-list & placeholder policy.

    NOTE: No module path rewrites are performed in Phase 1. Future phases may add a REMAP dict.
    """
    def __init__(self, *args, strict: Optional[bool] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.strict = STRICT_MODE_DEFAULT if strict is None else strict

    # TODO: Add header / checksum validation prior to invoking parent .load() (Phase 2)

    def find_class(self, module: str, name: str):  # noqa: D401
        tup = (module, name)
        if tup in ALLOWED_CLASS_WHITELIST:
            return super().find_class(module, name)
        # Not allowed
        if self.strict:
            _log("reject", module, name, True, "Disallowed class in strict mode")
            raise RestrictedUnpicklingError(f"Disallowed class encountered during strict unpickling: {module}.{name}")
        # Legacy placeholder path (non-strict mode)
        placeholder = type(name, (object,), {"_legacy_placeholder": True, "__module__": module})
        _log("placeholder", module, name, False, "Created legacy placeholder class")
        return placeholder


# Public API ------------------------------------------------------------------

def load(filename: str, strict: Optional[bool] = None) -> Any:
    """Load a pickle file via SafeUnpickler.

    :param filename: path to pickle file
    :param strict: override strict mode (True/False) else default from config/env
    """
    with open(filename, 'rb') as f:
        unpickler = SafeUnpickler(f, strict=strict)
        return unpickler.load()


def save_unsafe(filename: str, obj: Any):  # convenience for symmetry (not used yet)
    with open(filename, 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)


__all__ = [
    'load',
    'save_unsafe',
    'SafeUnpickler',
    'RestrictedUnpicklingError',
    'EVENT_LOG',
    'ALLOWED_CLASS_WHITELIST'
]
