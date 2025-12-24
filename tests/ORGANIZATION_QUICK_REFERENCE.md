# Test Organization - Quick Reference

## Structure Summary

The `tests/` directory has been reorganized into 11 functional categories:

```
tests/
├── combat/              (7 files)   - Turn-based combat & moves
├── config/              (7 files)   - Configuration & managers
├── functions/           (4 files)   - Core utility functions
├── game_mechanics/      (6 files)   - Game loop & mechanics
├── items/               (5 files)   - Items & inventory
├── manual/              (3 files)   - Manual testing utilities
├── maps/                (7 files)   - Map generation & tiles
├── misc/                (6 files)   - Miscellaneous tests
├── npc_ai/              (9 files)   - NPC behavior & AI
├── positions/           (3 files)   - Coordinate system
├── ui/                  (5 files)   - User interface
└── uat/                 (3 files)   - User acceptance tests
```

**Total:** 65+ test files, 947 total tests, 300+ test cases

## Quick Run Commands

```bash
# Run everything
pytest

# Run specific category
pytest tests/combat/
pytest tests/items/
pytest tests/npc_ai/

# Run specific file
pytest tests/combat/test_moves_attack.py

# Run with verbose output
pytest -v tests/combat/

# Run with coverage
pytest --cov=src --cov=ai --cov-report=term-missing

# Run specific test function
pytest tests/combat/test_moves_attack.py::test_attack_initial_evaluate_uses_fists

# Run tests matching pattern
pytest -k "combat" -v
```

## Category Descriptions

| Category | Files | Purpose | Key Tests |
|----------|-------|---------|-----------|
| **combat** | 7 | Combat system, moves, attacks | test_moves_attack.py, test_advance_viable.py |
| **config** | 7 | Configuration, managers | test_config_integration.py, test_coordinate_config.py |
| **functions** | 4 | Utility functions | test_functions_io_pickle.py, test_functions_utilities.py |
| **game_mechanics** | 6 | Game loop, events, states | test_game_tick_events.py, test_states.py |
| **items** | 5 | Items, equipment, loot | test_commodity_items.py, test_loot_tables.py |
| **manual** | 3 | Manual verification | manual_npc_spawner_check.py |
| **maps** | 7 | Maps, tiles, generation | test_map_generator.py, test_tiles.py |
| **misc** | 6 | Miscellaneous features | test_animations.py, test_universe.py |
| **npc_ai** | 9 | NPCs, merchants, AI | test_merchant.py, test_mynx.py, test_llm_openrouter.py |
| **positions** | 3 | Coordinate math, positioning | test_positions_math.py, test_positions_integration.py |
| **ui** | 5 | Interface, display | test_shop_ui.py, test_book_pagination.py |
| **uat** | 3 | Acceptance testing | UAT_MEMORY_FLASH.md |

## Finding Tests

Need to find a test? Use these patterns:

- **Combat mechanics?** → `tests/combat/`
- **Item/inventory?** → `tests/items/`
- **NPC or merchant?** → `tests/npc_ai/`
- **UI or shop?** → `tests/ui/`
- **Map or tiles?** → `tests/maps/`
- **Configuration issue?** → `tests/config/`
- **Game loop/events?** → `tests/game_mechanics/`
- **Coordinates/positions?** → `tests/positions/`
- **Utility functions?** → `tests/functions/`
- **Not sure?** → Try `grep -r "test_name" tests/` or see `TEST_ORGANIZATION.md`

## Adding New Tests

1. Place new test file in appropriate subdirectory
2. Follow naming: `test_<feature>.py`
3. Each directory already has `__init__.py` (no action needed)
4. Import fixtures normally from `conftest.py`

Example:
```bash
# New combat test
cat > tests/combat/test_new_combat_feature.py << 'EOF'
from src.moves import Move

def test_new_feature():
    move = Move()
    assert move is not None
EOF

pytest tests/combat/test_new_combat_feature.py
```

## Migration Details

✅ **Preserved:** All original test files remain (just reorganized)  
✅ **Preserved:** `conftest.py`, `phase4_test_executor.py`, PHASE4 results  
✅ **Added:** 11 new subdirectories with `__init__.py` for each  
✅ **Added:** `TEST_ORGANIZATION.md` (comprehensive guide)  
✅ **Working:** All pytest discovery and execution  

## Troubleshooting

**Tests not discovered?**
```bash
pytest --collect-only tests/combat/
```

**Import errors when running tests?**
- Check `sys.path` setup in test file (see `conftest.py` pattern)
- Ensure `__init__.py` exists in subdirectory
- Run from project root: `cd Heart-Of-Virtue && pytest`

**Need to see all available tests?**
```bash
pytest --collect-only -q
```

## Documentation

- **Full Details:** See `tests/TEST_ORGANIZATION.md`
- **Import Patterns:** See `tests/TEST_ORGANIZATION.md` → "Import Patterns"
- **New Test Guidelines:** See `tests/TEST_ORGANIZATION.md` → "Adding New Tests"

---

**Last Updated:** 2025-11-01  
**Total Tests:** 947 test cases organized across 12 categories

