"""Contract: the heat tooltip must agree with the engine's heat rules.

`frontend/src/utils/heat.js` shows the player a table of what raises and
lowers combat heat -- "Land a hit x1.25", "Parry an attack x1.40" and so
on. Those numbers are a hand-copied mirror of the `change_heat()` call sites in
`src/moves/_base.py`, written in a different language, and nothing linked them.

The JS-side test asserts those literals against the same JS literals, which is
a mock agreeing with itself: it cannot fail when the engine moves. So a balance
retune of any `change_heat` multiplier would leave a tooltip that actively
teaches the player the wrong rule, with a fully green suite. That is the wire-
drift failure mode CLAUDE.md names as this codebase's dominant bug class, in
its most literal form -- the client displaying a number the engine no longer
produces.

This test is the missing link. It reads the multipliers out of the Python
source with `ast`, reads the table out of the JS source with a regex, and
asserts the two multisets are equal.

It deliberately compares MULTISETS of the numeric multipliers rather than
matching label to value. Mapping "Parry an attack" to a specific call site
would mean re-encoding the engine's control flow here, which is the very
duplication being guarded against; the multiset catches the case that matters
(a multiplier changed, or one was added or removed) without inventing a second
source of truth for which branch is which.
"""

import ast
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE_SOURCE = REPO_ROOT / "src" / "moves" / "_base.py"
TOOLTIP_SOURCE = REPO_ROOT / "frontend" / "src" / "utils" / "heat.js"

#: A tooltip row whose effect is a formula rather than a constant -- taking a
#: hit scales heat by `1 - damage/maxhp`, rendered as "x(1 - dmg / max HP)".
#: Detected by the parenthesis, matching the convention the JS-side test uses.
#: NOT detected by "does it contain a digit": that formula contains a literal
#: 1, so a naive digit-scrape reads it as a x1.00 multiplier and silently adds
#: a ninth entry that the engine never produces.
_FORMULA_MARKER = "("

#: Everything that is not part of a decimal number, for scraping "x1.25 more".
_NON_NUMERIC = re.compile(r"[^\d.]")


def _engine_heat_multipliers():
    """Every literal multiplier passed to `change_heat()` in the engine.

    Uses `ast` rather than a regex so a reformatted or line-wrapped call site
    is still found -- one of the nine spans multiple lines today.
    """
    tree = ast.parse(ENGINE_SOURCE.read_text())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "attr", None) != "change_heat":
            continue
        if not node.args:
            continue  # keyword-only form (`add=`), no multiplier
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
            found.append(round(float(arg.value), 4))
        # A computed argument (the `1 - damage/maxhp` case) has no literal to
        # compare; it is represented in the tooltip by the formula row.
    return sorted(found)


def _tooltip_multipliers():
    """The numeric multipliers the player-facing rules table advertises."""
    source = TOOLTIP_SOURCE.read_text()
    found = []
    for table in ("HEAT_GAINS", "HEAT_LOSSES"):
        match = re.search(rf"{table}\s*=\s*\[(.*?)\n\]", source, re.S)
        assert match, f"could not locate {table} in {TOOLTIP_SOURCE.name}"
        for effect in re.findall(r"effect:\s*'([^']*)'", match.group(1)):
            if _FORMULA_MARKER in effect:
                continue  # a formula row; the engine side has no literal either
            number = _NON_NUMERIC.sub("", effect)
            if number:
                found.append(round(float(number), 4))
    return sorted(found)


def test_the_engine_is_the_only_place_heat_multipliers_live():
    """A `change_heat` call outside `_base.py` would escape this contract.

    The tooltip's comment points at `_base.py` as the authority. If a call site
    appears elsewhere the comparison below silently stops being complete, so
    fail loudly and make whoever added it extend this test.
    """
    strays = []
    for path in (REPO_ROOT / "src").rglob("*.py"):
        if path == ENGINE_SOURCE:
            continue
        text = path.read_text(errors="ignore")
        if "change_heat(" in text and "def change_heat" not in text:
            strays.append(str(path.relative_to(REPO_ROOT)))
    assert not strays, (
        "change_heat() is called outside src/moves/_base.py:\n  "
        + "\n  ".join(strays)
        + "\nThe heat tooltip's rules table only mirrors _base.py, so these "
        "multipliers are not covered by the contract below. Extend "
        "_engine_heat_multipliers() to include them."
    )


def test_tooltip_multipliers_match_the_engine():
    """The numbers shown to the player must be the numbers the engine applies."""
    engine = _engine_heat_multipliers()
    tooltip = _tooltip_multipliers()
    assert engine, "found no change_heat literals -- the AST scan is broken"
    assert tooltip, "found no tooltip multipliers -- the JS regex is broken"
    assert tooltip == engine, (
        "the heat tooltip and the engine disagree about heat.\n"
        f"  engine  (src/moves/_base.py):            {engine}\n"
        f"  tooltip (frontend/src/utils/heat.js):     {tooltip}\n"
        "Whichever moved, the other has to follow -- a mismatch means the "
        "in-game tooltip is teaching the player a rule the engine does not use."
    )


@pytest.mark.parametrize("scan", [_engine_heat_multipliers, _tooltip_multipliers])
def test_the_scans_are_not_silently_empty(scan):
    """A guard that matches nothing passes forever.

    Both scans are text-driven and would degrade to an empty list if the source
    were reformatted past their patterns; an empty list compares equal to an
    empty list, so the contract above would go quietly vacuous.
    """
    values = scan()
    assert len(values) >= 8, f"{scan.__name__} found only {len(values)}: {values}"
    assert all(0.1 < v < 10 for v in values), f"implausible multipliers: {values}"
