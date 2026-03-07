# Chest Rumbler Battle Narrative Fix - Summary

## Problem
When looting the wooden chest in the Dark Grotto (tile 7,1), the narrative text describing Jean finding the rusty iron mace and hearing the ominous rumbling was being skipped because combat started immediately. Players were missing important story context for their first major battle.

## Root Cause
The `Ch01ChestRumblerBattle` event was designed to trigger when the chest became empty, but it immediately spawned the Rock Rumbler enemy and started combat without giving the player a chance to read the narrative text.

## Solution

### 1. Event Base Class Enhancement (`src/events.py`)
- Modified `pass_conditions_to_process()` to check for `needs_input` flag
- Events requiring user input are no longer automatically removed from the tile
- This allows events to pause and wait for player acknowledgment

### 2. Game Service Enhancement (`src/api/services/game_service.py`)
- Updated `trigger_tile_events()` to detect when events dynamically request input during processing
- Events that set `needs_input=True` during execution are now properly captured and stored in session
- This enables narrative-heavy events to pause mid-execution

### 3. Ch01ChestRumblerBattle Event Redesign (`src/story/ch01.py`)
**Added triggered flag:**
```python
def __init__(self, player, tile, params=None, repeat=True, name='Ch01_Chest_Rumbler_Battle'):
    super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)
    self.triggered = False  # Prevents re-triggering
```

**Split process() into two phases:**
- **Phase 1** (user_input=None): Shows narrative, equips mace, sets needs_input=True
- **Phase 2** (user_input="continue"): Spawns enemy, starts combat

**Added check_conditions guard:**
```python
def check_conditions(self):
    if self.triggered:
        return  # Don't re-process
    # ... rest of logic
```

### 4. Bug Fix: CombatantSerializer Import (`src/api/combat_adapter.py`)
- Fixed `name 'CombatantSerializer' is not defined` error
- Moved import to module level to ensure it's available for tactical suggestions

## Flow After Fix

1. Player takes last item from chest
2. `Ch01ChestRumblerBattle.check_conditions()` detects empty chest
3. Sets `triggered=True` and calls `process(user_input=None)`
4. `process()` shows narrative text, equips mace, sets `needs_input=True`
5. Event stays on tile (not removed due to base class change)
6. Frontend displays "Continue" button
7. Player clicks "Continue"
8. `process_event_input()` calls `process(user_input="continue")`
9. Rock Rumbler spawns, combat initiates
10. Event marks itself as `completed=True` and removes itself from tile

## Testing

### Integration Test Suite (`tests/api/test_chest_rumbler_integration.py`)
Created comprehensive test coverage:

1. **test_complete_chest_rumbler_sequence**
   - Opens chest
   - Takes all items
   - Verifies narrative pause with correct prompt
   - Submits user input
   - Confirms combat starts with Rock Rumbler
   - Validates mace is equipped

2. **test_event_does_not_retrigger**
   - Empties chest
   - Triggers event
   - Calls trigger_tile_events again
   - Verifies event doesn't re-process (triggered flag works)

3. **test_event_cleanup_after_completion**
   - Completes full event sequence
   - Verifies event removed from pending_events
   - Confirms event removed from tile

**All tests passing:** ✓

## Files Modified
- `src/events.py` - Base Event class enhancement
- `src/api/services/game_service.py` - Dynamic input detection
- `src/story/ch01.py` - Event redesign with triggered flag
- `src/api/combat_adapter.py` - Import fix
- `tests/api/test_chest_rumbler_integration.py` - New test suite

## Benefits
- ✅ Players can now read the narrative before combat
- ✅ Story beats are properly paced
- ✅ No more skipped flavor text
- ✅ Reusable pattern for other narrative-heavy events
- ✅ Comprehensive test coverage ensures stability
