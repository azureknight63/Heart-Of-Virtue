"""Shared scan infrastructure for the ``src/moves`` structural guards.

Three test modules (``test_preview_damage``, ``test_facing_damage_hand_rolled_
attacks``, ``test_multi_target_outcome_contract``) plus the canonical-damage
and friendly-fire guards each walk the moves package looking for damage paths.
Until this module existed, every one of them re-derived the module glob and
hand-synced its own copy of "how an execute() is recognised as reducing HP" --
and when ``resolve_pipeline_strike`` was extracted, all three signal copies
went stale in the same edit, which is precisely the drift a single source of
truth removes.

Two artefacts live here:

* ``move_module_paths(exclude=...)`` / ``move_module_names(exclude=...)`` --
  the globbed (never hand-maintained) list of ``src/moves`` submodules.
* ``DAMAGE_SIGNALS`` + ``writes_hp(node)`` -- the textual and AST spellings of
  "this code reduces somebody's HP". The two MUST stay in step: every shared
  resolver named in ``DAMAGE_SIGNALS`` that applies HP itself appears in
  ``_HP_APPLYING_CALLS`` too, and ``test_multi_target_outcome_contract``'s
  positive controls fail if the scan goes inert.
"""

import ast
import pathlib

import src.moves as _moves_pkg

#: How a piece of move code is recognised as reducing somebody's HP, as raw
#: source substrings. The package genuinely uses all of these spellings; a
#: signal list that is too narrow fails silently in the safe-looking
#: direction -- it certifies the code it cannot see. Historical misses, each
#: added only after a guard shipped blind: ``hp = max(`` (the four area
#: moves), ``resolve_strike_outcome(`` (the shared per-target resolver), and
#: ``resolve_pipeline_strike(`` (the shared hit/parry/miss dispatch -- the
#: moment it was extracted, every move with a bare hit branch stopped
#: containing ``self.hit(`` and dropped out of all three hand-synced copies
#: of this list at once, which is why there is now one copy).
DAMAGE_SIGNALS = (
    "self.hit(",
    "hp -=",
    "hp = max(",
    ".hp = max(",
    "resolve_strike_outcome(",
    "resolve_pipeline_strike(",
)

#: Call names that apply HP (or dispatch to something that does) themselves.
#: The AST predicate below and the textual DAMAGE_SIGNALS above must agree on
#: these -- a resolver present in one and not the other splits the guards.
_HP_APPLYING_CALLS = frozenset(
    {"hit", "resolve_strike_outcome", "resolve_pipeline_strike"}
)


def move_module_paths(exclude=()):
    """Every ``src/moves`` submodule path, globbed rather than listed.

    Deliberately NOT hand-maintained: an earlier guard enumerated four
    modules and a scrub found twelve unwired moves in the eight it did not
    name. ``exclude`` names stems to leave out (e.g. ``("_base",)`` for scans
    of the weapon modules only, or ``("_npc",)`` where NPC moves are out of
    scope); ``__init__`` is always excluded.
    """
    package_dir = pathlib.Path(_moves_pkg.__file__).parent
    skip = set(exclude) | {"__init__"}
    return tuple(
        path
        for path in sorted(package_dir.glob("*.py"))
        if path.stem not in skip
    )


def move_module_names(exclude=()):
    """The dotted module names for ``move_module_paths(exclude)``."""
    return tuple(
        f"src.moves.{path.stem}" for path in move_module_paths(exclude)
    )


def writes_hp(node):
    """True when the AST ``node`` reduces somebody's ``hp``, directly or via a
    shared resolver.

    The AST twin of ``DAMAGE_SIGNALS``: ``x.hp -= n`` / ``x.hp = ...``
    assignments, plus calls to any of ``_HP_APPLYING_CALLS``.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.AugAssign):
            if isinstance(child.target, ast.Attribute) and child.target.attr == "hp":
                return True
        elif isinstance(child, ast.Assign):
            if any(
                isinstance(t, ast.Attribute) and t.attr == "hp"
                for t in child.targets
            ):
                return True
        elif isinstance(child, ast.Call):
            func = child.func
            named = getattr(func, "id", None) or getattr(func, "attr", None)
            if named in _HP_APPLYING_CALLS:
                return True
    return False
