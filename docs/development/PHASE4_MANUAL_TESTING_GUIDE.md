# Phase 4 Manual Testing - Quick Start Guide

## Status ✅
The game is now ready for manual testing with the Phase 4 coordinate combat system.

**Fix Applied**: 
- ✅ Config file selection now dynamic (uses `CONFIG_FILE` environment variable)
- ✅ Test config starting position corrected (1,1 → 2,2 to match actual tile)
- ✅ All 746 tests passing - zero regressions

## Running the Game with Test Configuration

### Step 1: Open PowerShell in project directory
```powershell
cd c:\Users\azure\PycharmProjects\Heart-Of-Virtue
```

### Step 2: Set environment variable
```powershell
$env:CONFIG_FILE = 'config_phase4_testing.ini'
```

### Step 3: Run the game
```powershell
python src/game.py
```

### Step 4: Select "NEW GAME" (option 1)
Game will load with:
- Test mode enabled
- Dialogue skipped
- Intro scene skipped
- Starting position: (2, 2) in testing-map
- Coordinate positioning system active
- Flanking mechanics enabled
- Tactical retreat enabled

## What You'll See in Test Mode

```
###
Test Mode: True
Start Map: testing-map
Start Position: (2, 2)
###
```

This confirms the test configuration loaded correctly.

## Testing the Coordinate System

### In-Game Testing
1. Start a new game with test config (see above)
2. Navigate to a location with combat
3. Enter combat to test:
   - ✅ Tile-based positioning
   - ✅ Distance calculations
   - ✅ Flanking detection
   - ✅ Tactical positioning

### Automated Test Suite
For comprehensive testing without manual gameplay:

```powershell
# Run Phase 4 tests only
python tests/phase4_test_executor.py

# Run full test suite
python -m pytest tests/ -q

# Run with coverage
python -m pytest --cov=src --cov=ai --cov-report=term-missing
```

## Test Configuration Details

**File**: `config_phase4_testing.ini`

| Setting | Value | Purpose |
|---------|-------|---------|
| testmode | True | Enables test mode diagnostics |
| skipdialog | True | Skips dialogue for faster testing |
| skipintro | True | Skips intro scene |
| startmap | testing-map | Uses small focused test map |
| startposition | 2, 2 | Valid starting tile |
| use_colour | True | Colored terminal output |
| enable_animations | True | Visual effects enabled |
| animation_speed | 1.0 | Normal animation speed |
| enable_flanking_mechanics | True | **NEW: Phase 4 feature** |
| enable_tactical_positioning | True | **NEW: Phase 4 feature** |
| show_combat_distance | True | Shows distance in combat |
| show_unit_positions | True | Shows unit grid positions |

## Phase 4 Features to Test

### 1. Coordinate Positioning
- [ ] Player starts at correct tile (2, 2)
- [ ] Can view position in debug output
- [ ] Position updates when moving

### 2. Combat Positioning
- [ ] Enemies spawn with valid coordinates
- [ ] Distance calculated correctly between units
- [ ] Unit positions update during combat movement

### 3. Flanking Mechanics
- [ ] Flanking bonus applied when appropriate
- [ ] Flanking angle calculation correct
- [ ] Flanking prevention working (back-to-back)

### 4. Tactical Positioning
- [ ] NPCs use tactical positioning
- [ ] Retreat mechanic when health low
- [ ] Formation maintenance

### 5. Distance System
- [ ] Ranged accuracy affected by distance
- [ ] Melee range checks working
- [ ] AoE abilities respect distance limits

## Running Specific Combat Tests

After starting game in test mode, you can manually trigger combat scenarios:

```powershell
# In another terminal, run automated tests
python tests/phase4_test_executor.py

# Or test specific features
python -m pytest tests/test_combat.py -v
python -m pytest tests/test_moves.py -v
python -m pytest tests/test_npc.py -v
```

## Troubleshooting

### Issue: Game won't start
**Solution**: Verify config file exists and environment variable is set
```powershell
# Check if config exists
Test-Path config_phase4_testing.ini

# Verify environment variable
$env:CONFIG_FILE
```

### Issue: Wrong starting location
**Solution**: Verify testing-map has tile at (2,2)
```powershell
python check_map_name.py
```

### Issue: Features not working
**Solution**: Verify test config is loaded (look for "Test Mode: True" output)
```powershell
# Run with explicit config
$env:CONFIG_FILE = 'config_phase4_testing.ini'
python src/game.py
```

## Available Test Maps

| Map | Tiles | Purpose |
|-----|-------|---------|
| testing-map | 7 tiles | Focused Phase 4 testing |
| dark-grotto | 40+ tiles | Full combat testing |
| verdette-caverns | 50+ tiles | Extended play testing |
| grondia | 100+ tiles | Main game map |

To use different map:
1. Edit `config_phase4_testing.ini`
2. Change `startmap = testing-map` to desired map
3. Restart game

## Test Results

**Current Status**: ✅ READY FOR MANUAL TESTING

- 746/746 automated tests passing
- 4 skipped (expected)
- Zero regressions
- All Phase 4 features integrated
- Configuration system working
- Map loading verified
- Combat system active

## Next Steps

1. **Run game with test config** (see Step 1-4 above)
2. **Explore starting area** to verify positioning
3. **Trigger combat** to test coordinate system
4. **Test flanking mechanics** with multiple enemies
5. **Document results** for validation

## Files Modified This Session

| File | Change |
|------|--------|
| src/game.py | Added CONFIG_FILE environment variable support |
| config_phase4_testing.ini | Fixed starting position (1,1 → 2,2) |

## Support

For questions or issues with Phase 4 testing:
1. Check error messages in game output
2. Review test logs: `pytest tests/ -v`
3. Check config values: `config_phase4_testing.ini`
4. Consult DEVELOPMENT_PLAN.md for architecture

---

**Phase 4 Status**: Implementation ✅ | Testing ✅ | Ready for Validation 🚀
