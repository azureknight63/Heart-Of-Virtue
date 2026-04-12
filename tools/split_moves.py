#!/usr/bin/env python3
"""
One-shot migration script: splits src/moves.py into the src/moves/ package.

Run from the repo root:
    python tools/split_moves.py

What it does:
  1. Reads src/moves.py
  2. Splits it into submodule files inside src/moves/
  3. Converts PassiveMove subclasses (replaces boilerplate with PassiveMove base)
  4. Writes src/moves/__init__.py
  5. Does NOT delete src/moves.py — that's a manual step after verification

After running, verify with:
    python -c "import sys; sys.path.insert(0,'src'); import moves; print(moves.Attack, moves.PassiveMove)"
    cd src && python -m pytest -q ../tests/
"""

import os
import re

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
MOVES_PY = os.path.join(SRC, "moves.py")
PKG_DIR = os.path.join(SRC, "moves")

# ---------------------------------------------------------------------------
# Class → submodule assignments
# ---------------------------------------------------------------------------
CLASS_MODULE = {
    # _base
    "Move": "_base",
    # _utility
    "StrategicInsight": "_utility",
    "MasterTactician": "_utility",
    "Check": "_utility",
    "Wait": "_utility",
    "Attack": "_utility",
    "Rest": "_utility",
    "UseItem": "_utility",
    # _movement
    "Dodge": "_movement",
    "Parry": "_movement",
    "Advance": "_movement",
    "Withdraw": "_movement",
    "BullCharge": "_movement",
    "TacticalRetreat": "_movement",
    "FlankingManeuver": "_movement",
    "QuietMovement": "_movement",
    "TacticalPositioning": "_movement",
    "Turn": "_movement",
    "QuickSwap": "_movement",
    # _unarmed
    "PowerStrike": "_unarmed",
    "Jab": "_unarmed",
    "IronFist": "_unarmed",
    "CleaveInstinct": "_unarmed",
    "HeavyHanded": "_unarmed",
    # _dagger
    "Slash": "_dagger",
    "Backstab": "_dagger",
    "FeintAndPivot": "_dagger",
    "ShadowStep": "_dagger",
    # _sword
    "PommelStrike": "_sword",
    "Thrust": "_sword",
    "DisarmingSlash": "_sword",
    "Riposte": "_sword",
    "WhirlAttack": "_sword",
    "VertigoSpin": "_sword",
    "BladeMastery": "_sword",
    "CounterGuard": "_sword",
    # _scythe
    "Reap": "_scythe",
    "ReapersMark": "_scythe",
    "DeathsHarvest": "_scythe",
    "GrimPersistence": "_scythe",
    "HauntingPresence": "_scythe",
    # _spear
    "KeepAway": "_spear",
    "Lunge": "_spear",
    "Impale": "_spear",
    "SentinelsVigil": "_spear",
    "ArmorPierce": "_spear",
    # _pick
    "ChipAway": "_pick",
    "ExploitWeakness": "_pick",
    "Stupefy": "_pick",
    "WorkTheGap": "_pick",
    # _ranged
    "ShootBow": "_ranged",
    "ShootCrossbow": "_ranged",
    "BroadheadBolt": "_ranged",
    "AimedShot": "_ranged",
    "PinningBolt": "_ranged",
    "QuickReload": "_ranged",
    "EagleEye": "_ranged",
    "MarksmanEye": "_ranged",
    # _polearm
    "OverheadSmash": "_polearm",
    "Sweep": "_polearm",
    "BracePosition": "_polearm",
    "HalberdSpin": "_polearm",
    "ReachMastery": "_polearm",
    # _npc
    "NpcAttack": "_npc",
    "NpcRest": "_npc",
    "NpcIdle": "_npc",
    "TelegraphedSurge": "_npc",
    "SlimeVolley": "_npc",
    "TidalSurge": "_npc",
    "GorranClub": "_npc",
    "VenomClaw": "_npc",
    "SpiderBite": "_npc",
    "BatBite": "_npc",
}

# Passives that should be converted to PassiveMove base class.
# These all share: stage_beat=[0,0,0,0], targeted=False, passive=True,
# stage_announce=["","","",""], fatigue_cost=0, beats_left=0, target=user, xp_gain=0,
# and override viable() to return False.
PASSIVE_CLASSES = {
    "ShadowStep", "EagleEye", "IronFist", "CleaveInstinct", "HeavyHanded",
    "BladeMastery", "CounterGuard", "GrimPersistence", "HauntingPresence",
    "SentinelsVigil", "MarksmanEye", "ReachMastery",
}

# Standard imports header for all submodules
STANDARD_IMPORTS = """\
from neotermcolor import colored, cprint  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401
"""

MODULE_DOCSTRINGS = {
    "_base": '"""Move base class, PassiveMove base, and shared combat helpers."""\n\n',
    "_utility": '"""Universal utility moves: Check, Wait, Rest, UseItem, Attack, StrategicInsight, MasterTactician."""\n\n',
    "_movement": '"""Positioning and movement moves: Dodge, Parry, Advance, Withdraw, BullCharge, TacticalRetreat, FlankingManeuver, QuietMovement, TacticalPositioning, Turn, QuickSwap."""\n\n',
    "_unarmed": '"""Unarmed/fist moves: PowerStrike, Jab and passives IronFist, CleaveInstinct, HeavyHanded."""\n\n',
    "_dagger": '"""Dagger weapon moves: Slash, Backstab, FeintAndPivot and passive ShadowStep."""\n\n',
    "_sword": '"""Sword weapon moves: PommelStrike, Thrust, DisarmingSlash, Riposte, WhirlAttack, VertigoSpin and passives BladeMastery, CounterGuard."""\n\n',
    "_scythe": '"""Scythe weapon moves: Reap, ReapersMark, DeathsHarvest and passives GrimPersistence, HauntingPresence."""\n\n',
    "_spear": '"""Spear weapon moves: KeepAway, Lunge, Impale, ArmorPierce and passive SentinelsVigil."""\n\n',
    "_pick": '"""Pick weapon moves: ChipAway, ExploitWeakness, Stupefy, WorkTheGap."""\n\n',
    "_ranged": '"""Ranged weapon moves: ShootBow, ShootCrossbow and crossbow skills; passives EagleEye, MarksmanEye."""\n\n',
    "_polearm": '"""Polearm/halberd moves: OverheadSmash, Sweep, BracePosition, HalberdSpin and passive ReachMastery."""\n\n',
    "_npc": '"""NPC moves: NpcAttack, NpcRest, NpcIdle and enemy special abilities."""\n\n',
}

PASSIVE_MOVE_CLASS = '''\

class PassiveMove(Move):
    """Base for flag passives — never castable; queried by other moves for effect checks.

    Subclasses only need to supply name and description. All timing values are zero,
    targeted=False, passive=True, and viable() always returns False.
    """

    def __init__(self, user, name, description, category="Passive"):
        super().__init__(
            name=name,
            description=description,
            xp_gain=0,
            current_stage=0,
            stage_beat=[0, 0, 0, 0],
            targeted=False,
            stage_announce=["", "", "", ""],
            fatigue_cost=0,
            beats_left=0,
            target=user,
            user=user,
            category=category,
            passive=True,
        )

    def viable(self):
        return False
'''


def read_moves_py():
    with open(MOVES_PY, "r", encoding="utf-8") as f:
        return f.read()


def find_class_boundaries(source):
    """Return list of (class_name, start_line, end_line) tuples (1-based, inclusive)."""
    lines = source.splitlines(keepends=True)
    class_pattern = re.compile(r"^class (\w+)\s*[\(:]")
    boundaries = []

    for i, line in enumerate(lines):
        m = class_pattern.match(line)
        if m:
            boundaries.append((m.group(1), i))  # 0-based line index

    # Calculate end: each class ends just before the next one (or at EOF)
    result = []
    for idx, (name, start) in enumerate(boundaries):
        if idx + 1 < len(boundaries):
            end = boundaries[idx + 1][1] - 1
        else:
            end = len(lines) - 1
        result.append((name, start, end))

    return result, lines


def extract_preamble(lines, first_class_line):
    """Extract everything before the first class definition."""
    return "".join(lines[:first_class_line])


def build_passive_replacement(class_name, original_lines):
    """
    Generate a compact PassiveMove subclass from a passive Move subclass.
    We need to extract just the description string.
    """
    source = "".join(original_lines)

    # Extract docstring if any (class-level docstring)
    docstring_match = re.search(
        r'class\s+\w+[^:]*:\s*"""(.*?)"""', source, re.DOTALL
    )

    # Extract description from __init__
    desc_match = re.search(
        r'description\s*=\s*(\([\s\S]*?\)(?=\s*super)|\("[^"]*"\)(?=\s*super)|"[^"]*"(?=\s*\n\s*super)|\'[^\']*\'(?=\s*\n\s*super))',
        source,
    )

    # Try harder to get description - look for the description assignment
    desc_text = None
    lines_list = original_lines
    for i, line in enumerate(lines_list):
        stripped = line.strip()
        if stripped.startswith("description = "):
            # Collect the full description (may span multiple lines with parentheses)
            desc_content = stripped[len("description = "):]
            # If it starts with a paren, collect until matching close paren
            if desc_content.startswith("("):
                paren_depth = 0
                collected = []
                for j in range(i, len(lines_list)):
                    chunk = lines_list[j].strip() if j > i else desc_content
                    collected.append(chunk)
                    paren_depth += chunk.count("(") - chunk.count(")")
                    if paren_depth <= 0:
                        break
                desc_text = " ".join(collected)
            else:
                desc_text = desc_content
            break

    if desc_text is None:
        # fallback: use class name
        desc_text = f'"{class_name}"'

    # Get the docstring if present
    doc = ""
    if docstring_match:
        doc = f'    """{docstring_match.group(1).strip()}"""\n\n'

    result = f'\nclass {class_name}(PassiveMove):\n'
    if doc:
        result += doc
    result += f'    def __init__(self, user):\n'
    result += f'        super().__init__(user, "{_class_name_to_display(class_name)}", {desc_text})\n'
    return result


_DISPLAY_NAME_OVERRIDES = {
    "SentinelsVigil": "Sentinel's Vigil",
    "MarksmanEye": "Marksman's Eye",
}


def _class_name_to_display(name):
    """Convert CamelCase to 'Title Case' for display names."""
    if name in _DISPLAY_NAME_OVERRIDES:
        return _DISPLAY_NAME_OVERRIDES[name]
    # Insert space before uppercase letters
    result = re.sub(r"([A-Z])", r" \1", name).strip()
    return result


def build_submodule_files(source):
    """
    Parse moves.py and distribute classes into submodule buckets.
    Returns dict: module_name -> list of (class_name, lines)
    Also returns preamble (imports etc before first class).
    """
    boundaries, lines = find_class_boundaries(source)

    if not boundaries:
        raise ValueError("No class definitions found in moves.py")

    first_class_line = boundaries[0][1]
    preamble = extract_preamble(lines, first_class_line)

    # Buckets for each submodule
    modules = {mod: [] for mod in set(CLASS_MODULE.values())}
    modules["_base"] = []  # ensure _base is always present

    unassigned = []

    for class_name, start, end in boundaries:
        class_lines = lines[start : end + 1]
        target_mod = CLASS_MODULE.get(class_name)
        if target_mod is None:
            unassigned.append(class_name)
            print(f"  WARNING: {class_name} not assigned to any module — skipping")
            continue
        modules[target_mod].append((class_name, class_lines))

    return preamble, modules, unassigned


def extract_module_level_code(preamble):
    """Extract non-import, non-docstring module-level code from the preamble.

    Strategy: find the last import/from line, then return everything after it
    that is not blank-only. This reliably captures helper functions and
    module constants like _ensure_weapon_exp and default_animations.
    """
    lines = preamble.splitlines(keepends=True)

    # First pass: find the line index of the last import/from statement
    last_import_line = -1
    in_docstring = False
    quote_char = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Track multi-line docstrings/strings so we don't mis-detect
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                quote_char = stripped[:3]
                # Check if it closes on the same line
                if stripped.count(quote_char) >= 2 and len(stripped) > 3:
                    pass  # single-line docstring — already closed
                else:
                    in_docstring = True
            elif stripped.startswith("import ") or stripped.startswith("from "):
                last_import_line = i
        else:
            if quote_char and quote_char in stripped:
                in_docstring = False
                quote_char = None

    if last_import_line == -1:
        return ""  # no imports found

    # Return everything after the last import line, skipping leading blank lines
    after = lines[last_import_line + 1:]
    # Drop leading blank / comment lines
    start = 0
    while start < len(after) and after[start].strip() in ("", "#"):
        start += 1
    return "".join(after[start:])


def write_submodule(pkg_dir, mod_name, preamble_imports, class_entries):
    """Write a single submodule file."""
    path = os.path.join(pkg_dir, f"{mod_name}.py")

    parts = []

    # Module docstring
    parts.append(MODULE_DOCSTRINGS.get(mod_name, f'"""{mod_name}"""\n\n'))

    # Standard imports
    parts.append(STANDARD_IMPORTS)

    # For _base: include module-level helpers (_ensure_weapon_exp, default_animations)
    if mod_name == "_base":
        module_level = extract_module_level_code(preamble_imports)
        if module_level:
            parts.append("\n")
            parts.append(module_level)
    else:
        # For non-base modules, import from _base
        parts.append("from ._base import Move, PassiveMove, _ensure_weapon_exp, default_animations  # noqa: F401\n")
        # NPC submodule also needs NpcAttack internally (TelegraphedSurge inherits it)
        # — but since they're all in the same file that's fine; no extra import needed.

    parts.append("\n")

    # Add classes
    for class_name, class_lines in class_entries:
        if class_name == "Move":
            # Move base class — write as-is, then append PassiveMove
            parts.append("".join(class_lines))
            parts.append(PASSIVE_MOVE_CLASS)
        elif class_name in PASSIVE_CLASSES:
            # Convert to PassiveMove subclass
            parts.append(build_passive_replacement(class_name, class_lines))
        else:
            parts.append("".join(class_lines))

    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(parts))

    print(f"  Wrote {path}  ({len(class_entries)} classes)")


INIT_TEMPLATE = '''\
"""
moves — combat move package for Heart of Virtue.

This package replaces the monolithic src/moves.py with organised submodules:

    _base.py        Move, PassiveMove — base classes + shared combat helpers
    _utility.py     universal moves (Check, Wait, Rest, UseItem, Attack, StrategicInsight, ...)
    _movement.py    positioning moves (Dodge, Parry, Advance, Withdraw, ...)
    _unarmed.py     fist/unarmed moves
    _dagger.py      dagger weapon moves
    _sword.py       sword weapon moves
    _scythe.py      scythe weapon moves
    _spear.py       spear weapon moves
    _pick.py        pick weapon moves
    _ranged.py      bow and crossbow moves
    _polearm.py     polearm/halberd moves
    _npc.py         NPC-only moves and enemy special abilities

All public names are re-exported here so existing imports of the form
    import moves          →  moves.Attack(user)
    from src.moves import Attack
continue to work without any changes in calling code.
"""

from ._base import Move, PassiveMove, _ensure_weapon_exp, default_animations
from ._utility import StrategicInsight, MasterTactician, Check, Wait, Rest, UseItem, Attack
from ._movement import (
    Dodge, Parry, Advance, Withdraw, BullCharge, TacticalRetreat,
    FlankingManeuver, QuietMovement, TacticalPositioning, Turn, QuickSwap,
)
from ._unarmed import PowerStrike, Jab, IronFist, CleaveInstinct, HeavyHanded
from ._dagger import Slash, Backstab, FeintAndPivot, ShadowStep
from ._sword import (
    PommelStrike, Thrust, DisarmingSlash, Riposte, WhirlAttack,
    VertigoSpin, BladeMastery, CounterGuard,
)
from ._scythe import Reap, ReapersMark, DeathsHarvest, GrimPersistence, HauntingPresence
from ._spear import KeepAway, Lunge, Impale, SentinelsVigil, ArmorPierce
from ._pick import ChipAway, ExploitWeakness, Stupefy, WorkTheGap
from ._ranged import (
    ShootBow, ShootCrossbow, BroadheadBolt, AimedShot,
    PinningBolt, QuickReload, EagleEye, MarksmanEye,
)
from ._polearm import OverheadSmash, Sweep, BracePosition, HalberdSpin, ReachMastery
from ._npc import (
    NpcAttack, NpcRest, NpcIdle, TelegraphedSurge, SlimeVolley,
    TidalSurge, GorranClub, VenomClaw, SpiderBite, BatBite,
)

__all__ = [
    # Base classes
    "Move",
    "PassiveMove",
    "_ensure_weapon_exp",
    "default_animations",
    # Utility
    "StrategicInsight",
    "MasterTactician",
    "Check",
    "Wait",
    "Rest",
    "UseItem",
    "Attack",
    # Movement
    "Dodge",
    "Parry",
    "Advance",
    "Withdraw",
    "BullCharge",
    "TacticalRetreat",
    "FlankingManeuver",
    "QuietMovement",
    "TacticalPositioning",
    "Turn",
    "QuickSwap",
    # Unarmed
    "PowerStrike",
    "Jab",
    "IronFist",
    "CleaveInstinct",
    "HeavyHanded",
    # Dagger
    "Slash",
    "Backstab",
    "FeintAndPivot",
    "ShadowStep",
    # Sword
    "PommelStrike",
    "Thrust",
    "DisarmingSlash",
    "Riposte",
    "WhirlAttack",
    "VertigoSpin",
    "BladeMastery",
    "CounterGuard",
    # Scythe
    "Reap",
    "ReapersMark",
    "DeathsHarvest",
    "GrimPersistence",
    "HauntingPresence",
    # Spear
    "KeepAway",
    "Lunge",
    "Impale",
    "SentinelsVigil",
    "ArmorPierce",
    # Pick
    "ChipAway",
    "ExploitWeakness",
    "Stupefy",
    "WorkTheGap",
    # Ranged
    "ShootBow",
    "ShootCrossbow",
    "BroadheadBolt",
    "AimedShot",
    "PinningBolt",
    "QuickReload",
    "EagleEye",
    "MarksmanEye",
    # Polearm
    "OverheadSmash",
    "Sweep",
    "BracePosition",
    "HalberdSpin",
    "ReachMastery",
    # NPC
    "NpcAttack",
    "NpcRest",
    "NpcIdle",
    "TelegraphedSurge",
    "SlimeVolley",
    "TidalSurge",
    "GorranClub",
    "VenomClaw",
    "SpiderBite",
    "BatBite",
]
'''


def main():
    print("Reading moves.py...")
    source = read_moves_py()

    print("Parsing class boundaries...")
    preamble, modules, unassigned = build_submodule_files(source)

    if unassigned:
        print(f"\nWARNING: {len(unassigned)} unassigned classes: {unassigned}")

    print(f"\nCreating package directory: {PKG_DIR}")
    os.makedirs(PKG_DIR, exist_ok=True)

    # Write __init__.py
    init_path = os.path.join(PKG_DIR, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write(INIT_TEMPLATE)
    print(f"  Wrote {init_path}")

    # Write each submodule
    module_order = [
        "_base", "_utility", "_movement", "_unarmed", "_dagger",
        "_sword", "_scythe", "_spear", "_pick", "_ranged", "_polearm", "_npc",
    ]

    for mod in module_order:
        entries = modules.get(mod, [])
        write_submodule(PKG_DIR, mod, preamble, entries)  # preamble used by _base only

    # Summary
    total_classes = sum(len(entries) for entries in modules.values())
    passives_converted = sum(
        1 for entries in modules.values()
        for (name, _) in entries
        if name in PASSIVE_CLASSES
    )
    print(f"\nDone!")
    print(f"  Total classes distributed: {total_classes}")
    print(f"  Passive classes converted to PassiveMove: {passives_converted}")
    print(f"  Package written to: {PKG_DIR}")
    print(f"\nNext steps:")
    print(f"  1. Verify: cd src && python -c \"import moves; print(moves.Attack, moves.PassiveMove)\"")
    print(f"  2. Run tests: python -m pytest -q")
    print(f"  3. If all good, delete src/moves.py")


if __name__ == "__main__":
    main()
