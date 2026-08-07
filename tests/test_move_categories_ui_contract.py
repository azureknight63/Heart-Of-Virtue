"""Contract test: backend move categories ↔ frontend combat radial groups.

Every category string a castable move can carry must be collected by exactly one
UI button group (CATEGORY_GROUPS in frontend/src/utils/categories.js), and no UI
group may filter for a category the engine never emits.

This is the guard that was missing when the SPECIAL button filtered for three
categories that do not exist ("Special"/"Spiritual"/"Supernatural") while the
seven castable `Mastery` moves had no button at all — players could buy moves
they could never cast.

Passive moves are excluded: PassiveMove subclasses are never castable, so the
`Passive` category needs no button. NPC-only moves are included, because the
engine's category vocabulary is shared between player and NPC moves and a new
category introduced there would reach the same serializer.

There is no exception list: adding a new engine category without giving it a UI
group fails this test.
"""

import ast
import inspect
import pathlib
import re
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src import moves
from src.moves import Move, PassiveMove

_CATEGORIES_JS = _ROOT / "frontend" / "src" / "utils" / "categories.js"
_MOVES_DIR = _ROOT / "src" / "moves"


def _frontend_category_groups():
    """Parse CATEGORY_GROUPS out of the JS module as {group: [categories]}."""
    source = _CATEGORIES_JS.read_text(encoding="utf-8")
    match = re.search(r"export const CATEGORY_GROUPS = \{(.*?)\n\}", source, re.DOTALL)
    assert match, "CATEGORY_GROUPS block not found in categories.js"
    groups = {}
    for group, body in re.findall(r"^  (\w+): \[(.*?)\],?$", match.group(1), re.MULTILINE):
        groups[group] = re.findall(r"'([^']+)'", body)
    return groups


def _explicit_categories_by_class_name():
    """Map class name → the `category="..."` literal in its own class body.

    Static parse rather than instantiation: many move constructors do arithmetic
    on live player stats and cannot be built from a stub.
    """
    explicit = {}
    for path in sorted(_MOVES_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.keyword)
                    and sub.arg == "category"
                    and isinstance(sub.value, ast.Constant)
                ):
                    explicit[node.name] = sub.value.value
    return explicit


def _castable_move_classes():
    for name in moves.__all__:
        obj = getattr(moves, name)
        if not (inspect.isclass(obj) and issubclass(obj, Move)):
            continue
        if obj in (Move, PassiveMove) or issubclass(obj, PassiveMove):
            continue
        yield name, obj


def _categories_used_by_castable_moves():
    """The set of category strings castable moves actually carry.

    A class with no `category=` of its own inherits the one its nearest ancestor
    passes (e.g. the NpcAttack subclasses), falling back to Move's default.
    """
    explicit = _explicit_categories_by_class_name()
    default = inspect.signature(Move.__init__).parameters["category"].default
    used = {}
    for name, cls in _castable_move_classes():
        for ancestor in cls.__mro__:
            if ancestor.__name__ in explicit:
                used.setdefault(explicit[ancestor.__name__], []).append(name)
                break
        else:
            used.setdefault(default, []).append(name)
    return used


def test_frontend_groups_parsed():
    groups = _frontend_category_groups()
    # Sanity floor: the button keys HeroPanel renders must all be present.
    assert {
        "Offensive",
        "Maneuver",
        "Defensive",
        "Special",
        "Miscellaneous",
    } == set(groups)


def test_engine_categories_parsed():
    used = _categories_used_by_castable_moves()
    # Sanity floor: if this ever comes back empty the parse silently broke.
    assert "Offensive" in used and len(used["Offensive"]) > 10
    assert "Mastery" in used


def test_every_castable_category_has_exactly_one_ui_group():
    groups = _frontend_category_groups()
    used = _categories_used_by_castable_moves()

    owners = {}
    for group, categories in groups.items():
        for category in categories:
            owners.setdefault(category, []).append(group)

    unmapped = {
        category: sorted(move_names)
        for category, move_names in used.items()
        if category not in owners
    }
    assert not unmapped, (
        "castable moves whose category has no combat radial button — they can be "
        f"learned but never cast: {unmapped}. Map the category in CATEGORY_GROUPS "
        "(frontend/src/utils/categories.js)."
    )

    duplicated = {c: g for c, g in owners.items() if len(g) > 1}
    assert not duplicated, f"categories claimed by more than one UI group: {duplicated}"


def test_no_ui_group_filters_for_a_nonexistent_category():
    groups = _frontend_category_groups()
    used = _categories_used_by_castable_moves()

    dead = {
        group: [c for c in categories if c not in used]
        for group, categories in groups.items()
        if any(c not in used for c in categories)
    }
    assert not dead, (
        "UI groups filtering for category strings no engine move emits "
        f"(dead filters — the button will never appear): {dead}"
    )


def test_mastery_moves_are_reachable_under_the_special_button():
    """The seven 2500-XP Mastery moves are the concrete regression this guards."""
    groups = _frontend_category_groups()
    used = _categories_used_by_castable_moves()
    assert groups["Special"] == ["Mastery"]
    assert len(used["Mastery"]) == 7, used.get("Mastery")


def test_tactical_moves_are_reachable_under_the_misc_button():
    """MISC is the catch-all for the low-volume categories."""
    groups = _frontend_category_groups()
    used = _categories_used_by_castable_moves()
    assert "Tactical" in used
    assert "ReapersMark" in used["Tactical"]
    assert "Tactical" in groups["Miscellaneous"]


def test_passive_category_needs_no_ui_group():
    groups = _frontend_category_groups()
    used = _categories_used_by_castable_moves()
    assert "Passive" not in used
    mapped = {c for categories in groups.values() for c in categories}
    assert "Passive" not in mapped
