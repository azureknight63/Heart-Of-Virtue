"""A split pile is a new object, so it gets a new wire handle (#621 scrub).

Three places build a new item by copying another's ``__dict__`` -- a partial
``Item.take``, a split ``transfer_item`` and ``MapTile.spawn_item(template=)``
(each unit of a stack drop). All three copied ``_combat_handle`` too, so the
copy and its source answered to one handle. #621's whole design is that a
handle names exactly one object: the victory offer resolves drops by handle,
and the floor freeze finds the fight's tile by them.
"""

import ast
from pathlib import Path

import pytest

from src.combatant import wire_handle
from src.inventory_utils import transfer_item
from src.items import Restorative
from src.objects import Container
from tests._gs_fixtures import live_world


@pytest.fixture
def world():
    player, game_map = live_world()
    return player, game_map[(0, 0)]


def _handle_count(items, handle):
    return sum(1 for i in items if wire_handle(i) == handle)


def test_a_partial_take_leaves_the_floor_pile_its_own_handle(world):
    player, tile = world
    pile = tile.spawn_item("Restorative", amt=3)
    handle = wire_handle(pile)

    pile.take(player, quantity=1)

    (taken,) = [i for i in player.inventory if isinstance(i, Restorative)]
    assert taken is not pile
    assert wire_handle(taken) != handle
    assert wire_handle(pile) == handle, "the source keeps its identity"


def test_a_split_transfer_gets_its_own_handle(world):
    player, tile = world
    crate = Container(name="Crate", description="A crate.", player=player, tile=tile)
    stack = Restorative(count=3)
    crate.inventory = [stack]
    handle = wire_handle(stack)

    transfer_item(crate, player, stack, 1)

    moved = [i for i in player.inventory if isinstance(i, Restorative)]
    assert moved and all(wire_handle(i) != handle for i in moved)


def test_a_stack_drop_puts_down_units_with_their_own_handles(world):
    player, tile = world
    carried = Restorative(count=3)
    player.inventory.append(carried)
    handle = wire_handle(carried)

    carried.drop(player, quantity=2)

    assert _handle_count(tile.items_here, handle) == 0
    assert _handle_count(player.inventory, handle) == 1


# ---------------------------------------------------------------------------
# The clone paths, derived rather than listed (#633)
# ---------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parent.parent / "src"


def _state_source(node):
    """The expression whose instance state ``node`` reads wholesale, or None:
    ``x.__dict__``, ``getattr(x, "__dict__", ...)`` or ``vars(x)``."""
    if isinstance(node, ast.Attribute) and node.attr == "__dict__":
        return node.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "vars" and node.args:
            return node.args[0]
        if (
            node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "__dict__"
        ):
            return node.args[0]
    return None


def _clones_in(tree):
    """Nodes that copy one object's whole state onto ANOTHER object.

    A loop over a state's ``.items()`` that ``setattr``s onto a different
    object, a ``.__dict__.update(...)``, or an assignment to ``.__dict__``.
    Re-setting an object's own members (``_safe.py`` re-wraps a class's own
    ``serialize*`` methods) is not a clone and is not matched.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            it = node.iter
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "list" and it.args:
                it = it.args[0]
            if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr == "items"):
                continue
            source = _state_source(it.func.value)
            if source is None:
                continue
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "setattr"
                    and call.args
                    and ast.dump(call.args[0]) != ast.dump(source)
                ):
                    yield node
                    break
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "update"
            and _state_source(node.func.value) is not None
        ):
            yield node
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Attribute) and t.attr == "__dict__" for t in node.targets
        ):
            yield node


def _enclosing_function(tree, target):
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(n is target for n in ast.walk(fn)):
                return fn.name
    return "<module>"


def test_every_wholesale_state_copy_in_src_goes_through_copy_item_state():
    """#633 asked for the clone paths to be DERIVED, not hand-listed: the three
    tests above cover the three that existed, and a fourth written the old way
    (copying ``__dict__`` straight across) would carry the handle with it and
    pass all of them. So every wholesale state copy in ``src/`` is found here,
    and the only one allowed is ``functions.copy_item_state``, which skips it."""
    sites = set()
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _clones_in(tree):
            rel = path.relative_to(_SRC.parent).as_posix()
            sites.add(f"{rel}::{_enclosing_function(tree, node)}")

    # Non-empty first: a scan that matches nothing approves of everything.
    assert "src/functions.py::copy_item_state" in sites, (
        f"the scan no longer finds copy_item_state itself -- it has gone quiet: {sorted(sites)}"
    )
    # ``Item.__setstate__`` (#643) is pickle's own BUILD restoring an object
    # from ITS OWN saved state, not a split: a loaded item must keep its
    # handle, and the override writes exactly what the default BUILD wrote
    # before it (plus the baked-name strip). It is not a clone path.
    allowed = {"src/functions.py::copy_item_state", "src/items.py::__setstate__"}
    assert sites <= allowed, (
        "copies an object's whole state without functions.copy_item_state, so the "
        f"copy inherits the source's wire handle (#633): {sorted(sites - allowed)}"
    )
