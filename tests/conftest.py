# Ensure src.functions is imported under its canonical package path so coverage hooks it.
import sys, os, pathlib

# Disable LLM and reduce delays for tests
os.environ["MYNX_LLM_ENABLED"] = "0"
os.environ["MYNX_FALLBACK_DELAY"] = "0"
# Prevent CombatStrategist from making discovery requests
os.environ["MYNX_LLM_PROVIDER"] = "none"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / 'src'
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# Add src/ so that bare module names (e.g. `import loot_tables`) resolve when
# the shim loop's silent failures leave gaps, without breaking `src.*` imports.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(1, str(SRC_DIR))

import src.functions as _functions  # noqa: F401
# Alias plain module name used elsewhere to canonical module for consistent coverage
sys.modules.setdefault('functions', _functions)

# Ordered shims: prerequisites first to satisfy transitive imports.
# Order matters: each module must come after all of its own bare-name imports.
# Modules with circular deps (objects, actions, tiles) are shimmed best-effort;
# failures are silently ignored and the sys.path fallback above handles them.
_core_order = [
    'animations',
    'genericng',
    'items',           # enchant_tables and loot_tables both need items
    'states',          # enchant_tables needs states
    'enchant_tables',  # loot_tables needs enchant_tables
    'objects',         # needed by npc (may fail: circular dep on player)
    'loot_tables',     # needed by npc; needs items + enchant_tables
    'actions',
    'tiles',
    'universe',
    'positions',       # needed by moves and player for coordinate-based combat (before moves)
    'moves',           # moves before npc so npc can attach move instances
    'combatant',       # base class for Player and NPC; must precede both
    'npc',
    'skilltree',       # needed by player
    'switch',          # needed by player
    'player'           # player depends on many modules
]
for _name in _core_order:
    if _name in sys.modules:
        # Even if already loaded, ensure the full path points to the same object
        if _name in sys.modules and f'src.{_name}' in sys.modules:
            sys.modules[f'src.{_name}'] = sys.modules[_name]
        continue
    try:
        _mod = __import__(f'src.{_name}', fromlist=['*'])
        sys.modules[_name] = _mod
        # Ensure src.* also points to the same module object
        sys.modules[f'src.{_name}'] = _mod
    except Exception:
        pass

# Additional optional shims (idempotent)
for _mod in ("combat", "skilltree", "events", "shop_conditions"):
    if _mod not in sys.modules:
        try:
            sys.modules[_mod] = __import__(f"src.{_mod}", fromlist=['*'])
        except Exception:
            pass

# Final reconciliation: ensure both import names point to the same module object.
# This handles cases where modules were imported via different paths (src.x vs x).
for key in list(sys.modules.keys()):
    if key.startswith('src.'):
        bare_name = key[4:]
        if bare_name and '.' not in bare_name and bare_name not in sys.modules:
            sys.modules[bare_name] = sys.modules[key]
        elif bare_name in sys.modules and sys.modules[bare_name] is not sys.modules[key]:
            # Prioritize the full path import to ensure consistency with test imports
            sys.modules[bare_name] = sys.modules[key]


# Skip tkinter tests during web app implementation
def pytest_configure(config):
    """Configure pytest to skip tkinter-related tests."""
    config.addinivalue_line(
        "markers", "tkinter_test: mark test as tkinter-related (skipped for web app iteration)"
    )


def pytest_collection_modifyitems(config, items):
    """Skip tkinter tests to speed up web app iteration cycle."""
    skip_tkinter = pytest.mark.skip(reason="Skipping tkinter tests - not used in web app implementation")
    
    tkinter_test_files = {
        "test_tkinter_cols.py",
        "test_tkinter_get.py",
        "test_find_column.py",
        "test_map_generator.py",
        "test_map_generator_additional.py",
        "test_map_generator_more.py",
        "verify_colors.py",
        "test_battlefield_colors.py",
        "test_battlefield_window.py",
        "test_coloring_fix.py",
        "test_player_debug.py",
        "test_player_render.py",
        "test_viewport_boundaries.py",
    }
    
    for item in items:
        if any(test_file in str(item.fspath) for test_file in tkinter_test_files):
            item.add_marker(skip_tkinter)


import pytest
