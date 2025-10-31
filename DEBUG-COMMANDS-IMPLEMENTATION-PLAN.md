# Debug Commands Implementation Plan

**Date:** October 31, 2025  
**Status:** Design Phase (Pre-Implementation)  
**Related:** HV-1 Coordinate Combat Positioning, Phase 4 Testing  

---

## Overview

Debug commands should be **always available during combat when `debug_mode = True`**, rather than configured per-command via INI file. This provides a unified, always-present interface for testers to inspect and control the coordinate positioning system.

---

## Design Principles

1. **Always On in Debug Mode:** If `player.testing_mode = True` or `player.debug_mode = True`, debug menu is accessible
2. **Non-Intrusive:** Debug commands accessible without disrupting normal combat flow
3. **Real-Time Data:** All commands query current game state (positions, calculations, AI decisions)
4. **Extensible:** New debug commands can be added to one central place
5. **Logged:** All debug output goes to `combat_testing_phase4.log` when enabled

---

## Architecture

### Core Components

#### 1. Debug Manager Class
**File:** `src/debug_manager.py` (new)

```python
class DebugManager:
    """Manages debug commands and output during combat testing."""
    
    def __init__(self, player, universe):
        self.player = player
        self.universe = universe
        self.enabled = player.debug_mode
        self.log_file = "combat_testing_phase4.log"
        self.commands = self._register_commands()
    
    def _register_commands(self):
        """Register all available debug commands."""
        return {
            'show_positions': self.show_positions,
            'show_modifiers': self.show_modifiers,
            'show_calculations': self.show_calculations,
            'force_flank': self.force_flank,
            'force_retreat': self.force_retreat,
            'restart_combat': self.restart_combat,
            'instant_win': self.instant_win,
            'toggle_logging': self.toggle_logging,
        }
    
    def show_debug_menu(self):
        """Display debug command menu during combat."""
        pass
    
    def execute_command(self, command_name, *args):
        """Execute a debug command by name."""
        pass
    
    def log(self, message):
        """Write to debug log file."""
        pass
```

#### 2. Combat Integration
**File:** `src/combat.py` (modify)

```python
def combat(...):
    # ... existing combat setup ...
    debug_mgr = None
    if player.debug_mode:
        from debug_manager import DebugManager
        debug_mgr = DebugManager(player, player.universe)
    
    while combat_active:
        # ... existing combat loop ...
        
        # After displaying action menu
        if debug_mgr and player_turn:
            action = get_player_action(debug_mgr)  # Pass debug manager
        
        # ... rest of combat ...
```

---

## Debug Commands Specification

### Command: `show_positions`

**Purpose:** Display current coordinates and facing for all combat units

**Implementation:**
- Query `player.combat_position` (if exists) or calculate from proximity dict
- Query each NPC's `combat_position`
- Calculate distance from player using `positions.distance_from_coords()`
- Display in table format

**Output Format:**
```
[Debug] Unit Positions:
  Jean Claire      | X: 25 | Y: 15 | Facing: SE  | Distance: 0.0 ft
  CaveBat_1        | X: 28 | Y: 22 | Facing: NW  | Distance: 9.8 ft
  CaveBat_2        | X: 20 | Y: 18 | Facing: NE  | Distance: 5.0 ft
```

**Code Location:** `debug_manager.py::show_positions()`  
**Dependencies:** `positions.py`, NPC objects, player position

---

### Command: `show_modifiers`

**Purpose:** Display damage/accuracy modifiers for next attack based on positioning

**Implementation:**
- Get player's current facing direction
- Get target (nearest enemy or selected)
- Calculate attack angle using `positions.attack_angle_difference()`
- Get damage modifier via `positions.get_damage_modifier(angle_diff)`
- Get accuracy modifier via `positions.get_accuracy_modifier(angle_diff)`
- Display calculation breakdown

**Output Format:**
```
[Debug] Attack Modifiers (vs CaveBat_1):
  Attack Angle: 45°
  Angle Range: Flank (45-90°)
  Damage Modifier: 1.15x (+15%)
  Accuracy Modifier: 1.10x (+10%)
  Base Damage: 12 → Modified: 13.8
```

**Code Location:** `debug_manager.py::show_modifiers()`  
**Dependencies:** `positions.py`, player facing, target position

---

### Command: `show_calculations`

**Purpose:** Display detailed coordinate math for verification

**Implementation:**
- Show player position and facing
- Show target position and facing
- Calculate and show:
  - Distance (Euclidean)
  - Distance squared
  - Attack angle (0-360°)
  - Angle difference from target
  - Formatted direction name (N, NE, E, etc.)

**Output Format:**
```
[Debug] Coordinate Calculations:
  Player Position: (25, 15) Facing: SE
  Target (CaveBat_1): (28, 22) Facing: NW
  
  Distance Calculation:
    Δx = 28 - 25 = 3
    Δy = 22 - 15 = 7
    Distance = √(3² + 7²) = √58 = 7.6 ft
  
  Angle Calculation:
    atan2(7, 3) = 66.8°
    Angle Range: Flank (45-90°)
```

**Code Location:** `debug_manager.py::show_calculations()`  
**Dependencies:** `positions.py` (math functions), both unit positions

---

### Command: `force_flank`

**Purpose:** Force target NPC to attempt flanking move on next turn

**Implementation:**
- Display list of enemies with indices
- Get user selection (or target nearest)
- Set NPC's `forced_action = 'flank'` flag
- NPC AI sees flag and executes `FlankingManeuver` instead of normal decision
- Log decision with coordinates

**Output Format:**
```
[Debug] Forcing NPC Action:
  Target: CaveBat_1 at (28, 22)
  Action: FlankingManeuver
  Reason: Forced by debug command
```

**Code Location:** `debug_manager.py::force_flank()`, `npc.py` (read `forced_action` flag)  
**Dependencies:** NPC list, combat state

---

### Command: `force_retreat`

**Purpose:** Force target NPC to retreat on next turn

**Implementation:**
- Similar to `force_flank`
- Set `forced_action = 'retreat'`
- NPC executes `TacticalRetreat` instead of normal decision
- Verify retreat path is available

**Output Format:**
```
[Debug] Forcing NPC Action:
  Target: CaveBat_2 at (20, 18)
  Action: TacticalRetreat
  Reason: Forced by debug command
```

**Code Location:** `debug_manager.py::force_retreat()`, `npc.py`  
**Dependencies:** NPC list, combat state, grid validation

---

### Command: `show_ai_decision`

**Purpose:** Display NPC AI's current decision-making process (for selected enemy)

**Implementation:**
- Show which NPC is making decision
- Display options being considered (Advance, Withdraw, Flank, etc.)
- Show scores/weights for each option
- Show which option won
- Show positioning rationale

**Output Format:**
```
[Debug] NPC AI Decision (CaveBat_1):
  Current Position: (28, 22)
  Distance to Player: 9.8 ft
  Player Health: 75%
  
  Move Options Evaluated:
    Advance:              Score 8/10 (good distance, flank opportunity)
    Withdraw:             Score 3/10 (player not threatening)
    TacticalRetreat:      Score 2/10 (health not critical)
    FlankingManeuver:     Score 6/10 (angle 75°, could improve)
  
  Selected Action: Advance (move 3 squares)
  Reason: Closes distance, improves flanking angle
```

**Code Location:** `debug_manager.py::show_ai_decision()`, `npc.py` (expose decision logic)  
**Dependencies:** NPC AI evaluation, scoring system

---

### Command: `restart_combat`

**Purpose:** Reset current combat encounter with same scenario/NPCs

**Implementation:**
- Reset player HP to max
- Reset all NPC HP to max
- Reinitialize all combat_position values
- Clear status effects
- Return to combat start state

**Output Format:**
```
[Debug] Combat Restarted:
  Scenario: Standard Formation
  Player HP: 100/100
  Enemies: CaveBat_1 (8/8), CaveBat_2 (8/8), CaveBat_3 (8/8)
  Positions reinitialized
```

**Code Location:** `debug_manager.py::restart_combat()`, `combat.py`  
**Dependencies:** Combat initialization functions, `positions.py`

---

### Command: `instant_win`

**Purpose:** Kill all enemies immediately (victory condition)

**Implementation:**
- Set all NPC HP to 0
- Remove all NPCs from combat_list
- Trigger victory condition
- Show victory screen with damage/stats summary

**Output Format:**
```
[Debug] Instant Victory:
  All enemies defeated
  Combat ending...
```

**Code Location:** `debug_manager.py::instant_win()`, `combat.py`  
**Dependencies:** Combat end conditions, victory logic

---

### Command: `toggle_logging`

**Purpose:** Enable/disable detailed position logging during combat

**Implementation:**
- Toggle flag that controls debug output verbosity
- When ON: log each move, distance calculation, angle calculation, modifier application
- When OFF: only essential combat messages
- Write current state to log file

**Output Format:**
```
[Debug] Logging Toggled: ON
  Output destination: combat_testing_phase4.log
  Logging: positions, distances, angles, modifiers, NPC decisions
```

**Code Location:** `debug_manager.py::toggle_logging()`  
**Dependencies:** Logger, config flags

---

## Integration Points

### 1. Combat Loop (`src/combat.py`)

**Where:** Main combat loop, after action display, before player input

```python
def combat(...):
    debug_mgr = DebugManager(player, player.universe) if player.debug_mode else None
    
    while combat_active:
        # Display current state
        display_combat_state()
        
        # Show action menu
        if debug_mgr:
            action = display_action_menu_with_debug(debug_mgr)
        else:
            action = display_action_menu()
        
        # If debug command selected, execute it
        if isinstance(action, DebugCommand):
            debug_mgr.execute_command(action)
            continue  # Don't advance combat, stay for next action
        
        # Execute normal action
        execute_action(action)
```

### 2. NPC AI (`src/npc.py`)

**Where:** NPC decision-making

```python
def choose_action(self, combat_state):
    # Check if debug force_action is set
    if hasattr(self, 'forced_action') and self.forced_action:
        action = self.forced_action
        self.forced_action = None  # Clear flag
        return action
    
    # Normal AI decision
    return self.ai_decide(combat_state)
```

### 3. Game Startup (`src/game.py`)

**Where:** Config reading and debug mode setup

```python
# ... existing config read ...
debug_mode = config.getboolean('game', 'debug_mode', fallback=False)
player.debug_mode = debug_mode
player.universe.debug_mode = debug_mode
```

---

## Menu Interface

### Option A: Submenu Approach
Debug commands available via `D` key from action menu:

```
=== COMBAT ===
Jean Claire | HP: 100/100

1. Attack
2. Move
3. Defend
4. [D] Debug Menu      ← Press D here
5. Wait
6. Cancel

Select action:
```

Pressing `D` shows:
```
=== DEBUG COMMANDS ===
1. Show Positions       [p]
2. Show Modifiers       [m]
3. Show Calculations    [c]
4. Force Flank          [f]
5. Force Retreat        [r]
6. Show AI Decision     [a]
7. Restart Combat       [R]
8. Instant Win          [w]
9. Toggle Logging       [l]
10. Return to Actions   [Escape]

Select command:
```

### Option B: Hotkey Approach
Debug commands accessible via global hotkey regardless of menu state:

- Press `Ctrl+D` anytime → Shows debug menu overlay
- Doesn't interrupt current menu
- Debug menu appears as side panel

**Recommendation:** Option A (submenu) is less disruptive and integrates cleanly with existing action menu.

---

## Log Output Format

**File:** `combat_testing_phase4.log`

```
[2025-10-31 14:23:45] === Combat Started ===
[2025-10-31 14:23:45] Scenario: Standard Formation
[2025-10-31 14:23:45] Player Position: (25, 15) Facing: SE
[2025-10-31 14:23:45] Enemy Positions: 
  CaveBat_1: (28, 22) Facing: NW | Distance: 9.8 ft
  CaveBat_2: (20, 18) Facing: NE | Distance: 5.0 ft

[2025-10-31 14:23:52] [DEBUG] show_positions executed by player
[2025-10-31 14:23:52] Unit Positions:
  ...

[2025-10-31 14:24:15] Jean Claire attacks CaveBat_1
[2025-10-31 14:24:15] Attack Angle: 45° | Damage Mod: 1.15x | Accuracy Mod: 1.10x
[2025-10-31 14:24:15] Base Damage: 12 | Modified: 13.8
```

---

## Success Criteria

✅ **Design Phase Complete When:**
- Debug commands specified with clear purpose and output
- Integration points identified in game code
- Menu interface designed
- Log format specified
- No INI configuration required per-command
- Commands always available in debug mode
- Ready for implementation

---

## Implementation Phases (Future)

**Phase 1:** Create `debug_manager.py` with command registry  
**Phase 2:** Integrate with `combat.py` and display menu  
**Phase 3:** Implement individual commands  
**Phase 4:** Add NPC AI decision exposure and logging  
**Phase 5:** Test all commands during Phase 4 manual testing  

---

**Document Status:** Ready for Implementation  
**Next Step:** Begin Phase 1 implementation of `debug_manager.py`
