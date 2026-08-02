"""Authored-placeholder serialization for Map Editor content (issue #463).

Map JSON historically stored a full runtime-attribute dump of every placed
NPC/Item/Object/Event (``{"__class__", "__module__", "props"}`` walking
``vars(instance)``). This module defines the leaner replacement: a class
reference plus only the fields a class has explicitly declared as authored
(map-design-time) configuration.

Schema
------
A placeholder is a dict shaped like::

    {"class": "npc.MiloCurioDealer", "params": {"stock_count": 30,
                                                 "overrides": {"hidden": false}}}

``class`` is a bare ``module.ClassName`` string (the same bare-module
convention already used by legacy ``__module__`` fields and pickle saves;
see ``functions.canonical_module_name``). ``params`` holds two things:

* Real constructor keyword arguments, declared per-class via the
  ``MAP_AUTHORED_PARAMS`` class attribute (an iterable of names).
* An optional ``overrides`` sub-dict of attributes to ``setattr`` after
  construction, restricted to that class's ``MAP_AUTHORED_OVERRIDES`` allow
  list -- for fields no constructor exposes (most enemy stat blocks, generic
  ``hidden``/``hide_factor`` placement flags, etc.). Overrides are a security
  boundary as much as a data-modeling one: map JSON is attacker-influenceable,
  so anything not on the declared allow-list is dropped rather than applied.

Any value inside ``params`` may itself be a nested placeholder (for
container inventories, attached events, etc.) or the pre-existing bare
class-reference marker ``{"__class_type__": "module:ClassName"}`` (used
today by ``Container.allowed_item_types`` and ``NPCSpawnerEvent.npc_cls``,
left unchanged).

Both real map-JSON readers (the game's own boot loader,
``Universe._deserialize_saved_instance``, and the Map Editor's
``load_map()``) share the class-resolution/security-gate logic in this
module, so they can't silently diverge on which classes are trusted.
"""

import importlib
import inspect
import logging
from typing import Final

import src.functions as functions
import src.secure_pickle as secure_pickle

# Mirrors secure_pickle.py's own logger: this module is shared between the
# Flask game engine (via Universe) and the standalone Map Editor tool, and
# plain `logging` is the one diagnostic channel that works unmodified in
# both -- narration's context-local capture buffer only exists inside a
# live game session. Fallback-construction and override-application below
# use this rather than swallowing exceptions with no signal at all.
logger = logging.getLogger(__name__)

SCHEMA_VERSION: Final = 2

# Mirrors Universe.MAX_DESERIALIZE_DEPTH: map JSON is attacker-influenceable,
# so a deeply nested/cyclic-looking placeholder graph must not blow the stack.
MAX_DEPTH: Final = 100

_OVERRIDES_KEY = "overrides"


class PlaceholderError(Exception):
    """Raised for a malformed placeholder payload (bad shape, missing class)."""


class PlaceholderSecurityError(PlaceholderError):
    """Raised when a placeholder references a class outside the engine allow-list."""


def bare_module_name(module_name):
    """Strip a leading ``src.`` so a module name matches the bare-name
    convention persisted data has always used (map JSON ``__module__``
    fields, pickle saves). Public: also used by callers writing the legacy
    ``__class__``/``__module__`` shape (e.g. the Map Editor) whenever a class
    was resolved through this module's canonical-only ``resolve_class`` and
    would otherwise report a ``src.``-prefixed ``__module__``.
    """
    if module_name.startswith("src."):
        return module_name[len("src."):]
    return module_name


def class_ref_string(cls):
    """Return the bare ``module.ClassName`` reference string for ``cls``."""
    return f"{bare_module_name(cls.__module__)}.{cls.__name__}"


def resolve_class(class_ref):
    """Resolve a bare class reference string to the class object.

    Accepts both the dotted ``"module.ClassName"`` form used by placeholder
    ``class`` fields and the legacy ``"module:ClassName"`` form used by
    ``__class_type__`` markers. Always routes through
    ``functions.canonical_module_name`` + the shared ``secure_pickle``
    allow-list -- the same trust boundary the pickle save loader uses --
    so a hostile map file can't resolve an arbitrary Python global.
    """
    if not isinstance(class_ref, str):
        raise PlaceholderError(f"Malformed class reference: {class_ref!r}")
    sep = ":" if ":" in class_ref else "."
    try:
        mod_name, cls_name = class_ref.rsplit(sep, 1)
    except ValueError:
        raise PlaceholderError(f"Malformed class reference: {class_ref!r}")
    if not mod_name or not cls_name:
        raise PlaceholderError(f"Malformed class reference: {class_ref!r}")
    # Persisted data stores bare module names by contract; a "src."-prefixed
    # reference in a map file is either hand-corrupted or malicious, so this
    # rejects rather than tolerantly stripping the prefix (matching
    # Universe's existing strictness rather than the Map Editor's old
    # leniency -- see the issue #463 audit's "Risks found" section).
    if mod_name.startswith("src."):
        raise PlaceholderError(f"Invalid module reference (must be bare): {class_ref!r}")
    canonical = functions.canonical_module_name(mod_name)
    if not secure_pickle._is_allowed(canonical, cls_name):
        raise PlaceholderSecurityError(
            f"Class '{class_ref}' is not on the engine allow-list"
        )
    try:
        module = importlib.import_module(canonical)
        return getattr(module, cls_name)
    except (ImportError, AttributeError) as e:
        # A well-formed but nonexistent module/class reference (typo'd class
        # name, stale reference to a removed class) must fail the same way
        # malformed input does. Every caller (Universe._deserialize_saved_instance,
        # map_generator.load_map) only catches PlaceholderError so one bad
        # placeholder degrades gracefully instead of aborting the whole map load.
        raise PlaceholderError(f"Cannot resolve class '{class_ref}': {e}")


def _collect_class_attr(cls, attr_name, *, as_set):
    """Merge a class attribute declared anywhere in ``cls``'s MRO.

    Subclasses only need to declare what they add beyond their parent --
    this walks every ancestor so a leaf class automatically inherits its
    family base's authored surface.
    """
    merged = set() if as_set else {}
    for klass in reversed(cls.__mro__):
        value = klass.__dict__.get(attr_name)
        if not value:
            continue
        if as_set:
            merged |= set(value)
        else:
            merged.update(value)
    return merged


def authored_param_names(cls):
    """Return the set of constructor kwarg names declared authored for ``cls``."""
    return _collect_class_attr(cls, "MAP_AUTHORED_PARAMS", as_set=True)


def authored_override_names(cls):
    """Return the set of post-construction attribute names declared authored
    (overridable) for ``cls``."""
    return _collect_class_attr(cls, "MAP_AUTHORED_OVERRIDES", as_set=True)


def authored_attr_aliases(cls):
    """Return the ``{authored_name: actual_attribute_name}`` map for ``cls``.

    Most authored names match the instance attribute holding their value
    directly, so this is usually empty. A class declares
    ``MAP_AUTHORED_ATTR_ALIASES`` when the two genuinely differ -- e.g.
    ``Book`` authors under the name ``text`` (matching its constructor
    kwarg) but must read the private ``_text`` cache rather than the
    ``text`` property, since the property lazily loads the whole file from
    disk on access and would bake the entire book's contents into the
    placeholder redundantly alongside ``text_file_path``.
    """
    return _collect_class_attr(cls, "MAP_AUTHORED_ATTR_ALIASES", as_set=False)


def is_authorable(cls):
    """True if ``cls`` (or an ancestor) declares any authored-placeholder
    metadata at all -- i.e. it can be represented as a placeholder rather
    than a full legacy instance dump."""
    return bool(authored_param_names(cls)) or bool(authored_override_names(cls))


def is_placeholder_payload(payload):
    """True if ``payload`` is shaped like a placeholder, as opposed to a
    legacy full-instance dump (``__class__``/``__module__``/``props``) or a
    bare class-type marker (``__class_type__``).

    ``params`` may be omitted entirely for a zero-config placement (e.g.
    ``{"class": "npc.Slime"}``) -- requiring an explicit empty ``"params":
    {}`` on every trivial placement would be needless authoring boilerplate.
    """
    return isinstance(payload, dict) and "class" in payload


def is_class_type_marker(payload):
    return isinstance(payload, dict) and "__class_type__" in payload and len(payload) == 1


def _init_param_names(cls):
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return frozenset()
    return frozenset(p.name for p in sig.parameters.values() if p.name != "self")


# ---------------------------------------------------------------------------
# Serialization (Map Editor save path)
# ---------------------------------------------------------------------------

def to_placeholder(inst, *, nested_fallback=None):
    """Build an authored-placeholder dict for ``inst``.

    Returns ``None`` if ``inst``'s class declares no authored metadata at
    all -- callers should fall back to legacy full-instance serialization
    for those (nothing here forces every class to be representable).

    A name may be declared in both ``MAP_AUTHORED_PARAMS`` and
    ``MAP_AUTHORED_OVERRIDES`` (family base classes commonly declare their
    whole stat block as both, since some concrete subclasses accept it as a
    constructor kwarg -- e.g. ``Merchant`` -- while others hardcode it and
    can only take it as a post-construction override -- e.g. ``Slime``).
    Each name is routed to exactly one bucket per concrete class: ``params``
    if that class's ``__init__`` actually accepts it, otherwise
    ``overrides`` if declared there -- never both, to avoid writing the same
    value twice.

    ``nested_fallback``, if given, is called as ``nested_fallback(value)``
    to serialize a nested attribute value that is itself a non-authorable
    instance (e.g. a Container holding an item class with no declared
    metadata yet); its return value is embedded as-is. Without it, such a
    value raises ``PlaceholderError`` rather than silently full-dumping.
    """
    cls = type(inst)
    param_names = authored_param_names(cls)
    override_names = authored_override_names(cls)
    if not param_names and not override_names:
        return None

    aliases = authored_attr_aliases(cls)
    sig_names = _init_param_names(cls)
    raw_params = {}
    raw_override_candidates = {}
    for name in sorted(param_names | override_names):
        source_attr = aliases.get(name, name)
        if not hasattr(inst, source_attr):
            continue
        value = getattr(inst, source_attr)
        if name in param_names and name in sig_names:
            raw_params[name] = value
        elif name in override_names:
            raw_override_candidates[name] = value

    def ser(value):
        return _serialize_value(value, nested_fallback=nested_fallback)

    params = {name: ser(value) for name, value in raw_params.items()}
    overrides = _prune_default_overrides(cls, raw_params, raw_override_candidates, ser, aliases)
    if overrides:
        params[_OVERRIDES_KEY] = overrides

    return {"class": class_ref_string(cls), "params": params}


def _prune_default_overrides(cls, raw_params, raw_override_candidates, ser, aliases):
    """Drop override candidates whose value matches what a freshly
    constructed instance of the same class (built with the same authored
    ctor kwargs) already has. Returns the surviving candidates already
    serialized via ``ser``.

    Without this, every hardcoded-stat enemy class (Slime, KingSlime, ...)
    would dump its *entire* stat/resistance block on every single
    placement, even completely untouched ones -- since those classes'
    zero-arg constructors route the whole block through the override
    bucket (see NPC.MAP_AUTHORED_OVERRIDES). Pruning collapses an untouched
    placement to an empty ``overrides`` dict; only a genuine authored delta
    (a map author's explicit stat tweak) survives.

    Comparison happens on the *serialized* (``ser``-passed) form, not the
    raw Python value: most engine classes (Item, NPC, ...) don't define
    ``__eq__``, so a raw ``!=`` between two separately-constructed instances
    holding identical data (e.g. a merchant's hardcoded ``always_stock``
    item list) would always report "different" by object identity alone.
    Serializing first reduces both sides to JSON-comparable primitives/
    dicts/lists, so structurally-identical-but-distinct-instance values
    correctly prune away too.

    If ``cls(**raw_params)`` can't be constructed without runtime context
    this function doesn't have (most Object/Event classes require `player`/
    `tile`), every candidate is kept rather than risk silently dropping real
    customization -- pruning is an optimization, never a correctness
    requirement of the format.
    """
    if not raw_override_candidates:
        return {}
    try:
        reference = cls(**raw_params)
    except Exception:
        return {name: ser(value) for name, value in raw_override_candidates.items()}

    pruned = {}
    for name, value in raw_override_candidates.items():
        serialized_value = ser(value)
        try:
            default_value = getattr(reference, aliases.get(name, name))
        except AttributeError:
            pruned[name] = serialized_value
            continue
        try:
            same = serialized_value == ser(default_value)
        except PlaceholderError:
            same = False
        if not same:
            pruned[name] = serialized_value
    return pruned


def _serialize_value(value, *, nested_fallback=None):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if isinstance(value, type):
        return {"__class_type__": f"{bare_module_name(value.__module__)}:{value.__name__}"}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v, nested_fallback=nested_fallback) for v in value]
    if isinstance(value, dict):
        return {
            k: _serialize_value(v, nested_fallback=nested_fallback)
            for k, v in value.items()
        }
    if hasattr(value, "__dict__"):
        placeholder = to_placeholder(value, nested_fallback=nested_fallback)
        if placeholder is not None:
            return placeholder
        if nested_fallback is not None:
            return nested_fallback(value)
        raise PlaceholderError(
            f"{type(value).__name__} has no authored-placeholder metadata "
            "declared and no legacy fallback was supplied"
        )
    return str(value)


# ---------------------------------------------------------------------------
# Instantiation (shared by Universe's boot loader and the Map Editor's loader)
# ---------------------------------------------------------------------------

def instantiate_placeholder(payload, *, player=None, tile=None, _depth=0):
    """Build a fresh runtime instance from a placeholder dict.

    Mirrors ``Universe._deserialize_saved_instance``'s contract: resolve the
    class through the shared security gate, build constructor kwargs from
    the declared authored params (injecting ``player``/``tile`` exactly as
    the existing ``MapTile.spawn_*`` methods already do), then apply any
    ``overrides`` via ``setattr``, filtered to that class's declared
    allow-list -- unrecognized override keys are dropped, never applied.
    """
    if _depth > MAX_DEPTH:
        raise PlaceholderError("Placeholder nesting exceeded maximum depth")
    if not is_placeholder_payload(payload):
        raise PlaceholderError(f"Not a placeholder payload: {payload!r}")

    class_ref = payload.get("class")
    params = payload.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise PlaceholderError(f"'params' must be an object for {class_ref!r}")

    cls = resolve_class(class_ref)
    overrides = params.get(_OVERRIDES_KEY) or {}
    if not isinstance(overrides, dict):
        overrides = {}
    ctor_values = {k: v for k, v in params.items() if k != _OVERRIDES_KEY}

    def resolve_nested(value):
        return _resolve_nested_value(value, player=player, tile=tile, depth=_depth + 1)

    ctor_values = {k: resolve_nested(v) for k, v in ctor_values.items()}

    authored = authored_param_names(cls)
    sig_names = _init_param_names(cls)
    kwargs = {k: v for k, v in ctor_values.items() if k in authored and k in sig_names}
    if "player" in sig_names and "player" not in kwargs and player is not None:
        kwargs["player"] = player
    if "tile" in sig_names and "tile" not in kwargs and tile is not None:
        kwargs["tile"] = tile

    try:
        inst = cls(**kwargs)
    except Exception as e:
        logger.debug(
            "instantiate_placeholder: %s(**%r) failed (%s); falling back to "
            "a bare __new__ instance", cls.__name__, kwargs, e,
        )
        inst = cls.__new__(cls)
        try:
            cls.__init__(inst)
        except Exception as e2:
            logger.debug(
                "instantiate_placeholder: bare %s.__init__() also failed (%s); "
                "instance left partially constructed", cls.__name__, e2,
            )

    allowed_overrides = authored_override_names(cls)
    for key, value in overrides.items():
        if key not in allowed_overrides:
            continue
        try:
            setattr(inst, key, resolve_nested(value))
        except Exception as e:
            logger.debug(
                "instantiate_placeholder: setattr(%s, %r, ...) override failed (%s)",
                cls.__name__, key, e,
            )

    return inst


def _resolve_nested_value(value, *, player, tile, depth):
    if depth > MAX_DEPTH:
        raise PlaceholderError("Placeholder nesting exceeded maximum depth")
    if is_placeholder_payload(value):
        return instantiate_placeholder(value, player=player, tile=tile, _depth=depth)
    if is_class_type_marker(value):
        return resolve_class(value["__class_type__"])
    if isinstance(value, list):
        return [_resolve_nested_value(v, player=player, tile=tile, depth=depth + 1) for v in value]
    if isinstance(value, dict):
        return {
            k: _resolve_nested_value(v, player=player, tile=tile, depth=depth + 1)
            for k, v in value.items()
        }
    return value
