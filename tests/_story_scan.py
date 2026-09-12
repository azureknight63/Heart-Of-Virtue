"""The story-chapter roster, its syntax trees, and the objective-call idioms.

``TestObjectiveKeyRegistry`` (``test_journal_story_integration.py``) and the
reachability guard in ``test_ferry_landing_objective.py`` both scan the
chapter modules for objective calls, and each had its own hand-kept
``("ch01", "ch02", "ch03")`` tuple -- so a ``ch04.py`` added to one would have
left the other guard silently under-scanning. The roster is the population
those guards assert over, so it is read off the filesystem here and nowhere
else (see ``tests/_map_scan.py`` for why one derivation matters). The two
guards also read the same things off ``src.journal`` and off each objective
call -- which ``OBJ_*`` names the journal declares, which argument of a
``set_objective`` / ``complete_objective`` call is the key, and when that key
names an objective constant -- so those live here too.

No assertions live here. ``test_story_scan_helpers.py`` holds the controls
for this module, and each caller proves its own population non-empty.
"""

import ast
import functools
import pathlib
import re
from typing import NamedTuple, Optional, Set, Tuple

from src import journal
from tests._source_scan import SRC_ROOT

STORY_DIR = SRC_ROOT / "story"

#: A chapter module is ``chNN.py`` -- exactly two digits, so file-name order
#: is chapter order. ``effects.py`` and the other story helpers live in the
#: same package but are not chapters.
CHAPTER_FILE = re.compile(r"^ch\d{2}\.py$")

#: What makes a ``src.journal`` constant an objective key.
OBJECTIVE_PREFIX = "OBJ_"

#: The two journal calls that take an objective key, named off the functions
#: themselves so a rename in ``src.journal`` cannot leave the scans matching
#: a call that no longer exists.
SET_OBJECTIVE = journal.set_objective.__name__
COMPLETE_OBJECTIVE = journal.complete_objective.__name__
OBJECTIVE_CALLS = (SET_OBJECTIVE, COMPLETE_OBJECTIVE)

#: The attribute a live ``Journal`` is reached through (``player.universe.
#: journal``), which is also the module's own name, and the package that
#: module sits in -- both read off the code rather than typed, and used only
#: to tell the two spellings apart below.
JOURNAL_ATTR = journal.__name__.rpartition(".")[2]
SRC_PACKAGE = SRC_ROOT.name


class StoryModule(NamedTuple):
    """One chapter module, parsed."""

    #: The file stem -- ``"ch03"`` -- which is also the chapter prefix the
    #: journal's objective keys are spelled with.
    name: str
    dotted: str
    path: pathlib.Path
    tree: ast.Module


@functools.lru_cache(maxsize=1)
def story_modules() -> Tuple[StoryModule, ...]:
    """Every ``src/story/chNN.py``, parsed, in chapter order."""
    found = []
    for path in sorted(STORY_DIR.glob("*.py")):
        if not CHAPTER_FILE.match(path.name):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found.append(StoryModule(path.stem, f"src.story.{path.stem}", path, tree))
    return tuple(found)


def declared_objectives() -> Set[str]:
    """Every ``OBJ_*`` name ``src.journal`` declares -- the objective roster."""
    return {name for name in vars(journal) if name.startswith(OBJECTIVE_PREFIX)}


def _chain_root(node: ast.AST) -> Optional[str]:
    """The leftmost name of an attribute chain -- ``a.b.c`` is ``"a"``."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_journal_method(call: ast.Call) -> bool:
    """True when ``call`` is ``Journal``'s own method rather than the
    module-level helper of the same name.

    ``Journal.set_objective(self, key, text)`` puts the key FIRST, while the
    module-level ``set_objective(player, key, text)`` puts it second, and
    ``call_target`` strips receivers -- so the two are indistinguishable to a
    scan that matches on the name alone. The method is reached through an
    ATTRIBUTE chain ending in ``.journal``
    (``player.universe.journal.set_objective(...)``). The module is reached
    either bare (``from src import journal`` then ``journal.set_objective(
    player, ...)``, a Name, not an attribute chain) or as
    ``src.journal.set_objective(...)``, which ends in the same attribute but
    is rooted at the package -- so the root is checked too.

    The one shape this cannot tell apart is a local variable named ``journal``
    holding a live ``Journal``; it reads as the module. No chapter binds one,
    and the chapters are all this scans.
    """
    if not isinstance(call.func, ast.Attribute):
        return False
    receiver = call.func.value
    if not isinstance(receiver, ast.Attribute) or receiver.attr != JOURNAL_ATTR:
        return False
    return _chain_root(receiver) != SRC_PACKAGE


def objective_key_node(call: ast.Call) -> Optional[ast.expr]:
    """The AST node in the key position of an objective call, or None.

    ``set_objective(player, key, ...)`` / ``complete_objective(player, key)``
    take the key positionally; ``key=`` as a keyword is accepted too and would
    otherwise be invisible to every guard built on this.

    None for ``Journal``'s same-named methods, whose key sits in a different
    argument (see ``_is_journal_method``). The chapters use the module-level
    helpers throughout; a chapter that switched would be reported as not
    handling its objective, which is loud, rather than silently matched
    against the objective's text.
    """
    if _is_journal_method(call):
        return None
    if len(call.args) >= 2:
        return call.args[1]
    return next((k.value for k in call.keywords if k.arg == "key"), None)


def is_objective_name(node: Optional[ast.AST]) -> bool:
    """True when ``node`` is a bare name spelled like an ``OBJ_*`` constant --
    the one spelling of "which names count", so the guards cannot disagree.
    False for None, which ``objective_key_node`` answers for a keyless call."""
    return isinstance(node, ast.Name) and node.id.startswith(OBJECTIVE_PREFIX)


def objective_key_name(call: ast.Call) -> Optional[str]:
    """The ``OBJ_*`` constant an objective call names as its key, or None.

    None for anything else in the key position -- a loop variable, a bare
    string -- which the registry guard checks by other means.
    """
    node = objective_key_node(call)
    return node.id if is_objective_name(node) else None
