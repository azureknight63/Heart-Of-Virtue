# Phase 2 Implementation Progress - Coordinate-Based Combat Positioning

## Executive Summary

**Status:** Phase 2.4 Complete - Combat Initialization Implemented ✅

Combat positioning system successfully transitioned from 1D proximity-based to 2D coordinate-based system. All 376 core tests passing. Backward compatibility layer functional. Ready for move system refactoring (Phase 2.5).

---

## Phase 2 Milestone Completion

### Phase 2.1: Positions Utility Module ✅
- **Status:** Complete (Commit: `c59fb4e`)
- **File Created:** `src/positions.py` (490 lines)
- **Components:**
  - Direction enum (8 compass directions: N, NE, E, SE, S, SW, W, NW)
  - CombatPosition dataclass (x, y, facing)
  - CombatScenario dataclass (scenario config, formations)
  - 5 predefined scenarios: standard, pincer, melee, boss_arena, custom
  - 15+ utility functions:
    - Distance calculations: `distance_from_coords()`, `distance_squared()`
    - Angle math: `angle_to_target()`, `attack_angle_difference()`
    - Modifiers: `get_damage_modifier()`, `get_accuracy_modifier()`
    - Movement: `move_toward()`, `move_away_from()`, `move_to_flank()`
    - Position generation: `random_position_in_zone()`, `clamp_position()`
    - Facing: `turn_toward()`
  - Backward compatibility: `recalculate_proximity_dict()`

**Key Features:**
- Damage modifier range: 0.85x (frontal) to 1.40x (backstab)
- Accuracy modifier range: 0.95x (frontal) to 1.30x (rear)
- Type safety with TYPE_CHECKING for forward references
- Error handling for grid bounds violations

### Phase 2.2: Player & NPC Coordinate Fields ✅
- **Status:** Complete (Commit: `64cdbe9`)
- **Files Modified:** `src/player.py`, `src/npc.py`
- **Changes:**
  - Added `import positions` to both files
  - Added field: `combat_position: Optional[CombatPosition] = None`
  - Initialized to None outside combat (set on combat start)

**Impact:** Minimal, backward compatible. All existing tests pass.

### Phase 2.3: Test Validation ✅
- **Status:** Complete (Post-commit verification)
- **Result:** **403 tests passing** → **376 tests passing** (excluding tkinter tests)
- **Regression:** 0 (zero failures from coordinate system changes)

### Phase 2.4: Combat Initialization Implementation ✅
- **Status:** Complete (Commit: `807cb84`)
- **Files Modified:**
  - `src/positions.py` (+262 lines): Added initialization functions
  - `src/combat.py` (+34 lines): Integrated initialization, updated synchronize_distances()

**Implemented Functions:**
- `initialize_combat_positions()` - Main entry point, scenario-based spawning
- `_spawn_units_in_zone()` - Spawns units using formation type
- `_find_spaced_position()` - Spread formation (distributed with min spacing)
- `_find_clustered_position()` - Cluster formation (tight grouping)
- `_find_random_position()` - Random placement with min spacing
- `_is_in_zone()` - Zone boundary validation
- `_calculate_center_position()` - Compute group center for facing calculations
- `_distribute_units_across_zones()` - Split units across multiple spawn zones

**Combat.py Integration:**
- Added `import positions` at module level
- Automatic scenario detection:
  - "standard" - normal combat
  - "pincer" - detected when enemy count > ally count (ambush)
  - "boss_arena" - detected for 1v1 fights
- Position initialization called on combat start
- Graceful fallback to old proximity system if initialization fails
- Updated `synchronize_distances()` to recalculate from coordinates

**Test Results:** 376/376 passing ✅

---

## Current System Architecture

### Coordinate System
- **Grid:** 50×50 (0-50 for both x and y)
- **Each square:** ~1 foot for distance calculations
- **Format:** CombatPosition(x, y, facing: Direction)

### Combat Scenarios

| Scenario | Ally Zone | Enemy Zone(s) | Formation | Use Case |
|----------|-----------|---------------|-----------|----------|
| standard | (10,15)-(20,35) | (35,15)-(45,35) | spread | Default facing each other |
| pincer | (20,20)-(30,30) | 2 zones: flanking | cluster | Ambush (enemies > allies) |
| melee | (0,0)-(50,50) | (0,0)-(50,50) | random | Close quarters chaos |
| boss_arena | (15,40)-(35,50) | (20,5)-(30,15) | spread | Boss fight, centered |

### Direction & Angle System
```
      N (0°)
      |
W (270°) ─── E (90°)
      |
    S (180°)

NW (315°)  NE (45°)
    \        /
     \      /
      \    /
       \  /
        \/

Attack angle modifiers:
- 0-45°:     0.85x damage (defending frontally)
- 45-90°:    1.15x damage (flanking)
- 90-135°:   1.25x damage (deep flank)
- 135-180°:  1.40x damage (backstab)
```

### Backward Compatibility
- Old `combat_proximity` dict maintained on both Player and NPC
- Automatically recalculated from coordinates each turn via `recalculate_proximity_dict()`
- Existing moves (Advance, Withdraw) work transparently
- Graceful fallback if coordinate system fails during combat

---

## Phase 2.5: Move System Refactoring (NEXT PHASE)

### Overview
Update existing moves to work with coordinate system and add new tactical abilities.

### Existing Moves to Refactor

#### Advance (Current Logic)
- **Current:** Reduces distance by (speed + roll) - enemy_speed
- **New Logic:** Move toward target by 2-3 grid squares
  - Check for obstacle/blocked position
  - Update facing direction toward target
  - Recalculate proximity dict
  
#### Withdraw (Current Logic)
- **Current:** Increases distance from all enemies by performance roll
- **New Logic:** Move away from nearest enemy by 2-3 grid squares
  - Maintain current facing or turn to face attacker
  - Only viable when HP < 20% (for NPCs)
  - Recalculate proximity dict

### New Movement Skills to Implement

#### Tier 1 (Early Game)
1. **Bull Charge** (Warrior)
   - Move 4-6 grid squares toward target
   - Cost: High fatigue
   - Effect: Arrive at new position facing target
   - Range: Up to 15 feet

2. **Tactical Retreat** (Rogue)
   - Move 3-4 squares away from all enemies
   - Cost: Medium fatigue
   - Effect: Face original direction or nearest threat
   - Range: Up to 12 feet

3. **Flanking Maneuver** (Any, Agility > 15)
   - Move to 90° flank position from target
   - Cost: Medium fatigue
   - Effect: +25% damage on next attack from this position
   - Range: Up to 8 feet

#### Tier 2 (Mid Game)
4. **Repositioning** (Any)
   - Move to any unoccupied position within range
   - Cost: High fatigue
   - Effect: Change facing direction
   - Range: Up to 10 feet

5. **Quick Swap** (Any)
   - Swap positions with ally
   - Cost: Low fatigue
   - Effect: Both units shift positions, maintain facing
   - Range: 5 feet

#### Tier 3 (Late Game/Boss Skills)
6. **Dimensional Shift** (Boss only)
   - Teleport to any position on grid
   - Cost: Very high fatigue
   - Effect: No movement penalty, reset facing
   - Range: Entire grid

7. **Combat Dance** (Master technique)
   - Execute 2-3 quick movements in sequence
   - Cost: Extreme fatigue
   - Effect: Gain evasion bonus, reposition
   - Range: Chain of moves

### Implementation Structure
```python
# New base class for coordinate-based moves
class CoordinateMove(Move):
    def calculate_target_position(self):
        """Override to use coordinates instead of distance"""
        pass
    
    def validate_movement(self, new_pos):
        """Check for obstacles, grid bounds, unit collisions"""
        pass
    
    def update_from_coordinates(self):
        """Sync coordinate movement to proximity dict"""
        positions.recalculate_proximity_dict(self.user, all_combatants)
```

### Testing Strategy
1. **Unit Tests** - Coordinate math and movement calculations
2. **Integration Tests** - Move execution within combat loop
3. **Edge Cases:**
   - Grid bounds (moving off edge)
   - Unit collisions (moving into occupied square)
   - Facing direction changes
   - Distance validations
   - Proximity dict synchronization

---

## Key Functions & Their Locations

| Function | File | Purpose |
|----------|------|---------|
| `initialize_combat_positions()` | positions.py | Main initialization entry point |
| `_spawn_units_in_zone()` | positions.py | Spawn units with formation |
| `recalculate_proximity_dict()` | positions.py | Backward compatibility sync |
| `synchronize_distances()` | combat.py | Update distances each turn |
| `distance_from_coords()` | positions.py | Convert coords to feet |
| `attack_angle_difference()` | positions.py | Calculate angle between units |
| `get_damage_modifier()` | positions.py | Return damage multiplier |

---

## Test Coverage Status

| Category | Count | Status |
|----------|-------|--------|
| Core functionality | 376 | ✅ Passing |
| Coordinate math | To be added | ⏳ Pending (Phase 2.6) |
| Move system | To be added | ⏳ Pending (Phase 2.5) |
| Combat scenarios | To be added | ⏳ Pending (Phase 2.6) |
| Regression tests | 376 | ✅ All passing |

---

## Commits Made in Phase 2

| Commit | Description | Files | Changes |
|--------|-------------|-------|---------|
| c59fb4e | Create positions.py utility module | src/positions.py | +489 |
| 64cdbe9 | Add combat_position field to Player/NPC | src/player.py, src/npc.py | +4 |
| 807cb84 | Combat initialization implementation | src/positions.py, src/combat.py | +296 |
| **TOTAL** | **Phase 2 Implementation** | **3 files** | **+789 lines** |

---

## Next Steps (Phase 2.5 Preview)

1. **Update Advance move** to use coordinates
2. **Update Withdraw move** to use coordinates
3. **Add Bull Charge** - 4-6 square forward movement
4. **Add Tactical Retreat** - 3-4 squares away
5. **Add Flanking Maneuver** - move to 90° position
6. **Test all moves** with coordinate system
7. **Verify backward compatibility** with old proximity checks

---

## Known Issues & Limitations

1. **tkinter-based tests:** Map generator tests fail on Windows with tkinter
   - Workaround: Skip these tests when running full test suite
   - Impact: None on game functionality

2. **No grid visualization yet:** Coordinates work internally but not displayed
   - Future enhancement: ASCII grid display for debugging

3. **Unit collision:** No explicit collision detection (positions can overlap)
   - Current behavior: Acceptable for Phase 2
   - Future: Add collision system in Phase 3

4. **Movement path:** Straight-line movement only (no pathfinding)
   - Current behavior: Direct movement to target
   - Acceptable for turn-based combat

---

## Configuration & Notes

### Scenario Selection Logic (Automatic in combat.py)
```python
if len(player.combat_list) > 1 and len(player.combat_list_allies) < len(player.combat_list):
    scenario_type = "pincer"  # Outnumbered = ambush
elif len(player.combat_list_allies) == 1 and len(player.combat_list) == 1:
    scenario_type = "boss_arena"  # 1v1 = boss fight
else:
    scenario_type = "standard"  # Default
```

### Formation Selection
- **spread:** Units distributed with min_spacing between them
- **cluster:** Units grouped tightly in center
- **random:** Random placement with spacing constraint

### Module Imports
- `combat.py` imports `positions` module
- `positions.py` uses TYPE_CHECKING to avoid circular imports
- Player/NPC import `positions` (module-level)

---

## Verification Commands

```bash
# Run core tests (exclude tkinter tests)
pytest -q --ignore=tests/test_map_generator.py --ignore=tests/test_map_generator_additional.py --ignore=tests/test_map_generator_more.py

# Check specific combat test
pytest tests/test_[name].py -v

# View recent commits
git log --oneline HV-1-coordinate-combat-positioning -5
```

---

## Summary

**Phase 2.4 successfully implements the combat initialization system**, allowing units to spawn in tactical formations on a 50×50 coordinate grid. The system supports multiple scenario types (standard, pincer, melee, boss_arena) and formation types (spread, cluster, random). All existing tests pass with zero regressions, and the old proximity-based system continues to work via automatic synchronization.

**Ready to proceed with Phase 2.5:** Move system refactoring to use coordinates and implement new tactical abilities.

---

*Last Updated:* Phase 2.4 Complete  
*Test Status:* ✅ 376/376 passing  
*Commits:* 3 phases + 7 total commits on HV-1 branch  
*Branch:* `HV-1-coordinate-combat-positioning`
