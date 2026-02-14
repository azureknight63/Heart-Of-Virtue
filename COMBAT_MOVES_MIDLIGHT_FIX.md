## Combat Moves Mid-Fight Fix - Complete Implementation Report

### Issue Diagnosed
When enemies or allies are added to combat mid-fight, their moves retain stale `current_stage` and `beats_left` values, causing:
1. Moves not progressing through stages (prep → execute → recoil → cooldown)
2. Combat returning to player's turn prematurely  
3. Cascading failures with multiple additions (e.g., 5 RockRumblers in ch01.py)

### Root Cause
The main combat initialization resets move states, but `combat_engage()` and manual ally additions did not. NPCs joining mid-combat kept their initialization-time move state instead of getting a clean reset.

### Solution: DRY Principle Applied

#### Core Implementation - `src/npc.py`

**New Helper Method (lines 297-305):**
```python
def reset_combat_moves(self):
    """Resets all move states to stage 0 with 0 beats remaining."""
    for move in self.known_moves:
        move.current_stage = 0
        move.beats_left = 0
```

**Updated Method (lines 307-318):**
```python
def combat_engage(self, player):
    """Adds NPC to combat and resets move states."""
    player.combat_list.append(self)
    player.combat_proximity[self] = int(self.default_proximity * random.uniform(0.75, 1.25))
    if len(player.combat_list_allies) > 0:
        for ally in player.combat_list_allies:
            ally.combat_proximity[self] = int(self.default_proximity * random.uniform(0.75, 1.25))
    self.in_combat = True
    self.reset_combat_moves()  # ← Reusable call
```

#### Story Events - `src/story/ch01.py`

**Fix #1 - Ch01PostRumbler3 (lines 471-474):**
```python
gorran = self.tile.spawn_npc("Gorran", delay=0)
self.player.combat_list_allies.append(gorran)
gorran.in_combat = True
gorran.reset_combat_moves()  # Unconditional - always mid-combat here
```

**Fix #2 - AfterGorranIntro (lines 542-546):**
```python
for gorran in self.tile.npcs_here:
    if gorran.name == "Gorran":
        self.player.combat_list_allies.append(gorran)
        gorran.friend = True
        if self.player.in_combat:  # Conditional - may be out of combat
            gorran.reset_combat_moves()
```

#### Test Coverage

**Enhanced Test - `tests/test_cave_bat.py`:**
- Sets stale move state before calling `combat_engage()`
- Verifies all moves reset to stage=0, beats=0

**New Suite - `tests/test_combat_moves_mid_fight.py` (215 lines, 12 tests):**
- `TestResetCombatMoves` - Tests the helper method
- `TestCombatEngageMovesReset` - Tests enemy additions
- `TestMultipleEnemiesJoiningMidCombat` - Tests RockRumblers scenario
- `TestAllyJoiningMidCombat` - Tests Gorran scenario
- `TestMoveProgressionAfterReset` - Verifies correct progression

### Key Benefits

✅ **Single Source of Truth** - Reset logic in one place
✅ **Reusable** - Works for all NPC types and scenarios
✅ **Maintainable** - Clear method name and purpose documented
✅ **Testable** - Comprehensive test coverage with edge cases
✅ **Backward Compatible** - Existing code unchanged, only enhancements
✅ **Scalable** - Future NPCs automatically get the fix

### Verification Steps

```bash
# New comprehensive test suite
pytest tests/test_combat_moves_mid_fight.py -v

# Enhanced existing test
pytest tests/test_cave_bat.py::test_combat_engage_adds_to_player_and_allies -v

# All combat tests
pytest tests/ -k "combat" -v

# Full suite
pytest tests/ -v
```

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| `src/npc.py` | Added method + Updated | 297-318 |
| `src/story/ch01.py` | Added reset calls | 474, 546 |
| `tests/test_cave_bat.py` | Enhanced test | 84-105 |
| `tests/test_combat_moves_mid_fight.py` | New test file | 1-215 |

### Result

Enemies and allies now properly initialize move states when joining mid-combat, ensuring moves progress through all stages and combat flow continues normally.
