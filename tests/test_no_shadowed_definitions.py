"""Guard: no test or fixture may be silently shadowed by a later redefinition.

Python keeps only the last definition of a name in a class or module body. When
a test file defines ``test_foo`` twice, the first one is *deleted at import
time* -- pytest never sees it, never runs it, and never reports it. The suite
goes green with strictly less coverage than its author believed, and nothing in
a normal run signals the loss.

This is not hypothetical. ``tests/test_player_core.py`` carried four shadowed
pairs (``test_cycle_states``, ``test_get_equipped_items``,
``test_apply_state_compounding``, ``test_equip_item_from_room``), so four tests
had silently stopped running. In two of those pairs the *discarded* copy was
the stronger one -- the dead ``test_cycle_states`` processed two states where
the surviving one processed a single state, and the dead
``test_get_equipped_items`` pinned the exact list contents where the survivor
only checked membership. The other two pairs turned out to pin genuinely
different behaviours and were renamed so both now run.

Fixtures shadow the same way and fail more quietly still: the survivor is
simply used everywhere, so tests silently receive setup they were not written
against.

Flake8 reports this as F811, but the linter is not part of the test run, so
nothing enforced it.
"""

import ast
import collections
import pathlib

import pytest

TESTS_DIR = pathlib.Path(__file__).parent

_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _python_files():
    """Every .py file under tests/, including the excluded subdirectories.

    tests/api, tests/broken and tests/uat are not collected by the default run
    (see pytest.ini), but a shadowed test in them is still a lost test whenever
    they are run deliberately, so they are scanned too.
    """
    return sorted(p for p in TESTS_DIR.rglob("*.py") if p.name != "__init__.py")


def _is_fixture(node):
    """True when a decorator on ``node`` is pytest.fixture (called or bare)."""
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
    return False


def _duplicates_in(body, predicate):
    """Names defined more than once directly in ``body`` and matching ``predicate``.

    Only direct children are considered: a helper nested inside a function, or a
    method on an inner class, does not shadow anything at this level. Definitions
    guarded by ``if``/``try`` are likewise skipped -- those are deliberate
    conditional definitions, not accidents.
    """
    names = [n.name for n in body if isinstance(n, _FUNC_NODES) and predicate(n)]
    counts = collections.Counter(names)
    return {name: count for name, count in counts.items() if count > 1}


def _scan(path):
    """Yield ``(scope, kind, name, count)`` for each shadowed definition."""
    try:
        tree = ast.parse(path.read_text(encoding="utf8", errors="ignore"))
    except SyntaxError as exc:  # a genuinely broken file is a different failure
        pytest.fail(f"{path.relative_to(TESTS_DIR.parent)} does not parse: {exc}")

    scopes = [("<module>", tree.body)]
    scopes += [(n.name, n.body) for n in tree.body if isinstance(n, ast.ClassDef)]

    for scope, body in scopes:
        for name, count in _duplicates_in(
            body, lambda n: n.name.startswith("test")
        ).items():
            yield scope, "test", name, count
        for name, count in _duplicates_in(body, _is_fixture).items():
            yield scope, "fixture", name, count


def _format(path, findings):
    rel = path.relative_to(TESTS_DIR.parent)
    return "\n".join(
        f"  {rel}::{scope} defines {kind} '{name}' {count}x "
        f"-- only the last survives"
        for scope, kind, name, count in findings
    )


def test_no_test_or_fixture_is_shadowed():
    """Every test and fixture name is unique within its class or module."""
    report = []
    for path in _python_files():
        findings = list(_scan(path))
        if findings:
            report.append(_format(path, findings))

    assert not report, (
        "Shadowed definitions found. Python keeps only the last definition, so "
        "the earlier ones never run:\n" + "\n".join(report) + "\n\n"
        "Fix by deleting the redundant copy (keep whichever proves more), or -- "
        "if the two pin genuinely different behaviours -- renaming so both run."
    )


def test_the_scanner_detects_a_shadowed_test():
    """The guard must actually fire; a scanner that cannot fail is worthless."""
    source = (
        "class TestThing:\n"
        "    def test_a(self):\n"
        "        pass\n"
        "    def test_a(self):\n"
        "        pass\n"
    )
    tree = ast.parse(source)
    cls = tree.body[0]
    assert _duplicates_in(cls.body, lambda n: n.name.startswith("test")) == {
        "test_a": 2
    }


def test_the_scanner_detects_a_shadowed_fixture():
    """Both the bare and the called decorator forms must be recognised."""
    source = (
        "import pytest\n"
        "@pytest.fixture\n"
        "def thing():\n"
        "    pass\n"
        "@pytest.fixture(scope='module')\n"
        "def thing():\n"
        "    pass\n"
    )
    tree = ast.parse(source)
    assert _duplicates_in(tree.body, _is_fixture) == {"thing": 2}


def test_the_scanner_ignores_distinct_names_and_nested_scopes():
    """No false positives on same-named methods in *different* classes."""
    source = (
        "class TestOne:\n"
        "    def test_shared_name(self):\n"
        "        pass\n"
        "class TestTwo:\n"
        "    def test_shared_name(self):\n"
        "        pass\n"
    )
    tree = ast.parse(source)
    for cls in tree.body:
        assert _duplicates_in(cls.body, lambda n: n.name.startswith("test")) == {}
