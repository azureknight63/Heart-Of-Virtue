# Combat Event Injection Fix

## Problem
Combat events (particularly `Ch01PostRumblerRep`) that attempt to inject new enemies when all enemies are defeated failed because the victory screen/cleanup happened **before** the events had a chance to evaluate their conditions.

When `len(player.combat_list) == 0`, the old code would immediately:
1. Declare victory
2. Award experience
3. Break the combat loop

This prevented events from triggering their `process()` methods to spawn reinforcements.

## Solution
Evaluate **all combat events one final time** when enemies are defeated, but **before** declaring victory. If events inject new enemies, continue combat instead of exiting.

### Changes Made

#### 1. Terminal Combat (`src/combat.py`)
Added a final event evaluation pass when `len(player.combat_list) == 0`:

```python
if len(player.combat_list) == 0:
    # All enemies defeated. Before declaring victory, evaluate all combat events one final time.
    # This allows events (like reinforcement spawners) to inject new enemies before combat ends.
    if len(player.combat_events) > 0:
        for event in player.combat_events:
            event.check_combat_conditions()
    
    # If events injected new enemies, loop back to continue combat
    if len(player.combat_list) > 0:
        continue
    
    # True victory - no enemies remain and no events triggered
    print("Victory!")
    # ... rest of victory handling
```

**Key Flow:**
1. Check if enemies are gone
2. Evaluate all combat events (calls their `check_combat_conditions()`)
3. If an event's conditions are met, its `process()` method can spawn new enemies
4. If new enemies exist, loop continues
5. Only declare victory when truly no enemies remain

#### 2. API Combat (`src/api/combat_adapter.py`)

Added new method `_evaluate_combat_events()`:
```python
def _evaluate_combat_events(self):
    """
    Evaluate all active combat events when enemies are defeated.
    This allows events (like reinforcement spawners) to inject new enemies
    before combat ends, preventing premature victory declarations.
    """
    if len(self.player.combat_events) == 0:
        return
    
    for event in self.player.combat_events[:]:  # Use slice copy
        if hasattr(event, "check_combat_conditions"):
            try:
                event.check_combat_conditions()
            except Exception as e:
                # Log but don't crash on event evaluation errors
                logger = getattr(self, 'logger', None)
                if logger:
                    logger.warning(f"Error evaluating combat event {event.name}: {e}")
```

Modified victory check in `_execute_move()`:
```python
# Evaluate all combat events one final time when enemies are defeated
# This allows events (like reinforcement spawners) to inject new enemies before victory
if len(self.player.combat_list) == 0:
    self._evaluate_combat_events()

event_just_triggered = hasattr(self.player, 'combat_adapter_state') and 'events_triggered' in self.player.combat_adapter_state

if len(self.player.combat_list) == 0 and not event_just_triggered:
    self._handle_victory()
    # ... return victory state
```

## How Events Work

Events like `Ch01PostRumblerRep` follow this pattern:

```python
class Ch01PostRumblerRep(Event):
    def check_combat_conditions(self):
        if len(self.player.combat_list) == 0:
            self.pass_conditions_to_process()  # Signals to process()

    def process(self, user_input=None):
        # Spawn new enemies
        new_enemies = [tile.spawn_npc("RockRumbler") for _ in range(2)]
        add_enemies_to_combat(self.player, new_enemies)
```

With the fix:
1. All initial enemies defeated → `combat_list` is empty
2. Event evaluation triggered → `check_combat_conditions()` detected empty list
3. Event's `process()` spawned new enemies → `combat_list` repopulated
4. Combat loop continues instead of declaring victory
5. Player fights fresh wave of reinforcements

## Testing
To verify the fix:

1. **Terminal Combat:**
   - Run game and trigger `Ch01PostRumblerRep` scene
   - Defeat initial Rock Rumblers
   - Observe new waves spawning instead of victory screen appearing immediately

2. **API Combat:**
   - Use API to engage in combat with events configured
   - Clear enemies and verify new waves spawn before victory endpoint returns

## Files Modified
- `src/combat.py` - Lines 247-261 (added final event evaluation)
- `src/api/combat_adapter.py`:
  - Lines 1252-1276 (new `_evaluate_combat_events()` method)
  - Lines 965-974 (modified victory check to call new method)
