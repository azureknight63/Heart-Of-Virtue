# UAT: Combat with Coordinate Grid System (HV-1)

**Date**: October 31, 2025  
**Branch**: HV-1-coordinate-combat-positioning  
**Feature**: Coordinate-based combat positioning system  
**Scope**: All player and NPC moves affected by 2D coordinate positioning

---

## Overview

This UAT validates that the new coordinate-based combat system works correctly with all combat moves. The old 1D distance system has been replaced with a 2D grid (0-50 x 0-50), with 8-directional facing and sophisticated positioning mechanics.

---

## Test Environment Setup

### Configuration
```bash
# Use the Phase 4 testing configuration
$env:CONFIG_FILE='config_phase4_testing.ini'
python src/game.py
```

### Expected Coordinate System
- Grid: 50×50 (coordinates 0-50 for X and Y)
- Directions: N, NE, E, SE, S, SW, W, NW (8-point compass)
- Distance: Euclidean distance in feet (1 foot ≈ 1 grid square)
- Max diagonal distance: ~70.7 feet

---

## Player Moves - Coordinate System Tests

### 1. CHECK Move - Coordinate Display
**Test ID**: UAT-CHECK-001

**Objective**: Verify Check move displays coordinate-based information

**Steps**:
1. Start combat: `spawn npc slime count=1`
2. Enemy enters combat automatically
3. Select action 0: Check

**Expected Results**:
- ✅ Displays enemy position: `(x, y)` format (e.g., `(22, 5)`)
- ✅ Shows facing direction: N, NE, E, SE, S, SW, W, or NW
- ✅ Shows distance in feet (converted from coordinates)
- ✅ Shows relative positioning: "front", "flank", or "rear"
- ✅ Color coded: Red (front), Yellow (flank), Green (rear)
- ✅ Shows ally positions if present

**Example Output**:
```
Jean checks his surroundings.
Slime Nuthamekanre at (22, 5) facing N is 35 ft away (rear, N-facing)
```

---

### 2. ADVANCE Move - Distance Reduction
**Test ID**: UAT-ADV-001

**Objective**: Verify Advance move shows up when viable and reduces distance

**Steps**:
1. Start combat: `spawn npc slime count=1`
2. Select action 0: Check (note the initial distance)
3. Select action 4: Advance (or whatever number it shows)
4. Wait for move execution
5. Select action 0: Check again

**Expected Results**:
- ✅ Advance shows in move list when enemy > 1 ft away
- ✅ Move executes with message: `Jean advances on Slime...`
- ✅ Distance reduced after move (by 2-4 squares)
- ✅ Player faces target after movement
- ✅ New position within grid bounds (0-50)

**Boundary Test (UAT-ADV-002)**:
1. Advance a player already at position (50, 50)
2. Try advancing toward enemy outside grid
3. Position should clamp to max 50

---

### 3. WITHDRAW Move - Safe Retreat
**Test ID**: UAT-WITH-001

**Objective**: Verify Withdraw move moves away from nearest threat

**Steps**:
1. Start combat: `spawn npc slime count=2`
2. Select action 0: Check (note positions)
3. Select action 3: Withdraw
4. Wait for move execution
5. Select action 0: Check again

**Expected Results**:
- ✅ Withdraw available when enemies present
- ✅ Move executes: `Jean attempts to fall back...`
- ✅ Distance from nearest enemy increased (by 2-3 squares)
- ✅ Player maintains defensive facing (toward nearest enemy)
- ✅ Can retreat to edge of grid without error

**Boundary Test (UAT-WITH-002)**:
1. Position player at (0, 0)
2. Execute Withdraw
3. Should handle boundary gracefully (no crash)

---

### 4. BULL CHARGE Move - Aggressive Advance
**Test ID**: UAT-BULL-001

**Objective**: Verify BullCharge moves 4-6 squares toward target

**Steps**:
1. Start combat: `spawn npc slime count=1` (at distance > 3 ft)
2. Select action showing "Bull Charge"
3. Wait for execution
4. Select action 0: Check

**Expected Results**:
- ✅ Move only viable when 3-20 feet from target
- ✅ Shows in move menu: `Bull Charge`
- ✅ Executes with message: `Jean charges at Slime...`
- ✅ Moves 4-6 squares toward target
- ✅ Reduces distance significantly (more than Advance)
- ✅ Auto-faces target

---

### 5. TACTICAL RETREAT Move - Coordinated Withdrawal
**Test ID**: UAT-TACT-001

**Objective**: Verify TacticalRetreat moves 3-4 squares defensively

**Steps**:
1. Start combat: `spawn npc slime count=1`
2. Get close (within 10 feet)
3. Select action showing "Tactical Retreat"
4. Wait for execution
5. Select action 0: Check

**Expected Results**:
- ✅ Always viable in combat (no range requirements)
- ✅ Shows in move menu: `Tactical Retreat ||| F: 3`
- ✅ Executes: `Jean executes a tactical retreat...`
- ✅ Moves 3-4 squares away
- ✅ Faces threat (defensive positioning)
- ✅ Uses 3 fatigue cost

---

### 6. FLANKING MANEUVER Move - Positional Advantage
**Test ID**: UAT-FLANK-001

**Objective**: Verify FlankingManeuver positions perpendicular to target

**Steps**:
1. Start combat: `spawn npc slime count=1` (at 5-15 feet)
2. Select action showing "Flanking Maneuver"
3. Wait for execution
4. Select action 0: Check (note the angle description)

**Expected Results**:
- ✅ Only viable when 3-15 feet from target
- ✅ Shows in move menu (if eligible)
- ✅ Moves perpendicular to target's facing
- ✅ Positions 2-4 squares away from target
- ✅ Results in "flank" or "rear" positioning for next attack
- ✅ Shows in Check output: `(flank)` or `(rear)` instead of `(front)`

**Damage Bonus Test (UAT-FLANK-002)**:
1. Use FlankingManeuver to position at flank
2. Attack target
3. Damage output should be higher than frontal attack (+15-25% bonus)

---

### 7. WAIT Move - Beats Management
**Test ID**: UAT-WAIT-001

**Objective**: Verify Wait move doesn't affect positioning

**Steps**:
1. Start combat: `spawn npc slime count=1`
2. Select action 1: Wait
3. Input: 5 (beats to wait)
4. Select action 0: Check

**Expected Results**:
- ✅ Player position unchanged after wait
- ✅ Beat counter advances correctly
- ✅ No distance changes
- ✅ Fatigue unchanged

---

## NPC Moves - Coordinate System Tests

### 8. NPC Advance Move
**Test ID**: UAT-NPC-ADV-001

**Objective**: Verify NPCs use coordinate-based Advance

**Steps**:
1. Start combat: `spawn npc slime count=1`
2. Get far away (40+ feet)
3. Check enemy moves toward you
4. Select action 0: Check multiple times to observe

**Expected Results**:
- ✅ Enemy closes distance (2-4 squares per turn)
- ✅ Enemy auto-faces player
- ✅ Distance shown in Check decreases over time
- ✅ NPC doesn't go out of bounds
- ✅ Debug output shows: `[AI DEBUG] Slime: Selected Advance`

---

### 9. NPC Withdraw Move
**Test ID**: UAT-NPC-WITH-001

**Objective**: Verify NPCs withdraw intelligently

**Steps**:
1. Start combat with low HP enemy: `spawn npc slime count=1`
2. Damage enemy significantly
3. Observe if enemy retreats
4. Check positioning to confirm distance increased

**Expected Results**:
- ✅ Wounded NPCs may choose Withdraw
- ✅ Distance from player increases
- ✅ Enemy maintains defensive stance
- ✅ Doesn't retreat off grid boundaries

---

### 10. NPC Attack Positioning
**Test ID**: UAT-NPC-ATK-001

**Objective**: Verify NPC attacks from current position

**Steps**:
1. Start combat: `spawn npc slime count=1`
2. Let enemy close to melee range (~5 feet)
3. Let enemy attack
4. Observe positioning after attack

**Expected Results**:
- ✅ Enemy doesn't reposition during attack
- ✅ Attack resolves from current coordinates
- ✅ No out-of-bounds positioning
- ✅ Distance shown in Check reflects actual position

---

## Integration Tests

### 11. Multi-Enemy Combat - Positioning
**Test ID**: UAT-MULTI-001

**Objective**: Verify multiple enemies position independently

**Steps**:
1. Start combat: `spawn npc slime count=3`
2. Select action 0: Check
3. Observe all three enemy positions
4. Repeat Check over multiple turns

**Expected Results**:
- ✅ All three enemies have different coordinates
- ✅ Each with own facing direction
- ✅ Distances shown correctly for each
- ✅ No collision/overlap (spacing maintained)
- ✅ All within grid bounds (0-50)

---

### 12. Scenario Types - Standard Layout
**Test ID**: UAT-SCENARIO-001

**Objective**: Verify Standard scenario initialization

**Steps**:
1. Start combat against single slime
2. Select Check immediately
3. Observe enemy and player positions
4. Note: Player should be around (25, 10-15), Enemy around (25, 40-45)

**Expected Results**:
- ✅ Player and enemy on opposite sides of grid
- ✅ Facing toward each other initially
- ✅ Distance should be 30-35 feet
- ✅ Both within bounds (0-50)

---

### 13. Scenario Types - Pincer Ambush Layout
**Test ID**: UAT-SCENARIO-002

**Objective**: Verify Pincer scenario (more enemies than allies)

**Steps**:
1. Start combat with multiple strong enemies
2. Check positioning
3. Observe if enemies flank from multiple angles

**Expected Results**:
- ✅ Enemies spawn in flanking positions
- ✅ Some enemies at angles (not just front)
- ✅ Check shows enemies at various facing directions
- ✅ Creates tactical challenge

---

### 14. Backward Compatibility - Legacy Distance
**Test ID**: UAT-COMPAT-001

**Objective**: Verify system falls back gracefully if coordinates unavailable

**Steps**:
1. Start combat
2. Check that all distances shown convert properly
3. System should internally convert coordinates to feet

**Expected Results**:
- ✅ No crashes even if coordinates missing
- ✅ Distance displayed is always in feet (converted from coordinates)
- ✅ Legacy proximity dict still works
- ✅ Coordinate fallback transparent to player

---

## Edge Cases & Boundary Tests

### 15. Grid Boundary - Corner Positions
**Test ID**: UAT-EDGE-001

**Objective**: Verify movements work at grid corners

**Steps**:
1. Force player to (0, 0) using debug
2. Try Advance toward (0, 50)
3. Try Withdraw
4. Check position doesn't go negative

**Expected Results**:
- ✅ No negative coordinates
- ✅ No values > 50
- ✅ Moves clamp correctly
- ✅ All distance calculations valid

---

### 16. Diagonal Movement - All 8 Directions
**Test ID**: UAT-EDGE-002

**Objective**: Verify movements work in all 8 compass directions

**Steps**:
1. Run through multiple combats
2. Observe that enemies and player move in all directions
3. Use Check to verify facing values: N, NE, E, SE, S, SW, W, NW

**Expected Results**:
- ✅ All 8 directions appear in Check output
- ✅ Movements smooth in all directions
- ✅ Diagonal movement works (NE, SE, SW, NW)
- ✅ No directional biases

---

### 17. Dead Target Handling
**Test ID**: UAT-EDGE-003

**Objective**: Verify moves handle dead targets gracefully

**Steps**:
1. Start combat with 2 enemies
2. Kill first enemy with attack
3. Try to Advance on dead enemy
4. System should select new target

**Expected Results**:
- ✅ Advance cancels if target dies before execution
- ✅ NPC removes dead enemies from combat_proximity
- ✅ Check doesn't show dead enemies
- ✅ No crashes referencing dead units

---

## Performance & Stability Tests

### 18. Performance - Many Units Combat
**Test ID**: UAT-PERF-001

**Objective**: Verify system handles 20+ units efficiently

**Steps**:
1. Start combat: `spawn npc slime count=10`
2. Perform actions repeatedly
3. Measure response time

**Expected Results**:
- ✅ Check displays all 10 enemies instantly
- ✅ Move selection responsive (< 1 second)
- ✅ Moves execute quickly (< 2 seconds)
- ✅ No memory leaks (test for 10+ rounds)

---

### 19. Stability - Long Combat Session
**Test ID**: UAT-STAB-001

**Objective**: Verify system stable over extended combat

**Steps**:
1. Start combat
2. Run 50+ combat rounds
3. Monitor for errors/crashes
4. Check final positioning valid

**Expected Results**:
- ✅ No crashes after 50 rounds
- ✅ All positions remain valid
- ✅ No coordinate overflow
- ✅ Fatigue/beats tracking accurate

---

## Logging & Debug Tests

### 20. Combat Move Logging
**Test ID**: UAT-LOG-001

**Objective**: Verify moves are logged correctly

**Steps**:
1. Enable `debug_ai_decisions = True` in config
2. Run several combats
3. Check `combat_testing_phase4.log` file

**Expected Results**:
- ✅ Player moves logged: `log_combat_move()`
- ✅ NPC moves logged with debug: `[AI DEBUG] NPC: Selected Move`
- ✅ Distance calculations logged: `log_distance_calculation()`
- ✅ All logs timestamped and readable

---

### 21. Distance Calculation Logging
**Test ID**: UAT-LOG-002

**Objective**: Verify distance calculations logged

**Steps**:
1. Enable `log_distance_calculations = True`
2. Run one combat round
3. Check combat_testing_phase4.log

**Expected Results**:
- ✅ Each unit's distances to other units logged
- ✅ Format: `distance_calculation: Unit1 to Unit2: X feet`
- ✅ All combatants covered (player, allies, enemies)

---

## Test Execution Checklist

- [ ] UAT-CHECK-001: Check move displays coordinates
- [ ] UAT-ADV-001: Advance reduces distance
- [ ] UAT-ADV-002: Advance boundary clamping
- [ ] UAT-WITH-001: Withdraw safe retreat
- [ ] UAT-WITH-002: Withdraw boundary handling
- [ ] UAT-BULL-001: BullCharge aggressive move
- [ ] UAT-TACT-001: TacticalRetreat defensive
- [ ] UAT-FLANK-001: FlankingManeuver perpendicular
- [ ] UAT-FLANK-002: FlankingManeuver damage bonus
- [ ] UAT-WAIT-001: Wait positioning unchanged
- [ ] UAT-NPC-ADV-001: NPC Advance
- [ ] UAT-NPC-WITH-001: NPC Withdraw
- [ ] UAT-NPC-ATK-001: NPC Attack positioning
- [ ] UAT-MULTI-001: Multi-enemy positioning
- [ ] UAT-SCENARIO-001: Standard scenario layout
- [ ] UAT-SCENARIO-002: Pincer scenario layout
- [ ] UAT-COMPAT-001: Backward compatibility
- [ ] UAT-EDGE-001: Grid boundary corners
- [ ] UAT-EDGE-002: 8-directional movement
- [ ] UAT-EDGE-003: Dead target handling
- [ ] UAT-PERF-001: Many units performance
- [ ] UAT-STAB-001: Long session stability
- [ ] UAT-LOG-001: Combat move logging
- [ ] UAT-LOG-002: Distance calculation logging

---

## Success Criteria

**Overall Success**: All 24 test cases PASS

**Critical Tests** (must pass):
- UAT-CHECK-001: Coordinate display
- UAT-ADV-001: Advance function
- UAT-WITH-001: Withdraw function
- UAT-FLANK-001: Flanking maneuver
- UAT-MULTI-001: Multi-enemy coordination
- UAT-EDGE-003: Dead target handling

**Quality Gates**:
- ✅ Zero crashes in any test scenario
- ✅ All coordinates within valid bounds (0-50)
- ✅ All moves execute expected behavior
- ✅ Backward compatibility maintained
- ✅ Performance acceptable (< 2s per action)

---

## Known Limitations

1. **Random Positioning**: Enemy spawn positions use randomization, so exact coordinates vary
2. **Speed-based Movement**: Distance moved by Advance/BullCharge depends on speed stats
3. **AI Decision**: NPC move selection is based on AI, may not always choose same move
4. **Fatigue**: Some moves require fatigue; availability depends on current fatigue level

---

## Pass/Fail Report Template

```
TEST CASE: [UAT-XXX-###]
Test Name: [Name]

Result: [ ] PASS [ ] FAIL

Observations:
- Expected: [What should happen]
- Actual: [What actually happened]
- Variance: [Any differences]

Timestamp: [Date/Time]
Tester: [Name]
Notes: [Additional observations]
```

---

## Appendix: Debug Commands

Enable debug mode in config or use these commands:

```bash
# Spawn specific number of enemies
spawn npc slime count=5

# Check combat state
check

# Enable debug logging
debug_ai_decisions on
debug_positions on
debug_movement on
```

---

**Document Version**: 1.0  
**Last Updated**: October 31, 2025  
**Status**: Ready for UAT Execution
