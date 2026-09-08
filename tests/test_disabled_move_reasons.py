"""A disabled move must say what is actually blocking it (#565).

Reported: ``Shoot Crossbow`` greyed out with ``"Cannot use this move"`` while
every other unavailability reason was useful ("Enemy out of range (too far)",
"Available in 5 beats", "Not enough fatigue", "No valid target in range").

What the catch-all branch genuinely cannot distinguish: ``viable()`` returns a
bare bool, so the adapter only knows *that* the move said no. It guesses at the
reason from range, and range is the one thing that was fine —
``ShootCrossbow.viable`` refuses for three different reasons (no weapon, wrong
weapon, nothing in the 6–40 band) and Jean was holding a sword with an enemy
well inside that band, so the range guess passed and the branch shrugged.

The information is derivable, but only if the engine says it: the weapon gate
lives inside each ``viable()`` body. ``Move.weapon_requirement`` declares it,
and this module's AST scan keeps the declaration honest by deriving the same
set out of the ``viable()`` source.
"""

import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import src.items as items  # noqa: E402
import src.moves as moves  # noqa: E402
from _combat_fixtures import make_adapter, make_player, seeded  # noqa: E402
from _moves_scan import move_module_paths  # noqa: E402
from src.moves._base import Move  # noqa: E402
from src.npc import RockRumbler  # noqa: E402

CATCH_ALL = "Cannot use this move"

#: Attribute names an expression must mention for its ``.subtype`` read to be
#: about the WIELDED WEAPON. Without this, ``ShootBow``'s inventory scan
#: (``item.subtype == "Arrow"``) reads as a weapon requirement and the move
#: would advertise "Requires an arrow" as its weapon.
_WEAPON_EXPR_NAMES = {"eq_weapon", "weapon", "wpn", "current_weapon"}


def _string_constants(node):
    return {
        n.value
        for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


def _mentions_weapon(node):
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id in _WEAPON_EXPR_NAMES:
            return True
        if isinstance(n, ast.Attribute) and n.attr in _WEAPON_EXPR_NAMES:
            return True
    return False


def _reads_weapon_subtype(node):
    """True when ``node`` reads ``.subtype`` off something weapon-shaped.

    Both spellings the package uses: the plain attribute
    (``self.user.eq_weapon.subtype``) and the defensive
    ``getattr(weapon, "subtype", None)``.
    """
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Attribute)
            and n.attr == "subtype"
            and _mentions_weapon(n.value)
        ):
            return True
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "getattr"
            and len(n.args) >= 2
            and isinstance(n.args[1], ast.Constant)
            and n.args[1].value == "subtype"
            and _mentions_weapon(n.args[0])
        ):
            return True
    return False


def _gate_from_source(func_node):
    """The weapon subtypes ``viable()``'s source actually gates on.

    Two gate spellings, both real in the package: an inline comparison against
    ``.subtype`` (optionally through a local list, as ``Slash`` does), and the
    ``subtypes`` argument handed to ``Move.standard_viability_attack``.
    """
    sequences = {}
    for node in ast.walk(func_node):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, (ast.List, ast.Tuple, ast.Set))
        ):
            sequences[node.targets[0].id] = _string_constants(node.value)

    found = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Compare):
            operands = [node.left] + list(node.comparators)
            if not any(_reads_weapon_subtype(o) for o in operands):
                continue
            for operand in operands:
                if _reads_weapon_subtype(operand):
                    continue
                if isinstance(operand, ast.Constant) and isinstance(
                    operand.value, str
                ):
                    found.add(operand.value)
                elif isinstance(operand, (ast.List, ast.Tuple, ast.Set)):
                    found |= _string_constants(operand)
                elif isinstance(operand, ast.Name) and operand.id in sequences:
                    found |= sequences[operand.id]
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "standard_viability_attack"
        ):
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                found |= _string_constants(arg)
    return found


def _weapon_gated_moves():
    """``{class_name: frozenset(subtypes)}`` for every weapon-gated move class."""
    gated = {}
    for path in move_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for member in node.body:
                if not isinstance(member, ast.FunctionDef):
                    continue
                if member.name != "viable":
                    continue
                gate = _gate_from_source(member)
                if gate:
                    gated[node.name] = frozenset(gate)
    return gated


GATED = _weapon_gated_moves()


# ── the declaration must match what viable() actually enforces ──────────────

def test_the_scan_found_weapon_gated_moves():
    """Guard the guard: an inert scan would pass the agreement test below."""
    assert len(GATED) >= 20, (
        "the viable() scan of src/moves/ found almost no weapon gates, so the "
        f"agreement assertion proves nothing; found: {sorted(GATED)}"
    )
    # A single-subtype gate and a multi-subtype one are different code shapes
    # (`!= "Pick"` vs `in allowed_subtypes`); both must be in the population.
    assert any(len(v) == 1 for v in GATED.values()), sorted(GATED.items())
    assert any(len(v) > 1 for v in GATED.values()), sorted(GATED.items())


@pytest.mark.parametrize("class_name", sorted(GATED))
def test_declared_weapon_requirement_matches_the_viability_gate(class_name):
    """``weapon_requirement`` is what the UI explains; ``viable()`` is the rule.

    They are two spellings of one fact, so they are checked against each other
    rather than against a list in this file — a retuned gate that forgets the
    declaration would otherwise ship a confidently wrong "Requires a …".
    """
    cls = getattr(moves, class_name)
    declared = frozenset(getattr(cls, "weapon_requirement", ()) or ())
    assert declared == GATED[class_name], (
        f"{class_name}.viable() gates on {sorted(GATED[class_name])} but "
        f"declares weapon_requirement={sorted(declared)}"
    )


def test_an_ungated_move_declares_nothing():
    """The base default, and the moves that legitimately take any weapon."""
    assert Move.weapon_requirement == ()
    assert getattr(moves.Attack, "weapon_requirement", ()) == ()
    assert getattr(moves.Advance, "weapon_requirement", ()) == ()


# ── the reason the player actually reads ────────────────────────────────────

@pytest.fixture
def sword_vs_rumbler():
    """The reported scenario: a crossbow move listed while Jean holds a sword.

    A real adapter over real combatants, with the enemy pinned inside the
    crossbow's 6–40 ft band so the adapter's range guess passes and the
    catch-all branch is the one under test.
    """
    with seeded(3):
        player = make_player(weapon="Sword")
        player.fatigue = player.maxfatigue
        enemy = RockRumbler()
        adapter = make_adapter(player, enemies=[enemy])
        player.combat_proximity = {enemy: 12}
        player.known_moves = [moves.ShootCrossbow(player)]
        return adapter, player


def _reason_for(adapter, display_name):
    payload = next(
        entry
        for entry in adapter._get_available_moves()
        if entry["display_name"] == display_name
    )
    assert payload["available"] is False, payload
    return payload["reason"]


def test_the_wrong_weapon_is_named_not_shrugged_at(sword_vs_rumbler):
    adapter, _player = sword_vs_rumbler
    reason = _reason_for(adapter, "Shoot Crossbow")
    assert reason != CATCH_ALL, reason
    assert "crossbow" in reason.lower(), reason


def test_an_empty_hand_still_reads_as_no_weapon(sword_vs_rumbler):
    """The existing wording for the bare-handed case is kept, not replaced."""
    adapter, player = sword_vs_rumbler
    player.eq_weapon = None
    assert _reason_for(adapter, "Shoot Crossbow") == "No weapon equipped"


def test_the_right_weapon_out_of_range_still_reports_range(sword_vs_rumbler):
    """The weapon check must not swallow the range reasons the player relies on.

    With the crossbow actually equipped the move's remaining objection is
    distance, and that is what has to be reported.
    """
    adapter, player = sword_vs_rumbler
    player.eq_weapon = items.Crossbow()
    enemy = next(iter(player.combat_proximity))
    player.combat_proximity = {enemy: 2}
    assert _reason_for(adapter, "Shoot Crossbow") == "No valid target in range"


def test_bare_hands_satisfies_a_bare_hands_requirement():
    """Both engine spellings of unarmed count, so Jab never blames the hands.

    ``Jab._is_unarmed`` treats an absent ``eq_weapon`` and an
    ``items.Fists()`` alike; reading only the subtype would have told a
    genuinely bare-handed Jean that Jab "requires bare hands".
    """
    from src.api.combat_adapter import weapon_requirement_reason

    player = make_player()
    jab = moves.Jab(player)
    assert weapon_requirement_reason(jab, None) is None
    assert weapon_requirement_reason(jab, items.Fists()) is None
    assert weapon_requirement_reason(jab, items.Longsword()) == (
        "Requires bare hands"
    )


def test_a_multi_subtype_requirement_lists_the_alternatives():
    """One article, at the front, then the bare nouns — and no engine casing."""
    from src.api.combat_adapter import weapon_requirement_reason

    player = make_player()
    slash = moves.Slash(player)
    assert tuple(sorted(slash.weapon_requirement)) == (
        "Axe",
        "Dagger",
        "Halberd",
        "Stars",
        "Sword",
    )
    reason = weapon_requirement_reason(slash, items.Spear())
    assert reason == (
        "Requires an axe, dagger, halberd, throwing stars or sword"
    ), reason


def test_a_bare_hands_requirement_reads_as_bare_hands():
    """``Jab`` is fists-only, so "Requires a unarmed" would be nonsense."""
    with seeded(5):
        player = make_player(weapon="Sword")
        player.fatigue = player.maxfatigue
        enemy = RockRumbler()
        adapter = make_adapter(player, enemies=[enemy])
        player.combat_proximity = {enemy: 2}
        player.known_moves = [moves.Jab(player)]
        reason = _reason_for(adapter, "Jab")
        assert reason == "Requires bare hands", reason
