# Quick Start: Phase 4 Manual Testing

## One-Liner to Run Game with Test Config

### PowerShell
```powershell
$env:CONFIG_FILE='config_phase4_testing.ini'; python src/game.py
```

### Bash
```bash
CONFIG_FILE=config_phase4_testing.ini python src/game.py
```

## What to Expect

✅ **Game should load and show:**
```
###
Test Mode: True
Start Map: testing-map
Start Position: (2, 2)
###

A mossy alcove beneath a leaning cypress...
```

## Quick Test Checklist

- [ ] Game starts without errors
- [ ] Shows "Test Mode: True" output
- [ ] Displays starting room description
- [ ] Can move around (e, s, se commands)
- [ ] Can enter combat
- [ ] Combat shows coordinate positions
- [ ] Flanking mechanics work
- [ ] Distance calculations visible

## What Was Fixed

| Issue | Fix | Result |
|-------|-----|--------|
| Hardcoded config file | Made dynamic with env var | Can use any config file |
| Invalid start position | Changed 1,1 to 2,2 | Valid starting tile |
| No map found error | Position now exists in map | Game loads correctly |

## Files Changed

- `src/game.py` - Now reads `CONFIG_FILE` environment variable
- `config_phase4_testing.ini` - Starting position corrected

## Test Status

✅ All 746 tests passing  
✅ No regressions  
✅ Configuration system working  
✅ Game launches successfully  

## Next: Explore Phase 4 Features

1. Start game (see command above)
2. Select "1" for NEW GAME
3. Move around: type 'e' (east), 's' (south), 'se' (southeast)
4. Find combat encounters
5. Observe coordinate positioning and flanking mechanics

---

**Status**: Ready to test! 🚀
