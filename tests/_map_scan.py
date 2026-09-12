"""Shared scan infrastructure for the shipped-map structural guards.

The guards over authored map objects and events used to each glob the JSON,
step over ``metadata``, read ``tile["objects"]`` and resolve the class by
hand. They now share one parse (``map_data``), one placement walk
(``object_placements`` / ``event_placements``) that reads both authored
payload shapes -- the legacy full dump and the #463 placeholder -- and one
class resolution.

Sharing this is not tidiness. The scan is the *population* those guards assert
over, and a scan that quietly stops matching approves of everything (see
``tests/_moves_scan.py``, which exists for the same reason after three copies
of one signal list went stale in a single edit). One derivation means one place
where "what a placement is" can go wrong, and one place to fix it.

**Malformed placements raise, deliberately.** Skipping one reads as defensive
and is not: a payload the game would refuse at load is a broken map, and
skipping it removes exactly the placement most likely to be wrong from every
guard downstream. What counts as malformed is spelled once, in ``class_ref``
below, rather than restated here where the two could drift apart.

What ``class_ref`` checks is the payload's *shape*, never the class it names:
the trust gate lives in ``resolve_class``, which also rejects a
``src.``-prefixed module. So a guard that matches placements by class name
must resolve them too, or a stale module reference passes the guard while the
game refuses the placement. Nothing nested inside a payload's props is walked.

**No assertions live here.** A helper that asserts its own non-emptiness makes
each caller's positive control look redundant, and the callers are where the
threshold belongs -- ``> 20`` containers means something different from
``>= 10`` map files. Each module keeps its own; ``test_map_scan_helpers.py``
holds the controls for this module itself.
"""

import functools
import json
import pathlib
from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Tuple

from src import map_placeholders
from tests._source_scan import MAP_DIR


class ClassRef(NamedTuple):
    """The class an authored payload names, and the props authored with it.

    ``props`` is the legacy dump's own ``props`` dict (``{}`` when it
    authors none). For the placeholder shape it is a merged copy: ``params``
    with its ``overrides`` applied over them, in the order the loader applies
    them. Either way these are the props as AUTHORED. This walk resolves no
    classes, so it cannot see what the placeholder loader drops -- a
    constructor value its class does not list in both ``MAP_AUTHORED_PARAMS``
    and its ``__init__`` signature, and an override its class does not
    declare -- and it leaves as plain JSON the nested payloads both loaders
    deserialize into instances.
    """

    module_name: str
    class_name: str
    props: Dict[str, Any]

    @property
    def dotted(self) -> str:
        """``module.Class``, the spelling ``map_placeholders.resolve_class`` reads."""
        return f"{self.module_name}.{self.class_name}"


class Placement(NamedTuple):
    """One authored object or event on one tile of one shipped map."""

    map_name: str
    coord: str
    module_name: str
    class_name: str
    props: Dict[str, Any]

    @property
    def ref(self) -> ClassRef:
        """The class reference this placement carries."""
        return ClassRef(self.module_name, self.class_name, self.props)


def map_files() -> List[pathlib.Path]:
    """Every shipped map JSON, sorted so parametrize ids are stable."""
    return sorted(MAP_DIR.glob("*.json"))


@functools.lru_cache(maxsize=1)
def map_data() -> Tuple[Tuple[pathlib.Path, Dict[str, Any]], ...]:
    """``(path, decoded map)`` for every shipped map, parsed once per worker.

    The decoded dicts are shared across every caller and every test in the
    worker: read them, never mutate them (``tests/_ferry_fixtures.py`` deep-
    copies the one tile it hands to tests for exactly that reason).
    """
    return tuple(
        (path, json.loads(path.read_text(encoding="utf-8"))) for path in map_files()
    )


def tiles(decoded_map: Dict[str, Any]) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """The ``(coord, tile)`` pairs of one decoded map.

    ``metadata`` is a sibling key of the coordinates rather than a nested
    section, so every walk of a map has to step over it; a non-dict value is
    skipped for the same reason a coordinate key is expected to hold one.
    """
    for key, value in decoded_map.items():
        if key == "metadata" or not isinstance(value, dict):
            continue
        yield key, value


def class_ref(payload: Any) -> Optional[ClassRef]:
    """The class and props an authored payload names, in either shape.

    A #463 placeholder (``{"class": "module.Class", "params": ...}``) is
    recognised, split and read by the engine's own ``is_placeholder_payload``,
    ``split_class_ref`` and ``placeholder_params``, so a reference the game
    loads is a reference this walk sees. A reference that does not split
    into a module and a class, or ``params`` that is not an object, raises
    ``PlaceholderError`` here as it would at load; a reference that splits
    but names a class the game refuses (a ``src.``-prefixed module, a class
    off the allow-list) is refused only by ``resolve_class``.

    A legacy full dump (``__class__``/``__module__``/``props``) reads a falsy
    ``props`` as no props, as the loader does, and raises ``PlaceholderError``
    for a truthy ``props`` that is not an object, which the loader would
    silently drop. Returns None only for a value that is not a payload at
    all: not a dict, or a dump missing either class field.
    """
    if map_placeholders.is_placeholder_payload(payload):
        module_name, class_name = map_placeholders.split_class_ref(payload["class"])
        ctor_values, overrides = map_placeholders.placeholder_params(payload)
        return ClassRef(module_name, class_name, {**ctor_values, **overrides})
    if not isinstance(payload, dict):
        return None
    module_name = payload.get("__module__")
    class_name = payload.get("__class__")
    if not module_name or not class_name:
        return None
    # Read as ``Universe._deserialize_saved_instance`` reads it.
    props = payload.get("props") or {}
    if not isinstance(props, dict):
        raise map_placeholders.PlaceholderError(
            f"'props' must be an object for {module_name}.{class_name}"
        )
    return ClassRef(module_name, class_name, props)


def _placements(section: str) -> Tuple[Placement, ...]:
    """Every placement in the per-tile ``section`` list (``"objects"`` or
    ``"events"``) across every shipped map.
    """
    found = []
    for path, decoded in map_data():
        for coord, tile_data in tiles(decoded):
            for payload in tile_data.get(section) or []:
                ref = class_ref(payload)
                if ref is not None:
                    found.append(Placement(path.name, coord, **ref._asdict()))
    return tuple(found)


@functools.lru_cache(maxsize=1)
def object_placements() -> Tuple[Placement, ...]:
    """Every authored object placement across every shipped map.

    Memoised: the callers ask for it once per module plus once per
    ``parametrize`` decorator. A tuple rather than a list so a caller cannot
    reorder or extend the cached sequence -- but the ``props`` inside are not
    copied: for a legacy dump they are the shared parse (see ``map_data``) and
    must not be mutated either. Only a placeholder's ``props`` is a fresh merge.
    """
    return _placements("objects")


@functools.lru_cache(maxsize=1)
def event_placements() -> Tuple[Placement, ...]:
    """Every authored tile event across every shipped map."""
    return _placements("events")


def resolve_class(placement: Placement) -> type:
    """The class a placement names.

    Raises rather than returning None -- see the module docstring. Maps store
    the bare module name by contract (``"objects"``, not ``"src.objects"``);
    ``map_placeholders.resolve_class`` canonicalises it and applies the
    engine's allow-list, raising ``PlaceholderError`` (or its security
    subclass) for anything the game itself would refuse to load.
    """
    return map_placeholders.resolve_class(placement.ref.dotted)
