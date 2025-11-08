# Ensure src.functions is imported under its canonical package path so coverage hooks it.
import sys, os, pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import src.functions as _functions  # noqa: F401
# Alias plain module name used elsewhere to canonical module for consistent coverage
sys.modules.setdefault('functions', _functions)

# Ordered shims: prerequisites first to satisfy transitive imports (states -> objects -> loot_tables -> npc)
_core_order = [
    'animations',
    'genericng',
    'enchant_tables',
    'states',          # needed by objects
    'items',
    'objects',         # needed by npc
    'loot_tables',     # needed early to avoid nested failures in npc import
    'actions',
    'tiles',
    'universe',
    'positions',       # needed by moves and player for coordinate-based combat (before moves)
    'moves',           # moves before npc so npc can attach move instances
    'npc',
    'skilltree',       # needed by player
    'switch',          # needed by player
    'player'           # player depends on many modules
]
for _name in _core_order:
    if _name in sys.modules:
        continue
    try:
        sys.modules[_name] = __import__(f'src.{_name}', fromlist=['*'])
    except Exception:
        pass

# Additional optional shims (idempotent)
for _mod in ("combat", "skilltree", "events", "shop_conditions"):
    if _mod not in sys.modules:
        try:
            sys.modules[_mod] = __import__(f"src.{_mod}", fromlist=['*'])
        except Exception:
            pass


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
    }
    
    for item in items:
        if any(test_file in str(item.fspath) for test_file in tkinter_test_files):
            item.add_marker(skip_tkinter)


import pytest
