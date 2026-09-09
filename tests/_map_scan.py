"""Shared scan infrastructure for the shipped-map structural guards.

Three modules added by the same change each walked ``src/resources/maps`` the
same way — glob the JSON, skip the ``metadata`` key and any non-dict value,
read ``tile["objects"]``, then resolve ``props["__module__"]``/``__class__``
through ``importlib``:

* ``test_container_open_narration`` — is any shipped container narrated a lid?
* ``test_object_action_dispatch_contract`` — does every authored keyword
  dispatch to a real handler?
* ``test_map_object_names_unique`` — the tile-walk half of it.

Sharing this is not tidiness. The scan is the *population* those guards assert
over, and a scan that quietly stops matching approves of everything (see
``tests/_moves_scan.py``, which exists for the same reason after three copies
of one signal list went stale in a single edit). One derivation means one place
where "what a placement is" can go wrong, and one place to fix it.

**Class resolution raises, deliberately.** One of the two copies swallowed
``ImportError``/``AttributeError`` and skipped the row, which reads as
defensive and is not: an unresolvable ``__module__``/``__class__`` pair in a
shipped map is a broken map, and skipping it removes exactly the placement most
likely to be wrong from every guard downstream. Every shipped placement
resolves today, so there is nothing to be lenient about.

**No assertions live here.** A helper that asserts its own non-emptiness makes
each caller's positive control look redundant, and the callers are where the
threshold belongs — ``> 20`` containers means something different from
``>= 10`` map files. Each module keeps its own.
"""

import functools
import importlib
import json
import pathlib
import sys
from typing import Any, Dict, Iterator, List, NamedTuple, Tuple

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

MAP_DIR = _ROOT / "src" / "resources" / "maps"


class Placement(NamedTuple):
    """One authored object on one tile of one shipped map."""

    map_name: str
    coord: str
    module_name: str
    class_name: str
    props: Dict[str, Any]


def map_files() -> List[pathlib.Path]:
    """Every shipped map JSON, sorted so parametrize ids are stable."""
    return sorted(MAP_DIR.glob("*.json"))


def tiles(map_data: Dict[str, Any]) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """The ``(coord, tile)`` pairs of a loaded map.

    ``metadata`` is a sibling key of the coordinates rather than a nested
    section, so every walk of a map has to step over it; a non-dict value is
    skipped for the same reason a coordinate key is expected to hold one.
    """
    for key, value in map_data.items():
        if key == "metadata" or not isinstance(value, dict):
            continue
        yield key, value


@functools.lru_cache(maxsize=1)
def object_placements() -> Tuple[Placement, ...]:
    """Every authored object placement across every shipped map.

    Memoised: this parses ~20 JSON files, and the callers ask for it once per
    module plus once per ``parametrize`` decorator. A tuple rather than a list
    so a caller cannot mutate the cached result out from under the next one.
    """
    found = []
    for path in map_files():
        raw = json.loads(path.read_text(encoding="utf-8"))
        for coord, tile_data in tiles(raw):
            for payload in tile_data.get("objects", []) or []:
                module_name = payload.get("__module__")
                class_name = payload.get("__class__")
                if not module_name or not class_name:
                    continue
                found.append(
                    Placement(
                        map_name=path.name,
                        coord=coord,
                        module_name=module_name,
                        class_name=class_name,
                        props=payload.get("props") or {},
                    )
                )
    return tuple(found)


def resolve_class(placement: Placement) -> type:
    """The class a placement names.

    Raises rather than returning None — see the module docstring. Maps store
    the bare module name by contract (``"objects"``, not ``"src.objects"``),
    which is why the ``src.`` prefix is added here rather than authored.
    """
    module = importlib.import_module(f"src.{placement.module_name}")
    return getattr(module, placement.class_name)
