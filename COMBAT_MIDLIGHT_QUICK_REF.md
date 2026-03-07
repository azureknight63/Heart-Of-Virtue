## Quick Reference: Combat Moves Mid-Fight Fix

### What Was Fixed
Enemies/allies joining combat mid-fight now have move states properly reset, preventing:
- Moves not progressing through stages
- Combat returning to player turn prematurely
- Cascading failures with multiple additions

### Changes Summary

#### 1. src/npc.py - DRY Helper Method
```python
# Lines 297-305: NEW METHOD
def reset_combat_moves(self):
    for move in self.known_moves:
        move.current_stage = 0
        move.beats_left = 0

# Lines 307-318: UPDATED METHOD
def combat_engage(self, player):
    # ... existing code ...
    self.in_combat = True
    self.reset_combat_moves()  # ← ADDED
```

#### 2. src/story/ch01.py - Two Locations Fixed

**Location 1 (Lines 471-474):**
```python
gorran.in_combat = True
gorran.reset_combat_moves()  # ← ADDED
```

**Location 2 (Lines 542-546):**
```python
gorran.friend = True
if self.player.in_combat:
    gorran.reset_combat_moves()  # ← ADDED
```

#### 3. tests/test_cave_bat.py - Enhanced
```python
# Added before combat_engage() call:
for move in bat.known_moves:
    move.current_stage = 2
    move.beats_left = 5

# Added after assertions:
for move in bat.known_moves:
    assert move.current_stage == 0
    assert move.beats_left == 0
```

#### 4. tests/test_combat_moves_mid_fight.py - NEW
12 comprehensive tests covering:
- reset_combat_moves() method
- combat_engage() behavior
- Multiple enemies scenario
- Ally joining scenario
- Move progression after reset

### Quick Test Commands

```bash
# Validate all fixes
pytest tests/test_combat_moves_mid_fight.py -v

# Validate one specific enhanced test
pytest tests/test_cave_bat.py::test_combat_engage_adds_to_player_and_allies -v

# Run all combat tests
pytest tests/ -k combat -v
```

### DRY Principle Applied

**Before:** Move reset logic replicated in multiple places
**After:** Single `reset_combat_moves()` method called from all locations

This ensures:
- No duplicate code
- Single source of truth
- Easy to maintain
- Automatic coverage for future NPCs

### Tested Scenarios

✓ Single enemy joining via `combat_engage()` 
✓ Multiple enemies joining (`RockRumblers` in ch01.py)
✓ Ally joining unconditionally (`Gorran` at line 474)
✓ Ally joining conditionally (`Gorran` at line 546)
✓ Stale move states being reset
✓ Move progression after reset
✓ Empty move lists handled gracefully

### Critical Fix Locations

1. **src/npc.py line 318** - All enemies now reset on engage
2. **src/story/ch01.py line 474** - Gorran never enters with stale moves
3. **src/story/ch01.py line 546** - Conditional reset for safety

### Expected Behavior

**Before Fix:**
```
Enemy joins → stale move state → move.advance() fails → 
combat return early → player frustrated
```

**After Fix:**
```
Enemy joins → reset_combat_moves() called → clean state → 
move.advance() works → full combat flow → player happy
```

---
For detailed analysis, see: `COMBAT_MOVES_MIDLIGHT_FIX.md`
For validation details, see: `COMBAT_MOVES_FIX_VALIDATION.py`
