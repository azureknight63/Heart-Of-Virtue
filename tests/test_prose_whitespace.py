"""Guard against stray-space artifacts in shipped prose (#660).

Two artifact shapes are covered, each over a population derived from the
real data rather than a hand-kept list:

1. ``discovery_message`` with a leading/trailing space. Every consumer
   (``GameService.search``) interpolates it after a space --
   ``f"{player.name} found {discovery_msg}"`` -- so an edge space renders as
   "Jean found  a tent!". Population: every ``discovery_message`` string in
   every shipped map JSON, plus the effective default of every ``Object``
   subclass in ``src.objects``.

2. Hard-wrap residue in tile descriptions: a space before an embedded
   newline (``"compact, \\nwell-worn"``) or indentation after one
   (``"use,\\n        and a steady drip"`` -- leftover triple-quote
   indentation). Population: the top-level ``description`` of every tile in
   every shipped map.

Deliberately out of scope: ``idle_message``/``alert_message``, whose leading
space is load-bearing (they are appended directly to an NPC name, e.g.
``"Gorran" + " tends the fire."``), and bare ``\\n`` line breaks without
adjacent spaces, which are legitimate authored breaks.
"""

import ast
import inspect
import re
from pathlib import Path
from unittest.mock import MagicMock

import src.objects as objects_module
from tests._map_scan import map_data, tiles

# A space before a newline, or horizontal whitespace after one.
_WRAP_RESIDUE = re.compile(r"[ \t]+\n|\n[ \t]+")


def _load_maps():
    """``{file name: decoded map}`` over the shared, parse-once scan."""
    return {path.name: data for path, data in map_data()}


def _walk_key(node, key, found, where):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, str):
                found.append((where, v))
            else:
                _walk_key(v, key, found, where)
    elif isinstance(node, list):
        for v in node:
            _walk_key(v, key, found, where)


def _map_discovery_messages():
    found = []
    for name, data in _load_maps().items():
        _walk_key(data, "discovery_message", found, name)
    return found


def _object_default_discovery_messages():
    """Effective ``discovery_message`` of each Object subclass built with stub args."""
    found = []
    for cls_name, cls in inspect.getmembers(objects_module, inspect.isclass):
        if cls.__module__ != "src.objects" or not issubclass(cls, objects_module.Object):
            continue
        kwargs = {}
        params = list(inspect.signature(cls.__init__).parameters.values())[1:]
        for p in params:
            if p.default is inspect.Parameter.empty and p.kind in (
                p.POSITIONAL_OR_KEYWORD,
                p.KEYWORD_ONLY,
            ):
                kwargs[p.name] = "x" if p.name in ("name", "description") else MagicMock()
        try:
            instance = cls(**kwargs)
        except (TypeError, ValueError):
            continue  # needs real params (e.g. TileDescription); not a default carrier
        msg = getattr(instance, "discovery_message", None)
        if isinstance(msg, str):
            found.append((cls_name, msg))
    return found


def _tile_descriptions():
    found = []
    for name, data in _load_maps().items():
        for coord, tile in tiles(data):
            if isinstance(tile.get("description"), str):
                found.append((f"{name} {coord}", tile["description"]))
    return found


class TestDiscoveryMessageEdges:
    def test_populations_are_non_empty(self):
        map_msgs = _map_discovery_messages()
        defaults = _object_default_discovery_messages()
        assert len(map_msgs) >= 10
        # The known offenders' classes must actually be in the population.
        names = {n for n, _ in defaults}
        assert {"Container", "Crate", "Shelf", "Shrine", "HealingSpring", "Passageway"} <= names

    def test_map_discovery_messages_have_no_edge_spaces(self):
        offenders = [(w, m) for w, m in _map_discovery_messages() if m != m.strip()]
        assert offenders == []

    def test_object_default_discovery_messages_have_no_edge_spaces(self):
        offenders = [(w, m) for w, m in _object_default_discovery_messages() if m != m.strip()]
        assert offenders == []


class TestTileDescriptionWrapResidue:
    def test_population_is_non_empty(self):
        assert len(_tile_descriptions()) >= 100

    def test_no_space_adjacent_to_embedded_newline(self):
        offenders = [w for w, d in _tile_descriptions() if _WRAP_RESIDUE.search(d)]
        assert offenders == []

    def test_jambos_tent_entrance_is_one_continuous_paragraph(self):
        data = _load_maps()["grondia-jambos_shop.json"]
        desc = data["(2, 2)"]["description"]
        assert "\n" not in desc
        assert "compact, well-worn vestibule" in desc


#: Issue #694 item 3: ``Restorative.use`` built its narration from adjacent
#: string literals with an embedded "\n" mid-sentence -- 80-column terminal
#: wrap residue that survived the terminal teardown and rendered in the
#: combat/interaction log as a fragment with its own timestamp. The map-JSON
#: population above cannot see this: item narration lives in Python source,
#: not map data. This population is scanned from the AST rather than
#: hand-listed, per the same "population derived from the code" rule the two
#: classes above already follow.
_ITEMS_PY = Path(__file__).resolve().parent.parent / "src" / "items.py"


def _literal_text(node):
    """Best-effort reconstruction of a string-literal AST node's authored
    text, with any interpolated part (an f-string ``{expr}``, or the source
    ``str`` a chained ``.format(...)`` call is invoked on) replaced by a
    placeholder. Residue detection only cares about the literal text an
    author actually typed -- adjacent-literal concatenation (implicit or via
    ``+``) is where the wrap residue in #694 lived, and that survives here
    same as it does at runtime, whether or not the string also happens to be
    an f-string or feed a ``.format()`` call.

    Returns ``None`` for anything that isn't a string-literal expression.
    """
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return _literal_text(node.func.value)
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("X")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _literal_text(node.left), _literal_text(node.right)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _item_narration_strings():
    """``(location label, literal text)`` for every ``narrate()``/``cprint()``
    call's first argument in ``src/items.py``, scanned via AST rather than by
    instantiating every item class: ``use()``/``on_equip()``/etc. narration
    runs on a live ``Player`` with random rolls and inventory mutation, which
    a population scan has no business triggering -- the AST already has the
    authored literal text without calling anything.
    """
    tree = ast.parse(_ITEMS_PY.read_text(encoding="utf-8"), filename=str(_ITEMS_PY))
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id not in ("narrate", "cprint") or not node.args:
            continue
        text = _literal_text(node.args[0])
        if text is not None:
            found.append((f"src/items.py:{node.lineno}", text))
    return found


class TestItemNarrationWrapResidue:
    def test_population_is_non_empty(self):
        assert len(_item_narration_strings()) >= 20

    def test_no_space_adjacent_to_embedded_newline(self):
        offenders = [w for w, t in _item_narration_strings() if _WRAP_RESIDUE.search(t)]
        assert offenders == []
