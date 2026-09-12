"""Controls for ``tests/_story_scan.py``.

The chapter roster and the objective-key readers are the populations two
objective guards assert over. Each gets a control here, so a reader that
silently stops matching fails under its own name instead of turning those
guards vacuous.
"""

import ast
import importlib
import pathlib
import re

import pytest

from src import journal
from tests._story_scan import (
    CHAPTER_FILE,
    COMPLETE_OBJECTIVE,
    OBJECTIVE_CALLS,
    OBJECTIVE_PREFIX,
    SET_OBJECTIVE,
    STORY_DIR,
    declared_objectives,
    is_objective_name,
    objective_key_name,
    objective_key_node,
    story_modules,
)


def _call(source):
    node = ast.parse(source).body[0].value
    assert isinstance(node, ast.Call), source
    return node


class TestTheRoster:
    def test_every_chapter_an_objective_belongs_to_is_scanned(self):
        """The journal is the independent authority: each objective key is
        spelled after the chapter that owns it, so every such chapter must be
        on the roster."""
        chapters = set()
        for name in declared_objectives():
            value = getattr(journal, name)
            match = re.match(r"(ch\d+)_", value)
            assert match, f"{name} = {value!r} names no chapter"
            chapters.add(match.group(1))
        scanned = {module.name for module in story_modules()}
        assert chapters, "src.journal declares no objectives"
        assert chapters <= scanned, (chapters, scanned)

    def test_a_story_helper_module_is_not_a_chapter(self):
        assert (STORY_DIR / "effects.py").is_file()
        assert "effects" not in {module.name for module in story_modules()}

    @pytest.mark.parametrize("name", ["ch01.py", "ch03.py", "ch10.py"])
    def test_a_two_digit_chapter_file_is_a_chapter(self, name):
        assert CHAPTER_FILE.match(name)

    @pytest.mark.parametrize(
        "name", ["ch1.py", "ch100.py", "chapter01.py", "ch01.pyc", "effects.py"]
    )
    def test_any_other_file_name_is_not_a_chapter(self, name):
        # One- and three-digit names would sort out of chapter order, which
        # is what the two-digit rule buys the roster; "chapter01.py" is not
        # the ``chNN`` spelling, a compiled "ch01.pyc" is not a source file,
        # and "effects.py" is a story helper.
        assert not CHAPTER_FILE.match(name)

    def test_each_dotted_name_imports_the_file_that_was_parsed(self):
        for module in story_modules():
            imported = importlib.import_module(module.dotted)
            assert pathlib.Path(imported.__file__).resolve() == module.path.resolve()


class TestDeclaredObjectives:
    def test_is_the_journal_roster(self):
        declared = declared_objectives()
        assert declared
        assert all(name.startswith(OBJECTIVE_PREFIX) for name in declared)
        assert journal.OBJ_CH03_FERRY_LANDING in {getattr(journal, n) for n in declared}


class TestObjectiveCalls:
    def test_are_the_journal_functions_names(self):
        assert OBJECTIVE_CALLS == (SET_OBJECTIVE, COMPLETE_OBJECTIVE)
        assert SET_OBJECTIVE == "set_objective"
        assert COMPLETE_OBJECTIVE == "complete_objective"
        assert all(callable(getattr(journal, name)) for name in OBJECTIVE_CALLS)


class TestObjectiveKeys:
    @pytest.mark.parametrize(
        "source",
        [
            "set_objective(player, OBJ_X, 'text')",
            "complete_objective(player, OBJ_X)",
            "complete_objective(player, key=OBJ_X)",
        ],
    )
    def test_reads_the_key_positionally_or_by_keyword(self, source):
        call = _call(source)
        assert isinstance(objective_key_node(call), ast.Name)
        assert objective_key_name(call) == "OBJ_X"

    @pytest.mark.parametrize(
        "source",
        [
            "complete_objective(player, key)",       # a loop variable
            "complete_objective(player, 'ch03_x')",  # a bare string
            "complete_objective(player)",            # no key at all
        ],
    )
    def test_names_only_an_objective_constant(self, source):
        assert objective_key_name(_call(source)) is None

    @pytest.mark.parametrize(
        "source",
        [
            "player.universe.journal.set_objective(OBJ_X, 'text')",
            "self.player.universe.journal.complete_objective(OBJ_X)",
        ],
    )
    def test_journals_own_methods_are_not_read_as_the_helpers(self, source):
        """Their key is the FIRST argument, so reading argument two would
        take an objective's TEXT for its key -- and drop the real key."""
        assert objective_key_node(_call(source)) is None

    @pytest.mark.parametrize(
        "source",
        [
            # `from src import journal`, the spelling src/journal.py's own
            # callers use -- a Name receiver, not an attribute chain.
            "journal.set_objective(player, OBJ_X, 'text')",
            # The fully qualified module: the same `.journal` attribute the
            # method form ends in, but rooted at the package.
            "src.journal.set_objective(player, OBJ_X, 'text')",
        ],
    )
    def test_every_spelling_of_the_module_helper_is_still_read(self, source):
        assert objective_key_name(_call(source)) == "OBJ_X"

    @pytest.mark.parametrize(
        "source, expected",
        [("OBJ_X", True), ("obj_x", False), ("module.OBJ_X", False), ("'OBJ_X'", False)],
    )
    def test_an_objective_name_is_a_bare_obj_identifier(self, source, expected):
        assert is_objective_name(ast.parse(source, mode="eval").body) is expected

    def test_the_key_node_is_none_when_there_is_no_key(self):
        assert objective_key_node(_call("complete_objective(player)")) is None
