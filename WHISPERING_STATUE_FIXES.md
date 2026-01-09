# Whispering Statue Event Fixes

## Issues Fixed

### Issue 1: Missing Feedback for Reward
**Problem**: The event rewards the player, but the frontend wasn't refreshing the room state immediately to show the reward.

**Fix**: The event now spawns 500 Gold (which exists in the logic). The primary fix was ensuring the frontend and backend handle state updates correctly so the spawned item appears immediately.
```python
self.tile.spawn_item('Gold', amt=500)
```

### Issue 2: Spawned Enemies Don't Attack Immediately
**Problem**: When selecting the wrong answer, a Slime NPC was spawned but didn't attack Jean until the player left and re-entered the room.

**Fix**: Added combat detection after event processing in `src/api/services/game_service.py`:

1. **Backend (game_service.py)**: After processing an event with user input, the service now checks for combat using `check_for_combat()`. If aggressive NPCs are present, combat is automatically initiated and the combat state is returned to the frontend.

2. **Frontend (GamePage.jsx)**: The event input handler now checks for the `combat_started` flag in the response. If combat was initiated, it fetches the combat status to transition the UI to combat mode.

## Files Modified

1. **src/story/effects.py**
   - Line 479: Changed spawned item from Gold to Sapphire

2. **src/api/services/game_service.py**
   - Lines 407-432: Added combat check after event processing
   - Returns `combat_started` flag and `combat_state` if combat is initiated

3. **frontend/src/pages/GamePage.jsx**
   - Lines 140-144: Added combat initiation check after event processing
   - Calls `fetchCombatStatus()` if combat was triggered by the event

## Testing

To test these fixes:

1. **Correct Answer Test**:
   - Navigate to the Whispering Statue event
   - Select option 1 ("A River")
   - Verify that Gold appears in the room after closing the dialog
   - Check the Interact menu to confirm the Gold is visible

2. **Wrong Answer Test**:
   - Navigate to the Whispering Statue event (or reload the save)
   - Select option 2 or 3 (wrong answers)
   - Verify that combat starts immediately after the event dialog closes
   - Confirm that the Slime is present and combat UI is active

## Technical Details

The combat detection works as follows:
1. Event processes and spawns NPC (e.g., Slime)
2. `check_for_combat()` scans NPCs in the current room
3. If aggressive NPCs are found, combat is initialized via `_initialize_combat()`
4. Combat state is serialized and returned to frontend
5. Frontend transitions to combat mode automatically

This ensures that events can spawn enemies and trigger combat seamlessly without requiring the player to leave and re-enter the room.
