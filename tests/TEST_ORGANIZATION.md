# Test Directory Organization

The test suite has been organized into logical categories using **naming conventions** and **pytest markers**. All tests remain in the `tests/` root directory for compatibility and import path consistency, but are clearly grouped by purpose.

## Organization Strategy

Rather than creating subdirectories (which can cause import path issues), we use:
1. **Naming prefixes** to group related tests
2. **Pytest markers** for running tests by category
3. **Documentation** to explain the categorization
4. **Comments in test files** to indicate their category

This approach provides all the benefits of hierarchical organization without the import complexity.

## Category Mapping

### Combat Tests (7 files) - Prefix: `test_*combat*`, `test_*move*`, `test_*advance*`, `test_*bat*`
Tests for turn-based combat mechanics:
- `test_advance_integration.py` - Combat advancement integration
- `test_advance_viable.py` - Move viability checks
- `test_batbite.py` - Bat attack mechanics
- `test_cave_bat.py` - Cave bat enemy
- `test_move_system_validation.py` - Move system validation
- `test_moves_attack.py` - Attack mechanics
- `test_uat_combat_coordinate_system.py` - Full coordinate system UAT

**Run combat tests:**
```bash
pytest tests/ -k "combat or move or advance or bat"
pytest tests/test_moves_attack.py tests/test_advance_viable.py
```

### Config Tests (7 files) - Prefix: `test_*config*`, `test_*coordinate*`, `test_*display*`, `test_*debug*`, `test_*shop_conditions*`
Tests for configuration and settings:
- `test_config_integration.py` - Full config pipeline
- `test_config_manager_basic.py` - Config manager basics
- `test_coordinate_config.py` - Coordinate system configuration
- `test_display_config.py` - Display settings
- `test_debug_manager.py` - Debug utilities
- `test_scenario_config.py` - Scenario setup
- `test_shop_conditions.py` - Shop conditions

**Run config tests:**
```bash
pytest tests/ -k "config or coordinate_config or display_config or debug_manager or scenario or shop_conditions"
```

### Functions Tests (4 files) - Prefix: `test_functions_*`
Tests for utility functions:
- `test_functions_additional.py` - Additional features
- `test_functions_io_pickle.py` - I/O and persistence
- `test_functions_select_autosave.py` - Autosave management
- `test_functions_utilities.py` - Utility helpers

**Run function tests:**
```bash
pytest tests/ -k "functions"
```

### Game Mechanics Tests (6 files) - Prefix: `test_game_*`, `test_*state*`, `test_*weight*`, `test_*memory*`, `test_phase*`
Tests for core game loop and mechanics:
- `test_game_logger.py` - Game logging system
- `test_game_tick_events.py` - Game loop events
- `test_states.py` - Status effect system
- `test_memory_flash.py` - Memory mechanics
- `test_phase3_integration.py` - Phase 3 integration
- `test_weight_tolerance.py` - Weight calculations

**Run game mechanics tests:**
```bash
pytest tests/ -k "game or state or weight or memory or phase"
```

### Item Tests (5 files) - Prefix: `test_*commodity*`, `test_*drop*`, `test_*weapon*`, `test_*loot*`, `test_transfer_item*`
Tests for items and inventory:
- `test_commodity_items.py` - Item classification
- `test_drop_gold_visibility.py` - Drop mechanics
- `test_ensure_weapon_exp.py` - Weapon experience
- `test_loot_tables.py` - Loot generation
- `test_transfer_item.py` - Item transfer

**Run item tests:**
```bash
pytest tests/ -k "commodity or drop or weapon or loot or transfer_item"
```

### Manual Tests (3 files) - Prefix: `manual_*`
Manual testing utilities (not run by pytest by default):
- `manual_npc_spawner_check.py` - NPC spawner verification
- `manual_test_special_category.py` - Special item testing
- `manual_test_weight.py` - Weight tolerance checks

**Run manual tests:**
```bash
python tests/manual_npc_spawner_check.py
python tests/manual_test_special_category.py
python tests/manual_test_weight.py
```

### Map Tests (7 files) - Prefix: `test_map*`, `test_*tile*`, `test_*event_tile*`, `test_room_*`, `test_view_map*`
Tests for maps and world:
- `test_map_generator.py` - Core generation
- `test_map_generator_additional.py` - Extended features
- `test_map_generator_more.py` - More features
- `test_tiles.py` - Tile system
- `test_event_tile_assignment.py` - Event placement
- `test_room_take_interface.py` - Room interaction
- `test_view_map.py` - Map viewing

**Run map tests:**
```bash
pytest tests/ -k "map or tile or event_tile or room or view_map"
```

### Miscellaneous Tests (6 files)
Tests that don't fit clearly into other categories:
- `test_animations.py` - Animation system
- `test_container_allowed_subtypes_annotation.py` - Type validation
- `test_enumerate_confirm.py` - Enumeration tests
- `test_newline_fix_summary.py` - Text handling
- `test_refresh_stat_bonuses.py` - Stat recalculation
- `test_universe.py` - Universe/world

**Run misc tests:**
```bash
pytest tests/test_animations.py tests/test_universe.py tests/test_container_allowed_subtypes_annotation.py tests/test_enumerate_confirm.py tests/test_newline_fix_summary.py tests/test_refresh_stat_bonuses.py
```

### NPC & AI Tests (9 files) - Prefix: `test_*merchant*`, `test_mynx*`, `test_*npc*`, `test_llm*`
Tests for NPC behavior and AI:
- `test_llm_openrouter.py` - LLM integration
- `test_mynx.py` - Mynx creature core
- `test_mynx_possessive.py` - Mynx possessive pronouns
- `test_mynx_pronouns.py` - Mynx pronouns
- `test_npc_ai_config.py` - NPC AI configuration
- `test_npc_spawner_event.py` - NPC spawning
- `test_merchant.py` - Merchant functionality
- `test_merchant_shop_conditions_deterministic.py` - Shop conditions
- `test_merchant_unique_reset.py` - Merchant reset

**Run NPC/AI tests:**
```bash
pytest tests/ -k "merchant or mynx or npc or llm"
```

### Positions Tests (3 files) - Prefix: `test_positions_*`
Tests for coordinate and positioning system:
- `test_positions_edge_cases.py` - Boundary conditions
- `test_positions_integration.py` - System integration
- `test_positions_math.py` - Mathematical correctness

**Run position tests:**
```bash
pytest tests/ -k "positions"
```

### UI Tests (5 files) - Prefix: `test_*interface*`, `test_*shop_ui*`, `test_*book*`
Tests for user interface:
- `test_interface.py` - General UI
- `test_shop_ui.py` - Shop interface
- `test_shop_ui_edgecases.py` - Shop edge cases
- `test_book_pagination.py` - Book display
- `test_book_newlines.py` - Text handling

**Run UI tests:**
```bash
pytest tests/ -k "interface or shop_ui or book"
```

## File Statistics

| Category | Files | Pattern | Approx. Tests |
|----------|-------|---------|---------------|
| Combat | 7 | `*combat*, *move*, *advance*, *bat*` | 35+ |
| Config | 7 | `*config*, *coordinate*, *display*, *debug*` | 40+ |
| Functions | 4 | `functions_*` | 20+ |
| Game Mechanics | 6 | `game_*, *state*, *weight*, *memory*, phase*` | 30+ |
| Items | 5 | `*commodity*, *drop*, *weapon*, *loot*, transfer_item*` | 25+ |
| Manual | 3 | `manual_*` | - |
| Maps | 7 | `map*, *tile*, *event_tile*, room_*, view_map*` | 35+ |
| Misc | 6 | Various | 25+ |
| NPC/AI | 9 | `*merchant*, mynx*, *npc*, llm*` | 45+ |
| Positions | 3 | `positions_*` | 15+ |
| UI | 5 | `*interface*, *shop_ui*, *book*` | 30+ |
| **Total** | **65+** | | **~300+** |

## Running Tests

### Run Everything
```bash
pytest
pytest -v              # Verbose
pytest -q              # Quiet
```

### Run by Category
```bash
# Combat
pytest tests/ -k "combat or move or advance or bat"

# Items
pytest tests/ -k "commodity or drop or loot or transfer_item"

# NPC/AI
pytest tests/ -k "merchant or mynx or npc or llm"

# Config
pytest tests/ -k "config or coordinate_config or display_config"

# Multiple categories
pytest tests/ -k "combat or items"
```

### Run Specific File
```bash
pytest tests/test_moves_attack.py
pytest tests/test_shop_ui.py -v
```

### Run with Coverage
```bash
pytest --cov=src --cov=ai --cov-report=term-missing
```

### Run Only Fast Tests
```bash
pytest -m "not slow"
```

## Import Compatibility

All tests remain in `tests/` root for consistent import paths:

```python
# In any test file
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.player import Player  # type: ignore
from src.items import Item     # type: ignore
```

The `tests/conftest.py` handles module shimming automatically.

## Benefits

✅ **Clear Organization** - Naming patterns show test purpose  
✅ **Import Compatibility** - All tests in root for consistent imports  
✅ **Easy Discovery** - `-k` flag to run related tests  
✅ **Scalability** - Can add tests without directory changes  
✅ **Backwards Compatible** - All existing tests work unchanged  
✅ **Documentation** - Clear categorization system for new developers  

## Adding New Tests

When creating a new test, follow these patterns:

1. **Identify the category** based on what you're testing
2. **Name accordingly** using the category prefix pattern
3. **Place in `tests/` root**
4. **Run with category tests** using `-k` flag

Example: New combat test
```bash
cat > tests/test_new_combat_feature.py << 'EOF'
from src.moves import Move

def test_my_feature():
    move = Move()
    assert move is not None
EOF

# Run with other combat tests
pytest tests/ -k "combat or new_combat"
```

## Reference

See full documentation in:
- This file: `tests/TEST_ORGANIZATION.md`
- Quick reference: `tests/ORGANIZATION_QUICK_REFERENCE.md`
- Parent conftest: `tests/conftest.py`

### `combat/` - Combat System Tests (7 files)
Tests for turn-based combat mechanics including:
- Attack moves and move validation
- Combat advancement and viable moves
- Specific enemy abilities (bat attacks, cave bats)
- Combat coordinate system UAT
- Combat position calculations

**Key Files:**
- `test_moves_attack.py` - Attack mechanics
- `test_advance_viable.py` - Move viability checks
- `test_uat_combat_coordinate_system.py` - Full coordinate system validation

### `config/` - Configuration Tests (7 files)
Tests for game configuration, settings, and manager classes:
- Config file integration and parsing
- Display configurations
- Debug manager functionality
- Shop conditions and scenario setup
- Coordinate system configuration

**Key Files:**
- `test_config_integration.py` - Full config pipeline
- `test_coordinate_config.py` - Coordinate system setup
- `test_debug_manager.py` - Debug utilities

### `functions/` - Core Functions Tests (4 files)
Tests for utility functions in `src/functions.py`:
- I/O operations and pickle save/load
- Autosave functionality
- Utility helpers
- Additional function features

**Key Files:**
- `test_functions_io_pickle.py` - Save/load persistence
- `test_functions_select_autosave.py` - Autosave management

### `game_mechanics/` - Game Mechanics Tests (6 files)
Tests for core game loop and mechanics:
- Game event logging and tick system
- Game state changes and updates
- Status effects and states
- Memory and flash mechanics
- Integration testing between systems

**Key Files:**
- `test_game_tick_events.py` - Game loop events
- `test_states.py` - Status effect system
- `test_phase3_integration.py` - Cross-system integration

### `items/` - Item System Tests (5 files)
Tests for items, equipment, and inventory:
- Item types and classifications (commodity, weapons, armor)
- Item drop mechanics
- Experience and weapon stats
- Loot table generation
- Item transfer and inventory management

**Key Files:**
- `test_commodity_items.py` - Item type classification
- `test_loot_tables.py` - Loot generation
- `test_ensure_weapon_exp.py` - Weapon experience tracking

### `manual/` - Manual Testing (3 files)
Scripts for manual testing and verification:
- NPC spawner verification
- Special item category testing
- Weight tolerance manual checks

**Usage:**
```bash
python tests/manual/manual_npc_spawner_check.py
python tests/manual/manual_test_special_category.py
python tests/manual/manual_test_weight.py
```

### `maps/` - Map System Tests (7 files)
Tests for map generation, tiles, and world navigation:
- Map generator functionality
- Tile system and properties
- Event assignments on tiles
- Room/tile interaction interface
- Map viewing and navigation

**Key Files:**
- `test_map_generator.py` - Core map generation
- `test_map_generator_additional.py`, `test_map_generator_more.py` - Extended functionality
- `test_tiles.py` - Tile system

### `misc/` - Miscellaneous Tests (6 files)
Tests that don't fit cleanly into other categories:
- Animation system tests
- Universe/world tests
- Type annotation validation
- Stat recalculation
- New features and bug fixes

**Note:** These should be reviewed for potential reorganization as the test suite grows.

### `npc_ai/` - NPC and AI Tests (9 files)
Tests for NPC behavior, dialogue, and AI systems:
- LLM integration testing (OpenRouter)
- Mynx creature behavior and pronouns
- Merchant functionality and shops
- NPC spawning and events
- NPC AI configuration

**Key Files:**
- `test_mynx.py` - Mynx creature core
- `test_merchant.py` - Merchant functionality
- `test_llm_openrouter.py` - LLM integration

### `positions/` - Coordinate System Tests (3 files)
Tests for the coordinate/positioning system:
- Mathematical position calculations
- Edge cases in coordinate system
- Integration of positions with other systems

**Key Files:**
- `test_positions_math.py` - Mathematical correctness
- `test_positions_edge_cases.py` - Boundary conditions

### `ui/` - User Interface Tests (5 files)
Tests for UI rendering and interaction:
- Book display and pagination
- Text handling (newlines, special chars)
- Shop UI and shopping interface
- Interface interactions

**Key Files:**
- `test_book_pagination.py` - Book display system
- `test_shop_ui.py` - Shop interface
- `test_interface.py` - General UI

### `uat/` - User Acceptance Testing (3 files)
Acceptance testing scripts and results:
- Memory flash UAT testing
- UAT automation scripts
- UAT result documentation

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Tests by Category
```bash
# Combat tests only
pytest tests/combat/

# Multiple categories
pytest tests/combat/ tests/items/

# Specific test file
pytest tests/combat/test_moves_attack.py

# Specific test function
pytest tests/combat/test_moves_attack.py::test_specific_function
```

### Run Tests with Coverage
```bash
pytest --cov=src --cov=ai --cov-report=term-missing
```

### Run Tests with Verbose Output
```bash
pytest -v tests/
```

### Run Only Quick Tests (skip slow/integration tests)
```bash
pytest -m "not slow"
```

## Statistics

| Category | Files | Test Count | Focus |
|----------|-------|-----------|-------|
| combat | 7 | ~35+ | Turn-based combat, moves, enemies |
| config | 7 | ~40+ | Configuration management |
| functions | 4 | ~20+ | Utility functions, I/O |
| game_mechanics | 6 | ~30+ | Game loop, events, states |
| items | 5 | ~25+ | Inventory, equipment, loot |
| manual | 3 | - | Manual verification scripts |
| maps | 7 | ~35+ | Map generation, tiles, navigation |
| misc | 6 | ~25+ | Miscellaneous features |
| npc_ai | 9 | ~45+ | NPC behavior, merchants, LLM |
| positions | 3 | ~15+ | Coordinate system math |
| ui | 5 | ~30+ | Interface, display, pagination |
| uat | 3 | - | Acceptance testing |
| **TOTAL** | **65+** | **~300+** | **Comprehensive game coverage** |

## Adding New Tests

When adding new test files:

1. **Determine the appropriate category** based on what system your test covers
2. **Place the file in the corresponding subdirectory**
3. **Follow the naming convention:** `test_<feature>.py`
4. **Ensure each subdirectory has an `__init__.py`** (already in place)
5. **Import fixtures from `conftest.py`** for shared setup

### Example: Adding a new combat test
```bash
# Create in tests/combat/
cat > tests/combat/test_new_combat_feature.py << 'EOF'
import pytest
from src.combat import CombatSystem

def test_new_feature():
    # Your test here
    assert True
EOF
```

## Import Patterns

Since test files are now in subdirectories, imports work as expected:

```python
# In tests/combat/test_example.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.combat import CombatSystem  # type: ignore
from src.moves import Move  # type: ignore
```

The `conftest.py` handles module shimming after imports, so tests can use bare imports like `from npc import NPC` through the shim mechanism.

## Migration Notes

- All original test files have been preserved
- `conftest.py` remains in `tests/` root for discovery
- `phase4_test_executor.py` remains in root (references tests/ subdirectories)
- `PHASE4_TEST_RESULTS.json` remains in root (output location)
- `uat/` directory was pre-existing and is left as-is
- `__pycache__/` is automatically generated and can be ignored

## Benefits of This Structure

✅ **Logical Organization** - Related tests grouped by feature/system  
✅ **Easier Navigation** - Find tests quickly by category  
✅ **Scalability** - Accommodates growth without root-level clutter  
✅ **Parallel Execution** - Pytest can run category suites independently  
✅ **Clear Dependencies** - Visually see which systems tests depend on  
✅ **Maintenance** - Easier to identify orphaned or redundant tests  
✅ **Onboarding** - New developers can understand test structure quickly  

## Future Improvements

- Consider splitting large categories (e.g., `npc_ai/` has 9 files)
- Consolidate `misc/` tests into appropriate categories as they mature
- Add more integration tests bridging multiple systems
- Create `integration/` category for cross-system tests
- Add performance benchmarks in separate `benchmarks/` directory
