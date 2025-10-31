# Phase 4: Manual Combat Testing Checklist

**Date Created:** October 30, 2025  
**Status:** Ready for Execution  
**Test Environment:** Development Config with Testing Map  

---

## Overview

Phase 4 validates the coordinate-based combat positioning system through live game execution, NPC AI integration, and performance analysis.

---

## Pre-Test Setup

### ✅ Prerequisites Verification

- [ ] All Phase 3 tests passing (545/545) ✅
- [ ] No blocking issues in codebase
- [ ] `testing-map.json` loaded and accessible
- [ ] Development config (`config_dev.ini`) configured
- [ ] No active save file conflicts
- [ ] Python environment active
- [ ] Git branch: `HV-1-coordinate-combat-positioning`

### 🔧 Environment Setup

```bash
# Activate Python environment
.venv\Scripts\Activate.ps1

# Start game with dev config
python src/game.py
```

---

## Test Categories

### Category A: Combat Initialization & Positioning

#### A1: Standard Scenario Spawning
- [ ] **Test:** Start combat (standard scenario)
- [ ] **Verify:** Player spawns at correct position
- [ ] **Verify:** Enemies spawn in formation
- [ ] **Verify:** All units within grid bounds (0-50)
- [ ] **Verify:** Facing directions assigned to all units
- [ ] **Expected:** No errors, clean initialization
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### A2: Player Position Display
- [ ] **Test:** Check player combat position in debug
- [ ] **Verify:** X coordinate 0-50
- [ ] **Verify:** Y coordinate 0-50
- [ ] **Verify:** Facing direction set correctly
- [ ] **Verify:** Position updates during movement
- [ ] **Expected:** Accurate coordinate tracking
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### A3: Enemy Position Display
- [ ] **Test:** Inspect first enemy position
- [ ] **Verify:** X and Y coordinates valid
- [ ] **Verify:** Facing direction correct
- [ ] **Verify:** Distance calculation accurate
- [ ] **Expected:** All enemies properly positioned
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### A4: Formation Validation
- [ ] **Test:** Check enemy formation spacing
- [ ] **Verify:** Minimum spacing maintained (2 units)
- [ ] **Verify:** No unit overlaps
- [ ] **Verify:** Formation type matches scenario
- [ ] **Expected:** Valid formation layout
- [ ] **Log Result:** ✅ / ❌ / Notes:

---

### Category B: Movement Mechanics

#### B1: Advance Move
- [ ] **Test:** Execute Advance toward nearest enemy
- [ ] **Verify:** Player moves 2-4 squares closer
- [ ] **Verify:** Distance decreases
- [ ] **Verify:** Facing direction updated
- [ ] **Verify:** No grid boundary violations
- [ ] **Verify:** Combat log shows movement
- [ ] **Expected:** Smooth advance animation/message
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### B2: Withdraw Move
- [ ] **Test:** Execute Withdraw (move away)
- [ ] **Verify:** Player moves 2-3 squares away
- [ ] **Verify:** Distance increases
- [ ] **Verify:** Facing remains defensive
- [ ] **Verify:** Position clamped at edges
- [ ] **Verify:** Combat log shows withdrawal
- [ ] **Expected:** Strategic retreat message
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### B3: BullCharge Move
- [ ] **Test:** Execute BullCharge at medium range
- [ ] **Verify:** Player moves 4-6 squares
- [ ] **Verify:** Significant distance reduction
- [ ] **Verify:** Aggressive positioning achieved
- [ ] **Verify:** No overshooting off grid
- [ ] **Expected:** Charge message with distance
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### B4: TacticalRetreat Move
- [ ] **Test:** Execute TacticalRetreat with multiple enemies
- [ ] **Verify:** Moves away from nearest threat
- [ ] **Verify:** Retreats 3-4 squares
- [ ] **Verify:** Defensive stance maintained
- [ ] **Verify:** All threats at increased distance
- [ ] **Expected:** Strategic retreat confirmation
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### B5: FlankingManeuver Move
- [ ] **Test:** Execute flanking move
- [ ] **Verify:** Player moves perpendicular to enemy
- [ ] **Verify:** Attack angle 45-135 degrees
- [ ] **Verify:** Combat log shows flanking bonus
- [ ] **Verify:** Flanking damage modifier applied (+15-40%)
- [ ] **Expected:** Flanking bonus message and damage increase
- [ ] **Log Result:** ✅ / ❌ / Notes:

---

### Category C: Distance & Angle Calculations

#### C1: Distance Calculation Accuracy
- [ ] **Test:** Move to known position, verify distance
- [ ] **Verify:** Combat proximity dict updated
- [ ] **Verify:** Distance matches coordinate delta
- [ ] **Verify:** Multiple enemy distances correct
- [ ] **Expected:** ±0.5 foot accuracy
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### C2: Angle Calculation Accuracy
- [ ] **Test:** Position at different angles to enemy
- [ ] **Verify:** Attack angle calculated correctly
- [ ] **Verify:** Facing direction honored
- [ ] **Verify:** 0-360 degree range maintained
- [ ] **Expected:** Correct angle for each position
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### C3: Facing Direction Updates
- [ ] **Test:** Execute moves toward different targets
- [ ] **Verify:** Facing updates to face target
- [ ] **Verify:** 8-direction compass used
- [ ] **Verify:** Facing persists when stationary
- [ ] **Expected:** Smooth facing transitions
- [ ] **Log Result:** ✅ / ❌ / Notes:

---

### Category D: Damage & Accuracy Modifiers

#### D1: Frontal Attack Bonus
- [ ] **Test:** Attack enemy from front (0-45°)
- [ ] **Verify:** Damage modifier 0.85x (-15%)
- [ ] **Verify:** Accuracy modifier 0.95x (-5%)
- [ ] **Verify:** Reduced damage in log
- [ ] **Expected:** -15% damage from front
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### D2: Flanking Attack Bonus
- [ ] **Test:** Position at 45-90° angle, attack
- [ ] **Verify:** Damage modifier 1.15x (+15%)
- [ ] **Verify:** Accuracy modifier 1.10x (+10%)
- [ ] **Verify:** Increased damage in combat log
- [ ] **Expected:** +15% damage from flank
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### D3: Deep Flank Bonus
- [ ] **Test:** Position at 90-135°, execute attack
- [ ] **Verify:** Damage modifier 1.25x (+25%)
- [ ] **Verify:** Accuracy modifier 1.20x (+20%)
- [ ] **Verify:** Significant damage increase
- [ ] **Expected:** +25% damage bonus
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### D4: Rear Attack Bonus
- [ ] **Test:** Get behind enemy (135-180°), attack
- [ ] **Verify:** Damage modifier 1.40x (+40%)
- [ ] **Verify:** Accuracy modifier 1.30x (+30%)
- [ ] **Verify:** Maximum bonus applied
- [ ] **Expected:** +40% damage from rear
- [ ] **Log Result:** ✅ / ❌ / Notes:

---

### Category E: Combat Scenarios

#### E1: Standard Scenario
- [ ] **Test:** Start combat in standard formation
- [ ] **Verify:** Player and enemies facing each other
- [ ] **Verify:** Initial distance reasonable (~20-30 feet)
- [ ] **Verify:** All units spawned correctly
- [ ] **Expected:** Line vs line formation
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### E2: Pincer Scenario
- [ ] **Test:** Trigger pincer ambush
- [ ] **Verify:** Enemies flank from multiple angles
- [ ] **Verify:** Player surrounded by multiple foes
- [ ] **Verify:** Flanking bonuses potential
- [ ] **Expected:** Ambush formation active
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### E3: Melee Scenario
- [ ] **Test:** Start chaotic melee
- [ ] **Verify:** All units close together
- [ ] **Verify:** High flanking potential
- [ ] **Verify:** Tactical positioning important
- [ ] **Expected:** Close quarters combat
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### E4: Boss Arena
- [ ] **Test:** Face single powerful enemy
- [ ] **Verify:** Boss spawns with high stats
- [ ] **Verify:** Wide open arena for movement
- [ ] **Verify:** Large distances possible
- [ ] **Expected:** 1v1 combat scenario
- [ ] **Log Result:** ✅ / ❌ / Notes:

---

### Category F: Backward Compatibility

#### F1: Legacy Distance Dict
- [ ] **Test:** Check combat_proximity dict during combat
- [ ] **Verify:** Distance values present
- [ ] **Verify:** Match coordinate-based distances
- [ ] **Verify:** Updated after each move
- [ ] **Expected:** Transparent dual-system operation
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### F2: Old Move Execution Path
- [ ] **Test:** Verify fallback execution active
- [ ] **Verify:** Both coordinate and legacy paths work
- [ ] **Verify:** Results consistent
- [ ] **Expected:** Seamless fallback
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### F3: No Breaking Changes
- [ ] **Test:** All existing moves still work
- [ ] **Verify:** Attack, Rest, Wait functional
- [ ] **Verify:** All original features present
- [ ] **Expected:** Existing combat unchanged
- [ ] **Log Result:** ✅ / ❌ / Notes:

---

### Category G: Performance & Stability

#### G1: Combat Frame Rate
- [ ] **Test:** Monitor FPS during active combat
- [ ] **Verify:** No significant drops
- [ ] **Verify:** Smooth animation/rendering
- [ ] **Verify:** No lag during movement
- [ ] **Expected:** 30+ FPS maintained
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### G2: Memory Usage
- [ ] **Test:** Monitor memory during 10+ round combat
- [ ] **Verify:** No memory leaks
- [ ] **Verify:** Stable memory footprint
- [ ] **Verify:** No crashes or disconnects
- [ ] **Expected:** <500MB stable memory
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### G3: Position Calculation Speed
- [ ] **Test:** Time combat round completion
- [ ] **Verify:** Calculations complete quickly
- [ ] **Verify:** No noticeable delay
- [ ] **Verify:** Multiple moves fast
- [ ] **Expected:** <50ms per calculation
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### G4: Long Combat Session
- [ ] **Test:** Run 20+ round combat
- [ ] **Verify:** No crashes or errors
- [ ] **Verify:** Positioning stable
- [ ] **Verify:** AI responsive
- [ ] **Expected:** Stable long-term gameplay
- [ ] **Log Result:** ✅ / ❌ / Notes:

---

### Category H: NPC AI Integration

#### H1: NPC Movement Decisions
- [ ] **Test:** Watch NPC movement choices
- [ ] **Verify:** NPCs use new movement moves
- [ ] **Verify:** Tactical decisions logical
- [ ] **Verify:** Positioning improvements visible
- [ ] **Expected:** Improved enemy tactics
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### H2: NPC Flanking Attempts
- [ ] **Test:** Observe NPC flanking behavior
- [ ] **Verify:** NPCs attempt flanking
- [ ] **Verify:** Flank damage bonuses applied
- [ ] **Verify:** AI uses positioning advantage
- [ ] **Expected:** Smart flanking tactics
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### H3: NPC Retreat Behavior
- [ ] **Test:** Watch NPC retreat decisions
- [ ] **Verify:** Low-health NPCs retreat
- [ ] **Verify:** Tactical retreat used appropriately
- [ ] **Verify:** AI spacing maintained
- [ ] **Expected:** Defensive AI behavior
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### H4: Multi-Enemy Coordination
- [ ] **Test:** Monitor multiple enemies
- [ ] **Verify:** Coordination between enemies
- [ ] **Verify:** Flanking from multiple angles
- [ ] **Verify:** No friendly fire concerns
- [ ] **Expected:** Coordinated enemy tactics
- [ ] **Log Result:** ✅ / ❌ / Notes:

---

### Category I: Error Handling

#### I1: Invalid Position Rejection
- [ ] **Test:** Force invalid position creation
- [ ] **Verify:** System rejects or clamps
- [ ] **Verify:** Error logged appropriately
- [ ] **Verify:** Combat continues
- [ ] **Expected:** Graceful error handling
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### I2: Out-of-Bounds Movement
- [ ] **Test:** Move toward boundary
- [ ] **Verify:** Position clamped at edge
- [ ] **Verify:** No crash or undefined behavior
- [ ] **Verify:** Combat continues
- [ ] **Expected:** Smooth boundary enforcement
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### I3: Dead Unit Handling
- [ ] **Test:** Kill unit, verify positioning
- [ ] **Verify:** Dead unit removed from combat
- [ ] **Verify:** Other units unaffected
- [ ] **Verify:** No reference errors
- [ ] **Expected:** Clean dead unit removal
- [ ] **Log Result:** ✅ / ❌ / Notes:

#### I4: Missing Position Data
- [ ] **Test:** Check fallback when position unavailable
- [ ] **Verify:** Legacy system activates
- [ ] **Verify:** Combat continues
- [ ] **Verify:** Error gracefully handled
- [ ] **Expected:** Seamless fallback
- [ ] **Log Result:** ✅ / ❌ / Notes:

---

## Test Execution Log

### Session Information

**Date:** ___________  
**Tester:** ___________  
**Duration:** ___________  
**Environment:** Testing Map + Dev Config  

### Issues Found

#### Issue #1
- **Category:** _________
- **Description:** _________
- **Severity:** ☐ Critical ☐ High ☐ Medium ☐ Low
- **Steps to Reproduce:** _________
- **Expected Result:** _________
- **Actual Result:** _________
- **Status:** ☐ New ☐ Fixed ☐ Blocked

#### Issue #2
- **Category:** _________
- **Description:** _________
- **Severity:** ☐ Critical ☐ High ☐ Medium ☐ Low
- **Steps to Reproduce:** _________
- **Expected Result:** _________
- **Actual Result:** _________
- **Status:** ☐ New ☐ Fixed ☐ Blocked

---

## Summary & Sign-Off

### Test Statistics

- **Total Tests:** _____ / 40+ categories
- **Passed:** _____ 
- **Failed:** _____
- **Blocked:** _____
- **Pass Rate:** _____%

### Recommendations

_[Space for tester notes and recommendations]_

---

### Sign-Off

**Tested By:** ___________  
**Date:** ___________  
**Status:** ☐ PASS ☐ FAIL ☐ CONDITIONAL PASS  

**Notes:**

---

## Test Execution Commands

### Start Game with Testing Map

```bash
# Activate environment
.venv\Scripts\Activate.ps1

# Start game (config_dev.ini will load testing-map)
python src/game.py
```

### Debug Commands (in-game)

```
# View player position
debug_pos  # (if available)

# View enemy positions
debug_enemies  # (if available)

# Show distance calculations
debug_distances  # (if available)

# Display facing directions
debug_facing  # (if available)
```

### Monitor Performance

```bash
# Run performance profiler
python -m cProfile -s cumtime src/game.py
```

---

## Reference: Coordinate System

**Grid Dimensions:** 50×50 coordinate space  
**Directions:** N(0°), NE(45°), E(90°), SE(135°), S(180°), SW(225°), W(270°), NW(315°)  
**Distance Metric:** Euclidean distance in feet  

**Move Distances:**
- Advance: 2-4 squares
- Withdraw: 2-3 squares
- BullCharge: 4-6 squares
- TacticalRetreat: 3-4 squares
- FlankingManeuver: 2-4 squares

**Damage Modifiers:**
- Front (0-45°): 0.85x
- Flank (45-90°): 1.15x
- Deep Flank (90-135°): 1.25x
- Rear (135-180°): 1.40x

---

**Last Updated:** October 30, 2025  
**Version:** Phase 4 Ready
