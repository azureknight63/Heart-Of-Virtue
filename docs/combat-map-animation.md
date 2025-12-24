# Combat Map Beat-by-Beat Animation System

## Overview
The combat map now updates smoothly on every beat, displaying real-time changes to:
- Combatant positions (with smooth transitions)
- HP and fatigue levels (with animated arcs)
- Active move states (with colored glows)
- All other combat state changes

## Implementation Details

### Backend (Python)

#### 1. Beat State Capture (`src/api/combat_adapter.py`)
- Modified `_execute_move()` method to capture combat state at each beat
- Creates a `beat_states` array containing snapshots of the full combat state
- Each snapshot includes:
  - All combatant positions
  - HP and fatigue values
  - Current moves being executed
  - Combat log entries
- Returns `beat_states` in the API response

#### 2. Enhanced Serialization (`src/api/serializers/combat.py`)
- Added `fatigue` and `maxfatigue` fields to combatant serialization
- Added `current_move` serialization including:
  - Move name
  - Move category (for glow colors)
  - Move description
  - Current stage
- Position data includes x, y coordinates and facing direction

### Frontend (React)

#### 1. Beat Animation Controller (`Battlefield.jsx`)
- Detects when `combat.beat_states` is present in the response
- Implements interval-based animation:
  - Cycles through beat states at 750ms per beat
  - Updates `displayState` to show each beat's snapshot
  - Clears animation when complete
- Falls back to immediate update when no beat states present

#### 2. Smooth Position Transitions (`BattlefieldGrid.jsx`)
- Refactored to use absolute positioning overlay system
- Separates grid background from entity layer
- Entities positioned using percentage-based CSS:
  ```javascript
  left: `${(col / gridCols) * 100}%`
  top: `${(row / gridCols) * 100}%`
  ```
- CSS transitions on entity containers:
  ```javascript
  className="transition-all duration-500 ease-in-out will-change-[top,left]"
  ```

#### 3. HP/Fatigue Arc Animations (`CombatantMarker`)
- SVG paths use `strokeDasharray` to display HP/fatigue percentages
- Added CSS transitions to arc paths:
  ```javascript
  style={{ transition: 'stroke-dasharray 0.5s ease-in-out' }}
  ```
- Left arc (green): HP visualization
- Right arc (orange): Fatigue visualization

#### 4. Action Glow System
- Reads `current_move.category` from entity data
- Applies colored glow based on action type:
  - **Red**: Attack moves
  - **Blue**: Maneuver moves
  - **Purple**: Special moves
  - **Teal**: Supernatural moves
  - **White**: Miscellaneous moves
- Glow appears when combatant is charging/executing a move

## Animation Flow

1. **Player Action**: User selects a move in the frontend
2. **Backend Processing**: 
   - Move is executed beat-by-beat
   - State captured after each beat
   - All beat states returned in response
3. **Frontend Animation**:
   - Receives array of beat states
   - Displays first state immediately
   - Cycles through remaining states at 750ms intervals
   - Shows final state when animation completes
4. **Visual Updates**:
   - Positions smoothly transition (500ms CSS)
   - HP/Fatigue arcs smoothly animate (500ms CSS)
   - Glows appear/disappear based on active moves
   - Facing indicators rotate with combatants

## Performance Optimizations

- Uses `will-change` CSS property for GPU acceleration
- Absolute positioning prevents layout recalculation
- Interval cleanup prevents memory leaks
- Smooth 60fps animations via CSS transitions

## Data Flow

```
Backend (Python)
├── Combat beat loop
│   ├── Process moves
│   ├── Update positions
│   ├── Capture state snapshot
│   └── Add to beat_states array
└── Return response with beat_states

Frontend (React)
├── Receive combat response
├── Detect beat_states array
├── Start animation interval
│   ├── Update displayState
│   ├── Trigger CSS transitions
│   └── Advance to next beat
└── Complete animation
```

## Files Modified

### Backend
- `src/api/combat_adapter.py`: Beat state capture logic
- `src/api/serializers/combat.py`: Enhanced serialization with fatigue and current_move

### Frontend
- `frontend/src/components/Battlefield.jsx`: Beat animation controller
- `frontend/src/components/BattlefieldGrid.jsx`: Smooth positioning and transitions

