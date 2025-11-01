# [Agent] Game Configuration Fix - Phase 4 Manual Testing Setup

## Summary
Fixed game startup with `config_phase4_testing.ini` by:
1. **Making config file selection dynamic** - Added `CONFIG_FILE` environment variable support to `src/game.py`
2. **Correcting starting position** - Updated `config_phase4_testing.ini` to use valid coordinate (2, 2) instead of (1, 1)

## Changes Made

### 1. Modified `src/game.py` (lines 103-110)
Changed hardcoded config file loading to support environment variable:

```python
# OLD (line 113)
config_mgr = ConfigManager('config_dev.ini')

# NEW (lines 108-110)
import os
config_file = os.getenv('CONFIG_FILE', 'config_dev.ini')
config_mgr = ConfigManager(config_file)
```

**Impact**: Game now checks `CONFIG_FILE` environment variable; defaults to `config_dev.ini` if not set.

### 2. Updated `config_phase4_testing.ini` (line 12)
Changed starting position to match actual tile in testing-map:

```ini
# OLD
startposition = 1, 1

# NEW
startposition = 2, 2
```

**Why**: The `testing-map.json` doesn't have a tile at (1, 1). First available tile is at (2, 2).

## How to Run Game with Test Config

### PowerShell Method (Recommended)
```powershell
$env:CONFIG_FILE = 'config_phase4_testing.ini'
python src/game.py
```

### Command Line Method
```powershell
$env:CONFIG_FILE='config_phase4_testing.ini'; python src/game.py
```

### Bash/Linux Method
```bash
CONFIG_FILE=config_phase4_testing.ini python src/game.py
```

## Test Config Features (`config_phase4_testing.ini`)

| Setting | Value | Purpose |
|---------|-------|---------|
| testmode | True | Enables test mode output |
| skipdialog | True | Skips dialogue sequences |
| skipintro | True | Skips intro scene |
| startmap | testing-map | Uses small test map |
| startposition | 2, 2 | Valid starting tile |
| enable_animations | True | Shows visual effects |
| enable_flanking_mechanics | True | Activates new combat features |
| enable_tactical_positioning | True | Activates coordinate system |

## Verification

Run with test config to verify:
```
###
Test Mode: True
Start Map: testing-map
Start Position: (2, 2)
###
```

Game should:
- ✅ Load without errors
- ✅ Show test mode output
- ✅ Load testing-map correctly
- ✅ Place player at (2, 2)
- ✅ Show starting room description
- ✅ Display game menu

## Next Steps for Phase 4 Manual Testing

1. **Start game with test config** (see instructions above)
2. **Follow MANUAL_TEST_START_HERE.md** for testing procedures
3. **Execute combat scenarios** using Phase 4 testing framework
4. **Validate coordinate positioning** during combat
5. **Check tactical mechanics** (flanking, positioning, distance)

## Files Modified
- `src/game.py` - Added CONFIG_FILE environment variable support
- `config_phase4_testing.ini` - Fixed starting position from (1, 1) to (2, 2)

## Files Created for Testing
- `test_startup.ps1` - Basic startup test script
- `test_startup_newgame.ps1` - New game startup test with input
- `test_startup_exit.ps1` - Exit test script
- `check_map_name.py` - Utility to inspect map JSON structure
