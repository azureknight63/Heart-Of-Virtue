"""The combat arrival line must never double-space the NPC's name (#565).

Reported: ``Stone Creature Nurenly  lurches toward Jean...``

``alert_message`` is authored under two conventions that both live in
``src/npc/`` today — most messages open with a leading space (``" lurches
toward Jean..."``), a handful do not (``"burbles angrily at Jean!"``) — and the
one site that renders the arrival line adds a space of its own, so the
leading-space majority rendered with two.

Fixed at the join rather than by editing ~22 authored strings: one rule, and it
holds for whichever convention the next enemy is written under.

The parametrised expectation below is derived from the messages actually in the
tree (an AST scan of every ``alert_message`` literal in ``src/npc/``), not from
a list typed into this file, so a newly authored message is covered the day it
lands.
"""

import ast
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ast_helpers import calls_of  # noqa: E402
from _combat_fixtures import make_adapter, make_player, seeded  # noqa: E402
from src.api.combat_adapter import ApiCombatAdapter, combat_alert_line  # noqa: E402
from src.npc import CorruptedStoneCreature  # noqa: E402

NPC_PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "src" / "npc"


def _authored_alert_messages():
    """Every string literal assigned to ``alert_message`` in ``src/npc/``.

    Covers both spellings the package uses: the keyword argument in a
    subclass's ``super().__init__`` call (and in the ``__init__`` signatures'
    defaults), and the plain class-body assignment on ``NPC`` itself.

    Returns ``{message: "file:line"}`` so a failure names the offending
    author site instead of just the string.
    """
    found = {}
    for path in sorted(NPC_PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            literal = None
            if isinstance(node, ast.keyword) and node.arg == "alert_message":
                literal = node.value
            elif isinstance(node, ast.arg) and node.arg == "alert_message":
                continue  # the default sits on the FunctionDef, matched below
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                named = any(
                    (isinstance(t, ast.Name) and t.id == "alert_message")
                    or (isinstance(t, ast.Attribute) and t.attr == "alert_message")
                    for t in targets
                )
                if named:
                    literal = node.value
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                found.setdefault(literal.value, f"{path.name}:{literal.lineno}")
        # Keyword defaults on __init__ signatures (``alert_message=" ..."``)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = [a.arg for a in node.args.args[-len(node.args.defaults):]] \
                if node.args.defaults else []
            for arg_name, default in zip(names, node.args.defaults):
                if arg_name != "alert_message":
                    continue
                if isinstance(default, ast.Constant) and isinstance(
                    default.value, str
                ):
                    found.setdefault(
                        default.value, f"{path.name}:{default.lineno}"
                    )
    return found


AUTHORED = _authored_alert_messages()


def test_the_scan_found_messages_to_check():
    """Guard the guard: an empty population would make every check below pass."""
    assert len(AUTHORED) >= 10, (
        "the AST scan of src/npc/ found almost no alert_message literals, so "
        f"the spacing assertions prove nothing; found: {AUTHORED}"
    )


def test_both_authoring_conventions_are_present():
    """The defect exists only because the two conventions coexist.

    If the tree ever settles on one of them this fails loudly rather than
    quietly becoming a test of a single-shaped population.
    """
    leading_space = [m for m in AUTHORED if m[:1] == " "]
    no_leading_space = [m for m in AUTHORED if m[:1] != " "]
    assert leading_space, f"no leading-space alert_message found in {AUTHORED}"
    assert no_leading_space, f"every alert_message is leading-space in {AUTHORED}"


@pytest.mark.parametrize("message", sorted(AUTHORED), ids=lambda m: repr(m)[:48])
def test_arrival_line_single_spaces_the_name(message):
    """``<name> <alert>`` — exactly one space, whichever way it was authored."""
    line = combat_alert_line("Stone Creature Nurenly", message)
    assert "  " not in line, f"double space in {line!r} (from {AUTHORED[message]})"
    assert line.startswith("Stone Creature Nurenly "), line
    assert line == line.strip(), f"stray outer whitespace in {line!r}"


def test_arrival_line_survives_a_missing_name():
    """A nameless combatant must not leave a leading space on the line."""
    assert combat_alert_line("", " lurches toward Jean...") == (
        "lurches toward Jean..."
    )


def test_the_announcement_site_actually_uses_the_rule():
    """Wiring guard: the arrival line is the ONE place this rule must hold.

    A correct :func:`combat_alert_line` nobody calls fixes nothing, and the
    f-string it replaced satisfies every assertion above while still shipping
    the double space.
    """
    assert calls_of(
        ApiCombatAdapter._initialize_combat_locked, "combat_alert_line"
    ), (
        "initialize_combat builds the enemy arrival line without going "
        "through combat_alert_line"
    )


def test_arrival_line_in_a_real_encounter_is_single_spaced():
    """End to end: a real fight against a real enemy, through the real adapter."""
    with seeded(99):
        player = make_player()
        enemy = CorruptedStoneCreature()
        adapter = make_adapter(player, enemies=[enemy])
        arrival = [
            entry["message"]
            for entry in adapter.player.combat_log
            if entry.get("message", "").startswith(enemy.name)
        ]
        assert arrival, f"no arrival line logged; log: {adapter.player.combat_log}"
        assert not any("  " in line for line in arrival), (
            f"double space in the arrival line: {arrival!r}"
        )
