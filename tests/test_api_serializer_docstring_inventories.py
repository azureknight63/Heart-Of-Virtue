"""Prose inventories in ``src/api/serializers/`` docstrings, pinned by reflection.

The defect this closes is a class, not an instance.
``CombatantSerializer._serialize_damage_multiplier``'s docstring lists, by
name, which moves in ``src/moves/_npc.py`` declare ``_DAMAGE_MULTIPLIER`` and
how. Both of its lists silently went stale the moment ``NpcAttack`` joined the
convention: the docstring named nine classes where ten declare, and the same
docstring went on to describe ``NpcAttack.evaluate``'s ``uniform(0.8, 1.2)``
roll two paragraphs later -- so it contradicted itself in one screen and
nothing said so.

Note which inventories in this repository stopped rotting and which did not.
``TestDeclaredDamageMultiplier`` in ``tests/test_npc_moves_coverage.py``
discovers its declaring classes by reflection and fails in both directions, so
its list was right. ``_STYLE_INJECTORS`` in ``tests/test_security_headers.py``
is derived from a scan of ``frontend/src``, so its list was right. The two
lists that were wrong were the two nobody derived. This file derives them.

Deliberately an AST walk rather than an import: the question is what the class
*body* declares, and an import cannot distinguish a declaration from an
inherited value without ``__dict__`` gymnastics -- which is the exact hole
``NpcAttack`` fell through in the first place.
"""

import ast
import pathlib
import re

import pytest

from src.api.serializers.combat import CombatantSerializer

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_NPC_MOVES = _REPO_ROOT / "src" / "moves" / "_npc.py"

_DECL = "_DAMAGE_MULTIPLIER"
_ROLL_BOUNDS = ("_POWER_ROLL_MIN", "_POWER_ROLL_MAX")


def _class_body_assigns(node, name):
    """Every assignment of ``name`` directly in ``node``'s class body."""
    for stmt in node.body:
        targets = getattr(stmt, "targets", None) or (
            [stmt.target] if isinstance(stmt, ast.AnnAssign) else []
        )
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                yield stmt


def _mentions(node, names):
    return any(
        isinstance(sub, ast.Name) and sub.id in names for sub in ast.walk(node)
    )


@pytest.fixture(scope="module")
def declarations():
    """``{class name: (base names, "fixed" | "derived")}`` from the AST."""
    tree = ast.parse(_NPC_MOVES.read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in _class_body_assigns(node, _DECL):
            bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
            kind = "derived" if _mentions(stmt.value, _ROLL_BOUNDS) else "fixed"
            found[node.name] = (bases, kind)
    return found


def _docstring_list(after):
    """The CamelCase names in the parenthesised group following ``after``.

    The docstring is wrapped, so the text is flattened before matching.
    """
    doc = " ".join(
        CombatantSerializer._serialize_damage_multiplier.__doc__.split()
    )
    index = doc.index(after)
    group = doc[index + len(after):]
    group = group[: group.index(")")]
    return set(re.findall(r"[A-Z][A-Za-z]+", group))


def test_the_docstring_names_every_class_that_declares_one(declarations):
    """The 'plain ``Move`` subclasses' list, against the AST.

    This one exists to stop an audit that only looks at the
    ``TelegraphedSurge`` family, so a name missing from it is a heavy move
    nobody was told to check.
    """
    plain = {
        name for name, (bases, _) in declarations.items() if "Move" in bases
    }
    assert _docstring_list("subclasses (") == plain


def test_the_fixed_factor_list_matches_the_ast(declarations):
    fixed = {name for name, (_, kind) in declarations.items() if kind == "fixed"}
    assert _docstring_list("states it outright (") == fixed


def test_the_derived_midpoint_list_matches_the_ast(declarations):
    derived = {
        name for name, (_, kind) in declarations.items() if kind == "derived"
    }
    assert _docstring_list("the wire value with it (") == derived


def test_the_ast_walk_still_finds_the_declarations(declarations):
    """Non-vacuity for the three tests above, and nothing more.

    Each of those compares a docstring list against a set built by
    :func:`declarations`. If the AST walk ever stopped finding anything --
    ``_npc.py`` moved, ``_DAMAGE_MULTIPLIER`` renamed, the walk broken -- every
    one of those comparisons would become ``set() == set()`` for a docstring
    edited to match, and three green tests would be pinning nothing. This
    asserts the walk has something to say.

    It deliberately does not re-assert the partition. ``declarations`` assigns
    exactly one ``kind`` per class, so ``fixed | derived == set(declarations)``
    holds by construction, and the two per-kind tests already compare both
    halves in both directions -- deleting a name from a docstring list fails
    them directly (verified by injection). An assertion that cannot fail on its
    own is not a guard, whatever its name says.
    """
    assert len(declarations) >= 10, "declarations vanished; check the AST walk"
