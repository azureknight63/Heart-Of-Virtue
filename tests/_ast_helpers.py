"""Shared AST walkers for the structural (source-scanning) tests.

Several suites assert structural properties of the engine — "no one spells this
key by hand", "every exit routes through that helper" — by parsing a class or a
function and walking the tree. Each had grown its own copy of the same two
walkers, and the copies were not equivalent: the class walker in
``test_game_service_pending_event_shape.py`` matched only :class:`ast.FunctionDef`
and so was **blind to every ``async def``**. On :class:`GameService` that hid four
methods — ``save_game``, ``load_game``, ``list_saves``, ``delete_save``, i.e.
precisely the ones most likely to build payload dicts — while two tests built on
it claimed exhaustive coverage of the class.

An empty result from a structural scan is indistinguishable from "the scan
found nothing to look at", so every helper here is paired with a positive
control in :mod:`tests.test_ast_helpers`. Add one for any new walker.
"""

import ast
import inspect
import textwrap

#: Both function flavours. Matching only ``FunctionDef`` silently skips every
#: ``async def``, which is the blind spot this module exists to close.
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def class_functions(cls):
    """Every ``def`` and ``async def`` in ``cls``, by name.

    Walks the whole class body, so nested helpers are included under their own
    names. ``ast.walk`` on the parsed class source, not ``vars(cls)``: the point
    is to inspect what the source *says*, decorators and all.
    """
    tree = _tree_of(cls)
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, FUNCTION_NODES)
    }


def call_target(node):
    """The name an :class:`ast.Call` invokes, or None.

    A bare call or any attribute call answers its final name —
    ``f(...)`` is ``f``, and ``self.g(...)`` and ``obj.attr.h(...)`` are
    ``g`` and ``h`` — while a call on a subscript or on another call answers
    None, as does a node that is not a call. Shared by :func:`called_names`
    and :func:`calls_of` here, by the objective-call scan in
    ``test_journal_story_integration.py``, and by the completer and wiring
    scans in ``test_ferry_landing_objective.py``, so those cannot disagree
    about what a call names. Several older guards still spell the rule
    themselves -- ``test_rate_limiter.py``, ``test_multi_target_outcome_contract.py``
    and ``test_end_combat_cleanup.py`` among them -- so treat that list as
    open; point a new guard here instead.
    """
    if not isinstance(node, ast.Call):
        return None
    target = node.func
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return None


def _tree_of(source_object):
    """``source_object`` as a syntax tree: an AST node as given, a class or
    function parsed from its source."""
    if isinstance(source_object, ast.AST):
        return source_object
    return ast.parse(textwrap.dedent(inspect.getsource(source_object)))


def called_names(func):
    """Names of every ``self.<name>(...)`` / bare ``<name>(...)`` call in ``func``.

    An :class:`ast.Call` walk, not a source-substring search: a docstring or
    comment naming a method would satisfy a text match without ever invoking it,
    and the docstrings these tests scan routinely name every method in the area.

    Accepts a function or an already-parsed AST node, so a caller that already
    has a node from :func:`class_functions` need not re-parse.
    """
    return {
        target
        for target in map(call_target, ast.walk(_tree_of(func)))
        if target is not None
    }


def calls_of(func, name):
    """Every :class:`ast.Call` of ``self.<name>`` / bare ``<name>`` inside ``func``.

    :func:`called_names` answers "was it called at all"; this one hands back the
    call nodes so a test can inspect the arguments.
    """
    return [node for node in ast.walk(_tree_of(func)) if call_target(node) == name]


def source_calls(module_path, name):
    """Names of the functions in ``module_path`` that call ``.<name>(...)``.

    A whole-FILE scan, for the structural claims that span modules — "no exit
    outside the adapter reaches for the exp half". Reading a class through
    :func:`class_functions` cannot see those: the callers live in other files.
    """
    with open(module_path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    callers = set()
    for node in ast.walk(tree):
        if not isinstance(node, FUNCTION_NODES):
            continue
        if name in called_names(node):
            callers.add(node.name)
    return callers
