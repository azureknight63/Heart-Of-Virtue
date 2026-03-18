# Combat System Architecture

## Current State

The game has TWO combat systems:

1. **Terminal Combat** (`src/combat.py`): Full-featured turn-based system with:
   - Beat-based turns (granular timing)
   - Complex move system with casting/targeting
   - Heat combo multiplier
   - Distance/positioning mechanics
   - Status effects
   - NPC AI
   - Interactive prompts for player input

2. **API Combat** (`src/api/services/game_service.py`): Simplified system with:
   - Basic turn order
   - Simple damage calculations
   - Combat log
   - **Problem**: Doesn't use the actual game mechanics!

## The Problem

The API is reimplementing combat logic instead of using the existing robust system. This leads to:
- Duplicate code
- Inconsistent mechanics between terminal and web versions
- Missing features (heat, positioning, complex moves, etc.)
- Maintenance burden

## The Solution

**Adapt the existing combat system for API use** instead of reimplementing it.

### Architecture Changes Needed

#### 1. Make Combat Engine API-Friendly

The current `combat()` function in `src/combat.py` is designed for terminal interaction:
- Uses `input()` for player choices
- Uses `print()` for output
- Runs in a blocking loop
- Manages its own window/display

For API use, we need to:
- **Capture all print statements** into a combat log
- **Replace input() calls** with state-based command processing
- **Make it stateful** - save combat state between API calls
- **Return control** after each player action instead of looping

#### 2. Combat State Management

Store in player session:
```python
player.combat_state = {
    "beat": 0,
    "awaiting_input": True,
    "input_type": "move_selection",  # or "target_selection", "direction_selection"
    "available_moves": [...],
    "available_targets": [...],
    "combat_log": [...],
    "battlefield_state": {...}
}
```

#### 3. API Flow

```
Frontend                Backend
   |                       |
   |-- POST /combat/move --|
   |   {move_id: 2}        |
   |                       |---> Execute move
   |                       |---> Process NPC turns
   |                       |---> Update combat state
   |                       |---> Capture output to log
   |<-- Combat State ------|
   |   {log, state, ...}   |
```

### Implementation Plan

1. **Create `ApiCombatAdapter`** class that wraps the existing combat logic
2. **Refactor combat() function** to be step-based instead of loop-based
3. **Implement output capture** for combat log
4. **Replace blocking input** with state-based command queue
5. **Update API routes** to use the adapted combat system

### Benefits

- ✅ Single source of truth for combat mechanics
- ✅ Terminal and web versions have identical gameplay
- ✅ All features available in both versions
- ✅ Easier to maintain and extend
- ✅ Proper integration with existing move/state/positioning systems

## Next Steps

1. Review and approve this architecture
2. Create `ApiCombatAdapter` class
3. Refactor `combat()` to support step-based execution
4. Update API routes to use new adapter
5. Test combat flow end-to-end

