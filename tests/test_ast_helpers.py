"""Positive controls for the shared structural walkers (:mod:`tests._ast_helpers`).

A structural test asserts that a scan came back EMPTY: "no function spells this
key by hand", "no method outside the pair calls the exp half". An empty result
from a broken scan reads exactly the same, so every one of those tests is only
as good as a proof that the walker can find anything at all.

The concrete failure this file exists to prevent already shipped: the class
walker matched only :class:`ast.FunctionDef`, so all four ``async def`` methods
on :class:`GameService` were invisible to it while two tests built on it claimed
to cover the whole class.
"""

import ast
import textwrap

from src.api.combat_adapter import ApiCombatAdapter
from src.api.services.game_service import GameService
from tests._ast_helpers import (
    called_names,
    calls_of,
    class_functions,
    source_calls,
)

GAME_SERVICE_PATH = "src/api/services/game_service.py"


class TestClassFunctions:
    def test_it_finds_plain_methods(self):
        assert "process_event_input" in class_functions(GameService)

    def test_it_finds_async_methods(self):
        """THE regression control. ``save_game`` and friends are ``async def``.

        With an ``ast.FunctionDef``-only walker these four were silently absent,
        and every "nothing in this class does X" assertion built on it excluded
        the save/load methods — the ones most likely to build payload dicts.
        """
        found = class_functions(GameService)
        missing = {
            name
            for name in ("save_game", "load_game", "list_saves", "delete_save")
            if name not in found
        }
        assert missing == set(), (
            f"{sorted(missing)} are async methods of GameService that the class "
            "walker cannot see; every structural scan built on it silently "
            "skips them"
        )

    def test_the_async_methods_are_actually_async(self):
        """Guards the control itself: if they stop being ``async def``, the
        test above would keep passing while proving nothing."""
        found = class_functions(GameService)
        assert isinstance(found["save_game"], ast.AsyncFunctionDef)


class TestCalledNames:
    def test_it_finds_attribute_and_bare_calls(self):
        def sample(self):
            self.alpha()
            beta()

        assert called_names(sample) == {"alpha", "beta"}

    def test_it_accepts_an_already_parsed_node(self):
        node = ast.parse(textwrap.dedent("def sample():\n    self.alpha()\n"))
        assert called_names(node) == {"alpha"}

    def test_it_ignores_a_name_that_is_only_mentioned(self):
        def sample(self):
            """Mentions self.alpha() in prose only."""
            return "alpha"

        assert called_names(sample) == set()


class TestCallsOf:
    def test_it_returns_the_call_nodes(self):
        def sample(self):
            self.alpha(1)
            self.alpha(2)
            self.beta()

        nodes = calls_of(sample, "alpha")
        assert [n.args[0].value for n in nodes] == [1, 2]


class TestSourceCalls:
    def test_it_finds_a_caller_in_another_module(self):
        assert "get_combat_status" in source_calls(
            GAME_SERVICE_PATH, "settle_victory"
        ), (
            "the whole-file scan cannot see game_service's settle_victory "
            "callers, so any 'no other caller exists' assertion using it is "
            "vacuous"
        )

    def test_it_reports_nothing_for_a_name_no_one_calls(self):
        assert source_calls(GAME_SERVICE_PATH, "_no_such_method_anywhere") == set()

    def test_the_adapter_still_owns_the_method_the_scan_looks_for(self):
        # Keeps the control above honest if settle_victory is ever renamed.
        assert hasattr(ApiCombatAdapter, "settle_victory")
