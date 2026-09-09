"""An NPC's authored damage resistances must be live the moment it is built.

The latent half of #555. ``RockRumbler.__init__`` writes only
``resistance_base["slashing"] = 0.5``, and ``resistance`` is re-synced from
``resistance_base`` solely by ``reset_stats``/``refresh_stat_bonuses`` — which
the combat adapter runs on every enemy at combat start. So play is unaffected,
but a freshly constructed ``RockRumbler`` reports
``resistance["slashing"] == 1.0``: any code path reading ``npc.resistance``
outside a combat enrollment sees the wrong number, and
``functions.combat_resistance``'s fallback to ``resistance_base`` does not save
it — the key is *present* in the live dict, just stale.

Measured before the fix: 9 of the 33 constructible NPC classes were affected,
``WailWraith`` worst of all — authored immune to piercing, slashing and
crushing (0.0) yet reporting 1.0 on all three.

The status half of exactly this trap already has a fix and a docstring warning
about it: ``Combatant._set_status_resistance``. This is the damage-side
counterpart, ``Combatant._set_damage_resistance``, plus a structural guard so
the next enemy cannot reintroduce the split by writing the base dict directly.
"""

import ast
import inspect
import pathlib

import pytest
from src.npc import NPC

import src.npc as npc_package

NPC_SOURCE_DIR = pathlib.Path(inspect.getfile(npc_package)).parent


def _constructible_npc_classes():
    """Every NPC subclass exported from ``src.npc`` that builds with no args.

    ``NPC``, ``Friend`` and ``Merchant`` are abstract-by-signature (they
    require name/description/...) and are skipped; the concrete bestiary is
    what carries authored resistances.
    """
    classes = {}
    for name in dir(npc_package):
        obj = getattr(npc_package, name)
        if not (inspect.isclass(obj) and issubclass(obj, NPC)):
            continue
        try:
            classes[name] = obj()
        except TypeError:
            continue
    return classes


CONSTRUCTED = _constructible_npc_classes()

#: Classes whose ``__init__`` authors at least one non-neutral resistance —
#: the only ones where a stale live dict is observable at all.
AUTHORS_NON_NEUTRAL = sorted(
    name
    for name, npc in CONSTRUCTED.items()
    if any(value != 1.0 for value in npc.resistance_base.values())
)


def test_the_scan_found_a_bestiary_to_check():
    """Guard the guard: an empty population would pass every check below."""
    assert len(CONSTRUCTED) >= 20, sorted(CONSTRUCTED)
    assert len(AUTHORS_NON_NEUTRAL) >= 5, (
        "no NPC authors a non-neutral resistance, so the sync assertion below "
        f"is vacuous; constructed: {sorted(CONSTRUCTED)}"
    )


@pytest.mark.parametrize("name", AUTHORS_NON_NEUTRAL)
def test_authored_resistances_are_live_on_a_fresh_npc(name):
    """No combat enrollment required: ``resistance`` matches ``resistance_base``."""
    npc = CONSTRUCTED[name]
    stale = {
        key: (npc.resistance.get(key), base)
        for key, base in npc.resistance_base.items()
        if npc.resistance.get(key) != base
    }
    assert not stale, (
        f"{name} reports resistances that differ from what it authored "
        f"(live, authored): {stale}"
    )


def _direct_base_writes():
    """``self.resistance_base[...] = ...`` sites in ``src/npc/``, by file:line.

    Subscript assignment onto the *damage* base dict only — the attribute name
    is compared exactly, so ``status_resistance_base`` (which has its own
    helper and its own call sites) is not swept up.
    """
    found = []
    for path in sorted(NPC_SOURCE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Subscript):
                    continue
                base = target.value
                if (
                    isinstance(base, ast.Attribute)
                    and base.attr == "resistance_base"
                ):
                    found.append(f"{path.name}:{target.lineno}")
    return found


def _helper_call_sites():
    """``_set_damage_resistance(...)`` call sites in ``src/npc/``, by file:line."""
    found = []
    for path in sorted(NPC_SOURCE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_set_damage_resistance"
            ):
                found.append(f"{path.name}:{node.lineno}")
    return found


def test_the_bestiary_goes_through_the_helper_not_the_base_dict():
    """Structural guard: the split cannot be reintroduced one enemy at a time.

    Both halves are asserted. Zero direct writes alone would also be satisfied
    by a bestiary that authored no resistances at all, so the helper's own call
    sites are counted too — that is the population the assertion is about.
    """
    helper_calls = _helper_call_sites()
    assert len(helper_calls) >= 20, (
        "almost nothing calls Combatant._set_damage_resistance, so the "
        f"no-direct-writes assertion proves little; found: {helper_calls}"
    )
    direct = _direct_base_writes()
    assert not direct, (
        "these sites write resistance_base directly, leaving the live "
        "`resistance` dict stale until the next refresh_stat_bonuses; use "
        f"self._set_damage_resistance(key, value): {direct}"
    )


def test_the_helper_writes_both_dicts():
    """The unit contract, on a real ``Combatant`` subclass."""
    npc = CONSTRUCTED["Slime"]
    npc._set_damage_resistance("fire", 0.25)
    assert npc.resistance_base["fire"] == 0.25
    assert npc.resistance["fire"] == 0.25
