"""Keep bare ``x`` and ``src.x`` imports pointing at one module object.

Production entry points (``wsgi.py``, ``tools/run_api.py``) put BOTH the repo
root and ``src/`` on ``sys.path``. As a result ``import objects`` and
``import src.objects`` resolve to two *separate* module objects, each with its
own classes and module-level state. That splits the API/engine boundary:

* ``isinstance(engine_obj, src.items.Item)`` is ``False`` even though the object
  *is* an ``items.Item`` (different class objects), and
* module-level registries (e.g. ``items.unique_items_spawned``,
  ``narration``'s context buffer) desync between the two copies.

``tests/conftest.py`` installs an equivalent hook, which is why the test suite
never sees the split. :func:`install` mirrors that for the live server so
production behaves the same. Call it from the entry point AFTER ``sys.path`` is
set up and BEFORE the application is imported.

The long-term fix is to standardize every import on the ``src.`` path (tracked
as one issue per module); this hook makes the running process correct in the
meantime and is harmless once the imports are unified.
"""

import builtins
import sys

# Bare names that must NOT be aliased from ``src.*``. ``api`` is excluded to
# match conftest (the test package ``tests/api`` collides with ``src.api``);
# keeping the exclusion avoids any divergence between test and prod behavior.
_NO_BARE_ALIAS = frozenset({"api"})

# Canonical dependency order. Importing these as ``src.*`` first guarantees the
# ``src.*`` object is canonical and the bare name aliases to it, regardless of
# which import style later code uses. Mirrors conftest's ``_core_order``.
_CORE_ORDER = (
    "animations",
    "genericng",
    "items",
    "states",
    "enchant_tables",
    "objects",
    "loot_tables",
    "actions",
    "tiles",
    "universe",
    "positions",
    "moves",
    "combatant",
    "npc",
    "skilltree",
    "switch",
    "player",
)

_installed = False


def _sync_all_src() -> None:
    """Point every bare name at its ``src.*`` counterpart (src is canonical).

    Covers packages and their submodules at any depth (e.g. ``npc._enemies``,
    ``story.effects``, ``tilesets.dark_grotto``). Always aliases bare -> src so
    callers that imported a module either way share one object; the ``src.*``
    side is treated as canonical and never overwritten by a stray bare load.
    """
    for key in list(sys.modules.keys()):
        if not key.startswith("src.") or sys.modules[key] is None:
            continue
        bare = key[4:]
        if not bare or bare.split(".", 1)[0] in _NO_BARE_ALIAS:
            continue
        if sys.modules.get(bare) is not sys.modules[key]:
            sys.modules[bare] = sys.modules[key]


def install() -> None:
    """Install the bare<->src import sync hook and pre-load core modules.

    Idempotent: safe to call from multiple entry points / on reload.
    """
    global _installed
    if _installed:
        return
    _installed = True

    original_import = builtins.__import__

    def _synchronized_import(name, *args, **kwargs):
        result = original_import(name, *args, **kwargs)
        # Importing any src.* module may pull in submodules as a side effect;
        # re-sync the whole src.* set so every bare alias points at it. This is
        # bounded work (only fires on src.* imports, which are rare at runtime)
        # and keeps src.* canonical regardless of import order.
        if name.startswith("src."):
            _sync_all_src()
        elif (
            "." not in name
            and name not in _NO_BARE_ALIAS
            and f"src.{name}" in sys.modules
            and name in sys.modules
            and sys.modules[name] is not sys.modules[f"src.{name}"]
        ):
            # Bare module loaded fresh while a canonical src.* already exists:
            # redirect the bare name to the canonical object.
            sys.modules[name] = sys.modules[f"src.{name}"]
        return result

    builtins.__import__ = _synchronized_import

    # Force ``src.*`` to be the canonical object for each core module, in
    # dependency order. Best-effort: circular-dep modules that fail here are
    # handled by the hook on their first real import.
    for mod in _CORE_ORDER:
        if mod in sys.modules and f"src.{mod}" in sys.modules:
            sys.modules[f"src.{mod}"] = sys.modules[mod]
            continue
        if mod in sys.modules or f"src.{mod}" in sys.modules:
            continue
        try:
            loaded = __import__(f"src.{mod}", fromlist=["*"])
            sys.modules[mod] = loaded
            sys.modules[f"src.{mod}"] = loaded
        except Exception:
            pass
    _sync_all_src()
