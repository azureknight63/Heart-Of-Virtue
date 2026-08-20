"""Lock in removal of the terminal menu interface layer.

The game is web-only. The terminal menu classes (BaseInterface and its
subclasses InventoryInterface / InventoryCategorySubmenu / RoomTakeInterface /
ShopInterface / ContainerLootInterface) have been removed, along with the Player
verbs that only launched them (Player.take / Player.print_inventory /
Player.attack). Room-item pickup is handled by Item.take() +
GameService.interact_with_target; inventory browsing is handled by the
/inventory routes; shop pricing lives on the Merchant.

`interface` survives only as a thin re-export of the shared inventory/gold
helpers that callers and tests still import from it.
"""

import ast
import functools
import importlib
import pathlib

import pytest

from src.items import Gold, Item
from src.player import Player

SRC_ROOT = pathlib.Path(__file__).resolve().parent.parent / "src"

# The only surviving literal `input()` in the engine lives in
# src/animations.py's `main()`, the developer CLI entry point that is reached
# only via `if __name__ == "__main__"`. Anything else is a blocking prompt that
# would hang an API worker.
ALLOWED_INPUT_SITE = ("animations.py", "main")


def _is_main_guard(node):
    """True for an ``if __name__ == "__main__":`` statement."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _enclosing_function(tree):
    """Map id(node) -> name of the nearest enclosing function def."""
    owner = {}

    def visit(node, current):
        for child in ast.iter_child_nodes(node):
            name = current
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
            owner[id(child)] = name
            visit(child, name)

    visit(tree, None)
    return owner


@functools.lru_cache(maxsize=1)
def _input_call_sites():
    """Every literal ``input(...)`` call in src/, as (relpath, lineno, func)."""
    sites = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        owner = _enclosing_function(tree)
        rel = str(path.relative_to(SRC_ROOT))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "input"
            ):
                sites.append((rel, node.lineno, owner.get(id(node))))
    return tuple(sites)


class TestTerminalMenusRemoved:
    @pytest.mark.parametrize(
        "name",
        [
            "BaseInterface",
            "InventoryInterface",
            "InventoryCategorySubmenu",
            "RoomTakeInterface",
            "ShopInterface",
            "ShopBuyMenu",
            "ShopSellMenu",
            "ContainerLootInterface",
        ],
    )
    def test_interface_has_no_menu_classes(self, name):
        interface = importlib.import_module("src.interface")
        assert not hasattr(interface, name), f"{name} should be deleted"

    def test_inventory_helpers_are_the_real_implementations(self):
        """The shim must re-export inventory_utils, not shadow it with stubs."""
        interface = importlib.import_module("src.interface")
        inventory_utils = importlib.import_module("src.inventory_utils")
        for name in ("get_gold", "transfer_gold", "transfer_item"):
            assert getattr(interface, name) is getattr(inventory_utils, name)

    def test_reexported_transfer_gold_moves_real_gold(self):
        """Behavioural proof the re-export is wired to working code."""
        interface = importlib.import_module("src.interface")
        purse, till = [Gold(50)], [Gold(10)]

        interface.transfer_gold(purse, till, 30)

        assert interface.get_gold(purse) == 20
        assert interface.get_gold(till) == 40

    @pytest.mark.parametrize("verb", ["take", "print_inventory", "attack"])
    def test_player_has_no_terminal_ui_verbs(self, verb):
        # These only launched terminal menus; the web client uses the API paths.
        assert not hasattr(Player, verb)

    def test_item_take_still_exists(self):
        """The real ground-pickup verb (used by the API) must remain."""
        assert callable(Item.take)


class TestEngineIsFreeOfBlockingInput:
    """`src/` must not call input() — a blocking prompt hangs the API worker."""

    def test_no_unexpected_input_calls_in_src(self):
        unexpected = [
            (path, lineno)
            for path, lineno, func in _input_call_sites()
            if (path, func) != ALLOWED_INPUT_SITE
        ]
        assert unexpected == [], (
            "blocking input() calls found in the engine: "
            + ", ".join(f"src/{p}:{ln}" for p, ln in unexpected)
        )

    def test_allowlisted_site_still_exists_and_is_cli_only(self):
        """The one excused call must stay unreachable from game code."""
        allowed = [
            (path, lineno)
            for path, lineno, func in _input_call_sites()
            if (path, func) == ALLOWED_INPUT_SITE
        ]
        assert allowed, (
            f"src/{ALLOWED_INPUT_SITE[0]}::{ALLOWED_INPUT_SITE[1]} no longer calls "
            "input(); drop ALLOWED_INPUT_SITE so the scan becomes absolute."
        )

        # ...and `main()` must still be invoked only from the __main__ guard,
        # otherwise the excuse ("it is CLI-only") stops being true.
        tree = ast.parse(
            (SRC_ROOT / ALLOWED_INPUT_SITE[0]).read_text(encoding="utf-8")
        )
        guards = [n for n in ast.walk(tree) if _is_main_guard(n)]
        assert len(guards) == 1, "expected exactly one __main__ guard"
        guarded = {id(n) for g in guards for n in ast.walk(g)}
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == ALLOWED_INPUT_SITE[1]
        ]
        assert calls, f"{ALLOWED_INPUT_SITE[1]}() is never called"
        assert all(id(c) in guarded for c in calls), (
            f"{ALLOWED_INPUT_SITE[1]}() is now callable outside the __main__ "
            "guard, so its input() is reachable from game code"
        )

    def test_await_input_is_a_no_op(self):
        """The former 'press Enter' pause is retained only as a no-op."""
        from src import functions

        assert functions.await_input() is None
